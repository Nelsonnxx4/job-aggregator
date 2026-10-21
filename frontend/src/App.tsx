import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { DashboardPanels } from "./components/DashboardPanels";
import { JobCard } from "./components/JobCard";
import { JobDetailsDialog } from "./components/JobDetailsDialog";
import { JobFilters } from "./components/JobFilters";
import { Sidebar } from "./components/Sidebar";
import { StatsGrid } from "./components/StatsGrid";
import { StatusMessages } from "./components/StatusMessages";
import { TopBar } from "./components/TopBar";
import { WelcomeSection } from "./components/WelcomeSection";
import { useDashboardData } from "./hooks/useDashboardData";
import { useJobFilters } from "./hooks/useJobFilters";
import type { Job } from "./types";

function App() {
  const dashboard = useDashboardData();
  const filters = useJobFilters(dashboard.jobs);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const strongMatches = useMemo(
    () => dashboard.jobs.filter((job) => job.relevance_score >= 50).length,
    [dashboard.jobs],
  );
  const eligibleCount = useMemo(
    () =>
      dashboard.jobs.filter(
        (job) =>
          job.remote_status === "remote" &&
          (job.eligibility === "worldwide" || job.eligibility === "emea"),
      ).length,
    [dashboard.jobs],
  );
  const activeSources = useMemo(
    () => dashboard.sources.filter((source) => source.is_active).length,
    [dashboard.sources],
  );
  const selectedSource = selectedJob
    ? dashboard.sources.find((source) => source.id === selectedJob.source_id)
    : undefined;

  return (
    <div className="min-h-screen bg-slate-50 text-ink">
      <Sidebar jobCount={dashboard.jobs.length} />
      <main className="min-h-screen pb-[74px] md:ml-[232px] md:pb-0">
        <TopBar
          apiReady={dashboard.apiReady}
          refreshing={dashboard.loading || dashboard.refreshing}
          onRefresh={dashboard.reload}
        />

        <div className="mx-auto max-w-[1440px] px-4 pb-5 pt-6 md:px-[38px] md:pt-8">
          <WelcomeSection
            running={dashboard.running}
            apiReady={dashboard.apiReady}
            onRunIngestion={dashboard.runIngestion}
          />
          <StatsGrid
            loading={dashboard.loading}
            jobCount={dashboard.jobs.length}
            strongMatches={strongMatches}
            eligibleCount={eligibleCount}
            activeSources={activeSources}
          />

          <StatusMessages
            notice={dashboard.notice}
            error={dashboard.error}
            onDismissNotice={dashboard.dismissNotice}
            onRetry={dashboard.reload}
          />

          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_260px] xl:grid-cols-[minmax(0,1fr)_280px]">
            <section
              className="min-w-0 rounded-[10px] border border-slate-200 bg-white p-3 shadow-card md:p-4"
              id="jobs"
            >
              <div className="flex items-end justify-between gap-3">
                <div>
                  <div className="text-[9px] font-bold tracking-[1.05px] text-indigo-500">
                    THE LATEST
                  </div>
                  <h2 className="mb-0 mt-1 font-sans text-[15px] font-bold tracking-tight text-slate-800 md:text-[17px]">
                    Opportunities for you
                  </h2>
                </div>
                <span className="flex-none text-[9px] text-slate-400 md:text-[10px]">
                  {dashboard.loading
                    ? "Loading roles..."
                    : `${filters.filteredJobs.length} ${
                        filters.filteredJobs.length === 1 ? "role" : "roles"
                      }`}
                </span>
              </div>

              <JobFilters
                query={filters.query}
                onQueryChange={filters.setQuery}
                sourceFilter={filters.sourceFilter}
                onSourceChange={filters.setSourceFilter}
                sources={dashboard.sources}
                eligibilityFilter={filters.eligibilityFilter}
                onEligibilityChange={filters.setEligibilityFilter}
                minimumScore={filters.minimumScore}
                onMinimumScoreChange={filters.setMinimumScore}
                sortBy={filters.sortBy}
                onSortChange={filters.setSortBy}
                onClear={filters.clearFilters}
              />

              <div
                className="grid gap-2.5"
                aria-live="polite"
                aria-busy={dashboard.loading}
              >
                {dashboard.loading && dashboard.jobs.length === 0 ? (
                  <LoadingCards />
                ) : filters.filteredJobs.length > 0 ? (
                  filters.filteredJobs.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      source={dashboard.sources.find(
                        (source) => source.id === job.source_id,
                      )}
                      onOpen={() => setSelectedJob(job)}
                    />
                  ))
                ) : (
                  <EmptyState
                    hasJobs={dashboard.jobs.length > 0}
                    onReset={filters.clearFilters}
                  />
                )}
              </div>
            </section>

            <DashboardPanels
              sources={dashboard.sources}
              runs={dashboard.runs}
              loading={dashboard.loading}
              activeSources={activeSources}
            />
          </div>

          <footer className="flex flex-wrap justify-between gap-2 border-t border-slate-200 py-4 text-[9px] text-slate-400">
            <span>Remote Roles</span>
            <span>Job details always link to the original source.</span>
          </footer>
        </div>
      </main>

      {selectedJob && (
        <JobDetailsDialog
          job={selectedJob}
          source={selectedSource}
          onClose={() => setSelectedJob(null)}
        />
      )}
    </div>
  );
}

function LoadingCards() {
  return (
    <div className="grid gap-2.5" aria-label="Loading opportunities">
      {[0, 1, 2].map((item) => (
        <div
          className="grid min-h-[144px] animate-pulse gap-3 rounded-[9px] border border-slate-200 bg-white p-4"
          key={item}
        >
          <span className="h-4 w-2/3 rounded bg-slate-100" />
          <span className="h-3 w-1/2 rounded bg-slate-100" />
          <span className="h-3 w-3/4 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  hasJobs,
  onReset,
}: {
  hasJobs: boolean;
  onReset: () => void;
}) {
  return (
    <div className="grid justify-items-center rounded-[9px] border border-dashed border-slate-200 px-4 py-10 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-slate-50 text-slate-400">
        <Search size={20} />
      </span>
      <h3 className="mb-0 mt-3 font-sans text-xs font-bold text-slate-700">
        {hasJobs ? "No roles match those filters" : "No roles just yet"}
      </h3>
      <p className="mb-0 mt-1.5 max-w-[290px] text-[10px] leading-relaxed text-slate-400">
        {hasJobs
          ? "Try a different search or clear a few filters."
          : "Run a collection to look for recent opportunities."}
      </p>
      {hasJobs ? (
        <button
          className="mt-3 min-h-[32px] rounded-md border border-slate-200 bg-white px-3 text-[10px] font-semibold text-slate-600 hover:border-indigo-200 hover:text-brand"
          type="button"
          onClick={onReset}
        >
          Clear filters
        </button>
      ) : (
        <span className="mt-3 text-[9px] text-slate-400">
          New openings will appear here.
        </span>
      )}
    </div>
  );
}

export default App;
