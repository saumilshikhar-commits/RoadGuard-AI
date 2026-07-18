import 'package:flutter_test/flutter_test.dart';
import 'package:roadguard_mobile/main.dart';

void main() {
  testWidgets('RoadGuard Mobile Command UI Boot Test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const RoadGuardMobileApp());

    // Verify that the futuristic logo heading renders correctly
    expect(find.text('ROADGUARD AI'), findsOneWidget);
  });
}
