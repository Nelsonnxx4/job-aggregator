import type { DashboardData, IngestionRun, Job, JobSource } from "./types";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "/api"
).replace(/\/$/, "");

export async function request<T>(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new Error("Could not reach the API. Check that the service is running.");
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof body.detail === "string"
      ) {
        message = body.detail;
      }
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function loadDashboardData(
  signal?: AbortSignal,
): Promise<DashboardData> {
  const [jobs, sources, runs, health] = await Promise.all([
    request<Job[]>("/jobs?days=30&sort_by=relevance&limit=100", {}, signal),
    request<JobSource[]>("/sources", {}, signal),
    request<IngestionRun[]>("/ingestion/runs?limit=100", {}, signal),
    request<{ status: string }>("/health", {}, signal),
  ]);

  return {
    jobs,
    sources,
    runs,
    apiReady: health.status === "healthy",
  };
}
