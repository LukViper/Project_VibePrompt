import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../services/project_service.dart';

class IdeasScreen extends StatelessWidget {
  const IdeasScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const Expanded(child: Text('Candidate ideas are deduplicated against the project state.')),
            FilledButton(onPressed: session.busy ? null : session.loadIdeas, child: const Text('Generate')),
          ],
        ),
        const SizedBox(height: 12),
        for (var index = 0; index < session.ideas.length; index++)
          Card(
            color: AppTheme.card,
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Idea ${index + 1} — ${session.ideas[index].title}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text(session.ideas[index].problem),
                  const SizedBox(height: 6),
                  Text('Objective: ${session.ideas[index].objective}'),
                  Text('Difficulty: ${session.ideas[index].difficulty} · Scope: ${session.ideas[index].estimatedScope}'),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      FilledButton(
                        onPressed: session.busy ? null : () => session.selectIdea(session.ideas[index]),
                        child: Text(session.ideas[index].selected ? 'Selected' : 'Select'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: session.busy ? null : () => session.reject(session.ideas[index]),
                        child: const Text('Reject'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
