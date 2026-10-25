"""Bounded public GitHub reads at an immutable commit. Never clone or run code."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit

import httpx

MAX_FILES = 80
MAX_FILE_BYTES = 100_000
MAX_TOTAL_BYTES = 2_000_000
IGNORED = {"node_modules", ".git", ".venv", "venv", "env", "dist", "build", ".next", "coverage", "vendor", "__pycache__", "tests", "__tests__", "fixtures", "demo_repo", "examples"}


class SourceError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message, self.status = message, status


@dataclass
class SourceFile:
    path: str
    content: str


def parse_repo_url(value: str) -> tuple[str, str]:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise SourceError("Paste a public repository URL such as https://github.com/owner/repository.")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        raise SourceError("Use the repository URL, without /tree, /blob or a file path.")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in {".", ".."}:
        raise SourceError("That GitHub owner or repository name is invalid.")
    return owner, repo


def is_source(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if set(parts) & IGNORED or any(p.startswith(".") for p in parts[:-1] if p not in {".github"}):
        return path in {".github/CODEOWNERS"}
    return (path.endswith((".py", ".tsx", ".jsx", ".ts", ".js")) and not re.search(r"\.(test|spec)\.[jt]sx?$", path)) or path in {"CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"}


async def fetch_repository(value: str) -> tuple[dict, list[SourceFile], list[str]]:
    owner, name = parse_repo_url(value)
    repo_path = f"{owner}/{name}"
    warnings: list[str] = []
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "TritonTeam-MVP", "X-GitHub-Api-Version": "2022-11-28"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), follow_redirects=False) as client:
        async def api(path: str) -> dict:
            try:
                response = await client.get(f"https://api.github.com/repos/{repo_path}{path}", headers=headers)
            except httpx.HTTPError as exc:
                raise SourceError("GitHub could not be reached. Try the demo or scan again shortly.", 502) from exc
            if response.status_code == 404:
                raise SourceError("Repository not found. This version scans public repositories only.", 404)
            if response.status_code in {403, 429}:
                raise SourceError("GitHub's request limit was reached. Try again later or configure a server-side GitHub token.", 429)
            if response.status_code != 200:
                raise SourceError(f"GitHub returned HTTP {response.status_code}. Try the canonical repository URL.", 502)
            return response.json()

        metadata = await api("")
        if metadata.get("private"):
            raise SourceError("Private repository scanning is outside this MVP's scope.", 403)
        branch = metadata.get("default_branch", "main")
        commit = await api(f"/commits/{quote(branch, safe='')}")
        sha = commit["sha"]
        tree = await api(f"/git/trees/{sha}?recursive=1")
        if tree.get("truncated"):
            warnings.append("GitHub truncated the repository tree. Findings cover only the returned files.")
        candidates = sorted((item for item in tree.get("tree", []) if item.get("type") == "blob" and is_source(item["path"])), key=lambda item: ("CODEOWNERS" not in item["path"], item["path"]))
        oversized = [item for item in candidates if item.get("size", 0) > MAX_FILE_BYTES]
        if oversized:
            warnings.append(f"Skipped {len(oversized)} source files larger than 100 KB.")
        candidates = [item for item in candidates if item.get("size", 0) <= MAX_FILE_BYTES]
        chosen, total_bytes = [], 0
        for item in candidates:
            if len(chosen) >= MAX_FILES or total_bytes + item.get("size", 0) > MAX_TOTAL_BYTES:
                continue
            chosen.append(item)
            total_bytes += item.get("size", 0)
        if len(chosen) < len(candidates):
            warnings.append(f"Scan limited to {len(chosen)} of {len(candidates)} eligible files (80 files / 2 MB maximum).")
        semaphore = asyncio.Semaphore(8)

        async def read(item: dict) -> SourceFile | None:
            async with semaphore:
                try:
                    # Raw reads avoid using a GitHub API request for every source file.
                    url = f"https://raw.githubusercontent.com/{repo_path}/{sha}/{quote(item['path'], safe='/')}"
                    async with client.stream("GET", url, headers={"User-Agent": "TritonTeam-MVP"}) as response:
                        if response.status_code != 200:
                            warnings.append(f"Could not read {item['path']} (HTTP {response.status_code}).")
                            return None
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_FILE_BYTES:
                                warnings.append(f"Skipped oversized source file {item['path']}.")
                                return None
                    return SourceFile(item["path"], bytes(data).decode("utf-8"))
                except (httpx.HTTPError, UnicodeError):
                    warnings.append(f"Could not read {item['path']}.")
                    return None

        files = [item for item in await asyncio.gather(*(read(item) for item in chosen)) if item is not None]
    return {"name": name, "full_name": repo_path, "url": f"https://github.com/{repo_path}", "branch": branch, "commit": sha, "demo": False}, files, warnings
