import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:vibeprompt/core/api/api_client.dart';
import 'package:vibeprompt/features/chat/chat_screen.dart';
import 'package:vibeprompt/models/message.dart';
import 'package:vibeprompt/services/project_service.dart';

void main() {
  testWidgets('user and assistant message text are both SelectableText', (tester) async {
    final session = SessionController(ApiClient('http://localhost:8000'));
    session.messages.addAll([
      ChatMessage(role: 'user', content: 'I want an NLP project.'),
      ChatMessage(
        role: 'assistant',
        content: 'What part of NLP interests you most?\n\n```python\nprint("hello")\n```\nhttps://example.com',
      ),
    ]);

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: session,
        child: const MaterialApp(home: Scaffold(body: ChatScreen())),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(Scrollbar), findsWidgets);

    // Both roles use SelectableText (native selection / Ctrl+C / long-press copy).
    final selectable = find.byType(SelectableText);
    expect(selectable, findsWidgets);

    expect(
      find.descendant(
        of: find.byType(SelectableText),
        matching: find.text('I want an NLP project.'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byType(SelectableText),
        matching: find.textContaining('What part of NLP interests you most?'),
      ),
      findsOneWidget,
    );
    expect(find.textContaining('print("hello")'), findsOneWidget);
    expect(find.textContaining('https://example.com'), findsOneWidget);

    // Role labels are also selectable for both bubbles.
    expect(
      find.descendant(of: find.byType(SelectableText), matching: find.text('You')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: find.byType(SelectableText), matching: find.text('VibePrompt')),
      findsOneWidget,
    );
  });
}
