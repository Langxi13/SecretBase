import 'package:flutter/material.dart';

enum AppTextSize { standard, large }

abstract final class AppTheme {
  static const _primary = Color(0xFF006B68);
  static const _secondary = Color(0xFFB54708);
  static const _tertiary = Color(0xFF315DA8);

  static ThemeData light({AppTextSize textSize = AppTextSize.standard}) {
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
    return _build(scheme, const Color(0xFFF4F7F8), textSize);
  }

  static ThemeData dark({AppTextSize textSize = AppTextSize.standard}) {
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
    return _build(scheme, const Color(0xFF101416), textSize);
  }

  static ThemeData _build(
    ColorScheme scheme,
    Color scaffoldBackground,
    AppTextSize textSize,
  ) {
    final compact = textSize == AppTextSize.standard;
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scaffoldBackground,
      visualDensity: compact
          ? const VisualDensity(horizontal: -1, vertical: -1)
          : VisualDensity.standard,
    );
    final textTheme = _normalizeTextTheme(base.textTheme, compact ? 0.92 : 1);
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
          borderRadius: BorderRadius.circular(8),
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
        contentPadding: EdgeInsets.symmetric(
          horizontal: compact ? 12 : 14,
          vertical: compact ? 10 : 13,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: scheme.primary, width: 1.5),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        side: BorderSide(color: scheme.outlineVariant),
        labelStyle: textTheme.labelMedium,
        labelPadding: EdgeInsets.symmetric(horizontal: compact ? 5 : 7),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: compact ? 64 : 70,
        elevation: 0,
        backgroundColor: scheme.surfaceContainerLowest,
        indicatorColor: scheme.primaryContainer,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          return textTheme.labelSmall?.copyWith(
            color: states.contains(WidgetState.selected)
                ? scheme.primary
                : scheme.onSurfaceVariant,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w800
                : FontWeight.w600,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          return IconThemeData(
            size: states.contains(WidgetState.selected) ? 24 : 22,
            color: states.contains(WidgetState.selected)
                ? scheme.onPrimaryContainer
                : scheme.onSurfaceVariant,
          );
        }),
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
          minimumSize: Size(0, compact ? 42 : 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 15 : 18,
            vertical: compact ? 10 : 13,
          ),
          textStyle: textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: Size(0, compact ? 42 : 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 14 : 16,
            vertical: compact ? 9 : 12,
          ),
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
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          minimumSize: const Size(40, 40),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        elevation: 2,
        focusElevation: 2,
        hoverElevation: 3,
        highlightElevation: 1,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: scheme.surfaceContainerLowest,
        modalBackgroundColor: scheme.surfaceContainerLowest,
        showDragHandle: true,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: scheme.surfaceContainerLowest,
        elevation: 3,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: scheme.inverseSurface,
        contentTextStyle: textTheme.bodyMedium?.copyWith(
          color: scheme.onInverseSurface,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      checkboxTheme: CheckboxThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
        side: BorderSide(color: scheme.outline, width: 1.5),
      ),
      listTileTheme: ListTileThemeData(
        dense: compact,
        contentPadding: EdgeInsets.symmetric(horizontal: compact ? 14 : 16),
        horizontalTitleGap: compact ? 10 : 16,
        minLeadingWidth: compact ? 28 : 40,
        minVerticalPadding: compact ? 6 : 8,
      ),
    );
  }

  static TextTheme _normalizeTextTheme(TextTheme theme, double scale) {
    TextStyle normalize(TextStyle? style, double fontSize) {
      return (style ?? const TextStyle()).copyWith(
        fontSize: fontSize * scale,
        letterSpacing: 0,
      );
    }

    return theme.copyWith(
      displayLarge: normalize(theme.displayLarge, 57),
      displayMedium: normalize(theme.displayMedium, 45),
      displaySmall: normalize(theme.displaySmall, 36),
      headlineLarge: normalize(theme.headlineLarge, 32),
      headlineMedium: normalize(theme.headlineMedium, 28),
      headlineSmall: normalize(theme.headlineSmall, 24),
      titleLarge: normalize(theme.titleLarge, 22),
      titleMedium: normalize(theme.titleMedium, 16),
      titleSmall: normalize(theme.titleSmall, 14),
      bodyLarge: normalize(theme.bodyLarge, 16),
      bodyMedium: normalize(theme.bodyMedium, 14),
      bodySmall: normalize(theme.bodySmall, 12),
      labelLarge: normalize(theme.labelLarge, 14),
      labelMedium: normalize(theme.labelMedium, 12),
      labelSmall: normalize(theme.labelSmall, 11),
    );
  }
}
