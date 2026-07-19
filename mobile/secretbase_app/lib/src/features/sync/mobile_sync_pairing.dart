import 'dart:convert';

import 'package:crypto/crypto.dart';

class MobileSyncPairingException implements Exception {
  const MobileSyncPairingException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// The non-password portion of a SecretBase sync pairing link.
///
/// A pairing link is a bearer secret. It is parsed only after an explicit user
/// action and is never persisted by this class. The WebDAV password is
/// intentionally absent and must still be entered by the user.
class MobileSyncPairing {
  const MobileSyncPairing({
    required this.baseUrl,
    required this.username,
    required this.recoveryCode,
  });

  final String baseUrl;
  final String username;
  final String recoveryCode;

  Uri get uri => Uri(
    scheme: 'secretbase',
    host: 'sync',
    path: '/join',
    queryParameters: {
      'v': '2',
      'recovery_code': recoveryCode,
      'url': baseUrl,
      'username': username,
    },
  );

  static MobileSyncPairing parse(String raw) {
    final value = raw.trim();
    final parsed = Uri.tryParse(value);
    if (parsed == null ||
        parsed.scheme != 'secretbase' ||
        parsed.host != 'sync' ||
        parsed.path != '/join' ||
        parsed.userInfo.isNotEmpty ||
        parsed.fragment.isNotEmpty) {
      throw const MobileSyncPairingException('不是 SecretBase 同步配对链接');
    }
    for (final key in const [
      'v',
      'url',
      'username',
      'recovery_code',
      'key',
      'vault_id',
      'space_id',
    ]) {
      if ((parsed.queryParametersAll[key] ?? const []).length > 1) {
        throw MobileSyncPairingException('配对链接包含重复的 $key 参数');
      }
    }
    for (final key in const [
      'password',
      'webdav_password',
      'app_password',
      'token',
    ]) {
      if (parsed.queryParametersAll.containsKey(key)) {
        throw const MobileSyncPairingException('配对链接不得包含 WebDAV 应用密码或访问令牌');
      }
    }
    if (parsed.queryParameters['v'] != '2') {
      throw const MobileSyncPairingException(
        '仅支持 V2 加密快照配对链接，请先在已配置设备生成最新配对信息',
      );
    }

    final baseUrl = parsed.queryParameters['url']?.trim() ?? '';
    final webdav = Uri.tryParse(baseUrl);
    if (webdav == null ||
        webdav.scheme != 'https' ||
        webdav.host.isEmpty ||
        webdav.userInfo.isNotEmpty ||
        webdav.hasQuery ||
        webdav.hasFragment) {
      throw const MobileSyncPairingException('配对链接中的 WebDAV 地址无效');
    }
    final username = parsed.queryParameters['username']?.trim() ?? '';
    if (username.isEmpty) {
      throw const MobileSyncPairingException('配对链接缺少 WebDAV 用户名');
    }

    var recoveryCode = parsed.queryParameters['recovery_code']?.trim() ?? '';
    if (recoveryCode.isNotEmpty && parsed.queryParameters['key'] != null) {
      throw const MobileSyncPairingException('配对链接包含重复的同步密钥材料，请重新生成');
    }
    if (recoveryCode.isEmpty) {
      recoveryCode = _recoveryCodeFromLegacyKey(parsed.queryParameters);
    }
    final validated = _validateRecoveryCode(recoveryCode);
    final declaredVault = parsed.queryParameters['vault_id'];
    final declaredSpace = parsed.queryParameters['space_id'];
    if (declaredVault != null &&
        _canonicalUuid(declaredVault, 'Vault ID') != validated.vaultId) {
      throw const MobileSyncPairingException('配对链接中的 Vault 身份与恢复码不一致');
    }
    if (declaredSpace != null &&
        _canonicalUuid(declaredSpace, '同步空间 ID') != validated.spaceId) {
      throw const MobileSyncPairingException('配对链接中的同步空间身份与恢复码不一致');
    }
    return MobileSyncPairing(
      baseUrl: baseUrl,
      username: username,
      recoveryCode: validated.code,
    );
  }

