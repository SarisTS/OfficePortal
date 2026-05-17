/// Shape of every successful response from the FastAPI backend.
/// Mirrors `backend/app/utils/api_response.py::ApiResponse[T]`.
///
/// Generic over T so callers can `ApiResponse<EmployeeResponse>.fromJson(...)`
/// and get type-safe access to `.data`. The `fromJsonT` argument decodes
/// the payload — keep it small and reusable per feature.
class ApiResponse<T> {
  final int status;
  final String message;
  final T data;

  ApiResponse({
    required this.status,
    required this.message,
    required this.data,
  });

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Object?) fromJsonT,
  ) {
    return ApiResponse<T>(
      status: json['status'] as int,
      message: json['message'] as String,
      data: fromJsonT(json['data']),
    );
  }
}

/// Mirrors `backend/app/utils/api_response.py::PaginatedResponse[T]`.
class PaginatedResponse<T> {
  final int skip;
  final int limit;
  final int total;
  final List<T> items;

  PaginatedResponse({
    required this.skip,
    required this.limit,
    required this.total,
    required this.items,
  });

  factory PaginatedResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Object?) itemFromJson,
  ) {
    return PaginatedResponse<T>(
      skip: json['skip'] as int,
      limit: json['limit'] as int,
      total: json['total'] as int,
      items: (json['items'] as List<dynamic>).map(itemFromJson).toList(),
    );
  }
}

/// Body shape produced by the FastAPI exception handlers in main.py.
/// `status` here is the literal string "error" — the HTTP code lives
/// in `code`. Helpful when bubbling messages up to the UI layer.
class ApiErrorBody {
  final String status;
  final int code;
  final String message;

  ApiErrorBody({
    required this.status,
    required this.code,
    required this.message,
  });

  factory ApiErrorBody.fromJson(Map<String, dynamic> json) {
    return ApiErrorBody(
      status: json['status'] as String? ?? 'error',
      code: json['code'] as int? ?? 0,
      message: json['message'] as String? ?? 'Unexpected error',
    );
  }
}
