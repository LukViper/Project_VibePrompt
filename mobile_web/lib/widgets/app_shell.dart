import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/theme/app_theme.dart';
import '../features/chat/chat_screen.dart';
import '../features/project_state/project_state_panel.dart';
import '../services/project_service.dart';

/// Chat-first workspace. Ideas / Grill / Spec / Prompt are capabilities, not mandatory tabs.
class AppShell extends StatelessWidget {
  const AppShell({super.key});

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 960;
    return wide ? const _DesktopWorkspace() : const _MobileWorkspace();
  }
}

class _DesktopWorkspace extends StatelessWidget {
  const _DesktopWorkspace();

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Scaffold(
      body: Column(
        children: [
          _ContextStrip(session: session),
          if (session.error != null)
            ColoredBox(
              color: AppTheme.rust,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Text(session.error!, style: const TextStyle(color: Colors.white)),
              ),
            ),
          Expanded(
            child: Row(
              children: [
                SizedBox(
                  width: 220,
                  child: ColoredBox(
                    color: AppTheme.ink,
                    child: DefaultTextStyle(
                      style: const TextStyle(color: AppTheme.paper),
                      child: _ProjectColumn(state: session.state, stage: session.stage),
                    ),
                  ),
                ),
                const VerticalDivider(width: 1),
                const Expanded(child: ChatScreen()),
                const VerticalDivider(width: 1),
                SizedBox(
                  width: 320,
                  child: _SideInsight(session: session),
                ),
              ],
            ),
          ),
          _CapabilityBar(session: session),
        ],
      ),
    );
  }
}

class _MobileWorkspace extends StatelessWidget {
  const _MobileWorkspace();

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('VibePrompt'),
        actions: [
          IconButton(
            tooltip: 'Project state',
            onPressed: () => _openSheet(context, 'State', ProjectStatePanel(state: session.state)),
            icon: const Icon(Icons.account_tree_outlined),
          ),
        ],
      ),
      body: Column(
        children: [
          _ContextStrip(session: session),
          if (session.error != null) Text(session.error!, style: const TextStyle(color: AppTheme.rust)),
          const Expanded(child: ChatScreen()),
          _CapabilityBar(session: session),
        ],
      ),
    );
  }
}

class _ContextStrip extends StatelessWidget {
  const _ContextStrip({required this.session});

  final SessionController session;

