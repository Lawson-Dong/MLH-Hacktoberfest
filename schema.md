# TritonTeam integration contract (v0.1)

All requests/responses are JSON except `/api/export` (ZIP). The FastAPI entrypoint is `backend/app.py`; canonical models live in `backend/schema.py` and frontend types in `frontend/src/types.ts`.

The server is stateless. `POST /api/scan` returns a completed scan in the same request; there is no in-memory asynchronous job registry or GET-by-scan-ID API. `scan_id` identifies the repository/commit snapshot. Browser-local state is keyed by repository, commit and endpoint ID.

## Routes

| Method | Path                                      | Request                              | Response                                                  |
| ------ | ----------------------------------------- | ------------------------------------ | --------------------------------------------------------- |
| GET    | `/api/health`                             | none                                 | `{status,version,model_configured,engine}`                |
| GET    | `/api/demo`                               | none                                 | `Scan` using the checked-in fixture and the real detector |
| POST   | `/api/scan`                               | `{repo_url:string}`                  | `Scan` at an immutable GitHub commit                      |
| POST   | `/api/contract`                           | `{endpoint:Endpoint}`                | `{contract:Contract,warnings:string[]}`                   |
| POST   | `/api/mock`                               | `{contract:Contract,approved:true}`  | `Mock` (409 if approval is false/missing)                 |
| POST   | `/api/export`                             | `{contract:Contract,approved:true}`  | `application/zip`, the approved portable bundle           |
| POST   | `/api/verify`                             | `{contract:Contract,response:any}`   | `{valid:boolean,errors:[{path,message}]}`                 |
| varies | `/api/playground/{token}/{endpoint_path}` | approved method + optional JSON body | actual synthetic JSON response                            |
| GET    | `/api/docs`                               | none                                 | interactive API documentation                             |

Scan errors use `{detail:string}` with 400 invalid URL, 404 public repository not found, 429 GitHub allowance, 502 upstream error or 504 scan timeout. Validation errors use FastAPI's 422 detail array. Clients must display the actual error and retain any previous result with clear context.

## Scan

```ts
{
  scan_id: string;
  repository: {
    name: string; full_name: string; url: string;
    branch: string; commit: string; demo: boolean;
  };
  scanned_at: string; // UTC ISO timestamp
  duration_ms: number;
  stats: { files: number; calls: number; routes: number; matched: number; review: number };
  endpoints: Endpoint[];
  warnings: string[]; // incomplete reads / unsupported detected syntax / truncated scope
  scope: string;
}
```

`calls` counts **unique method + normalized path pairs**, not all call sites. `routes` counts supported statically mounted backend routes. `matched` means path + method exist, not that payload semantics have been verified. `review` includes missing and method-mismatched endpoints.

## Endpoint

```ts
{
  id: string; // stable hash of method + parameter-normalized path
  method: 'GET'|'POST'|'PUT'|'PATCH'|'DELETE'|'HEAD'|'OPTIONS';
  path: string; // /api/projects/{projectId}/tasks
  status: 'missing'|'mismatch'|'matched';
  callers: Evidence[];
  backend: Evidence|null;
  available_methods: string[];
  frontend_owner: string|null;
  backend_owner: string|null;
  request_fields: Record<string, 'string'|'number'|'boolean'>;
  response_fields: Record<string, 'string'|'number'|'boolean'>;
  response_is_array: boolean;
}
```

Evidence: `{file:string,line:number,snippet:string,url:string|null}`. Line numbers are 1-based. GitHub URLs use the scan's exact commit. Bundled demo evidence uses fixture file names and no fabricated source URL. For a `missing` endpoint, `backend` may be the closest route as **context**, not an implementation or ownership proof. `*_owner` values come from supported CODEOWNERS patterns; otherwise null.

## Contract

```ts
{
  endpoint_id: string;
  method: string; path: string; title: string;
  engine: string; // "Schema inference" or the configured model's name
  request_schema: JSONSchema|null;
  response_schema: JSONSchema;
  response_example: unknown;
  questions: string[]; // assumptions for a human to resolve
}
```

The response example must validate against the schema. Schemas are limited in size/depth, cannot use external references or arbitrary regexes, and cannot execute source code. The contract editor edits request/response schema and example while retaining detected method/path/endpoint identity. Accepting a changed draft creates a new fingerprint and mock URL; edits clear the prior mock approval in the UI.

Approval is an explicit user acknowledgement in this prototype, not an authenticated team signature. The stateless API cannot prove who clicked it.

## Mock

```ts
{
  fingerprint: string;
  method: string;
  path: string;
  url: string; // same-origin, self-contained /api/playground/... path
  response_example: unknown;
  request_example: unknown | null;
  files: Array<{ name: string; content: string }>;
}
```

Mock path/method/request fields are checked before returning the example. Incorrect methods return 405, invalid request bodies 422, invalid tokens/paths 404. Generated bundles include `openapi.json`, `mock_server.py`, `backend_skeleton.py`, `handlers.ts`, `requirements.txt`, and `README.md`. The Pydantic skeleton has the approved fields and intentionally returns 501 until the backend owner implements it.
