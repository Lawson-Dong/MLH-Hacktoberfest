"""Pipeline orchestration; all entrypoints use the same detector."""
import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .detect import detect
    from .github_source import SourceFile, fetch_repository
except ImportError:
    from detect import detect
    from github_source import SourceFile, fetch_repository


def scan_files(repo: dict, files: list[SourceFile], warnings: list[str] | None = None) -> dict:
    start = time.perf_counter()
    warnings = list(warnings or [])
    endpoints, routes = detect(files, repo, warnings)
    matched = sum(endpoint.status == "matched" for endpoint in endpoints)
    return {"scan_id": hashlib.sha256((repo["full_name"] + repo["commit"]).encode()).hexdigest()[:16], "repository": repo,
        "scanned_at": datetime.now(timezone.utc).isoformat(), "duration_ms": round((time.perf_counter() - start) * 1000),
        "stats": {"files": len(files), "calls": len(endpoints), "routes": len(routes), "matched": matched, "review": len(endpoints) - matched},
        "endpoints": [endpoint.model_dump() for endpoint in endpoints], "warnings": list(dict.fromkeys(warnings))[:30],
        "scope": "Literal root-relative fetch/axios calls and statically mounted FastAPI routes. Other frameworks, wrappers and business/schema compatibility need manual review."}


def demo_scan() -> dict:
    root = Path(__file__).parent / "demo_repo"
    # Deployment runtimes may precompile every .py file, including the fixture.
    # Restrict inputs to fixture source instead of decoding generated .pyc files.
    files = [SourceFile(str(path.relative_to(root)), path.read_text())
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
        and (path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"} or path.name == "CODEOWNERS")]
    digest = hashlib.sha256("".join(file.content for file in files).encode()).hexdigest()
    return scan_files({"name": "campus-connect", "full_name": "demo/campus-connect", "url": "https://github.com/Lawson-Dong/MLH-Hacktoberfest", "branch": "demo", "commit": digest, "demo": True}, files)


async def scan_repository(url: str) -> dict:
    start = time.perf_counter()
    repo, files, warnings = await fetch_repository(url)
    result = scan_files(repo, files, warnings)
    result["duration_ms"] = round((time.perf_counter() - start) * 1000)
    return result


def run(repo_path: str) -> dict:
    """Local CLI adapter for teammates' scanner/integration work."""
    try:
        from .github_source import is_source
    except ImportError:
        from github_source import is_source
    root = Path(repo_path).resolve()
    files = [SourceFile(str(path.relative_to(root)), path.read_text()) for path in sorted(root.rglob("*")) if path.is_file() and is_source(str(path.relative_to(root))) and path.stat().st_size <= 100000][:80]
    return scan_files({"name": root.name, "full_name": f"local/{root.name}", "url": "", "branch": "local", "commit": "local", "demo": True}, files)


if __name__ == "__main__":
    import sys
    print(json.dumps(asyncio.run(scan_repository(sys.argv[1])) if len(sys.argv) > 1 and sys.argv[1].startswith("https://") else run(sys.argv[1]) if len(sys.argv) > 1 else demo_scan(), indent=2))
