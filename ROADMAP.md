# TestWeaver 로드맵

이 문서는 TestWeaver가 지금까지 무엇을 완료했고, 8/27 제출 전까지 무엇을 정리하며, 1차 평가(9/3~4) 전후로 무엇을 더 다듬을지, 그리고 장기적으로 어떤 구조적 개선이 필요한지를 정리합니다.

## 현재 상태

### Track A/B — 기능 추출 (①)

FastAPI 프로젝트를 정적 분석해서 라우터, Pydantic 제약 조건, 의존성 주입 구조, 예외 처리 흐름을 추출하는 기능이 완료되어 있습니다. `RouteInfo`/`FieldConstraint`는 `Endpoint`/`Constraint`로 정리되었고, `Constraint`에는 `location`(path/query/header/cookie/body/form) 필드가 추가되어 있습니다.

### Track C — 규칙 기반 매트릭스 생성 (②)

정상/경계/실패/보안 네 관점으로 테스트 케이스 후보를 자동 도출하는 기능이 완료되어 있습니다. 다만 오늘 실제 외부 프로젝트로 검증하는 과정에서 두 가지 버그가 새로 발견되었고, 아직 미해결 상태입니다. `build_path_params`가 모든 path parameter에 무조건 `1`을 채워서 "리소스가 존재하는" 케이스와 "리소스가 없는" 404 케이스가 같은 id를 요구하는 문제, 그리고 `expected_error_code` 검증이 `{"error_code": ...}` 형태를 가정하지만 FastAPI 기본 `HTTPException`은 `{"detail": ...}`을 반환해서 커스텀 에러 포맷을 안 쓰는 프로젝트에서는 항상 실패하는 문제입니다.

### Track D — LLM 보강(②) + CLI(③)

`analyze`, `generate`, `test`, `run` 네 CLI 명령어가 구현되어 있고, `generate` 명령은 인터랙티브로 케이스를 선택할 수 있습니다. LLM 기반 케이스 보강은 아직 개발 중입니다.

### Track E — pytest 생성(④) + 문서

매트릭스 JSON에서 Jinja2 템플릿으로 pytest 코드를 생성하는 기능이 완료되어 있습니다. 생성된 테스트는 status code 검증에 더해 response의 content-type이 JSON인지도 확인합니다. 또한 외부 프로젝트를 실제로 테스트할 수 있도록, 대상 프로젝트 전용 `conftest.py`를 자동 생성해주는 scaffold 기능이 추가되었습니다.

## 8/27 제출 전까지

결과보고서와 AI 활용 서식을 완성하는 것이 최우선입니다. README의 CLI 사용법을 실제 명령어에 맞게 정정하는 작업도 포함됩니다. 오늘 발견한 Track C의 두 버그는 코드 수정 없이 이슈로만 등록해두고, 결과보고서의 "확인된 한계와 향후 계획" 섹션에 명시하는 것으로 이번 제출에서는 충분합니다.

## 1차 평가(9/3~4) 전까지

Track C의 두 버그(path_params 재사용, error_code 포맷 불일치)를 실제로 수정합니다. Track A/B의 실제 파서 출력이 `Endpoint`/`Constraint` 계약과 정확히 맞물리는지 확인하는 통합 체크포인트도 이 시기에 다시 확인이 필요합니다.

## 장기 개선 과제

TestWeaver 팀이 이전에 정리한 개선 문서를 기준으로 구조적 문제들의 우선순위는 다음과 같습니다.

**P0 — 먼저 합의하거나 해결해야 하는 구조**

`NORMAL` 케이스의 의미(schema-valid request로 볼지, 실제 성공을 보장하는 request로 볼지)를 명확히 정의하는 것이 첫 번째입니다. 실행 환경 문제는 오늘 scaffold로 부분적으로 풀었지만, `testweaver run . --app src.main:app` 같은 CLI 차원의 정식 지원과 dependency override 설계는 아직 남아 있습니다.

**P1 — 실제 테스트 기능 완성**

Query/Header/Cookie 값을 실제 요청에 반영하는 기능이 필요합니다. Response 검증은 status code와 JSON 응답 여부까지는 확인하지만, 필수 필드 존재·필드 타입·response schema 검증은 아직 남아 있고, 이는 Analyzer가 `response_model` 정보를 노출해야 가능합니다.

**P2 — 결과 전달 및 CLI UX**

pytest 실행 결과를 TestWeaver 자체의 Expected/Actual summary로 보여주는 기능, Windows 콘솔 인코딩 문제, `all`/`none`/`--all` CLI 옵션이 이 단계에 해당합니다.