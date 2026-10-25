"""The shared, stateless API contract. Scanned source is never executed."""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import BaseModel, ConfigDict, Field, model_validator

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class Evidence(BaseModel):
    file: str = Field(max_length=500)
    line: int = Field(ge=1)
    snippet: str = Field(max_length=5000)
    url: str | None = Field(default=None, max_length=2000)


class Endpoint(BaseModel):
    id: str
    method: Method
    path: str = Field(max_length=300)
    status: Literal["missing", "mismatch", "matched"]
    callers: list[Evidence] = Field(max_length=20)
    backend: Evidence | None = None
    available_methods: list[str] = Field(default_factory=list)
    frontend_owner: str | None = None
    backend_owner: str | None = None
    request_fields: dict[str, str] = Field(default_factory=dict, max_length=40)
    response_fields: dict[str, str] = Field(default_factory=dict, max_length=40)
    response_is_array: bool = False


def check_schema(schema: dict[str, Any], depth: int = 0) -> None:
    """Only a bounded, local JSON Schema subset is accepted. No remote refs."""
    if depth > 8 or len(json.dumps(schema)) > 16000:
        raise ValueError("Schema is too large or deeply nested.")
    allowed = {"type", "properties", "required", "items", "enum", "description", "additionalProperties"}
    if set(schema) - allowed:
        raise ValueError("Use type, properties, required, items, enum, description and additionalProperties only.")
    if isinstance(schema.get("properties"), dict):
        if len(schema["properties"]) > 50:
            raise ValueError("A schema may have at most 50 properties.")
        for value in schema["properties"].values():
            if not isinstance(value, dict):
                raise ValueError("Each property must be a JSON Schema object.")
            check_schema(value, depth + 1)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            check_schema(schema[key], depth + 1)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"Invalid JSON Schema: {exc.message}") from exc


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint_id: str = Field(max_length=80)
    method: Method
    path: str = Field(max_length=300)
    title: str = Field(max_length=160)
    engine: str = Field(default="Schema inference", max_length=120)
    request_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any]
    response_example: Any
    questions: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_contract(self):
        if not re.fullmatch(r"/[A-Za-z0-9_/{}/.\-]*", self.path) or ".." in self.path:
            raise ValueError("Use an absolute API path with optional {parameter} segments.")
        for segment in self.path.split("/"):
            if ("{" in segment or "}" in segment) and not re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", segment):
                raise ValueError("Path parameters must occupy a segment and use valid identifiers.")
        if len(self.path) > 1 and self.path.endswith("/"):
            self.path = self.path.rstrip("/")
        check_schema(self.response_schema)
        if self.request_schema is not None:
            check_schema(self.request_schema)
        if len(json.dumps(self.response_example)) > 24000:
            raise ValueError("Response example is too large.")
        try:
            Draft202012Validator(self.response_schema).validate(self.response_example)
        except ValidationError as exc:
            raise ValueError(f"The response example does not match the schema: {exc.message}") from exc
        if self.method in {"GET", "HEAD"} and self.request_schema is not None:
            raise ValueError("GET and HEAD request bodies are not supported in this prototype.")
        return self


class ScanInput(BaseModel):
    repo_url: str = Field(min_length=1, max_length=500)


class DraftInput(BaseModel):
    endpoint: Endpoint


class ApprovedInput(BaseModel):
    contract: Contract
    approved: bool = False


class VerifyInput(BaseModel):
    contract: Contract
    response: Any
