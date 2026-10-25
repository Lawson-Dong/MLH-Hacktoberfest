"""CODEOWNERS hints are ownership signals, not proof that a person caused a blocker."""
import fnmatch


def owner_for(path: str, files) -> str | None:
    by_path = {file.path: file.content for file in files}
    content = next((by_path[name] for name in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS") if name in by_path), "")
    owner = None
    for line in content.splitlines():
        parts = line.split("#", 1)[0].split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        if pattern.startswith("!") or "[" in pattern:
            continue  # Not supported by GitHub's CODEOWNERS syntax either.
        rooted = pattern.startswith("/")
        pattern = pattern.lstrip("/")
        if pattern.endswith("/"):
            matched = path.startswith(pattern) if rooted or "/" in pattern.rstrip("/") else pattern.rstrip("/") in path.split("/")[:-1]
        elif rooted or "/" in pattern:
            matched = fnmatch.fnmatchcase(path, pattern)
        else:
            matched = any(fnmatch.fnmatchcase(part, pattern) for part in path.split("/"))
        if matched:
            owner = ", ".join(parts[1:])
    return owner
