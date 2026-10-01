import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/api/api_client.dart';
import 'core/config/app_config.dart';
import 'core/theme/app_theme.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'services/project_service.dart';

void main() {
  runApp(const VibePromptApp());
}

class VibePromptApp extends StatelessWidget {
  const VibePromptApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => SessionController(ApiClient(AppConfig.baseUrl)),
      child: MaterialApp(
        title: 'VibePrompt',
        theme: AppTheme.light(),
        home: const OnboardingScreen(),
      ),
    );
  }
}
