import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secretbase/src/features/update/mobile_update_download.dart';

void main() {
  test('已有部分文件时通过 Range 继续下载', () async {
    final root = await Directory.systemTemp.createTemp('secretbase-range-');
    addTearDown(() => root.delete(recursive: true));
    final target = File('${root.path}/update.apk.part');
    final bytes = List<int>.generate(32, (index) => index);
    await target.writeAsBytes(bytes.sublist(0, 11));
    final client = MockClient((request) async {
      expect(request.headers['range'], 'bytes=11-');
      return http.Response.bytes(
        bytes.sublist(11),
        HttpStatus.partialContent,
        headers: {'content-range': 'bytes 11-31/32'},
      );
    });
    final downloader = MobileUpdateDownloader(client: client, maxAttempts: 1);

    await downloader.download(
      url: Uri.parse('https://example.test/update.apk'),
      temporary: target,
      expectedSize: bytes.length,
      userAgent: 'SecretBase/test',
      cancellation: DownloadCancellation(),
      onProgress: (_, _) {},
    );

    expect(await target.readAsBytes(), bytes);
  });

  test('服务器忽略 Range 时自动覆盖部分文件', () async {
    final root = await Directory.systemTemp.createTemp('secretbase-range-');
    addTearDown(() => root.delete(recursive: true));
    final target = File('${root.path}/update.apk.part');
    final bytes = List<int>.generate(24, (index) => index + 1);
    await target.writeAsBytes(bytes.sublist(0, 7));
    final client = MockClient((request) async {
      expect(request.headers['range'], 'bytes=7-');
      return http.Response.bytes(bytes, HttpStatus.ok);
    });
    final downloader = MobileUpdateDownloader(client: client, maxAttempts: 1);

    await downloader.download(
      url: Uri.parse('https://example.test/update.apk'),
      temporary: target,
      expectedSize: bytes.length,
      userAgent: 'SecretBase/test',
      cancellation: DownloadCancellation(),
      onProgress: (_, _) {},
    );

    expect(await target.readAsBytes(), bytes);
  });

  test('网络中断时保留已经写入的部分文件', () async {
    final root = await Directory.systemTemp.createTemp('secretbase-range-');
    addTearDown(() => root.delete(recursive: true));
    final target = File('${root.path}/update.apk.part');
    final client = _StreamingClient((request) async {
      final stream = Stream<List<int>>.multi((events) {
        events.add(const [1, 2, 3, 4]);
        events.addError(const SocketException('offline'));
        events.close();
      });
      return http.StreamedResponse(stream, HttpStatus.ok);
    });
    final downloader = MobileUpdateDownloader(client: client, maxAttempts: 1);

    await expectLater(
      downloader.download(
        url: Uri.parse('https://example.test/update.apk'),
        temporary: target,
        expectedSize: 8,
        userAgent: 'SecretBase/test',
        cancellation: DownloadCancellation(),
        onProgress: (_, _) {},
      ),
      throwsA(
        isA<MobileUpdateDownloadFailure>().having(
          (error) => error.message,
          'message',
          contains('已保留下载进度'),
        ),
      ),
    );
    expect(await target.readAsBytes(), const [1, 2, 3, 4]);
  });

  test('服务器拒绝续传后会清理部分文件并完整重试', () async {
    final root = await Directory.systemTemp.createTemp('secretbase-range-');
    addTearDown(() => root.delete(recursive: true));
    final target = File('${root.path}/update.apk.part');
    final bytes = List<int>.generate(18, (index) => index + 3);
    await target.writeAsBytes(bytes.sublist(0, 5));
    var calls = 0;
    final client = MockClient((request) async {
      calls += 1;
      if (calls == 1) {
        expect(request.headers['range'], 'bytes=5-');
        return http.Response('', HttpStatus.requestedRangeNotSatisfiable);
      }
      expect(request.headers.containsKey('range'), isFalse);
      return http.Response.bytes(bytes, HttpStatus.ok);
    });
    final downloader = MobileUpdateDownloader(
      client: client,
      maxAttempts: 2,
      retryDelays: const [Duration.zero],
    );

    await downloader.download(
      url: Uri.parse('https://example.test/update.apk'),
      temporary: target,
      expectedSize: bytes.length,
      userAgent: 'SecretBase/test',
      cancellation: DownloadCancellation(),
      onProgress: (_, _) {},
    );

    expect(calls, 2);
    expect(await target.readAsBytes(), bytes);
  });

  test('网络流无响应时暂停操作会立即返回并保留进度', () async {
    final root = await Directory.systemTemp.createTemp('secretbase-range-');
    addTearDown(() => root.delete(recursive: true));
    final target = File('${root.path}/update.apk.part');
    await target.writeAsBytes(const [1, 2, 3, 4]);
    final stream = StreamController<List<int>>();
    addTearDown(stream.close);
    final client = _StreamingClient((request) async {
      expect(request.headers['range'], 'bytes=4-');
      return http.StreamedResponse(
        stream.stream,
        HttpStatus.partialContent,
        headers: {'content-range': 'bytes 4-7/8'},
      );
    });
    final cancellation = DownloadCancellation();
    final downloader = MobileUpdateDownloader(
      client: client,
      maxAttempts: 1,
      idleTimeout: const Duration(minutes: 5),
    );
    final stopwatch = Stopwatch()..start();
    final result = downloader.download(
      url: Uri.parse('https://example.test/update.apk'),
      temporary: target,
      expectedSize: 8,
      userAgent: 'SecretBase/test',
      cancellation: cancellation,
      onProgress: (_, _) {},
    );

    await Future<void>.delayed(const Duration(milliseconds: 20));
    cancellation.cancel();

    await expectLater(
      result,
      throwsA(
        isA<MobileUpdateDownloadFailure>().having(
          (error) => error.message,
          'message',
          allOf(contains('已暂停'), contains('已保留下载进度')),
        ),
      ),
    );
    stopwatch.stop();
    expect(stopwatch.elapsed, lessThan(const Duration(seconds: 1)));
    expect(await target.readAsBytes(), const [1, 2, 3, 4]);
  });
}

class _StreamingClient extends http.BaseClient {
  _StreamingClient(this.handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request)
  handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    return handler(request);
  }
}
