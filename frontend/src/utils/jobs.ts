import type { IngestionRun, JobSource } from "../types";

export const eligibilityLabels: Record<string, string> = {
  worldwide: "Worldwide",
  emea: "EMEA",
  region_restricted: "Region restricted",
  country_restricted: "Country restricted",
  non_remote: "Not remote",
  unknown: "Eligibility unknown",
};

export function getRunForSource(
  source: JobSource,
  runs: IngestionRun[],
): IngestionRun | undefined {
  return runs.find(
    (run) =>
      run.source_slug === source.slug ||
      (run.source_id !== null && run.source_id === source.id),
  );
}

export function getEligibilityClass(value: string): string {
  if (value === "worldwide") return "worldwide";
  if (value === "emea") return "emea";
  if (value === "unknown") return "unknown";
  return "restricted";
}
