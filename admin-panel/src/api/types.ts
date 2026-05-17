/**
 * Shape of every successful response from the FastAPI backend.
 * Mirrors `app/utils/api_response.py::ApiResponse[T]`.
 */
export interface ApiResponse<T = unknown> {
  status: number;
  message: string;
  data: T;
}

/** Mirrors `app/utils/api_response.py::PaginatedResponse[T]`. */
export interface PaginatedResponse<T> {
  skip: number;
  limit: number;
  total: number;
  items: T[];
}

/**
 * Shape of error responses produced by `main.py`'s exception handlers.
 * `status` is the literal string "error" here, NOT the HTTP code — the
 * code lives in `code`.
 */
export interface ApiErrorBody {
  status: "error";
  code: number;
  message: string;
}
