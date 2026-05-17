import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// JWT storage backed by Keychain (iOS) / EncryptedSharedPreferences
/// (Android). Distinct from the admin panel's localStorage approach —
/// mobile platforms expose proper at-rest encryption so we take it.
///
/// Refresh tokens will live here too once Phase 2 backend work
/// lands. For now only the access token is stored.
class TokenStorage {
  static const _accessTokenKey = 'officeportal.mobile.access_token';

  final FlutterSecureStorage _storage;

  TokenStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
            );

  Future<String?> readAccessToken() => _storage.read(key: _accessTokenKey);

  Future<void> writeAccessToken(String token) =>
      _storage.write(key: _accessTokenKey, value: token);

  Future<void> clearAccessToken() => _storage.delete(key: _accessTokenKey);
}
