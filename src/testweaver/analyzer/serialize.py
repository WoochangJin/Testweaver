"""분석 결과를 JSON 으로 직렬화한다.

`dataclasses.asdict` 를 쓰지 않는다. 자동 변환에 맡기면 내부 필드를 하나
바꿀 때마다 하류가 조용히 깨진다. 여기 적힌 모양이 곧 하류(케이스 매트릭스,
코드 생성)와의 계약이다.

기능 객체의 앞 세 필드는 합의된 매트릭스 스키마의 이름을 그대로 쓴다.
매트릭스를 만드는 쪽이 그대로 옮겨 담을 수 있게 하기 위해서다.

    feature_name / endpoint / method

나머지는 `cases[]` 를 만들 재료다. 어떤 재료가 어떤 케이스가 되는지는
매트릭스를 만드는 쪽이 정한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from testweaver.analyzer.models import (
    AnalysisNote,
    AnalysisResult,
    Constraint,
    DependencyNode,
    ExceptionFlow,
    Feature,
    SymbolRef,
)


def dumps(result: AnalysisResult, indent: int | None = 2) -> str:
    return json.dumps(
        analysis_to_dict(result), indent=indent, ensure_ascii=False, sort_keys=False
    )


def analysis_to_dict(result: AnalysisResult) -> dict[str, Any]:
    return {
        "features": [
            feature_to_dict(feature, result.root) for feature in result.features
        ],
        "notes": [note_to_dict(note, result.root) for note in result.notes],
    }


def feature_to_dict(feature: Feature, root: Path | None = None) -> dict[str, Any]:
    endpoint = feature.endpoint
    return {
        # 매트릭스 스키마와 이름이 같은 부분.
        "feature_name": feature.name,
        "endpoint": endpoint.path,
        "method": endpoint.method.value,
        # 케이스를 만들 재료.
        "feature_id": feature.id,
        "success_status_code": endpoint.success_status_code,
        "requires_auth": endpoint.requires_auth,
        "requires_permission": endpoint.requires_permission,
        "request_model": _symbol(endpoint.request_model),
        "response_model": _symbol(endpoint.response_model),
        "constraints": [constraint_to_dict(c) for c in feature.constraints],
        "exceptions": [exception_to_dict(e) for e in endpoint.exceptions],
        "dependencies": [dependency_to_dict(d) for d in endpoint.dependencies],
        # 테스트를 실행 가능하게 만들 때 필요한 부가 정보.
        "source_file": _path(endpoint.source_file, root),
        "module_path": endpoint.module_path,
        "is_async": endpoint.is_async,
        "tags": list(endpoint.tags),
        "deprecated": endpoint.deprecated,
        "calls_external": list(endpoint.calls_external),
        "nondeterministic": list(endpoint.nondeterministic),
        "notes": [note_to_dict(note, root) for note in feature.notes],
    }


def constraint_to_dict(constraint: Constraint) -> dict[str, Any]:
    """제약 하나. `location` 이 이 값을 요청의 어디에 실을지 정한다.

    body 만 있는 게 아니라 path/query/header/cookie/form 이 함께 온다.
    평평한 payload 객체 하나로는 표현할 수 없으므로, 매트릭스를 만드는 쪽은
    위치별로 나눠 담아야 한다.
    """
    payload: dict[str, Any] = {
        "field_name": constraint.field_name,
        "location": constraint.location.value,
        "type_name": constraint.type_name,
        "required": constraint.required,
        "nullable": constraint.nullable,
    }
    optional = {
        "min_length": constraint.min_length,
        "max_length": constraint.max_length,
        "ge": constraint.ge,
        "le": constraint.le,
        "gt": constraint.gt,
        "lt": constraint.lt,
        "multiple_of": constraint.multiple_of,
        "pattern": constraint.pattern,
        "allowed_values": constraint.allowed_values,
        "default": constraint.default,
        "default_factory": constraint.default_factory,
        "nested_model": _symbol(constraint.nested_model),
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    if constraint.has_custom_validator:
        payload["has_custom_validator"] = True
    return payload


def exception_to_dict(flow: ExceptionFlow) -> dict[str, Any]:
    """실패 케이스의 재료.

    `status_code` 가 null 이면 예외는 찾았지만 응답 코드를 확정하지 못한
    것이다. `resolved` 로 그 사실을 명시하고 이유는 노트에 남긴다.
    """
    return {
        "exception_type": flow.exception_type,
        "status_code": flow.status_code,
        "error_code": flow.error_code,
        "raised_in": flow.raised_in,
        "depth": flow.depth,
        "resolved": flow.resolved,
    }


def dependency_to_dict(dependency: DependencyNode) -> dict[str, Any]:
    return {
        "name": dependency.name,
        "source": _symbol(dependency.source),
        "origin": dependency.origin.value,
        "is_auth": dependency.is_auth,
        "is_permission": dependency.is_permission,
        "scopes": list(dependency.scopes),
        "overridable": dependency.overridable,
    }


def note_to_dict(note: AnalysisNote, root: Path | None = None) -> dict[str, Any]:
    return {
        "level": note.level.value,
        "code": note.code.value,
        "message": note.message,
        "file": _path(Path(note.file), root) if note.file else "",
        "line": note.line,
    }


def write_analysis(result: AnalysisResult, path: Path) -> Path:
    """결과를 파일로 저장하고 그 경로를 돌려준다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(result), encoding="utf-8")
    return path


def _symbol(ref: SymbolRef | None) -> str | None:
    """심볼은 모듈까지 포함한 문자열로 낸다.

    이름만 남기면 코드 생성 단계에서 import 문을 만들 수 없다.
    """
    return str(ref) if ref is not None else None


def _path(path: Path | None, root: Path | None = None) -> str | None:
    """경로는 분석 루트 기준 상대 경로로 낸다.

    절대 경로를 그대로 담으면 산출물이 머신마다 달라져 비교도 공유도 어렵다.
    """
    if path is None:
        return None
    if root is not None:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            pass
    return path.as_posix()
