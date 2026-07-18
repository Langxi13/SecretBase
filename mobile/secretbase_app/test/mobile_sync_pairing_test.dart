import 'package:flutter_test/flutter_test.dart';
import 'package:secretbase/src/features/sync/mobile_sync_pairing.dart';

void main() {
  test('新版配对链接可以往返解析且不包含 WebDAV 密码', () {
    const pairing = MobileSyncPairing(
      baseUrl: 'https://dav.example.test/secretbase',
      username: 'tester@example.test',
      recoveryCode:
          'SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-Q',
    );

    final uri = pairing.uri;
    expect(uri.queryParameters.containsKey('password'), isFalse);
    expect(uri.queryParameters.containsKey('key'), isFalse);
    expect(MobileSyncPairing.parse(uri.toString()).baseUrl, pairing.baseUrl);
    expect(MobileSyncPairing.parse(uri.toString()).username, pairing.username);
    expect(
      MobileSyncPairing.parse(uri.toString()).recoveryCode,
      pairing.recoveryCode,
    );
  });

  test('V5.3 旧配对链接可转换为相同的 V2 恢复码', () {
    final uri = Uri(
      scheme: 'secretbase',
      host: 'sync',
      path: '/join',
      queryParameters: const {
        'v': '2',
        'vault_id': '11111111-1111-4111-8111-111111111111',
        'space_id': '22222222-2222-4222-8222-222222222222',
        'key': 'AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA',
        'url': 'https://dav.example.test/secretbase',
        'username': 'tester',
      },
    );

    expect(
      MobileSyncPairing.parse(uri.toString()).recoveryCode,
      'SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-Q',
    );
  });

  test('拒绝 HTTP、带凭据 URL 和非 SecretBase 链接', () {
    for (final value in [
      'https://example.test',
      'secretbase://sync/join?v=2&recovery_code=SBSYNC2-TEST&url=https%3A%2F%2Fdav.example.test&username=tester',
      'secretbase://sync/join?v=2&recovery_code=SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-R&url=https%3A%2F%2Fdav.example.test&username=tester',
      'secretbase://sync/join?v=2&recovery_code=SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-Q&url=http%3A%2F%2Fdav.example.test&username=tester',
      'secretbase://sync/join?v=2&recovery_code=SBSYNC2-AIIRC-EIRCE-IUCEM-BCEIR-CEIRC-EISEI-RCEIR-CEQRC-QIRCE-IRCEI-RCEAI-CAMCA-KBQHB-AEQUC-YMBUH-A6EAR-CIJRI-FIWC4-MBSGQ-3DQOR-4HZAJ-QFRST-Q&url=https%3A%2F%2Fname%3Apass%40dav.example.test&username=tester',
    ]) {
      expect(
        () => MobileSyncPairing.parse(value),
        throwsA(isA<MobileSyncPairingException>()),
      );
    }
  });
}
