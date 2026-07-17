import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

class DownloadCancellation {
  bool _cancelled = false;
  final Completer<void> _signal = Completer<void>();

  bool get cancelled => _cancelled;
  Future<void> get whenCancelled => _signal.future;

  void cancel() {
    if (_cancelled) return;
    _cancelled = true;
    _signal.complete();
  }
}

class MobileUpdateDownloadFailure implements Exception {
  const MobileUpdateDownloadFailure(this.message, {this.partialBytes = 0});

  final String message;
  final int partialBytes;

  @override
  String toString() => message;
}

class MobileUpdateDownloader {
  const MobileUpdateDownloader({
    required this.client,
    this.requestTimeout = const Duration(seconds: 60),
    this.idleTimeout = const Duration(seconds: 120),
    this.maxAttempts = 3,
    this.retryDelays = const [
      Duration(seconds: 1),
      Duration(seconds: 3),
      Duration(seconds: 7),
    ],
  }) : assert(maxAttempts > 0);

  final http.Client client;
  final Duration requestTimeout;
  final Duration idleTimeout;
  final int maxAttempts;
  final List<Duration> retryDelays;

  Future<int> download({
    required Uri url,
    required File temporary,
    required int expectedSize,
    required String userAgent,
    required DownloadCancellation cancellation,
    required void Function(int downloaded, int total) onProgress,
    bool restart = false,
  }) async {
    if (restart) await _deleteIfExists(temporary);
    await temporary.parent.create(recursive: true);
    await _sanitizePartial(temporary, expectedSize);

    for (var attempt = 0; attempt < maxAttempts; attempt += 1) {
      if (cancellation.cancelled) {
        throw await _failure(temporary, '更新下载已暂停', preserveHint: true);
      }
      try {
        return await _downloadAttempt(
          url: url,
          temporary: temporary,
          expectedSize: expectedSize,
          userAgent: userAgent,
          cancellation: cancellation,
          onProgress: onProgress,
        );
      } on _RestartDownload {
        await _deleteIfExists(temporary);
        if (attempt + 1 >= maxAttempts) {
          throw const MobileUpdateDownloadFailure('更新服务器拒绝了续传，请稍后重试');
        }
      } on _CorruptDownload catch (error) {
        await _deleteIfExists(temporary);
        if (attempt + 1 >= maxAttempts) {
          throw MobileUpdateDownloadFailure(error.message);
        }
      } on _CancelledDownload {
        throw await _failure(temporary, '更新下载已暂停', preserveHint: true);
      } on HandshakeException {
        throw await _failure(
          temporary,
          '更新下载的 HTTPS 证书验证失败，请检查系统时间、VPN 或代理证书',
          preserveHint: true,
        );
      } on TimeoutException {
        if (attempt + 1 >= maxAttempts) {
          throw await _failure(
            temporary,
            '更新下载超时，请检查网络后重试',
            preserveHint: true,
          );
        }
      } on SocketException {
        if (attempt + 1 >= maxAttempts) {
          throw await _failure(
            temporary,
            '无法连接更新下载服务，请检查网络、DNS 或 VPN',
            preserveHint: true,
          );
        }
      } on http.ClientException {
        if (attempt + 1 >= maxAttempts) {
          throw await _failure(
            temporary,
            '更新下载连接失败，请检查网络后重试',
            preserveHint: true,
          );
        }
      } on FileSystemException {
        throw await _failure(
          temporary,
          '无法写入更新缓存，请检查设备剩余空间',
          preserveHint: true,
        );
      } on _RetryableDownload catch (error) {
        if (attempt + 1 >= maxAttempts) {
          throw await _failure(temporary, error.message, preserveHint: true);
        }
      } on MobileUpdateDownloadFailure {
        rethrow;
      }

      await _waitBeforeRetry(attempt, cancellation);
    }
    throw await _failure(temporary, '更新下载失败，请稍后重试', preserveHint: true);
  }

