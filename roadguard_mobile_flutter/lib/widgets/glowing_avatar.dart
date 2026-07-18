import 'package:flutter/material.dart';
import '../theme/cyber_theme.dart';

class GlowingAvatar extends StatefulWidget {
  final IconData icon;
  final Color glowColor;

  const GlowingAvatar({
    Key? key,
    required this.icon,
    this.glowColor = CyberTheme.neonCyan,
  }) : super(key: key);

  @override
  State<GlowingAvatar> createState() => _GlowingAvatarState();
}

class _GlowingAvatarState extends State<GlowingAvatar>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _pulse = Tween<double>(begin: 0.3, end: 1.0).animate(_controller);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (context, child) {
        return Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(
              color: widget.glowColor.withOpacity(_pulse.value),
              width: 1.5,
            ),
            boxShadow: [
              BoxShadow(
                color: widget.glowColor.withOpacity(0.15 * _pulse.value),
                blurRadius: 8,
                spreadRadius: 2,
              ),
            ],
          ),
          child: CircleAvatar(
            radius: 20,
            backgroundColor: CyberTheme.cardBackground,
            child: Icon(
              widget.icon,
              color: widget.glowColor,
              size: 20,
            ),
          ),
        );
      },
    );
  }
}
