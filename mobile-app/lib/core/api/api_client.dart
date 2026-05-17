import 'package:dio/dio.dart';

import 'package:officeportal_mobile/core/auth/token_storage.dart';
import 'package:officeportal_mobile/core/env/env.dart';

import 'package:officeportal_mobile/core/api/api_types.dart';

/// Single Dio instance for the whole app. Interceptor attaches the
/// stored JWT on every outgoing request and clears it on 401.
///
/// Mirrors the admin-panel's axios setup; the same auth flow story
/// applies here.
class ApiClient {
  final Dio _dio;
  final TokenStorage _tokens;

  ApiClient({TokenStorage? tokenStorage, Dio? dio})
      : _tokens = tokenStorage ?? TokenStorage(),
        _dio = dio ??
            Dio(BaseOptions(
              baseUrl: Env.apiUrl,
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 15),
              sendTimeout: const Duration(seconds: 15),
              // Default to JSON requests + responses. Per-request
              // overrides (file upload etc.) can change this.
              contentType: 'application/json',
              responseType: ResponseType.json,
            )) {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _tokens.readAccessToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (err, handler) async {
        if (err.response?.statusCode == 401) {
          await _tokens.clearAccessToken();
          // Caller / router guard handles the redirect — we keep this
          // module navigation-agnostic.
        }
        handler.next(err);
      },
    ));
  }

  Dio get raw => _dio;

  /// Pull the user-facing message out of a DioException. Backend wraps
  /// errors as `{ status: "error", code, message }` — fall back to the
  /// transport message and finally to a generic label.
  static String errorMessage(Object error) {
    if (error is DioException) {
      final body = error.response?.data;
      if (body is Map<String, dynamic>) {
        try {
          return ApiErrorBody.fromJson(body).message;
        } catch (_) {
          // Body didn't match the envelope — fall through.
        }
      }
      return error.message ?? 'Network error';
    }
    return 'Unexpected error';
  }
}
