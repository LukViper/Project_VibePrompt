class ProjectModels {
  static List<Map<String, dynamic>> requirements(Map<String, dynamic>? state) {
    final rows = state?['requirements'];
    if (rows is! List) return [];
    return rows.whereType<Map>().map((row) => Map<String, dynamic>.from(row)).toList();
  }

  static List<Map<String, dynamic>> decisions(Map<String, dynamic>? state) {
    final rows = state?['decisions'];
    if (rows is! List) return [];
    return rows.whereType<Map>().map((row) => Map<String, dynamic>.from(row)).toList();
  }

  static List<Map<String, dynamic>> conflicts(Map<String, dynamic>? state) {
    final rows = state?['conflicts'];
    if (rows is! List) return [];
    return rows.whereType<Map>().map((row) => Map<String, dynamic>.from(row)).toList();
  }
}
