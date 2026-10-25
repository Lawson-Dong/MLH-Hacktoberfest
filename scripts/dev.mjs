// One development entrypoint for both services, supervised as a single preview.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
const root = fileURLToPath(new URL("../", import.meta.url));
const python = existsSync(resolve(root, ".venv/bin/python"))
  ? resolve(root, ".venv/bin/python")
  : "python";
const backend = spawn(
  python,
  ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000"],
  { cwd: root, stdio: "inherit" },
);
const frontend = spawn(
  "npm",
  [
    "--prefix",
    "frontend",
    "run",
    "dev",
    "--",
    "--port",
    process.env.PORT || "5173",
    ...process.argv.slice(2),
  ],
  { cwd: root, stdio: "inherit" },
);
function stop() {
  backend.kill("SIGTERM");
  frontend.kill("SIGTERM");
}
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    stop();
    process.exit(0);
  });
for (const child of [backend, frontend])
  child.on("exit", (code) => {
    stop();
    process.exit(code || 0);
  });
