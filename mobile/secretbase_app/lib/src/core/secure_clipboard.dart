import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/state/preferences_controller.dart';

final secureClipboardProvider = Provider<SecureClipboard>((ref) {
  final clipboard = SecureClipboard();
  ref.onDispose(clipboard.dispose);
  return clipboard;
});

class SecureClipboard {
  static const _channel = MethodChannel('secretbase/security');
  Timer? _clearTimer;

  Future<void> copy(String value, {required int clearAfterSeconds}) async {
    _clearTimer?.cancel();
    try {
      await _channel.invokeMethod<void>('copySensitive', {'text': value});
    } on MissingPluginException {
      await Clipboard.setData(ClipboardData(text: value));
    }
    _clearTimer = Timer(Duration(seconds: clearAfterSeconds), () async {
      try {
        await _channel.invokeMethod<void>('clearClipboardIfMatches', {
          'text': value,
        });
      } on MissingPluginException {
        final current = await Clipboard.getData(Clipboard.kTextPlain);
        if (current?.text == value) {
          await Clipboard.setData(const ClipboardData(text: ''));
        }
      }
    });
  }

  void dispose() {
    _clearTimer?.cancel();
  }
}

Future<void> copySensitiveValue(WidgetRef ref, String value) {
  final seconds = ref.read(preferencesProvider).clipboardClearSeconds;
  return ref
      .read(secureClipboardProvider)
      .copy(value, clearAfterSeconds: seconds);
}
