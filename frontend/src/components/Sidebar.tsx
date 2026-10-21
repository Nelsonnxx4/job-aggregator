import {
  BriefcaseBusiness,
  ChevronDown,
  Clock3,
  Command,
  Globe2,
} from "lucide-react";

interface SidebarProps {
  jobCount: number;
}

export function Sidebar({ jobCount }: SidebarProps) {
  return (
    <aside
      aria-label="Main navigation"
      className="fixed inset-x-0 bottom-0 z-20 flex h-[58px] items-center border-t border-slate-200 bg-white/95 px-3 backdrop-blur md:inset-y-0 md:right-auto md:h-auto md:w-[232px] md:flex-col md:items-stretch md:border-r md:border-t-0 md:px-4 md:pb-4 md:pt-7"
    >
      <a
        className="hidden items-center gap-2.5 px-2 text-ink no-underline md:flex"
        href="#"
        aria-label="Remote Roles dashboard"
      >
        <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-brand text-white">
          <Command size={19} strokeWidth={2.5} />
        </span>
        <span className="font-sans text-base font-extrabold tracking-tight">
          remote<span className="text-brand">roles</span>
        </span>
      </a>

      <div className="mb-3 ml-2 mt-12 hidden text-[10px] font-bold tracking-[1.05px] text-slate-400 md:block">
        WORKSPACE
      </div>
      <nav className="flex h-full w-full justify-around gap-1.5 md:h-auto md:flex-col md:justify-start md:gap-1">
        <a
          className="flex w-1/3 flex-col items-center justify-center gap-1 rounded-lg bg-indigo-50 px-2 py-1.5 text-[8px] font-bold text-brand md:h-[42px] md:w-full md:flex-row md:justify-start md:gap-[11px] md:px-2.5 md:py-0 md:text-[13px]"
          href="#jobs"
        >
          <BriefcaseBusiness size={17} />
          <span>Find roles</span>
          <span className="ml-auto hidden rounded-full bg-white px-[7px] py-0.5 text-[11px] text-brand md:inline">
            {jobCount}
          </span>
        </a>
        <a
          className="flex w-1/3 flex-col items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-[8px] font-medium text-slate-500 transition hover:bg-slate-50 md:h-[42px] md:w-full md:flex-row md:justify-start md:gap-[11px] md:px-2.5 md:py-0 md:text-[13px]"
          href="#sources"
        >
          <Globe2 size={17} />
          <span>Sources</span>
        </a>
        <a
          className="flex w-1/3 flex-col items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-[8px] font-medium text-slate-500 transition hover:bg-slate-50 md:h-[42px] md:w-full md:flex-row md:justify-start md:gap-[11px] md:px-2.5 md:py-0 md:text-[13px]"
          href="#activity"
        >
          <Clock3 size={17} />
          <span>Activity</span>
        </a>
      </nav>

      <div className="mt-auto hidden border-t border-slate-100 pt-3 md:block">
        <div className="flex items-center gap-2.5 px-2 py-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-full border border-indigo-100 bg-indigo-50 text-xs font-bold text-indigo-600">
            N
          </div>
          <div className="grid gap-0.5">
            <strong className="text-[11px] text-slate-700">Job seeker</strong>
            <span className="text-[10px] text-slate-400">Nigeria · EAT</span>
          </div>
          <ChevronDown size={15} className="ml-auto text-slate-400" />
        </div>
        <p className="ml-2 mt-1 text-[10px] text-slate-400">
          Made for your next move.
        </p>
      </div>
    </aside>
  );
}
