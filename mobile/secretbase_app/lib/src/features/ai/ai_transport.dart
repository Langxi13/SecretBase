import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:secretbase/src/rust/mobile/models.dart';

class AiTransportException implements Exception {
  const AiTransportException(this.message);

  final String message;

  @override
  String toString() => message;
}

class AiTransportCancelledException extends AiTransportException {
  const AiTransportCancelledException() : super('AI 请求已取消');
}

class AiTransportOperation {
  AiTransportOperation._(this._request) {
    _future = _run();
  }

  final AiHttpRequest _request;
  late final Future<String> _future;
  http.Client? _client;
  bool _cancelled = false;

  Future<String> get future => _future;
  bool get cancelled => _cancelled;

  void cancel() {
    if (_cancelled) return;
    _cancelled = true;
    final client = _client;
    _client = null;
    client?.close();
  }

  Future<String> _run() async {
    if (_cancelled) throw const AiTransportCancelledException();
    final uri = Uri.tryParse(_request.url);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
      throw const AiTransportException('移动端 AI 只允许访问有效的 HTTPS 地址');
    }
    final client = http.Client();
    _client = client;
    try {
      final outbound = http.Request(_request.method, uri)
        ..followRedirects = false
        ..maxRedirects = 0;
      for (final header in _request.headers) {
        outbound.headers[header.name] = header.value;
      }
      if (_request.body.isNotEmpty) outbound.body = _request.body;
      final response = await client
          .send(outbound)
          .timeout(Duration(seconds: _request.timeoutSeconds));
      if (response.isRedirect) {
        throw const AiTransportException('AI 服务返回了重定向，已阻止继续请求');
      }
      if (response.contentLength != null &&
          response.contentLength! > AiTransport.maximumResponseBytes) {
        throw const AiTransportException('AI 返回内容过大，请缩小处理范围');
      }
      final bytes = <int>[];
      await for (final chunk in response.stream.timeout(
        Duration(seconds: _request.timeoutSeconds),
      )) {
        bytes.addAll(chunk);
        if (bytes.length > AiTransport.maximumResponseBytes) {
          throw const AiTransportException('AI 返回内容过大，请缩小处理范围');
        }
      }
      if (_cancelled) throw const AiTransportCancelledException();
      final body = utf8.decode(bytes, allowMalformed: true);
      switch (response.statusCode) {
        case 200:
          return body;
        case 401:
        case 403:
          throw const AiTransportException('AI 服务认证失败，请检查 API Key');
        case 408:
        case 504:
          throw const AiTransportException('AI 服务响应超时');
        case 429:
          throw const AiTransportException('AI 服务请求过于频繁，请稍后重试');
        default:
          throw AiTransportException('AI 服务调用失败（${response.statusCode}）');
      }
    } on TimeoutException {
      if (_cancelled) throw const AiTransportCancelledException();
      throw const AiTransportException('AI 服务响应超时，请稍后重试');
    } on http.ClientException {
      if (_cancelled) throw const AiTransportCancelledException();
      throw const AiTransportException('无法连接 AI 服务');
    } catch (_) {
      if (_cancelled) throw const AiTransportCancelledException();
      rethrow;
    } finally {
      if (identical(_client, client)) _client = null;
      client.close();
    }
  }
}

abstract final class AiTransport {
  static const maximumResponseBytes = 4 * 1024 * 1024;

  static AiTransportOperation start(AiHttpRequest request) =>
      AiTransportOperation._(request);

  static Future<String> send(AiHttpRequest request) => start(request).future;
}
