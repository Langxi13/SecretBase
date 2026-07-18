import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:xml/xml.dart';

class MobileWebDavException implements Exception {
  const MobileWebDavException(this.code, this.message, {this.statusCode});

  final String code;
  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class MobileWebDavChild {
  const MobileWebDavChild({
    required this.name,
    required this.collection,
    this.contentLength = 0,
  });

  final String name;
  final bool collection;
  final int contentLength;
}

class MobileWebDavObject {
  const MobileWebDavObject(this.content);

  final Uint8List content;
}

class MobileWebDavClient {
  MobileWebDavClient({
    required String baseUrl,
    required String username,
    required String password,
    http.Client? client,
  }) : _client = client ?? http.Client(),
       _username = username,
       _password = password,
       baseUri = _normalize(baseUrl) {
    if (username.trim().isEmpty || password.isEmpty) {
      throw const MobileWebDavException(
        'WEBDAV_CREDENTIALS_REQUIRED',
        '请输入 WebDAV 用户名和应用密码',
      );
    }
    _activeClients.add(this);
  }

  static const _maxObjectBytes = 64 * 1024 * 1024;
  static const _maxPropfindBytes = 4 * 1024 * 1024;
  static const _maxControlResponseBytes = 1024 * 1024;
  static const _retryStatuses = {408, 425, 429, 500, 502, 503, 504};
  static final Set<MobileWebDavClient> _activeClients = {};

  final Uri baseUri;
  final http.Client _client;
  final String _username;
  final String _password;
  bool _closed = false;

  static Uri _normalize(String value) {
    final parsed = Uri.tryParse(value.trim());
    if (parsed == null ||
        parsed.host.isEmpty ||
        parsed.userInfo.isNotEmpty ||
        parsed.hasQuery ||
        parsed.hasFragment) {
      throw const MobileWebDavException('INVALID_WEBDAV_URL', 'WebDAV 地址无效');
    }
    final isLoopback = const {
      '127.0.0.1',
      'localhost',
      '::1',
    }.contains(parsed.host.toLowerCase());
    if (parsed.scheme != 'https' && !(parsed.scheme == 'http' && isLoopback)) {
      throw const MobileWebDavException(
        'INSECURE_WEBDAV_URL',
        'WebDAV 必须使用 HTTPS',
      );
    }
    final path = parsed.path.replaceFirst(RegExp(r'/+$'), '');
    return parsed.replace(path: path.isEmpty ? '/' : path);
  }

  void close() {
    if (_closed) return;
    _closed = true;
    _activeClients.remove(this);
    _client.close();
  }

  static void cancelAll() {
    for (final client in _activeClients.toList()) {
      client.close();
    }
  }

  Uri _uri(List<String> segments) {
    final encoded = segments.map(Uri.encodeComponent).join('/');
    final root = baseUri.path.replaceFirst(RegExp(r'/+$'), '');
    return baseUri.replace(path: encoded.isEmpty ? root : '$root/$encoded');
  }

  Map<String, String> _headers({String? contentType, String? depth}) {
    final auth = base64Encode(utf8.encode('$_username:$_password'));
    final result = <String, String>{
      'Authorization': 'Basic $auth',
      'User-Agent': 'SecretBase-Android-Sync/2',
    };
    if (contentType != null) result['Content-Type'] = contentType;
    if (depth != null) result['Depth'] = depth;
    return result;
  }

  Future<http.Response> _request(
    String method,
    Uri uri, {
    Uint8List? body,
    Map<String, String>? headers,
    int maxResponseBytes = _maxControlResponseBytes,
  }) async {
    Object? lastError;
    for (var attempt = 0; attempt < 3; attempt++) {
      if (_closed) {
        throw const MobileWebDavException('SYNC_CANCELLED', '同步已取消');
      }
      try {
        final request = http.Request(method, uri)
          ..followRedirects = false
          ..headers.addAll({..._headers(), ...?headers});
        if (body != null) request.bodyBytes = body;
        final response = await _client
            .send(request)
            .timeout(const Duration(seconds: 35));
        final result = await _readResponse(response, maxResponseBytes);
        if (_retryStatuses.contains(result.statusCode) && attempt < 2) {
          await Future<void>.delayed(_retryDelay(result, attempt));
          continue;
        }
        if (result.statusCode >= 300 && result.statusCode < 400) {
          throw const MobileWebDavException(
            'WEBDAV_REDIRECT_REJECTED',
            'WebDAV 返回了不受信任的重定向',
          );
        }
        if (result.statusCode == 401 || result.statusCode == 403) {
          throw const MobileWebDavException(
            'WEBDAV_AUTH_FAILED',
            'WebDAV 用户名、应用密码或目录权限无效',
          );
        }
        return result;
      } on MobileWebDavException {
        rethrow;
      } on TimeoutException catch (error) {
        lastError = error;
      } on http.ClientException catch (error) {
        lastError = error;
      }
      if (attempt < 2) {
        await Future<void>.delayed(
          Duration(milliseconds: 250 * (1 << attempt)),
        );
      }
    }
    if (lastError is TimeoutException) {
      throw const MobileWebDavException(
        'WEBDAV_TIMEOUT',
        'WebDAV 请求超时，请检查网络后重试',
      );
    }
    throw const MobileWebDavException('WEBDAV_UNREACHABLE', '无法连接 WebDAV 服务');
  }

