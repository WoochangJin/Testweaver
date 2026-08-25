"""샘플 픽스처 앱 자체의 건전성 검사.

이 앱의 `app.openapi()` 결과를 정적 분석의 정답지로 쓸 예정이므로,
앱이 실제로 로드되고 기대한 라우트를 갖는지 먼저 고정해 둔다.
analyzer 가 아직 없어도 이 테스트는 독립적으로 통과해야 한다.
"""

from tests.fixtures.sample_app.main import app

EXPECTED_ROUTES = {
    ("/api/v1/auth/login", "POST"),
    ("/api/v1/auth/signup", "POST"),
    ("/api/v1/auth/me", "GET"),
    ("/api/v1/orders", "GET"),
    ("/api/v1/orders", "POST"),
    ("/api/v1/orders/{order_id}", "GET"),
    ("/api/v1/orders/{order_id}", "DELETE"),
    ("/health", "GET"),
}

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _spec_routes() -> set[tuple[str, str]]:
    spec = app.openapi()
    return {
        (path, method.upper())
        for path, operations in spec["paths"].items()
        for method in operations
        if method.upper() in HTTP_METHODS
    }


def test_router_prefixes_are_composed():
    """include_router(prefix) + APIRouter(prefix) 가 실제 경로에 반영된다."""
    assert _spec_routes() == EXPECTED_ROUTES


def test_declared_success_status_codes():
    """status_code 를 명시한 엔드포인트는 그 코드로 문서화된다."""
    spec = app.openapi()
    assert "201" in spec["paths"]["/api/v1/auth/signup"]["post"]["responses"]
    assert "204" in spec["paths"]["/api/v1/orders/{order_id}"]["delete"]["responses"]


def test_query_and_path_parameters_are_declared():
    """path/query 파라미터와 그 제약이 스펙에 드러난다."""
    params = {
        p["name"]: p
        for p in app.openapi()["paths"]["/api/v1/orders"]["get"]["parameters"]
    }
    assert params["q"]["in"] == "query"
    assert params["q"]["required"] is False
    assert params["limit"]["in"] == "query"

    order_params = {
        p["name"]: p
        for p in app.openapi()["paths"]["/api/v1/orders/{order_id}"]["get"][
            "parameters"
        ]
    }
    assert order_params["order_id"]["in"] == "path"
    assert order_params["order_id"]["required"] is True


def test_inherited_and_constrained_body_fields():
    """상속 필드와 제약이 요청 본문 스키마에 나타난다."""
    schema = app.openapi()["components"]["schemas"]["SignupRequest"]
    assert "nickname" in schema["properties"], "UserBase 에서 상속받은 필드"
    assert set(schema["required"]) == {"nickname", "email", "password", "role"}
    assert schema["properties"]["password"]["minLength"] == 8
