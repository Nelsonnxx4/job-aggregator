import { Check, X } from "lucide-react";

interface StatusMessagesProps {
  notice: string | null;
  error: string | null;
  onDismissNotice: () => void;
  onRetry: () => void;
}

export function StatusMessages({
  notice,
  error,
  onDismissNotice,
  onRetry,
}: StatusMessagesProps) {
  return (
    <>
      {notice && (
        <div
          className="mb-5 -mt-2.5 flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-700"
          role="status"
        >
          <Check size={16} />
          <span className="flex-1">{notice}</span>
          <button
            className="grid h-[26px] w-[26px] place-items-center rounded-md text-emerald-700 hover:bg-emerald-100"
            type="button"
            onClick={onDismissNotice}
            aria-label="Dismiss message"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {error && (
        <div
          className="mb-5 -mt-2.5 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-800"
          role="alert"
        >
          <div className="grid gap-1">
            <strong>Couldn’t load the dashboard</strong>
            <span className="text-[11px] text-red-700">{error}</span>
          </div>
          <button
            className="min-h-[31px] rounded-md border border-slate-200 bg-white px-2.5 text-[10px] font-semibold text-slate-600 hover:border-indigo-200 hover:text-brand"
            type="button"
            onClick={onRetry}
          >
            Try again
          </button>
        </div>
      )}
    </>
  );
}
