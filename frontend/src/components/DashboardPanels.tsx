import {
  ArrowUpRight,
  Clock3,
  MapPin,
  Sparkles,
} from "lucide-react";

import { formatTime } from "../utils/date";
import { getRunForSource } from "../utils/jobs";
import type { IngestionRun, JobSource } from "../types";

interface DashboardPanelsProps {
  sources: JobSource[];
  runs: IngestionRun[];
  loading: boolean;
  activeSources: number;
}

export function DashboardPanels({
  sources,
  runs,
  loading,
  activeSources,
}: DashboardPanelsProps) {
  return (
    <aside className="grid content-start gap-3.5">
      <section className="rounded-[10px] border border-indigo-100 bg-indigo-50/70 p-4">
        <div className="mb-2.5 flex items-center gap-2">
          <span className="grid h-[34px] w-[34px] place-items-center rounded-lg bg-white text-indigo-500">
            <MapPin size={18} />
          </span>
          <div className="grid gap-0.5">
            <span className="text-[8px] font-bold tracking-[.9px] text-indigo-400">
              YOUR SEARCH REGION
            </span>
            <strong className="text-xs text-slate-800">Nigeria &amp; EMEA</strong>
          </div>
        </div>
        <p className="m-0 text-[10px] leading-relaxed text-slate-500">
          Roles marked worldwide or EMEA are highlighted. Always confirm
          location eligibility on the original listing.
        </p>
        <div className="mt-3 flex gap-1.5">
          {["Nigeria", "Africa", "EMEA"].map((region) => (
            <span
              className="rounded-md border border-indigo-100 bg-white px-2 py-1 text-[9px] text-indigo-600"
              key={region}
            >
              {region}
            </span>
          ))}
        </div>
      </section>

      <section
        className="rounded-[10px] border border-slate-200 bg-white p-3.5 shadow-card"
        id="sources"
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-[8px] font-bold tracking-[.9px] text-indigo-500">
              CONNECTED
            </div>
            <h3 className="mb-0 mt-1 font-sans text-[13px] font-bold text-slate-800">
              Job sources
            </h3>
          </div>
          <span className="text-[9px] text-slate-400">{activeSources} active</span>
        </div>
        {sources.length === 0 && !loading ? (
          <p className="my-4 text-center text-[10px] text-slate-400">
            No sources have run yet.
          </p>
        ) : (
          <ul className="m-0 grid list-none gap-2.5 p-0">
            {sources.map((source) => {
              const lastRun = getRunForSource(source, runs);
              return (
                <li className="flex items-center gap-2" key={source.id}>
                  <span className="grid h-[29px] w-[29px] flex-none place-items-center rounded-lg border border-slate-200 bg-slate-50 text-[10px] font-bold text-slate-500">
                    {source.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="grid min-w-0 flex-1 gap-0.5">
                    {source.base_url ? (
                      <a
                        className="overflow-hidden text-ellipsis whitespace-nowrap text-[10px] font-bold text-slate-700 underline-offset-2 hover:text-brand hover:underline"
                        href={source.base_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {source.name}
                      </a>
                    ) : (
                      <strong className="overflow-hidden text-ellipsis whitespace-nowrap text-[10px] text-slate-700">
                        {source.name}
                      </strong>
                    )}
                    <span className="text-[8px] text-slate-400">
                      {lastRun
                        ? `${formatTime(lastRun.finished_at)} · ${lastRun.status}`
                        : "Waiting for first run"}
                    </span>
                  </span>
                  <span
                    className={`h-[7px] w-[7px] rounded-full ${
                      source.is_active ? "bg-emerald-500" : "bg-slate-300"
                    }`}
                    aria-label={source.is_active ? "Active" : "Inactive"}
                    title={source.is_active ? "Active" : "Inactive"}
                  />
                </li>
              );
            })}
          </ul>
        )}
        <a
          className="mt-3 inline-flex items-center gap-1 text-[9px] font-semibold text-indigo-600 hover:text-indigo-800"
          href="#activity"
        >
          View source activity <ArrowUpRight size={14} />
        </a>
      </section>

      <section
        className="rounded-[10px] border border-slate-200 bg-white p-3.5 shadow-card"
        id="activity"
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-[8px] font-bold tracking-[.9px] text-indigo-500">
              WHAT’S HAPPENING
            </div>
            <h3 className="mb-0 mt-1 font-sans text-[13px] font-bold text-slate-800">
              Recent activity
            </h3>
          </div>
          <Clock3 size={17} className="text-slate-400" />
        </div>
        {runs.length === 0 ? (
          <div className="grid justify-items-center gap-2 py-4 text-center">
            <span className="grid h-[34px] w-[34px] place-items-center rounded-full bg-slate-50 text-slate-400">
              <Clock3 size={17} />
            </span>
            <p className="m-0 text-[9px] text-slate-400">
              Your first collection run will show up here.
            </p>
          </div>
        ) : (
          <ul className="m-0 grid list-none gap-3 p-0">
            {runs.slice(0, 4).map((run) => (
              <li className="flex items-center gap-2" key={run.id}>
                <span
                  className={`h-2 w-2 flex-none rounded-full ${
                    run.status === "completed"
                      ? "bg-emerald-500"
                      : run.status === "failed"
                        ? "bg-red-500"
                        : "bg-amber-400"
                  }`}
                />
                <span className="grid min-w-0 flex-1 gap-0.5">
                  <strong className="overflow-hidden text-ellipsis whitespace-nowrap text-[9px] text-slate-700">
                    {run.source_name}
                  </strong>
                  <span className="text-[8px] text-slate-400">
                    {run.status === "completed"
                      ? `${run.saved} new · ${run.duplicates} duplicates`
                      : run.status}
                  </span>
                </span>
                <time className="flex-none text-[8px] text-slate-400">
                  {formatTime(run.finished_at ?? run.started_at)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex gap-2.5 rounded-[10px] border border-amber-100 bg-amber-50 p-3">
        <Sparkles className="mt-0.5 flex-none text-amber-500" size={15} />
        <p className="m-0 text-[9px] leading-relaxed text-amber-900">
          <strong className="block">A quick tip</strong>
          Use the match score to spot roles that mention your skills and
          experience.
        </p>
      </section>
    </aside>
  );
}
