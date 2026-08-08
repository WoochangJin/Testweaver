# TestWeaver Analyzer

TestWeaver Analyzer는 FastAPI 프로젝트를 정적으로 분석하여 테스트 설계에 필요한
구조화 데이터를 생성하는 모듈입니다. Python 표준 `ast` 모듈을 사용하며, 분석
대상 애플리케이션을 import하거나 실행하지 않습니다.

## 1. 역할과 범위

Analyzer는 다음 정보를 추출합니다.

- 최종 prefix가 적용된 API 경로와 HTTP 메서드
- 요청 및 응답 모델
- body, path, query, header, cookie, form 입력 제약
- handler, route, router, app 수준의 의존성
- 인증 및 권한 요구 여부
- handler, 서비스 함수, 의존성에서 발생할 수 있는 예외
- 외부 시스템 호출과 비결정적 동작 후보
- 정적으로 확정할 수 없는 항목에 대한 진단 정보

Analyzer의 출력은 테스트 매트릭스 및 테스트 코드 생성 단계의 입력으로 사용됩니다.
다음 작업은 Analyzer의 책임 범위에 포함되지 않습니다.

- 테스트 케이스 조합 및 우선순위 결정
- 테스트 매트릭스 UI 제공
- pytest 코드 생성
- 생성된 테스트 실행 및 수정
- 프로젝트 전체 CLI, 배포 및 패키징 구성

## 2. 요구 사항

- Python 3.13 이상
- 분석 대상: FastAPI 및 Pydantic 기반 Python 프로젝트
- 입력 형식: 프로젝트 루트 디렉터리
- 출력 형식: `AnalysisResult` 또는 JSON

## 3. 빠른 시작

### 명령줄 실행

분석 요약을 출력합니다.

```powershell
uv run python -m testweaver.analyzer path\to\project --summary
```

전체 분석 결과를 JSON으로 출력합니다.

```powershell
uv run python -m testweaver.analyzer path\to\project
```

분석 결과를 파일로 저장합니다.

```powershell
uv run python -m testweaver.analyzer path\to\project --output analysis.json
```

`uv`를 사용하지 않는 환경에서는 활성화된 Python 환경에서 동일한 모듈을
실행할 수 있습니다.

```powershell
python -m testweaver.analyzer path\to\project --summary
```

### Python API

```python
from pathlib import Path

from testweaver.analyzer.pipeline import analyze_project
from testweaver.analyzer.serialize import dumps

result = analyze_project(Path("path/to/project"))
print(dumps(result))
```

## 4. 공개 API

### `analyze_project`

```python
def analyze_project(
    root: Path,
    exclude_patterns: tuple[str, ...] | list[str] | None = None,
    extractors: list[EndpointExtractor] | None = None,
) -> AnalysisResult:
    ...
```

프로젝트 파일 수집, 인덱스 구축, 엔드포인트 추출을 한 번에 수행합니다.

| 매개변수 | 설명 |
| --- | --- |
| `root` | 분석할 프로젝트의 루트 디렉터리 |
| `exclude_patterns` | 루트 기준 제외 패턴 목록 |
| `extractors` | 기본 extractor 대신 실행할 extractor 목록 |

`exclude_patterns=None`이면 기본 제외 패턴을 사용합니다. 목록을 직접 전달하면
기본 패턴에 추가되는 것이 아니라 기본 패턴 전체를 대체합니다.

기본 제외 대상은 다음과 같습니다.

- `.venv`, `venv`, `site-packages`
- `node_modules`
- `__pycache__`
- `.git`
- `tests`

### `extract_features`

```python
def extract_features(
    index: ProjectIndex,
    extractors: list[EndpointExtractor] | None = None,
) -> AnalysisResult:
    ...
```

이미 구축된 `ProjectIndex`에서 엔드포인트 추출 단계만 실행합니다. 동일한
프로젝트 인덱스를 재사용하거나 특정 extractor만 시험할 때 사용합니다.

