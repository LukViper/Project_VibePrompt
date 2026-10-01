import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/project_service.dart';

class SpecificationScreen extends StatelessWidget {
  const SpecificationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: FilledButton(onPressed: session.busy ? null : session.buildSpecification, child: const Text('Generate specification')),
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: SelectableText(session.specification.isEmpty ? 'No specification yet.' : session.specification),
          ),
        ),
      ],
    );
  }
}
