import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/cyber_theme.dart';
import '../widgets/cyber_grid.dart';
import '../widgets/glowing_avatar.dart';
import '../widgets/command_card.dart';
import '../services/api_service.dart';

// Screens
import 'ai_feed_screen.dart';
import 'gps_map_screen.dart';
import 'voice_copilot_screen.dart';
import 'alerts_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  late AnimationController _hudPulseController;
  final List<String> _terminalLogs = [];
  final ScrollController _terminalScrollController = ScrollController();
  int _logIndex = 0;
  
  // Real-time Telemetry state parameters
  int _totalPotholes = 14;
  int _safetyScore = 94;
  int _criticalAlerts = 2;
  bool _isOffline = true;

  Timer? _telemetryTimer;
  Timer? _clockTimer;
  DateTime _currentTime = DateTime.now();

  final List<String> _mockLogs = [
    "[SYS] RoadGuard Mobile Command V4 initialized.",
    "[JARVIS] Establishing secure sat-uplink connection...",
    "[SYS] Direct webcam AI video feed socket synchronizing.",
    "[AI] Core YOLOv8 inference weights loaded.",
    "[GPS] Tactical smart-city navigation node online.",
    "[JARVIS] Real-time visual frame analyzer active.",
    "[SYS] Flask dashboard web-system connected on port 5001.",
    "[AI] Surface threat analysis scan running.",
    "[JARVIS] Safety score nominal at 94 percent.",
    "[JARVIS] Vocal assistance sub-systems stand-by.",
  ];

  @override
  void initState() {
    super.initState();
    
    // 60fps HUD pulse animation
    _hudPulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    // Defer heavy network loaders and secondary tickers until after initial frame is drawn
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadBackendTelemetry();
      _startTerminalTicker();
      
      // Live digital clock timer
      _clockTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (mounted) {
          setState(() {
            _currentTime = DateTime.now();
          });
        }
      });

      // Real-time telemetry fetch scheduler
      _telemetryTimer = Timer.periodic(const Duration(seconds: 3), (timer) {
        if (mounted) {
          _loadBackendTelemetry();
        }
      });
    });
  }

  Future<void> _loadBackendTelemetry() async {
    final stats = await ApiService.fetchLiveStats();
    if (mounted) {
      setState(() {
        _totalPotholes = stats['total'] ?? 14;
        _safetyScore = stats['score'] ?? 94;
        _criticalAlerts = stats['critical'] ?? 2;
        _isOffline = stats['isOffline'] ?? true;
      });
    }
  }

  void _startTerminalTicker() {
    _addLog();
    Timer.periodic(const Duration(seconds: 4), (timer) {
      if (mounted) {
        _addLog();
      } else {
        timer.cancel();
      }
    });
  }

  void _addLog() {
    setState(() {
      _terminalLogs.add(_mockLogs[_logIndex % _mockLogs.length]);
      _logIndex++;
    });
    // Auto-scroll terminal
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_terminalScrollController.hasClients) {
        _terminalScrollController.animateTo(
          _terminalScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _hudPulseController.dispose();
    _clockTimer?.cancel();
    _telemetryTimer?.cancel();
    _terminalScrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CyberTheme.darkBackground,
      body: Stack(
        children: [
          const CyberGridBackground(),

          SafeArea(
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 15.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // 1. HEADER HUD
                  _buildHeaderHUD(),
                  const SizedBox(height: 20),

                  // 2. MAIN STATUS TELEMETRY PANEL
                  _buildStatusDashboard(),
                  const SizedBox(height: 25),

                  // 3. SECTOR LABEL
                  const Padding(
                    padding: EdgeInsets.only(left: 4.0, bottom: 12.0),
                    child: Text(
                      "TACTICAL APPLICATIONS",
                      style: CyberTheme.sectionHeader,
                    ),
                  ),

                  // 4. ACTION GRID TILES (Navigable Screens)
                  _buildActionGrid(),
                  const SizedBox(height: 25),

                  // 5. LIVE TERMINAL LOG CONSOLE
                  _buildTerminalHUD(),
                  const SizedBox(height: 20),

                  // 6. BOTTOM HUD FOOTER
                  _buildFooterHUD(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderHUD() {
    final double pulse = _hudPulseController.value;
    final Color statusColor = _isOffline ? CyberTheme.neonPink : CyberTheme.neonGreen;

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                AnimatedBuilder(
                  animation: _hudPulseController,
                  builder: (context, child) {
                    return Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: statusColor.withOpacity(0.6 * pulse),
                            blurRadius: 4,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    );
                  },
                ),
                const SizedBox(width: 8),
                Text(
                  _isOffline ? "UPLINK: SIMULATED [OFFLINE]" : "UPLINK: ACTIVE [SAT-COM]",
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: statusColor,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            // Symmetrical glowing title similar to desktop website
            ShaderMask(
              shaderCallback: (bounds) => const LinearGradient(
                colors: [CyberTheme.neonCyan, CyberTheme.neonPurple],
              ).createShader(bounds),
              child: const Text(
                "ROADGUARD AI",
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 3,
                  color: Colors.white,
                ),
              ),
            ),
          ],
        ),

        // Custom pulsing radar HUD reticle
        GlowingAvatar(
          icon: Icons.radar,
          glowColor: _isOffline ? CyberTheme.neonPink : CyberTheme.neonCyan,
        ),
      ],
    );
  }

  Widget _buildStatusDashboard() {
    final double pulse = _hudPulseController.value;
    final Color engineColor = _isOffline ? CyberTheme.neonPink : CyberTheme.neonGreen;
    final String timeString = "${_currentTime.hour.toString().padLeft(2, '0')}:${_currentTime.minute.toString().padLeft(2, '0')}:${_currentTime.second.toString().padLeft(2, '0')}";
    
    return Container(
      decoration: BoxDecoration(
        color: CyberTheme.cardBackground.withOpacity(0.65),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: CyberTheme.neonCyan.withOpacity(0.2 + 0.1 * pulse),
          width: 1.5,
        ),
        boxShadow: CyberTheme.neonGlow(CyberTheme.neonCyan, intensity: 0.05 + 0.02 * pulse, radius: 10),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Top Bar of Dashboard
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: engineColor,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: engineColor.withOpacity(0.6 * pulse),
                            blurRadius: 4,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _isOffline ? "COGNITIVE RADAR: STANDBY" : "COGNITIVE RADAR: ONLINE",
                      style: TextStyle(
                        fontFamily: 'Courier',
                        fontSize: 10.5,
                        fontWeight: FontWeight.bold,
                        color: engineColor,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ),
                Text(
                  "SYS_TIME: $timeString",
                  style: const TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 10.5,
                    fontWeight: FontWeight.bold,
                    color: CyberTheme.neonCyan,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TacticalHUDDivider(color: CyberTheme.neonCyan.withOpacity(0.4)),
            const SizedBox(height: 16),
            
            // Safety Score Gradient Gauge
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "GRID SURFACE INTEGRITY",
                        style: TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 9.5,
                          fontWeight: FontWeight.bold,
                          color: CyberTheme.textSecondary,
                          letterSpacing: 1.2,
                        ),
                      ),
                      const SizedBox(height: 6),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: Container(
                          height: 10,
                          child: LinearProgressIndicator(
                            value: _safetyScore / 100.0,
                            backgroundColor: Colors.black.withOpacity(0.5),
                            valueColor: AlwaysStoppedAnimation<Color>(
                              _safetyScore > 85
                                  ? CyberTheme.neonGreen
                                  : (_safetyScore > 60 ? CyberTheme.neonAmber : CyberTheme.neonRed),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.4),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: (_safetyScore > 85
                          ? CyberTheme.neonGreen
                          : (_safetyScore > 60 ? CyberTheme.neonAmber : CyberTheme.neonRed)).withOpacity(0.4),
                    ),
                  ),
                  child: Column(
                    children: [
                      Text(
                        "$_safetyScore%",
                        style: TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                          color: _safetyScore > 85
                              ? CyberTheme.neonGreen
                              : (_safetyScore > 60 ? CyberTheme.neonAmber : CyberTheme.neonRed),
                        ),
                      ),
                      Text(
                        _safetyScore > 85 ? "STABLE" : (_safetyScore > 60 ? "WARNING" : "CRITICAL"),
                        style: const TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 8,
                          fontWeight: FontWeight.bold,
                          color: CyberTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // 2-Column Grid of Telemetries
            Row(
              children: [
                Expanded(child: _buildTelemetryHUDCell("POTHOLES LOGGED", "$_totalPotholes Defects", CyberTheme.neonPink)),
                const SizedBox(width: 12),
                Expanded(child: _buildTelemetryHUDCell("CRITICAL SECTORS", "$_criticalAlerts Zones", CyberTheme.neonAmber)),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _buildTelemetryHUDCell("UPLINK QUALITY", _isOffline ? "LOST [SIM]" : "99.4% [SAT]", _isOffline ? CyberTheme.neonPink : CyberTheme.neonGreen)),
                const SizedBox(width: 12),
                Expanded(child: _buildTelemetryHUDCell("AI ENGINE PULSE", _isOffline ? "STANDBY" : "ACTIVE", _isOffline ? CyberTheme.neonPurple : CyberTheme.neonCyan)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTelemetryHUDCell(String title, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.35),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: color.withOpacity(0.25),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 8.5,
              fontWeight: FontWeight.bold,
              color: CyberTheme.textSecondary.withOpacity(0.8),
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value.toUpperCase(),
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 12.5,
              fontWeight: FontWeight.bold,
              color: color,
              shadows: [
                Shadow(
                  color: color.withOpacity(0.4),
                  blurRadius: 5,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionGrid() {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 16,
      mainAxisSpacing: 16,
      childAspectRatio: 1.15,
      children: [
        CommandCard(
          title: "LIVE AI FEED",
          subtitle: "Webcam Stream",
          icon: Icons.videocam,
          neonColor: CyberTheme.neonCyan,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const AiFeedScreen()),
            );
          },
        ),
        CommandCard(
          title: "SMART GPS MAP",
          subtitle: "Tactical Node",
          icon: Icons.map_outlined,
          neonColor: CyberTheme.neonPink,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const GpsMapScreen()),
            );
          },
        ),
        CommandCard(
          title: "AI VOICE CO-PILOT",
          subtitle: "Jarvis Agent",
          icon: Icons.keyboard_voice,
          neonColor: CyberTheme.neonPurple,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const VoiceCopilotScreen()),
            );
          },
        ),
        CommandCard(
          title: "ALERTS & REPORTS",
          subtitle: "Logs Registry",
          icon: Icons.notifications_active,
          neonColor: CyberTheme.neonAmber,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => AlertsScreen()),
            );
          },
        ),
      ],
    );
  }

  Widget _buildTerminalHUD() {
    final double pulse = _hudPulseController.value;

    return Container(
      height: 125,
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.85),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: CyberTheme.neonCyan.withOpacity(0.15),
          width: 1.2,
        ),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "COMMUNICATIONS LOG TERMINAL",
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                  color: Color(0xFF475569),
                ),
              ),
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: CyberTheme.neonCyan.withOpacity(0.3 + 0.7 * pulse),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: CyberTheme.neonCyan.withOpacity(0.5 * pulse),
                      blurRadius: 4,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Expanded(
            child: ListView.builder(
              controller: _terminalScrollController,
              itemCount: _terminalLogs.length,
              itemBuilder: (context, index) {
                final log = _terminalLogs[index];
                Color logColor = const Color(0xFFE2E8F0);
                if (log.startsWith("[SYS]")) {
                  logColor = const Color(0xFF64748B);
                } else if (log.startsWith("[JARVIS]")) {
                  logColor = CyberTheme.neonGreen;
                } else if (log.startsWith("[AI]")) {
                  logColor = CyberTheme.neonCyan;
                } else if (log.startsWith("[GPS]")) {
                  logColor = CyberTheme.neonPink;
                }

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2.0),
                  child: Text(
                    log,
                    style: CyberTheme.terminalText.copyWith(color: logColor),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooterHUD() {
    return const Center(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: 10.0),
        child: Text(
          "ROADGUARD MOBILE COMMAND CENTER V4",
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 11,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
            color: Color(0xFF475569),
          ),
        ),
      ),
    );
  }
}

// Custom sci-fi line divider widget
class TacticalHUDDivider extends StatelessWidget {
  final Color color;
  const TacticalHUDDivider({Key? key, required this.color}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 6,
      child: CustomPaint(
        painter: _TacticalDividerPainter(color),
      ),
    );
  }
}

class _TacticalDividerPainter extends CustomPainter {
  final Color color;
  _TacticalDividerPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final double w = size.width;
    // Draw a cyberpunk horizontal line with angled brackets at the ends
    canvas.drawLine(Offset(0, size.height / 2), Offset(w, size.height / 2), paint);
    canvas.drawLine(Offset.zero, Offset(0, size.height), paint);
    canvas.drawLine(Offset(w, 0), Offset(w, size.height), paint);
    
    // Tiny center tech dot decoration
    canvas.drawRect(
      Rect.fromCenter(center: Offset(w / 2, size.height / 2), width: 8, height: 4),
      Paint()..color = color,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
