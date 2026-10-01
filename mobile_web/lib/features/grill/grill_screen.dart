import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/project_service.dart';

class GrillScreen extends StatefulWidget {
  const GrillScreen({super.key});

  @override
  State<GrillScreen> createState() => _GrillScreenState();
}

class _GrillScreenState extends State<GrillScreen> {
  final _responseCtrl = TextEditingController();
  String _resolution = 'RESOLVED';
  String? _activeAttackId;

  @override
  void dispose() {
    _responseCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final report = session.grillReport;
    final listing = session.grillListing;
    final open = (listing?['open'] as List?)?.whereType<Map>().toList() ??
        (report?['attacks'] as List?)?.whereType<Map>().toList() ??
        const [];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const Expanded(
              child: Text('Grill Mode challenges concrete ProjectState entities before compilation.'),
            ),
            FilledButton(onPressed: session.busy ? null : session.runGrill, child: const Text('Run grill')),
          ],
        ),
        const SizedBox(height: 12),
        if (report != null) Text(report['narrative']?.toString() ?? report['summary']?.toString() ?? ''),
        const SizedBox(height: 12),
        Text('Open attacks: ${open.length}', style: const TextStyle(fontWeight: FontWeight.w700)),
        for (final attack in open)
          Card(
            margin: const EdgeInsets.symmetric(vertical: 6),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${attack['id']} → ${attack['target_type']} ${attack['target_id']}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text('Severity: ${attack['severity']} · Blocking: ${attack['blocking']}'),
                  const SizedBox(height: 4),
                  Text(attack['challenge']?.toString() ?? ''),
                  if ((attack['evidence_required']?.toString() ?? '').isNotEmpty)
                    Text('Evidence requested: ${attack['evidence_required']}'),
                  if ((attack['failure_condition']?.toString() ?? '').isNotEmpty)
                    Text('Failure: ${attack['failure_condition']}'),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: [
                      OutlinedButton(
                        onPressed: () => setState(() {
                          _activeAttackId = attack['id']?.toString();
                          _resolution = 'RESOLVED';
                        }),
                        child: const Text('Respond'),
                      ),
                      OutlinedButton(
                        onPressed: () => setState(() {
                          _activeAttackId = attack['id']?.toString();
                          _resolution = 'REJECTED';
                          _responseCtrl.text = 'Reject this attack';
                        }),
                        child: const Text('Reject'),
                      ),
                      OutlinedButton(
                        onPressed: () => setState(() {
                          _activeAttackId = attack['id']?.toString();
                          _resolution = 'DEFERRED';
                          _responseCtrl.text = 'Defer for later';
                        }),
                        child: const Text('Defer'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        if (_activeAttackId != null) ...[
          const Divider(),
          Text('Response to $_activeAttackId', style: const TextStyle(fontWeight: FontWeight.w700)),
          TextField(
            controller: _responseCtrl,
            maxLines: 3,
            decoration: const InputDecoration(hintText: 'Your answer…'),
          ),
          DropdownButton<String>(
            value: _resolution,
            items: const [
              DropdownMenuItem(value: 'RESOLVED', child: Text('RESOLVED')),
              DropdownMenuItem(value: 'REJECTED', child: Text('REJECTED')),
              DropdownMenuItem(value: 'DEFERRED', child: Text('DEFERRED')),
              DropdownMenuItem(value: 'PARTIALLY_RESOLVED', child: Text('PARTIALLY_RESOLVED')),
            ],
            onChanged: (v) => setState(() => _resolution = v ?? 'RESOLVED'),
          ),
          Row(
            children: [
              OutlinedButton(
                onPressed: () {
                  session.previewGrillResponse(_activeAttackId!, _responseCtrl.text, _resolution);
                },
                child: const Text('Preview state changes'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: session.pendingGrillPreview == null || session.busy
                    ? null
                    : () async {
                        await session.confirmGrillResponse();
                        setState(() {
                          _activeAttackId = null;
                          _responseCtrl.clear();
                        });
                      },
                child: const Text('Confirm'),
              ),
            ],
          ),
          if (session.pendingGrillPreview != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                session.pendingGrillPreview!['note']?.toString() ?? '',
                style: const TextStyle(fontStyle: FontStyle.italic),
              ),
            ),
        ],
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
