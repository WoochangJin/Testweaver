# TestWeaver Analyzer 안내서

## 한눈에 보기

Analyzer는 FastAPI 프로젝트의 Python 파일을 **실행하지 않고** AST로 읽어
테스트 설계에 필요한 정보를 추출합니다.

입력은 프로젝트 디렉터리이고, 출력은 다음 정보를 담은 `AnalysisResult` 또는
JSON입니다.

- 실제 prefix가 합쳐진 엔드포인트 경로와 HTTP 메서드
- 성공 상태 코드와 요청·응답 모델
- body, path, query, header, cookie, form 입력 제약
- handler, route, router, app에 선언된 의존성
- 인증과 권한 요구 여부
- 직접 또는 호출 그래프에서 발생하는 예외와 상태 코드
- 외부 호출 및 비결정적 동작 후보
- 정적으로 확정하지 못한 이유를 설명하는 분석 노트

Analyzer는 테스트 코드를 생성하지 않습니다. 테스트 매트릭스와 코드 생성기가
사용할 수 있는, 정규화된 분석 결과를 만드는 계층입니다.

## 원래 설계 의도와 보존 원칙

이 절은 현재 구현을 새로 해석해 붙인 설명이 아니라, 처음 작성된 소스의
모듈 docstring, 모델 주석, 테스트와 `TestWeaver_기획서.md`에서 반복된 의도를
정리한 것입니다. 이후 analyzer를 수정할 때 지켜야 하는 기준이기도 합니다.

### 1. 대상 프로젝트를 실행하지 않는다

Analyzer의 가장 중요한 경계는 **순수 AST 정적 분석**입니다. FastAPI 앱을
import하거나 실행해서 결과를 얻지 않습니다. 분석 대상의 startup hook, DB 연결,
환경 변수 접근 같은 부작용이 사용자 머신에서 실행되지 않아야 하기 때문입니다.

OpenAPI parity 테스트만 정답 비교를 위해 fixture 앱을 실행합니다. 이 코드는
테스트에만 있고 실제 분석 경로에는 들어가지 않습니다.

### 2. 수집과 판정을 분리한다

Pass 0과 Pass 1은 파일과 심볼을 최대한 있는 그대로 수집합니다. 예를 들어
클래스를 색인하는 단계에서 곧바로 Pydantic 모델이라고 단정하지 않고, 프로젝트
인덱스가 완성된 뒤 상속 관계와 import를 따라 판정합니다.

이 원칙 때문에 파일 순서에 따라 분석 결과가 달라지지 않고, 다른 파일에 있는
부모 모델·의존성·예외 처리기도 해석할 수 있습니다.

### 3. 이름이 아니라 심볼의 출처를 보존한다

`LoginRequest`나 `get_current_user` 같은 단순 이름만 저장하면 동명 심볼을
구분할 수 없고, 다음 단계가 올바른 import 또는 dependency override를 만들 수
없습니다. 그래서 공개 모델은 `(module, name)`을 가진 `SymbolRef`를 사용합니다.

라우터에서 상속된 의존성도 AST 노드만 전달하지 않고 **어느 모듈에서 선언됐는지**
함께 전달합니다. 이 정보는 내부 처리용이며 최종 공개 스키마는 기존처럼
`DependencyNode.source`와 `origin`으로 유지됩니다.

### 4. 확정하지 못한 정보를 성공처럼 꾸미지 않는다

정적 분석은 모든 Python 표현을 해석할 수 없습니다. 이때 임의 기본값이나 빈
목록으로 덮지 않고 `AnalysisNote`를 남깁니다. 예를 들어 상태 코드 인자는 있지만
값을 풀지 못했다면 `200`으로 가정하지 않고 `null`과 `UNRESOLVED_STATUS`를
내보냅니다.

즉, 결과의 빈 값과 “분석하지 못한 값”을 구분할 수 있어야 한다는 것이 원래
설계 계약입니다.

### 5. 추출기는 독립적으로 확장할 수 있어야 한다

