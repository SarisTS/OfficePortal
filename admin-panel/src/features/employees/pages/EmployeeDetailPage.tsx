import { Link, useParams } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { Badge } from "@/components/Badge";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState, LoadingState } from "@/components/StateViews";

import { useEmployee } from "../api";
import type { Employee } from "../types";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fullAddress(e: Employee): string | null {
  const parts = [
    e.address_line_1,
    e.address_line_2,
    e.landmark,
    e.city,
    e.state,
    e.pincode,
  ].filter((p): p is string => Boolean(p));
  return parts.length === 0 ? null : parts.join(", ");
}

export function EmployeeDetailPage() {
  const { id: idParam } = useParams<{ id: string }>();
  const id = idParam ? Number(idParam) : undefined;
  const validId = id !== undefined && Number.isFinite(id);

  const { data: employee, isLoading, isError, error, refetch } =
    useEmployee(validId ? id : undefined);

  if (!validId) {
    return (
      <ErrorState message="Invalid employee id in the URL." />
    );
  }

  if (isLoading) return <LoadingState label="Loading employee…" />;
  if (isError) {
    return (
      <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
    );
  }
  if (!employee) {
    return <ErrorState message="Employee not found." />;
  }

  const address = fullAddress(employee);

  return (
    <div>
      <PageHeader
        title={employee.name}
        description={
          employee.roll_no
            ? `Roll no ${employee.roll_no}`
            : "No roll number assigned"
        }
        actions={
          <Link
            to="/employees"
            className="text-sm text-slate-500 underline hover:text-slate-700"
          >
            Back to list
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Section title="Identity">
          <Field label="Role">
            <Badge variant="info">
              {employee.user_type.replace("_", " ")}
            </Badge>
          </Field>
          <Field label="Status">
            {employee.is_active === false ? (
              <Badge variant="warning">Inactive</Badge>
            ) : (
              <Badge variant="success">Active</Badge>
            )}
          </Field>
          <Field label="Email">{employee.email ?? "—"}</Field>
          <Field label="Mobile">{employee.mobile ?? "—"}</Field>
        </Section>

        <Section title="Organisation">
          <Field label="Role name">{employee.role_name ?? "—"}</Field>
          <Field label="Department">
            {employee.department_name ?? "—"}
          </Field>
          <Field label="Company id">{employee.company_id ?? "—"}</Field>
          <Field label="Hostel id">{employee.hostel_id ?? "—"}</Field>
        </Section>

        <Section title="Address" className="md:col-span-2">
          {address ? (
            <p className="text-sm text-slate-700">{address}</p>
          ) : (
            <p className="text-sm text-slate-500">No address on file.</p>
          )}
        </Section>

        <Section title="Metadata" className="md:col-span-2">
          <Field label="Created">{formatDate(employee.created_at)}</Field>
          <Field label="Last updated">
            {formatDate(employee.updated_at)}
          </Field>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  className,
  children,
}: {
  title: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={
        "rounded-md border border-slate-200 bg-white p-4 " + (className ?? "")
      }
    >
      <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>
      <dl className="space-y-2 text-sm">{children}</dl>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-800 text-right">{children}</dd>
    </div>
  );
}