### 직렬화 함수

```python
from testweaver.analyzer.serialize import (
    analysis_to_dict,
    dumps,
    write_analysis,
)
```

| 함수 | 반환값 | 설명 |
| --- | --- | --- |
| `analysis_to_dict(result)` | `dict` | 공개 JSON 스키마로 변환 |
| `dumps(result, indent=2)` | `str` | UTF-8 JSON 문자열 생성 |
| `write_analysis(result, path)` | `Path` | 상위 디렉터리를 생성하고 JSON 저장 |

## 5. 분석 처리 모델

Analyzer는 파일을 한 번만 읽고 파싱한 뒤 세 단계로 처리합니다.

### Pass 0: 파일 수집 및 파싱

1. 프로젝트 루트 아래의 Python 파일을 탐색합니다.
2. 제외 패턴을 적용합니다.
3. 각 파일을 UTF-8로 읽고 AST로 변환합니다.
4. 읽기 또는 파싱에 실패한 파일은 진단을 기록하고 건너뜁니다.

### Pass 1: 프로젝트 인덱스 구축

다음 정보를 프로젝트 전역 인덱스로 구성합니다.

- 모듈 경로
- import 및 별칭
- 클래스와 최상위 함수
- 모듈 상수와 클래스 인스턴스
- 타입 별칭
- FastAPI 앱, 라우터 및 마운트 관계
- 전역 예외 처리기

이 단계에서는 가능한 한 정보를 있는 그대로 수집합니다. Pydantic 모델 여부와
같이 다른 심볼을 확인해야 하는 판정은 인덱스가 완성된 후 수행합니다.

### Pass 2: 엔드포인트 추출

각 라우트에 대해 extractor를 실행하여 `Endpoint`, `Constraint`,
`DependencyNode`, `ExceptionFlow`를 구성합니다.

| Extractor | 책임 |
| --- | --- |
| `route` | 경로, 메서드, 성공 상태 코드, 응답 모델, 태그 |
| `dependency` | 직접 및 전이 의존성 |
| `params` | path, query, header, cookie, form 파라미터 |
| `body` | Pydantic 요청 모델과 필드 제약 |
| `auth` | 인증 및 권한 요구 여부 |
| `exception` | 직접·간접 예외 흐름 |
| `effects` | 외부 호출 및 비결정적 동작 후보 |

Extractor 실행 순서는 등록 순서가 아니라 각 extractor의 `requires` 선언을
위상 정렬하여 결정합니다.

## 6. 라우트 해석

Analyzer는 다음 라우트 선언을 지원합니다.

- `@app.get`, `@app.post`, `@app.put`, `@app.patch`, `@app.delete`
- `@app.head`, `@app.options`
- `@router.<method>`
- `@router.api_route(..., methods=[...])`
- 하나의 handler에 적용된 복수의 라우트 데코레이터
- 중첩 `include_router`
- 반복문을 이용한 정적 라우터 등록
- 동일 라우터의 다중 마운트

경로는 다음 요소를 순서대로 결합합니다.

```text
상위 라우터 또는 앱의 mount prefix
  + 현재 라우터의 mount prefix
  + APIRouter(prefix=...)
  + 라우트 데코레이터의 path
```

예를 들어 다음 선언은 `GET /api/v1/orders/{order_id}`로 분석됩니다.

```python
# main.py
app.include_router(router, prefix="/api/v1")

# routes.py
router = APIRouter(prefix="/orders")

@router.get("/{order_id}")
def get_order(order_id: int): ...
```

동일한 라우터가 여러 위치에 마운트되면 경로별로 별도의 feature를 생성합니다.
각 마운트의 의존성과 태그도 다른 경로와 섞이지 않도록 별도로 유지합니다.

## 7. 의존성 해석

다음 네 위치의 `Depends` 및 `Security`를 수집합니다.

