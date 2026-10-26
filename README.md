# TritonTeam

**Find the missing link between your frontend and backend. Keep building, together.**

An API collaboration prototype for Hacktoberfest. Paste a public GitHub repository, inspect potential frontend/backend interface gaps, review a proposed contract, and generate a runnable mock so the frontend can keep moving while the backend is implemented.

**Detect → Follow the evidence → Agree on a contract → Unblock → Verify**

## What works

- Public GitHub scanning at an immutable commit; source code is read, never executed.
- Root-relative JS/TS `fetch` and Axios calls, including TypeScript generics, local URL constants, simple concatenation/template parameters, and Axios instances with static `baseURL` values.
- Traceable local fetch wrappers (function or arrow syntax), including named relative imports: fixed methods, forwarded fetch options, or the explicit `body === undefined ? "GET" : "POST"` convention. Evidence points to the caller rather than the wrapper definition.
- Python AST extraction of FastAPI routes and statically mounted APIRouter prefixes, including imports and nested mounts.
- Method/path matching, missing route candidates and method mismatches, with file/line evidence.
- CODEOWNERS ownership hints. These are signals for discussion, not proof that someone is blocking the team.
- Editable JSON Schema contracts and synthetic examples, with explicit review and acceptance.
- A real, stateless mock endpoint: send requests from the playground or copy its URL.
- Downloadable ZIP with OpenAPI 3.1, a FastAPI mock, a Pydantic backend skeleton and an MSW v2 handler.
- Schema validation of pasted real backend JSON responses.
- A bundled React + FastAPI example: 6 unique calls, 3 matched, 2 missing and 1 method mismatch. It runs through the same detector as a real repository.

This version checks **route existence**, not full runtime or business compatibility. A missing route is a potential interface gap, not a confirmed blocked teammate.

## Run locally

Requirements: Python 3.12+ and Node.js 22.12+ (Node 24 recommended).

```bash
git clone https://github.com/Lawson-Dong/MLH-Hacktoberfest.git
cd MLH-Hacktoberfest
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
npm --prefix frontend ci
npm run dev
```

Open `http://localhost:5173`. The one development entrypoint starts FastAPI on port 8000 and Vite on port 5173; Vite proxies `/api` to FastAPI.

On Windows, activate with `.venv\Scripts\activate` and run the two services in separate terminals if needed:

```bash
python -m uvicorn backend.app:app --reload --port 8000
npm --prefix frontend run dev
```

Interactive API docs: `http://localhost:8000/api/docs`.

### Demo in 60 seconds

1. Open **Repository scanner** and choose **Try a demo repository**.
2. Select `GET /api/projects/{projectId}/tasks` and inspect the frontend and backend source evidence.
3. Choose **Propose contract**. Review the inferred Task fields and open questions. **Edit JSON** to change the schema or example.
4. Check the review acknowledgement, then **Accept & generate mock**.
5. **Send request** to receive a real JSON response from the generated endpoint.
6. **Download bundle**. Give the mock/MSW handler to frontend and the Pydantic skeleton to backend.
7. Expand the contract check, paste a backend response, and verify its fields and types.

## Vercel deployment

The repository is configured for **Vercel Services (Beta)** so React/Vite and FastAPI ship in the same deployment:

| Service  | Root        | Framework          | Public route           |
| -------- | ----------- | ------------------ | ---------------------- |
| Frontend | `frontend/` | Vite               | `/` and frontend paths |
| Backend  | `backend/`  | FastAPI, `app:app` | `/api/*`               |

Import this repository as **one Vercel project**, with the repository root as Root Directory. Keep service build settings in `vercel.json`; do not select only the frontend directory. No environment variables or paid database are required for the baseline flow.

With a Vercel CLI authenticated to your intended account:

```bash
vercel link
vercel project inspect --non-interactive
vercel deploy
```

Verify the returned preview's `/api/health`, then run the demo flow above. Promote or deploy to production only when you intend to publish it. Vercel account/team consent must be completed by the account owner if the connection requests it.

