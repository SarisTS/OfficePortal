import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import type { ApiResponse, PaginatedResponse } from "@/api/types";

import type { Employee, EmployeeListParams } from "./types";

const KEYS = {
  all: ["employees"] as const,
  list: (params: EmployeeListParams) =>
    [...KEYS.all, "list", params] as const,
  detail: (id: number) => [...KEYS.all, "detail", id] as const,
};

async function fetchEmployees(
  params: EmployeeListParams,
): Promise<PaginatedResponse<Employee>> {
  const response = await apiClient.get<
    ApiResponse<PaginatedResponse<Employee>>
  >("/employees/", { params });
  return response.data.data;
}

async function fetchEmployee(id: number): Promise<Employee> {
  const response = await apiClient.get<ApiResponse<Employee>>(
    `/employees/${id}`,
  );
  return response.data.data;
}

export function useEmployees(params: EmployeeListParams) {
  return useQuery({
    queryKey: KEYS.list(params),
    queryFn: () => fetchEmployees(params),
    // Pagination metadata jitters as the user pages — keep the
    // previous page visible while the next one is fetched so the
    // table doesn't flash empty.
    placeholderData: (prev) => prev,
  });
}

export function useEmployee(id: number | undefined) {
  return useQuery({
    queryKey: id !== undefined ? KEYS.detail(id) : ["employees", "detail", "unset"],
    queryFn: () => fetchEmployee(id as number),
    enabled: id !== undefined,
  });
}

export const employeesQueryKeys = KEYS;
