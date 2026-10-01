class ProjectIdea {
  ProjectIdea({
    required this.id,
    required this.title,
    required this.problem,
    required this.objective,
    required this.difficulty,
    required this.estimatedScope,
    required this.features,
    required this.technology,
    required this.selected,
  });

  final String id;
  final String title;
  final String problem;
  final String objective;
  final String difficulty;
  final String estimatedScope;
  final List<String> features;
  final List<String> technology;
  final bool selected;

  factory ProjectIdea.fromJson(Map<String, dynamic> json) {
    return ProjectIdea(
      id: json['id'].toString(),
      title: json['title']?.toString() ?? '',
      problem: json['problem']?.toString() ?? '',
      objective: json['objective']?.toString() ?? '',
      difficulty: json['difficulty']?.toString() ?? '',
      estimatedScope: json['estimated_scope']?.toString() ?? '',
      features: _strings(json['features']),
      technology: _strings(json['technology']),
      selected: json['selected'] == true,
    );
  }

  static List<String> _strings(dynamic value) {
    if (value is! List) return [];
    return value.map((item) => item.toString()).toList();
  }
}
