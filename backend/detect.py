"""Conservative literal-call scanning plus Python AST route extraction.

This is intentionally bounded static analysis, not a general JS or Python interpreter.
Every finding retains its source location; unsupported syntax lowers scan coverage.
"""
from __future__ import annotations

import ast
import hashlib
import re
import posixpath
from collections import defaultdict
from urllib.parse import quote

try:
    from .attribute import owner_for
    from .schema import Endpoint, Evidence
except ImportError:
    from attribute import owner_for
    from schema import Endpoint, Evidence

METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def normalize(path: str) -> str:
    path = path.split("?", 1)[0].split("#", 1)[0]
    path = re.sub(r"\$\{\s*([A-Za-z_$][\w$]*)\s*\}", r"{\1}", path)
    return path.rstrip("/") or "/"


def canonical(path: str) -> str:
    return re.sub(r"\{[^{}]+\}", "{}", normalize(path))


def evidence(file, offset: int, repo: dict, *, line: int | None = None) -> Evidence:
    lines = file.content.splitlines()
    line = line or file.content.count("\n", 0, offset) + 1
    start, end = max(0, line - 2), min(len(lines), line + 5)
    snippet = "\n".join(f"{i + 1:>3}  {lines[i]}" for i in range(start, end))[:5000]
    url = f"{repo['url']}/blob/{repo['commit']}/{quote(file.path, safe='/')}#L{line}" if not repo.get("demo") else None
    return Evidence(file=file.path, line=line, snippet=snippet, url=url)


def js_source(text: str) -> tuple[str, list[bool]]:
    """Blank comments, keep offsets, and mark string interiors as non-code."""
    chars, code = list(text), [True] * len(text)
    i = 0
    while i < len(text):
        if text[i] in "'\"`":
            delimiter, start = text[i], i
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == delimiter:
                    i += 1
                    break
                else:
                    i += 1
            for j in range(start, min(i, len(text))):
                code[j] = False
        elif text.startswith("//", i) or text.startswith("/*", i):
            block = text.startswith("/*", i)
            stop = text.find("*/" if block else "\n", i + 2)
            stop = len(text) if stop < 0 else stop + (2 if block else 0)
            for j in range(i, stop):
                if chars[j] != "\n":
                    chars[j] = " "
                code[j] = False
            i = stop
        else:
            i += 1
    return "".join(chars), code


def call_end(source: str, opening: int) -> int:
    depth, delimiter, i = 0, None, opening
    while i < min(len(source), opening + 6000):
        char = source[i]
        if delimiter:
            if char == "\\":
                i += 2
                continue
            if char == delimiter:
                delimiter = None
        elif char in "'\"`":
            delimiter = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return min(len(source), opening + 6000)


def response_shape(source: str, path: str) -> tuple[dict[str, str], bool]:
    segments = [part for part in path.split("/") if part and not part.startswith("{")]
    resource = segments[-1].replace("-", "").replace("_", "").lower() if segments else ""
    singular = resource[:-3] + "y" if resource.endswith("ies") else resource.rstrip("s")
    for match in re.finditer(r"(?:interface\s+(\w+)|type\s+(\w+)\s*=)\s*\{([^{}]{0,3000})\}", source):
        name = (match.group(1) or match.group(2)).lower()
        if name not in {resource, singular, singular + "response", resource + "response"}:
            continue
        fields = {field.group(1): {"number": "number", "boolean": "boolean"}.get(field.group(2), "string") for field in re.finditer(r"\b(\w+)\??\s*:\s*(string|number|boolean)\b", match.group(3))}
        return dict(list(fields.items())[:40]), bool(path.endswith(segments[-1]) and resource.endswith("s"))
    return {}, False


