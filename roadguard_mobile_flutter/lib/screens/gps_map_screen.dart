import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/cyber_theme.dart';
import '../widgets/cyber_grid.dart';

class GpsMapScreen extends StatefulWidget {
  final String? initialSearch;
  const GpsMapScreen({Key? key, this.initialSearch}) : super(key: key);

  @override
  State<GpsMapScreen> createState() => _GpsMapScreenState();
}

class _GpsMapScreenState extends State<GpsMapScreen> with SingleTickerProviderStateMixin {
  final TextEditingController _searchController = TextEditingController();
  late AnimationController _radarController;
  late Animation<double> _radarAnimation;

  bool _isScanning = false;
  String _currentLocationName = "BENGALURU CENTRAL GRID";
  int _potholesFound = 12;
  String _threatLevel = "MODERATE";
  double _threatScore = 45.0;
  String _coordinatesText = "LAT: 12.9716° N // LON: 77.5946° E";
  String _roadStatus = "NOMINAL TELEMETRY";
  int _criticalZones = 3;

  // Active radar targets (pothole indicators)
  List<Offset> _tacticalNodes = [
    const Offset(100, 150),
    const Offset(220, 110),
    const Offset(180, 260),
    const Offset(280, 220),
    const Offset(80, 310),
  ];

  @override
  void initState() {
    super.initState();
    // Continuous 2.5s radar circle sweep animation
    _radarController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    )..repeat();
    _radarAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(_radarController);

