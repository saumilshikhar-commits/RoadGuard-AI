import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:flutter_tts/flutter_tts.dart';
import '../theme/cyber_theme.dart';
import '../widgets/cyber_grid.dart';
import '../services/api_service.dart';
import 'gps_map_screen.dart';

class VoiceCopilotScreen extends StatefulWidget {
  const VoiceCopilotScreen({Key? key}) : super(key: key);

  @override
  State<VoiceCopilotScreen> createState() => _VoiceCopilotScreenState();
}

class _VoiceCopilotScreenState extends State<VoiceCopilotScreen> with SingleTickerProviderStateMixin {
  late AnimationController _waveformController;
  final stt.SpeechToText _speech = stt.SpeechToText();
  final ScrollController _chatScrollController = ScrollController();
  final FlutterTts _flutterTts = FlutterTts();
  
  bool _speechEnabled = false;
  bool _isListeningState = false;
  String _assistantState = "STANDBY"; // STANDBY, LISTENING, PROCESSING, RESPONDING
  String _liveTranscription = "";
  Color _stateColor = CyberTheme.neonCyan;
  
  // 25-node rich vertical equalizer frequency bars
  final List<double> _waveformHeights = List.generate(25, (index) => 4.0);
  final TextEditingController _manualInputController = TextEditingController();
  bool _isSpeaking = false;

  Future<void> _initTts() async {
    await _flutterTts.setLanguage("en-US");
    await _flutterTts.setSpeechRate(0.5);
    await _flutterTts.setPitch(1.0);
    await _flutterTts.setVolume(1.0);
    
    // Eliminate double pauses and lag
    await _flutterTts.awaitSpeakCompletion(true);
    
    _flutterTts.setStartHandler(() {
      _isSpeaking = true;
      if (mounted) {
        setState(() {
          _assistantState = "RESPONDING";
          _stateColor = CyberTheme.neonPurple;
        });
      }
    });

    _flutterTts.setCompletionHandler(() {
      _isSpeaking = false;
      if (mounted) {
        setState(() {
          _assistantState = "STANDBY";
          _stateColor = CyberTheme.neonCyan;
        });
      }
    });

    _flutterTts.setErrorHandler((msg) {
      _isSpeaking = false;
      if (mounted) {
        setState(() {
          _assistantState = "STANDBY";
          _stateColor = CyberTheme.neonCyan;
        });
      }
    });
  }

  // Multi-line conversation dialogues stream log
  final List<Map<String, String>> _messages = [
    {
      "sender": "JARVIS",
      "text": "RoadGuard AI voice sub-system active. Tap the microphone reticle or enter a vocal query."
    }
  ];

  final List<String> _sampleQueries = [
    "Hello",
    "Who are you",
    "Open GPS",
    "Scan Whitefield",
    "Scan Hebbal",
    "Scan MG Road",
    "How is traffic",
    "What is RoadGuard",
    "Tell me road condition",
    "Good morning",
    "What can you do",
  ];

  @override
  void initState() {
    super.initState();
    _initTts();
    
    // Continuous smooth audio wave animation controller
    _waveformController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();

    _waveformController.addListener(() {
      if (_assistantState == "LISTENING" || _assistantState == "RESPONDING") {
        setState(() {
          final t = _waveformController.value * 2 * pi;
          for (int i = 0; i < _waveformHeights.length; i++) {
            final amplitude = _assistantState == "LISTENING" ? 18.0 : 28.0;
            final base = 5.0;
            // Generate elegant, multi-harmonic organic frequency shape
            final waveVal = sin(t + (i * 0.35)) * cos(t * 1.7 - (i * 0.15)) + 0.3 * sin(t * 3.0 + i);
            _waveformHeights[i] = (waveVal.abs() * amplitude) + base;
          }
        });
      } else {
        if (_waveformHeights.any((h) => h > 4.0)) {
          setState(() {
            for (int i = 0; i < _waveformHeights.length; i++) {
              _waveformHeights[i] = 4.0;
            }
          });
        }
      }
    });

    _initSpeechRecognizer();
  }

