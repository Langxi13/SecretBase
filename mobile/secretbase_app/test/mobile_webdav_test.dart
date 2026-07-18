import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secretbase/src/features/sync/mobile_webdav.dart';

const _baseUrl = 'https://dav.example.test/dav/secretbase';

String _propfindResponse() => '''<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/dav/secretbase/secretbase-sync-v2/vault/space/snapshots/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/secretbase/secretbase-sync-v2/vault/space/snapshots/device-a/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/secretbase/secretbase-sync-v2/vault/space/snapshots/device-b/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/secretbase/secretbase-sync-v2/vault/space/snapshots/1-a.sbs</d:href>
    <d:propstat><d:prop>
      <d:resourcetype/>
      <d:getcontentlength>7</d:getcontentlength>
    </d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/secretbase/secretbase-sync-v2/vault/space/snapshots/device-a/1-nested.sbs</d:href>
    <d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat>
  </d:response>
</d:multistatus>''';

void main() {
  test('解析 DAV 命名空间并只返回目录的直接子项', () async {
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async {
        expect(request.method, 'PROPFIND');
        expect(request.headers['depth'], '1');
        expect(
          request.url.toString(),
          'https://dav.example.test/dav/secretbase/secretbase-sync-v2/vault/space/snapshots',
        );
        return http.Response(
          _propfindResponse(),
          207,
          headers: {'content-type': 'application/xml; charset=utf-8'},
        );
      }),
    );
    addTearDown(client.close);

    final children = await client.listChildren([
      'secretbase-sync-v2',
      'vault',
      'space',
      'snapshots',
    ]);
    expect(children.map((item) => item.name), [
      '1-a.sbs',
      'device-a',
      'device-b',
    ]);
    expect(children.first.collection, isFalse);
    expect(children.first.contentLength, 7);
    expect(children.skip(1).every((item) => item.collection), isTrue);
  });

  test('无 ETag 时可以写入并逐字节校验', () async {
    final requests = <String>[];
    final body = Uint8List.fromList(utf8.encode('snapshot-content'));
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async {
        requests.add(request.method);
        if (request.method == 'PUT') return http.Response('', 201);
        if (request.method == 'GET') {
          return http.Response.bytes(body, 200);
        }
        throw StateError('unexpected request');
      }),
    );
    addTearDown(client.close);

    await client.put(['snapshot.sbs'], body);
    await client.verifyStored(['snapshot.sbs'], body);
    expect(requests, ['PUT', 'GET']);
  });

  test('临时 503 会退避重试，最终返回成功响应', () async {
    var calls = 0;
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async {
        calls++;
        if (calls < 3) return http.Response('', 503);
        return http.Response.bytes(Uint8List.fromList([1, 2, 3]), 200);
      }),
    );
    addTearDown(client.close);

    final object = await client.get(['snapshot.sbs']);
    expect(object?.content, [1, 2, 3]);
    expect(calls, 3);
  });

  test('可选读取遇到 404 返回空对象', () async {
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async => http.Response('', 404)),
    );
    addTearDown(client.close);

    expect(await client.get(['missing.sbs'], optional: true), isNull);
  });

  test('畸形 PROPFIND XML 返回可识别的同步错误', () async {
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async => http.Response('<broken>', 207)),
    );
    addTearDown(client.close);

    expect(
      () => client.listChildren(['root']),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'WEBDAV_LIST_INVALID',
        ),
      ),
    );
  });

  test('拒绝不安全的公网 HTTP WebDAV 地址', () {
    expect(
      () => MobileWebDavClient(
        baseUrl: 'http://dav.example.test/root',
        username: 'user',
        password: 'app-password',
      ),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'INSECURE_WEBDAV_URL',
        ),
      ),
    );
  });

  test('拒绝在 WebDAV 地址中内嵌账号信息', () {
    expect(
      () => MobileWebDavClient(
        baseUrl: 'https://embedded:secret@dav.example.test/root',
        username: 'user',
        password: 'app-password',
      ),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'INVALID_WEBDAV_URL',
        ),
      ),
    );
  });

  test('PROPFIND 声明超大响应时在解析前停止读取', () async {
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient(
        (request) async => http.Response(
          '<d:multistatus xmlns:d="DAV:"/>',
          207,
          headers: {'content-length': '${5 * 1024 * 1024}'},
        ),
      ),
    );
    addTearDown(client.close);

    expect(
      () => client.listChildren(['root']),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'WEBDAV_RESPONSE_TOO_LARGE',
        ),
      ),
    );
  });

  test('清理同步空间遇到未知对象时停止且不发送删除请求', () async {
    var deleteCalls = 0;
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async {
        if (request.method == 'DELETE') {
          deleteCalls++;
          return http.Response('', 204);
        }
        return http.Response('''<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:">
  <d:response><d:href>${request.url.path}/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
  <d:response><d:href>${request.url.path}/notes.txt</d:href><d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat></d:response>
</d:multistatus>''', 207);
      }),
    );
    addTearDown(client.close);

    await expectLater(
      client.deleteV2Space('vault', 'space'),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'WEBDAV_DELETE_FAILED',
        ),
      ),
    );
    expect(deleteCalls, 0);
  });

  test('客户端关闭后立即拒绝新的同步请求', () async {
    final client = MobileWebDavClient(
      baseUrl: _baseUrl,
      username: 'user',
      password: 'app-password',
      client: MockClient((request) async => http.Response('', 200)),
    );
    client.close();

    await expectLater(
      client.get(['snapshot.sbs']),
      throwsA(
        isA<MobileWebDavException>().having(
          (error) => error.code,
          'code',
          'SYNC_CANCELLED',
        ),
      ),
    );
  });
}
