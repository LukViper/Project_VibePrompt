import 'package:flutter/foundation.dart';

import '../core/api/api_client.dart';
import '../core/api/api_exception.dart';
import '../models/idea.dart';
import '../models/message.dart';

enum WorkspaceMode { chat, ideas, professional, grill, specification, prompt, state }

class SessionController extends ChangeNotifier {
  SessionController(this.api);

  final ApiClient api;
  String? projectId;
  String? accessToken;
  Map<String, dynamic>? user;
  Map<String, dynamic>? state;
  Map<String, dynamic>? promptValidation;
  String? stage;
  final List<ChatMessage> messages = [];
  List<ProjectIdea> ideas = [];
  Map<String, dynamic>? grillReport;
  Map<String, dynamic>? grillListing;
  Map<String, dynamic>? pendingGrillPreview;
  String? selectedAttackId;
  Map<String, dynamic>? reviewReport;
  Map<String, dynamic>? selectedLineage;
  String specification = '';
  String prompt = '';
  WorkspaceMode mode = WorkspaceMode.chat;
  bool busy = false;
  String? error;

  bool get hasProject => projectId != null;
  bool get isGuest => user?['is_guest'] == true;
  bool get isAuthenticated => accessToken != null && accessToken!.isNotEmpty;

  Future<void> continueAsGuest() async {
    await _run(() async {
      final auth = await api.continueAsGuest();
      _applyAuth(auth);
    });
  }

  Future<void> register(String email, String password, {String displayName = ''}) async {
    await _run(() async {
      final auth = await api.register(email: email, password: password, displayName: displayName);
      _applyAuth(auth);
    });
  }

  Future<void> login(String email, String password) async {
    await _run(() async {
      final auth = await api.login(email: email, password: password);
      _applyAuth(auth);
    });
  }

  void _applyAuth(Map<String, dynamic> auth) {
    accessToken = auth['access_token']?.toString();
    api.accessToken = accessToken;
    if (auth['user'] is Map) {
      user = Map<String, dynamic>.from(auth['user'] as Map);
    }
  }

  Future<void> start(String description) async {
    await _run(() async {
      if (!isAuthenticated) {
        final auth = await api.continueAsGuest();
        _applyAuth(auth);
      }
      final created = await api.createProject(description: description);
      projectId = created['id'].toString();
      state = Map<String, dynamic>.from(created['state'] as Map);
      stage = state?['conversation_stage']?.toString() ?? created['stage']?.toString();
      final analysis = created['analysis'];
      if (analysis is Map) {
        _addTurn(analysis.cast<String, dynamic>());
        stage = analysis['stage']?.toString() ?? stage;
      }
      mode = WorkspaceMode.chat;
    });
  }

  Future<void> send(String content) async {
    final id = projectId;
    if (id == null || content.trim().isEmpty) return;
    await _run(() async {
      final result = await api.sendMessage(id, content.trim());
      _addTurn(result);
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
      stage = result['stage']?.toString() ?? state?['conversation_stage']?.toString() ?? stage;
      final ideaRows = result['ideas'];
      if (ideaRows is List && ideaRows.isNotEmpty) {
        ideas = ideaRows
            .whereType<Map>()
            .map((row) => ProjectIdea.fromJson(Map<String, dynamic>.from(row)))
            .toList();
      }
    });
  }

