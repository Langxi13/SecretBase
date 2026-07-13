import 'package:flutter/material.dart';

abstract final class AppTheme {
  static const _primary = Color(0xFF006B68);
  static const _secondary = Color(0xFFB54708);
  static const _tertiary = Color(0xFF315DA8);

  static ThemeData light() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: _primary,
          brightness: Brightness.light,
        ).copyWith(
          primary: _primary,
          secondary: _secondary,
          tertiary: _tertiary,
          surface: const Color(0xFFFFFFFF),
          surfaceContainerLowest: const Color(0xFFFFFFFF),
          surfaceContainerLow: const Color(0xFFF7F9FA),
          surfaceContainer: const Color(0xFFF0F3F5),
          surfaceContainerHigh: const Color(0xFFE8ECEF),
          outline: const Color(0xFF859197),
          outlineVariant: const Color(0xFFD5DCDF),
          error: const Color(0xFFB42318),
        );
    return _build(scheme, const Color(0xFFF4F7F8));
  }

  static ThemeData dark() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: const Color(0xFF58C7C1),
          brightness: Brightness.dark,
        ).copyWith(
          primary: const Color(0xFF66D4CE),
          onPrimary: const Color(0xFF003735),
          secondary: const Color(0xFFFFB77C),
          tertiary: const Color(0xFFAFC6FF),
          surface: const Color(0xFF151A1C),
          surfaceContainerLowest: const Color(0xFF101416),
          surfaceContainerLow: const Color(0xFF1B2123),
          surfaceContainer: const Color(0xFF22292C),
          surfaceContainerHigh: const Color(0xFF2B3336),
          outline: const Color(0xFF899497),
          outlineVariant: const Color(0xFF3B4548),
          error: const Color(0xFFFFB4AB),
        );
    return _build(scheme, const Color(0xFF101416));
  }

  static ThemeData _build(ColorScheme scheme, Color scaffoldBackground) {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scaffoldBackground,
      visualDensity: VisualDensity.standard,
    );
    final textTheme = _zeroLetterSpacing(base.textTheme);
    return base.copyWith(
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: scaffoldBackground,
        foregroundColor: scheme.onSurface,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          color: scheme.onSurface,
          fontWeight: FontWeight.w700,
        ),
      ),
      cardTheme: CardThemeData(
        margin: EdgeInsets.zero,
        elevation: 0,
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLow,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 13,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: BorderSide(color: scheme.primary, width: 1.5),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        side: BorderSide(color: scheme.outlineVariant),
        labelStyle: textTheme.labelMedium,
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 68,
        elevation: 3,
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primaryContainer,
        labelTextStyle: WidgetStatePropertyAll(textTheme.labelSmall),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primaryContainer,
        selectedIconTheme: IconThemeData(color: scheme.onPrimaryContainer),
        selectedLabelTextStyle: textTheme.labelMedium?.copyWith(
          color: scheme.primary,
          fontWeight: FontWeight.w700,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
          textStyle: textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          textStyle: textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: scheme.inverseSurface,
          borderRadius: BorderRadius.circular(4),
        ),
        textStyle: textTheme.bodySmall?.copyWith(
          color: scheme.onInverseSurface,
        ),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
      ),
    );
  }

  static TextTheme _zeroLetterSpacing(TextTheme theme) {
    TextStyle? normalize(TextStyle? style) => style?.copyWith(letterSpacing: 0);
    return theme.copyWith(
      displayLarge: normalize(theme.displayLarge),
      displayMedium: normalize(theme.displayMedium),
      displaySmall: normalize(theme.displaySmall),
      headlineLarge: normalize(theme.headlineLarge),
      headlineMedium: normalize(theme.headlineMedium),
      headlineSmall: normalize(theme.headlineSmall),
      titleLarge: normalize(theme.titleLarge),
      titleMedium: normalize(theme.titleMedium),
      titleSmall: normalize(theme.titleSmall),
      bodyLarge: normalize(theme.bodyLarge),
      bodyMedium: normalize(theme.bodyMedium),
      bodySmall: normalize(theme.bodySmall),
      labelLarge: normalize(theme.labelLarge),
      labelMedium: normalize(theme.labelMedium),
      labelSmall: normalize(theme.labelSmall),
    );
  }
}
