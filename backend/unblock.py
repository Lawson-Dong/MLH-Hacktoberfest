"""Portable, stateless mocks. Tokens contain synthetic contract data, not code."""
from __future__ import annotations

import base64
import hashlib
import json
import keyword
import re
import zlib

try:
    from .contract import example_for, to_openapi
    from .schema import Contract
except ImportError:
    from contract import example_for, to_openapi
    from schema import Contract


def fingerprint(contract: Contract) -> str:
    return hashlib.sha256(contract.model_dump_json().encode()).hexdigest()[:16]


def encode_contract(contract: Contract) -> str:
    payload = contract.model_dump_json().encode()
    token = base64.urlsafe_b64encode(zlib.compress(payload, 9)).decode().rstrip("=")
    if len(payload) > 48000 or len(token) > 6000:
        raise ValueError("This contract is too large for a stateless mock URL. Use a smaller example.")
    return token


def decode_contract(token: str) -> Contract:
    if len(token) > 6000:
        raise ValueError("Invalid mock token")
    data = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
    decompressor = zlib.decompressobj()
    payload = decompressor.decompress(data, 48001)
    if len(payload) > 48000 or not decompressor.eof or decompressor.unused_data:
        raise ValueError("Invalid mock token")
    return Contract.model_validate_json(payload)


def model_code(schema: dict, name: str) -> str:
    definitions = []

    def annotation(value, class_name):
        kind = value.get("type", "object")
        if isinstance(kind, list):
            return " | ".join(dict.fromkeys(annotation({**value, "type": item}, class_name) for item in kind))
        if "enum" in value and value["enum"] and all(isinstance(item, (str, int, float, bool)) or item is None for item in value["enum"]):
            return "Literal[" + ", ".join(repr(item) for item in value["enum"]) + "]"
        if kind == "array":
            return f"list[{annotation(value.get('items', {}), class_name + 'Item')}]"
        if kind != "object":
            return {"string": "str", "number": "float", "integer": "int", "boolean": "bool", "null": "None"}.get(kind, "Any")
        properties = value.get("properties", {})
        if not properties:
            return "dict[str, Any]"
        fields, used_names = [], set()
        for index, (key, nested) in enumerate(properties.items()):
            field_type = annotation(nested, f"{class_name}Field{index}")
            safe = key if key.isidentifier() and not keyword.iskeyword(key) and not key.startswith("_") and not key.startswith("model_") else f"field_{index}"
            while safe in used_names:
                safe += "_"
            used_names.add(safe)
            required = key in value.get("required", [])
            fields.append(f"    {safe}: {field_type}{'' if required else ' | None'} = Field({('...' if required else 'None')}, alias={key!r})")
        extra = "forbid" if value.get("additionalProperties") is False else "allow"
        definitions.append(f"class {class_name}(BaseModel):\n    model_config = ConfigDict(extra={extra!r}, populate_by_name=True)\n" + "\n".join(fields))
        return class_name

    value_type = annotation(schema, name + "Data")
    definitions.append(f"class {name}(RootModel[{value_type}]):\n    pass")
    return "\n\n".join(definitions)


def files_for(contract: Contract) -> list[dict]:
    models = model_code(contract.response_schema, "ResponseModel")
    if contract.request_schema is not None:
        models += "\n\n" + model_code(contract.request_schema, "RequestModel")
    imports = "from typing import Any, Literal\nfrom fastapi import FastAPI, HTTPException, Request\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom pydantic import BaseModel, ConfigDict, Field, RootModel\nimport json\nimport os\n\n"
    setup = "\n\napp = FastAPI(title='TritonTeam approved contract')\napp.add_middleware(CORSMiddleware, allow_origins=os.getenv('MOCK_CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(','), allow_methods=['*'], allow_headers=['*'])\n\n"
    decorator = f"@app.api_route({contract.path!r}, methods={[contract.method]!r}, response_model=ResponseModel)\n"
    signature = "def endpoint(request: Request" + (", body: RequestModel" if contract.request_schema is not None else "") + "):\n"
    example = json.dumps(contract.response_example, ensure_ascii=True)
    mock_code = imports + models + setup + f"RESPONSE = json.loads({example!r})\n\n" + decorator + signature + "    return RESPONSE\n"
    skeleton = imports + models + setup + decorator + signature + "    # Read route parameters from request.path_params.\n    # Implement the approved contract here, then run the contract check.\n    raise HTTPException(status_code=501, detail='Backend implementation pending')\n"
    msw_path = re.sub(r"\{([^{}]+)\}", r":\1", contract.path)
    msw = f"import {{ http, HttpResponse }} from 'msw';\n\nexport const handlers = [\n  http.{contract.method.lower()}({json.dumps('*' + msw_path)}, () =>\n    HttpResponse.json({json.dumps(contract.response_example, indent=2)})\n  ),\n];\n"
    readme = f"# {contract.method} {contract.path}\n\nApproved contract fingerprint: {fingerprint(contract)}\n\n## Run the mock\n\n```bash\npython -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\nuvicorn mock_server:app --reload --port 8001\n```\n\nUse `http://localhost:8001` as your frontend API origin. Default CORS origins are localhost ports 5173 and 3000; configure MOCK_CORS_ORIGINS for another origin. The endpoint accepts {contract.method}; path parameters can use any value.\n\n`openapi.json` is the agreed interface. `backend_skeleton.py` contains Pydantic models and a 501 stub for the backend owner. `handlers.ts` is an MSW v2 handler (install and initialize MSW in your frontend before using it).\n\nMock data is synthetic. Business rules, authentication, pagination and error responses still need agreement. Never put secrets in a mock URL.\n"
    return [
        {"name": "openapi.json", "content": json.dumps(to_openapi(contract), indent=2)},
        {"name": "mock_server.py", "content": mock_code},
        {"name": "backend_skeleton.py", "content": skeleton},
        {"name": "handlers.ts", "content": msw},
        {"name": "requirements.txt", "content": "fastapi==0.143.0\nuvicorn==0.38.0\n"},
        {"name": "README.md", "content": readme},
    ]


def create_mock(contract: Contract) -> dict:
    token = encode_contract(contract)
    path = re.sub(r"\{[^{}]+\}", "demo_001", contract.path)
    return {"fingerprint": fingerprint(contract), "method": contract.method, "path": contract.path,
        "url": f"/api/playground/{token}{path}", "response_example": contract.response_example,
        "request_example": example_for(contract.request_schema) if contract.request_schema is not None else None, "files": files_for(contract)}