| 선언 위치 | `DependencyOrigin` |
| --- | --- |
| handler 매개변수 | `handler` |
| 라우트 데코레이터 | `route` |
| `APIRouter` 또는 `include_router` | `router` |
| `FastAPI` | `app` |

의존성이 다시 다른 의존성을 요구하면 제한된 깊이까지 재귀적으로 추적합니다.
호출 가능한 클래스 인스턴스는 해당 클래스의 `__call__` 메서드를 확인합니다.

모든 의존성 심볼은 실제 선언 모듈 기준으로 해석됩니다. 이 규칙은 앱 설정
모듈과 라우트 모듈에 동일한 이름의 함수가 존재할 때 잘못된 심볼이 선택되는
것을 방지합니다.

`Security(..., scopes=[...])`의 scope는 `DependencyNode.scopes`에 보존됩니다.

## 8. 입력 제약 해석

### 매개변수 위치

명시적인 FastAPI marker가 있으면 해당 marker를 우선합니다.

| Marker | 위치 |
| --- | --- |
| `Path` | `path` |
| `Query` | `query` |
| `Header` | `header` |
| `Cookie` | `cookie` |
| `Body` | `body` |
| `Form`, `File` | `form` |

Marker가 없으면 다음 규칙을 적용합니다.

1. URL 템플릿에 포함된 이름은 path로 분류합니다.
2. `UploadFile`은 form으로 분류합니다.
3. 프로젝트 내부 Pydantic 모델은 body로 분류합니다.
4. collection 타입은 body로 분류합니다.
5. 나머지 scalar 타입은 query로 분류합니다.

### 지원 제약

`Field`, `Path`, `Query`, `Header`, `Cookie`, `Body`, `Form`에서 다음 정보를
추출합니다.

- `min_length`, `max_length`
- `ge`, `le`, `gt`, `lt`
- `multiple_of`
- `pattern` 및 `regex`
- 기본값과 `default_factory`
- alias와 `validation_alias`
- `Literal` 및 enum 허용값
- nullable 여부
- 필수 여부

Pydantic 필드의 필수 여부는 타입의 optional 여부가 아니라 기본값 존재 여부로
판정합니다. 상속 모델과 중첩 모델을 추적하며, 중첩 필드는
`address.zipcode` 형식으로 표현합니다.

## 9. 인증 및 예외 해석

### 인증과 권한

의존성 함수가 직접 발생시키는 상태 코드와 다음 보조 정보를 사용합니다.

- `401`: 인증 요구
- `403`: 권한 요구
- `Security` scope: 권한 요구
- 인증·권한과 관련된 일반적인 심볼 이름

이름 기반 판정은 함수 본문을 확인할 수 없는 경우를 보완하는 휴리스틱입니다.

### 예외 흐름

다음 위치에서 발생 가능한 예외를 수집합니다.

- 라우트 handler 본문
- 프로젝트 내부의 호출 대상 함수
- endpoint에 적용된 의존성
- 호출 가능한 의존성 객체의 `__call__`

`HTTPException`과 `StarletteHTTPException`은 상태 코드와 문자열 detail을
추출합니다. 커스텀 예외는 등록된 전역 예외 처리기에서 상태 코드를 찾습니다.

실행되지 않는 중첩 함수 또는 클래스의 본문은 바깥 함수의 예외·효과로 계산하지
않습니다.

## 10. 출력 모델

### `AnalysisResult`

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `features` | `list[Feature]` | 분석된 엔드포인트 목록 |
| `notes` | `list[AnalysisNote]` | 전역 및 feature 진단 목록 |
| `root` | `Path \| None` | 경로 상대화 기준 |

### `Feature`

| 필드 | 설명 |
| --- | --- |
| `id` | `METHOD /path` 형식의 식별자 |
| `name` | handler 함수 이름 |
| `endpoint` | 엔드포인트 정보 |
| `constraints` | 입력 제약 목록 |
| `notes` | 해당 feature의 진단 목록 |

