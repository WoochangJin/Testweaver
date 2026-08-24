from pathlib import Path

from testweaver.analyzer.models import (
    Constraint,
    Feature,
    HttpMethod,
    ParamLocation,
    SymbolRef,
)


def test_symbol_identity_ignores_file():
    """심볼의 정체성은 (module, name) 뿐이다.

    import 표에서 온 참조는 file 이 비어 있고 정의부에서 만든 참조는 채워져
    있다. file 이 비교에 들어가면 둘이 다른 키가 되어 인덱스 조회가 조용히
    실패한다.
    """
    from_import = SymbolRef("router", "routers.auth")
    from_definition = SymbolRef("router", "routers.auth", Path("routers/auth.py"))

    assert from_import == from_definition
    assert hash(from_import) == hash(from_definition)
    assert {from_import: 1}[from_definition] == 1


def test_symbol_with_different_module_is_a_different_symbol():
    assert SymbolRef("router", "routers.auth") != SymbolRef("router", "routers.orders")


def test_unresolved_symbol_is_flagged():
    assert SymbolRef("LoginRequest").is_resolved is False
    assert SymbolRef("LoginRequest", "schemas.auth").is_resolved is True


def test_symbol_renders_qualified_name():
    assert str(SymbolRef("LoginRequest", "schemas.auth")) == "schemas.auth.LoginRequest"
    assert str(SymbolRef("LoginRequest")) == "LoginRequest"


def test_constraints_are_filtered_by_location():
    feature = Feature(
        id="GET /orders",
        name="list_orders",
        endpoint=None,  # type: ignore[arg-type]
        constraints=[
            Constraint("order_id", "int", location=ParamLocation.PATH),
            Constraint("limit", "int", location=ParamLocation.QUERY),
            Constraint("memo", "str", location=ParamLocation.BODY),
        ],
    )
    assert [c.field_name for c in feature.constraints_in(ParamLocation.QUERY)] == [
        "limit"
    ]


def test_is_bounded_reports_generatable_edges():
    assert Constraint("x", "str").is_bounded is False
    assert Constraint("x", "str", min_length=3).is_bounded is True
    assert Constraint("x", "int", gt=0).is_bounded is True


def test_enums_serialise_as_plain_strings():
    """합의된 매트릭스 스키마가 method 와 category 를 문자열로 받는다."""
    import json

    payload = json.dumps({"method": HttpMethod.POST, "in": ParamLocation.QUERY})
    assert payload == '{"method": "POST", "in": "query"}'
