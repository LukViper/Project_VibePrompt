import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../services/project_service.dart';
import '../../widgets/app_shell.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _controller = TextEditingController(
    text: 'I have to build a project for NLP. I am working alone and have six weeks.',
  );
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _showAccount = false;

  @override
  void dispose() {
    _controller.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _enter(SessionController session) async {
    await session.start(_controller.text);
    if (!mounted || session.projectId == null) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const AppShell()));
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: SingleChildScrollView(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'VibePrompt',
                    style: Theme.of(context).textTheme.displaySmall?.copyWith(
                          color: AppTheme.ink,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Continue as guest for a temporary workspace, or sign in to keep projects permanently.',
                  ),
                  const SizedBox(height: 20),
                  TextField(
                    controller: _controller,
                    minLines: 5,
                    maxLines: 8,
                    decoration: const InputDecoration(
                      filled: true,
                      fillColor: Colors.white,
                      border: OutlineInputBorder(),
                      hintText: 'I need a project for NLP...',
                    ),
                  ),
                  if (session.error != null) ...[
                    const SizedBox(height: 12),
                    Text(session.error!, style: const TextStyle(color: AppTheme.rust)),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: session.busy
                        ? null
                        : () async {
                            await session.continueAsGuest();
                            if (!context.mounted || session.error != null) return;
                            await _enter(session);
                          },
                    child: Text(session.busy ? 'Starting...' : 'Continue as Guest'),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: session.busy ? null : () => setState(() => _showAccount = !_showAccount),
                    child: Text(_showAccount ? 'Hide account options' : 'Login / Create Account'),
                  ),
                  if (_showAccount) ...[
                    const SizedBox(height: 8),
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        labelText: 'Email',
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _password,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Password (min 8)',
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        FilledButton(
                          onPressed: session.busy
                              ? null
                              : () async {
                                  await session.login(_email.text.trim(), _password.text);
                                  if (!context.mounted || session.error != null) return;
                                  await _enter(session);
                                },
                          child: const Text('Login'),
                        ),
                        const SizedBox(width: 12),
                        OutlinedButton(
                          onPressed: session.busy
                              ? null
                              : () async {
                                  await session.register(_email.text.trim(), _password.text);
                                  if (!context.mounted || session.error != null) return;
                                  await _enter(session);
                                },
                          child: const Text('Create Account'),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