### JSON feature 스키마

```json
{
  "feature_name": "get_order",
  "endpoint": "/api/v1/orders/{order_id}",
  "method": "GET",
  "feature_id": "GET /api/v1/orders/{order_id}",
  "success_status_code": 200,
  "requires_auth": true,
  "requires_permission": false,
  "request_model": null,
  "response_model": "schemas.OrderOut",
  "constraints": [],
  "exceptions": [],
  "dependencies": [],
  "source_file": "routes/orders.py",
  "module_path": "routes.orders",
  "is_async": true,
  "tags": ["orders"],
  "deprecated": false,
  "calls_external": [],
  "nondeterministic": [],
  "notes": []
}
```

`source_file`과 진단의 파일 경로는 가능하면 분석 루트 기준 POSIX 상대 경로로
직렬화됩니다.

### `Constraint`

모든 constraint에는 다음 필드가 포함됩니다.

- `field_name`
- `location`
- `type_name`
- `required`
- `nullable`

값이 존재할 때만 길이·범위·패턴·허용값·기본값·중첩 모델 정보가 추가됩니다.

### `DependencyNode`

의존성의 원본 심볼, 선언 위치, 인증·권한 판정, scope 및 override 가능 여부를
제공합니다.

### `ExceptionFlow`

예외 타입, 상태 코드, 오류 코드, 발생 함수, 호출 깊이 및 상태 코드 해석 여부를
제공합니다. `resolved=false`이면 `status_code`를 확정하지 못한 상태입니다.

## 11. 진단

정적으로 해석하지 못한 항목은 `AnalysisNote`로 보고합니다.

### 진단 수준

| 수준 | 의미 |
| --- | --- |
| `error` | 분석 요청 자체를 정상적으로 완료할 수 없음 |
| `warning` | 일부 정보를 확정하지 못했지만 나머지 분석은 계속됨 |
| `info` | 결과를 생성했으나 수동 검토가 필요한 제한이 있음 |

CLI는 하나 이상의 `error` 진단이 있으면 종료 코드 `1`, 그렇지 않으면 `0`을
반환합니다.

### 진단 코드

| 코드 | 설명 |
| --- | --- |
| `PARSE_FAILED` | 파일 읽기, Python 파싱 또는 분석 루트 확인 실패 |
| `UNRESOLVED_PATH` | 라우트 경로를 문자열로 확정할 수 없음 |
| `UNRESOLVED_PREFIX` | 라우터 또는 mount prefix를 확정할 수 없음 |
| `UNRESOLVED_STATUS` | 성공 또는 예외 상태 코드를 확정할 수 없음 |
| `MODEL_NOT_FOUND` | 프로젝트에서 모델 정의를 찾을 수 없음 |
| `AMBIGUOUS_MODEL` | 동일 이름의 후보가 여러 개라 심볼을 특정할 수 없음 |
| `EXTERNAL_SYMBOL` | 프로젝트 외부 심볼이라 override 대상을 확정할 수 없음 |
| `DYNAMIC_ROUTE` | 런타임 라우트 등록 또는 동적 mount를 해석할 수 없음 |
| `MULTI_MOUNT` | 순환 라우터 마운트를 발견함 |
| `CUSTOM_VALIDATOR` | validator 로직을 선언형 제약으로 변환할 수 없음 |
| `UNSUPPORTED_SYNTAX` | 현재 출력 모델로 완전히 표현할 수 없는 선언 |

진단이 있는 결과를 소비할 때는 빈 값만 검사하지 말고 `code`, `resolved`,
`overridable`을 함께 확인해야 합니다.

## 12. 설계 보장

### 비실행 분석

프로덕션 분석 경로는 대상 프로젝트를 import하거나 실행하지 않습니다. OpenAPI
parity 테스트만 비교 목적으로 fixture 애플리케이션을 실행합니다.

