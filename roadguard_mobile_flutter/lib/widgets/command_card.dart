import 'package:flutter/material.dart';
import '../theme/cyber_theme.dart';

class CommandCard extends StatefulWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color neonColor;
  final VoidCallback onTap;

  const CommandCard({
    Key? key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.neonColor,
    required this.onTap,
  }) : super(key: key);

  @override
  State<CommandCard> createState() => _CommandCardState();
}

class _CommandCardState extends State<CommandCard> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) => setState(() => _isPressed = false),
      onTapCancel: () => setState(() => _isPressed = false),
      onTap: widget.onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOut,
        transform: _isPressed ? (Matrix4.identity()..scale(0.96)) : Matrix4.identity(),
        decoration: BoxDecoration(
          color: CyberTheme.cardBackground.withOpacity(0.6),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _isPressed ? widget.neonColor : widget.neonColor.withOpacity(0.35),
            width: 1.5,
          ),
          boxShadow: [
            BoxShadow(
              color: widget.neonColor.withOpacity(_isPressed ? 0.16 : 0.04),
              blurRadius: _isPressed ? 12 : 6,
              spreadRadius: 0,
            ),
          ],
        ),
        padding: const EdgeInsets.all(14.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Icon(
                  widget.icon,
                  color: widget.neonColor,
                  size: 26,
                ),
                Container(
                  width: 5,
                  height: 5,
                  decoration: BoxDecoration(
                    color: widget.neonColor,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: widget.neonColor.withOpacity(0.6),
                        blurRadius: 3,
                        spreadRadius: 0.5,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.8,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  widget.subtitle.toUpperCase(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 9.5,
                    fontWeight: FontWeight.bold,
                    color: widget.neonColor.withOpacity(0.75),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
