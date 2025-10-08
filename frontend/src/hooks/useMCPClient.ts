import { useCallback, useEffect, useMemo, useState } from "react";
import { getHealth, getMetrics, GraphMetricsResponse } from "../services/api";

type HealthState = {
  service: string;
  neo4j: boolean;
  timestamp: string;
};

export function useMCPClient(pollIntervalMs = 10000) {
  const [metrics, setMetrics] = useState<GraphMetricsResponse | null>(null);
  const [health, setHealth] = useState<HealthState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const [metricsPayload, healthPayload] = await Promise.all([
        getMetrics(),
        getHealth(),
      ]);
      setMetrics(metricsPayload);
      setHealth(healthPayload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => {
      void refresh();
    }, pollIntervalMs);
    return () => window.clearInterval(interval);
  }, [pollIntervalMs, refresh]);

  return useMemo(
    () => ({ metrics, health, refresh, loading, error }),
    [metrics, health, refresh, loading, error]
  );
}

export type UseMCPClientReturn = ReturnType<typeof useMCPClient>;