  // Safe Speech recognition initialization with permissions safeguards
  Future<void> _initSpeechRecognizer() async {
    try {
      bool available = await _speech.initialize(
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') {
            _handleSpeechComplete();
          }
        },
        onError: (val) {
          _handleSpeechComplete();
        },
      );
      if (mounted) {
        setState(() {
          _speechEnabled = available;
        });
      }
    } catch (_) {
      // Permission denied or platform unsupported - falls back cleanly to simulators
      if (mounted) {
        setState(() {
          _speechEnabled = false;
        });
      }
    }
  }

  // Click to toggle speech recording V3.5
  void _toggleSpeechListening() async {
    if (_isListeningState) {
      _stopSpeechListening();
    } else {
      _startSpeechListening();
    }
  }

  Future<void> _startSpeechListening() async {
    if (!_speechEnabled) {
      // If mic is not ready, select a random query template to simulate
      final random = Random();
      final q = _sampleQueries[random.nextInt(_sampleQueries.length)];
      _processDialogueQuery(q);
      return;
    }

    setState(() {
      _isListeningState = true;
      _assistantState = "LISTENING";
      _stateColor = CyberTheme.neonCyan;
      _liveTranscription = "Listening... Speak now...";
    });

    await _speech.listen(
      onResult: (result) {
        setState(() {
          _liveTranscription = result.recognizedWords;
        });
        if (result.finalResult && mounted) {
          _stopSpeechListening();
          _processDialogueQuery(result.recognizedWords);
        }
      },
    );
  }

  Future<void> _stopSpeechListening() async {
    if (_isListeningState) {
      await _speech.stop();
      if (mounted) {
        setState(() {
          _isListeningState = false;
        });
      }
    }
  }

  void _handleSpeechComplete() {
    if (_isListeningState && mounted) {
      setState(() {
        _isListeningState = false;
      });
    }
  }

  Future<void> _processDialogueQuery(String query) async {
    if (query.trim().isEmpty) return;

    // Stop ongoing speech before triggering a new command to prevent overlapping stutters
    await _flutterTts.stop();
    _isSpeaking = false;

    setState(() {
      _messages.add({"sender": "DRV", "text": query});
      _assistantState = "PROCESSING";
      _stateColor = CyberTheme.neonPink;
      _liveTranscription = "";
      for (int i = 0; i < _waveformHeights.length; i++) {
        _waveformHeights[i] = 4.0;
      }
    });
    _scrollToBottom();

    // Query NLP voice model (real Flask endpoint or high-fidelity simulated fallback)
    final result = await ApiService.queryVoiceCopilot(query);

    if (mounted) {
      final String replyText = result['response'] ?? "Telemetry parsed successfully.";
      
      setState(() {
        _assistantState = "RESPONDING";
        _stateColor = CyberTheme.neonPurple;
        _messages.add({"sender": "JARVIS", "text": replyText});
      });
      _scrollToBottom();

      // Answer verbally FIRST using native pre-loaded TTS
      if (!_isSpeaking) {
        _flutterTts.speak(replyText);
      }

      // Extract search details if action is map_search
      final location = result['action_data'] != null ? result['action_data']['location'] as String? : null;

      // Automatically redirect to GPS map screen after answering verbally FIRST (1.8s delay feels natural)
      if (result['action'] == 'map_search' && location != null) {
        Future.delayed(const Duration(milliseconds: 1800), () {
          if (mounted) {
            Navigator.push(
              context,
              PageRouteBuilder(
                pageBuilder: (context, animation, secondaryAnimation) => GpsMapScreen(initialSearch: location),
                transitionsBuilder: (context, animation, secondaryAnimation, child) {
                  return SlideTransition(
                    position: animation.drive(Tween(
                      begin: const Offset(1.0, 0.0),
                      end: Offset.zero,
                    ).chain(CurveTween(curve: Curves.easeInOutCubic))),
                    child: FadeTransition(
                      opacity: animation,
                      child: child,
                    ),
                  );
                },
                transitionDuration: const Duration(milliseconds: 650),
              ),
            );
          }
        });
      } else if (result['action'] == 'open_gps') {
        Future.delayed(const Duration(milliseconds: 1800), () {
          if (mounted) {
            Navigator.push(
              context,
              PageRouteBuilder(
                pageBuilder: (context, animation, secondaryAnimation) => const GpsMapScreen(),
                transitionsBuilder: (context, animation, secondaryAnimation, child) {
                  return SlideTransition(
                    position: animation.drive(Tween(
                      begin: const Offset(1.0, 0.0),
                      end: Offset.zero,
                    ).chain(CurveTween(curve: Curves.easeInOutCubic))),
                    child: FadeTransition(
                      opacity: animation,
                      child: child,
                    ),
                  );
                },
                transitionDuration: const Duration(milliseconds: 650),
              ),
            );
          }
        });
      }
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_chatScrollController.hasClients) {
        _chatScrollController.animateTo(
          _chatScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _flutterTts.stop();
    _waveformController.dispose();
    _manualInputController.dispose();
    _chatScrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: CyberTheme.darkBackground,
      appBar: AppBar(
        title: const Text(
          "[ ROADGUARD VOICE CO-PILOT ]",
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 14,
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
                  // 1. DYNAMIC SYSTEM STATE INDICATOR
                  _buildStateIndicatorHeader(),
                  const SizedBox(height: 20),

                  // 2. SCROLLABLE LINE-BY-LINE CONVERSATION DIALOGUE CARD V3.5
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: CyberTheme.cardBackground.withOpacity(0.55),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: _stateColor.withOpacity(0.35),
                          width: 1.5,
                        ),
                        boxShadow: CyberTheme.neonGlow(_stateColor, intensity: 0.05),
                      ),
                      child: Column(
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                "// CO-PILOT STREAM MONITOR //",
                                style: TextStyle(
                                  fontFamily: 'Courier',
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.bold,
                                  color: CyberTheme.textSecondary,
                                  letterSpacing: 1.2,
                                ),
                              ),
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: _stateColor,
                                  shape: BoxShape.circle,
                                  boxShadow: [
                                    BoxShadow(
                                      color: _stateColor.withOpacity(0.6),
                                      blurRadius: 4,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const Divider(color: Color(0xFF1E293B), height: 20),
                          
                          // Dialogue List
                          Expanded(
                            child: ListView.builder(
                              controller: _chatScrollController,
                              itemCount: _messages.length,
                              physics: const BouncingScrollPhysics(),
                              itemBuilder: (context, index) {
                                final msg = _messages[index];
                                final isUser = msg['sender'] == 'DRV';
                                final color = isUser ? CyberTheme.neonCyan : CyberTheme.neonPurple;

                                return TweenAnimationBuilder<double>(
                                  key: ValueKey(msg['text'] ?? index.toString()),
                                  tween: Tween<double>(begin: 0.0, end: 1.0),
                                  duration: const Duration(milliseconds: 400),
                                  curve: Curves.easeOutCubic,
                                  builder: (context, animValue, child) {
                                    return Transform.translate(
                                      offset: Offset(0, 15 * (1.0 - animValue)),
                                      child: Opacity(
                                        opacity: animValue,
                                        child: child,
                                      ),
                                    );
                                  },
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(vertical: 10.0),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          "${msg['sender']} >>",
                                          style: TextStyle(
                                            fontFamily: 'Courier',
                                            fontSize: 11,
                                            fontWeight: FontWeight.w900,
                                            color: color,
                                            letterSpacing: 1.5,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                                          decoration: BoxDecoration(
                                            color: Colors.black.withOpacity(0.2),
                                            borderRadius: BorderRadius.circular(8),
                                            border: Border.all(
                                              color: color.withOpacity(0.15),
                                            ),
                                          ),
                                          child: Text(
                                            msg['text'] ?? "",
                                            style: TextStyle(
                                              fontSize: 13.5,
                                              fontWeight: FontWeight.w500,
                                              color: Colors.white.withOpacity(0.95),
                                              height: 1.45,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),

                          // Live voice transcription HUD overlay
                          if (_liveTranscription.isNotEmpty)
                            Container(
                              padding: const EdgeInsets.all(8),
                              margin: const EdgeInsets.only(top: 8),
                              width: double.infinity,
                              decoration: BoxDecoration(
                                color: CyberTheme.neonCyan.withOpacity(0.08),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: CyberTheme.neonCyan.withOpacity(0.3),
                                ),
                              ),
                              child: Text(
                                _liveTranscription,
                                style: const TextStyle(
                                  fontFamily: 'Courier',
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: CyberTheme.neonCyan,
                                ),
                              ),
                            ),

                          const SizedBox(height: 8),
                          
                          // Glowing wave visualizer
                          _buildAudioWaveform(),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // 3. MANUAL CYBER COMMAND INPUT
                  _buildManualCommandField(),
                  const SizedBox(height: 20),

                  // 4. MICROPHONE BUTTON HUD V3.5 (Concentric HUD Ticks overlay)
                  _buildMicrophoneHUD(),
                  const SizedBox(height: 20),

                  // 5. SUGGESTED CHIPS TEMPLATES
                  _buildSuggestionsPane(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStateIndicatorHeader() {
    return Center(
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: _stateColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                "AGENT STATE: $_assistantState",
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 2,
                  color: _stateColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            _speechEnabled ? "HARDWARE MICROPHONE ACTIVE // AGENT STABLE" : "TACTICAL AUDIO EMULATOR ACTIVE",
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 9.5,
              fontWeight: FontWeight.bold,
              color: CyberTheme.textSecondary,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAudioWaveform() {
    return Container(
      height: 35,
      margin: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(_waveformHeights.length, (index) {
          final height = _waveformHeights[index];
          return AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            width: 3.2,
            height: height,
            margin: const EdgeInsets.symmetric(horizontal: 1.5),
            decoration: BoxDecoration(
              color: _stateColor.withOpacity(0.8),
              borderRadius: BorderRadius.circular(2),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildManualCommandField() {
    return Container(
      decoration: BoxDecoration(
        color: CyberTheme.cardBackground.withOpacity(0.6),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: CyberTheme.neonCyan.withOpacity(0.3),
        ),
      ),
      child: TextField(
        controller: _manualInputController,
        style: const TextStyle(fontSize: 13.5, color: Colors.white),
        decoration: InputDecoration(
          hintText: "Transmit manual query to co-pilot...",
          hintStyle: const TextStyle(color: CyberTheme.textMuted, fontSize: 13),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          suffixIcon: IconButton(
            icon: const Icon(Icons.send, color: CyberTheme.neonCyan),
            onPressed: () {
              final query = _manualInputController.text.trim();
              if (query.isNotEmpty) {
                _manualInputController.clear();
                _processDialogueQuery(query);
              }
            },
          ),
        ),
        onSubmitted: (text) {
          final query = text.trim();
          if (query.isNotEmpty) {
            _manualInputController.clear();
            _processDialogueQuery(query);
          }
        },
      ),
    );
  }

  Widget _buildMicrophoneHUD() {
    final bool activePulse = _assistantState == "LISTENING";
    final bool isSpeaking = _assistantState == "RESPONDING";
    final double pulse = _waveformController.value;

    return Center(
      child: GestureDetector(
        onTap: _toggleSpeechListening,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Outer rotating tactical ring
            AnimatedBuilder(
              animation: _waveformController,
              builder: (context, child) {
                final double angle = pulse * 2 * pi;
                return Transform.rotate(
                  angle: angle,
                  child: Container(
                    width: 105,
                    height: 105,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: _stateColor.withOpacity(activePulse ? 0.45 : 0.15),
                        width: 1.5,
                      ),
                    ),
                    child: CustomPaint(
                      painter: RingTicksPainter(_stateColor.withOpacity(activePulse ? 0.75 : 0.25)),
                    ),
                  ),
                );
              },
            ),
            
            // Inner pulsing ring
            AnimatedBuilder(
              animation: _waveformController,
              builder: (context, child) {
                final double sizeVal = activePulse || isSpeaking 
                  ? 82 + 10 * sin(pulse * 2 * pi).abs()
                  : 82.0;
                return Container(
                  width: sizeVal,
                  height: sizeVal,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: _stateColor.withOpacity(activePulse || isSpeaking ? 0.6 : 0.25),
                      width: 2.0,
                    ),
                    boxShadow: activePulse || isSpeaking
                      ? CyberTheme.neonGlow(_stateColor, intensity: 0.15, radius: 12)
                      : null,
                  ),
                );
              },
            ),

            // Main central button
            AnimatedBuilder(
              animation: _waveformController,
              builder: (context, child) {
                final double pulseVal = isSpeaking ? (0.6 + 0.4 * sin(pulse * 2 * pi).abs()) : 1.0;
                return AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: CyberTheme.cardBackground.withOpacity(0.9),
                    border: Border.all(
                      color: _stateColor.withOpacity(activePulse ? 0.95 : (isSpeaking ? 0.8 : 0.4)),
                      width: 2.5,
                    ),
                    boxShadow: CyberTheme.neonGlow(
                      _stateColor,
                      intensity: activePulse ? 0.35 : (isSpeaking ? (0.12 + 0.2 * pulseVal) : 0.08),
                      radius: activePulse ? 16 : (isSpeaking ? (8 + 10 * pulseVal) : 6),
                    ),
                  ),
                  child: Icon(
                    activePulse ? Icons.mic_off : Icons.mic,
                    color: _stateColor,
                    size: 30,
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionsPane() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          "// SUGGESTED QUICK TRANSMISSIONS //",
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 9.5,
            fontWeight: FontWeight.bold,
            color: CyberTheme.textMuted,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 38,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: _sampleQueries.length,
            physics: const BouncingScrollPhysics(),
            itemBuilder: (context, index) {
              final query = _sampleQueries[index];
              return Padding(
                padding: const EdgeInsets.only(right: 10.0),
                child: ActionChip(
                  label: Text(
                    query,
                    style: const TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 10.5,
                      fontWeight: FontWeight.bold,
                      color: CyberTheme.neonCyan,
                    ),
                  ),
                  backgroundColor: CyberTheme.cardBackground.withOpacity(0.5),
                  side: BorderSide(
                    color: CyberTheme.neonCyan.withOpacity(0.2),
                  ),
                  onPressed: () {
                    _processDialogueQuery(query);
                  },
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

// Tick marks painter for sci-fi rotating ring
class RingTicksPainter extends CustomPainter {
  final Color color;
  RingTicksPainter(this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke;

    final double cx = size.width / 2;
    final double cy = size.height / 2;
    final double radius = size.width / 2;

    // Draw small tick lines around the circle
    for (int i = 0; i < 8; i++) {
      final double angle = (i * pi / 4);
      final double startX = cx + (radius - 5) * cos(angle);
      final double startY = cy + (radius - 5) * sin(angle);
      final double endX = cx + radius * cos(angle);
      final double endY = cy + radius * sin(angle);
      canvas.drawLine(Offset(startX, startY), Offset(endX, endY), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
