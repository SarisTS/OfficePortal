import { useEffect, useState } from "react";

/**
 * Debounced text input. Local state mirrors keystrokes for snappy UX;
 * the parent's onChange fires after `delayMs` of inactivity. Reset
 * when `value` is changed externally (e.g. filter cleared).
 */
export function SearchInput({
  value,
  onChange,
  placeholder = "Search…",
  delayMs = 300,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  delayMs?: number;
}) {
  const [internal, setInternal] = useState(value);

  // External resets keep the input in sync.
  useEffect(() => {
    setInternal(value);
  }, [value]);

  // Debounce: only fire onChange after the user stops typing.
  useEffect(() => {
    if (internal === value) return;
    const handle = window.setTimeout(() => onChange(internal), delayMs);
    return () => window.clearTimeout(handle);
  }, [internal, value, delayMs, onChange]);

  return (
    <input
      type="search"
      value={internal}
      onChange={(e) => setInternal(e.target.value)}
      placeholder={placeholder}
      className="w-64 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
    />
  );
}
