import { useCallback, useMemo, useState } from "react";
import { CodeEditor } from "./components/CodeEditor";
import { GraphVisualization } from "./components/GraphVisualization";
import { StatusDisplay, StatusMessage } from "./components/StatusDisplay";
import { ToolPanel } from "./components/ToolPanel";
import {
  executeCode,
  generateCode,
  graphQuery,
  graphUpsert,
  lintCode,
  runTests,
} from "./services/api";
import { useMCPClient } from "./hooks/useMCPClient";

const INITIAL_CODE = `def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
`;

function createMessage(text: string, level: StatusMessage["level"]): StatusMessage {
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`;
  return {
    id,
    level,
    text,
    timestamp: new Date().toISOString(),
  };
}

function App() {
  const [code, setCode] = useState(INITIAL_CODE);
  const [language, setLanguage] = useState("python");
  const [token, setToken] = useState("");
  const [template, setTemplate] = useState("def {{ name }}():
    return {{ value }}
");
  const [templateContext, setTemplateContext] = useState('{"name": "answer", "value": 42}');
  const [graphNodes, setGraphNodes] = useState('[{"key":"App:1","labels":["Service"],"properties":{"name":"frontend"}}]');
  const [graphRelationships, setGraphRelationships] = useState('[{"start":"App:1","end":"App:1","type":"DEPENDS_ON","properties":{"weight":1}}]');
  const [graphQueryText, setGraphQueryText] = useState("MATCH (n) RETURN count(n) AS nodes");
  const [messages, setMessages] = useState<StatusMessage[]>([]);

  const pushMessage = useCallback((text: string, level: StatusMessage["level"]) => {
    setMessages((prev) => [createMessage(text, level), ...prev].slice(0, 50));
  }, []);

  const { metrics, health, refresh, loading, error } = useMCPClient();

  const authToken = useMemo(() => (token.trim() === "" ? undefined : token.trim()), [token]);

  const handleLint = useCallback(async () => {
    try {
      const result = await lintCode({ code, language });
      pushMessage(`Lint succeeded: complexity ${result.complexity.toFixed(2)}, functions ${result.functions.join(", ")}`, "info");
    } catch (err) {
      pushMessage(`Lint failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [code, language, pushMessage]);

  const handleExecute = useCallback(async () => {
    if (!authToken) {
      pushMessage("Auth token required for execution.", "error");
      return;
    }
    try {
      const result = await executeCode({ code, language }, authToken);
      pushMessage(`Execute (rc=${result.return_code}) stdout: ${result.stdout.trim()}`, "info");
    } catch (err) {
      pushMessage(`Execute failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [authToken, code, language, pushMessage]);

  const handleRunTests = useCallback(async () => {
    if (!authToken) {
      pushMessage("Auth token required for running tests.", "error");
      return;
    }
    try {
      const result = await runTests({ code, language }, authToken);
      pushMessage(`Tests completed (rc=${result.return_code})`, result.return_code === 0 ? "info" : "error");
    } catch (err) {
      pushMessage(`Tests failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [authToken, code, language, pushMessage]);

  const handleGenerate = useCallback(async () => {
    if (!authToken) {
      pushMessage("Auth token required for code generation.", "error");
      return;
    }
    try {
      const context = JSON.parse(templateContext) as Record<string, unknown>;
      const result = await generateCode(template, context, authToken);
      pushMessage(`Generated code:
${result.output}`, "info");
    } catch (err) {
      pushMessage(`Generation failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [authToken, template, templateContext, pushMessage]);

  const handleGraphUpsert = useCallback(async () => {
    if (!authToken) {
      pushMessage("Auth token required for graph mutations.", "error");
      return;
    }
    try {
      const nodes = JSON.parse(graphNodes);
      const relationships = JSON.parse(graphRelationships);
      const result = await graphUpsert({ nodes, relationships }, authToken);
      pushMessage(`Graph upsert ok. Nodes=${result.metrics.node_count} Relationships=${result.metrics.relationship_count}`, "info");
      await refresh();
    } catch (err) {
      pushMessage(`Graph upsert failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [authToken, graphNodes, graphRelationships, pushMessage, refresh]);

  const handleGraphQuery = useCallback(async () => {
    try {
      const result = await graphQuery(graphQueryText);
      pushMessage(`Graph query returned ${result.results.length} row(s)`, "info");
    } catch (err) {
      pushMessage(`Graph query failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  }, [graphQueryText, pushMessage]);

  return (
    <main>
      <CodeEditor
        code={code}
        language={language}
        onCodeChange={setCode}
        onLanguageChange={setLanguage}
        onLint={handleLint}
        onExecute={handleExecute}
      />
      <GraphVisualization metrics={metrics} loading={loading} error={error} onRefresh={refresh} />
      <ToolPanel
        onRunTests={handleRunTests}
        onGenerate={handleGenerate}
        onGraphUpsert={handleGraphUpsert}
        onGraphQuery={handleGraphQuery}
        token={token}
        onTokenChange={setToken}
        template={template}
        onTemplateChange={setTemplate}
        templateContext={templateContext}
        onTemplateContextChange={setTemplateContext}
        graphNodes={graphNodes}
        onGraphNodesChange={setGraphNodes}
        graphRelationships={graphRelationships}
        onGraphRelationshipsChange={setGraphRelationships}
        graphQuery={graphQueryText}
        onGraphQueryChange={setGraphQueryText}
      />
      <StatusDisplay messages={messages} />
      {health && (
        <div className="health-indicator">
          <span>Service: {health.service}</span>
          <span>Neo4j: {health.neo4j ? "online" : "offline"}</span>
          <span>{new Date(health.timestamp).toLocaleString()}</span>
        </div>
      )}
    </main>
  );
}

export default App;