  Future<void> requestIdeas() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      messages.add(const ChatMessage(role: 'user', content: 'Suggest detailed project ideas'));
      try {
        final rows = await api.generateIdeas(id);
        final cards = ProjectIdeaCard.listFrom(rows);
        ideas = rows
            .whereType<Map>()
            .map((row) => ProjectIdea.fromJson(Map<String, dynamic>.from(row)))
            .toList();
        state = await api.getState(id);
        stage = state?['conversation_stage']?.toString() ?? stage;
        final buffer = StringBuffer('Here are detailed project ideas you can customize or select:');
        for (var i = 0; i < ideas.length; i++) {
          final idea = ideas[i];
          buffer.writeln('\n${i + 1}. ${idea.title}');
          if (idea.problem.isNotEmpty) buffer.writeln('   Problem: ${idea.problem}');
          if (idea.objective.isNotEmpty) buffer.writeln('   Objective: ${idea.objective}');
        }
        messages.add(ChatMessage(role: 'assistant', content: buffer.toString(), ideas: cards));
      } on ApiException catch (err) {
        messages.add(ChatMessage(role: 'assistant', content: _capabilityGateMessage(err)));
      }
    });
  }

  Future<void> requestMoreIdeas() => requestIdeas();

  Future<void> loadIdeas() => requestIdeas();

  Future<void> requestArchitecture() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      messages.add(const ChatMessage(role: 'user', content: 'Propose an architecture and tech stack'));
      try {
        final result = await api.proposeArchitecture(id);
        if (result['state'] is Map) {
          state = Map<String, dynamic>.from(result['state'] as Map);
        } else {
          state = await api.getState(id);
        }
        stage = state?['conversation_stage']?.toString() ?? stage;
        final narrative = result['narrative']?.toString() ?? 'Architecture proposed.';
        messages.add(ChatMessage(role: 'assistant', content: narrative));
      } on ApiException catch (err) {
        messages.add(ChatMessage(role: 'assistant', content: _capabilityGateMessage(err)));
      }
    });
  }

  String _capabilityGateMessage(ApiException err) {
    final body = err.message;
    final guidanceMatch = RegExp(r'"guidance"\s*:\s*"([^"]+)"').firstMatch(body);
    if (guidanceMatch != null) return guidanceMatch.group(1)!;
    if (body.contains('missing_domain')) {
      return 'Tell me the course or domain first before I suggest project ideas.';
    }
    if (body.contains('missing_core_idea')) {
      return 'Pick or describe a concrete project direction first, then I can propose architecture.';
    }
    if (body.contains('missing_project_to_grill')) {
      return 'Share a direction or requirements first — grilling needs a real project to challenge.';
    }
    return 'That capability is gated until ProjectState is ready. $body';
  }

  Future<void> selectIdeaCard(ProjectIdeaCard idea) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.selectIdea(id, idea.id);
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
      stage = state?['conversation_stage']?.toString() ?? stage;
      _stripIdeaActions();
      messages.add(ChatMessage(role: 'user', content: 'I select idea ${idea.index}: ${idea.title}'));
      messages.add(
        ChatMessage(
          role: 'assistant',
          content:
              'Locked “${idea.title}” as the core direction. Tell me what to refine, '
              'or ask for research, architecture, grill, or the final prompt.',
        ),
      );
      ideas = ideas
          .map(
            (item) => ProjectIdea(
              id: item.id,
              title: item.title,
              problem: item.problem,
              objective: item.objective,
              difficulty: item.difficulty,
              estimatedScope: item.estimatedScope,
              features: item.features,
              technology: item.technology,
              selected: item.id == idea.id,
            ),
          )
          .toList();
      mode = WorkspaceMode.chat;
    });
  }

  Future<void> selectIdea(ProjectIdea idea) async {
    await selectIdeaCard(
      ProjectIdeaCard(
        id: idea.id,
        index: ideas.indexWhere((item) => item.id == idea.id) + 1,
        title: idea.title,
        problem: idea.problem,
        objective: idea.objective,
        difficulty: idea.difficulty,
        estimatedScope: idea.estimatedScope,
        selected: idea.selected,
      ),
    );
  }

  Future<void> reject(ProjectIdea idea) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.rejectIdea(id, idea.id);
      if (result['state'] is Map) state = Map<String, dynamic>.from(result['state'] as Map);
      ideas = ideas.where((item) => item.id != idea.id).toList();
    });
  }

  Future<void> approveProposedDecision(String decisionId) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.approveDecision(id, decisionId);
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
      messages.add(ChatMessage(role: 'user', content: 'I approve decision $decisionId'));
      messages.add(
        ChatMessage(
          role: 'assistant',
          content: 'Decision activated. It is now ACTIVE with your approval.',
        ),
      );
    });
  }

  Future<void> rejectProposedDecision(String decisionId) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.rejectDecision(id, decisionId);
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
    });
  }

  List<Map<String, dynamic>> get proposedDecisions {
    final rows = state?['decisions'];
    if (rows is! List) return const [];
    return rows
        .whereType<Map>()
        .map((row) => Map<String, dynamic>.from(row))
        .where((row) => row['status'] == 'PROPOSED' || row['status'] == 'UNCERTAIN')
        .toList();
  }

  Future<void> loadSummary() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.getSummary(id);
      final narrative = result['narrative']?.toString() ?? '';
      if (narrative.isNotEmpty) {
        messages.add(ChatMessage(role: 'assistant', content: narrative));
      }
    });
  }

  Future<void> runGrill() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      messages.add(const ChatMessage(role: 'user', content: 'Grill this project'));
      try {
        grillReport = await api.grill(id);
        grillListing = await api.listGrill(id);
        if (grillReport?['state'] is Map) {
          state = Map<String, dynamic>.from(grillReport!['state'] as Map);
        } else {
          state = await api.getState(id);
        }
        pendingGrillPreview = null;
        selectedAttackId = null;
        mode = WorkspaceMode.grill;
        final narrative = grillReport?['narrative']?.toString()
            ?? 'Grill completed. Review attacks in the Grill panel.';
        messages.add(ChatMessage(role: 'assistant', content: narrative));
      } on ApiException catch (err) {
        messages.add(ChatMessage(role: 'assistant', content: _capabilityGateMessage(err)));
      }
    });
  }

  Future<void> previewGrillResponse(String attackId, String responseText, String resolutionType) async {
    final id = projectId;
    if (id == null) return;
    selectedAttackId = attackId;
    // Preview only — do not persist. Show intended resolution locally.
    pendingGrillPreview = {
      'attack_id': attackId,
      'response_text': responseText,
      'resolution_type': resolutionType,
      'note': 'Preview only — confirm to persist state changes.',
    };
    notifyListeners();
  }

  Future<void> confirmGrillResponse() async {
    final id = projectId;
    final preview = pendingGrillPreview;
    if (id == null || preview == null) return;
    await _run(() async {
      final result = await api.respondGrill(
        id,
        preview['attack_id'].toString(),
        responseText: preview['response_text']?.toString() ?? '',
        resolutionType: preview['resolution_type']?.toString() ?? 'RESOLVED',
        mutate: true,
      );
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
      grillListing = result['grill'] is Map
          ? Map<String, dynamic>.from(result['grill'] as Map)
          : await api.listGrill(id);
      pendingGrillPreview = null;
      selectedAttackId = null;
    });
  }

  Future<void> attachEvidenceToRequirement(String requirementId, String claim) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.attachEvidence(
        id,
        claim: claim,
        attachToType: 'requirement',
        attachToId: requirementId,
        verificationStatus: 'UNVERIFIED',
      );
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
    });
  }

  Future<void> loadRequirementLineage(String requirementId) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      selectedLineage = await api.getRequirementLineage(id, requirementId);
      mode = WorkspaceMode.state;
    });
  }

  Future<void> runReview() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      reviewReport = await api.review(id);
      mode = WorkspaceMode.professional;
    });
  }

  Future<void> buildSpecification() async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.specification(id);
      specification = result['markdown']?.toString() ?? '';
      mode = WorkspaceMode.specification;
    });
  }

  Future<void> buildPrompt({bool force = false}) async {
    final id = projectId;
    if (id == null) return;
    await _run(() async {
      final result = await api.compilePrompt(id, force: force);
      prompt = result['content']?.toString() ?? '';
      if (result['validation'] is Map) {
        promptValidation = Map<String, dynamic>.from(result['validation'] as Map);
      }
      if (result['state'] is Map) {
        state = Map<String, dynamic>.from(result['state'] as Map);
      }
      mode = WorkspaceMode.prompt;
    });
  }

  void setMode(WorkspaceMode next) {
    mode = next;
    notifyListeners();
  }

  void _stripIdeaActions() {
    for (var i = 0; i < messages.length; i++) {
      if (messages[i].hasIdeas) {
        messages[i] = messages[i].copyWithoutIdeas();
      }
    }
  }

  void _addTurn(Map<String, dynamic> result) {
    final user = result['user_message'];
    final assistant = result['assistant_message'];
    if (user is Map) messages.add(ChatMessage.fromJson(Map<String, dynamic>.from(user)));
    if (assistant is Map) {
      final msg = ChatMessage.fromJson(Map<String, dynamic>.from(assistant));
      // Prefer top-level ideas payload when analysis omitted them.
      final topIdeas = ProjectIdeaCard.listFrom(result['ideas']);
      if (!msg.hasIdeas && topIdeas.isNotEmpty) {
        messages.add(
          ChatMessage(role: msg.role, content: msg.content, intent: msg.intent, ideas: topIdeas),
        );
      } else {
        messages.add(msg);
      }
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action();
    } catch (error) {
      this.error = error.toString();
    } finally {
      busy = false;
      notifyListeners();
    }
  }
}
