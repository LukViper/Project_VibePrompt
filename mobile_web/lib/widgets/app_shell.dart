import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/theme/app_theme.dart';
import '../features/chat/chat_screen.dart';
import '../features/project_state/project_state_panel.dart';
import '../services/project_service.dart';

/// Professional tab-based workspace.
class AppShell extends StatelessWidget {
  const AppShell({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('VibePrompt'),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.chat_bubble_outline), text: 'Conversation'),
              Tab(icon: Icon(Icons.account_tree_outlined), text: 'Architecture & State'),
              Tab(icon: Icon(Icons.description_outlined), text: 'Agent Prompt'),
            ],
            indicatorColor: AppTheme.copper,
            labelColor: AppTheme.copper,
            unselectedLabelColor: AppTheme.pine,
          ),
        ),
        body: _WorkspaceContent(),
      ),
    );
  }
}

class _WorkspaceContent extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final wide = MediaQuery.sizeOf(context).width >= 960;

    return Column(
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
          child: TabBarView(
            children: [
              // Tab 1: Conversation
              Column(
                children: [
                  const Expanded(child: ChatScreen()),
                  _CapabilityBar(session: session),
                ],
              ),
              
              // Tab 2: Architecture & State
              wide
                  ? Row(
                      children: [
                        SizedBox(
                          width: 250,
                          child: ColoredBox(
                            color: AppTheme.ink,
                            child: DefaultTextStyle(
                              style: const TextStyle(color: AppTheme.paper),
                              child: _ProjectColumn(state: session.state, stage: session.stage),
                            ),
                          ),
                        ),
                        const VerticalDivider(width: 1),
                        Expanded(child: ProjectStatePanel(state: session.state)),
                        const VerticalDivider(width: 1),
                        SizedBox(
                          width: 350,
                          child: _SideInsight(session: session),
                        ),
                      ],
                    )
                  : Column(
                      children: [
                        _SideInsight(session: session),
                        Expanded(child: ProjectStatePanel(state: session.state)),
                      ],
                    ),
                    
              // Tab 3: Agent Prompt
              _PromptPane(session: session),
            ],
          ),
        ),
      ],
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
            Text('Workspace', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800, color: AppTheme.ink)),
            const SizedBox(width: 12),
            Chip(label: Text(stage), visualDensity: VisualDensity.compact, backgroundColor: AppTheme.copper.withOpacity(0.2)),
            if (guest) ...[
              const SizedBox(width: 8),
              const Chip(label: Text('Guest'), visualDensity: VisualDensity.compact),
            ],
            const Spacer(),
            Flexible(
              child: Text(
                title?.isNotEmpty == true ? title! : 'Untitled project',
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppTheme.ink, fontWeight: FontWeight.bold),
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
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
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
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Grill completed. Check state.')));
                }
              }),
              _cap(context, 'Architecture', Icons.schema_outlined, () {
                session.send('Propose an architecture and tech stack');
              }),
              _cap(context, 'Compile Prompt', Icons.build_circle_outlined, () async {
                await session.buildPrompt();
                if (context.mounted) {
                   ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Prompt compiled! Check the Agent Prompt tab.')));
                }
              }, isPrimary: true),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cap(BuildContext context, String label, IconData icon, VoidCallback onTap, {bool isPrimary = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: isPrimary 
        ? FilledButton.icon(
            onPressed: session.busy ? null : onTap,
            style: FilledButton.styleFrom(backgroundColor: AppTheme.copper),
            icon: Icon(icon, size: 18),
            label: Text(label),
          )
        : TextButton.icon(
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
    final proposed = session.proposedDecisions;
    if (proposed.isEmpty) {
       return const Center(child: Text("No pending decisions.", style: TextStyle(color: Colors.grey)));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: ColoredBox(
            color: Colors.white,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text('Pending Decisions', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
                const SizedBox(height: 8),
                Text(
                  'PROPOSED items need your approval before they become ACTIVE.',
                  style: TextStyle(fontSize: 13, color: AppTheme.ink.withOpacity(0.7)),
                ),
                const SizedBox(height: 16),
                for (final item in proposed)
                  Card(
                    elevation: 2,
                    margin: const EdgeInsets.only(bottom: 12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(item['summary']?.toString() ?? '', style: const TextStyle(fontSize: 14)),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Expanded(
                                child: FilledButton(
                                  onPressed: session.busy ? null : () => session.approveProposedDecision(item['id'].toString()),
                                  style: FilledButton.styleFrom(backgroundColor: AppTheme.pine),
                                  child: const Text('Accept'),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: OutlinedButton(
                                  onPressed: session.busy ? null : () => session.rejectProposedDecision(item['id'].toString()),
                                  child: const Text('Reject'),
                                ),
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
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('PROJECT', style: TextStyle(letterSpacing: 1.2, fontWeight: FontWeight.w900, fontSize: 16)),
          const SizedBox(height: 8),
          Text(stage ?? 'DISCOVERY', style: const TextStyle(color: AppTheme.copper, fontWeight: FontWeight.bold)),
          const Divider(color: Colors.white24, height: 32),
          const Text('Core Idea', style: TextStyle(color: AppTheme.copper, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(core?['primary_objective']?.toString() ?? project['objective']?.toString() ?? 'Not locked', style: const TextStyle(height: 1.4)),
          const Divider(color: Colors.white24, height: 32),
          const Text('Constraints', style: TextStyle(color: AppTheme.copper, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text('Team: ${constraints['team_size'] ?? '-'}'),
          Text('Duration: ${constraints['duration']?.toString() ?? '-'}'),
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
    if (session.prompt.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.description_outlined, size: 64, color: AppTheme.copper.withOpacity(0.5)),
            const SizedBox(height: 16),
            const Text("No prompt compiled yet.", style: TextStyle(fontSize: 18, color: AppTheme.pine)),
            const SizedBox(height: 8),
            const Text("Use the 'Compile Prompt' action to generate it.", style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    final validation = session.promptValidation;

    return Column(
      children: [
        Container(
          color: AppTheme.ink,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              if (validation != null)
                Text(
                  'Quality Score: ${(validation['metrics'] as Map?)?['requirement_coverage'] ?? '-'}',
                  style: const TextStyle(color: AppTheme.copper, fontWeight: FontWeight.bold),
                ),
              const Spacer(),
              FilledButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: session.prompt));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Prompt copied to clipboard!')));
                  }
                },
                icon: const Icon(Icons.copy, size: 18),
                label: const Text('Copy Prompt'),
                style: FilledButton.styleFrom(backgroundColor: AppTheme.pine),
              ),
            ],
          ),
        ),
        Expanded(
          child: Container(
            color: Colors.white,
            width: double.infinity,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: SelectableText(
                session.prompt,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 13, height: 1.5, color: Colors.black87),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
