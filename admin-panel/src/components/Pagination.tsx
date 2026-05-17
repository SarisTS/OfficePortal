/**
 * Skip/limit pagination matching the backend's PaginatedResponse[T].
 * Renders "X–Y of N" and prev/next buttons. No page-number list — keep
 * the surface tiny until a feature needs jump-to-page.
 */
export function Pagination({
  skip,
  limit,
  total,
  onPageChange,
}: {
  skip: number;
  limit: number;
  total: number;
  onPageChange: (nextSkip: number) => void;
}) {
  const start = total === 0 ? 0 : skip + 1;
  const end = Math.min(skip + limit, total);
  const hasPrev = skip > 0;
  const hasNext = end < total;

  return (
    <div className="flex items-center justify-between text-sm text-slate-600">
      <span>
        {total === 0
          ? "0 of 0"
          : `${start.toLocaleString()}–${end.toLocaleString()} of ${total.toLocaleString()}`}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!hasPrev}
          onClick={() => onPageChange(Math.max(0, skip - limit))}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={!hasNext}
          onClick={() => onPageChange(skip + limit)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}
