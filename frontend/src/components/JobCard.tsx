import {
  ArrowUpRight,
  BriefcaseBusiness,
  Clock3,
  Globe2,
  MapPin,
  Sparkles,
} from "lucide-react";

import { formatRelativeDate } from "../utils/date";
import { eligibilityLabels, getEligibilityClass } from "../utils/jobs";
import type { Job, JobSource } from "../types";

interface JobCardProps {
  job: Job;
  source?: JobSource;
  onOpen: () => void;
}

export function JobCard({ job, source, onOpen }: JobCardProps) {
  const firstReason = job.relevance_reasons[0];
  const skillReason = job.relevance_reasons.find((reason) =>
    reason.startsWith("Matching technologies:"),
  );
  const skills = skillReason
    ? skillReason.replace("Matching technologies: ", "").split(", ").slice(0, 3)
    : [];

  return (
    <article className="rounded-[9px] border border-slate-200 bg-white px-3 pt-3.5 transition hover:-translate-y-px hover:border-indigo-100 hover:shadow-elevated md:px-[15px]">
      <div className="flex items-start gap-2.5">
        <div className="grid h-9 w-9 flex-none place-items-center rounded-[9px] border border-slate-200 bg-slate-50 font-sans text-sm font-bold text-slate-500">
          {job.company.trim().slice(0, 1).toUpperCase() || "?"}
        </div>
        <div className="min-w-0 pt-px">
          <button
            className="block max-w-full overflow-hidden text-ellipsis whitespace-nowrap border-0 bg-transparent p-0 text-left font-sans text-[11px] font-bold text-slate-800 hover:text-brand md:text-[13px]"
            type="button"
            onClick={onOpen}
          >
            {job.title}
          </button>
          <div className="mt-1 flex items-center gap-1.5 text-[9px] text-slate-500 md:text-[10px]">
            <span>{job.company}</span>
            <span className="text-slate-300">·</span>
            {source?.base_url ? (
              <a
                className="text-indigo-600 underline-offset-2 hover:underline"
                href={source.base_url}
                target="_blank"
                rel="noreferrer"
              >
                {source.name}
              </a>
            ) : (
              <span>{source?.name ?? "Job source"}</span>
            )}
          </div>
        </div>
        <div
          className="ml-auto inline-flex h-6 min-w-[41px] flex-none items-center justify-center gap-1 rounded-md border border-indigo-100 bg-indigo-50 px-1.5 text-[10px] font-bold text-indigo-600"
          title="Heuristic relevance score"
        >
          <Sparkles size={13} />
          {job.relevance_score}
        </div>
      </div>

      <div className="my-3 flex flex-wrap gap-x-3 gap-y-2 text-[9px] text-slate-500 md:text-[10px]">
        <span className="inline-flex items-center gap-[5px]">
          <MapPin size={14} className="text-slate-400" />
          {job.location || "Location not specified"}
        </span>
        <span className="inline-flex items-center gap-[5px]">
          <Clock3 size={14} className="text-slate-400" />
          {formatRelativeDate(job.posted_at)}
        </span>
        {job.employment_type && (
          <span className="inline-flex items-center gap-[5px]">
            <BriefcaseBusiness size={14} className="text-slate-400" />
            {job.employment_type}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span
          className={`inline-flex min-h-[23px] items-center gap-1 rounded-md border px-[7px] text-[9px] font-semibold ${eligibilityBadgeClass(job.eligibility)}`}
        >
          <Globe2 size={13} />
          {eligibilityLabels[job.eligibility] ?? job.eligibility}
        </span>
        {job.eligibility_confidence !== "verified" &&
          job.eligibility !== "unknown" && (
            <span className="inline-flex min-h-[23px] items-center rounded-md border border-amber-100 bg-amber-50 px-[7px] text-[9px] font-semibold text-amber-800">
              Inferred · verify
            </span>
          )}
        {skills.map((skill) => (
          <span
            className="inline-flex min-h-[22px] items-center rounded-md border border-slate-200 bg-slate-50 px-[7px] text-[9px] text-slate-500"
            key={skill}
          >
            {skill}
          </span>
        ))}
      </div>
      {firstReason && (
        <p className="mt-2.5 overflow-hidden text-ellipsis whitespace-nowrap text-[9px] text-slate-400">
          {firstReason}
        </p>
      )}
      <div className="mt-3 flex items-center justify-between border-t border-slate-100 py-[9px] text-[9px] text-slate-400">
        <span>
          {job.remote_status === "remote"
            ? "Remote"
            : job.remote_status === "hybrid"
              ? "Hybrid"
              : "Work mode unverified"}
        </span>
        <button
          className="inline-flex items-center gap-1 border-0 bg-transparent py-[3px] text-[10px] font-semibold text-indigo-600 hover:text-brand-dark"
          type="button"
          onClick={onOpen}
        >
          View details <ArrowUpRight size={15} />
        </button>
      </div>
    </article>
  );
}

function eligibilityBadgeClass(value: string): string {
  const classes: Record<string, string> = {
    worldwide: "border-emerald-100 bg-emerald-50 text-emerald-700",
    emea: "border-indigo-100 bg-indigo-50 text-indigo-700",
    unknown: "border-amber-100 bg-amber-50 text-amber-800",
    restricted: "border-orange-100 bg-orange-50 text-orange-800",
  };
  return classes[getEligibilityClass(value)] ?? classes.restricted;
}