  Future<http.Response> _readResponse(
    http.StreamedResponse response,
    int maxBytes,
  ) async {
    final declared = int.tryParse(response.headers['content-length'] ?? '');
    if (declared != null && declared > maxBytes) {
      throw const MobileWebDavException(
        'WEBDAV_RESPONSE_TOO_LARGE',
        'WebDAV 响应过大，已停止读取',
      );
    }
    final bytes = BytesBuilder(copy: false);
    var length = 0;
    await for (final chunk in response.stream.timeout(
      const Duration(seconds: 35),
    )) {
      length += chunk.length;
      if (length > maxBytes) {
        throw const MobileWebDavException(
          'WEBDAV_RESPONSE_TOO_LARGE',
          'WebDAV 响应过大，已停止读取',
        );
      }
      bytes.add(chunk);
    }
    return http.Response.bytes(
      bytes.takeBytes(),
      response.statusCode,
      request: response.request,
      headers: response.headers,
      isRedirect: response.isRedirect,
      persistentConnection: response.persistentConnection,
      reasonPhrase: response.reasonPhrase,
    );
  }

  static Duration _retryDelay(http.Response response, int attempt) {
    final seconds = double.tryParse(response.headers['retry-after'] ?? '');
    if (seconds != null) {
      return Duration(milliseconds: (seconds.clamp(0, 5) * 1000).round());
    }
    return Duration(milliseconds: 250 * (1 << attempt));
  }

  Future<void> mkcol(List<String> path) async {
    final response = await _request('MKCOL', _uri(path));
    if (response.statusCode != 201 && response.statusCode != 405) {
      throw MobileWebDavException(
        'WEBDAV_MKCOL_FAILED',
        '无法创建 WebDAV 同步目录（HTTP ${response.statusCode}）',
        statusCode: response.statusCode,
      );
    }
  }

  Future<void> ensureV2Layout(
    String vaultId,
    String spaceId, [
    String? deviceId,
  ]) async {
    final paths = <List<String>>[
      ['secretbase-sync-v2'],
      ['secretbase-sync-v2', vaultId],
      ['secretbase-sync-v2', vaultId, spaceId],
      ['secretbase-sync-v2', vaultId, spaceId, 'snapshots'],
    ];
    if (deviceId != null && deviceId.isNotEmpty) {
      paths.add([
        'secretbase-sync-v2',
        vaultId,
        spaceId,
        'snapshots',
        deviceId,
      ]);
    }
    for (final path in paths) {
      await mkcol(path);
    }
  }

  Future<void> put(List<String> path, Uint8List content) async {
    if (content.length > _maxObjectBytes) {
      throw const MobileWebDavException('WEBDAV_OBJECT_TOO_LARGE', '同步对象过大');
    }
    final response = await _request(
      'PUT',
      _uri(path),
      body: content,
      headers: {'Content-Type': 'application/octet-stream'},
    );
    if (response.statusCode != 200 &&
        response.statusCode != 201 &&
        response.statusCode != 204) {
      throw MobileWebDavException(
        'WEBDAV_WRITE_FAILED',
        'WebDAV 写入失败（HTTP ${response.statusCode}）',
        statusCode: response.statusCode,
      );
    }
  }

