import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../services/project_service.dart';

class PromptScreen extends StatelessWidget {
  const PromptScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              FilledButton(onPressed: session.busy ? null : session.buildPrompt, child: const Text('Compile prompt')),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: session.prompt.isEmpty
                    ? null
                    : () async {
                        await Clipboard.setData(ClipboardData(text: session.prompt));
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Prompt copied')));
                        }
                      },
                child: const Text('Copy'),
              ),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: SelectableText(session.prompt.isEmpty ? 'The prompt is compiled from the specification, not the raw chat.' : session.prompt),
          ),
        ),
      ],
    );
  }
}
