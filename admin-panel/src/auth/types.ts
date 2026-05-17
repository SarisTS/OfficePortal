/**
 * Mirrors the relevant subset of `app/models/employee.py::UserTypes`.
 * The backend's `/auth/me` response is typed against this in
 * src/auth/AuthContext.
 */
export type UserType =
  | "super_admin"
  | "office_admin"
  | "staff"
  | "employee";

/**
 * Subset of EmployeeResponse the admin panel cares about. Add fields as
 * features need them — keep this lean so the auth context doesn't carry
 * the full HR record around.
 */
export interface AuthenticatedUser {
  id: number;
  name: string;
  email: string | null;
  user_type: UserType;
  company_id: number | null;
  role_id: number;
  is_active?: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponseData {
  token_type: "bearer";
  access_token: string;
}
