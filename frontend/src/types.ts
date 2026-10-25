export type Method =
  | "GET"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE"
  | "HEAD"
  | "OPTIONS";
export type Status = "missing" | "mismatch" | "matched";
export interface Evidence {
  file: string;
  line: number;
  snippet: string;
  url: string | null;
}
export interface Endpoint {
  id: string;
  method: Method;
  path: string;
  status: Status;
  callers: Evidence[];
  backend: Evidence | null;
  available_methods: string[];
  frontend_owner: string | null;
  backend_owner: string | null;
  request_fields: Record<string, string>;
  response_fields: Record<string, string>;
  response_is_array: boolean;
}
export interface Scan {
  scan_id: string;
  repository: {
    name: string;
    full_name: string;
    url: string;
    branch: string;
    commit: string;
    demo: boolean;
  };
  scanned_at: string;
  duration_ms: number;
  stats: {
    files: number;
    calls: number;
    routes: number;
    matched: number;
    review: number;
  };
  endpoints: Endpoint[];
  warnings: string[];
  scope: string;
}
export interface Contract {
  endpoint_id: string;
  method: Method;
  path: string;
  title: string;
  engine: string;
  request_schema: Record<string, unknown> | null;
  response_schema: Record<string, unknown>;
  response_example: unknown;
  questions: string[];
}
export interface Mock {
  fingerprint: string;
  method: Method;
  path: string;
  url: string;
  response_example: unknown;
  request_example: unknown;
  files: { name: string; content: string }[];
}
export interface ContractRecord {
  draft: Contract;
  mock?: Mock;
  warnings?: string[];
}
export type Records = Record<string, ContractRecord>;
export type Section = "overview" | "scanner" | "contracts" | "playground";

export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(
      "The server did not return JSON. Please try again shortly.",
    );
  }
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg || "Invalid contract")
              .join(" ")
          : "Something went wrong. Please try again.",
    );
  }
  return result as T;
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
export function saveFile(
  name: string,
  data: BlobPart,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function loadStored<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
export function storeLocal(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* The app also works with browser storage disabled. */
  }
}
