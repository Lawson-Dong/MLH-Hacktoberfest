import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Braces,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Code2,
  Copy,
  ExternalLink,
  FileCode2,
  FileJson,
  GitBranch,
  LoaderCircle,
  Play,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleAlert,
  Unplug,
  X,
} from "lucide-react";
import type {
  Contract,
  ContractRecord,
  Endpoint,
  Evidence,
  Mock,
  Scan,
} from "./types";
import { api, message, saveFile } from "./types";

export function Brand({ small = false }: { small?: boolean }) {
  return (
    <div className={`brand ${small ? "brand-small" : ""}`}>
      <span className="brand-mark">
        <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path
            d="M8 8v8a8 8 0 0 0 16 0V8M16 5v23M4 11l4-4 4 4m8 0 4-4 4 4M12 9l4-4 4 4"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {!small && (
        <span>
          Triton<span className="brand-light">Team</span>
          <span className="brand-dot">.</span>
        </span>
      )}
    </div>
  );
}

export function MethodBadge({ method }: { method: string }) {
  return (
    <span className={`method method-${method.toLowerCase()}`}>{method}</span>
  );
}
export function StatusBadge({
  status,
  mocked = false,
}: {
  status: Endpoint["status"];
  mocked?: boolean;
}) {
  return (
    <span className={`status status-${mocked ? "mock" : status}`}>
      <span className="status-dot" />
      {mocked
        ? "Mock ready"
        : status === "missing"
          ? "Missing route"
          : status === "mismatch"
            ? "Method mismatch"
            : "Route matched"}
    </span>
  );
}

export function DependencyMap({
  scan,
  onReview,
}: {
  scan: Scan;
  onReview: () => void;
}) {
  const healthy = scan.stats.review === 0;
  return (
    <section className="card map-card">
      <div className="card-heading">
        <h2>See the missing link</h2>
        <span className="eyebrow">DEPENDENCIES</span>
      </div>
      <div
        className="dependency-map"
        role="img"
        aria-label={`${scan.stats.calls} frontend API calls connect to ${scan.stats.routes} backend routes; ${scan.stats.review} need review.`}
      >
        <div className="map-grid" />
        <div className="map-node map-frontend">
          <span className="node-icon">
            <Code2 size={19} />
          </span>
          <span>
            <strong>Frontend</strong>
            <small>React components</small>
          </span>
          <span className="node-mini">{scan.stats.calls}</span>
        </div>
        <svg
          className="map-lines"
          viewBox="0 0 320 200"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            d="M160 39V79M160 121V161"
            stroke={healthy ? "#5f8a71" : "#d1876f"}
            strokeWidth="1.7"
            strokeDasharray="4 5"
          />
          <path
            d="m156 153 4 5 4-5"
            fill="none"
            stroke="#8e9b90"
            strokeWidth="1.5"
          />
        </svg>
        <div className={`map-gap ${healthy ? "map-gap-healthy" : ""}`}>
          {healthy ? <Check size={15} /> : <Unplug size={15} />}
          <span>
            {healthy
              ? "Routes connected"
              : `${scan.stats.review} interfaces need review`}
          </span>
        </div>
        <div className="map-node map-backend">
          <span className="node-icon backend-icon">
            <Terminal size={18} />
          </span>
          <span>
            <strong>Backend</strong>
            <small>FastAPI routes</small>
          </span>
          <span className="node-mini">{scan.stats.routes}</span>
        </div>
      </div>
      <div className="map-caption">
        <span className={`tiny-dot ${healthy ? "green" : "orange"}`} />
        <span>
          {healthy
            ? "Path and method checks passed"
            : "A small gap can slow the whole team."}
        </span>
      </div>
      <button className="text-button map-action" onClick={onReview}>
        {healthy ? "Explore the API calls" : "Review an interface"}
        <ArrowRight size={14} />
      </button>
    </section>
  );
}

