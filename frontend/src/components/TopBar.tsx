import { RefreshCw } from "lucide-react";

interface TopBarProps {
  apiReady: boolean;
  refreshing: boolean;
  onRefresh: () => void;
}

export function TopBar({
  apiReady,
  refreshing,
  onRefresh,
}: TopBarProps) {
  return (
    <header className="sticky top-0 z-10 flex h-[61px] items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-[38px]">
      <div className="flex items-center gap-2.5 text-xs text-slate-400">
        <span>Workspace</span>
        <span className="text-slate-300">/</span>
        <strong className="font-semibold text-slate-600">Find roles</strong>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-[7px] text-[11px] text-slate-400">
          <span
            className={`h-[7px] w-[7px] rounded-full ${
              apiReady
                ? "bg-emerald-500 shadow-[0_0_0_3px_#e4f6ef]"
                : "bg-amber-500"
            }`}
          />
          {apiReady ? "API connected" : "API disconnected"}
        </div>
        <button
          className="grid h-[34px] w-[34px] place-items-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-indigo-200 hover:text-brand disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          onClick={onRefresh}
          aria-label="Refresh dashboard"
          title="Refresh dashboard"
          disabled={refreshing}
        >
          <RefreshCw
            size={17}
            className={refreshing ? "animate-spin" : undefined}
          />
        </button>
      </div>
    </header>
  );
}
