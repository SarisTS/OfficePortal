import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { Badge } from "@/components/Badge";
import { DataTable, type Column } from "@/components/DataTable";
import { Pagination } from "@/components/Pagination";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, LoadingState } from "@/components/StateViews";

import { useEmployees } from "../api";
import {
  EmployeesFilters,
  type EmployeesFiltersValue,
} from "../components/EmployeesFilters";
import type { Employee, EmployeeListParams } from "../types";

const PAGE_SIZE = 25;

const EMPTY_FILTERS: EmployeesFiltersValue = {
  q: "",
  user_type: "",
  is_active: "",
};

function formatUserType(t: Employee["user_type"]) {
  return t.replace("_", " ");
}

function userTypeVariant(t: Employee["user_type"]) {
  switch (t) {
    case "super_admin":
      return "info" as const;
    case "office_admin":
      return "info" as const;
    case "staff":
      return "neutral" as const;
    case "employee":
      return "neutral" as const;
  }
}

export function EmployeesListPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<EmployeesFiltersValue>(EMPTY_FILTERS);
  const [skip, setSkip] = useState(0);

  // Translate UI filter state into backend query params. Reset skip to
  // 0 whenever a filter narrows — the user expects to see the first
  // page of the new result set, not page 5 of the old one.
  const params: EmployeeListParams = useMemo(() => {
    return {
      skip,
      limit: PAGE_SIZE,
      q: filters.q || undefined,
      user_type: filters.user_type || undefined,
      is_active:
        filters.is_active === "" ? undefined : filters.is_active === "true",
    };
  }, [filters, skip]);

  function handleFilterChange(next: EmployeesFiltersValue) {
    setFilters(next);
    setSkip(0);
  }

  const { data, isLoading, isError, error, refetch, isFetching } =
    useEmployees(params);

  const columns: ReadonlyArray<Column<Employee>> = [
    {
      id: "roll_no",
      header: "Roll no",
      cell: (e) => (
        <span className="font-mono text-xs text-slate-600">
          {e.roll_no ?? "—"}
        </span>
      ),
    },
    {
      id: "name",
      header: "Name",
      cell: (e) => (
        <div>
          <p className="font-medium text-slate-900">{e.name}</p>
          {e.email && (
            <p className="text-xs text-slate-500">{e.email}</p>
          )}
        </div>
      ),
    },
    {
      id: "user_type",
      header: "Role",
      cell: (e) => (
        <Badge variant={userTypeVariant(e.user_type)}>
          {formatUserType(e.user_type)}
        </Badge>
      ),
    },
    {
      id: "department",
      header: "Department",
      cell: (e) => (
        <span className="text-slate-700">{e.department_name ?? "—"}</span>
      ),
    },
    {
      id: "mobile",
      header: "Mobile",
      cell: (e) => (
        <span className="text-slate-700">{e.mobile ?? "—"}</span>
      ),
    },
    {
      id: "is_active",
      header: "Status",
      cell: (e) =>
        e.is_active === false ? (
          <Badge variant="warning">Inactive</Badge>
        ) : (
          <Badge variant="success">Active</Badge>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Employees"
        description="Directory of every employee in your scope. Click a row for the full profile."
      />

      <EmployeesFilters value={filters} onChange={handleFilterChange} />

      {isLoading ? (
        <LoadingState label="Loading employees…" />
      ) : isError ? (
        <ErrorState
          message={getErrorMessage(error)}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="space-y-3">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(e) => e.id}
            onRowClick={(e) => navigate(`/employees/${e.id}`)}
            emptyMessage="No employees match these filters."
          />
          <Pagination
            skip={data?.skip ?? skip}
            limit={data?.limit ?? PAGE_SIZE}
            total={data?.total ?? 0}
            onPageChange={setSkip}
          />
          {isFetching && (
            <p className="text-xs text-slate-400">Refreshing…</p>
          )}
        </div>
      )}
    </div>
  );
}
