import { RefreshCw, Sparkles } from "lucide-react";

interface WelcomeSectionProps {
  running: boolean;
  apiReady: boolean;
  onRunIngestion: () => void;
}

export function WelcomeSection({
  running,
  apiReady,
  onRunIngestion,
}: WelcomeSectionProps) {
  return (
    <section className="mb-7 flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
      <div>
        <div className="mb-3 flex items-center gap-[7px] text-[9px] font-bold tracking-[1.05px] text-indigo-500">
          <Sparkles size={14} />
          YOUR NEXT CHAPTER STARTS HERE
        </div>
        <h1 className="m-0 font-sans text-[25px] font-bold leading-tight tracking-tight text-slate-800 md:text-[32px]">
          Find work that works for you.
        </h1>
        <p className="mt-2 max-w-[480px] text-[11px] leading-relaxed text-slate-500 md:text-[13px]">
          Curated remote opportunities, matched to your skills and where you
          call home.
        </p>
      </div>
      <button
        className="inline-flex min-h-[42px] flex-none items-center justify-center gap-2 rounded-lg border border-brand bg-brand px-4 text-xs font-semibold text-white shadow-md shadow-brand/20 transition hover:border-brand-dark hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
        type="button"
        onClick={onRunIngestion}
        disabled={running || !apiReady}
      >
        <RefreshCw size={16} className={running ? "animate-spin" : undefined} />
        {running ? "Finding new roles..." : "Find new roles"}
      </button>
    </section>
  );
}