  static _ValidatedRecoveryCode _validateRecoveryCode(String value) {
    const prefix = 'SBSYNC2';
    final normalized = value
        .replaceAll('-', '')
        .replaceAll(RegExp(r'\s'), '')
        .toUpperCase();
    if (!normalized.startsWith(prefix)) {
      throw const MobileSyncPairingException('配对链接缺少有效的 V2 恢复码');
    }
    final raw = _base32Decode(normalized.substring(prefix.length));
    if (raw.length != 69 || raw[0] != 2) {
      throw const MobileSyncPairingException('同步恢复码版本无效');
    }
    final body = raw.sublist(0, raw.length - 4);
    final checksum = raw.sublist(raw.length - 4);
    final expected = sha256
        .convert([...utf8.encode(prefix), ...body])
        .bytes
        .sublist(0, 4);
    for (var index = 0; index < checksum.length; index += 1) {
      if (checksum[index] != expected[index]) {
        throw const MobileSyncPairingException('同步恢复码校验失败');
      }
    }
    return _ValidatedRecoveryCode(
      code: _groupedCode(prefix, raw),
      vaultId: _uuidText(raw.sublist(1, 17)),
      spaceId: _uuidText(raw.sublist(17, 33)),
    );
  }

  static String _recoveryCodeFromLegacyKey(Map<String, String> query) {
    final vaultId = query['vault_id'];
    final spaceId = query['space_id'];
    final encodedKey = query['key'];
    if (vaultId == null || spaceId == null || encodedKey == null) {
      throw const MobileSyncPairingException('配对链接缺少恢复码');
    }
    final payload = <int>[
      2,
      ..._uuidBytes(vaultId, 'Vault ID'),
      ..._uuidBytes(spaceId, '同步空间 ID'),
      ..._decodeKey(encodedKey),
    ];
    final checksum = sha256
        .convert([...utf8.encode('SBSYNC2'), ...payload])
        .bytes
        .sublist(0, 4);
    return 'SBSYNC2-${_base32([...payload, ...checksum])}';
  }

  static List<int> _uuidBytes(String value, String label) {
    final normalized = value.replaceAll('-', '');
    if (!RegExp(r'^[0-9a-fA-F]{32}$').hasMatch(normalized)) {
      throw MobileSyncPairingException('$label 无效');
    }
    return [
      for (var index = 0; index < normalized.length; index += 2)
        int.parse(normalized.substring(index, index + 2), radix: 16),
    ];
  }

  static String _canonicalUuid(String value, String label) {
    return _uuidText(_uuidBytes(value, label));
  }

  static String _uuidText(List<int> bytes) {
    if (bytes.length != 16) {
      throw const MobileSyncPairingException('UUID 长度无效');
    }
    final hex = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }

  static List<int> _decodeKey(String value) {
    try {
      final normalized = value.trim();
      final decoded = base64Url.decode(
        normalized.padRight(normalized.length + (-normalized.length % 4), '='),
      );
      if (decoded.length != 32) throw const FormatException();
      return decoded;
    } catch (_) {
      throw const MobileSyncPairingException('配对链接中的同步密钥无效');
    }
  }

  static String _base32(List<int> bytes) {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    var buffer = 0;
    var bits = 0;
    final output = StringBuffer();
    for (final byte in bytes) {
      buffer = (buffer << 8) | byte;
      bits += 8;
      while (bits >= 5) {
        bits -= 5;
        output.write(alphabet[(buffer >> bits) & 31]);
      }
    }
    if (bits > 0) output.write(alphabet[(buffer << (5 - bits)) & 31]);
    final encoded = output.toString();
    return [
      for (var index = 0; index < encoded.length; index += 5)
        encoded.substring(
          index,
          index + 5 > encoded.length ? encoded.length : index + 5,
        ),
    ].join('-');
  }

  static String _groupedCode(String prefix, List<int> bytes) {
    return '$prefix-${_base32(bytes)}';
  }

  static List<int> _base32Decode(String value) {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    final normalized = value.replaceAll(RegExp(r'\s'), '').toUpperCase();
    if (normalized.isEmpty || !RegExp(r'^[A-Z2-7]+$').hasMatch(normalized)) {
      throw const MobileSyncPairingException('同步恢复码格式无效');
    }
    final bytes = <int>[];
    var buffer = 0;
    var bits = 0;
    for (final character in normalized.split('')) {
      buffer = (buffer << 5) | alphabet.indexOf(character);
      bits += 5;
      while (bits >= 8) {
        bits -= 8;
        bytes.add((buffer >> bits) & 0xff);
      }
    }
    if (bits > 0 && ((buffer << (8 - bits)) & 0xff) != 0) {
      throw const MobileSyncPairingException('同步恢复码格式无效');
    }
    return bytes;
  }
}

class _ValidatedRecoveryCode {
  const _ValidatedRecoveryCode({
    required this.code,
    required this.vaultId,
    required this.spaceId,
  });

  final String code;
  final String vaultId;
  final String spaceId;
}
