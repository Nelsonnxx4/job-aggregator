import {
  ArrowDownWideNarrow,
  ChevronDown,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import type { ReactNode } from "react";
import type {
  EligibilityFilter,
  JobSource,
  SortOption,
} from "../types";

interface JobFiltersProps {
  query: string;
  onQueryChange: (query: string) => void;
  sourceFilter: string;
  onSourceChange: (sourceId: string) => void;
  sources: JobSource[];
  eligibilityFilter: EligibilityFilter;
  onEligibilityChange: (filter: EligibilityFilter) => void;
  minimumScore: number;
  onMinimumScoreChange: (score: number) => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
  onClear: () => void;
}

const eligibilityOptions: Array<[EligibilityFilter, string]> = [
  ["all", "All roles"],
  ["worldwide", "Worldwide"],
  ["emea", "EMEA"],
  ["unknown", "Unverified"],
];

export function JobFilters({
  query,
  onQueryChange,
  sourceFilter,
  onSourceChange,
  sources,
  eligibilityFilter,
  onEligibilityChange,
  minimumScore,
  onMinimumScoreChange,
  sortBy,
  onSortChange,
  onClear,
}: JobFiltersProps) {
  return (
    <>
      <div className="mt-[18px] flex h-[42px] items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 px-3 text-slate-400 focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-indigo-50">
        <Search size={18} />
        <label className="sr-only" htmlFor="job-search">
          Search jobs
        </label>
        <input
          id="job-search"
          className="w-full min-w-0 border-0 bg-transparent text-[11px] text-slate-700 outline-none placeholder:text-slate-400"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search roles, companies, or skills..."
        />
        <kbd className="hidden flex-none rounded border border-slate-200 bg-white px-1.5 py-0.5 font-sans text-[9px] text-slate-400 sm:block">
          ⌘ K
        </kbd>
      </div>

      <div className="mt-[15px] flex items-center justify-between gap-2.5">
        <div
          className="flex min-w-0 items-center gap-1 overflow-x-auto"
          role="group"
          aria-label="Filter by geographic eligibility"
        >
          {eligibilityOptions.map(([value, label]) => (
            <button
              className={`min-h-[30px] flex-none rounded-md border px-2.5 text-[9px] font-medium transition md:text-[10px] ${
                eligibilityFilter === value
                  ? "border-indigo-100 bg-indigo-50 font-bold text-brand"
                  : "border-transparent text-slate-500 hover:bg-slate-50"
              }`}
              type="button"
              key={value}
              onClick={() => onEligibilityChange(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          className="inline-flex flex-none items-center gap-1.5 border-0 bg-transparent px-0.5 py-1 text-[9px] text-slate-500 hover:text-brand md:text-[10px]"
          type="button"
          onClick={onClear}
        >
          <SlidersHorizontal size={15} />
          Reset
        </button>
      </div>

      <div className="mb-[15px] mt-2.5 flex flex-wrap items-center gap-1.5">
        <SelectWrap label="Filter by source">
          <select
            className="max-w-[160px]"
            value={sourceFilter}
            onChange={(event) => onSourceChange(event.target.value)}
          >
            <option value="all">Every source</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </SelectWrap>
        <SelectWrap label="Minimum match score">
          <select
            value={minimumScore}
            onChange={(event) =>
              onMinimumScoreChange(Number(event.target.value))
            }
          >
            <option value={0}>Any match</option>
            <option value={30}>Score 30+</option>
            <option value={50}>Score 50+</option>
            <option value={70}>Score 70+</option>
          </select>
        </SelectWrap>
        <SelectWrap label="Sort jobs by" className="ml-auto">
          <ArrowDownWideNarrow size={15} />
          <select
            className="max-w-[96px]"
            value={sortBy}
            onChange={(event) =>
              onSortChange(event.target.value as SortOption)
            }
          >
            <option value="relevance">Best match</option>
            <option value="date">Most recent</option>
          </select>
        </SelectWrap>
      </div>
    </>
  );
}

function SelectWrap({
  label,
  className = "",
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label
      className={`relative inline-flex min-h-[31px] items-center gap-1.5 rounded-md border border-slate-200 px-2 text-slate-500 ${className}`}
    >
      <span className="sr-only">{label}</span>
      {children}
      <ChevronDown
        className="pointer-events-none absolute right-[7px]"
        size={14}
      />
    </label>
  );
}