각 extractor는 `ExtractionContext` 하나를 받아 자기 책임만 수행합니다. 실행
순서는 중앙 목록의 위치가 아니라 `requires` 의존성으로 선언하며 위상 정렬로
결정합니다. 새 extractor를 추가할 때 기존 extractor의 호출 코드를 다시 엮지
않는 구조를 유지합니다.

### 6. 하류 단계와의 공개 계약을 안정적으로 유지한다

Analyzer의 공개 계약은 `models.py`의 자료구조와 `serialize.py`의 JSON 형태입니다.
현재 수정은 이 공개 필드를 삭제하거나 이름을 바꾸지 않았습니다. 라우터 마운트와
심볼 출처를 정확히 보존하기 위한 `DependencySite`, `RouteVariant`는 내부
인덱싱 타입이며, 매트릭스·코드 생성 단계가 소비하는 출력 형식은 그대로입니다.

### 이번 수정이 원래 의도를 강화한 부분

| 수정 | 보존하거나 강화한 원래 의도 |
| --- | --- |
| 앱·라우터 의존성의 선언 모듈 보존 | 문자열이 아닌 정확한 심볼 출처 유지 |
| 다중 앱의 의존성 분리 | 실제 FastAPI 구조를 endpoint 단위로 정확히 표현 |
| 다중 마운트의 경로·의존성·태그 분리 | 하나의 실제 route variant를 하나의 기능으로 표현 |
| 일반 객체의 `.get()` 데코레이터 제외 | 라우트를 이름만으로 추측하지 않음 |
| 반복 사용된 중첩 모델을 필드별로 전개 | 재귀 방지와 정상 형제 필드 분석을 구분 |
| 실행되지 않는 중첩 함수 본문 제외 | 실행 가능 흐름을 과장하지 않는 보수적 분석 |
| 실패·동적 선언을 노트로 유지 | 불확실성을 조용히 숨기지 않음 |

### analyzer가 의도적으로 맡지 않는 책임

다음 단계는 analyzer의 출력 소비자 또는 다른 모듈의 책임입니다.

- 분석 결과로 정상·경계·예외 테스트 케이스를 조합하는 일
- 사용자가 선택할 테스트 매트릭스 UI를 만드는 일
- pytest 코드를 생성하고 프로젝트 스타일에 맞추는 일
- 생성된 테스트를 실행하고 실패를 수정하는 일
- 프로젝트 전체 CLI와 배포·패키징 흐름을 완성하는 일

따라서 analyzer 변경은 위 기능을 직접 구현하기보다, 그 기능들이 판단할 수 있는
근거를 정확하고 설명 가능한 형태로 제공하는 데 집중해야 합니다.

## 실행 방법

요약만 확인:

```powershell
.\.venv\Scripts\python.exe -m testweaver.analyzer path\to\fastapi-project --summary
```

JSON을 화면에 출력:

```powershell
.\.venv\Scripts\python.exe -m testweaver.analyzer path\to\fastapi-project
```

JSON 파일로 저장:

```powershell
.\.venv\Scripts\python.exe -m testweaver.analyzer path\to\fastapi-project -o analysis.json
```

Python 코드에서는 다음과 같이 사용합니다.

```python
from pathlib import Path

from testweaver.analyzer.pipeline import analyze_project
from testweaver.analyzer.serialize import dumps

result = analyze_project(Path("path/to/fastapi-project"))
print(dumps(result))
```

분석 루트가 없으면 예외로 중단하지 않고 오류 노트를 반환하며 CLI 종료 코드는
`1`이 됩니다. 정상 분석은 `0`입니다.

## 처리 흐름

Analyzer는 세 단계로 동작합니다.

1. **Pass 0 — 파일 수집과 파싱**
   Python 파일을 한 번씩 읽어 AST로 변환합니다. 읽기 실패나 문법 오류가 있는
   파일은 `PARSE_FAILED` 노트를 남기고 건너뜁니다.
2. **Pass 1 — 프로젝트 인덱스 구축**
   모듈, import, 클래스, 함수, 상수, 타입 별칭, 라우터 마운트, 예외 처리기를
   색인합니다. 이후 단계는 파일을 다시 읽지 않습니다.
3. **Pass 2 — 엔드포인트별 추출**
   라우트마다 extractor를 의존 순서에 맞춰 실행해 `Endpoint`, `Constraint`,
   `DependencyNode`, `ExceptionFlow`를 채웁니다.