    if (widget.initialSearch != null) {
      _searchController.text = widget.initialSearch!;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _triggerScan(widget.initialSearch!);
      });
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    _radarController.dispose();
    super.dispose();
  }

  void _triggerScan(String targetLocation) {
    final query = targetLocation.trim();
    if (query.isEmpty) return;

    setState(() {
      _isScanning = true;
      _currentLocationName = "ACQUIRING LINK TO ${query.toUpperCase()}...";
    });

    // Simulate lock sequence
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() {
          _isScanning = false;
          _currentLocationName = query.toUpperCase();
          
          final lowerQuery = query.toLowerCase();
          if (lowerQuery.contains("whitefield")) {
            _potholesFound = 7;
            _threatLevel = "CRITICAL";
            _threatScore = 85.0;
            _coordinatesText = "LAT: 12.9698° N // LON: 77.7499° E";
            _roadStatus = "SEVERE SURFACE DAMAGE";
            _criticalZones = 7;
            _tacticalNodes = [
              const Offset(80, 120),
              const Offset(140, 160),
              const Offset(200, 100),
              const Offset(240, 220),
              const Offset(180, 280),
              const Offset(110, 320),
              const Offset(290, 300),
            ];
          } else if (lowerQuery.contains("hebbal")) {
            _potholesFound = 2;
            _threatLevel = "LOW THREAT";
            _threatScore = 20.0;
            _coordinatesText = "LAT: 13.0358° N // LON: 77.5970° E";
            _roadStatus = "NOMINAL TELEMETRY";
            _criticalZones = 2;
            _tacticalNodes = [
              const Offset(150, 180),
              const Offset(210, 240),
            ];
          } else if (lowerQuery.contains("mg road")) {
            _potholesFound = 3;
            _threatLevel = "MODERATE";
            _threatScore = 45.0;
            _coordinatesText = "LAT: 12.9733° N // LON: 77.6117° E";
            _roadStatus = "SLIGHT SURFACING ANOMALIES";
            _criticalZones = 3;
            _tacticalNodes = [
              const Offset(120, 140),
              const Offset(180, 220),
              const Offset(260, 180),
            ];
          } else if (lowerQuery.contains("indiranagar")) {
            _potholesFound = 1;
            _threatLevel = "LOW THREAT";
            _threatScore = 15.0;
            _coordinatesText = "LAT: 12.9784° N // LON: 77.6408° E";
            _roadStatus = "NOMINAL TELEMETRY";
            _criticalZones = 1;
            _tacticalNodes = [
              const Offset(190, 200),
            ];
          } else if (lowerQuery.contains("btm layout")) {
            _potholesFound = 8;
            _threatLevel = "CRITICAL";
            _threatScore = 90.0;
            _coordinatesText = "LAT: 12.9166° N // LON: 77.6101° E";
            _roadStatus = "SEVERE SURFACE DAMAGE";
            _criticalZones = 8;
            _tacticalNodes = [
              const Offset(70, 100),
              const Offset(120, 150),
              const Offset(160, 210),
              const Offset(220, 140),
              const Offset(250, 260),
              const Offset(190, 310),
              const Offset(100, 280),
              const Offset(280, 320),
            ];
          } else if (lowerQuery.contains("koramangala")) {
            _potholesFound = 4;
            _threatLevel = "MODERATE";
            _threatScore = 50.0;
            _coordinatesText = "LAT: 12.9279° N // LON: 77.6271° E";
            _roadStatus = "SLIGHT SURFACING ANOMALIES";
            _criticalZones = 4;
            _tacticalNodes = [
              const Offset(110, 160),
              const Offset(230, 130),
              const Offset(170, 220),
              const Offset(250, 280),
            ];
          } else {
            _potholesFound = 10;
            _threatLevel = "HIGH THREAT";
            _threatScore = 65.0;
            _coordinatesText = "LAT: 12.9304° N // LON: 77.6784° E";
            _roadStatus = "CRACKED RADAR ROUTE";
            _criticalZones = 5;
            _tacticalNodes = [
              const Offset(100, 150),
              const Offset(220, 110),
              const Offset(180, 260),
              const Offset(280, 220),
              const Offset(80, 310),
            ];
          }
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CyberTheme.darkBackground,
      appBar: AppBar(
        title: const Text(
          "TACTICAL GPS RADAR",
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: CyberTheme.neonCyan),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Stack(
        children: [
          const CyberGridBackground(),

          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // 1. SEARCH BAR
                  _buildSearchBar(),
                  const SizedBox(height: 18),

                  // 2. CYBER TACTICAL SCANNER RADAR CANVAS
                  Expanded(
                    flex: 4,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A).withOpacity(0.9),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: CyberTheme.neonCyan.withOpacity(_isScanning ? 0.8 : 0.4),
                          width: 1.5,
                        ),
                        boxShadow: CyberTheme.neonGlow(CyberTheme.neonCyan, intensity: 0.05),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: Stack(
                          children: [
                            // Custom Painter drawing glowing bright green/cyan map lines & radar sweeps
                            AnimatedBuilder(
                              animation: _radarAnimation,
                              builder: (context, child) {
                                return Positioned.fill(
                                  child: CustomPaint(
                                    painter: TacticalRadarPainter(
                                      nodes: _tacticalNodes,
                                      scanActive: _isScanning,
                                      radarValue: _radarAnimation.value,
                                    ),
                                  ),
                                );
                              },
                            ),

                            // Loading scan sweep overlay
                            if (_isScanning)
                              const Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    CircularProgressIndicator(
                                      valueColor: AlwaysStoppedAnimation<Color>(CyberTheme.neonCyan),
                                    ),
                                    SizedBox(height: 16),
                                    Text(
                                      "LOCKING TARGET COORDINATES...",
                                      style: TextStyle(
                                        fontFamily: 'Courier',
                                        fontSize: 10.5,
                                        fontWeight: FontWeight.bold,
                                        color: CyberTheme.neonCyan,
                                        letterSpacing: 1,
                                      ),
                                    ),
                                  ],
                                ),
                              ),

                            // Map Info Overlay Tags
                            Positioned(
                              top: 14,
                              left: 14,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _currentLocationName,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 13,
                                      letterSpacing: 1,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    _coordinatesText,
                                    style: const TextStyle(
                                      fontFamily: 'Courier',
                                      fontSize: 9.5,
                                      color: CyberTheme.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),

                  // 3. STATS INFO BOX (Advanced V3 details)
                  _buildStatsInfoPanel(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      decoration: BoxDecoration(
        color: CyberTheme.cardBackground.withOpacity(0.8),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: CyberTheme.neonCyan.withOpacity(0.3),
        ),
      ),
      child: TextField(
        controller: _searchController,
        style: const TextStyle(fontSize: 14, color: Colors.white),
        decoration: InputDecoration(
          hintText: "Scan Sector... (Hebbal, Whitefield, MG Road)",
          hintStyle: const TextStyle(color: CyberTheme.textMuted, fontSize: 13),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          suffixIcon: IconButton(
            icon: const Icon(Icons.gps_fixed, color: CyberTheme.neonCyan),
            onPressed: () => _triggerScan(_searchController.text),
          ),
        ),
        onSubmitted: (text) => _triggerScan(text),
      ),
    );
  }

  Widget _buildStatsInfoPanel() {
    Color threatColor = CyberTheme.neonGreen;
    if (_threatLevel.contains("CRITICAL")) {
      threatColor = CyberTheme.neonRed;
    } else if (_threatLevel.contains("HIGH")) {
      threatColor = CyberTheme.neonAmber;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: CyberTheme.cardBackground.withOpacity(0.6),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: CyberTheme.neonCyan.withOpacity(0.2),
          width: 1.2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "THREAT OVERVIEW DIAGNOSTICS",
                    style: TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 10.5,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1,
                      color: CyberTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _roadStatus,
                    style: TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: threatColor,
                    ),
                  ),
                ],
              ),
              Icon(Icons.security, color: threatColor, size: 18),
            ],
          ),
          const Divider(color: Color(0xFF1E293B), height: 16),
          
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text("Tactical threat score:", style: TextStyle(fontSize: 12.5, color: CyberTheme.textSecondary)),
              Text("${_threatScore.toInt()}%", style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: threatColor)),
            ],
          ),
          const SizedBox(height: 8),
          
          // Threat Progress Bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _threatScore / 100.0,
              backgroundColor: const Color(0xFF1E293B),
              valueColor: AlwaysStoppedAnimation<Color>(threatColor),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 14),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatsBadge("POTHOLES SCAN", "$_potholesFound LOGGED", CyberTheme.neonPink),
              _buildStatsBadge("SECTOR SHIELD", _threatLevel, threatColor),
              _buildStatsBadge("RISK ZONES", "$_criticalZones ACTIVE", CyberTheme.neonAmber),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatsBadge(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontFamily: 'Courier',
            fontSize: 8.5,
            fontWeight: FontWeight.bold,
            color: CyberTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: TextStyle(
            fontSize: 12.5,
            fontWeight: FontWeight.w900,
            color: color,
          ),
        ),
      ],
    );
  }
}

