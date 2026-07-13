import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw StateError('SharedPreferences 尚未初始化'),
);

class AppPreferences {
  const AppPreferences({
    required this.themeMode,
    required this.entryPageSize,
    required this.taxonomyPageSize,
    required this.clipboardClearSeconds,
    required this.aiPrivacyAccepted,
  });

  final ThemeMode themeMode;
  final int entryPageSize;
  final int taxonomyPageSize;
  final int clipboardClearSeconds;
  final bool aiPrivacyAccepted;

  AppPreferences copyWith({
    ThemeMode? themeMode,
    int? entryPageSize,
    int? taxonomyPageSize,
    int? clipboardClearSeconds,
    bool? aiPrivacyAccepted,
  }) {
    return AppPreferences(
      themeMode: themeMode ?? this.themeMode,
      entryPageSize: entryPageSize ?? this.entryPageSize,
      taxonomyPageSize: taxonomyPageSize ?? this.taxonomyPageSize,
      clipboardClearSeconds:
          clipboardClearSeconds ?? this.clipboardClearSeconds,
      aiPrivacyAccepted: aiPrivacyAccepted ?? this.aiPrivacyAccepted,
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
      entryPageSize: _validPageSize(
        _preferences.getInt('entry_page_size'),
        fallback: 20,
      ),
      taxonomyPageSize: _validPageSize(
        _preferences.getInt('taxonomy_page_size'),
        fallback: 20,
      ),
      clipboardClearSeconds: _validClipboardSeconds(
        _preferences.getInt('clipboard_clear_seconds'),
      ),
      aiPrivacyAccepted: _preferences.getBool('ai_privacy_accepted') ?? false,
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = state.copyWith(themeMode: mode);
    await _preferences.setString('theme_mode', mode.name);
  }

  Future<void> setEntryPageSize(int value) async {
    final pageSize = _validPageSize(value, fallback: 20);
    state = state.copyWith(entryPageSize: pageSize);
    await _preferences.setInt('entry_page_size', pageSize);
  }

  Future<void> setTaxonomyPageSize(int value) async {
    final pageSize = _validPageSize(value, fallback: 20);
    state = state.copyWith(taxonomyPageSize: pageSize);
    await _preferences.setInt('taxonomy_page_size', pageSize);
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

  static ThemeMode _themeFromName(String? value) {
    return ThemeMode.values.where((mode) => mode.name == value).firstOrNull ??
        ThemeMode.system;
  }

  static int _validPageSize(int? value, {required int fallback}) {
    return const [5, 10, 20, 50].contains(value) ? value! : fallback;
  }

  static int _validClipboardSeconds(int? value) {
    return const [15, 30, 60, 120].contains(value) ? value! : 30;
  }
}
