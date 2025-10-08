import { GraphMetricsResponse } from "../services/api";

type GraphVisualizationProps = {
  metrics: GraphMetricsResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
};

export function GraphVisualization({ metrics, loading, error, onRefresh }: GraphVisualizationProps) {
  return (
    <section className="panel">
      <header className="panel__header">
        <h2>Graph Metrics</h2>
        <button type="button" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </header>
      <div className="panel__body">
        {loading && <p>Loading metrics…</p>}
        {error && <p className="error">{error}</p>}
        {!loading && metrics && (
          <div className="graph-metrics">
            <p>
              <strong>Nodes:</strong> {metrics.node_count}
            </p>
            <p>
              <strong>Relationships:</strong> {metrics.relationship_count}
            </p>
            <p>
              <strong>Average Degree:</strong> {metrics.average_degree.toFixed(2)}
            </p>
            <div>
              <h3>Labels</h3>
              <ul>
                {Object.entries(metrics.labels).map(([label, count]) => (
                  <li key={label}>
                    {label}: {count}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Relationship Types</h3>
              <ul>
                {Object.entries(metrics.relationship_types).map(([name, count]) => (
                  <li key={name}>
                    {name}: {count}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {!loading && !metrics && !error && <p>No metrics available yet.</p>}
      </div>
    </section>
  );
}
