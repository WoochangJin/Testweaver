# TestWeaver 설계 결정 기록

이 문서는 각 트랙에서 내린 주요 설계 결정과 그 이유를 기록합니다. 목적은 두 가지입니다.

1. **"왜 이렇게 만들었는가"를 나중에 다시 찾아보기 쉽게** — 이슈나 PR 코멘트에 흩어진 결정 근거를 한곳에 모아둡니다.
2. **결과보고서 작성 시 재활용** — 이 문서를 취합하면 결과보고서의 "설계 과정" 섹션 초안이 됩니다.

## 작성 방법

결정을 내렸을 때 자신의 트랙 섹션 아래에 항목을 추가해주세요. 형식:

```
### [결정 제목]
- **무엇을 결정했나**:
- **왜** (고려했던 대안 포함):
- **트레이드오프**:
- **관련 이슈/PR**: #번호
```

짧게 써도 괜찮습니다. 나중에 결과보고서 쓸 때 다듬으면 됩니다.

---

## Track A, B — 기능 추출 (① 테스트 대상 기능 추출)

### AST 기반 정적 분석 방식 채택
- **무엇을 결정했나**: FastAPI 프로젝트를 직접 실행하지 않고 Python의 AST를 이용해 라우터, 엔드포인트, 의존성, 예외 처리 구조를 분석하도록 구현.
- **왜** (고려했던 대안 포함): 프로젝트를 직접 실행하는 방식은 데이터베이스, 환경변수, 외부 서비스 등 실행환경이 필요하고 분석 중 부작용이 발생할 수 있음. AST 정적 분석은 프로젝트를 실행하지 않고도 코드 구조를 안전하게 확인할 수 있어 채택.
- **트레이드오프**: 함수 반환값이나 환경변수로 동적으로 만들어지는 경로처럼 실행해야만 알 수 있는 값은 완전히 분석하지 못할 수 있음. 이런 경우 잘못된 값을 임의로 생성하지 않고 `AnalysisNote`로 기록.
- **관련 이슈/PR**: #13, #27

### 실제 FastAPI 앱에 연결된 라우터만 엔드포인트로 추출
- **무엇을 결정했나**: `APIRouter`에 라우트가 선언되어 있어도 `FastAPI.include_router()`를 통해 실제 앱에 연결된 라우터만 최종 엔드포인트로 추출.
- **왜** (고려했던 대안 포함): 선언된 라우트를 모두 추출하면 실제 앱에서 사용되지 않는 미장착 라우터까지 테스트 대상에 포함되는 오류가 발생함. 따라서 라우터와 앱의 연결 관계를 추적하고, 실제로 장착된 경로만 결과에 포함하도록 변경.
- **트레이드오프**: 동적으로 `include_router()`를 호출하거나 실행 중 라우터를 등록하는 구조는 정확한 연결 여부를 판단하기 어려울 수 있음. 판단할 수 없는 동적 등록은 경고로 남김.
- **관련 이슈/PR**: #13, #27

### 라우터 마운트별 경로·의존성·태그를 독립적으로 관리
- **무엇을 결정했나**: 동일한 라우터가 여러 위치에 마운트될 수 있으므로 각 마운트의 `prefix`, `dependencies`, `tags`를 별도의 라우트 변형으로 관리.
- **왜** (고려했던 대안 포함): 라우터 하나당 경로 정보를 하나만 저장하면 동일한 라우터가 서로 다른 prefix나 의존성으로 여러 번 연결될 때 마지막 정보로 덮어써지는 문제가 발생함. 각 연결 경로를 독립적으로 보존해야 실제 엔드포인트를 정확히 추출할 수 있음.
- **트레이드오프**: 동일한 핸들러가 여러 엔드포인트로 추출될 수 있어 결과 개수가 늘어날 수 있지만, 실제 앱에서 서로 다른 URL로 제공되는 기능이므로 별도 엔드포인트로 취급하는 것이 맞다고 판단.
- **관련 이슈/PR**: #13, #27

### Analyzer 출력 스키마 확장
- **무엇을 결정했나**: 분석 결과에 고유한 `Feature.id`를 추가하고, 입력 제약조건에 `Constraint.location`을 추가해 `path`, `query`, `header`, `cookie`, `body`, `form`을 구분하도록 결정. 클래스 이름은 `RouteInfo`에서 `Endpoint`, `FieldConstraint`에서 `Constraint`로 정리.
- **왜** (고려했던 대안 포함): 핸들러 이름만으로는 서로 다른 파일이나 경로의 기능이 겹칠 수 있어 `"{HTTP 메서드} {경로}"` 형식의 `Feature.id`가 필요했음. 또한 모든 파라미터를 하나의 body 제약조건처럼 전달하면 path/query/header 값까지 JSON body에 들어가는 문제가 생기므로 위치 정보가 필요했음.
- **트레이드오프**: 하류 트랙에서 `Feature`를 직접 생성하는 코드에 `id`를 추가해야 하며, case generator도 `Constraint.location`에 따라 값을 분리해서 처리해야 함. 스키마 변경 내용을 팀에 공지하고 C 트랙 대응 이슈를 별도로 관리하기로 함.
- **관련 이슈/PR**: #27, #28, #29

