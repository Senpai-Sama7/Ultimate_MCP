import { ChangeEvent } from "react";

type ToolPanelProps = {
  onRunTests: () => void;
  onGenerate: () => void;
  onGraphUpsert: () => void;
  onGraphQuery: () => void;
  token: string;
  onTokenChange: (token: string) => void;
  template: string;
  onTemplateChange: (value: string) => void;
  templateContext: string;
  onTemplateContextChange: (value: string) => void;
  graphNodes: string;
  onGraphNodesChange: (value: string) => void;
  graphRelationships: string;
  onGraphRelationshipsChange: (value: string) => void;
  graphQuery: string;
  onGraphQueryChange: (value: string) => void;
  disableActions?: boolean;
};

export function ToolPanel({
  onRunTests,
  onGenerate,
  onGraphUpsert,
  onGraphQuery,
  token,
  onTokenChange,
  template,
  onTemplateChange,
  templateContext,
  onTemplateContextChange,
  graphNodes,
  onGraphNodesChange,
  graphRelationships,
  onGraphRelationshipsChange,
  graphQuery,
  onGraphQueryChange,
  disableActions = false,
}: ToolPanelProps) {
  const handleChange = (handler: (value: string) => void) =>
    (event: ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => handler(event.target.value);

  return (
    <section className="panel">
      <header className="panel__header">
        <h2>Tool Controls</h2>
        <label>
          Auth Token
          <input
            type="password"
            value={token}
            onChange={handleChange(onTokenChange)}
            placeholder="Optional bearer token"
          />
        </label>
      </header>
      <div className="panel__body panel__body--vertical">
        <div className="panel__row">
          <h3>Testing</h3>
          <button type="button" onClick={onRunTests} disabled={disableActions}>
            Run Tests
          </button>
        </div>

        <div className="panel__row">
          <h3>Code Generation</h3>
          <textarea
            value={template}
            onChange={handleChange(onTemplateChange)}
            rows={4}
            aria-label="Generation template"
          />
          <textarea
            value={templateContext}
            onChange={handleChange(onTemplateContextChange)}
            rows={4}
            aria-label="Generation context as JSON"
          />
          <button type="button" onClick={onGenerate} disabled={disableActions}>
            Generate Code
          </button>
        </div>

        <div className="panel__row">
          <h3>Graph Upsert</h3>
          <textarea
            value={graphNodes}
            onChange={handleChange(onGraphNodesChange)}
            rows={4}
            aria-label="Graph nodes JSON"
          />
          <textarea
            value={graphRelationships}
            onChange={handleChange(onGraphRelationshipsChange)}
            rows={4}
            aria-label="Graph relationships JSON"
          />
          <button type="button" onClick={onGraphUpsert} disabled={disableActions}>
            Upsert Graph
          </button>
        </div>

        <div className="panel__row">
          <h3>Graph Query</h3>
          <textarea
            value={graphQuery}
            onChange={handleChange(onGraphQueryChange)}
            rows={3}
            aria-label="Cypher query"
          />
          <button type="button" onClick={onGraphQuery} disabled={disableActions}>
            Run Query
          </button>
        </div>
      </div>
    </section>
  );
}
