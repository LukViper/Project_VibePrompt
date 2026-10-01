class ChatMessage {
  ChatMessage({
    required this.role,
    required this.content,
    this.intent,
    this.ideas = const [],
  });

  final String role;
  final String content;
  final String? intent;
  final List<ProjectIdeaCard> ideas;

  bool get hasIdeas => ideas.isNotEmpty;

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    final analysis = json['analysis'];
    final rawIdeas = analysis is Map ? analysis['ideas'] : null;
    return ChatMessage(
      role: json['role']?.toString() ?? 'assistant',
      content: json['content']?.toString() ?? '',
      intent: json['intent']?.toString(),
      ideas: ProjectIdeaCard.listFrom(rawIdeas),
    );
  }

  ChatMessage copyWithoutIdeas() => ChatMessage(
        role: role,
        content: content,
        intent: intent,
        ideas: const [],
      );
}

class ProjectIdeaCard {
  ProjectIdeaCard({
    required this.id,
    required this.index,
    required this.title,
    required this.problem,
    required this.objective,
    required this.difficulty,
    required this.estimatedScope,
    this.selected = false,
  });

  final String id;
  final int index;
  final String title;
  final String problem;
  final String objective;
  final String difficulty;
  final String estimatedScope;
  final bool selected;

  factory ProjectIdeaCard.fromJson(Map<String, dynamic> json) {
    return ProjectIdeaCard(
      id: json['id'].toString(),
      index: (json['index'] as num?)?.toInt() ?? 0,
      title: json['title']?.toString() ?? '',
      problem: json['problem']?.toString() ?? '',
      objective: json['objective']?.toString() ?? '',
      difficulty: json['difficulty']?.toString() ?? '',
      estimatedScope: json['estimated_scope']?.toString() ?? '',
      selected: json['selected'] == true,
    );
  }

  static List<ProjectIdeaCard> listFrom(dynamic value) {
    if (value is! List) return const [];
    return value
        .whereType<Map>()
        .map((row) => ProjectIdeaCard.fromJson(Map<String, dynamic>.from(row)))
        .toList();
  }
}