function SourceEvidence({
  value,
  label,
}: {
  value: Evidence | null;
  label: string;
}) {
  return (
    <div className="source-evidence">
      <div className="source-label">
        <span>
          <FileCode2 size={14} />
          {label}
        </span>
        {value?.url && (
          <a href={value.url} target="_blank" rel="noreferrer">
            View on GitHub <ExternalLink size={12} />
          </a>
        )}
      </div>
      {value ? (
        <>
          <div className="source-file">
            {value.file}
            <span>:{value.line}</span>
          </div>
          <pre className="source-code">
            <code>{value.snippet}</code>
          </pre>
        </>
      ) : (
        <div className="source-empty">
          <Unplug size={22} />
          <strong>No supported route found</strong>
          <p>
            Review this API with your backend teammate. It may live in a
            separate service.
          </p>
        </div>
      )}
    </div>
  );
}

function CopyButton({
  value,
  label = "Copy",
}: {
  value: string;
  label?: string;
}) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => setState("idle"), 2200);
    return () => clearTimeout(timer);
  }, [state]);
  return (
    <button
      className="quiet-button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setState("copied");
        } catch {
          setState("error");
        }
      }}
      aria-label={label}
    >
      {state === "copied" ? <Check size={14} /> : <Copy size={14} />}
      <span>
        {state === "copied"
          ? "Copied"
          : state === "error"
            ? "Select to copy"
            : label}
      </span>
    </button>
  );
}

