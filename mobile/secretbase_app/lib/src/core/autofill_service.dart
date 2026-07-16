import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AutofillStatus {
  const AutofillStatus({
    required this.supported,
    required this.enabled,
    required this.savePromptsEnabled,
    required this.inlineSuggestionsEnabled,
    required this.blockedTargetCount,
  });

  const AutofillStatus.unsupported()
    : supported = false,
      enabled = false,
      savePromptsEnabled = true,
      inlineSuggestionsEnabled = true,
      blockedTargetCount = 0;

  final bool supported;
  final bool enabled;
  final bool savePromptsEnabled;
  final bool inlineSuggestionsEnabled;
  final int blockedTargetCount;

  factory AutofillStatus.fromMap(Map<Object?, Object?> value) {
    return AutofillStatus(
      supported: value['supported'] == true,
      enabled: value['enabled'] == true,
      savePromptsEnabled: value['savePromptsEnabled'] != false,
      inlineSuggestionsEnabled: value['inlineSuggestionsEnabled'] != false,
      blockedTargetCount: (value['blockedTargetCount'] as num?)?.toInt() ?? 0,
    );
  }
}

abstract interface class AutofillPlatform {
  Future<AutofillStatus> status();

  Future<void> requestService();

  Future<void> openSettings();

  Future<AutofillStatus> setPreference(String name, bool value);

  Future<AutofillStatus> clearBlockedTargets();
}

class MethodChannelAutofillPlatform implements AutofillPlatform {
  const MethodChannelAutofillPlatform();

  static const _channel = MethodChannel('secretbase/platform');

  @override
  Future<AutofillStatus> status() => _statusCall('getAutofillStatus');

  @override
  Future<void> requestService() =>
      _channel.invokeMethod<void>('requestAutofillService');

  @override
  Future<void> openSettings() =>
      _channel.invokeMethod<void>('openAutofillSettings');

  @override
  Future<AutofillStatus> setPreference(String name, bool value) =>
      _statusCall('setAutofillPreference', {'name': name, 'value': value});

  @override
  Future<AutofillStatus> clearBlockedTargets() =>
      _statusCall('clearAutofillBlockedTargets');

  Future<AutofillStatus> _statusCall(String method, [Object? arguments]) async {
    try {
      final value = await _channel.invokeMapMethod<Object?, Object?>(
        method,
        arguments,
      );
      return value == null
          ? const AutofillStatus.unsupported()
          : AutofillStatus.fromMap(value);
    } on MissingPluginException {
      return const AutofillStatus.unsupported();
    }
  }
}

final autofillPlatformProvider = Provider<AutofillPlatform>(
  (ref) => const MethodChannelAutofillPlatform(),
);

final autofillStatusProvider = FutureProvider<AutofillStatus>(
  (ref) => ref.watch(autofillPlatformProvider).status(),
);