  Future<int> _downloadAttempt({
    required Uri url,
    required File temporary,
    required int expectedSize,
    required String userAgent,
    required DownloadCancellation cancellation,
    required void Function(int downloaded, int total) onProgress,
  }) async {
    var existing = await _partialLength(temporary);
    if (existing == expectedSize) {
      onProgress(existing, expectedSize);
      return existing;
    }

    final request = http.Request('GET', url)..headers['User-Agent'] = userAgent;
    if (existing > 0) request.headers['Range'] = 'bytes=$existing-';
    final response = await Future.any<http.StreamedResponse>([
      client.send(request).timeout(requestTimeout),
      cancellation.whenCancelled.then<http.StreamedResponse>(
        (_) => throw const _CancelledDownload(),
      ),
    ]);

    var mode = existing > 0 ? FileMode.append : FileMode.write;
    if (response.statusCode == HttpStatus.ok) {
      if (existing > 0) {
        await _deleteIfExists(temporary);
        existing = 0;
        mode = FileMode.write;
      }
    } else if (response.statusCode == HttpStatus.partialContent) {
      _validateContentRange(
        response.headers['content-range'],
        expectedStart: existing,
        expectedSize: expectedSize,
      );
    } else if (response.statusCode == HttpStatus.forbidden ||
        response.statusCode == HttpStatus.requestedRangeNotSatisfiable) {
      await _discard(response);
      throw const _RestartDownload();
    } else if (response.statusCode == HttpStatus.tooManyRequests ||
        response.statusCode >= 500) {
      await _discard(response);
      throw _RetryableDownload('更新下载失败：HTTP ${response.statusCode}');
    } else {
      await _discard(response);
      throw MobileUpdateDownloadFailure(
        '更新下载失败：HTTP ${response.statusCode}',
        partialBytes: existing,
      );
    }

    var downloaded = existing;
    onProgress(downloaded, expectedSize);
    final output = temporary.openWrite(mode: mode);
    final streamDone = Completer<void>();
    late final StreamSubscription<List<int>> subscription;
    subscription = response.stream
        .timeout(idleTimeout)
        .listen(
          (chunk) {
            if (cancellation.cancelled) {
              if (!streamDone.isCompleted) {
                streamDone.completeError(const _CancelledDownload());
              }
              unawaited(subscription.cancel());
              return;
            }
            downloaded += chunk.length;
            if (downloaded > expectedSize) {
              if (!streamDone.isCompleted) {
                streamDone.completeError(const _CorruptDownload('更新文件超过清单大小'));
              }
              unawaited(subscription.cancel());
              return;
            }
            output.add(chunk);
            onProgress(downloaded, expectedSize);
          },
          onError: (Object error, StackTrace stackTrace) {
            if (!streamDone.isCompleted) {
              streamDone.completeError(error, stackTrace);
            }
          },
          onDone: () {
            if (!streamDone.isCompleted) streamDone.complete();
          },
          cancelOnError: true,
        );
    unawaited(
      cancellation.whenCancelled.then((_) async {
        await subscription.cancel();
        if (!streamDone.isCompleted) {
          streamDone.completeError(const _CancelledDownload());
        }
      }),
    );
    try {
      await streamDone.future;
      await output.flush();
    } finally {
      await subscription.cancel();
      await output.close();
    }
    if (cancellation.cancelled) throw const _CancelledDownload();
    if (downloaded != expectedSize) {
      throw const _RetryableDownload('更新连接提前中断，请重试');
    }
    return downloaded;
  }

  static void _validateContentRange(
    String? value, {
    required int expectedStart,
    required int expectedSize,
  }) {
    final match = RegExp(
      r'^bytes (\d+)-(\d+)/(\d+)$',
      caseSensitive: false,
    ).firstMatch(value?.trim() ?? '');
    if (match == null) {
      throw const _RestartDownload();
    }
    final start = int.tryParse(match.group(1)!);
    final end = int.tryParse(match.group(2)!);
    final total = int.tryParse(match.group(3)!);
    if (start != expectedStart ||
        end == null ||
        end < expectedStart ||
        total != expectedSize ||
        end >= expectedSize) {
      throw const _RestartDownload();
    }
  }

  static Future<void> _sanitizePartial(File file, int expectedSize) async {
    final length = await _partialLength(file);
    if (length > expectedSize) await _deleteIfExists(file);
  }

  static Future<int> _partialLength(File file) async {
    try {
      return await file.exists() ? await file.length() : 0;
    } catch (_) {
      return 0;
    }
  }

  static Future<void> _discard(http.StreamedResponse response) async {
    try {
      await response.stream.drain<void>();
    } catch (_) {
      // The response is already unusable; draining only helps connection reuse.
    }
  }

  Future<void> _waitBeforeRetry(
    int attempt,
    DownloadCancellation cancellation,
  ) async {
    final index = attempt < retryDelays.length
        ? attempt
        : retryDelays.length - 1;
    final delay = retryDelays.isEmpty ? Duration.zero : retryDelays[index];
    if (delay > Duration.zero) {
      await Future.any<void>([
        Future<void>.delayed(delay),
        cancellation.whenCancelled,
      ]);
    }
  }

  static Future<MobileUpdateDownloadFailure> _failure(
    File temporary,
    String message, {
    required bool preserveHint,
  }) async {
    final partialBytes = await _partialLength(temporary);
    final hint = preserveHint && partialBytes > 0 ? '；已保留下载进度，重试时将继续' : '';
    return MobileUpdateDownloadFailure(
      '$message$hint',
      partialBytes: partialBytes,
    );
  }

  static Future<void> _deleteIfExists(File file) async {
    try {
      if (await file.exists()) await file.delete();
    } catch (_) {
      // Cache cleanup is best effort; the download error remains actionable.
    }
  }
}

class _RetryableDownload implements Exception {
  const _RetryableDownload(this.message);

  final String message;
}

class _RestartDownload implements Exception {
  const _RestartDownload();
}

class _CancelledDownload implements Exception {
  const _CancelledDownload();
}

class _CorruptDownload implements Exception {
  const _CorruptDownload(this.message);

  final String message;
}
