export interface SelectOption<V extends string> {
  value: V;
  label: string;
}

/**
 * Controlled native <select>. The "" empty value is treated as "no
 * selection" — keeps URL state simple.
 */
export function Select<V extends string>({
  value,
  onChange,
  options,
  placeholder = "All",
  ariaLabel,
}: {
  value: V | "";
  onChange: (next: V | "") => void;
  options: ReadonlyArray<SelectOption<V>>;
  placeholder?: string;
  ariaLabel?: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value as V | "")}
      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
