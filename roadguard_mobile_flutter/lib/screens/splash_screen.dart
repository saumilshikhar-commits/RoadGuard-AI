import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/cyber_theme.dart';
import '../widgets/cyber_grid.dart';
import '../services/api_service.dart';
import 'home_screen.dart';

class CinematicSplashScreen extends StatefulWidget {
  const CinematicSplashScreen({Key? key}) : super(key: key);

  @override
  State<CinematicSplashScreen> createState() => _CinematicSplashScreenState();
}

class _CinematicSplashScreenState extends State<CinematicSplashScreen> with SingleTickerProviderStateMixin {
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;
  
  String _loadingText = "INITIALIZING ROADGUARD MOBILE";
  int _stateIndex = 0;
  Timer? _tickerTimer;
  Timer? _transitionTimer;

  final List<String> _steps = [
    "INITIALIZING ROADGUARD MOBILE",
    "LINKING AI COGNITIVE CORE",
    "CONNECTING TO SURVEILLANCE NETWORK",
    "UPLINK STABLE. LAUNCHING COMMAND SYSTEM",
  ];

  @override
  void initState() {
    super.initState();
    
    // Proactively resolve active base url during splash to prevent home screen startup lag
    ApiService.resolveBaseUrl();

    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(_fadeController);
    _fadeController.forward();

    // Cinematic status text ticker animation
    _tickerTimer = Timer.periodic(const Duration(milliseconds: 380), (timer) {
      if (mounted) {
        setState(() {
          if (_stateIndex < _steps.length - 1) {
            _stateIndex++;
            _loadingText = _steps[_stateIndex];
          } else {
            timer.cancel();
          }
        });
      }
    });

    // Fluid 1.7-second splash-to-dashboard transition
    _transitionTimer = Timer(const Duration(milliseconds: 1700), () {
      if (mounted) {
        _fadeController.reverse().then((_) {
          Navigator.pushReplacement(
            context,
            PageRouteBuilder(
              pageBuilder: (context, animation, secondaryAnimation) => const HomeScreen(),
              transitionsBuilder: (context, animation, secondaryAnimation, child) {
                return FadeTransition(opacity: animation, child: child);
              },
              transitionDuration: const Duration(milliseconds: 450),
            ),
          );
        });
      }
    });
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _tickerTimer?.cancel();
    _transitionTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CyberTheme.darkBackground,
      body: Stack(
        children: [
          const CyberGridBackground(),
          
          Center(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Symmetrical Sci-Fi Logo HUD
                  Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: CyberTheme.neonCyan.withOpacity(0.35), width: 2),
                      boxShadow: CyberTheme.neonGlow(CyberTheme.neonCyan, intensity: 0.12, radius: 12),
                    ),
                    child: const Icon(
                      Icons.radar,
                      size: 60,
                      color: CyberTheme.neonCyan,
                    ),
                  ),
                  const SizedBox(height: 25),
                  
                  // Brand Name
                  const Text(
                    "ROADGUARD AI",
                    style: TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 24,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 4,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    "TACTICAL MOBILE COMPANION V4.1",
                    style: TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 9.5,
                      fontWeight: FontWeight.bold,
                      color: CyberTheme.textSecondary,
                      letterSpacing: 1.5,
                    ),
                  ),
                  const SizedBox(height: 40),
                  
                  // Diagnostic Loading Progress Panel
                  Container(
                    width: 280,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(0.4),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: CyberTheme.neonCyan.withOpacity(0.2)),
                    ),
                    child: Column(
                      children: [
                        Text(
                          _loadingText,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontFamily: 'Courier',
                            fontSize: 9.2,
                            fontWeight: FontWeight.bold,
                            color: CyberTheme.neonCyan,
                            height: 1.3,
                          ),
                        ),
                        const SizedBox(height: 8),
                        // Loading Progress Indicator
                        SizedBox(
                          height: 2,
                          width: 200,
                          child: LinearProgressIndicator(
                            value: (_stateIndex + 1) / _steps.length,
                            backgroundColor: Colors.transparent,
                            valueColor: const AlwaysStoppedAnimation<Color>(CyberTheme.neonCyan),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
