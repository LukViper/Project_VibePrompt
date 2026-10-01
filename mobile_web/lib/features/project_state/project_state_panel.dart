import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../models/project.dart';
import '../../services/project_service.dart';

class ProjectStatePanel extends StatelessWidget {
  const ProjectStatePanel({super.key, required this.state, this.dense = false});

  final Map<String, dynamic>? state;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final project = state?['project'] as Map? ?? {};
    final academic = state?['academic'] as Map? ?? {};
    final constraints = state?['constraints'] as Map? ?? {};
    final technology = state?['technology'] as Map? ?? {};
    final core = state?['core_idea'] as Map?;
    final requirements = ProjectModels.requirements(state);
    final decisions = ProjectModels.decisions(state);
    final conflicts = ProjectModels.conflicts(state);
    final integrity = state?['integrity'] as Map? ?? {};
    final claims = (state?['claims'] as List?)?.cast<Map>() ?? [];
    final evidence = (state?['evidence'] as List?)?.cast<Map>() ?? [];
    final attacks = (state?['grill_attacks'] as List?)?.cast<Map>() ?? [];
    final traceLinks = (state?['trace_links'] as List?)?.cast<Map>() ?? [];
    final lineage = session.selectedLineage;
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        const Text('PROJECT INTEGRITY', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 0.6)),
        const SizedBox(height: 6),
        _integrityRow('Requirements', integrity['requirements']),
        _integrityRow('Decisions', integrity['decisions']),
        _integrityRow('Assumptions', integrity['assumptions']),
        _integrityRow('Evidence', integrity['evidence']),
        _integrityRow('Grill', integrity['grill']),
        _integrityRow('Traceability', integrity['traceability']),
        _integrityRow('Verification', integrity['verification']),
        _integrityRow('Compilation', integrity['compilation']),
        Text('Trace links: ${traceLinks.length}', style: const TextStyle(fontSize: 12)),
        const SizedBox(height: 14),
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
            title: Text(
              '${req['id']} · ${req['assertion_status'] ?? req['status']} · ${req['assertion_origin'] ?? ''}',
              style: const TextStyle(fontSize: 13),
            ),
            subtitle: Text(req['text']?.toString() ?? ''),
            trailing: IconButton(
              tooltip: 'Lineage',
              icon: const Icon(Icons.account_tree_outlined, size: 18),
              onPressed: session.busy
                  ? null
                  : () => session.loadRequirementLineage(req['id']?.toString() ?? ''),
            ),
          ),
        if (lineage != null) ...[
          const SizedBox(height: 8),
          Text(
            'Lineage: ${lineage['requirement_id']}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          for (final chain in ((lineage['chains'] as List?) ?? const []).take(6))
            Padding(
              padding: const EdgeInsets.only(left: 8, bottom: 4),
              child: Text(
                _formatChain(chain),
                style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
              ),
            ),
          if (((lineage['chains'] as List?) ?? const []).isEmpty)
            const Text('No trace chains yet for this requirement.', style: TextStyle(fontSize: 12)),
        ],
        if (claims.isNotEmpty) ...[
          const Text('Claims', style: TextStyle(fontWeight: FontWeight.w700)),
          for (final c in claims.take(6)) Text('• ${c['id']}: ${c['text']}', style: const TextStyle(fontSize: 12)),
        ],
        if (evidence.isNotEmpty) ...[
          const Text('Evidence', style: TextStyle(fontWeight: FontWeight.w700)),
          for (final e in evidence.take(8))
            Text(
              '• ${e['id']} · ${e['verification_status']} · ${e['claim'] ?? e['title']}',
              style: const TextStyle(fontSize: 12),
            ),
          const Text(
            'Note: UNVERIFIED ≠ VERIFIED',
            style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic),
          ),
        ],
        if (attacks.isNotEmpty) ...[
          const Text('Grill attacks', style: TextStyle(fontWeight: FontWeight.w700)),
          for (final a in attacks.take(6))
            Text('• ${a['id']} → ${a['target_id']}: ${a['challenge']}', style: const TextStyle(fontSize: 12)),
        ],
        const Text('Decisions', style: TextStyle(fontWeight: FontWeight.w700)),
        for (final item in _uniqueDecisions(decisions)) Text('• ${item['summary']}'),
        const SizedBox(height: 8),
        const Text('Conflicts', style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.rust)),
        if (conflicts.isEmpty) const Text('None open.'),
        for (final item in conflicts) Text(item['explanation']?.toString() ?? ''),
      ],
    );
  }

  String _formatChain(dynamic chain) {
    if (chain is! List) return chain.toString();
    return chain
        .whereType<Map>()
        .map((step) => '${step['entity_type']}:${step['entity_id']}')
        .join(' → ');
  }

  Widget _integrityRow(String label, dynamic section) {
    if (section is! Map) {
      return Text('$label: —', style: const TextStyle(fontSize: 12));
    }
    final parts = section.entries.map((e) => '${e.key}: ${e.value}').join(' · ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text('$label — $parts', style: const TextStyle(fontSize: 12)),
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
