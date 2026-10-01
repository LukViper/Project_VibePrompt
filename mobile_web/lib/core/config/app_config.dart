import 'platform_url.dart';

class AppConfig {
  static const definedUrl = String.fromEnvironment('API_BASE_URL');

  static String get baseUrl {
    if (definedUrl.isNotEmpty) return definedUrl;
    return defaultApiBaseUrl();
  }
}
