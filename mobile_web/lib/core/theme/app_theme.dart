import 'package:flutter/material.dart';

class AppTheme {
  static const ink = Color(0xFF1B2430);
  static const paper = Color(0xFFF3EFE4);
  static const copper = Color(0xFFB85C38);
  static const pine = Color(0xFF2F6F4E);
  static const rust = Color(0xFF9C2F2F);
  static const card = Color(0xFFFFFCF7);

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: copper,
      primary: ink,
      secondary: copper,
      surface: paper,
    );
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: paper,
      useMaterial3: true,
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: ink,
        foregroundColor: paper,
        elevation: 0,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: ink,
        indicatorColor: copper.withValues(alpha: 0.35),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected) ? paper : paper.withValues(alpha: 0.7),
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected) ? paper : paper.withValues(alpha: 0.7),
          ),
        ),
      ),
    );
  }
}
