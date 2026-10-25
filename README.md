# TritonTeam

**Find the missing link between your frontend and backend. Keep building, together.**

An API collaboration prototype for Hacktoberfest. Paste a public GitHub repository, inspect potential frontend/backend interface gaps, review a proposed contract, and generate a runnable mock so the frontend can keep moving while the backend is implemented.

**Detect → Follow the evidence → Agree on a contract → Unblock → Verify**

## What works

- Public GitHub scanning at an immutable commit; source code is read, never executed.
- Literal root-relative React/JS/TS `fetch` and `axios.get/post/put/patch/delete` calls, including simple template path parameters.
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

## Optional AI: Groq + Qwen 3.8 27B

The scanner, review workflow, and runnable mocks work without any model credentials, using **Schema inference**. They must not be described as LLM-powered unless `/api/contract` actually returns a model-backed result.

### Recommended Groq setup for TritonTeam

Groq's [supported models](https://console.groq.com/docs/models) include `qwen/qwen3.8-27b` (preview). Its [free plan](https://console.groq.com/docs/rate-limits) offers a limited number of calls, subject to account-specific limits and model availability. It is not unlimited free computing.

1. Create an API key at [Groq Console → API Keys](https://console.groq.com/keys).
2. In **Vercel → tritonteam-hacktoberfest → Settings → Environment Variables**, add:
   - `MODEL_PROVIDER=groq` as a **Config** variable for **Production**.
   - `GROQ_API_KEY=<your Groq key>` as a **Secret** variable for **Production**.
3. Save, then **redeploy Production** to load the new variables.

These variables select `https://api.groq.com/openai/v1` and `qwen/qwen3.8-27b` automatically. When `MODEL_PROVIDER=groq`, existing Hugging Face / OpenRouter keys are **not used**. You do not need to delete legacy variables, and a Groq key is never sent to another provider. Do not store keys in GitHub or client-side `VITE_*` variables.

The backend requests **JSON Object Mode** with Qwen non-thinking inference (`reasoning_effort=none`), then validates every contract with Pydantic and JSON Schema; detected method, path and endpoint ID cannot be changed by a model. The API returns `Schema inference` with a warning when Groq is unavailable, its key is absent, or the output is invalid.

**How to verify actual AI inference:** `GET /api/health` should report `model_configured: true` and `engine: "qwen/qwen3.8-27b"`; this only verifies configuration. Run a proposal in the UI or `POST /api/contract` and check `contract.engine: "Model: qwen/qwen3.8-27b"` and `warnings: []`. A configured model that responds with 401, 429 or 402 did **not** successfully generate the contract.

### Alternative open-weight endpoints

To use another OpenAI-compatible model, clear or unset `MODEL_PROVIDER` and `GROQ_API_KEY`. The legacy OpenRouter key, if present, takes priority over generic `MODEL_*` settings. Without either provider's key, the optional generic endpoint is selected through:

```text
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
- Root-relative literal calls only. Custom HTTP clients, computed URLs, base-URL-dependent/external calls, generated clients and non-FastAPI backends need manual review. Unsupported detected patterns produce coverage notes.
- Scan limits: 80 eligible files, 100 KB per file, 2 MB total, 48-second request budget. Tests, fixtures, example folders, vendored dependencies and build outputs are excluded. Truncated/unreadable scans show coverage notes.
- Simple CODEOWNERS rules provide hints; this is not Git blame, a runtime dependency graph or a full GitHub ownership resolver.
- Contract inference is provisional. Types of variable request values, optional fields, authentication, error responses and pagination require agreement. Field shape validation does not prove business correctness.
- Mock endpoints support GET/POST/PUT/PATCH/DELETE. They return one synthetic success example, not a database or an implementation of backend behavior. The exported skeleton intentionally returns 501 until implemented.
- Mock URLs contain compressed contract/example data. They remain usable across cold starts without server storage, and anyone with a URL can read that synthetic example. Use small examples; never include secrets or private data.
- The JSON Schema editor accepts a bounded subset: `type`, `properties`, `required`, `items`, `enum`, `description` and `additionalProperties`; remote references are rejected.

MIT licensed. Built for the MLH Hacktoberfest collaboration repository.
