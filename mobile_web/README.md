# VibePrompt client

One Flutter codebase for web, Android, and iOS. It talks only to the FastAPI backend. It does not hold an LLM key.

```bash
flutter pub get
flutter run -d chrome
flutter run -d android
flutter run -d ios
```

Desktop width shows the three-column workspace: project, conversation, and project state, with Ideas, Professional, Grill, Specification, and Prompt along the bottom. Narrow screens use Chat, Ideas, State, and Prompt.

Set the API host when it is not localhost:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000
```
