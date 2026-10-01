import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_exception.dart';

class ApiClient {
  ApiClient(this.baseUrl, {http.Client? client}) : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  String? accessToken;

  Future<Map<String, dynamic>> continueAsGuest() => _map('POST', '/auth/guest');

  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    String displayName = '',
  }) {
    return _map('POST', '/auth/register', {
      'email': email,
      'password': password,
      'display_name': displayName,
    });
  }

  Future<Map<String, dynamic>> login({required String email, required String password}) {
    return _map('POST', '/auth/login', {'email': email, 'password': password});
  }

  Future<Map<String, dynamic>> me() => _map('GET', '/auth/me');

  Future<List<dynamic>> listProjects() async => _asList(await _send('GET', '/projects'));

  Future<Map<String, dynamic>> createProject({String? title, String? description}) {
    return _map('POST', '/projects', {'title': title ?? '', 'description': description});
  }

  Future<Map<String, dynamic>> getState(String id) => _map('GET', '/projects/$id/state');

  Future<List<dynamic>> getMessages(String id) async {
    final body = await _send('GET', '/projects/$id/messages');
    return _asList(body);
  }

  Future<Map<String, dynamic>> sendMessage(String id, String content) {
    return _map('POST', '/projects/$id/messages', {'content': content});
  }

  Future<List<dynamic>> getRequirements(String id) async {
    return _asList(await _send('GET', '/projects/$id/requirements'));
  }

  Future<List<dynamic>> generateIdeas(String id) async {
    return _asList(await _send('POST', '/projects/$id/ideas'));
  }

  Future<Map<String, dynamic>> selectIdea(String id, String ideaId) {
    return _map('POST', '/projects/$id/ideas/$ideaId/select');
  }

  Future<Map<String, dynamic>> rejectIdea(String id, String ideaId) {
    return _map('POST', '/projects/$id/ideas/$ideaId/reject');
  }

  Future<List<dynamic>> listDecisions(String id, {String? status}) async {
    final path = status == null ? '/projects/$id/decisions' : '/projects/$id/decisions?status=$status';
    return _asList(await _send('GET', path));
  }

  Future<Map<String, dynamic>> approveDecision(String id, String decisionId) {
    return _map('POST', '/projects/$id/decisions/$decisionId/approve');
  }

  Future<Map<String, dynamic>> rejectDecision(String id, String decisionId) {
    return _map('POST', '/projects/$id/decisions/$decisionId/reject');
  }

  Future<Map<String, dynamic>> getSummary(String id) => _map('GET', '/projects/$id/summary');

  Future<Map<String, dynamic>> grill(String id) => _map('POST', '/projects/$id/grill');

  Future<Map<String, dynamic>> listGrill(String id) => _map('GET', '/projects/$id/grill');

  Future<Map<String, dynamic>> respondGrill(
    String id,
    String attackId, {
    required String responseText,
    String resolutionType = 'RESOLVED',
    bool mutate = true,
  }) {
    return _map('POST', '/projects/$id/grill/$attackId/respond', {
      'response_text': responseText,
      'resolution_type': resolutionType,
      'mutate': mutate,
    });
  }

  Future<Map<String, dynamic>> attachEvidence(
    String id, {
    required String claim,
    String? attachToType,
    String? attachToId,
    String verificationStatus = 'UNVERIFIED',
  }) {
    return _map('POST', '/projects/$id/evidence', {
      'claim': claim,
      'attach_to_type': attachToType,
      'attach_to_id': attachToId,
      'verification_status': verificationStatus,
    });
  }

  Future<Map<String, dynamic>> getIntegrity(String id) => _map('GET', '/projects/$id/integrity');

  Future<Map<String, dynamic>> getRequirementLineage(String id, String requirementId) {
    return _map('GET', '/projects/$id/requirements/$requirementId/lineage');
  }

  Future<Map<String, dynamic>> review(String id) => _map('POST', '/projects/$id/review');

  Future<Map<String, dynamic>> specification(String id) => _map('POST', '/projects/$id/specification');

  Future<Map<String, dynamic>> compilePrompt(String id, {bool force = false}) {
    return _map('POST', '/projects/$id/prompt', {'force': force});
  }

  Future<Map<String, dynamic>> validatePrompt(String id) {
    return _map('POST', '/projects/$id/prompt/validate', {'repair': true});
  }

  Future<Map<String, dynamic>> getPrompt(String id) => _map('GET', '/projects/$id/prompt');

  Future<Map<String, dynamic>> _map(String method, String path, [Object? jsonBody]) async {
    final body = await _send(method, path, jsonBody);
    return Map<String, dynamic>.from(body as Map);
  }

  Future<dynamic> _send(String method, String path, [Object? jsonBody]) async {
    final uri = Uri.parse('$baseUrl$path');
    late http.Response response;
    try {
      if (method == 'POST') {
        response = await _client.post(uri, headers: _headers, body: jsonEncode(jsonBody ?? {}));
      } else if (method == 'PATCH') {
        response = await _client.patch(uri, headers: _headers, body: jsonEncode(jsonBody ?? {}));
      } else if (method == 'DELETE') {
        response = await _client.delete(uri, headers: _headers);
      } else {
        response = await _client.get(uri, headers: _headers);
      }
    } catch (error) {
      throw ApiException('Cannot reach the VibePrompt API at $baseUrl. Start the backend and try again.');
    }
    if (response.statusCode >= 400) {
      throw ApiException('API ${response.statusCode}: ${response.body}', statusCode: response.statusCode);
    }
    if (response.body.isEmpty) return <String, dynamic>{};
    return jsonDecode(response.body);
  }

  Map<String, String> get _headers {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    final token = accessToken;
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  List<dynamic> _asList(dynamic body) {
    if (body is List) return body;
    return const [];
  }
}
