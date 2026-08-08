"""실제 프로젝트에서 조용히 잘못된 결과를 만들었던 조합의 회귀 테스트."""

from testweaver.analyzer.models import DependencyOrigin
from testweaver.analyzer.pipeline import analyze_project


def _write(root, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_app_dependencies_are_scoped_and_direct_routes_inherit_them(tmp_path):
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import APIRouter, Depends, FastAPI

def first_guard(): pass
def second_guard(): pass

first_router = APIRouter()
second_router = APIRouter()
first_app = FastAPI(dependencies=[Depends(first_guard)])
second_app = FastAPI(dependencies=[Depends(second_guard)])

@first_app.get('/direct')
def direct(): pass

@first_router.get('/one')
def one(): pass

@second_router.get('/two')
def two(): pass

first_app.include_router(first_router)
second_app.include_router(second_router)
""",
    )

    features = {feature.id: feature for feature in analyze_project(tmp_path).features}
    assert set(features) == {"GET /direct", "GET /one", "GET /two"}

    direct = features["GET /direct"].endpoint.dependencies
    one = features["GET /one"].endpoint.dependencies
    two = features["GET /two"].endpoint.dependencies
    assert [(d.source.name, d.origin) for d in direct] == [
        ("first_guard", DependencyOrigin.APP)
    ]
    assert [d.source.name for d in one] == ["first_guard"]
    assert [d.source.name for d in two] == ["second_guard"]


def test_non_fastapi_get_decorator_is_not_a_route(tmp_path):
    _write(
        tmp_path,
        "main.py",
        """
class Registry:
    def get(self, path):
        return lambda fn: fn

registry = Registry()

@registry.get('/not-an-endpoint')
def helper(): pass
""",
    )
    assert analyze_project(tmp_path).features == []


def test_app_dependency_is_resolved_from_the_app_module(tmp_path):
    _write(tmp_path, "guards.py", "def global_guard(): pass\n")
    _write(
        tmp_path,
        "routes.py",
        """
from fastapi import APIRouter

router = APIRouter()

@router.get('/mounted')
def mounted(): pass
""",
    )
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import Depends, FastAPI
from guards import global_guard
from routes import router

app = FastAPI(dependencies=[Depends(global_guard)])
app.include_router(router)
""",
    )

    [feature] = analyze_project(tmp_path).features
    [dependency] = feature.endpoint.dependencies
    assert (dependency.source.module, dependency.source.name) == (
        "guards",
        "global_guard",
    )


def test_imported_parent_router_can_mount_a_child(tmp_path):
    _write(
        tmp_path,
        "parent.py",
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/parent')\n",
    )
    _write(
        tmp_path,
        "child.py",
        """
from fastapi import APIRouter
router = APIRouter(prefix='/child')

@router.get('/leaf')
def leaf(): pass
""",
    )
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import FastAPI
from parent import router as parent
from child import router as child

app = FastAPI()
parent.include_router(child, prefix='/nested')
app.include_router(parent, prefix='/api')
""",
    )

    assert [feature.id for feature in analyze_project(tmp_path).features] == [
        "GET /api/parent/nested/child/leaf"
    ]


def test_multiple_mounts_keep_dependencies_and_tags_separate(tmp_path):
    _write(
        tmp_path,
        "routes.py",
        """
from fastapi import APIRouter

router = APIRouter()

@router.get('/items')
def items(): pass
""",
    )
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import Depends, FastAPI
from routes import router

def v1_guard(): pass
def v2_guard(): pass

app = FastAPI()
app.include_router(router, prefix='/v1', dependencies=[Depends(v1_guard)], tags=['v1'])
app.include_router(router, prefix='/v2', dependencies=[Depends(v2_guard)], tags=['v2'])
""",
    )

    features = {feature.id: feature for feature in analyze_project(tmp_path).features}
    assert [d.source.name for d in features["GET /v1/items"].endpoint.dependencies] == [
        "v1_guard"
    ]
    assert features["GET /v1/items"].endpoint.tags == ["v1"]
    assert [d.source.name for d in features["GET /v2/items"].endpoint.dependencies] == [
        "v2_guard"
    ]
    assert features["GET /v2/items"].endpoint.tags == ["v2"]


def test_reused_nested_model_is_expanded_for_each_field(tmp_path):
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class Address(BaseModel):
    zipcode: str = Field(min_length=5)

class Delivery(BaseModel):
    billing: Address
    shipping: Address

@app.post('/deliver')
def deliver(payload: Delivery): pass
""",
    )

    [feature] = analyze_project(tmp_path).features
    names = {constraint.field_name for constraint in feature.constraints}
    assert {"billing.zipcode", "shipping.zipcode"} <= names


def test_transitive_dependency_alias_is_resolved_in_declaring_module(tmp_path):
    _write(
        tmp_path,
        "deps.py",
        """
from typing import Annotated
from fastapi import Depends

def authenticate(): pass
Guard = Annotated[str, Depends(authenticate)]
def outer(value: Guard): pass
""",
    )
    _write(
        tmp_path,
        "main.py",
        """
from typing import Annotated
from fastapi import Depends, FastAPI
from deps import outer

app = FastAPI()

@app.get('/secure')
def secure(value: Annotated[str, Depends(outer)]): pass
""",
    )

    [feature] = analyze_project(tmp_path).features
    assert [d.source.name for d in feature.endpoint.dependencies] == [
        "outer",
        "authenticate",
    ]


def test_unused_nested_function_does_not_add_effects_or_exceptions(tmp_path):
    _write(
        tmp_path,
        "main.py",
        """
from fastapi import FastAPI, HTTPException
from uuid import uuid4

app = FastAPI()

@app.get('/clean')
def clean():
    def unused():
        uuid4()
        client.get('https://example.com')
        raise HTTPException(418, 'UNUSED')
    return {'ok': True}
""",
    )

    [feature] = analyze_project(tmp_path).features
    assert feature.endpoint.exceptions == []
    assert feature.endpoint.calls_external == []
    assert feature.endpoint.nondeterministic == []
