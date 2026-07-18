import 'package:flutter/material.dart';
import 'theme/cyber_theme.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(const RoadGuardMobileApp());
}

class RoadGuardMobileApp extends StatelessWidget {
  const RoadGuardMobileApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RoadGuard AI Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: CyberTheme.darkBackground,
        primaryColor: CyberTheme.neonCyan,
        colorScheme: const ColorScheme.dark(
          primary: CyberTheme.neonCyan,
          secondary: CyberTheme.neonPink,
          surface: CyberTheme.cardBackground,
        ),
      ),
      home: const CinematicSplashScreen(),
    );
  }
}
