import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:secretbase/src/core/theme/app_theme.dart';
import 'package:shared_preferences/shared_preferences.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw StateError('SharedPreferences 尚未初始化'),
);

class AppPreferences {
  const AppPreferences({
    required this.themeMode,
    required this.textSize,
    required this.entryPageSize,
    required this.taxonomyPageSize,
    required this.groupPageSize,
    required this.clipboardClearSeconds,
    required this.aiPrivacyAccepted,
    required this.updateAutoCheck,
    required this.updateAutoDownload,
    required this.updateAllowMeteredDownload,
    required this.lastUpdateCheckAt,
  });

  final ThemeMode themeMode;
  final AppTextSize textSize;
  final int entryPageSize;
  final int taxonomyPageSize;
  final int groupPageSize;
  final int clipboardClearSeconds;
  final bool aiPrivacyAccepted;
  final bool updateAutoCheck;
  final bool updateAutoDownload;
  final bool updateAllowMeteredDownload;
  final DateTime? lastUpdateCheckAt;

  AppPreferences copyWith({
    ThemeMode? themeMode,
    AppTextSize? textSize,
    int? entryPageSize,
    int? taxonomyPageSize,
    int? groupPageSize,
    int? clipboardClearSeconds,
    bool? aiPrivacyAccepted,
    bool? updateAutoCheck,
    bool? updateAutoDownload,
    bool? updateAllowMeteredDownload,
    DateTime? lastUpdateCheckAt,
    bool clearLastUpdateCheckAt = false,
  }) {
    return AppPreferences(
      themeMode: themeMode ?? this.themeMode,
      textSize: textSize ?? this.textSize,
      entryPageSize: entryPageSize ?? this.entryPageSize,
      taxonomyPageSize: taxonomyPageSize ?? this.taxonomyPageSize,
      groupPageSize: groupPageSize ?? this.groupPageSize,
      clipboardClearSeconds:
          clipboardClearSeconds ?? this.clipboardClearSeconds,
      aiPrivacyAccepted: aiPrivacyAccepted ?? this.aiPrivacyAccepted,
      updateAutoCheck: updateAutoCheck ?? this.updateAutoCheck,
      updateAutoDownload: updateAutoDownload ?? this.updateAutoDownload,
      updateAllowMeteredDownload:
          updateAllowMeteredDownload ?? this.updateAllowMeteredDownload,
      lastUpdateCheckAt: clearLastUpdateCheckAt
          ? null
          : lastUpdateCheckAt ?? this.lastUpdateCheckAt,
    );
  }
}

final preferencesProvider =
    NotifierProvider<PreferencesController, AppPreferences>(
      PreferencesController.new,
    );

class PreferencesController extends Notifier<AppPreferences> {
  late SharedPreferences _preferences;

  @override
  AppPreferences build() {
    _preferences = ref.watch(sharedPreferencesProvider);
    return AppPreferences(
      themeMode: _themeFromName(_preferences.getString('theme_mode')),
      textSize: _textSizeFromName(_preferences.getString('text_size')),
      entryPageSize: _validPageSize(
        _preferences.getInt('entry_page_size'),
        fallback: 5,
      ),
      taxonomyPageSize: _validPageSize(
        _preferences.getInt('taxonomy_page_size'),
        fallback: 5,
      ),
      groupPageSize: _validPageSize(
        _preferences.getInt('group_page_size'),
        fallback: 5,
      ),
      clipboardClearSeconds: _validClipboardSeconds(
        _preferences.getInt('clipboard_clear_seconds'),
      ),
      aiPrivacyAccepted: _preferences.getBool('ai_privacy_accepted') ?? false,
      updateAutoCheck: _preferences.getBool('update_auto_check') ?? true,
      updateAutoDownload: _preferences.getBool('update_auto_download') ?? true,
      updateAllowMeteredDownload:
          _preferences.getBool('update_allow_metered_download') ?? false,
      lastUpdateCheckAt: _dateTimeFromMillis(
        _preferences.getInt('last_update_check_at'),
      ),
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = state.copyWith(themeMode: mode);
    await _preferences.setString('theme_mode', mode.name);
  }

  Future<void> setTextSize(AppTextSize value) async {
    state = state.copyWith(textSize: value);
    await _preferences.setString('text_size', value.name);
  }

  Future<void> setEntryPageSize(int value) async {
    final pageSize = _validPageSize(value, fallback: 5);
    state = state.copyWith(entryPageSize: pageSize);
    await _preferences.setInt('entry_page_size', pageSize);
  }

  Future<void> setTaxonomyPageSize(int value) async {
    final pageSize = _validPageSize(value, fallback: 5);
    state = state.copyWith(taxonomyPageSize: pageSize);
    await _preferences.setInt('taxonomy_page_size', pageSize);
  }

  Future<void> setGroupPageSize(int value) async {
    final pageSize = _validPageSize(value, fallback: 5);
    state = state.copyWith(groupPageSize: pageSize);
    await _preferences.setInt('group_page_size', pageSize);
  }

  Future<void> setClipboardClearSeconds(int value) async {
    final seconds = _validClipboardSeconds(value);
    state = state.copyWith(clipboardClearSeconds: seconds);
    await _preferences.setInt('clipboard_clear_seconds', seconds);
  }

  Future<void> acceptAiPrivacy() async {
    state = state.copyWith(aiPrivacyAccepted: true);
    await _preferences.setBool('ai_privacy_accepted', true);
  }

  Future<void> setUpdateAutoCheck(bool value) async {
    state = state.copyWith(updateAutoCheck: value);
    await _preferences.setBool('update_auto_check', value);
  }

  Future<void> setUpdateAutoDownload(bool value) async {
    state = state.copyWith(updateAutoDownload: value);
    await _preferences.setBool('update_auto_download', value);
  }

  Future<void> setUpdateAllowMeteredDownload(bool value) async {
    state = state.copyWith(updateAllowMeteredDownload: value);
    await _preferences.setBool('update_allow_metered_download', value);
  }

  Future<void> setLastUpdateCheckAt(DateTime value) async {
    state = state.copyWith(lastUpdateCheckAt: value);
    await _preferences.setInt(
      'last_update_check_at',
      value.millisecondsSinceEpoch,
    );
  }

  static ThemeMode _themeFromName(String? value) {
    return ThemeMode.values.where((mode) => mode.name == value).firstOrNull ??
        ThemeMode.system;
  }

  static AppTextSize _textSizeFromName(String? value) {
    return AppTextSize.values.where((size) => size.name == value).firstOrNull ??
        AppTextSize.standard;
  }

  static int _validPageSize(int? value, {required int fallback}) {
    return const [5, 10, 20, 50].contains(value) ? value! : fallback;
  }

  static int _validClipboardSeconds(int? value) {
    return const [15, 30, 60, 120].contains(value) ? value! : 30;
  }

  static DateTime? _dateTimeFromMillis(int? value) {
    if (value == null || value <= 0) return null;
    return DateTime.fromMillisecondsSinceEpoch(value);
  }
}