function Playground({ record }: { record: ContractRecord }) {
  const mock = record.mock!;
  const [running, setRunning] = useState(false);
  const [requestBody, setRequestBody] = useState(
    JSON.stringify(mock.request_example ?? {}, null, 2),
  );
  const [result, setResult] = useState<{
    status: number;
    ms: number;
    body: unknown;
  } | null>(null);
  const [error, setError] = useState("");
  const [file, setFile] = useState("mock_server.py");
  const [verifyText, setVerifyText] = useState(
    JSON.stringify(mock.response_example, null, 2),
  );
  const [verification, setVerification] = useState<{
    valid: boolean;
    errors: { path: string; message: string }[];
  } | null>(null);
  const [checking, setChecking] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const url = new URL(mock.url, window.location.origin).href;
  async function send() {
    setRunning(true);
    setError("");
    try {
      const body = record.draft.request_schema
        ? JSON.stringify(JSON.parse(requestBody))
        : undefined;
      const start = performance.now();
      const response = await fetch(mock.url, {
        method: mock.method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body,
      });
      const data = await response.json();
      setResult({
        status: response.status,
        ms: Math.round(performance.now() - start),
        body: data,
      });
      if (response.ok) {
        setVerifyText(JSON.stringify(data, null, 2));
        setVerification(null);
      }
    } catch (caught) {
      setError(message(caught));
    } finally {
      setRunning(false);
    }
  }
  async function download() {
    setDownloading(true);
    setError("");
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract: record.draft, approved: true }),
      });
      if (!response.ok)
        throw new Error(
          "Could not export this contract. Review its fields and try again.",
        );
      saveFile("tritonteam-mock.zip", await response.blob(), "application/zip");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setDownloading(false);
    }
  }
  return (
    <div className="playground-content">
      <div className="success-banner">
        <span className="success-icon">
          <CheckCheck size={20} />
        </span>
        <div>
          <strong>Your frontend can keep moving.</strong>
          <p>Contract accepted. This endpoint now returns synthetic data.</p>
        </div>
        <span className="tag green-tag">MOCK LIVE</span>
      </div>
      <div className="request-toolbar">
        <MethodBadge method={mock.method} />
        <input value={url} readOnly aria-label="Generated mock endpoint URL" />
        <CopyButton value={url} label="Copy URL" />
        <button className="button primary" disabled={running} onClick={send}>
          {running ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <Play size={14} />
          )}
          Send request
        </button>
      </div>
      {record.draft.request_schema && (
        <label className="editor-label">
          Request body
          <textarea
            className="json-editor short-editor"
            value={requestBody}
            onChange={(event) => setRequestBody(event.target.value)}
            spellCheck={false}
          />
        </label>
      )}
      {error && (
        <div role="alert" className="inline-error">
          <TriangleAlert size={15} />
          {error}
        </div>
      )}
      <div className="response-bar">
        <span>RESPONSE</span>
        {result ? (
          <span
            className={result.status < 300 ? "response-ok" : "response-error"}
          >
            {result.status} · {result.ms} ms
          </span>
        ) : (
          <span>Send a request to test your mock</span>
        )}
      </div>
      <pre className={`response-code ${!result ? "response-placeholder" : ""}`}>
        <code>
          {result
            ? JSON.stringify(result.body, null, 2)
            : "// Your response will appear here.\n// This is a real request to your generated mock."}
        </code>
      </pre>
      <div className="bundle-heading">
        <div>
          <h3>Two teammates. One agreement.</h3>
          <p>Frontend gets a mock. Backend gets a Pydantic starting point.</p>
        </div>
        <button
          className="button secondary"
          onClick={download}
          disabled={downloading}
        >
          {downloading ? (
            <LoaderCircle size={15} className="spin" />
          ) : (
            <ArrowDownToLine size={15} />
          )}
          Download bundle
        </button>
      </div>
      <div className="file-viewer">
        <div className="file-tabs">
          {mock.files
            .filter(
              (item) => !["requirements.txt", "README.md"].includes(item.name),
            )
            .map((item) => (
              <button
                key={item.name}
                className={file === item.name ? "active" : ""}
                onClick={() => setFile(item.name)}
              >
                {item.name.endsWith(".json") ? (
                  <FileJson size={13} />
                ) : (
                  <FileCode2 size={13} />
                )}
                <span>{item.name}</span>
              </button>
            ))}
          <CopyButton
            value={mock.files.find((item) => item.name === file)?.content || ""}
          />
        </div>
        <pre>
          <code>{mock.files.find((item) => item.name === file)?.content}</code>
        </pre>
      </div>
      <details className="verify-details">
        <summary>
          <ShieldCheck size={17} />
          <span>Check a real backend response against this contract</span>
          <ChevronDown size={15} />
        </summary>
        <div className="verify-body">
          <p>
            Paste the JSON returned by your backend. This checks its shape,
            fields and types; business behavior still needs integration tests.
          </p>
          <textarea
            aria-label="Backend JSON response to validate"
            className="json-editor short-editor"
            value={verifyText}
            onChange={(event) => {
              setVerifyText(event.target.value);
              setVerification(null);
            }}
            spellCheck={false}
          />
          <button
            className="button secondary"
            disabled={checking}
            onClick={async () => {
              setChecking(true);
              setError("");
              try {
                setVerification(
                  await api("/api/verify", {
                    contract: record.draft,
                    response: JSON.parse(verifyText),
                  }),
                );
              } catch (caught) {
                setError(message(caught));
              } finally {
                setChecking(false);
              }
            }}
          >
            {checking ? (
              <LoaderCircle size={15} className="spin" />
            ) : (
              <ShieldCheck size={15} />
            )}
            Check contract
          </button>
          {verification && (
            <div
              role="status"
              className={`verification ${verification.valid ? "verification-pass" : "verification-fail"}`}
            >
              {verification.valid ? (
                <>
                  <Check size={15} />
                  Response matches the approved schema.
                </>
              ) : (
                <>
                  <TriangleAlert size={15} />
                  <div>
                    <strong>Response needs changes</strong>
                    {verification.errors.map((item, index) => (
                      <p key={index}>
                        <code>{item.path}</code>: {item.message}
                      </p>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </details>
      <p className="mock-footnote">
        <ShieldCheck size={13} />
        Portable mock URL · No database required · Synthetic data only ·{" "}
        <code>{mock.fingerprint}</code>
      </p>
    </div>
  );
}

export function Inspector({
  endpoint,
  record,
  onChange,
  preferredTab = "evidence",
}: {
  endpoint: Endpoint;
  record?: ContractRecord;
  onChange: (value: ContractRecord) => void;
  preferredTab?: "evidence" | "contract" | "mock";
}) {
  const [tab, setTab] = useState(preferredTab);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [schemaText, setSchemaText] = useState("");
  const [exampleText, setExampleText] = useState("");
  const [requestText, setRequestText] = useState("null");
  const [editing, setEditing] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  useEffect(() => setTab(preferredTab), [preferredTab]);
  useEffect(() => {
    if (record?.draft) {
      setSchemaText(JSON.stringify(record.draft.response_schema, null, 2));
      setExampleText(JSON.stringify(record.draft.response_example, null, 2));
      setRequestText(JSON.stringify(record.draft.request_schema, null, 2));
    }
    setReviewed(Boolean(record?.mock));
  }, [record?.draft]);
  async function generate() {
    setBusy("draft");
    setError("");
    try {
      const result = await api<{ contract: Contract; warnings: string[] }>(
        "/api/contract",
        { endpoint },
      );
      onChange({ draft: result.contract, warnings: result.warnings });
      setTab("contract");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy("");
    }
  }
  async function approve() {
    if (!record || !reviewed) return;
    setBusy("approve");
    setError("");
    try {
      const draft: Contract = {
        ...record.draft,
        response_schema: JSON.parse(schemaText),
        response_example: JSON.parse(exampleText),
        request_schema: JSON.parse(requestText),
      };
      const mock = await api<Mock>("/api/mock", {
        contract: draft,
        approved: true,
      });
      onChange({ draft, mock, warnings: record.warnings });
      setTab("mock");
      setEditing(false);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy("");
    }
  }
  function changeText(setter: (value: string) => void, value: string) {
    setter(value);
    setReviewed(false);
    if (record?.mock)
      onChange({ draft: record.draft, warnings: record.warnings });
  }
  const description =
    endpoint.status === "matched"
      ? "A route with this method and path exists. Runtime behavior and schema compatibility still need testing."
      : endpoint.status === "mismatch"
        ? `The frontend calls ${endpoint.method}, but this path only implements ${endpoint.available_methods.join(", ")}.`
        : "The frontend calls this endpoint, but no matching route was found in the scanned FastAPI code.";
  return (
    <section id="endpoint-inspector" className="card inspector">
      <div className="inspector-top">
        <div>
          <span className="eyebrow">INTERFACE WORKSPACE</span>
          <div className="endpoint-title">
            <MethodBadge method={endpoint.method} />
            <h2>{endpoint.path}</h2>
          </div>
          <p>{description}</p>
        </div>
        <StatusBadge status={endpoint.status} mocked={Boolean(record?.mock)} />
      </div>
      <div
        className="inspector-tabs"
        role="tablist"
        aria-label="Interface workflow"
      >
        {(
          [
            { id: "evidence", icon: Code2, label: "Code evidence", n: "01" },
            {
              id: "contract",
              icon: Braces,
              label: "Proposed contract",
              n: "02",
            },
            { id: "mock", icon: Terminal, label: "Mock & unblock", n: "03" },
          ] as const
        ).map((item) => (
          <button
            role="tab"
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            id={`tab-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                const ids = ["evidence", "contract", "mock"] as const;
                const index =
                  (ids.indexOf(tab) + (event.key === "ArrowRight" ? 1 : 2)) % 3;
                setTab(ids[index]);
                document.getElementById(`tab-${ids[index]}`)?.focus();
              }
            }}
            key={item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
          >
            <span className="step-number">{item.n}</span>
            <item.icon size={15} />
            {item.label}
            {((item.id === "contract" && record) ||
              (item.id === "mock" && record?.mock)) && (
              <Check size={13} className="tab-check" />
            )}
          </button>
        ))}
      </div>
      {error && (
        <div role="alert" className="inline-error inspector-error">
          <TriangleAlert size={16} />
          {error}
          <button
            className="icon-button"
            aria-label="Dismiss error"
            onClick={() => setError("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "evidence" && (
          <div className="evidence-content">
            <div className="evidence-grid">
              <SourceEvidence
                value={endpoint.callers[0] || null}
                label="FRONTEND CALL"
              />
              <SourceEvidence
                value={endpoint.backend}
                label={
                  endpoint.status === "missing"
                    ? "CLOSEST ROUTE · CONTEXT ONLY"
                    : "BACKEND ROUTE"
                }
              />
            </div>
            {endpoint.callers.length > 1 && (
              <details className="more-callers">
                <summary>
                  {endpoint.callers.length - 1} more call site
                  {endpoint.callers.length > 2 ? "s" : ""}
                  <ChevronDown size={14} />
                </summary>
                {endpoint.callers.slice(1).map((caller, index) => (
                  <SourceEvidence
                    key={index}
                    value={caller}
                    label="ADDITIONAL FRONTEND CALL"
                  />
                ))}
              </details>
            )}
            <div className="ownership-strip">
              <div className="owner-pair">
                <span className="avatar avatar-peach">
                  {(endpoint.frontend_owner || "?")
                    .replace("@", "")
                    .slice(0, 1)
                    .toUpperCase()}
                </span>
                <div>
                  <small>Frontend ownership hint</small>
                  <strong>{endpoint.frontend_owner || "Not assigned"}</strong>
                </div>
                <ArrowRight size={16} />
                <span className="avatar avatar-lilac">
                  {(endpoint.backend_owner || "?")
                    .replace("@", "")
                    .slice(0, 1)
                    .toUpperCase()}
                </span>
                <div>
                  <small>Backend ownership hint</small>
                  <strong>{endpoint.backend_owner || "Not assigned"}</strong>
                </div>
              </div>
              <span className="muted-note">
                From CODEOWNERS · not an attribution of fault
              </span>
            </div>
            <div className="inspector-next">
              <div>
                <span className="small-icon">
                  <Braces size={19} />
                </span>
                <div>
                  <h3>Agree on the interface. Keep building.</h3>
                  <p>
                    Turn these code signals into a contract your team can
                    review.
                  </p>
                </div>
              </div>
              <button
                className="button primary"
                onClick={record ? () => setTab("contract") : generate}
                disabled={Boolean(busy)}
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Sparkles size={15} />
                )}{" "}
                {record ? "Review contract" : "Propose contract"}
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}
        {tab === "contract" &&
          (!record ? (
            <div className="empty-stage">
              <span className="stage-icon">
                <Braces size={28} />
              </span>
              <h3>A clear agreement starts here.</h3>
              <p>
                Infer a draft from the code evidence, then confirm the fields
                with your teammate.
              </p>
              <button
                className="button primary"
                disabled={Boolean(busy)}
                onClick={generate}
              >
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                Propose contract
              </button>
              <span className="muted-note">
                Schema inference by default · Open-weight model support is
                configurable
              </span>
            </div>
          ) : (
            <div className="contract-content">
              <div className="proposal-heading">
                <div>
                  <span
                    className={`tag ${record.mock ? "green-tag" : "peach-tag"}`}
                  >
                    {record.mock
                      ? "ACCEPTED CONTRACT"
                      : "PROPOSED · NEEDS REVIEW"}
                  </span>
                  <span className="engine-label">
                    <Sparkles size={13} />
                    {record.draft.engine}
                  </span>
                </div>
                <button
                  className="quiet-button"
                  onClick={() => setEditing(!editing)}
                >
                  <Code2 size={14} />
                  {editing ? "Close JSON editor" : "Edit JSON"}
                </button>
              </div>
              {record.warnings?.map((warning) => (
                <div key={warning} className="soft-notice">
                  <TriangleAlert size={14} />
                  {warning}
                </div>
              ))}
              <div className="contract-columns">
                <div>
                  <div className="section-label">
                    <span>Response schema</span>
                    <span>JSON SCHEMA</span>
                  </div>
                  {editing ? (
                    <textarea
                      aria-label="Response JSON schema"
                      className="json-editor"
                      value={schemaText}
                      onChange={(event) =>
                        changeText(setSchemaText, event.target.value)
                      }
                      spellCheck={false}
                    />
                  ) : (
                    <pre className="schema-preview">
                      <code>{schemaText}</code>
                    </pre>
                  )}
                </div>
                <div>
                  <div className="section-label">
                    <span>Example response</span>
                    <span>200 OK · SYNTHETIC</span>
                  </div>
                  {editing ? (
                    <textarea
                      aria-label="Example JSON response"
                      className="json-editor"
                      value={exampleText}
                      onChange={(event) =>
                        changeText(setExampleText, event.target.value)
                      }
                      spellCheck={false}
                    />
                  ) : (
                    <pre className="example-preview">
                      <code>{exampleText}</code>
                    </pre>
                  )}
                </div>
              </div>
              {(record.draft.request_schema || editing) && (
                <details className="request-schema">
                  <summary>
                    Request body schema <ChevronDown size={14} />
                  </summary>
                  {editing ? (
                    <textarea
                      aria-label="Request JSON schema"
                      className="json-editor short-editor"
                      value={requestText}
                      onChange={(event) =>
                        changeText(setRequestText, event.target.value)
                      }
                      spellCheck={false}
                    />
                  ) : (
                    <pre>
                      <code>{requestText}</code>
                    </pre>
                  )}
                </details>
              )}
              <div className="questions">
                <span className="questions-icon">
                  <CircleHelp size={19} />
                </span>
                <div>
                  <h3>Before you shake on it</h3>
                  {record.draft.questions.map((question, index) => (
                    <p key={index}>{question}</p>
                  ))}
                </div>
              </div>
              <div className="approve-footer">
                <label className="review-checkbox">
                  <input
                    type="checkbox"
                    checked={reviewed}
                    onChange={(event) => setReviewed(event.target.checked)}
                  />
                  <span>
                    I reviewed this proposal and accept it as our working
                    contract.
                  </span>
                </label>
                <button
                  className="button primary"
                  disabled={!reviewed || Boolean(busy)}
                  onClick={approve}
                >
                  {busy === "approve" ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <CheckCheck size={16} />
                  )}
                  Accept & generate mock
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          ))}
        {tab === "mock" &&
          (record?.mock ? (
            <Playground key={record.mock.fingerprint} record={record} />
          ) : (
            <div className="empty-stage">
              <span className="stage-icon">
                <Terminal size={28} />
              </span>
              <h3>A mock starts with an agreement.</h3>
              <p>
                Review and accept your proposed contract to generate a live
                mock, OpenAPI file and backend skeleton.
              </p>
              <button
                className="button secondary"
                onClick={() => setTab("contract")}
              >
                Review the contract
                <ArrowRight size={15} />
              </button>
              <span className="muted-note">
                <ShieldCheck size={13} /> Human approval comes first
              </span>
            </div>
          ))}
      </div>
    </section>
  );
}

export function Workflow({ onStart }: { onStart: () => void }) {
  return (
    <div className="workflow-panel">
      <div className="workflow-intro">
        <span className="tag peach-tag">THE TRITONTEAM WAY</span>
        <h2>
          One contract.
          <br />
          <span>Everyone moves forward.</span>
        </h2>
        <p>
          Find an interface gap, agree on its shape, and let frontend and
          backend build in parallel.
        </p>
        <button className="button primary" onClick={onStart}>
          Find your missing link
          <ArrowRight size={15} />
        </button>
      </div>
      <div className="workflow-steps">
        {[
          {
            icon: Code2,
            title: "Detect the gap",
            text: "Compare frontend calls with implemented backend routes.",
          },
          {
            icon: GitBranch,
            title: "Follow the evidence",
            text: "See the exact source lines and CODEOWNERS hints.",
          },
          {
            icon: Braces,
            title: "Agree on a contract",
            text: "Review inferred fields. Make assumptions explicit.",
          },
          {
            icon: Terminal,
            title: "Unblock both sides",
            text: "Frontend gets a working mock. Backend gets a typed skeleton.",
          },
        ].map((step, index) => (
          <div className="workflow-step" key={step.title}>
            <span className="workflow-number">0{index + 1}</span>
            <span className="workflow-icon">
              <step.icon size={19} />
            </span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
            {index < 3 && <ChevronRight size={14} className="workflow-arrow" />}
          </div>
        ))}
      </div>
    </div>
  );
}