기본 extractor의 역할은 다음과 같습니다.

| Extractor | 역할 |
| --- | --- |
| `route` | 경로, 메서드, 상태 코드, 응답 모델, 태그 |
| `dependency` | 네 선언 위치의 의존성과 전이 의존성 |
| `params` | path/query/header/cookie/form 파라미터와 요청 모델 |
| `body` | Pydantic 모델의 필드·상속·중첩 제약 |
| `auth` | 401/403, scope, 이름 단서를 통한 인증·권한 판정 |
| `exception` | handler, 서비스 호출, 의존성의 예외 흐름 |
| `effects` | DB·HTTP 등 외부 호출과 시간·난수 등 비결정성 후보 |

실행 순서는 목록 순서가 아니라 각 extractor의 `requires`로 결정됩니다.

## 라우터와 의존성 처리

FastAPI의 실제 경로는 보통 여러 파일에 나뉩니다.

```python
# main.py
app.include_router(router, prefix="/api/v1")

# routes.py
router = APIRouter(prefix="/orders")

@router.get("/{order_id}")
def get_order(order_id: int): ...
```

Analyzer는 이를 `GET /api/v1/orders/{order_id}`로 합칩니다. 중첩 라우터와
동일 라우터의 다중 마운트도 처리합니다. 다중 마운트에서는 각 경로의
의존성과 태그를 섞지 않고 별도로 유지합니다.

의존성은 다음 네 위치를 모두 수집합니다.

- `FastAPI(dependencies=[...])` — `app`
- `APIRouter(dependencies=[...])` 및 `include_router(..., dependencies=[...])` — `router`
- 라우트 데코레이터의 `dependencies=[...]` — `route`
- handler 인자의 `Depends` 또는 `Security` — `handler`

의존성 이름은 선언된 원본 모듈 기준으로 해석합니다. 따라서 앱 설정 파일과
라우트 파일에 동명 함수가 있어도 잘못 연결하지 않습니다.

## 결과 읽는 법

`features`의 원소 하나가 엔드포인트 하나입니다. 핵심 필드는 다음과 같습니다.

| 필드 | 의미 |
| --- | --- |
| `feature_id` | `METHOD /path` 형태의 기능 식별자 |
| `success_status_code` | 확정된 성공 상태 코드. 해석 실패 시 `null` |
| `constraints` | 입력 위치와 필드별 제약 목록 |
| `dependencies` | 원본 심볼, 선언 위치, scope, override 가능 여부 |
| `exceptions` | 예외 타입, 상태 코드, 발생 함수, 호출 깊이 |
| `requires_auth` | 인증 정보가 필요한지 여부 |
| `requires_permission` | 역할·scope 등 권한 검사가 필요한지 여부 |
| `calls_external` | 테스트에서 mock/fixture가 필요할 수 있는 호출 |
| `nondeterministic` | 시간·UUID·난수처럼 결과 고정이 필요한 호출 |
| `notes` | 해당 기능에서 정적으로 확정하지 못한 내용 |

`Constraint.location`은 값을 어디에 실어야 하는지 나타냅니다. body 필드는
중첩 구조를 `address.zipcode` 같은 점 표기로 펼치며, 중첩 모델 자체에 대한
제약도 함께 남깁니다.

## 분석 노트

정적 분석 실패를 빈 값으로 숨기지 않고 `AnalysisNote`로 기록합니다.

- `ERROR`: 분석 요청 자체를 정상 완료하지 못한 상태입니다. 현재 대표 사례는
  분석 루트가 존재하지 않는 경우입니다.
- `WARNING`: 일부 파일·경로·상태 코드를 확정하지 못했지만 나머지 분석은
  계속했습니다.
- `INFO`: 결과는 만들었지만 수동 검토가 필요한 제한이 있습니다.

자주 보는 코드는 다음과 같습니다.