// Tactical Map Custom Radar Painter
class TacticalRadarPainter extends CustomPainter {
  final List<Offset> nodes;
  final bool scanActive;
  final double radarValue;

  TacticalRadarPainter({
    required this.nodes,
    required this.scanActive,
    required this.radarValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    
    final gridPaint = Paint()
      ..color = CyberTheme.neonCyan.withOpacity(0.12)
      ..strokeWidth = 1.0;

    final radarLinePaint = Paint()
      ..color = CyberTheme.neonCyan.withOpacity(0.2)
      ..strokeWidth = 1.5;

    // Draw grid intersections
    for (double x = 0; x < size.width; x += 40) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += 40) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // Concentric expanding radar rings
    final pulsePaint = Paint()
      ..color = CyberTheme.neonCyan.withOpacity(0.3 * (1.0 - radarValue))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;
    
    final double maxRadius = size.width * 0.45;
    canvas.drawCircle(center, maxRadius * radarValue, pulsePaint);
    canvas.drawCircle(center, maxRadius * ((radarValue + 0.5) % 1.0), pulsePaint);

    // Draw crosshair axes
    canvas.drawLine(Offset(0, center.dy), Offset(size.width, center.dy), radarLinePaint);
    canvas.drawLine(Offset(center.dx, 0), Offset(center.dx, size.height), radarLinePaint);

    // Connect nodes with a glowing path route trail
    final pathPaint = Paint()
      ..color = CyberTheme.neonPurple.withOpacity(0.4)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    
    if (nodes.length >= 2) {
      final path = Path()..moveTo(nodes[0].dx, nodes[0].dy);
      for (int i = 1; i < nodes.length; i++) {
        path.lineTo(nodes[i].dx, nodes[i].dy);
      }
      canvas.drawPath(path, pathPaint);
    }

    // Draw warning nodes
    final nodePaint = Paint()
      ..color = CyberTheme.neonPink
      ..style = PaintingStyle.fill;

    final nodePulsePaint = Paint()
      ..color = CyberTheme.neonPink.withOpacity(0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    for (var node in nodes) {
      canvas.drawCircle(node, 6, nodePaint);
      canvas.drawCircle(node, 12, nodePulsePaint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
