import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image/image.dart' as img;
import '../theme/cyber_theme.dart';
import '../widgets/cyber_grid.dart';
import '../services/api_service.dart';

class AiFeedScreen extends StatefulWidget {
  const AiFeedScreen({Key? key}) : super(key: key);

  @override
  State<AiFeedScreen> createState() => _AiFeedScreenState();
}

class _AiFeedScreenState extends State<AiFeedScreen> with TickerProviderStateMixin {
  late AnimationController _scanController;
  late Animation<double> _scanAnimation;
  late AnimationController _recController;
  late Animation<double> _recPulse;

  // 4 Connection States: CONNECTING, ONLINE, RECONNECTING, OFFLINE
  String _connectionState = "CONNECTING"; 
  bool _isConnected = false;
  bool _isLoading = true;
  
  int _activeDetections = 0;
  int _cumulativePotholes = 0;
  int _roadScore = 100;
  String _roadStatus = "Excellent";
  int _fps = 0;
  int _connectionEpoch = DateTime.now().millisecondsSinceEpoch;
  Timer? _telemetryTimer;

  // Latency & Feed health simulated parameters for HUD immersion
  int _simulatedLatency = 12;
  double _simulatedUplinkQuality = 99.8;
  final Random _random = Random();

  // Camera integration variables
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraInitialized = false;
  Timer? _frameTimer;
  bool _isProcessingFrame = false;
  List<dynamic> _detections = [];

  @override
  void initState() {
    super.initState();
    
    // 60fps Scanline/radar sweep animation
    _scanController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..repeat();
    _scanAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(_scanController);

    // 1Hz Pulse animation for the recording LED indicator
    _recController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _recPulse = Tween<double>(begin: 0.2, end: 1.0).animate(_recController);

    // Run connection probe and telemetry load immediately
    _verifyBackendConnection();

    // Heartbeat verification scheduler every 2.5 seconds
    _telemetryTimer = Timer.periodic(const Duration(milliseconds: 2500), (timer) {
      if (mounted) {
        _verifyBackendConnection();
      }
    });

    // Initialize mobile camera automatically
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        debugPrint("No cameras found");
        return;
      }
      CameraDescription? backCam;
      for (var cam in _cameras) {
        if (cam.lensDirection == CameraLensDirection.back) {
          backCam = cam;
          break;
        }
      }
      backCam ??= _cameras.first;

