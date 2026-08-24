from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

@dataclass
class Constraint:
    field_name: str
    type_name: str
    required: bool = True
    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None
    le: float | None = None
    pattern: str | None = None
    allowed_values: list[str] | None = None


@dataclass
class DependencyNode:
    name: str
    source: str | None = None
    is_auth: bool = False
    override: bool = True


@dataclass
class ExceptionFlow:
    exception_type: str
    status_code: int | None = None
    error_code: str | None = None
    raised_in: str = ""


@dataclass
class Endpoint:
    path: str
    method: HttpMethod
    handler_name: str
    request_model: str | None = None
    response_model: str | None = None
    dependencies: list[DependencyNode] = field(default_factory=list)
    exceptions: list[ExceptionFlow] = field(default_factory=list)
    requires_auth: bool = False
    calls_external: list[str] = field(default_factory=list)


@dataclass 
class Feature:
    name: str
    endpoint: Endpoint
    constraints: list[Constraint] = field(default_factory=list) 