def object_parts(value: str) -> list[str] | None:
    """Return only top-level properties, without treating nested method fields as HTTP options."""
    value = value.strip()
    if not value.startswith("{"):
        return None
    depth, delimiter, start, i, parts = 0, None, 1, 0, []
    while i < len(value):
        char = value[i]
        if delimiter:
            if char == "\\":
                i += 2
                continue
            if char == delimiter:
                delimiter = None
        elif char in "'\"`":
            delimiter = char
        elif char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
            if depth == 0:
                parts.append(value[start:i].strip())
                return parts
        elif char == "," and depth == 1:
            parts.append(value[start:i].strip())
            start = i + 1
        i += 1
    return None


def arguments(value: str) -> list[str] | None:
    # Reuse the balanced object splitter for call arguments and concatenations.
    parts = object_parts("{" + value + "}")
    return [part for part in parts if part] if parts is not None else None


def static_url(value: str, constants: dict[str, str], stack=()) -> str | None:
    """Resolve bounded local constants, concatenations and simple path parameters."""
    value = value.strip()
    if len(stack) > 8 or len(value) > 3000:
        return None
    if re.fullmatch(r"[A-Za-z_$][\w$]*", value):
        if value in stack or value not in constants:
            return None
        return static_url(constants[value], constants, (*stack, value))
    # Split + only outside strings. Unknown identifiers are path parameters only
    # after a resolved prefix; never invent an unknown origin or base URL.
    pieces, start, delimiter, i = [], 0, None, 0
    while i < len(value):
        char = value[i]
        if delimiter:
            if char == "\\":
                i += 2
                continue
            if char == delimiter:
                delimiter = None
        elif char in "'\"`":
            delimiter = char
        elif char == "+":
            pieces.append(value[start:i].strip())
            start = i + 1
        i += 1
    if pieces:
        pieces.append(value[start:].strip())
        result = ""
        for piece in pieces:
            part = static_url(piece, constants, stack)
            if part is None and result.endswith("/") and re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", piece):
                part = "{" + piece.replace(".", "_") + "}"
            if part is None:
                return None
            result += part
        return result
    if len(value) < 2 or value[0] not in "'\"`" or value[-1] != value[0] or "\\" in value:
        return None
    if value[0] != "`":
        return value[1:-1] if value[0] not in value[1:-1] else None
    result = value[1:-1]
    def substitute(match):
        expression = match.group(1).strip()
        resolved = static_url(expression, constants, stack)
        if resolved is not None:
            return resolved
        if re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", expression):
            return "{" + expression.replace(".", "_") + "}"
        return match.group(0)
    result = re.sub(r"\$\{([^{}]+)\}", substitute, result)
    return None if "${" in result else result