### 예외 처리기의 반환 응답에서 상태 코드 추출
- **무엇을 결정했나**: 예외 처리기 함수 안에 있는 모든 `status_code=` 호출을 확인하는 대신, 실제 `return` 문으로 반환되는 응답에서 상태 코드를 추출하도록 범위를 제한.
- **왜** (고려했던 대안 포함): 기존 방식은 로깅 함수나 일반 헬퍼 함수에 `status_code=`가 있으면 그것을 실제 응답 코드로 잘못 판단할 수 있었음. 반환되는 응답만 확인해야 예외와 실제 HTTP 상태 코드의 연결을 더 정확하게 분석할 수 있음.
- **트레이드오프**: 응답을 변수에 저장하거나 복잡한 함수를 거쳐 반환하는 경우에는 상태 코드를 찾지 못할 수 있음. 이 경우 잘못된 값을 추측하지 않고 분석 경고를 남김.
- **관련 이슈/PR**: #27 후속 리뷰 수정

### 예외 처리기 상태 코드 해석 시 실행되지 않는 중첩 정의 배제
- **무엇을 결정했나**: `handler_map.py`의 `_status_in_body`가 함수 본문을 `ast.walk`으로 순회하던 것을 `ast_utils.iter_runtime_nodes`로 교체.
- **왜** (고려했던 대안 포함): 바로 위 "return 문으로 범위 제한" 수정은 PR #27 리뷰 코멘트 하나는 해결했지만, 여전히 `ast.walk`을 쓰고 있어서 핸들러 안에 정의만 되고 실제로는 호출되지 않는 중첩 함수·클래스의 `return`까지 같이 잡히는 문제가 남아 있었음. `iter_runtime_nodes`는 정확히 이 문제(실행되지 않는 중첩 정의로 내려가는 것) 때문에 이미 만들어져 있었고 `exception.py`는 이걸 올바르게 쓰고 있었는데, `handler_map.py`만 빠져 있었음. 재현 코드를 직접 실행해 확인: 핸들러 안에 미사용 중첩 함수가 있고 그 안에 `return`이 있으면, 실제 응답의 상태 코드보다 그 미사용 함수의 상태 코드가 먼저 채택됨(예: 실제 404/410 대신 500이 채택).
- **트레이드오프**: 없음 — 이미 검증된 헬퍼를 재사용하는 것이라 새 리스크 없이 버그만 닫힘.
- **관련 이슈/PR**: #41, #42

### 분석 오류에 대한 회귀 테스트 추가
- **무엇을 결정했나**: 실제 개발 과정에서 발견한 라우터 추출 오류가 다시 발생하지 않도록 `tests/analyzer/test_regressions.py`와 `test_edge_app.py`에 회귀 테스트를 추가.
- **왜** (고려했던 대안 포함): 앱 의존성 상속, 다중 마운트, 미장착 라우터, FastAPI가 아닌 객체의 `add_route`, 사용되지 않는 중첩 함수, 예외 처리기 상태 코드 등의 오류는 단순 정상 사례 테스트만으로 발견하기 어려움. 발견한 결함을 각각 테스트로 남겨 이후 수정으로 같은 문제가 재발하지 않게 함.
- **트레이드오프**: 테스트와 픽스처 수가 늘어나지만 Analyzer의 변경 범위가 크기 때문에 정확성과 회귀 방지가 더 중요하다고 판단.
- **관련 이슈/PR**: #13, #27

---

## Track C — 규칙 기반 매트릭스 생성 (② 테스트 케이스 매트릭스 생성)

### 규칙 기반 케이스 도출 구조 채택 (derive_* + build_case_matrix)
- **무엇을 결정했나**: `case_generator/`에 `derive_normal_cases`, `derive_boundary_cases`, `derive_failure_cases`, `derive_security_cases` 4개 규칙 함수와 이를 조합하는 `build_case_matrix`를 구현. Feature의 constraints, exceptions, 인증 요구사항을 근거로 케이스를 규칙 기반으로 도출하도록 함.
- **왜** (고려했던 대안 포함): analyzer(Track A/B)의 실제 구현체가 나오기 전에 case_generator 개발을 먼저 진행할 수 있도록, 합의된 JSON 계약 구조를 따르는 임시 Feature/Endpoint 모델을 analyzer/models.py에 먼저 추가해 병행 개발. 각 요청을 실제로 구성할 수 있도록 `payload.py`에서 sample_payload를 함께 생성하고, TestCaseMatrix에는 analyzer/case_generator 간 합의된 계약에 맞춰 endpoint/method 필드를 포함.
- **트레이드오프**: 병행 개발을 위해 만든 임시 모델을 되돌리는 과정(revert)에서 case_generator가 이미 참조하고 있던 필드(sample_payload, endpoint/method)가 함께 삭제되어 TypeError가 발생, 별도 커밋으로 복구해야 했음. 병행 개발은 속도를 얻는 대신 계약이 확정되기 전까지 이런 동기화 비용을 감수해야 함.
- **관련 이슈/PR**: #20 (feature/case-matrix)