References: [Vercel Services](https://vercel.com/docs/services), [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi).

## AI: DeepSeek V4.1 (default)

The scanner, review workflow, and runnable mocks work without any model credentials, using **Schema inference**. They must not be described as LLM-powered unless `/api/contract` actually returns a model-backed result.

### DeepSeek setup for TritonTeam

TritonTeam defaults to [DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) (`deepseek-flash`) through the official OpenAI-compatible API at `https://api.deepseek.com`. The weights are MIT-licensed; the hosted API is pay-as-you-go with no standing free tier, but a hobby-scale workload typically costs around $1–2/month. Availability, account balance, permissions, and provider charges still apply.

1. Create an API key at the [DeepSeek platform](https://platform.deepseek.com/).
2. In **Vercel → tritonteam-hacktoberfest → Settings → Environment Variables**, add:
   - `MODEL_PROVIDER=deepseek` as a **Config** variable for **Production**.
   - `DEEPSEEK_API_KEY=<your DeepSeek key>` as a **Secret** variable for **Production**.
   - Optionally, `DEEPSEEK_MODEL=deepseek-flash` as a **Config** variable.
3. Save, then **redeploy Production** to load the new variables.

These variables select `https://api.deepseek.com`. The backend requests `chat/completions` with `response_format: json_object`. DeepSeek requires the word "JSON" in the prompt; the contract system prompt already includes it. A missing key, HTTP failure, timeout, or invalid output returns an explicit `Schema inference` warning. Mock generation still requires developer review and acceptance.

**Verify actual AI inference:** `GET /api/health` should report `model_configured: true` and `engine: "deepseek-flash"`; this verifies configuration only. Generate a proposal in the UI or use `POST /api/contract`, then check `contract.engine: "Model: deepseek-flash"` and `warnings: []`. A configured model returning 401, 403, 402, 429, or a timeout did **not** successfully generate the contract.

### Grok setup for TritonTeam

TritonTeam supports the [xAI Responses API](https://docs.x.ai/developers/rest-api-reference/inference/responses). The default is [Grok 4.3](https://docs.x.ai/developers/models/grok-4.3), with reasoning disabled for this short contract-generation task. `XAI_MODEL` can select another model; other Grok models use low reasoning effort. Availability, account credits, permissions, and provider charges still apply.

1. Create an API key at the [xAI Console](https://console.x.ai/).
2. In **Vercel → tritonteam-hacktoberfest → Settings → Environment Variables**, add:
   - `MODEL_PROVIDER=xai` as a **Config** variable for **Production** (`grok` is also accepted).
   - `XAI_API_KEY=<your xAI key>` as a **Secret** variable for **Production**.
   - Optionally, `XAI_MODEL=grok-4.3` as a **Config** variable.
3. Save, then **redeploy Production** to load the new variables.

These variables select `https://api.x.ai/v1/responses`. The existing deployed Secret `Grok_API_Key` is accepted directly, so it does not need to be renamed or copied. Key priority is `XAI_API_KEY`, `GROK_API_KEY`, then `Grok_API_Key`.

**Grok/xAI and Groq are different services.** Grok keys are never used for Groq, OpenRouter, or the generic provider. Explicit provider selection never falls through to another provider's credentials. Do not put keys in GitHub or client-side `VITE_*` variables.

The backend requests structured JSON through `text.format` with the Contract JSON Schema. Detected endpoint ID, method, and path are constrained and validated locally as well. Responses are not stored by the provider (`store: false`). Invalid output gets at most one correction request, preserving opaque response items for the native Responses protocol; the same validation rules apply. A missing key, HTTP failure, timeout, or invalid output returns an explicit `Schema inference` warning. Timeouts and HTTP failures are not retried. Mock generation still requires developer review and acceptance.

**Verify actual AI inference:** `GET /api/health` should report `model_configured: true` and `engine: "grok-4.3"`; this verifies configuration only. Generate a proposal in the UI or use `POST /api/contract`, then check `contract.engine: "Model: grok-4.3"` and `warnings: []`. A configured model returning 401, 403, 402, 429, or a timeout did **not** successfully generate the contract.

### Other providers

DeepSeek, xAI/Grok, Groq, and OpenRouter are different services. A key for one provider is never sent to another, and explicit provider selection never falls through to another provider's credentials. Do not put keys in GitHub or client-side `VITE_*` variables.

The separate Groq/Qwen adapter remains available through `MODEL_PROVIDER=groq` and its own `GROQ_API_KEY`. The legacy OpenRouter adapter uses `MODEL_PROVIDER=openrouter` and `OPENROUTER_API_KEY`. Select another OpenAI-compatible chat endpoint explicitly with:

```text
MODEL_PROVIDER=generic
MODEL_BASE_URL=https://your-model-provider.example/v1
MODEL_NAME=the-exact-model-id
MODEL_API_KEY=your-provider-key-if-required
```

The provider receives only the proposed contract and up to two public code evidence excerpts; source code is never executed. Model suggestions always require a developer's review and approval before generating mocks.

An optional server-side `GITHUB_TOKEN` increases GitHub API allowance; the scanner still rejects private repositories. Anonymous GitHub scans are rate limited.

## Development and teammate handoff

```text
frontend/src/
  App.tsx           repository, navigation, results and browser-local review state
  components.tsx    evidence, contract editor, mock playground and export
  types.ts          shared frontend types and API client
  styles.css        responsive workspace design
backend/
  app.py            FastAPI HTTP entrypoint
  main.py           scan pipeline + local CLI adapter
  github_source.py  bounded public GitHub source retrieval
  detect.py         deterministic call and route detection
  attribute.py      CODEOWNERS hints
  contract.py       schema proposals + optional model adapter + OpenAPI
  unblock.py        stateless mock URLs and portable code generation
  schema.py         validated shared Pydantic request/response models
  demo_repo/        intentionally incomplete React + FastAPI fixture
  tests/            detector and full API/export flow checks
schema.md           integration contract and field meanings
vercel.json         services and routing
```

Suggested handoff boundaries: scanner/ownership in `detect.py` + `github_source.py`; model integration in `contract.py`; mocks/backend in `unblock.py` + `app.py`; frontend in `frontend/src`. Agree on [schema.md](schema.md) before changing the JSON shape.

```bash
source .venv/bin/activate
python -m unittest discover -s backend/tests -v
npm run build

# Scanner CLI: demo, local directory, or public GitHub URL
python -m backend.main
python -m backend.main /absolute/path/to/project
python -m backend.main https://github.com/owner/repository
```

## Prototype boundaries

- Browser-local scan/approval state; no shared team database, authentication or synchronized teammate sign-off.
- On-demand scans; no continuous GitHub monitoring, webhook, notifications or automatic PR writes.
- Static root-relative calls only. Arbitrary wrapper logic, re-export chains, default-imported custom clients, computed origins, external API hosts, generated clients and non-FastAPI backends need manual review. Unsupported detected patterns produce coverage notes. **Zero detected calls does not prove there are no APIs.** Zero-call or zero-route scans expand their coverage notes in the UI.
- Scan limits: 80 eligible files, 100 KB per file, 2 MB total, 48-second request budget. JavaScript and Python sources share the file budget so an alphabetically earlier backend cannot crowd out every frontend file. Tests, fixtures, example folders, vendored dependencies and build outputs are excluded. Truncated/unreadable scans show coverage notes.
- Simple CODEOWNERS rules provide hints; this is not Git blame, a runtime dependency graph or a full GitHub ownership resolver.
- Contract inference is provisional. Types of variable request values, optional fields, authentication, error responses and pagination require agreement. Field shape validation does not prove business correctness.
- Mock endpoints support GET/POST/PUT/PATCH/DELETE. They return one synthetic success example, not a database or an implementation of backend behavior. The exported skeleton intentionally returns 501 until implemented.
- Mock URLs contain compressed contract/example data. They remain usable across cold starts without server storage, and anyone with a URL can read that synthetic example. Use small examples; never include secrets or private data.
- The JSON Schema editor accepts a bounded subset: `type`, `properties`, `required`, `items`, `enum`, `description` and `additionalProperties`; remote references are rejected.

MIT licensed. Built for the MLH Hacktoberfest collaboration repository.