  Future<MobileWebDavObject?> get(
    List<String> path, {
    bool optional = false,
  }) async {
    final response = await _request(
      'GET',
      _uri(path),
      maxResponseBytes: _maxObjectBytes,
    );
    if (optional && response.statusCode == 404) return null;
    if (response.statusCode != 200) {
      throw MobileWebDavException(
        'WEBDAV_READ_FAILED',
        'WebDAV 读取失败（HTTP ${response.statusCode}）',
        statusCode: response.statusCode,
      );
    }
    if (response.bodyBytes.length > _maxObjectBytes) {
      throw const MobileWebDavException('WEBDAV_OBJECT_TOO_LARGE', '同步对象过大');
    }
    return MobileWebDavObject(Uint8List.fromList(response.bodyBytes));
  }

  Future<List<MobileWebDavChild>> listChildren(
    List<String> path, {
    bool optional = false,
  }) async {
    const body =
        '<?xml version="1.0" encoding="utf-8"?><propfind xmlns="DAV:"><prop><resourcetype/><getcontentlength/></prop></propfind>';
    final response = await _request(
      'PROPFIND',
      _uri(path),
      body: Uint8List.fromList(utf8.encode(body)),
      headers: {'Depth': '1', 'Content-Type': 'application/xml; charset=utf-8'},
      maxResponseBytes: _maxPropfindBytes,
    );
    if (optional && response.statusCode == 404) return const [];
    if (response.statusCode != 200 && response.statusCode != 207) {
      throw MobileWebDavException(
        'WEBDAV_LIST_FAILED',
        'WebDAV 目录读取失败（HTTP ${response.statusCode}）',
        statusCode: response.statusCode,
      );
    }
    if (response.bodyBytes.length > _maxPropfindBytes) {
      throw const MobileWebDavException(
        'WEBDAV_DIRECTORY_TOO_LARGE',
        'WebDAV 目录响应过大',
      );
    }
    final XmlDocument document;
    try {
      document = XmlDocument.parse(utf8.decode(response.bodyBytes));
    } catch (_) {
      throw const MobileWebDavException(
        'WEBDAV_LIST_INVALID',
        'WebDAV 目录响应格式无效',
      );
    }
    final requested = _decodePath(
      _uri(path).path.replaceFirst(RegExp(r'/+$'), ''),
    );
    final result = <String, MobileWebDavChild>{};
    for (final node in _elementsNamed(document, 'response')) {
      final href = _elementsNamed(node, 'href').firstOrNull?.innerText.trim();
      if (href == null || href.isEmpty) continue;
      final hrefUri = Uri.tryParse(href);
      final rawPath = hrefUri?.path ?? href;
      final itemPath = _decodePath(rawPath.replaceFirst(RegExp(r'/+$'), ''));
      if (itemPath == requested || !itemPath.startsWith('$requested/')) {
        continue;
      }
      final relative = itemPath.substring(requested.length + 1);
      if (relative.contains('/') || relative.isEmpty) {
        continue;
      }
      final resourceType = _elementsNamed(node, 'resourcetype').firstOrNull;
      final collection =
          resourceType != null &&
          _elementsNamed(resourceType, 'collection').isNotEmpty;
      final lengthText =
          _elementsNamed(
            node,
            'getcontentlength',
          ).firstOrNull?.innerText.trim() ??
          '';
      final length = int.tryParse(lengthText) ?? 0;
      result[relative] = MobileWebDavChild(
        name: relative,
        collection: collection,
        contentLength: length,
      );
    }
    final values = result.values.toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    return values;
  }

  Future<void> delete(List<String> path, {bool optional = true}) async {
    final response = await _request('DELETE', _uri(path));
    if (optional && response.statusCode == 404) return;
    if (response.statusCode != 200 &&
        response.statusCode != 202 &&
        response.statusCode != 204) {
      throw MobileWebDavException(
        'WEBDAV_DELETE_FAILED',
        'WebDAV 删除失败（HTTP ${response.statusCode}）',
        statusCode: response.statusCode,
      );
    }
  }

  Future<void> verifyStored(List<String> path, Uint8List expected) async {
    final stored = await get(path);
    if (stored == null || !_sameBytes(stored.content, expected)) {
      throw const MobileWebDavException(
        'SYNC_UPLOAD_VERIFY_FAILED',
        '同步快照上传后校验失败',
      );
    }
  }

