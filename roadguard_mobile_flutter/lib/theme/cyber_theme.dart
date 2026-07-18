import 'package:flutter/material.dart';

class CyberTheme {
  // Brand Colors
  static const Color darkBackground = Color(0xFF070A13);
  static const Color cardBackground = Color(0xFF0F172A);
  static const Color glassOverlay = Color(0x661E293B);
  
  static const Color neonCyan = Color(0xFF00E5FF);
  static const Color neonPink = Color(0xFFFF007F);
  static const Color neonPurple = Color(0xFFBB66FF);
  static const Color neonGreen = Color(0xFF00FF88);
  static const Color neonAmber = Color(0xFFFFB300);
  static const Color neonRed = Color(0xFFFF3366);

  static const Color textPrimary = Colors.white;
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted = Color(0xFF475569);

  // Outer Neon Glow Shadows
  static List<BoxShadow> neonGlow(Color color, {double intensity = 0.15, double radius = 8}) {
    return [
      BoxShadow(
        color: color.withOpacity(intensity),
        blurRadius: radius,
        spreadRadius: 1,
      ),
      BoxShadow(
        color: color.withOpacity(intensity * 0.5),
        blurRadius: radius * 2,
        spreadRadius: 2,
      ),
    ];
  }

  // Futuristic Text Styles
  static const TextStyle brandHeader = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w900,
    letterSpacing: 2,
    color: textPrimary,
    shadows: [
      Shadow(
        color: Color(0x6600E5FF),
        blurRadius: 10,
      ),
    ],
  );

  static const TextStyle sectionHeader = TextStyle(
    fontFamily: 'Courier',
    fontSize: 12,
    fontWeight: FontWeight.bold,
    letterSpacing: 1.5,
    color: textSecondary,
  );

  static const TextStyle terminalText = TextStyle(
    fontFamily: 'Courier',
    fontSize: 11,
    letterSpacing: 0.5,
    color: textPrimary,
  );
}
