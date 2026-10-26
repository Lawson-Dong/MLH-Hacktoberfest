import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Braces,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Code2,
  ExternalLink,
  FolderGit2,
  GitBranch,
  Github,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Radar,
  RotateCw,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleAlert,
  Unplug,
  X,
} from "lucide-react";
import {
  Brand,
  DependencyMap,
  Inspector,
  MethodBadge,
  StatusBadge,
  Workflow,
} from "./components";
import { api, loadStored, message, saveFile, storeLocal } from "./types";
import type { Endpoint, Records, Scan, Section } from "./types";
import "./styles.css";

const SOURCE = "https://github.com/Lawson-Dong/MLH-Hacktoberfest";
const SCAN_KEY = "tritonteam.scan.v2";
const CONTRACTS_KEY = "tritonteam.contracts.v1";
const sections = {
  overview: "Overview",
  scanner: "Repository scanner",
  contracts: "API contracts",
  playground: "Mock playground",
};
function savedScan(): Scan | null {
  const value = loadStored<Scan | null>(SCAN_KEY, null);
  return value?.repository && Array.isArray(value.endpoints) && value.stats
    ? value
    : null;
}

export default function App() {
  const [section, setSection] = useState<Section>("scanner");
  const [scan, setScan] = useState<Scan | null>(savedScan);
  const [records, setRecords] = useState<Records>(() =>
    loadStored(CONTRACTS_KEY, {}),
  );
  const [repoUrl, setRepoUrl] = useState(SOURCE);
  const [busy, setBusy] = useState<"scan" | "demo" | "">("");
  const [loading, setLoading] = useState(!scan);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState<"all" | "review" | "matched">("all");
  const [search, setSearch] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [engine, setEngine] = useState("Schema inference");
  const inputRef = useRef<HTMLInputElement>(null);
  const guideRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const abort = new AbortController();
    api<{ engine: string }>("/api/health", undefined, abort.signal)
      .then((data) => setEngine(data.engine))
      .catch(() => {});
    if (!scan)
      api<Scan>("/api/demo", undefined, abort.signal)
        .then((data) => {
          setScan(data);
          setSelectedId(data.endpoints[0]?.id || "");
        })
        .catch((caught) => {
          if (!abort.signal.aborted) setError(message(caught));
        })
        .finally(() => {
          if (!abort.signal.aborted) setLoading(false);
        });
    return () => abort.abort();
    // The initial snapshot is loaded once; subsequent scans are user-initiated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (scan) storeLocal(SCAN_KEY, scan);
  }, [scan]);
  useEffect(() => storeLocal(CONTRACTS_KEY, records), [records]);
  useEffect(() => {
    if (guideOpen) guideRef.current?.showModal();
    else guideRef.current?.close();
  }, [guideOpen]);
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const keyFor = (id: string) =>
    `${scan?.repository.full_name}:${scan?.repository.commit}:${id}`;
  const visible = useMemo(
    () =>
      scan?.endpoints.filter(
        (endpoint) =>
          (filter === "all" ||
            (filter === "review"
              ? endpoint.status !== "matched"
              : endpoint.status === "matched")) &&
          `${endpoint.method} ${endpoint.path} ${endpoint.callers[0]?.file}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ) || [],
    [scan, filter, search],
  );
  const ready =
    scan?.endpoints.filter((endpoint) => records[keyFor(endpoint.id)]?.mock) ||
    [];
  const drafts =
    scan?.endpoints.filter((endpoint) => records[keyFor(endpoint.id)]?.draft) ||
    [];
  const candidate =
    scan?.endpoints.find((endpoint) => endpoint.id === selectedId) ||
    scan?.endpoints[0];
  const selected =
    section === "playground" &&
    candidate &&
    !records[keyFor(candidate.id)]?.mock
      ? ready[0]
      : candidate;

  async function performScan(demo = false) {
    setBusy(demo ? "demo" : "scan");
    setError("");
    try {
      const data = await api<Scan>(
        demo ? "/api/demo" : "/api/scan",
        demo ? undefined : { repo_url: repoUrl.trim() },
      );
      setScan(data);
      setSelectedId(data.endpoints[0]?.id || "");
      setFilter("all");
      setSearch("");
      setSection("scanner");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy("");
      setLoading(false);
    }
  }
  function navigate(value: Section) {
    setSection(value);
    setMenuOpen(false);
  }
  function review(endpoint?: Endpoint) {
    if (endpoint) setSelectedId(endpoint.id);
    setSection("scanner");
    setTimeout(
      () =>
        document
          .getElementById("endpoint-inspector")
          ?.scrollIntoView({ behavior: "smooth", block: "start" }),
      20,
    );
  }
  const pageCopy =
    section === "overview"
      ? {
          eyebrow: "YOUR TEAM, IN SYNC",
          title: "Keep building. Together.",
          description: "A shared interface is where great teamwork begins.",
        }
      : section === "contracts"
        ? {
            eyebrow: "AGREE FIRST. BUILD IN PARALLEL.",
            title: "A little clarity. A lot of progress.",
            description:
              "Turn code evidence into an API contract both sides can build against.",
          }
        : section === "playground"
          ? {
              eyebrow: "LESS WAITING. MORE BUILDING.",
              title: "Your next step is unblocked.",
              description:
                "Test a live mock, grab the code, and keep your frontend moving.",
            }
          : {
              eyebrow: "REPOSITORY SCANNER",
              title: "Find the missing link.",
              description:
                "Connect your frontend and backend. Keep your whole team moving.",
            };

  return (
    <div className="app-shell">
      {menuOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <a
          className="brand-link"
          href="#"
          aria-label="TritonTeam home"
          onClick={(event) => {
            event.preventDefault();
            navigate("overview");
          }}
        >
          <Brand />
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <div className="workspace-switch">
          <span className="workspace-icon">
            <Layers3 size={17} />
          </span>
          <div>
            <strong>Hacktoberfest</strong>
            <small>Team workspace · prototype</small>
          </div>
          <span className="workspace-letter">H</span>
        </div>
        <div className="nav-label">BUILD TOGETHER</div>
        <nav aria-label="Main navigation">
          {(
            [
              { id: "overview", icon: LayoutDashboard },
              { id: "scanner", icon: Radar },
              { id: "contracts", icon: Braces },
              { id: "playground", icon: Terminal },
            ] as const
          ).map((item) => (
            <button
              className={`nav-item ${section === item.id ? "nav-active" : ""}`}
              key={item.id}
              onClick={() => navigate(item.id)}
              aria-current={section === item.id ? "page" : undefined}
            >
              <item.icon size={18} />
              <span>{sections[item.id]}</span>
              {item.id === "scanner" && Boolean(scan?.stats.review) && (
                <span className="nav-count">{scan?.stats.review}</span>
              )}
              {item.id === "contracts" && drafts.length > 0 && (
                <span className="nav-count neutral-count">{drafts.length}</span>
              )}
              {item.id === "playground" && ready.length > 0 && (
                <span className="nav-count green-count">{ready.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="note-symbol">
            <Sparkles size={19} />
            <span className="note-dot" />
          </div>
          <h3>
            Great teams don't
            <br />
            wait on each other.
          </h3>
          <p>
            Agree on the interface.
            <br />
            Keep the ideas flowing.
          </p>
          <button onClick={() => setGuideOpen(true)}>
            How it works <ArrowRight size={14} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <div className="event-mark">
            <span className="event-asterisk">✳</span>
            <div>
              <strong>Built for Hacktoberfest</strong>
              <small>Small team. Big momentum.</small>
            </div>
          </div>
          <div className="profile">
            <span className="profile-avatar">LD</span>
            <div>
              <strong>Lawson's workspace</strong>
              <small>Saved in this browser</small>
            </div>
            <ShieldCheck size={15} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{sections[section]}</strong>
          </div>
          <div className="topbar-right">
            <span className="prototype-label">
              <span className="tiny-dot green" />
              Hackathon prototype
            </span>
            <span className="topbar-divider" />
            <button
              className="icon-button guide-button"
              aria-label="How TritonTeam works"
              onClick={() => setGuideOpen(true)}
            >
              <CircleHelp size={18} />
            </button>
            <a
              href={SOURCE}
              target="_blank"
              rel="noreferrer"
              className="source-link"
            >
              <Github size={17} />
              <span>View source</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="page-eyebrow">
                <span />
                {pageCopy.eyebrow}
              </div>
              <h1>{pageCopy.title}</h1>
              <p>{pageCopy.description}</p>
            </div>
            <span className="heading-graphic" aria-hidden="true">
              <span className="graphic-left">
                <Code2 size={25} />
              </span>
              <span className="graphic-connector" />
              <span className="graphic-right">
                <Terminal size={24} />
              </span>
              <span className="graphic-spark">✳</span>
            </span>
          </div>
          <section className="scan-box" aria-label="Scan a GitHub repository">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void performScan();
              }}
            >
              <div className="repo-input-wrap">
                <Github size={20} />
                <input
                  ref={inputRef}
                  aria-label="GitHub repository URL"
                  type="url"
                  required
                  value={repoUrl}
                  onChange={(event) => setRepoUrl(event.target.value)}
                  placeholder="https://github.com/your-team/your-project"
                  disabled={Boolean(busy)}
                />
                <kbd>⌘ K</kbd>
              </div>
              <button
                className="button primary scan-submit"
                disabled={Boolean(busy) || loading}
                type="submit"
              >
                {busy === "scan" ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Radar size={17} />
                )}
                <span>
                  {busy === "scan" ? "Scanning repository…" : "Scan repository"}
                </span>
                <ArrowRight size={15} />
              </button>
            </form>
            <div className="scan-box-footer">
              <span>
                <ShieldCheck size={13} />
                Public repositories · Read-only scan · React + FastAPI
              </span>
              <button
                className="text-button"
                disabled={Boolean(busy)}
                onClick={() => void performScan(true)}
              >
                {busy === "demo" ? (
                  <LoaderCircle size={13} className="spin" />
                ) : (
                  <PlayIcon />
                )}
                Try a demo repository
                <ArrowRight size={12} />
              </button>
            </div>
          </section>
          {busy === "scan" && (
            <div className="scan-progress" role="status">
              <LoaderCircle size={16} className="spin" />
              <div>
                <strong>Following the code, finding the connections.</strong>
                <span>
                  Reading a pinned GitHub commit and comparing supported calls
                  with routes. Large scans can take up to 48 seconds.
                </span>
              </div>
            </div>
          )}
          {error && (
            <div className="page-error" role="alert">
              <TriangleAlert size={18} />
              <div>
                <strong>We couldn't finish that request.</strong>
                <p>{error}</p>
                {scan && (
                  <small>Your previous scan is still shown below.</small>
                )}
              </div>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state" role="status">
              <LoaderCircle size={28} className="spin" />
              <h2>Opening your workspace</h2>
              <p>Running the bundled repository through the scanner…</p>
            </div>
          ) : scan ? (
            <>
              <div className="repo-heading">
                <div className="repo-title">
                  <span className="repo-icon">
                    <FolderGit2 size={20} />
                  </span>
                  <div>
                    <div>
                      <h2>{scan.repository.full_name}</h2>
                      <span
                        className={`tag ${scan.repository.demo ? "neutral-tag" : "green-tag"}`}
                      >
                        {scan.repository.demo
                          ? "DEMO REPOSITORY"
                          : "GITHUB SCAN"}
                      </span>
                    </div>
                    <p>
                      <GitBranch size={12} />
                      {scan.repository.branch}
                      <span>·</span>
                      <code>{scan.repository.commit.slice(0, 7)}</code>
                      <span>·</span>
                      {scan.stats.files} source files analyzed
                      {scan.repository.demo && (
                        <>
                          <span>·</span>Bundled example, real analysis
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <div className="repo-actions">
                  <button
                    className="quiet-button"
                    onClick={() =>
                      saveFile(
                        "tritonteam-scan.json",
                        JSON.stringify(scan, null, 2),
                      )
                    }
                  >
                    <ArrowDownToLine size={14} />
                    <span>Export scan</span>
                  </button>
                  <button
                    className="icon-button"
                    disabled={Boolean(busy)}
                    aria-label="Refresh current repository scan"
                    onClick={() => {
                      if (!scan.repository.demo)
                        setRepoUrl(scan.repository.url);
                      setBusy(scan.repository.demo ? "demo" : "scan");
                      setError("");
                      api<Scan>(
                        scan.repository.demo ? "/api/demo" : "/api/scan",
                        scan.repository.demo
                          ? undefined
                          : { repo_url: scan.repository.url },
                      )
                        .then((data) => {
                          setScan(data);
                          setSelectedId(data.endpoints[0]?.id || "");
                        })
                        .catch((caught) => setError(message(caught)))
                        .finally(() => setBusy(""));
                    }}
                  >
                    <RotateCw size={15} className={busy ? "spin" : ""} />
                  </button>
                </div>
              </div>
              <div className="stats-grid">
                {[
                  {
                    icon: Code2,
                    name: "Frontend API calls",
                    value: scan.stats.calls,
                    note: scan.stats.calls ? "unique method + path" : "check scan coverage below",
                    cls: "ink",
                  },
                  {
                    icon: CheckCheck,
                    name: "Routes matched",
                    value: scan.stats.matched,
                    note: scan.stats.calls && scan.stats.routes ? "path & method connected" : "coverage is insufficient",
                    cls: "green",
                  },
                  {
                    icon: Unplug,
                    name: "Need a closer look",
                    value: scan.stats.review,
                    note: "potential interface gaps",
                    cls: "orange",
                  },
                  {
                    icon: Terminal,
                    name: "Mocks ready",
                    value: ready.length,
                    note: "accepted & ready to use",
                    cls: "purple",
                  },
                ].map((stat) => (
                  <div className={`stat-card stat-${stat.cls}`} key={stat.name}>
                    <div className="stat-top">
                      <span>{stat.name}</span>
                      <stat.icon size={17} />
                    </div>
                    <div className="stat-bottom">
                      <strong>{String(stat.value).padStart(2, "0")}</strong>
                      <span>{stat.note}</span>
                    </div>
                  </div>
                ))}
              </div>
              {scan.warnings.length > 0 && (
                <details className="coverage-notice" open={!scan.stats.calls || !scan.stats.routes}>
                  <summary>
                    <TriangleAlert size={15} />
                    <span>
                      Partial scan · {scan.warnings.length} coverage note
                      {scan.warnings.length > 1 ? "s" : ""}
                    </span>
                    <ChevronDown size={14} />
                  </summary>
                  <ul>
                    {scan.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </details>
              )}
              {section === "overview" && (
                <Workflow onStart={() => navigate("scanner")} />
              )}
              {(section === "scanner" || section === "overview") && (
                <div className="results-layout">
                  <section className="card findings-card">
                    <div className="card-heading">
                      <div>
                        <h2>
                          Your API connections{" "}
                          <span className="count-bubble">
                            {scan.stats.calls}
                          </span>
                        </h2>
                        <p>A clearer picture of where your code meets.</p>
                      </div>
                      <span className="tag neutral-tag">
                        <Activity size={11} />
                        {scan.stats.calls && scan.stats.routes ? "SCAN COMPLETE" : "LIMITED COVERAGE"}
                      </span>
                    </div>
                    <div className="table-toolbar">
                      <div
                        className="filter-tabs"
                        role="group"
                        aria-label="Filter API calls"
                      >
                        {(
                          [
                            {
                              id: "all",
                              label: "All calls",
                              count: scan.stats.calls,
                            },
                            {
                              id: "review",
                              label: "Needs review",
                              count: scan.stats.review,
                            },
                            {
                              id: "matched",
                              label: "Matched",
                              count: scan.stats.matched,
                            },
                          ] as const
                        ).map((item) => (
                          <button
                            aria-pressed={filter === item.id}
                            key={item.id}
                            className={filter === item.id ? "active" : ""}
                            onClick={() => setFilter(item.id)}
                          >
                            {item.label}
                            <span>{item.count}</span>
                          </button>
                        ))}
                      </div>
                      <div className="table-search">
                        <Search size={14} />
                        <input
                          aria-label="Filter endpoints by path"
                          placeholder="Find endpoint…"
                          value={search}
                          onChange={(event) => setSearch(event.target.value)}
                        />
                      </div>
                    </div>
                    <div className="endpoints-table-wrap">
                      <table className="endpoints-table">
                        <thead>
                          <tr>
                            <th>ENDPOINT</th>
                            <th>CONNECTION</th>
                            <th>OWNER HINT</th>
                            <th>
                              <span className="sr-only">Action</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {visible.map((endpoint) => (
                            <tr
                              key={endpoint.id}
                              className={
                                selected?.id === endpoint.id
                                  ? "selected-row"
                                  : ""
                              }
                            >
                              <td>
                                <button
                                  className="endpoint-button"
                                  onClick={() => review(endpoint)}
                                >
                                  <span>
                                    <MethodBadge method={endpoint.method} />
                                    <code>{endpoint.path}</code>
                                  </span>
                                  <small>
                                    <FileCodeIcon />
                                    {endpoint.callers[0]?.file
                                      .split("/")
                                      .slice(-2)
                                      .join("/")}
                                    :{endpoint.callers[0]?.line}
                                  </small>
                                </button>
                              </td>
                              <td>
                                <StatusBadge
                                  status={endpoint.status}
                                  mocked={Boolean(
                                    records[keyFor(endpoint.id)]?.mock,
                                  )}
                                />
                              </td>
                              <td>
                                <span className="table-owner">
                                  <span
                                    className={`mini-avatar ${endpoint.status === "matched" ? "avatar-sage" : "avatar-peach"}`}
                                  >
                                    {(endpoint.frontend_owner || "?")
                                      .replace("@", "")
                                      .slice(0, 1)
                                      .toUpperCase()}
                                  </span>
                                  <span>
                                    {endpoint.frontend_owner
                                      ?.replace("@", "")
                                      .replace("-demo", "") || "Unassigned"}
                                  </span>
                                </span>
                              </td>
                              <td>
                                <button
                                  className="row-action"
                                  aria-label={`Review ${endpoint.method} ${endpoint.path}`}
                                  onClick={() => review(endpoint)}
                                >
                                  <ArrowRight size={16} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {visible.length === 0 && (
                        <div className="table-empty">
                          <Search size={24} />
                          <h3>
                            {scan.stats.calls
                              ? "No matching endpoints"
                              : "No supported API calls found"}
                          </h3>
                          <p>
                            {scan.stats.calls
                              ? "Try another path or clear your filters."
                              : "Zero detected calls does not mean there are no APIs. Read the coverage notes above; custom clients, dynamic URLs or excluded files may need manual review. Try the demo to see a supported example."}
                          </p>
                          {scan.stats.calls > 0 && (
                            <button
                              className="text-button"
                              onClick={() => {
                                setSearch("");
                                setFilter("all");
                              }}
                            >
                              Clear filters <X size={13} />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="table-footer">
                      <span>
                        <span className="tiny-dot green" />
                        {visible.length} of {scan.stats.calls} connections
                      </span>
                      <span>Evidence first. Assumptions second.</span>
                    </div>
                  </section>
                  <div className="results-aside">
                    <DependencyMap
                      scan={scan}
                      onReview={() =>
                        review(
                          scan.endpoints.find(
                            (endpoint) => endpoint.status !== "matched",
                          ) || scan.endpoints[0],
                        )
                      }
                    />
                    <div className="next-step-card">
                      <span className="next-step-icon">
                        <Braces size={20} />
                      </span>
                      <div>
                        <span className="eyebrow">YOUR NEXT GOOD MOVE</span>
                        <h3>
                          {scan.stats.review
                            ? "Turn a gap into an agreement."
                            : "Routes connect. Check the contract."}
                        </h3>
                        <p>
                          {scan.stats.review
                            ? "A reviewed contract lets both sides work without waiting."
                            : "A matched route is a starting point. Confirm the response shape, too."}
                        </p>
                        <button
                          className="text-button"
                          onClick={() => navigate("contracts")}
                        >
                          Open API contracts
                          <ArrowRight size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {(section === "contracts" || section === "playground") && (
                <div className="section-workspace-heading">
                  <div>
                    <h2>
                      {section === "contracts"
                        ? "Your interface agreements"
                        : "Your runnable mocks"}
                    </h2>
                    <p>
                      {section === "contracts"
                        ? `${drafts.length} proposed · ${ready.length} accepted · Review before generating a mock.`
                        : `${ready.length} ready · Built from the exact contract you accepted.`}
                    </p>
                  </div>
                  <span className="engine-chip">
                    <Sparkles size={14} />
                    {engine}
                  </span>
                </div>
              )}
              {section === "playground" && ready.length === 0 ? (
                <section className="card empty-stage empty-mocks">
                  <span className="stage-icon">
                    <Terminal size={30} />
                  </span>
                  <h3>Your first mock is one agreement away.</h3>
                  <p>
                    Pick an interface, review its proposed contract, and accept
                    it to unblock your frontend.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => navigate("contracts")}
                  >
                    Review an interface
                    <ArrowRight size={15} />
                  </button>
                </section>
              ) : (
                <>
                  {(section === "contracts" || section === "playground") && (
                    <div
                      className="endpoint-picker"
                      role="group"
                      aria-label="Choose an interface"
                    >
                      {(section === "playground" ? ready : scan.endpoints).map(
                        (endpoint) => (
                          <button
                            key={endpoint.id}
                            className={
                              selected?.id === endpoint.id ? "active" : ""
                            }
                            onClick={() => setSelectedId(endpoint.id)}
                          >
                            <MethodBadge method={endpoint.method} />
                            <code>{endpoint.path}</code>
                            {records[keyFor(endpoint.id)]?.mock ? (
                              <Check size={14} />
                            ) : (
                              <ChevronRight size={14} />
                            )}
                          </button>
                        ),
                      )}
                    </div>
                  )}
                  {selected && section !== "overview" && (
                    <Inspector
                      key={keyFor(selected.id)}
                      endpoint={selected}
                      record={records[keyFor(selected.id)]}
                      onChange={(value) =>
                        setRecords((previous) => ({
                          ...previous,
                          [keyFor(selected.id)]: value,
                        }))
                      }
                      preferredTab={
                        section === "contracts"
                          ? "contract"
                          : section === "playground"
                            ? "mock"
                            : "evidence"
                      }
                    />
                  )}
                </>
              )}
              <div className="scope-note">
                <ShieldCheck size={14} />
                <span>{scan.scope}</span>
                <button
                  onClick={() => setGuideOpen(true)}
                  aria-label="Read scanner limitations"
                >
                  <CircleHelp size={14} />
                </button>
              </div>
            </>
          ) : (
            <section className="card empty-stage">
              <Unplug size={30} />
              <h3>Let's connect your code.</h3>
              <p>
                Scan a public repository, or start with our bundled React +
                FastAPI demo.
              </p>
              <button
                className="button primary"
                onClick={() => void performScan(true)}
              >
                Open demo
                <ArrowRight size={15} />
              </button>
            </section>
          )}
          <footer className="main-footer">
            <span>
              <Brand small />
              Made for the way small teams build.
            </span>
            <span>
              Detect<span>→</span>Agree<span>→</span>Keep building
              <span className="footer-spark">✳</span>
            </span>
          </footer>
        </main>
      </div>
      <dialog
        className="guide-dialog"
        ref={guideRef}
        onClose={() => setGuideOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setGuideOpen(false);
        }}
      >
        <div className="guide-content">
          <button
            className="icon-button dialog-close"
            onClick={() => setGuideOpen(false)}
            aria-label="Close guide"
          >
            <X size={20} />
          </button>
          <Brand />
          <span className="page-eyebrow">A LITTLE CLARITY GOES A LONG WAY</span>
          <h2>
            From interface gap
            <br />
            to forward progress.
          </h2>
          <ol>
            <li>
              <strong>Scan the repository.</strong>
              <p>
                We read public source files at one commit. The scanner compares
                literal fetch/axios calls with FastAPI routes, including static
                router prefixes.
              </p>
            </li>
            <li>
              <strong>Review the evidence.</strong>
              <p>
                A missing route is a potential gap. It may live in another
                repository. CODEOWNERS provides hints, never blame.
              </p>
            </li>
            <li>
              <strong>Agree on a contract.</strong>
              <p>
                Review inferred TypeScript fields and assumptions. Schema
                inference works without a model; an open-weight model can be
                configured on the server.
              </p>
            </li>
            <li>
              <strong>Unblock and verify.</strong>
              <p>
                Accept the contract to get a working mock, OpenAPI, an MSW
                handler and a Pydantic skeleton. Paste a real backend response
                to check its schema.
              </p>
            </li>
          </ol>
          <div className="guide-note">
            <ShieldCheck size={19} />
            <p>
              This prototype stores your review state in this browser. It does
              not sync teammate approvals, continuously monitor GitHub or scan
              private repositories. Dynamic clients and other backend frameworks
              are outside the scanner's scope.
            </p>
          </div>
          <button
            className="button primary"
            onClick={() => setGuideOpen(false)}
          >
            Let's keep building
            <ArrowRight size={15} />
          </button>
        </div>
      </dialog>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <path d="m3 1 6 4-6 4Z" fill="currentColor" />
    </svg>
  );
}
function FileCodeIcon() {
  return <Code2 size={11} />;
}