  Future<void> deleteV2Space(String vaultId, String spaceId) async {
    final root = ['secretbase-sync-v2', vaultId, spaceId, 'snapshots'];
    final devices = await listChildren(root, optional: true);
    final uuidPattern = RegExp(
      r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
    );
    final snapshotPattern = RegExp(
      r'^[1-9][0-9]{0,18}-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\.sbs$',
    );
    for (final device in devices) {
      if (!device.collection || !uuidPattern.hasMatch(device.name)) {
        throw const MobileWebDavException(
          'WEBDAV_DELETE_FAILED',
          '远端同步空间包含未知对象，已停止清理',
        );
      }
      final devicePath = [...root, device.name];
      final objects = await listChildren(devicePath, optional: true);
      for (final object in objects) {
        if (object.collection || !snapshotPattern.hasMatch(object.name)) {
          throw const MobileWebDavException(
            'WEBDAV_DELETE_FAILED',
            '远端同步目录包含未知对象，已停止清理',
          );
        }
        await delete([...devicePath, object.name], optional: false);
      }
      if (await listChildren(
        devicePath,
        optional: true,
      ).then((value) => value.isNotEmpty)) {
        throw const MobileWebDavException(
          'SYNC_REMOTE_CHANGED',
          '删除期间远端出现新同步对象，请重试',
        );
      }
      await delete(devicePath, optional: false);
    }
    final remaining = await listChildren(root, optional: true);
    if (remaining.isNotEmpty) {
      throw const MobileWebDavException(
        'SYNC_REMOTE_CHANGED',
        '删除期间远端出现新同步对象，请重试',
      );
    }
    await delete(root, optional: false);
    await delete(['secretbase-sync-v2', vaultId, spaceId], optional: false);
  }

  static bool _sameBytes(Uint8List left, Uint8List right) {
    if (left.length != right.length) return false;
    for (var index = 0; index < left.length; index++) {
      if (left[index] != right[index]) return false;
    }
    return true;
  }

  Future<void> probeV2() async {
    final random = Random.secure();
    String id() => List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
    // UUID-shaped values are not required by the server probe, but keep paths portable.
    final vault =
        '${id().substring(0, 8)}-${id().substring(8, 12)}-4${id().substring(12, 15)}-8${id().substring(15, 18)}-${id().substring(18, 30)}';
    final space =
        '${id().substring(0, 8)}-${id().substring(8, 12)}-4${id().substring(12, 15)}-8${id().substring(15, 18)}-${id().substring(18, 30)}';
    final device =
        '${id().substring(0, 8)}-${id().substring(8, 12)}-4${id().substring(12, 15)}-8${id().substring(15, 18)}-${id().substring(18, 30)}';
    final snapshot =
        '${id().substring(0, 8)}-${id().substring(8, 12)}-4${id().substring(12, 15)}-8${id().substring(15, 18)}-${id().substring(18, 30)}';
    final path = [
      'secretbase-sync-v2',
      vault,
      space,
      'snapshots',
      device,
      '1-$snapshot.sbs',
    ];
    final content = Uint8List.fromList(utf8.encode('secretbase-mobile-probe'));
    try {
      await ensureV2Layout(vault, space, device);
      await put(path, content);
      await verifyStored(path, content);
      final children = await listChildren([
        'secretbase-sync-v2',
        vault,
        space,
        'snapshots',
      ]);
      if (!children.any((item) => item.name == device && item.collection)) {
        throw const MobileWebDavException(
          'WEBDAV_CAPABILITY_FAILED',
          'WebDAV 目录发现失败',
        );
      }
    } finally {
      await _bestEffortDelete(path);
      await _bestEffortDelete([
        'secretbase-sync-v2',
        vault,
        space,
        'snapshots',
        device,
      ]);
      await _bestEffortDelete([
        'secretbase-sync-v2',
        vault,
        space,
        'snapshots',
      ]);
      await _bestEffortDelete(['secretbase-sync-v2', vault, space]);
      await _bestEffortDelete(['secretbase-sync-v2', vault]);
    }
  }

  Future<void> _bestEffortDelete(List<String> path) async {
    try {
      await delete(path);
    } on MobileWebDavException {
      // Probe cleanup must not hide the actual capability result.
    }
  }
}

Iterable<XmlElement> _elementsNamed(XmlNode node, String localName) => node
    .descendants
    .whereType<XmlElement>()
    .where((element) => element.name.local == localName);

String _decodePath(String value) {
  try {
    return Uri.decodeFull(value);
  } on FormatException catch (_) {
    throw const MobileWebDavException(
      'WEBDAV_LIST_INVALID',
      'WebDAV 目录响应包含无效路径',
    );
  }
}

extension<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
