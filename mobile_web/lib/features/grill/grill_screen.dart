import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/project_service.dart';

class GrillScreen extends StatelessWidget {
  const GrillScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final report = session.grillReport;
    final questions = report?['questions'];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const Expanded(child: Text('Grill Mode looks for weaknesses before prompt compilation.')),
            FilledButton(onPressed: session.busy ? null : session.runGrill, child: const Text('Run grill')),
          ],
        ),
        const SizedBox(height: 12),
        if (report != null) Text(report['narrative']?.toString() ?? report['summary']?.toString() ?? ''),
        if (questions is List)
          for (final item in questions.whereType<Map>())
            ListTile(
              title: Text(item['question']?.toString() ?? ''),
              subtitle: Text(item['answer']?.toString() ?? ''),
            ),
      ],
    );
  }
}

class ProfessionalScreen extends StatelessWidget {
  const ProfessionalScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final report = session.reviewReport;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const Expanded(child: Text('Professional Mode explains feasibility and scope. You decide.')),
            FilledButton(onPressed: session.busy ? null : session.runReview, child: const Text('Review')),
          ],
        ),
        const SizedBox(height: 12),
        if (report != null) ...[
          Text(report['summary']?.toString() ?? ''),
          const SizedBox(height: 8),
          Text('Feasibility: ${report['feasibility']}'),
          Text('Scope: ${report['scope']}'),
          Text('Academic relevance: ${report['academic_relevance']}'),
        ],
      ],
    );
  }
}
