from __future__ import annotations

import asyncio
import io
import os
import re
import zipfile
import zlib

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from jsonschema import Draft202012Validator
from itertools import islice

try:
    from .contract import active_model, propose
    from .github_source import SourceError
    from .main import demo_scan, scan_repository
    from .schema import ApprovedInput, DraftInput, ScanInput, VerifyInput
    from .unblock import create_mock, decode_contract, files_for
except ImportError:
    from contract import active_model, propose
    from github_source import SourceError
    from main import demo_scan, scan_repository
    from schema import ApprovedInput, DraftInput, ScanInput, VerifyInput
    from unblock import create_mock, decode_contract, files_for

app = FastAPI(title="TritonTeam API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)


@app.middleware("http")
async def request_limits(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if len(await request.body()) > 256000:
            return JSONResponse({"detail": "Request exceeds 256 KB."}, status_code=413)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    base_url, model, api_key = active_model()
    return {"status": "ok", "version": "0.1.0", "model_configured": bool(base_url and model and api_key), "engine": model if base_url and model and api_key else "Schema inference"}


@app.get("/api/demo")
def demo():
    return demo_scan()


@app.post("/api/scan")
async def scan(body: ScanInput):
    try:
        return await asyncio.wait_for(scan_repository(body.repo_url), timeout=48)
    except SourceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="This scan took too long. Try a smaller repository or use the demo.") from exc


@app.post("/api/contract")
async def contract(body: DraftInput):
    draft, warnings = await propose(body.endpoint)
    return {"contract": draft.model_dump(), "warnings": warnings}


def require_approval(body: ApprovedInput):
    if not body.approved:
        raise HTTPException(status_code=409, detail="Review and accept this contract before generating a mock.")


@app.post("/api/mock")
def mock(body: ApprovedInput):
    require_approval(body)
    if body.contract.method in {"HEAD", "OPTIONS"}:
        raise HTTPException(status_code=422, detail="Mock generation currently supports GET, POST, PUT, PATCH and DELETE.")
    try:
        return create_mock(body.contract)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/export")
def export(body: ApprovedInput):
    require_approval(body)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files_for(body.contract):
            archive.writestr(file["name"], file["content"])
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="tritonteam-mock.zip"'})


@app.post("/api/verify")
def verify(body: VerifyInput):
    errors = list(islice(Draft202012Validator(body.contract.response_schema).iter_errors(body.response), 20))
    return {"valid": not errors, "errors": [{"path": ".".join(map(str, error.absolute_path)) or "$", "message": error.message} for error in errors]}


@app.api_route("/api/playground/{token}/{mock_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def playground(token: str, mock_path: str, request: Request):
    cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "X-TritonTeam-Mock": "true"}
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=cors)
    try:
        draft = decode_contract(token)
    except (ValueError, TypeError, zlib.error):
        raise HTTPException(status_code=404, detail="Mock URL is invalid.")
    pattern = re.sub(r"\\\{[^{}]+\\\}", "[^/]+", re.escape(draft.path))
    if not re.fullmatch(pattern, "/" + mock_path.rstrip("/")):
        raise HTTPException(status_code=404, detail="Path does not match the approved contract.")
    if request.method != draft.method:
        return JSONResponse({"detail": f"This mock expects {draft.method}."}, status_code=405, headers={**cors, "Allow": draft.method})
    if draft.request_schema is not None:
        try:
            data = await request.json()
        except (ValueError, UnicodeError):
            return JSONResponse({"detail": "Expected a JSON request body."}, status_code=422, headers=cors)
        errors = list(islice(Draft202012Validator(draft.request_schema).iter_errors(data), 5))
        if errors:
            return JSONResponse({"detail": [error.message for error in errors]}, status_code=422, headers=cors)
    return JSONResponse(draft.response_example, headers=cors)
