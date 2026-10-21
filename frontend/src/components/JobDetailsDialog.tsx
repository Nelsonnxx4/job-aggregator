import { useEffect } from "react";
import { Clock3, ExternalLink, Globe2, MapPin, X } from "lucide-react";

import { formatRelativeDate } from "../utils/date";
import { eligibilityLabels } from "../utils/jobs";
import type { Job, JobSource } from "../types";

interface JobDetailsDialogProps {
  job: Job;
  source?: JobSource;
  onClose: () => void;
}

export function JobDetailsDialog({
  job,
  source,
  onClose,
}: JobDetailsDialogProps) {
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-900/50 p-6 backdrop-blur-[3px] max-[650px]:items-end max-[650px]:p-0"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="max-h-[90vh] w-full max-w-[540px] overflow-y-auto rounded-[13px] border border-slate-200 bg-white p-[22px] shadow-2xl max-[650px]:max-h-[88vh] max-[650px]:rounded-b-none max-[650px]:rounded-t-[14px] max-[650px]:px-4 max-[650px]:pb-6 max-[650px]:pt-[18px]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
      >
        <div className="mb-[19px] flex items-center justify-between">
          <span className="text-[10px] font-bold tracking-[1.05px] text-slate-400">
            OPPORTUNITY DETAILS
          </span>
          <button
            className="grid h-[34px] w-[34px] place-items-center rounded-lg border border-slate-200 bg-white text-slate-500"
            type="button"
            onClick={onClose}
            aria-label="Close job details"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className="grid h-[45px] w-[45px] flex-none place-items-center rounded-[9px] border border-slate-200 bg-slate-50 font-sans text-[17px] font-bold text-slate-500">
            {job.company.trim().slice(0, 1).toUpperCase() || "?"}
          </div>
          <div>
            <h2
              className="m-0 font-sans text-base font-bold tracking-tight text-slate-800 md:text-[19px]"
              id="dialog-title"
            >
              {job.title}
            </h2>
            <p className="mt-1 text-xs text-slate-500">{job.company}</p>
          </div>
        </div>
        <div className="my-[17px] flex flex-wrap gap-3 border-y border-slate-100 py-3 text-[10px] text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <MapPin size={15} className="text-slate-400" />
            {job.location || "Location not specified"}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Globe2 size={15} className="text-slate-400" />
            {eligibilityLabels[job.eligibility] ?? job.eligibility}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Clock3 size={15} className="text-slate-400" />
            Posted {formatRelativeDate(job.posted_at).toLowerCase()}
          </span>
        </div>
        {job.eligibility_reason && (
          <div className="grid gap-[5px] rounded-md border border-amber-100 bg-amber-50 p-3">
            <strong className="text-[10px] text-amber-900">
              Eligibility{" "}
              {job.eligibility_confidence === "verified"
                ? "verified"
                : "is not verified"}
            </strong>
            <span className="text-[10px] leading-relaxed text-amber-800">
              {job.eligibility_reason}
            </span>
          </div>
        )}
        {job.description && (
          <div className="mt-[18px]">
            <h3 className="mb-[7px] font-sans text-xs font-bold text-slate-600">
              About this role
            </h3>
            <p className="m-0 max-h-[210px] overflow-y-auto whitespace-pre-line text-[11px] leading-[1.7] text-slate-500">
              {job.description}
            </p>
          </div>
        )}
        <div className="my-[18px] flex justify-between gap-3 text-[9px] text-slate-400">
          <span>Found on {source?.name ?? "job board"}</span>
          <span>Match score {job.relevance_score}/100</span>
        </div>
        <a
          className="inline-flex min-h-[42px] w-full items-center justify-center gap-2 rounded-lg border border-brand bg-brand px-4 text-xs font-semibold text-white hover:bg-brand-dark"
          href={job.url}
          target="_blank"
          rel="noreferrer"
        >
          View original listing <ExternalLink size={16} />
        </a>
      </section>
    </div>
  );
}
