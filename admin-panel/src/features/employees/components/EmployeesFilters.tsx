import { SearchInput } from "@/components/SearchInput";
import { Select } from "@/components/Select";
import type { UserType } from "@/auth/types";

const USER_TYPE_OPTIONS = [
  { value: "super_admin", label: "Super admin" },
  { value: "office_admin", label: "Office admin" },
  { value: "staff", label: "Staff" },
  { value: "employee", label: "Employee" },
] as const satisfies ReadonlyArray<{ value: UserType; label: string }>;

const ACTIVE_OPTIONS = [
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
] as const;

type ActiveValue = (typeof ACTIVE_OPTIONS)[number]["value"];

export interface EmployeesFiltersValue {
  q: string;
  user_type: UserType | "";
  is_active: ActiveValue | "";
}

export function EmployeesFilters({
  value,
  onChange,
}: {
  value: EmployeesFiltersValue;
  onChange: (next: EmployeesFiltersValue) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 pb-4">
      <SearchInput
        value={value.q}
        onChange={(q) => onChange({ ...value, q })}
        placeholder="Search name, email, roll no, mobile…"
      />
      <Select<UserType>
        value={value.user_type}
        onChange={(user_type) => onChange({ ...value, user_type })}
        options={USER_TYPE_OPTIONS}
        placeholder="All roles"
        ariaLabel="Filter by user type"
      />
      <Select<ActiveValue>
        value={value.is_active}
        onChange={(is_active) => onChange({ ...value, is_active })}
        options={ACTIVE_OPTIONS}
        placeholder="Active + inactive"
        ariaLabel="Filter by active status"
      />
      {(value.q || value.user_type || value.is_active) && (
        <button
          type="button"
          onClick={() => onChange({ q: "", user_type: "", is_active: "" })}
          className="text-sm text-slate-500 underline hover:text-slate-700"
        >
          Clear
        </button>
      )}
    </div>
  );
}