| 코드 | 의미와 대응 |
| --- | --- |
| `PARSE_FAILED` | 파일 읽기 또는 Python 파싱 실패. 해당 파일을 직접 확인합니다. |
| `UNRESOLVED_PATH` | 라우트 경로가 동적 값이라 확정되지 않았습니다. |
| `UNRESOLVED_PREFIX` | router 또는 mount prefix를 상수로 풀지 못했습니다. |
| `UNRESOLVED_STATUS` | 성공 또는 예외 상태 코드를 확정하지 못했습니다. |
| `MODEL_NOT_FOUND` | 요청 모델 정의를 프로젝트에서 찾지 못했습니다. |
| `DYNAMIC_ROUTE` | 런타임 등록 라우트 또는 해석 불가능한 mount가 있습니다. |
| `CUSTOM_VALIDATOR` | validator 존재는 확인했지만 규칙을 제약으로 변환하지 못했습니다. |
| `UNSUPPORTED_SYNTAX` | 여러 body 모델 등 현재 표현 범위를 벗어난 선언입니다. |

`WARNING`과 `INFO`가 있다고 분석 전체가 실패한 것은 아닙니다. 다만 해당
엔드포인트의 자동 생성 케이스는 노트와 함께 검토해야 합니다.

## 지원 범위와 알려진 한계

현재 구현은 일반적인 FastAPI 선언을 안정적으로 다루지만, Python 실행 결과를
완전히 대신하지는 않습니다.

- 리터럴과 색인 가능한 모듈 상수는 해석하지만 함수 반환값, 환경 변수,
  복잡한 계산으로 만든 경로·prefix는 실행하지 않습니다.
- `add_api_route`처럼 런타임에 등록하는 라우트는 누락 가능성을 노트로 남깁니다.
- 호출 그래프와 전이 의존성은 깊이 제한이 있습니다. 매우 깊거나 동적인 호출은
  결과에 포함되지 않을 수 있습니다.
- 호출 그래프는 프로젝트의 최상위 함수를 중심으로 따라갑니다. 실행 중 생성해
  호출하는 중첩 함수나 동적 callable은 완전히 추적하지 않습니다.
- 커스텀 Pydantic validator의 임의 Python 로직은 `CUSTOM_VALIDATOR`로 표시하며
  자동으로 경계값 제약으로 변환하지 않습니다.
- 여러 body 모델을 한 handler에서 받으면 첫 모델을 대표 모델로 사용하고
  `UNSUPPORTED_SYNTAX` 노트를 남깁니다.
- 외부 호출과 인증 판정 일부는 이름·타입 휴리스틱을 사용하므로 프로젝트별
  명명 규칙에 따라 수동 확인이 필요할 수 있습니다.
- 동일한 HTTP 메서드와 경로를 중복 등록하면 `feature_id`도 중복될 수 있습니다.
  FastAPI 라우트 선언 자체의 중복 여부를 먼저 정리하는 것이 안전합니다.
- 기본 제외 패턴에는 `tests`, 가상환경, `site-packages`, `.git` 등이 포함됩니다.
  `exclude_patterns`를 직접 넘기면 기본 목록에 추가되는 것이 아니라 **기본 목록을
  대체**합니다.

이 한계 때문에 생성 단계에서는 `notes`, `resolved`, `overridable` 값을 무시하지
않아야 합니다.

## 검증 방법

전체 회귀 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.test-tmp
```

코드 검사와 컴파일 확인:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m compileall -q src tests
```

현재 회귀 테스트에는 다중 앱, 직접 앱 라우트, 중첩·다중 마운트, 모듈 간
의존성, 전이 타입 별칭, 반복 중첩 모델, 실행되지 않는 중첩 함수 오판 등이
포함됩니다.

## 새 extractor 추가

`EndpointExtractor` 규약에 맞춰 `name`, `requires`, `extract(context)`를
구현하고 `DEFAULT_EXTRACTORS`에 인스턴스를 추가합니다.

```python
class ExampleExtractor:
    name = "example"
    requires = ("route",)

    def extract(self, context):
        ...
```

`requires`에 적힌 이름을 바탕으로 위상 정렬되므로 목록에서 수동으로 실행
순서를 맞출 필요는 없습니다. 순환 의존성을 만들면 `TopologicalSorter`가
오류를 발생시키므로 반드시 extractor 순서 테스트도 함께 추가합니다.
