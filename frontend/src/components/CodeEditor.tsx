import { FormEvent } from "react";

type CodeEditorProps = {
  code: string;
  language: string;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: string) => void;
  onLint: () => void;
  onExecute: () => void;
  disableActions?: boolean;
};

export function CodeEditor({
  code,
  language,
  onCodeChange,
  onLanguageChange,
  onLint,
  onExecute,
  disableActions = false,
}: CodeEditorProps) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onLint();
  };

  return (
    <section className="panel">
      <header className="panel__header">
        <h2>Source Editor</h2>
        <div className="panel__controls">
          <label>
            Language
            <select
              value={language}
              onChange={(event) => onLanguageChange(event.target.value)}
            >
              <option value="python">Python</option>
            </select>
          </label>
          <button type="button" onClick={onLint} disabled={disableActions}>
            Lint
          </button>
          <button type="button" onClick={onExecute} disabled={disableActions}>
            Execute
          </button>
        </div>
      </header>
      <form onSubmit={handleSubmit} className="panel__body">
        <textarea
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          spellCheck={false}
          className="code-editor"
          aria-label="Code editor"
        />
      </form>
    </section>
  );
}
