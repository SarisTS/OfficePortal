import type { UserType } from "@/auth/types";

/**
 * Mirrors backend/app/schemas/employee.py::EmployeeResponse. Keep this
 * field set in sync as the backend evolves — the Pydantic schema is
 * the source of truth.
 */
export interface Employee {
  id: number;
  roll_no: string | null;
  name: string;
  email: string | null;
  user_type: UserType;

  role_id: number;
  role_name: string | null;

  company_id: number | null;
  department_id: number | null;
  department_name: string | null;

  hostel_id: number | null;

  mobile: string | null;

  address_line_1: string | null;
  address_line_2: string | null;
  landmark: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;

  is_active: boolean | null;

  created_at: string;
  updated_at: string;
}

/**
 * Query params accepted by GET /employees/. Mirrors the FastAPI
 * signature in backend/app/routers/employee.py::get_all_employees.
 */
export interface EmployeeListParams {
  skip?: number;
  limit?: number;
  q?: string;
  department_id?: number;
  user_type?: UserType;
  is_active?: boolean;
}
