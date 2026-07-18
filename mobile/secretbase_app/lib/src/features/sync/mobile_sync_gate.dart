class MobileSyncBusyException implements Exception {
  const MobileSyncBusyException();

  @override
  String toString() => '同步正在进行，请稍后重试。';
}

class MobileSyncGate {
  MobileSyncGate._();

  static bool _busy = false;

  static bool get busy => _busy;

  static Future<T> run<T>(Future<T> Function() operation) async {
    if (_busy) {
      throw const MobileSyncBusyException();
    }
    _busy = true;
    try {
      return await operation();
    } finally {
      _busy = false;
    }
  }
}
