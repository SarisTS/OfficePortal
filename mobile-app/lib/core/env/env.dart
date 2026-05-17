/// Compile-time env access. Values come from --dart-define-from-file=.env
/// at build time; there is no runtime .env file shipped in the bundle.
///
/// Run with `flutter run --dart-define-from-file=.env` (see
/// .env.example). For production, CI passes the same flag with the
/// staging/production .env contents.
class Env {
  /// Base URL of the FastAPI backend. No trailing slash.
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    // Fall back to the Android emulator host alias so a developer who
    // forgets to set --dart-define-from-file still hits something
    // sensible on their local backend.
    defaultValue: 'http://10.0.2.2:8000',
  );

  /// True when running a debug build (`flutter run` without --release).
  static bool get isDebug {
    bool debug = false;
    assert(() {
      debug = true;
      return true;
    }());
    return debug;
  }
}
