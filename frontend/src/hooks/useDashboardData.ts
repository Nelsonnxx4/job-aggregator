import { useCallback, useEffect, useState } from "react";

import { loadDashboardData, request } from "../api";
import type { DashboardData, IngestionAction } from "../types";

const ingestionActions: IngestionAction[] = [
  { name: "configured feeds", path: "/ingestion/feeds/run" },
  { name: "Arbeitnow", path: "/ingestion/arbeitnow/run" },
];

export function useDashboardData() {
  const [data, setData] = useState<DashboardData>({
    jobs: [],
    sources: [],
    runs: [],
    apiReady: false,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = useCallback(() => setReloadKey((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        setData(await loadDashboardData(controller.signal));
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError") {
          return;
        }
        setData((current) => ({ ...current, apiReady: false }));
        setError(
          cause instanceof Error ? cause.message : "Could not load dashboard.",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }, 100);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const runIngestion = useCallback(async () => {
    setRunning(true);
    setNotice(null);
    try {
      const results = await Promise.allSettled(
        ingestionActions.map((action) =>
          request<unknown>(action.path, { method: "POST" }),
        ),
      );
      const completed = results.filter(
        (result) => result.status === "fulfilled",
      ).length;
      const failedNames = results.flatMap((result, index) =>
        result.status === "rejected" ? [ingestionActions[index].name] : [],
      );

      if (failedNames.length > 0) {
        setNotice(
          `${completed} ingestion request${completed === 1 ? "" : "s"} completed. Failed: ${failedNames.join(", ")}.`,
        );
      } else {
        setNotice("Ingestion finished. Dashboard data refreshed.");
      }
    } finally {
      setRunning(false);
      setRefreshing(true);
      refresh();
    }
  }, [refresh]);

  const reload = useCallback(() => {
    setRefreshing(true);
    refresh();
  }, [refresh]);

  return {
    ...data,
    loading,
    refreshing,
    error,
    notice,
    running,
    dismissNotice: () => setNotice(null),
    runIngestion,
    reload,
  };
}
