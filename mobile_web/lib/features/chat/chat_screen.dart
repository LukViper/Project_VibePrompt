import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/app_theme.dart';
import '../../services/project_service.dart';
import '../../widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  /// Distance from the bottom within which new messages auto-follow.
  static const double _followThreshold = 120;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  bool _isNearBottom() {
    if (!_scroll.hasClients) return true;
    final position = _scroll.position;
    if (!position.hasContentDimensions) return true;
    return position.pixels >= position.maxScrollExtent - _followThreshold;
  }

  Future<void> _scrollToBottomIfFollowing(bool follow) async {
    if (!follow) return;
    // Wait until ListView has laid out the new messages.
    await Future<void>.delayed(Duration.zero);
    if (!mounted) return;
    final done = WidgetsBinding.instance.endOfFrame;
    await done;
    if (!mounted || !_scroll.hasClients) return;
    await _scroll.animateTo(
      _scroll.position.maxScrollExtent,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final latestIdeaIndex = session.messages.lastIndexWhere((message) => message.hasIdeas);
    return Column(
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: Row(
            children: [
              for (final tip in const [
                ('Suggest ideas', 'Suggest detailed project ideas'),
                ('Grill this project', 'Grill this project'),
                ('Find existing systems', 'Are there any existing systems or datasets for this project?'),
                ('Propose architecture', 'Propose an architecture and tech stack'),
                ('Compile the final prompt', 'Compile the final prompt'),
              ])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    label: Text(tip.$1),
                    onPressed: session.busy ? null : () => _send(tip.$2),
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          child: Scrollbar(
            controller: _scroll,
            thumbVisibility: true,
            interactive: true,
            // MessageBubble uses SelectableText for BOTH user and assistant
            // content (native selection / copy). Do not wrap SelectableText in
            // SelectionArea — nested selectable regions assert at runtime.
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(16),
              itemCount: session.messages.length,
              itemBuilder: (context, index) => MessageBubble(
                message: session.messages[index],
                showIdeaActions: index == latestIdeaIndex,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  decoration: const InputDecoration(
                    hintText: 'Describe your idea, pick from suggestions, or refine…',
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: session.busy ? null : _send,
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: session.busy ? null : () => _send(_input.text),
                icon: const Icon(Icons.send),
                style: IconButton.styleFrom(backgroundColor: AppTheme.pine),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _send(String value) async {
    if (value.trim().isEmpty) return;
    // Capture before the list grows — otherwise maxScrollExtent moves and
    // a user who was at the bottom looks "scrolled up".
    final follow = _isNearBottom();
    _input.clear();
    await context.read<SessionController>().send(value);
    await _scrollToBottomIfFollowing(follow);
  }
}