  @override
  Widget build(BuildContext context) {
    final stage = session.stage ?? 'DISCOVERY';
    final title = (session.state?['project'] as Map?)?['title']?.toString();
    final guest = session.isGuest;
    return Material(
      color: AppTheme.paper,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            Text('VibePrompt', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(width: 12),
            Chip(label: Text(stage), visualDensity: VisualDensity.compact),
            if (guest) ...[
              const SizedBox(width: 8),
              const Chip(label: Text('Guest'), visualDensity: VisualDensity.compact),
            ],
            const Spacer(),
            Flexible(
              child: Text(
                title?.isNotEmpty == true ? title! : 'Untitled project',
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppTheme.ink),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CapabilityBar extends StatelessWidget {
  const _CapabilityBar({required this.session});

  final SessionController session;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppTheme.ink,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _cap(context, 'Summary', Icons.summarize_outlined, () {
                session.loadSummary();
              }),
              _cap(context, 'Ideas', Icons.lightbulb_outline, () {
                session.requestIdeas();
              }),
              _cap(context, 'Research', Icons.science_outlined, () {
                session.send('Are there any existing systems or datasets for this project?');
              }),
              _cap(context, 'Grill', Icons.whatshot_outlined, () async {
                await session.runGrill();
                if (context.mounted) {
                  _openSheet(
                    context,
                    'Grill',
                    _TextBlock(text: session.grillReport?['narrative']?.toString() ?? session.grillReport.toString()),
                  );
                }
              }),
              _cap(context, 'Architecture', Icons.schema_outlined, () {
                session.send('Propose an architecture and tech stack');
              }),
              _cap(context, 'Compile prompt', Icons.description_outlined, () async {
                await session.buildPrompt();
                if (context.mounted) {
                  _openSheet(
                    context,
                    'Agent prompt',
                    _PromptPane(session: session),
                  );
                }
              }),
              _cap(context, 'State', Icons.account_tree_outlined, () {
                _openSheet(context, 'Project state', ProjectStatePanel(state: session.state));
              }),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cap(BuildContext context, String label, IconData icon, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: TextButton.icon(
        onPressed: session.busy ? null : onTap,
        style: TextButton.styleFrom(foregroundColor: AppTheme.paper),
        icon: Icon(icon, size: 18, color: AppTheme.copper),
        label: Text(label),
      ),
    );
  }
}

class _SideInsight extends StatelessWidget {
  const _SideInsight({required this.session});

  final SessionController session;

  @override
  Widget build(BuildContext context) {
    final promptPreview = session.prompt;
    final validation = session.promptValidation;
    final proposed = session.proposedDecisions;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (proposed.isNotEmpty)
          SizedBox(
            height: 220,
            child: ColoredBox(
              color: Colors.white,
              child: ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  const Text('Your decision', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(
                    'PROPOSED items need your approval before they become ACTIVE.',
                    style: TextStyle(fontSize: 12, color: AppTheme.ink.withValues(alpha: 0.7)),
                  ),
                  const SizedBox(height: 8),
                  for (final item in proposed.take(6))
                    Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(item['summary']?.toString() ?? '', style: const TextStyle(fontSize: 13)),
                            const SizedBox(height: 6),
                            Row(
                              children: [
                                FilledButton(
                                  onPressed: session.busy
                                      ? null
                                      : () => session.approveProposedDecision(item['id'].toString()),
                                  style: FilledButton.styleFrom(backgroundColor: AppTheme.pine),
                                  child: const Text('Accept'),
                                ),
                                const SizedBox(width: 8),
                                OutlinedButton(
                                  onPressed: session.busy
                                      ? null
                                      : () => session.rejectProposedDecision(item['id'].toString()),
                                  child: const Text('Reject'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        Expanded(child: ProjectStatePanel(state: session.state)),
        if (promptPreview.isNotEmpty)
          SizedBox(
            height: 180,
            child: ColoredBox(
              color: Colors.white,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Prompt preview', style: TextStyle(fontWeight: FontWeight.w700)),
                    if (validation != null)
                      Text(
                        'Coverage ${(validation['metrics'] as Map?)?['requirement_coverage'] ?? '-'}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.pine),
                      ),
                    const SizedBox(height: 6),
                    Expanded(
                      child: SingleChildScrollView(
                        child: Text(promptPreview, maxLines: 12, overflow: TextOverflow.ellipsis),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ProjectColumn extends StatelessWidget {
  const _ProjectColumn({required this.state, this.stage});

  final Map<String, dynamic>? state;
  final String? stage;

  @override
  Widget build(BuildContext context) {
    final project = state?['project'] as Map? ?? {};
    final core = state?['core_idea'] as Map?;
    final constraints = state?['constraints'] as Map? ?? {};
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('PROJECT', style: TextStyle(letterSpacing: 1.1, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Text(stage ?? 'DISCOVERY', style: const TextStyle(color: AppTheme.copper)),
          const SizedBox(height: 16),
          const Text('Core Idea', style: TextStyle(color: AppTheme.copper, fontWeight: FontWeight.w700)),
          Text(core?['primary_objective']?.toString() ?? project['objective']?.toString() ?? 'Not locked'),
          const SizedBox(height: 16),
          const Text('Constraints', style: TextStyle(color: AppTheme.copper, fontWeight: FontWeight.w700)),
          Text('Team ${constraints['team_size'] ?? '-'}'),
          Text(constraints['duration']?.toString() ?? 'Duration not set'),
        ],
      ),
    );
  }
}

class _PromptPane extends StatelessWidget {
  const _PromptPane({required this.session});

  final SessionController session;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
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
            child: SelectableText(session.prompt),
          ),
        ),
      ],
    );
  }
}

class _TextBlock extends StatelessWidget {
  const _TextBlock({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(padding: const EdgeInsets.all(16), child: SelectableText(text));
  }
}

void _openSheet(BuildContext context, String title, Widget child) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (context) {
      return SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.75,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(title, style: Theme.of(context).textTheme.titleLarge),
            ),
            const Divider(height: 1),
            Expanded(child: child),
          ],
        ),
      );
    },
  );
}