      _cameraController = CameraController(
        backCam,
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _cameraController!.initialize();
      if (mounted) {
        setState(() {
          _isCameraInitialized = true;
        });
        _startFrameCaptureLoop();
      }
    } catch (e) {
      debugPrint("Error initializing camera: $e");
    }
  }

  void _startFrameCaptureLoop() {
    _frameTimer?.cancel();
    _frameTimer = Timer.periodic(const Duration(milliseconds: 400), (timer) async {
      if (!_isCameraInitialized || _cameraController == null || !_cameraController!.value.isInitialized) return;
      if (_isProcessingFrame) return;
      _isProcessingFrame = true;

      try {
        final XFile file = await _cameraController!.takePicture();
        final Uint8List rawBytes = await file.readAsBytes();
        
        try {
          File(file.path).deleteSync();
        } catch (_) {}

        final List<int> processedBytes = await compute(_resizeWorker, rawBytes);

        final result = await ApiService.detectPotholes(processedBytes);

        if (mounted) {
          setState(() {
            if (result['success'] == true) {
              _detections = result['detections'] ?? [];
              _activeDetections = _detections.length;
              _verifyBackendConnection();
            } else {
              _detections = [];
            }
          });
        }
      } catch (e) {
        debugPrint("Error in frame capture loop: $e");
      } finally {
        _isProcessingFrame = false;
      }
    });
  }

  Future<void> _verifyBackendConnection() async {
    final String initialStatus = _connectionState;
    final bool connected = await ApiService.checkConnection();
    
    if (connected) {
      final stats = await ApiService.fetchLiveStats();
      if (mounted) {
        setState(() {
          if (_connectionState != "ONLINE") {
            _connectionEpoch = DateTime.now().millisecondsSinceEpoch;
          }
          _connectionState = "ONLINE";
          _isConnected = true;
          _isLoading = false;
          _activeDetections = _detections.isNotEmpty ? _detections.length : (stats['livePotholes'] ?? 0);
          _cumulativePotholes = stats['total'] ?? _cumulativePotholes;
          _roadScore = stats['score'] ?? _roadScore;
          _roadStatus = stats['status'] ?? _roadStatus;
          _fps = 25 + _random.nextInt(6); 
          _simulatedLatency = 8 + _random.nextInt(10);
          _simulatedUplinkQuality = 98.5 + _random.nextDouble() * 1.4;
        });
      }
    } else {
      if (mounted) {
        setState(() {
          if (initialStatus == "ONLINE" || initialStatus == "RECONNECTING") {
            _connectionState = "RECONNECTING";
          } else {
            _connectionState = "OFFLINE";
          }
          _isConnected = false;
          _isLoading = false;
          _fps = 0;
          _simulatedLatency = 0;
          _simulatedUplinkQuality = 0.0;
        });
      }
    }
  }

  @override
  void dispose() {
    _scanController.dispose();
    _recController.dispose();
    _telemetryTimer?.cancel();
    _frameTimer?.cancel();
    _cameraController?.dispose();
    super.dispose();
  }

  // Helper color selector based on current connection state
  Color _getStateColor() {
    switch (_connectionState) {
      case "ONLINE":
        return CyberTheme.neonCyan;
      case "CONNECTING":
      case "RECONNECTING":
        return CyberTheme.neonAmber;
      case "OFFLINE":
      default:
        return CyberTheme.neonPink;
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color stateColor = _getStateColor();

    return Scaffold(
      backgroundColor: CyberTheme.darkBackground,
      appBar: AppBar(
        title: const Text(
          "[ ROADGUARD SURVEILLANCE V4.1 ]",
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 13,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
            color: CyberTheme.neonCyan,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: CyberTheme.neonCyan),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.sync_outlined, color: stateColor),
            onPressed: () {
              setState(() {
                _isLoading = true;
                _connectionEpoch = DateTime.now().millisecondsSinceEpoch;
              });
              _verifyBackendConnection();
            },
          ),
        ],
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
                  // 1. LIVE SURVEILLANCE STREAMS SCREEN CARD
                  Expanded(
                    flex: 3,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.95),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: stateColor,
                          width: 2.0,
                        ),
                        boxShadow: CyberTheme.neonGlow(
                          stateColor,
                          intensity: 0.15,
                        ),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(16),
                        child: Stack(
                          children: [
                            if (_isLoading)
                              const Center(
                                child: CircularProgressIndicator(
                                  valueColor: AlwaysStoppedAnimation<Color>(CyberTheme.neonCyan),
                                ),
                              )
                            else if (_isCameraInitialized && _cameraController != null && _cameraController!.value.isInitialized)
                              Positioned.fill(
                                child: LayoutBuilder(
                                  builder: (context, constraints) {
                                    return Stack(
                                      children: [
                                        Positioned.fill(
                                          child: FittedBox(
                                            fit: BoxFit.cover,
                                            child: SizedBox(
                                              width: _cameraController!.value.previewSize?.height ?? 640,
                                              height: _cameraController!.value.previewSize?.width ?? 480,
                                              child: CameraPreview(_cameraController!),
                                            ),
                                          ),
                                        ),
                                        // Draw Bounding Boxes Overlay
                                        ..._detections.map((det) {
                                          final double x = (det['x'] as num).toDouble();
                                          final double y = (det['y'] as num).toDouble();
                                          final double w = (det['width'] as num).toDouble();
                                          final double h = (det['height'] as num).toDouble();
                                          final double conf = (det['confidence'] as num).toDouble();

                                          final double left = (x / 640.0) * constraints.maxWidth;
                                          final double top = (y / 640.0) * constraints.maxHeight;
                                          final double width = (w / 640.0) * constraints.maxWidth;
                                          final double height = (h / 640.0) * constraints.maxHeight;

                                          return Positioned(
                                            left: left,
                                            top: top,
                                            width: width,
                                            height: height,
                                            child: Container(
                                              decoration: BoxDecoration(
                                                border: Border.all(
                                                  color: CyberTheme.neonPink,
                                                  width: 2.0,
                                                ),
                                                boxShadow: CyberTheme.neonGlow(CyberTheme.neonPink, intensity: 0.15),
                                              ),
                                              child: Stack(
                                                clipBehavior: Clip.none,
                                                children: [
                                                  Positioned(
                                                    top: -16,
                                                    left: 0,
                                                    child: Container(
                                                      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                                                      color: CyberTheme.neonPink,
                                                      child: Text(
                                                        "POTHOLE ${(conf * 100).toStringAsFixed(0)}%",
                                                        style: const TextStyle(
                                                          fontFamily: 'Courier',
                                                          fontSize: 9,
                                                          fontWeight: FontWeight.bold,
                                                          color: Colors.black,
                                                        ),
                                                      ),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          );
                                        }).toList(),
                                      ],
                                    );
                                  },
                                ),
                              )
                            else
                              _buildFallbackScannerHUD(),

                            // Neon Corner Brackets Painter overlay
                            Positioned.fill(
                              child: CustomPaint(
                                painter: HUDCornerPainter(
                                  glowColor: stateColor,
                                ),
                              ),
                            ),

                            // Camera state HUD overlays
                            _buildCameraOverlayHUD(),

                            // Tactical Crosshair Overlay
                            const Positioned.fill(
                              child: Center(
                                child: CyberCrosshairWidget(),
                              ),
                            ),

                            // Glowing scanline effect (Only visible when online)
                            if (_connectionState == "ONLINE")
                              AnimatedBuilder(
                                animation: _scanAnimation,
                                builder: (context, child) {
                                  return Positioned(
                                    left: 0,
                                    right: 0,
                                    top: MediaQuery.of(context).size.height * 0.55 * _scanAnimation.value,
                                    child: Container(
                                      height: 3,
                                      decoration: BoxDecoration(
                                        boxShadow: [
                                          BoxShadow(
                                            color: CyberTheme.neonCyan.withOpacity(0.85),
                                            blurRadius: 6,
                                            spreadRadius: 2,
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                },
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),

                  // 2. DIAGNOSTICS & SYSTEM STATUS READOUTS
                  Expanded(
                    flex: 2,
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: CyberTheme.cardBackground.withOpacity(0.7),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: CyberTheme.neonCyan.withOpacity(0.25),
                          width: 1.2,
                        ),
                        boxShadow: CyberTheme.neonGlow(CyberTheme.neonCyan, intensity: 0.03),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                "// TELEMETRY REGISTERED COGNITIVE LAYER //",
                                style: TextStyle(
                                  fontFamily: 'Courier',
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1.5,
                                  color: CyberTheme.textSecondary,
                                ),
                              ),
                              // Heartbeat state badge
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                decoration: BoxDecoration(
                                  color: stateColor.withOpacity(0.15),
                                  border: Border.all(color: stateColor.withOpacity(0.5)),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  "STATE: $_connectionState",
                                  style: TextStyle(
                                    fontFamily: 'Courier',
                                    fontSize: 9.5,
                                    fontWeight: FontWeight.bold,
                                    color: stateColor,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const Divider(color: Color(0xFF1E293B), height: 16),
                          
                          // Diagnostics telemetries grid
                          Expanded(
                            child: GridView.count(
                              crossAxisCount: 2,
                              childAspectRatio: 2.3,
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              children: [
                                _buildMetricTile("YOLO FRAME FPS", "$_fps FPS", CyberTheme.neonCyan),
                                _buildMetricTile("LIVE POTHOLES", "$_activeDetections DETECTED", _activeDetections > 0 ? CyberTheme.neonPink : CyberTheme.neonGreen),
                                _buildMetricTile(
                                  "SYSTEM UPLINK", 
                                  _isConnected ? "STABLE [SAT-COM]" : "UPLINK DOWN", 
                                  _isConnected ? CyberTheme.neonGreen : CyberTheme.neonPink
                                ),
                                _buildMetricTile(
                                  "GRID HEALTH SCORE", 
                                  "$_roadScore% $_roadStatus", 
                                  _roadScore > 85 ? CyberTheme.neonGreen : (_roadScore > 60 ? CyberTheme.neonAmber : CyberTheme.neonRed)
                                ),
                                _buildMetricTile("SESSION TOTAL LOGGED", "$_cumulativePotholes DEFECTS", CyberTheme.neonPurple),
                                _buildMetricTile("FEED QUALITY", _isConnected ? "${_simulatedUplinkQuality.toStringAsFixed(1)}%" : "0.0%", CyberTheme.neonAmber),
                              ],
                            ),
                          ),
                        ],
                      ),
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

  Widget _buildFallbackScannerHUD() {
    final Color stateColor = _getStateColor();
    
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Cyber scanning radar
          AnimatedBuilder(
            animation: _scanAnimation,
            builder: (context, child) {
              return Container(
                width: 140,
                height: 140,
                child: CustomPaint(
                  painter: RadarScannerPainter(
                    _scanAnimation.value * 2 * pi,
                    stateColor,
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          Text(
            _connectionState == "RECONNECTING" 
                ? "CONNECTION LOST — RECONNECTING UPLINK" 
                : "BACKEND OFFLINE — SURVEILLANCE LINK LOST",
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 12,
              fontWeight: FontWeight.w900,
              letterSpacing: 1.5,
              color: stateColor,
              shadows: CyberTheme.neonGlow(stateColor, intensity: 0.4),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            "Targeting Flask socket server: ${ApiService.activeBaseUrl}\nAuto-heartbeat scan active.",
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 10,
              color: CyberTheme.textSecondary,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraOverlayHUD() {
    final double pulse = _recPulse.value;
    final bool online = _connectionState == "ONLINE";

    return Positioned.fill(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    // Pulsing recording LED indicator
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: online ? CyberTheme.neonRed : CyberTheme.neonPink,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: (online ? CyberTheme.neonRed : CyberTheme.neonPink).withOpacity(0.6 * pulse),
                            blurRadius: 4,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: (online ? CyberTheme.neonRed : CyberTheme.neonPink).withOpacity(0.15),
                        border: Border.all(color: (online ? CyberTheme.neonRed : CyberTheme.neonPink).withOpacity(0.4)),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        online ? "REC // LIVE FEED" : "STANDBY // EMULATOR",
                        style: TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          color: online ? CyberTheme.neonRed : CyberTheme.neonPink,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                  ],
                ),
                
                // Pulsing SAT-LINK Uplink Signal Meter
                Row(
                  children: [
                    Text(
                      online ? "||||| SAT-LINK " : "||    SAT-LINK ",
                      style: TextStyle(
                        fontFamily: 'Courier',
                        fontSize: 9,
                        fontWeight: FontWeight.w900,
                        color: online ? CyberTheme.neonGreen.withOpacity(0.6 + 0.4 * pulse) : CyberTheme.neonPink,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      online ? "[LATENCY: ${_simulatedLatency}ms]" : "[NO UPLINK]",
                      style: TextStyle(
                        fontFamily: 'Courier',
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                        color: online ? CyberTheme.neonGreen : CyberTheme.neonPink,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // Advanced diagnostics badges: AI engine core & Feed Health
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.5),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: CyberTheme.neonCyan.withOpacity(0.3)),
                      ),
                      child: Text(
                        online ? "AI CORE: ACTIVE" : "AI CORE: STANDBY",
                        style: TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 8,
                          fontWeight: FontWeight.bold,
                          color: online ? CyberTheme.neonGreen : CyberTheme.neonPink,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.5),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: CyberTheme.neonCyan.withOpacity(0.3)),
                      ),
                      child: Text(
                        online ? "HEALTH: OPTIMAL" : "HEALTH: LOST",
                        style: TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 8,
                          fontWeight: FontWeight.bold,
                          color: online ? CyberTheme.neonGreen : CyberTheme.neonPink,
                        ),
                      ),
                    ),
                  ],
                ),
                Text(
                  "MODEL: YOLOv8s_POTHOLE",
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 9,
                    fontWeight: FontWeight.bold,
                    color: CyberTheme.textSecondary.withOpacity(0.8),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricTile(String title, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.3),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: color.withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: CyberTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 13,
              fontWeight: FontWeight.w900,
              color: color,
              shadows: [
                Shadow(
                  color: color.withOpacity(0.3),
                  blurRadius: 4,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Concentric Sweep Radar Fallback Painter
class RadarScannerPainter extends CustomPainter {
  final double sweepAngle;
  final Color baseColor;

  RadarScannerPainter(this.sweepAngle, this.baseColor);

  @override
  void paint(Canvas canvas, Size size) {
    final double cx = size.width / 2;
    final double cy = size.height / 2;
    final double maxRadius = min(size.width, size.height) * 0.48;

    final paint = Paint()
      ..color = baseColor.withOpacity(0.15)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    // Draw Concentric rings
    canvas.drawCircle(Offset(cx, cy), maxRadius, paint);
    canvas.drawCircle(Offset(cx, cy), maxRadius * 0.66, paint);
    canvas.drawCircle(Offset(cx, cy), maxRadius * 0.33, paint);

    // Draw grids
    canvas.drawLine(Offset(cx - maxRadius, cy), Offset(cx + maxRadius, cy), paint);
    canvas.drawLine(Offset(cx, cy - maxRadius), Offset(cx, cy + maxRadius), paint);

    // Sweeping beam
    final sweepPaint = Paint()
      ..color = baseColor.withOpacity(0.7)
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke;
    
    final double endX = cx + maxRadius * cos(sweepAngle);
    final double endY = cy + maxRadius * sin(sweepAngle);
    canvas.drawLine(Offset(cx, cy), Offset(endX, endY), sweepPaint);

    // Sweeping gradient trail
    final path = Path();
    path.moveTo(cx, cy);
    for (double a = 0; a <= 0.6; a += 0.05) {
      final double angle = sweepAngle - a;
      path.lineTo(cx + maxRadius * cos(angle), cy + maxRadius * sin(angle));
    }
    path.close();

    final trailPaint = Paint()
      ..shader = RadialGradient(
        colors: [baseColor.withOpacity(0.25), baseColor.withOpacity(0.0)],
      ).createShader(Rect.fromCircle(center: Offset(cx, cy), radius: maxRadius))
      ..style = PaintingStyle.fill;
    
    canvas.drawPath(path, trailPaint);
  }

  @override
  bool shouldRepaint(covariant RadarScannerPainter oldDelegate) {
    return oldDelegate.sweepAngle != sweepAngle || oldDelegate.baseColor != baseColor;
  }
}

// Tactical Corner Bracket HUD Painter
class HUDCornerPainter extends CustomPainter {
  final Color glowColor;
  HUDCornerPainter({required this.glowColor});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = glowColor.withOpacity(0.8)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke;

    final double len = 20.0;

    // Draw corners
    // Top-Left
    canvas.drawLine(Offset.zero, Offset(len, 0), paint);
    canvas.drawLine(Offset.zero, Offset(0, len), paint);

    // Top-Right
    canvas.drawLine(Offset(size.width, 0), Offset(size.width - len, 0), paint);
    canvas.drawLine(Offset(size.width, 0), Offset(size.width, len), paint);

    // Bottom-Left
    canvas.drawLine(Offset(0, size.height), Offset(len, size.height), paint);
    canvas.drawLine(Offset(0, size.height), Offset(0, size.height - len), paint);

    // Bottom-Right
    canvas.drawLine(Offset(size.width, size.height), Offset(size.width - len, size.height), paint);
    canvas.drawLine(Offset(size.width, size.height), Offset(size.width, size.height - len), paint);
  }

  @override
  bool shouldRepaint(covariant HUDCornerPainter oldDelegate) => oldDelegate.glowColor != glowColor;
}

// Central crosshair overlay
class CyberCrosshairWidget extends StatelessWidget {
  const CyberCrosshairWidget({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 120,
      height: 120,
      child: CustomPaint(
        painter: CrosshairPainter(),
      ),
    );
  }
}

class CrosshairPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = CyberTheme.neonCyan.withOpacity(0.4)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final double length = 18.0;

    // Draw reticles
    // Top-Left corner
    canvas.drawLine(Offset.zero, Offset(length, 0), paint);
    canvas.drawLine(Offset.zero, Offset(0, length), paint);

    // Top-Right corner
    canvas.drawLine(Offset(size.width, 0), Offset(size.width - length, 0), paint);
    canvas.drawLine(Offset(size.width, 0), Offset(size.width, length), paint);

    // Bottom-Left corner
    canvas.drawLine(Offset(0, size.height), Offset(length, size.height), paint);
    canvas.drawLine(Offset(0, size.height), Offset(0, size.height - length), paint);

    // Bottom-Right corner
    canvas.drawLine(Offset(size.width, size.height), Offset(size.width - length, size.height), paint);
    canvas.drawLine(Offset(size.width, size.height), Offset(size.width, size.height - length), paint);

    // Center dot circle
    canvas.drawCircle(Offset(size.width / 2, size.height / 2), 6, paint);
  }

  @override
  bool shouldRepaint(covariant CrosshairPainter oldDelegate) => false;
}

// Top-level worker function to resize and compress frames in a separate Isolate
List<int> _resizeWorker(Uint8List rawBytes) {
  final img.Image? decoded = img.decodeImage(rawBytes);
  if (decoded == null) return rawBytes;
  final img.Image resized = img.copyResize(decoded, width: 640, height: 640);
  return img.encodeJpg(resized, quality: 80);
}
