import { useMemo, useState } from "react";

import type { EligibilityFilter, Job, SortOption } from "../types";

export function useJobFilters(jobs: Job[]) {
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [eligibilityFilter, setEligibilityFilter] =
    useState<EligibilityFilter>("all");
  const [minimumScore, setMinimumScore] = useState(0);
  const [sortBy, setSortBy] = useState<SortOption>("relevance");

  const filteredJobs = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const filtered = jobs.filter((job) => {
      const text = [
        job.title,
        job.company,
        job.location,
        job.description,
        ...job.relevance_reasons,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();

      return (
        (!normalizedQuery || text.includes(normalizedQuery)) &&
        (sourceFilter === "all" || job.source_id === Number(sourceFilter)) &&
        (eligibilityFilter === "all" ||
          job.eligibility === eligibilityFilter) &&
        job.relevance_score >= minimumScore
      );
    });

    return filtered.sort((first, second) => {
      if (sortBy === "relevance") {
        return (
          second.relevance_score - first.relevance_score ||
          new Date(second.posted_at ?? 0).getTime() -
            new Date(first.posted_at ?? 0).getTime()
        );
      }
      return (
        new Date(second.posted_at ?? 0).getTime() -
        new Date(first.posted_at ?? 0).getTime()
      );
    });
  }, [
    eligibilityFilter,
    jobs,
    minimumScore,
    query,
    sortBy,
    sourceFilter,
  ]);

  const clearFilters = () => {
    setQuery("");
    setSourceFilter("all");
    setEligibilityFilter("all");
    setMinimumScore(0);
    setSortBy("relevance");
  };

  return {
    query,
    setQuery,
    sourceFilter,
    setSourceFilter,
    eligibilityFilter,
    setEligibilityFilter,
    minimumScore,
    setMinimumScore,
    sortBy,
    setSortBy,
    filteredJobs,
    clearFilters,
  };
}
