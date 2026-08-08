"""엔드포인트가 인증을 요구하는지, 권한까지 요구하는지 판정한다.

이름 규칙만으로 판정하면 `verify_token` 이나 `admin_required` 처럼 조금만
달라도 놓친다. 그래서 이름은 1차 단서로만 쓰고, 의존성 함수의 본문에서
실제로 401/403 을 던지는지 확인해 확정한다.

인증(401)과 권한(403)을 나누는 이유는 하류에서 만들 보안 케이스가 다르기
때문이다. 토큰 없이 접근하는 경우와, 토큰은 있지만 권한이 모자란 경우는
서로 다른 테스트다.
"""

from __future__ import annotations

import ast
import re

from testweaver.analyzer.ast_utils import resolve_status_constant
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.models import DependencyNode, SymbolRef

_AUTH_NAME = re.compile(
    r"current_user|get_user|active_user|auth|token|credential|login_required|"
    r"oauth2|bearer|api_key|session",
    re.IGNORECASE,
)
_PERMISSION_NAME = re.compile(
    r"admin|role|permission|scope|require_|superuser|staff|owner",
    re.IGNORECASE,
)

_UNAUTHORIZED = 401
_FORBIDDEN = 403


class AuthExtractor:
    """의존성 목록을 근거로 인증·권한 여부를 정한다."""

    name = "auth"
    requires = ("dependency",)

    def extract(self, context: ExtractionContext) -> None:
        for dependency in context.endpoint.dependencies:
            raised = self._statuses_raised(context, dependency.source)

            dependency.is_auth = _UNAUTHORIZED in raised or bool(
                _AUTH_NAME.search(str(dependency.source))
            )
            dependency.is_permission = (
                _FORBIDDEN in raised
                or bool(dependency.scopes)
                or bool(_PERMISSION_NAME.search(str(dependency.source)))
            )

        context.endpoint.requires_auth = any(
            dependency.is_auth for dependency in context.endpoint.dependencies
        )
        context.endpoint.requires_permission = any(
            dependency.is_permission for dependency in context.endpoint.dependencies
        )

    def _statuses_raised(self, context: ExtractionContext, ref: SymbolRef) -> set[int]:
        """의존성 함수가 직접 던지는 상태코드들.

        이름 휴리스틱보다 확실한 근거다. 프로젝트 밖 심볼은 본문을 볼 수
        없으므로 빈 집합이 되고, 그때는 이름 규칙으로만 판정한다.
        """
        target = context.index.find_callable(ref)
        if target is None:
            return set()

        statuses: set[int] = set()
        for node in ast.walk(target.node):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            from testweaver.analyzer.ast_utils import argument_of

            status = resolve_status_constant(argument_of(node.exc, 0, "status_code"))
            if status is not None:
                statuses.add(status)
        return statuses


def auth_dependencies(dependencies: list[DependencyNode]) -> list[DependencyNode]:
    """인증·권한과 관련된 의존성만 추린다. 테스트 준비 코드가 이걸 쓴다."""
    return [d for d in dependencies if d.is_auth or d.is_permission]