def client_bindings(files):
    """Trace simple local fetch wrappers and Axios instances through relative imports.

    Names alone never establish that a function is an HTTP client. Unsupported
    wrappers remain unresolved rather than guessing their URL or method.
    """
    modules = {}
    for file in files:
        if not file.path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
            continue
        source, positions = js_source(file.content)
        constants, duplicate_constants, shadows = {}, set(), set()
        for match in re.finditer(r"\bconst\s+([A-Za-z_$][\w$]*)(?:\s*:\s*[^=;\n]+)?\s*=\s*([^;\n]+)", source):
            if positions[match.start()]:
                if match[1] in constants:
                    duplicate_constants.add(match[1])
                constants[match[1]] = match[2].strip()
        clients = {"axios": ("axios", "")}
        for match in re.finditer(r"\bimport\s+(\w+)\s+from\s*['\"]axios['\"]", source):
            if positions[match.start()]:
                clients[match[1]] = ("axios", "")
        aliases = "|".join(re.escape(name) for name in clients)
        for match in re.finditer(rf"\bconst\s+(\w+)\s*=\s*(?:{aliases})\.create\s*\(", source):
            if not positions[match.start()]:
                continue
            context = source[match.end():call_end(source, match.end() - 1) - 1]
            parts = object_parts(context)
            if parts is None or any(part.startswith("...") for part in parts):
                continue
            base_prop = next((part.split(":", 1)[1] for part in parts if re.match(r"(?:baseURL|['\"]baseURL['\"])\s*:", part)), "''")
            clients[match[1]] = ("axios", static_url(base_prop, constants))
        ranges = []
        signature = re.compile(
            r"\bfunction\s+(?P<name>\w+)\s*(?:<[^()]{1,300}>)?\s*\((?P<params>[^()]*)\)\s*(?::[^{};=]+)?\{"
            r"|\bconst\s+(?P<arrow>\w+)\s*=\s*(?:async\s*)?(?:<[^()]{1,300}>)?\s*\((?P<arrow_params>[^()]*)\)\s*(?::[^{};=]+)?=>\s*(?P<brace>\{)?")
        for match in signature.finditer(source):
            if not positions[match.start()]:
                continue
            name = match["name"] or match["arrow"]
            expression = bool(match["arrow"] and not match["brace"])
            if expression:
                fetch_start = re.match(r"fetch\s*\(", source[match.end():])
                if not fetch_start:
                    continue
                end = call_end(source, match.end() + fetch_start.end() - 1)
            else:
                depth, end = 1, match.end()
                while end < min(len(source), match.end() + 12000) and depth:
                    if positions[end]:
                        depth += (source[end] == "{") - (source[end] == "}")
                    end += 1
                if depth:
                    continue
            params = [re.match(r"\s*(\w+)", part) for part in (arguments(match["params"] or match["arrow_params"] or "") or [])]
            if not params or not all(params):
                continue
            names = [param[1] for param in params]
            shadows.update(names)
            if any("=" in part and not re.search(r"=\s*(?:\{\}|undefined)\s*$", part) for part in (arguments(match["params"] or match["arrow_params"] or "") or [])):
                continue
            body = source[match.end():end if expression else end - 1]
            fetches = list(re.finditer(r"(?<![\w$.])fetch\s*\(", body))
            fetches = [item for item in fetches if positions[match.end() + item.start()]]
            if len(fetches) != 1:
                continue
            fetch = fetches[0]
            fetch_args = arguments(body[fetch.end():call_end(body, fetch.end() - 1) - 1])
            if not fetch_args or fetch_args[0] != names[0]:
                continue
            options = fetch_args[1] if len(fetch_args) > 1 else "{}"
            if len(names) > 1 and options == names[1]:
                spec = ("options", "")
            else:
                parts = object_parts(options)
                if parts is None or any(part.startswith("...") for part in parts):
                    continue
                method_props = [part.split(":", 1)[1].strip() for part in parts if re.match(r"(?:method|['\"]method['\"])\s*:", part)]
                if "method" in parts:
                    continue
                method = method_props[-1] if method_props else "'GET'"
                literal = re.fullmatch(r"['\"](GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)['\"]", method, re.I)
                conditional = re.fullmatch(rf"{re.escape(names[1])}\s*===\s*undefined\s*\?\s*['\"]GET['\"]\s*:\s*['\"]POST['\"]", method) if len(names) > 1 else None
                if literal:
                    spec = ("fixed", literal[1].upper())
                elif conditional:
                    spec = ("body", "")
                else:
                    continue
            # Do not infer wrappers that conditionally call fetch or reassign URL/method inputs.
            before = body[:fetch.start()]
            if re.search(r"\b(if|switch|for|while)\s*\(", before) or any(re.search(rf"\b{re.escape(name)}\s*=(?!=)", body) for name in names):
                continue
            clients[name] = spec
            ranges.append((match.start(), match.end()))
            ranges.append((match.end() + fetch.start(), match.end() + call_end(body, fetch.end() - 1)))
        for match in re.finditer(r"\b(\w+)\s*=>", source):
            if positions[match.start()]:
                shadows.add(match[1])
        constants = {name: value for name, value in constants.items() if name not in duplicate_constants | shadows}
        modules[file.path] = {"source": source, "positions": positions, "constants": constants, "clients": clients, "ranges": ranges, "shadows": shadows}
    for path, data in modules.items():
        source, positions = data["source"], data["positions"]
        for match in re.finditer(r"\bimport\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", source):
            if not positions[match.start()] or not match[2].startswith("."):
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), match[2]))
            targets = [target] if target in modules else [target + ext for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")] + [target + "/index" + ext for ext in (".ts", ".js")]
            imported = next((modules[item] for item in targets if item in modules), None)
            if imported:
                for entry in match[1].split(","):
                    names = re.fullmatch(r"\s*(\w+)(?:\s+as\s+(\w+))?\s*", entry)
                    if names and names[1] in imported["clients"] and re.search(rf"\bexport\s+(?:async\s+)?(?:function|const)\s+{re.escape(names[1])}\b", imported["source"]):
                        data["clients"][names[2] or names[1]] = imported["clients"][names[1]]
        for name in data["shadows"]:
            data["clients"].pop(name, None)
    return modules


def frontend_calls(files, repo: dict, warnings: list[str]) -> list[dict]:
    calls = []
    modules = client_bindings(files)
    for file in files:
        if file.path not in modules:
            continue
        data = modules[file.path]
        source, positions, clients = data["source"], data["positions"], data["clients"]
        names = ["fetch"] + [re.escape(name) + (r"\.(?:get|post|put|patch|delete|head|options)" if kind == "axios" else "") for name, (kind, _) in clients.items()]
        pattern = re.compile(r"(?<![\w$.])(?P<client>" + "|".join(names) + r")\s*(?:<[^()]{1,500}>)?\s*\(")
        for match in pattern.finditer(source):
            if not positions[match.start()] or any(start <= match.start() < end for start, end in data["ranges"]):
                continue
            arg_start = match.end()
            context = source[arg_start:call_end(source, match.end() - 1) - 1]
            args = arguments(context)
            path = static_url(args[0], data["constants"]) if args else None
            if path is None:
                warnings.append(f"Unresolved dynamic API URL at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                continue
            client = match.group("client")
            kind, setting = clients.get(client.split(".")[0], ("options", ""))
            if kind == "axios":
                if setting is None:
                    warnings.append(f"Unresolved Axios baseURL at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                    continue
                if setting:
                    path = setting.rstrip("/") + "/" + path.lstrip("/") if not path.startswith(("http:", "https:", "//")) else path
            if not path.startswith("/") or path.startswith("//"):
                warnings.append(f"External or base-URL-dependent call excluded at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                continue
            if "${" in re.sub(r"\$\{\s*[A-Za-z_$][\w$]*\s*\}", "{param}", path):
                warnings.append(f"Complex URL expression excluded at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                continue
            path = normalize(path)
            if not re.fullmatch(r"/[A-Za-z0-9_/{}/.\-]*", path):
                warnings.append(f"Unsupported URL syntax at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                continue
            method = "GET"
            if kind == "axios":
                method = client.split(".")[-1].upper()
            elif kind == "fixed":
                method = setting
            elif kind == "body" and len(args) > 1 and args[1] != "undefined":
                method = "POST"
            if kind == "body" and len(args) > 1 and args[1] != "undefined" and not args[1].startswith(("{", "[", "'", '"', "`")) and args[1] not in {"null", "true", "false"}:
                warnings.append(f"Unresolved wrapper HTTP method at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                continue
            if client == "fetch" or kind == "options":
                options = object_parts(args[1]) if len(args) > 1 and args[1] != "undefined" else []
                if options is None or any(part.startswith("...") for part in options):
                    warnings.append(f"Dynamic fetch options excluded at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                    continue
                method_prop = next((re.fullmatch(r"(?:method|['\"]method['\"])\s*:\s*(.*)", part, re.S) for part in reversed(options) if re.match(r"(?:method|['\"]method['\"])\s*:", part)), None)
                if "method" in options:
                    warnings.append(f"Dynamic fetch method excluded at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                    continue
                if method_prop:
                    method_literal = re.fullmatch(r"\s*['\"]([A-Za-z]+)['\"]\s*", method_prop.group(1))
                    if not method_literal or method_literal.group(1).lower() not in METHODS:
                        warnings.append(f"Dynamic or unsupported HTTP method excluded at {file.path}:{source.count(chr(10), 0, match.start()) + 1}.")
                        continue
                    method = method_literal.group(1).upper()
            request_fields = {}
            body = re.search(r"JSON\.stringify\s*\(\s*\{([^{}]{0,2000})\}", context, re.S)
            if kind in {"axios", "body"} and method in {"POST", "PATCH", "PUT"} and len(args) > 1:
                body = re.fullmatch(r"\s*\{([^{}]{0,2000})\}\s*", args[1], re.S) or body
            if body:
                for field in body.group(1).split(","):
                    prop = re.match(r"\s*([A-Za-z_]\w*)\s*(?::\s*(.*))?$", field.strip(), re.S)
                    if prop:
                        value = (prop.group(2) or "").strip()
                        request_fields[prop.group(1)] = "boolean" if value in {"true", "false"} else "number" if re.fullmatch(r"-?\d+(?:\.\d+)?", value) else "string"
            fields, is_array = response_shape(source, path)
            calls.append({"method": method, "path": path, "evidence": evidence(file, match.start(), repo), "request_fields": dict(list(request_fields.items())[:40]), "response_fields": fields, "response_is_array": is_array and method == "GET"})
    return calls


def backend_routes(files, repo: dict, warnings: list[str]) -> list[dict]:
    modules, nodes, includes = {}, {}, defaultdict(list)
    for file in files:
        if not file.path.endswith(".py"):
            continue
        module = file.path[:-3].replace("/", ".").removesuffix(".__init__")
        try:
            tree = ast.parse(file.content)
        except SyntaxError:
            warnings.append(f"Could not parse Python file {file.path}.")
            continue
        imports, constants = {}, {}
        for item in tree.body:
            if isinstance(item, ast.ImportFrom):
                base = module.split(".")[:-item.level] if item.level else []
                target = ".".join(base + ([item.module] if item.module else []))
                for alias in item.names:
                    imports[alias.asname or alias.name] = f"{target}.{alias.name}".strip(".")
            elif isinstance(item, ast.Import):
                for alias in item.names:
                    imports[alias.asname or alias.name] = alias.name
            elif isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = item.value.value
        modules[module] = {"file": file, "tree": tree, "imports": imports, "constants": constants}

    def text(node, data, default=None):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return data["constants"].get(node.id, default)
        return default

    def expr(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return expr(node.value) + "." + node.attr
        return ""

    for module, data in modules.items():
        for item in ast.walk(data["tree"]):
            if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                name = expr(item.value.func)
                root_name, *rest = name.split(".")
                imported = data["imports"].get(root_name, root_name) + ("." + ".".join(rest) if rest else "")
                kind = imported.split(".")[-1]
                if kind not in {"FastAPI", "APIRouter"} or not imported.startswith("fastapi."):
                    continue
                prefix_node = next((keyword.value for keyword in item.value.keywords if keyword.arg == "prefix"), None)
                prefix = text(prefix_node, data, "") if prefix_node is None else text(prefix_node, data)
                if prefix is None:
                    warnings.append(f"Dynamic router prefix excluded at {data['file'].path}:{item.lineno}.")
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        nodes[(module, target.id)] = {"kind": kind, "prefix": prefix, "routes": []}

    def resolve(module: str, target) -> tuple | None:
        name = expr(target)
        if (module, name) in nodes:
            return module, name
        root, *rest = name.split(".")
        full = modules[module]["imports"].get(root, root) + ("." + ".".join(rest) if rest else "")
        candidates = [key for key in nodes if full == ".".join(key) or ".".join(key).endswith("." + full)]
        return candidates[0] if len(candidates) == 1 else None

    for module, data in modules.items():
        for item in ast.walk(data["tree"]):
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "include_router":
                source = resolve(module, item.func.value)
                target = resolve(module, item.args[0]) if item.args else None
                prefix_node = next((keyword.value for keyword in item.keywords if keyword.arg == "prefix"), None)
                prefix = "" if prefix_node is None else text(prefix_node, data)
                if source and target and prefix is not None:
                    includes[source].append((target, prefix))
                else:
                    warnings.append(f"Unresolved router mount at {data['file'].path}:{item.lineno}.")
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in item.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr
                owner = resolve(module, decorator.func.value)
                if not owner or method not in METHODS | {"api_route"}:
                    continue
                path_node = decorator.args[0] if decorator.args else next((keyword.value for keyword in decorator.keywords if keyword.arg == "path"), None)
                path = text(path_node, data)
                if path is None:
                    warnings.append(f"Dynamic backend route excluded at {data['file'].path}:{decorator.lineno}.")
                    continue
                methods = [method.upper()]
                if method == "api_route":
                    methods_node = next((keyword.value for keyword in decorator.keywords if keyword.arg == "methods"), None)
                    if not isinstance(methods_node, (ast.List, ast.Tuple)):
                        warnings.append(f"Unresolved backend methods at {data['file'].path}:{decorator.lineno}.")
                        continue
                    methods = [value.value.upper() for value in methods_node.elts if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.lower() in METHODS]
                for http_method in methods:
                    nodes[owner]["routes"].append({"method": http_method, "path": path, "evidence": evidence(data["file"], 0, repo, line=decorator.lineno)})

    routes, mounted = [], set()

    def walk(key, prefix="", stack=()):
        if key in stack or nodes[key]["prefix"] is None:
            return
        mounted.add(key)
        prefix += nodes[key]["prefix"]
        routes.extend({**route, "path": normalize(prefix + route["path"])} for route in nodes[key]["routes"])
        for target, extra_prefix in includes[key]:
            walk(target, prefix + extra_prefix, (*stack, key))

    for key, node in nodes.items():
        if node["kind"] == "FastAPI":
            walk(key)
    if any(node["routes"] and key not in mounted for key, node in nodes.items()):
        warnings.append("Some APIRouter routes could not be traced to a FastAPI app and were excluded.")
    return routes


def detect(files, repo: dict, warnings: list[str]) -> tuple[list[Endpoint], list[dict]]:
    calls = frontend_calls(files, repo, warnings)
    routes = backend_routes(files, repo, warnings)
    if calls and not routes:
        warnings.append("No supported FastAPI routes were found. APIs may be implemented in another framework, service or repository.")
    if not calls:
        warnings.append("No supported frontend API calls were found. Zero detected calls does not prove this repository has no API calls. Unresolved wrappers, generated clients, dynamic URLs or excluded files require manual review.")
    grouped = {}
    for call in calls:
        key = call["method"], canonical(call["path"])
        if key not in grouped:
            grouped[key] = {**call, "callers": []}
        if len(grouped[key]["callers"]) < 20:
            grouped[key]["callers"].append(call["evidence"])
    endpoints = []
    for (method, normalized), call in grouped.items():
        same_path = [route for route in routes if canonical(route["path"]) == normalized]
        matched = next((route for route in same_path if route["method"] == method), None)
        status = "matched" if matched else "mismatch" if same_path else "missing"
        backend = matched or (same_path[0] if same_path else None)
        if not backend:
            parts = normalized.split("/")
            near = sorted(routes, key=lambda route: sum(a == b and bool(a) for a, b in zip(parts, canonical(route["path"]).split("/"))), reverse=True)
            if near and sum(a == b and bool(a) for a, b in zip(parts, canonical(near[0]["path"]).split("/"))) >= 2:
                backend = near[0]
        endpoints.append(Endpoint(
            id=hashlib.sha256(f"{method} {normalized}".encode()).hexdigest()[:12], method=method, path=call["path"], status=status,
            callers=call["callers"], backend=backend["evidence"] if backend else None,
            available_methods=sorted({route["method"] for route in same_path}),
            frontend_owner=owner_for(call["evidence"].file, files), backend_owner=owner_for(backend["evidence"].file, files) if backend else None,
            request_fields=call["request_fields"], response_fields=call["response_fields"], response_is_array=call["response_is_array"],
        ))
    endpoints.sort(key=lambda endpoint: ({"missing": 0, "mismatch": 1, "matched": 2}[endpoint.status], endpoint.path, endpoint.method))
    return endpoints, routes
