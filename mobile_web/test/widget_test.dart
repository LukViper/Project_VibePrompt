import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:vibeprompt/core/api/api_client.dart';
import 'package:vibeprompt/features/onboarding/onboarding_screen.dart';
import 'package:vibeprompt/services/project_service.dart';

void main() {
  testWidgets('onboarding asks for a natural-language project description', (tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => SessionController(ApiClient('http://localhost:8000')),
        child: const MaterialApp(home: OnboardingScreen()),
      ),
    );
    expect(find.text('VibePrompt'), findsOneWidget);
    expect(find.text('Start the conversation'), findsOneWidget);
  });
}