### case_generator 자체 모델을 schema.py 기준으로 통일
- **무엇을 결정했나**: case_generator가 schema.py 대신 자체 models.py(dataclass 기반 TestCase/TestCaseMatrix/TestCaseCategory)를 따로 정의해 쓰던 구조를 schema.py(pydantic BaseModel) 기준으로 통일. `rules/{normal,boundary,failure,security}.py`의 import를 `schema.CaseCategory`/`CaseSource`/`TestCase`로 교체하고 source에 `CaseSource.RULE`을 명시, 참조가 없어진 `case_generator/models.py`는 삭제.
- **왜** (고려했던 대안 포함): writer.py, selection.py처럼 schema 타입의 `model_dump()`/`model_copy()`에 의존하는 다운스트림 코드에 case_generator 결과가 연결되면 AttributeError가 발생하는 구조였고, `schema.TestCase.source`가 기본값 없는 필수 필드라 기존 rule 생성 코드를 그대로 넘기면 ValidationError도 나는 상황이었음. 두 모델을 계속 따로 유지하는 대안도 있었지만, 다운스트림 코드가 늘어날수록 변환 계층 비용이 커진다고 판단해 계약을 하나로 합침.
- **트레이드오프**: rules/* 4개 파일을 전부 수정해야 했지만, 기존 테스트가 모두 통과함을 확인해 회귀 없이 정리.
- **관련 이슈/PR**: #32 (Fixes), PR #40

### Constraint.location 기준으로 payload 구성 범위 제한
- **무엇을 결정했나**: `build_valid_payload`가 위치 구분 없이 모든 constraint를 payload에 채우던 것을, `location`이 BODY인 constraint만 필터링해서 구성하도록 수정. `derive_boundary_cases`는 `feature.constraints_in(ParamLocation.BODY)`로 순회 범위를 body 제약으로 한정하고, `derive_failure_cases`는 `exc.resolved`가 False인(=expected_status 확정 불가) 예외는 스킵하도록 함.
- **왜** (고려했던 대안 포함): Track A/B에서 `Constraint.location`(path/query/header/cookie/body 구분) 필드가 추가된 이후에도 payload 생성 로직이 이를 반영하지 못해, query/header/path 값까지 body(sample_payload)에 섞여 들어갔음. 그 결과 GET/DELETE나 인증이 필요한 엔드포인트에서 생성된 pytest가 실제로는 통과해야 할 케이스인데도 422/404로 깨지는 문제가 있었음.
- **트레이드오프**: query/header/cookie 파라미터를 실제 요청에 실어 보내는 기능(TestCase 필드 신설 + Jinja 템플릿 반영)은 이번 수정 범위 밖으로 남기고 별도 이슈로 분리 — body 외 위치 값을 "요청에 반영"하는 것과 "payload에 안 섞이게 막는 것"을 별개 문제로 다뤄, 수정 범위를 좁게 유지.
- **관련 이슈/PR**: #28 (Fixes)

### path_params 필드 추출 로직 추가
- **무엇을 결정했나**: `case_generator/payload.py`에 `build_path_params()` 헬퍼를 추가해 `endpoint.path`에서 `{name}` 패턴을 정규식으로 추출. normal/boundary/failure/security 4개 규칙 함수 모두에서 TestCase 생성 시 path_params를 채우도록 수정.
- **왜** (고려했던 대안 포함): 매트릭스 스키마에 `path_params` 필드는 먼저 추가돼 있었지만(Track E 결정), 실제 값을 채워 넣는 추출 로직은 case_generator 쪽에 아직 반영되지 않은 상태였음. `GET /api/users/{user_id}`처럼 경로에 placeholder가 있는 엔드포인트를 커버하려면 4개 규칙 함수 모두 이 로직을 공유해야 했음.
- **트레이드오프**: 없음 — 필드를 채우는 로직만 추가된 것이라 기존 케이스와 하위 호환.
- **관련 이슈/PR**: PR #19 이후 커밋

### allowed_values(enum) boundary 케이스 처리 추가
- **무엇을 결정했나**: `Constraint.allowed_values` 제약이 boundary 케이스 생성에서 누락돼 있던 것을 추가. 허용 목록에 없는 값을 넣었을 때 422가 나오는지 검증하는 `invalid_choice` 케이스를 신설. `_valid_value`가 `allowed_values`를 최우선으로 고려하도록 수정해, enum 제약이 걸린 필드도 정상(NORMAL) 케이스에서 유효한 값을 갖도록 함. 동시에 `build_invalid_payload`의 `below_min_length`/`above_max_length`가 constraint의 실제 min/max 값을 기준으로 정확한 경계값을 생성하도록 수정.
- **왜** (고려했던 대안 포함): enum(허용값 목록) 제약을 가진 필드에 대한 케이스 생성 규칙이 애초에 규칙 목록에서 빠져 있었음. NORMAL 케이스에서 `_valid_value`가 allowed_values를 고려하지 않으면, enum 필드가 있는 엔드포인트는 정상 케이스조차 422로 실패하는 부작용이 있었음.
- **트레이드오프**: 없음 — 기존 규칙에 조건 분기 하나를 추가하는 형태라 다른 케이스 생성 로직에 영향 없음.
- **관련 이슈/PR**: PR #12 이후 커밋

### success_status_code 처리 정합성 확보 (2단계 수정)
- **무엇을 결정했나**: 1차로 `derive_normal_cases`가 NORMAL 케이스의 `expected_status`를 항상 200으로 고정하던 것을 `feature.endpoint.success_status_code` 기준으로 바꿈. 이후 이 수정이 `success_status_code or 200` 형태였던 탓에 "분석 실패로 None이 반환된 경우"까지 200으로 뭉개버리는 2차 버그를 발견해, `or 200`을 제거하고 None을 그대로 전달하도록 재수정.
- **왜** (고려했던 대안 포함): `status_code=204`로 선언된 DELETE 같은 라우트도 항상 200을 기대해, 생성된 pytest가 실제 응답(204)과 어긋나 실패하는 문제가 있었음. 1차 수정 이후에도 "해석 실패(None)"와 "성공 코드 없음(200 확정)"이라는 서로 다른 두 상황이 `or 200` 한 줄로 뭉뚱그려져, 분석이 실패한 상황이 조용히 잘못된 기대값(200)으로 둔갑하는 문제가 남아 있었음. 잘못된 값을 임의로 확정하지 않고 None을 그대로 흘려보내는 쪽을 선택.
- **트레이드오프**: `render.py`/`test_case.py.j2` 템플릿은 이미 `expected_status=None`을 "-" 표시 및 `pytest.skip`으로 안전하게 처리하고 있어, 템플릿 쪽 추가 수정은 필요 없었음.
- **관련 이슈/PR**: #36 (Fixes), PR #43

---

## Track D — LLM 보강 (② LLM 보강) + CLI (③ 사용자 조합 기반 테스트 생성)

### 케이스 선택 문법과 표시 순서를 단일 정렬 함수에 위임
- **무엇을 결정했나**: 사용자가 케이스를 행 번호로 고르도록 `parse_selection`이 콤마 구분 번호·범위(`1,3,5-7`)와 대소문자 무시 키워드 `all`/`none`을 받게 함. 매트릭스는 feature 단위로 하나씩(`render_matrix`) 패널로 출력하고, 한 매트릭스 안에서는 `group_cases_by_category`로 카테고리별(NORMAL→BOUNDARY→FAILURE→SECURITY)로 묶음. 표시용 인덱스(1-based)와 선택 해석은 둘 다 `order_cases_for_selection` 하나만 거치도록 강제.
- **왜** (고려했던 대안 포함): 매트릭스 JSON을 그대로 보여주고 케이스 id를 입력받는 방식은 사람이 쓰기 어려움. 표의 행 번호로 고르게 하려면 화면 정렬 순서와 선택 해석 순서가 반드시 일치해야 하는데, 렌더링과 선택이 각자 정렬을 구현하면 어긋날 수 있어 두 경로가 같은 함수에 위임하도록 함. 범위(`5-7`)·전체(`all`)·해제(`none`)는 흔한 패턴이라 문법으로 지원.
- **트레이드오프**: 표시 인덱스↔케이스 매핑이 `order_cases_for_selection`에 의존하므로, 정렬 규칙을 바꾸면 렌더링·선택을 함께 재검증해야 함 (#38에서 priority 정렬을 이 함수에 추가할 때 실제로 두 경로를 같이 확인).
- **관련 이슈/PR**: #5 (feature/cli-select, PR #23)

### `select` 단일 명령어를 analyze / generate / test / run으로 재편
- **무엇을 결정했나**: 매트릭스 JSON을 읽어 케이스를 고르고 결과를 다시 JSON에 되쓰던 `select` 명령어를 없애고, CLI를 `analyze`(프로젝트 → 매트릭스 JSON), `generate`(매트릭스 JSON → 대화형 선택 → pytest 모듈), `test`(생성된 pytest를 in-process 실행), `run`(위 셋을 중간 파일 없이 한 번에)으로 재편. 사용자 선택은 독립 명령어로 노출하지 않고 `generate`/`run` 안의 대화형 프롬프트로 흡수. orchestration 로직은 Typer 인자 파싱과 분리해 `pipeline.py`에 둠.
- **왜** (고려했던 대안 포함): (1) `generate`/`select`/`test`처럼 내부 구현 단계를 그대로 명령어로 노출하기보다 사용자 관점에서 자연스러운 단위로 묶는 게 낫다고 판단 — select는 generate의 일부지 별도 산출물이 아님. (2) 각 단계를 파일 입출력으로만 분리하는 안과 전체를 한 번에만 실행하는 안 중 양쪽을 다 살림: 개발·디버깅 때는 단계별로 독립 실행하며 중간 매트릭스 JSON을 확인하고, 실제 사용자는 `run` 한 번으로 끝냄. (3) case_generator가 만든 케이스를 전부 자동으로 pytest에 넘기지 않고 feature별로 사람에게 보여주고 고르게 하는 human-in-the-loop 구조는 유지 — 자동 생성기가 만든 불필요·부적절한 케이스를 사용자가 걸러낼 수 있음. `run`은 TestWeaver에서 처음으로 analyze → build_matrices → 선택 → pytest 생성·실행 전체가 실제로 이어진 지점.
- **트레이드오프**: 테스트해야 할 CLI 실행 경로가 늘어남(4개 명령어 + `run` 조합). 기존 `select`가 하던 "선택 결과를 매트릭스 JSON에 되쓰기"를 버리고 pytest를 바로 출력하도록 바꿔, 선택 상태를 파일로 보존해 재사용하는 워크플로는 포기. 생성과 선택이라는 서로 다른 책임이 `generate` 한 명령어에 들어감.
- **관련 이슈/PR**: #31 (feature/cli-integration, PR #39)

### case_generator 출력을 pytest 렌더링용으로 정규화하는 계층을 pipeline에 둠
- **무엇을 결정했나**: `pipeline._normalize_case`가 case_generator가 낸 `TestCase`를 그대로 쓰지 않고 (1) `id`의 `::` 계층 구분자를 identifier-safe 문자로 치환하고, (2) bodyless 메서드(GET/DELETE/HEAD/OPTIONS)에서는 `sample_payload`를 `None`으로 비운 복사본을 만들어 넘기도록 함.
- **왜** (고려했던 대안 포함): case_generator의 id 규칙(`::` 구분)과 payload 생성 방식(메서드 무관하게 sample_payload 채움)은 case_generator 자체 계약상 정상인데, `generator.py`의 pytest 함수명에는 `::`가 못 들어가고 httpx `TestClient.get()`/`delete()` 등은 json body를 받지 않음. case_generator를 직접 고쳐 D 쪽 요구를 반영하는 대신 통합 계층에서 `model_copy`로 정규화해 트랙 간 결합도를 낮춤 — 어떤 필드를 왜 바꾸는지가 `_normalize_case` 한 곳에 드러남.
- **트레이드오프**: 통합 지점에 case_generator 출력을 손보는 코드가 한 겹 생김. case_generator가 이 제약(identifier-safe id, 메서드별 payload)을 직접 만족하게 되면 이 계층은 제거 대상.
- **관련 이슈/PR**: #31

### 전체 파이프라인 E2E 테스트 도입 + 잠복 결함을 xfail(strict=True)로 명시
- **무엇을 결정했나**: `runner.invoke(app, ["run", DEMO_APP_ROOT, ...], input=...)`로 실제 demo FastAPI 프로젝트에 사용자 선택까지 흉내 내는 end-to-end 테스트를 추가. `run` 연결 직후 이 테스트에서 드러난 두 결함 — NORMAL 케이스가 `expected_status`를 무조건 200으로 생성(→ 204 endpoint 실패), 타입 없는 `dict` body 파라미터에서 유효한 login payload를 만들지 못함(→ 422) — 을 CLI에서 보정하거나 테스트를 지우지 않고 `@pytest.mark.xfail(..., strict=True)`로 남기고 #36/#37로 별도 추적.
- **왜** (고려했던 대안 포함): 각 단계 unit test가 다 통과해도 전체를 이으면 드러나는 문제가 있으므로 통합 경로 자체를 테스트해야 함. 실패를 CLI 버그로 오해하지 않도록 (a) CLI 테스트가 통과하게 억지 보정, (b) E2E 테스트 삭제, (c) skip, (d) 알려진 upstream 문제로 명시 중 (d)를 택함 — D가 다른 트랙의 결함을 몰래 보정해 소유권을 섞지 않고, 통합 테스트는 유지하면서 현재 시스템의 한계를 명시적으로 기록. `strict=True`라 #36/#37이 고쳐져 테스트가 XPASS하면 CI가 알려주고, 그때 xfail을 제거할 수 있음.
- **트레이드오프**: 통합 테스트가 실제 pytest 실행까지 포함해 느리고, xfail이 붙어 있는 동안은 그 경로의 회귀를 자동으로 못 잡음.
- **관련 이슈/PR**: #31 (PR #39), #36, #37 — #36은 Track C의 "success_status_code 처리 정합성 확보" 항목에서도 다뤄짐

### CLI 선택 프롬프트를 매트릭스별 → 전역 단일 프롬프트로 변경
- **무엇을 결정했나**: `generate`/`run` 커맨드에서 매트릭스마다 반복하던 선택 프롬프트 루프(`_select_matrix_interactively`)를 없애고, 모든 매트릭스를 `render_matrices`로 한 번에 출력한 뒤 `typer.prompt`로 전체에 대해 한 번만 입력받아 반영하도록 변경. 이를 위해 `render_matrix`가 매트릭스마다 1로 리셋하던 행 번호를 `render_matrices`가 이어서 넘길 수 있도록 `start_index` 파라미터를 추가하고, `selection.py`에 여러 매트릭스에 걸친 전역 인덱스를 처리하는 `select_cases_globally`를 추가.
- **왜** (고려했던 대안 포함): 매트릭스 수만큼 프롬프트를 반복하는 것은 사용자 입력 횟수만 늘릴 뿐 실익이 적다고 판단. 우선순위 지정처럼 다른 목적의 프롬프트 분리는 이 결정과 별개 트랙에서 다룸. `select_cases_globally`는 순서·선택 로직을 새로 만들지 않고, 전체 인덱스 범위를 먼저 검증한 뒤 매트릭스별 오프셋만큼 로컬 인덱스로 변환해 기존 `select_cases`에 위임하는 방식을 택함 — 매트릭스 단일용 `select_cases`/`order_cases_for_selection`은 그대로 재사용.
- **트레이드오프**: 사용자가 한 번에 모든 매트릭스의 케이스 번호를 확인하고 입력해야 해서, 매트릭스 수가 많아지면 입력이 번거로워질 수 있음. 매트릭스별로 나눠서 바로바로 확인하며 선택하던 방식의 장점은 포기.
- **관련 이슈/PR**: #44

### LLM 기반 케이스 생성 + 우선순위 정렬 (OpenAI, priority 필드)
- **무엇을 결정했나**: `OPENAI_API_KEY`가 설정된 경우, `llm_augment.py`가 매트릭스마다 GPT를
  한 번 호출해 (1) rule 기반 로직이 놓친 케이스를 `source=CaseSource.LLM`으로 추가 제안하고,
  (2) rule+LLM 전체 케이스에 우선순위(`TestCase.priority: int | None`, 1이 최우선)를 매기도록
  구현. 키가 없으면 `augment_matrices`가 매트릭스를 그대로 통과시켜 기존 #44 동작(카테고리 순서)을
  유지. `order_cases_for_selection`(`grouping.py`)은 케이스 전체에 priority가 채워져 있을 때만
  priority 순으로 정렬하고, 아니면 기존 카테고리 순서로 폴백 — render/selection이 모두 이
  함수 하나에 위임하므로 두 경로에 동일하게 적용됨.
- **왜** (고려했던 대안 포함): provider는 GPT/Claude/Gemini 세 곳 모두 지원하는 안도 검토했으나,
  런타임 비용(어차피 설정된 provider 하나만 호출)보다 개발/테스트 비용(SDK별 매핑, provider별
  mock fixture)이 선형으로 늘어나는 게 더 커서 이번 브랜치는 provider-agnostic 인터페이스
  없이 OpenAI 하나로 좁힘. 추후 다른 provider 추가 시 `llm_augment.py`의 `ChatClient` Protocol
  자리에 맞는 클라이언트만 주입하면 되는 구조로 열어둠.
- **트레이드오프**: `TestCase.priority` 필드는 schema.py(Track C 소유 계약 파일)를 D/E가
  직접 확장. Optional 필드라 rule 기반 파이프라인은 영향 없음(항상 None으로 둬도 무방)이라
  C의 사전 승인 없이 진행하고 사후 통지하기로 함 — Analyzer 스키마 확장 때(`Feature.id`/
  `Constraint.location`) 쓴 선례를 따름. LLM 호출 결과(`priority_order`)가 케이스 전체를
  정확히 한 번씩 포함하지 않으면 보정하지 않고 `ValueError`로 처리(계약 위반은 조용히
  고치지 않는다는 원칙 적용).
- **관련 이슈/PR**: #38

### render.py 카테고리별 테이블 → 매트릭스당 단일 테이블
- **무엇을 결정했나**: 매트릭스 하나에 NORMAL/BOUNDARY/FAILURE/SECURITY 테이블을 각각 그리던
  방식을 없애고, `order_cases_for_selection` 순서로 정렬한 케이스를 "Category" 컬럼이 있는
  테이블 하나로 표시하도록 변경.
- **왜**: 우선순위 정렬이 카테고리 경계를 넘나드는데, 카테고리별로 테이블을 분리하면 우선순위
  순서가 화면에 그대로 드러나지 않음. 단일 테이블 + Category 컬럼이면 카테고리 정보를 잃지
  않으면서도 실제 정렬 순서를 그대로 보여줄 수 있음.
- **트레이드오프**: 카테고리별로 시각적으로 구획된 표를 보던 기존 UI는 포기. `render_matrices`의
  연속 행 번호(#44)와 `select_cases_globally`는 구조 변경 없이 그대로 재사용됨.
- **관련 이슈/PR**: #38

### CLI 출력·비대화식 옵션과 Windows 콘솔 인코딩 통일
- **무엇을 결정했나**: 모든 명령어의 출력 경로 옵션을 `--output`/`-o`로 통일. 프롬프트 없이 전량 선택하는 `--all` 플래그를 `generate`/`run`에 추가. `main()` 진입 시 `_ensure_utf8_console()`로 Windows에서 콘솔 코드페이지를 UTF-8(65001)로 강제하고 `sys.stdout`/`stderr`를 재설정.
- **왜** (고려했던 대안 포함): 명령어마다 옵션명을 따로 만드는 대신 기존 select CLI의 `--output`/`-o` 관례를 유지해 일관된 CLI UX 확보. Windows 콘솔은 기본 로케일 코드페이지(cp949 등)라 비ASCII 케이스 id·설명이 mojibake로 나오거나 `UnicodeEncodeError`가 남 — 사용자가 `PYTHONUTF8=1`이나 `chcp 65001`을 직접 하지 않아도 되게 진입점에서 처리. `--all`은 CI·스크립트에서 대화형 프롬프트 없이 파이프라인을 돌리기 위함.
- **트레이드오프**: `_ensure_utf8_console`가 `ctypes.windll` 등 Windows 전용 API를 직접 만져 플랫폼 분기와 그 자체의 테스트(비Windows no-op, Windows 전용)가 필요함.
- **관련 이슈/PR**: PR #55 (feat/cli-select-all-and-win-utf8-console)

### LLM 응답의 계약 위반을 보정 없이 거부 (temp_id 검증 + 깨진 텍스트)
- **무엇을 결정했나**: LLM이 제안한 `new_cases`에 대해 temp_id 중복·기존 케이스 id와의 충돌을 `ValueError`로 거부하고, `description`/`expected_error_code`에 제어문자나 U+FFFD가 섞인 경우도 `_reject_garbled_text`로 거부. 보정하지 않고 augmentation 자체를 실패시킴.
- **왜** (고려했던 대안 포함): `generator.py`가 `description`을 pytest docstring에 그대로 삽입하므로 NUL 바이트가 들어가면 생성된 `.py`에 리터럴 NUL이 박혀 `ast.parse`가 깨짐(gpt-4o-mini가 비ASCII 설명 생성 시 mojibake를 내는 사례 관찰됨). 계약을 만족하지 않는 입력은 보정하지 않고 검증 오류로 처리한다는 프로젝트 원칙(`CLAUDE.md`)을 LLM 출력에도 그대로 적용. 기존 #38 항목의 `priority_order` 커버리지 검증과 같은 계열의 결정.
- **트레이드오프**: LLM이 부분적으로 유용한 응답을 줘도 한 필드라도 기준 미달이면 그 매트릭스의 보강을 통째로 버림.
- **관련 이슈/PR**: PR #56 (fix/reject-garbled-llm-text), 커밋 `9c030d7`

---

## Track E — pytest 생성 (④ 테스트 데이터 자동 생성) + 문서총괄

### Jinja2 템플릿 방식 채택
- **무엇을 결정했나**: pytest 코드 생성기를 순수 문자열(f-string) 조합 대신 Jinja2 템플릿 기반으로 구현.
- **왜**: 매트릭스 스키마 특성상 `expected_status`, `expected_error_code`, `sample_payload`가 케이스마다 null일 수 있어 조건 분기가 여러 개 겹친다. f-string 조합은 이 분기가 중첩되면서 가독성이 급격히 떨어지는 반면, Jinja2의 `{% if %}`는 "최종 코드가 어떤 모양이어야 하는지"가 템플릿 파일에 그대로 드러나 유지보수에 유리하다. 또한 템플릿(`.j2`)과 생성 로직(`generator.py`)이 분리되어, 코드 포맷을 바꿀 때 생성 로직을 건드릴 필요가 없다.
- **트레이드오프**: 의존성이 하나 늘지만(`jinja2`, 이미 `pyproject.toml`에 포함) 팀원이 템플릿 문법(변수 치환/if/for)을 새로 익혀야 하는 진입 장벽이 있음. 문법 자체가 단순해 부담은 크지 않다고 판단.
- **관련 이슈/PR**: #11

### 매트릭스 스키마에 path_params 필드 추가
- **무엇을 결정했나**: 기존 확정 스키마에 `path_params` 필드를 추가. `GET /api/users/{user_id}`처럼 경로에 placeholder가 있는 엔드포인트의 실제 값을 케이스마다 지정.
- **왜**: 기존 스키마로는 path parameter가 있는 엔드포인트의 실제 값을 채울 방법이 없어, 생성된 테스트 코드에 `{user_id}` 문자열이 그대로 남는 문제가 있었음. `sample_payload`를 겸용하는 대안도 검토했으나, 하나의 필드가 request body와 path param 두 역할을 겸하면 나중에 헷갈릴 수 있어 기각.
- **트레이드오프**: 스키마가 "확정"된 이후의 변경이라 C 트랙 코드에도 영향. 필드 추가는 기존 케이스에 `path_params: null`을 채우는 것으로 하위 호환 유지.
- **관련 이슈/PR**: #15

### client fixture scope를 function으로 명시
- **무엇을 결정했나**: `tests/conftest.py`의 `client`, `fresh_db` fixture 모두 `scope="function"`으로 명시적으로 지정.
- **왜**: 명시하지 않으면 pytest 기본값(function scope)이 암묵적으로 적용되는데, 이게 의도한 선택이라는 걸 코드만 보고는 알 수 없었음. session scope로 하면 테스트 속도는 빨라지지만, `dependency_overrides`나 DB 상태가 테스트 간에 새어나갈 수 있어 생성된 테스트가 순서 무관하게 독립적으로 돌아야 한다는 요구사항과 맞지 않음.
- **트레이드오프**: 테스트마다 새 TestClient/DB를 만들어 약간 느려지지만, 생성된 테스트의 독립성이 더 중요하다고 판단.
- **관련 이슈/PR**: #16

### 엣지케이스 검증용 픽스처를 별도 파일로 분리
- **무엇을 결정했나**: PUT/DELETE, path_params+sample_payload 동시 존재 케이스를 tests/fixtures/mock_matrix.json이 아니라 tests/fixtures/edge_case_matrix.json이라는 새 파일에 넣음.
- **왜**: 처음엔 검증용 케이스를 mock_matrix.json에 그냥 추가했는데, 이 파일이 D 트랙(CLI 선택 도구)의 테스트(test_cli.py, test_loader.py)가 "feature 2개, 각각 4개 카테고리 모두 존재"라는 고정된 형태로 의존하고 있는 공유 픽스처라는 걸 뒤늦게 발견함. feature를 추가하자마자 CI에서 5개 테스트가 깨졌음.
- **트레이드오프**: 픽스처 파일이 하나 더 늘지만, 트랙 간 공유 픽스처는 "누구나 마음대로 확장 가능한 것"이 아니라 암묵적으로 스키마가 고정된 계약이라는 걸 팀 전체가 인지할 필요가 있음. 앞으로 공유 픽스처를 바꿔야 할 일이 있으면, 바꾸기 전에 그 파일에 의존하는 다른 트랙 테스트가 있는지 먼저 확인하는 습관이 필요함.
- **관련 이슈/PR**: #26

### demo_app 스텁의 인증/소유권 처리

`tests/fixtures/demo_app/main.py`는 실제 토큰 검증 로직이 없다 (`login()`이 
`fake-token`을 발급하지만 아무 dependency도 이를 검증하지 않음). `GET /api/users/{user_id}`의 
소유권 체크(mock_matrix.json의 profile-004: 타인 프로필 조회 시 403)는 
`_CURRENT_USER_ID = "1"` 하드코딩 비교로 구현되어 있다 — 실제 인증 시스템을 
흉내내려는 게 아니라, 매트릭스 기대값(200 vs 403)을 만족시키기 위한 최소한의 
스텁 로직임에 유의.

### 대상 프로젝트별 conftest.py를 scaffold로 생성
- 무엇을 결정했나: tests/conftest.py를 건드리는 대신 generate_conftest()로 대상 프로젝트에 별도 conftest.py를 생성하는 방식 채택
- 왜: client fixture가 demo_app에 하드코딩돼 있어 외부 프로젝트 테스트 시 전부 404가 나는 문제 발견. 기존 260여 개 테스트를 건드리지 않고 해결 가능한 최소 변경 선택
- 트레이드오프: reset_state는 프로젝트마다 사용자가 직접 채워야 함 (TestWeaver가 임의 저장소 구조를 일반적으로 추론할 수 없음)
- 관련 이슈/PR: #47
---

## 결과보고서 반영 메모

- (결과보고서 초안 작성 시 이 섹션에 "어느 항목을 어느 섹션에 넣었는지" 체크리스트 형태로 남기면 중복/누락 방지에 도움)
