import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/message.dart';
import '../core/theme/app_theme.dart';
import '../services/project_service.dart';

class MessageBubble extends StatelessWidget {
  const MessageBubble({super.key, required this.message, this.showIdeaActions = false});

  final ChatMessage message;
  final bool showIdeaActions;

  @override
  Widget build(BuildContext context) {
    final mine = message.role == 'user';
    final session = context.watch<SessionController>();
    final locked = (session.state?['core_idea'] as Map?)?['locked'] == true;
    final bodyStyle = TextStyle(color: mine ? AppTheme.paper : AppTheme.ink);
    final labelStyle = TextStyle(
      color: mine ? AppTheme.copper : AppTheme.pine,
      fontWeight: FontWeight.w700,
      fontSize: 12,
    );

    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 720),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: mine ? AppTheme.ink : Colors.white,
          borderRadius: BorderRadius.circular(8),
        ),
        // Same selectable path for user AND assistant — native long-press /
        // drag + Ctrl/Cmd+C. No copy button; no custom painting.
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SelectableText(mine ? 'You' : 'VibePrompt', style: labelStyle),
            const SizedBox(height: 4),
            SelectableText(message.content, style: bodyStyle),
            if (!mine && showIdeaActions && message.hasIdeas && !locked) ...[
              const SizedBox(height: 12),
              SelectableText(
                'Choose one, ask for more, or type your own domain/idea in the chat.',
                style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.7), fontSize: 12),
              ),
              const SizedBox(height: 8),
              for (final idea in message.ideas)
                _IdeaChoiceCard(
                  idea: idea,
                  busy: session.busy,
                  onSelect: () => session.selectIdeaCard(idea),
                ),
              const SizedBox(height: 4),
              SelectionContainer.disabled(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: session.busy ? null : () => session.requestMoreIdeas(),
                      icon: const Icon(Icons.refresh, size: 16),
                      label: const Text('More ideas'),
                    ),
                    TextButton(
                      onPressed: session.busy
                          ? null
                          : () => session.send('I have my own idea / domain to work on.'),
                      child: const Text('I have my own idea'),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _IdeaChoiceCard extends StatelessWidget {
  const _IdeaChoiceCard({required this.idea, required this.onSelect, required this.busy});

  final ProjectIdeaCard idea;
  final VoidCallback onSelect;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.copper.withValues(alpha: 0.45)),
        borderRadius: BorderRadius.circular(8),
        color: AppTheme.paper,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SelectableText(
            '${idea.index}. ${idea.title}',
            style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
          ),
          if (idea.problem.isNotEmpty) ...[
            const SizedBox(height: 4),
            SelectableText(idea.problem, style: const TextStyle(fontSize: 13)),
          ],
          if (idea.objective.isNotEmpty) ...[
            const SizedBox(height: 4),
            SelectableText('Objective: ${idea.objective}', style: const TextStyle(fontSize: 13)),
          ],
          const SizedBox(height: 4),
          SelectableText(
            'Difficulty: ${idea.difficulty} · Scope: ${idea.estimatedScope}',
            style: TextStyle(fontSize: 12, color: AppTheme.ink.withValues(alpha: 0.65)),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: SelectionContainer.disabled(
              child: FilledButton(
                onPressed: busy ? null : onSelect,
                style: FilledButton.styleFrom(backgroundColor: AppTheme.pine),
                child: const Text('Select'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
