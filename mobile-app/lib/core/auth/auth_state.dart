import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:officeportal_mobile/core/api/api_client.dart';

import 'package:officeportal_mobile/core/auth/auth_models.dart';
import 'package:officeportal_mobile/core/auth/token_storage.dart';

/// Auth state. Three discrete states keep the router's redirect logic
/// simple: while we're loading, don't bounce; once resolved, send the
/// user to /login or /dashboard based on whether `user` is non-null.
enum AuthStatus { loading, authenticated, unauthenticated }

class AuthState {
  final AuthStatus status;
  final AuthenticatedUser? user;

  const AuthState({required this.status, required this.user});

  const AuthState.loading()
      : status = AuthStatus.loading,
        user = null;

  const AuthState.unauthenticated()
      : status = AuthStatus.unauthenticated,
        user = null;

  AuthState.authenticated(AuthenticatedUser u)
      : status = AuthStatus.authenticated,
        user = u;
}

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

/// Single ApiClient instance shared across the app. Constructed once
/// at first access; reads from secure storage on each request via the
/// interceptor, so token rotation just works.
final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});

final tokenStorageProvider = Provider<TokenStorage>((ref) {
  return TokenStorage();
});

/// Auth controller. Exposes `login` and `logout` actions plus the
/// current AuthState. Wire screens with `ref.watch(authProvider)`.
class AuthController extends StateNotifier<AuthState> {
  final ApiClient _api;
  final TokenStorage _tokens;

  AuthController(this._api, this._tokens) : super(const AuthState.loading()) {
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final token = await _tokens.readAccessToken();
    if (token == null) {
      state = const AuthState.unauthenticated();
      return;
    }
    await _refreshUser();
  }

  Future<void> _refreshUser() async {
    try {
      final res = await _api.raw.get<Map<String, dynamic>>('/auth/me');
      final body = res.data;
      if (body == null || body['data'] == null) {
        throw DioException(
          requestOptions: res.requestOptions,
          message: 'Empty /auth/me payload',
        );
      }
      final user = AuthenticatedUser.fromJson(
        body['data'] as Map<String, dynamic>,
      );
      state = AuthState.authenticated(user);
    } catch (_) {
      // Token expired, invalid, or backend unreachable. The axios-side
      // interceptor already cleared the stored token on 401. For other
      // errors we clear defensively so we don't loop forever.
      await _tokens.clearAccessToken();
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> login({required String roll, required String password}) async {
    // Mobile uses the roll-no flow. Admin web uses email — different
    // login endpoints on the backend.
    final res = await _api.raw.post<Map<String, dynamic>>(
      '/auth/employee/login',
      data: {'roll_no': roll, 'password': password},
    );
    final data = (res.data?['data'] as Map<String, dynamic>?);
    final token = data?['access_token'] as String?;
    if (token == null) {
      throw StateError('Login response missing access_token');
    }
    await _tokens.writeAccessToken(token);
    await _refreshUser();
  }

  Future<void> logout() async {
    try {
      await _api.raw.post('/auth/logout');
    } catch (_) {
      // Server-side logout is a stub and may fail; proceed with the
      // client-side teardown regardless.
    }
    await _tokens.clearAccessToken();
    state = const AuthState.unauthenticated();
  }
}

final authProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  return AuthController(
    ref.watch(apiClientProvider),
    ref.watch(tokenStorageProvider),
  );
});
