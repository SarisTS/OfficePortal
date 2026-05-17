import { useEffect, useState } from "react";

/**
 * Debounced text input. Local state mirrors keystrokes for snappy UX;
 * the parent's onChange fires after `delayMs` of inactivity.
 *
 * Prop-sync: when the parent passes a new `value` (e.g. filters
 * cleared), React 19's conditional-setState-during-render pattern
 * resyncs `internal` without a useEffect.
 *
 * Debounce: scheduled via setTimeout inside a useEffect. The
 * setState happens asynchronously in the timer callback — outside
 * the effect body — so it doesn't trip set-state-in-effect.
 * `onChange` is included in deps; its identity stays stable during
 * typing bursts because typing only mutates this component's local
 * state, not the parent's.
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
  const [lastSeenValue, setLastSeenValue] = useState(value);

  if (value !== lastSeenValue) {
    setLastSeenValue(value);
    setInternal(value);
  }

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
