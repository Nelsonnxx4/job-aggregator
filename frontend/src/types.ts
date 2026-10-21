export interface Job {
  id: number;
  title: string;
  company: string;
  url: string;
  source_id: number;
  external_id: string | null;
  location: string | null;
  description: string | null;
  employment_type: string | null;
  experience_level: string | null;
  remote_scope: string;
  remote_status: string;
  region: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  eligible_countries: string[];
  eligibility_confidence: string;
  eligibility_source: string | null;
  eligibility_reason: string | null;
  duplicate_of_id: number | null;
  created_at: string;
  relevance_score: number;
  eligibility: string;
  relevance_reasons: string[];
}

export interface JobSource {
  id: number;
  name: string;
  slug: string;
  base_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IngestionRun {
  id: number;
  source_id: number | null;
  source_slug: string;
  source_name: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  fetched: number;
  saved: number;
  skipped: number;
  duplicates: number;
  stale: number;
  failed: number;
  error_summary: string | null;
}

export type EligibilityFilter = "all" | "worldwide" | "emea" | "unknown";
export type SortOption = "relevance" | "date";

export interface DashboardData {
  jobs: Job[];
  sources: JobSource[];
  runs: IngestionRun[];
  apiReady: boolean;
}

export interface IngestionAction {
  name: string;
  path: string;
}
