import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../models/project.dart';

class ProjectStatePanel extends StatelessWidget {
  const ProjectStatePanel({super.key, required this.state, this.dense = false});

  final Map<String, dynamic>? state;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final project = state?['project'] as Map? ?? {};
    final academic = state?['academic'] as Map? ?? {};
    final constraints = state?['constraints'] as Map? ?? {};
    final technology = state?['technology'] as Map? ?? {};
    final core = state?['core_idea'] as Map?;
    final requirements = ProjectModels.requirements(state);
    final decisions = ProjectModels.decisions(state);
    final conflicts = ProjectModels.conflicts(state);
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        const Text('PROJECT STATE', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 0.6)),
        const SizedBox(height: 8),
        Text(project['title']?.toString().isNotEmpty == true ? project['title'].toString() : 'Untitled project'),
        if (core != null) Text('Core idea: ${core['primary_objective'] ?? ''}'),
        Text('Subject: ${academic['subject'] ?? 'not set'}'),
        Text('Team: ${constraints['team_size'] ?? 'not set'} · ${constraints['duration'] ?? 'duration not set'}'),
        Text('Model: ${technology['model'] ?? 'not set'} · Database: ${technology['database'] ?? 'not set'}'),
        const SizedBox(height: 14),
        const Text('Requirements', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final req in requirements)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('${req['id']} · ${req['status']}', style: const TextStyle(fontSize: 13)),
            subtitle: Text(req['text']?.toString() ?? ''),
          ),
        const Text('Decisions', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final item in _uniqueDecisions(decisions)) Text('• ${item['summary']}'),
        const SizedBox(height: 8),
        const Text('Conflicts', style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.rust)),
        if (conflicts.isEmpty) const Text('None open.'),
        for (final item in conflicts) Text(item['explanation']?.toString() ?? ''),
      ],
    );
  }

  List<Map<String, dynamic>> _uniqueDecisions(List<Map<String, dynamic>> decisions) {
    final seen = <String>{};
    final unique = <Map<String, dynamic>>[];
    for (final item in decisions.reversed) {
      final summary = item['summary']?.toString() ?? '';
      if (summary.isEmpty || !seen.add(summary)) continue;
      unique.add(item);
      if (unique.length >= 8) break;
    }
    return unique.reversed.toList();
  }
}

class StateScreen extends StatelessWidget {
  const StateScreen({
    super.key,
    required this.state,
    required this.onGrill,
    required this.onReview,
    required this.onSpecification,
  });

  final Map<String, dynamic>? state;
  final VoidCallback onGrill;
  final VoidCallback onReview;
  final VoidCallback onSpecification;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: Wrap(
            spacing: 8,
            children: [
              OutlinedButton(onPressed: onReview, child: const Text('Professional')),
              OutlinedButton(onPressed: onGrill, child: const Text('Grill')),
              OutlinedButton(onPressed: onSpecification, child: const Text('Specification')),
            ],
          ),
        ),
        Expanded(child: ProjectStatePanel(state: state)),
      ],
    );
  }
}
