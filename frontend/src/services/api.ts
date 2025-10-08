const BASE_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export interface LintPayload {
  code: string;
  language: string;
}

export interface ExecutionPayload {
  code: string;
  language: string;
  timeout_seconds?: number;
}

export interface TestPayload {
  code: string;
  language?: string;
  timeout_seconds?: number;
}

export interface GraphNodePayload {
  key: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface GraphRelationshipPayload {
  start: string;
  end: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphUpsertPayload {
  nodes: GraphNodePayload[];
  relationships?: GraphRelationshipPayload[];
}

export interface GraphMetricsResponse {
  node_count: number;
  relationship_count: number;
  labels: Record<string, number>;
  relationship_types: Record<string, number>;
  average_degree: number;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  return (await response.json()) as T;
}

export function lintCode(payload: LintPayload) {
  return request("/lint_code", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeCode(payload: ExecutionPayload, token?: string) {
  return request("/execute_code", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function runTests(payload: TestPayload, token?: string) {
  return request("/run_tests", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function graphUpsert(payload: GraphUpsertPayload, token?: string) {
  return request("/graph_upsert", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export function graphQuery(cypher: string, parameters?: Record<string, unknown>) {
  return request("/graph_query", {
    method: "POST",
    body: JSON.stringify({ cypher, parameters: parameters ?? {} }),
  });
}

export function generateCode(template: string, context: Record<string, unknown>, token?: string) {
  return request("/generate_code", {
    method: "POST",
    body: JSON.stringify({ template, context, language: "python" }),
  }, token);
}

export function getMetrics() {
  return request<GraphMetricsResponse>("/metrics", { method: "GET" });
}

export function getHealth() {
  return request<{ service: string; neo4j: boolean; timestamp: string }>("/health");
}