### 결정적 결과

파일과 feature는 정렬된 순서로 처리됩니다. 동일한 입력과 설정은 동일한 분석
순서와 직렬화 결과를 생성해야 합니다.

### 심볼 출처 보존

프로젝트 내부 참조는 단순 이름이 아니라 모듈과 이름을 포함한 `SymbolRef`로
표현합니다. 내부 라우터 그래프도 의존성의 선언 모듈을 보존합니다.

### 불확실성 공개

해석 실패를 임의 기본값으로 대체하지 않습니다. 불확실한 값은 `None` 또는
부분 결과로 표현하고 대응하는 `AnalysisNote`를 제공합니다.

### 공개 출력 호환성

Analyzer의 하류 계약은 `models.py`의 공개 자료구조와 `serialize.py`의 JSON
형식입니다. `DependencySite`와 `RouteVariant`는 라우터 분석을 위한 내부 타입이며
직렬화 스키마에 노출되지 않습니다.

## 13. 제한 사항

정적 분석 특성상 다음 표현은 완전하게 해석되지 않을 수 있습니다.

- 함수 반환값, 환경 변수 또는 복잡한 계산으로 생성한 path와 prefix
- `add_api_route`를 포함한 런타임 라우트 등록
- 매우 깊거나 동적으로 결정되는 함수 호출 및 전이 의존성
- 실행 중 정의하고 호출하는 중첩 함수
- 임의 Python 코드로 작성된 Pydantic validator
- 한 handler에서 사용하는 복수의 독립 body 모델
- 동적으로 생성된 callable과 descriptor

추가 제한은 다음과 같습니다.

- 인증 및 외부 호출 판정 일부는 심볼 이름과 타입 휴리스틱을 사용합니다.
- 동일한 HTTP 메서드와 경로를 중복 등록하면 `feature_id`도 중복될 수 있습니다.
- 본문 모델 중첩, 상속 및 호출 그래프에는 무한 순환 방지를 위한 깊이 제한이
  적용됩니다.

해석할 수 없는 항목은 가능한 경우 진단으로 보고합니다.

## 14. 사용자 정의 Extractor

사용자 정의 extractor는 `EndpointExtractor` 프로토콜을 구현해야 합니다.

```python
class ExampleExtractor:
    name = "example"
    requires = ("route",)

    def extract(self, context):
        context.endpoint.calls_external.append("example.call")
```

`name`은 extractor 목록 안에서 고유해야 합니다. `requires`에는 먼저 실행되어야
하는 extractor 이름을 지정합니다. 목록에 존재하지 않는 의존성 이름은 선택 실행을
지원하기 위해 무시됩니다. 순환 의존성은 `TopologicalSorter` 오류를 발생시킵니다.

```python
from pathlib import Path

from testweaver.analyzer.extractors import RouteExtractor
from testweaver.analyzer.pipeline import analyze_project

result = analyze_project(
    Path("path/to/project"),
    extractors=[RouteExtractor(), ExampleExtractor()],
)
```

## 15. 검증

전체 테스트를 실행합니다.

```powershell
uv run pytest -q
```

샌드박스 또는 제한된 임시 디렉터리 환경에서는 프로젝트 내부 경로를 지정합니다.

```powershell
uv run pytest -q -p no:cacheprovider --basetemp=.test-tmp
```

정적 검사와 컴파일 검사를 실행합니다.

```powershell
uv run ruff check src tests
uv run python -m compileall -q src tests
```

회귀 테스트는 다음 범주를 포함합니다.

- OpenAPI 경로·파라미터·상태 코드 parity
- 다중 앱 및 직접 앱 라우트
- 중첩·반복·다중 라우터 마운트
- 모듈 간 심볼 및 의존성 해석
- Pydantic 상속·중첩·별칭·validator
- 직접·간접 예외 흐름
- 실행되지 않는 중첩 본문의 오판 방지
