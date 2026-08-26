# TestWeaver

> FastAPI 프로젝트를 분석해 **무엇을 테스트해야 하는지 먼저 설계**하고, 선택한 시나리오를 실행 가능한 테스트 코드로 짜주는 AI 기반 테스트 설계 도구.

테스트를 잘 못 쓰는 이유는 대개 "코드 작성법을 몰라서"가 아니라 "무엇을, 어떤 경우까지 테스트해야 하는지 판단하기 어려워서"입니다. TestWeaver는 테스트 코드를 바로 생성하기 전에 **테스트 설계표(Test Design Matrix)**를 먼저 만들고, 그중 선택된 케이스만 실행 가능한 pytest 코드로 변환합니다.

## 동작 방식

```
FastAPI 프로젝트 분석          (analyzer)
        ↓
기능 단위 Feature 추출         (analyzer.models)
        ↓
규칙 기반 테스트 케이스 도출     (case_generator)  — 정상/경계/실패/보안
        ↓
LLM 보강 + 사용자 케이스 선택    (예정)
        ↓
실행 가능한 pytest 코드 생성    (generator)
```

- **정적 분석 기반**: 코드를 실행하지 않고 라우터·Pydantic 제약·의존성·예외 흐름에서 테스트 케이스를 도출합니다.
- **네 가지 관점**: 도출되는 케이스는 `normal`(정상) / `boundary`(경계) / `failure`(실패) / `security`(보안)로 분류됩니다.
- **선택 가능한 생성**: 도출된 케이스 후보 중 `selected: true`로 표시된 것만 pytest 코드로 만듭니다. 일괄 생성이 아닙니다.
- **바로 실행 가능**: FastAPI `TestClient`와 `dependency_overrides` 패턴을 활용해, 외부 DB 없이도 생성된 테스트가 즉시 실행됩니다.

## 설치

이 프로젝트는 [uv](https://docs.astral.sh/uv/)로 의존성을 관리합니다.

```bash
git clone https://github.com/WoochangJin/testweaver.git
cd testweaver
uv sync --group dev
uv run pytest
```

## 사용법

### CLI로 실행하기

```bash
# 1. FastAPI 프로젝트를 분석해서 매트릭스 생성
uv run testweaver analyze <프로젝트경로> -o matrix.json

# 2. 매트릭스에서 케이스를 골라 pytest 코드 생성 (인터랙티브로 케이스 선택)
uv run testweaver generate matrix.json -o tests/generated/test_generated.py

# 3. 생성된 테스트 실행
uv run testweaver test tests/generated

# 또는 analyze → generate → run을 한 번에
uv run testweaver run <프로젝트경로>
```

> `generate` 명령은 매트릭스 **JSON 파일 경로**를 인자로 받습니다.
> (`generate <프로젝트경로> <기능명>` 형태가 아닙니다 — 예전 문서의 오기이니 이 표기를 보셨다면 무시하세요.)

각 명령어의 옵션은 `uv run testweaver <명령어> --help`로 확인할 수 있습니다.

### Python API로 직접 다루기

CLI 없이 코드에서 직접 규칙 기반 케이스 도출/생성을 다루고 싶다면 아래 방식을 사용할 수 있습니다.

#### 1. 규칙 기반으로 테스트 케이스 매트릭스 만들기

`Feature`(엔드포인트 + 제약 조건 + 예외 흐름)가 주어지면, 정상/경계/실패/보안 네 가지 관점의 케이스를 자동으로 도출합니다.

```python
from testweaver.analyzer.models import Endpoint, Feature, HttpMethod
from testweaver.case_generator.matrix import build_case_matrix

feature = Feature(
    name="login",
    endpoint=Endpoint(
        path="/api/login",
        method=HttpMethod.POST,
        handler_name="login",
        requires_auth=False,
    ),
    constraints=[...],  # Pydantic 모델에서 추출된 제약 조건
)

matrix = build_case_matrix(feature)
# matrix.cases 안에 normal/boundary/failure/security 케이스가 들어있음
```

> 규칙 기반으로 새로 도출된 케이스의 `selected`는 기본값(`False`)입니다. 어떤 케이스를 실제로 테스트 코드로 만들지는 CLI의 `generate` 명령이 인터랙티브로 선택하게 하거나, 아래 2번처럼 `selected` 값이 채워진 매트릭스 JSON을 직접 사용하면 됩니다.

#### 2. 매트릭스 JSON에서 pytest 코드 생성

`tests/fixtures/mock_matrix.json`에 `selected: true`가 채워진 샘플 매트릭스가
있습니다. 스키마:

```json
{
  "id": "login-001",
  "feature_name": "login",
  "category": "normal",
  "description": "올바른 이메일/비밀번호로 로그인 성공",
  "expected_status": 200,
  "expected_error_code": null,
  "sample_payload": { "email": "user@example.com", "password": "correct-pw" },
  "path_params": null,
  "source": "rule",
  "selected": true
}
```

생성 실행:

```bash
uv run python -c "
from pathlib import Path
from testweaver.generator import generate_from_file
generate_from_file(
    Path('tests/fixtures/mock_matrix.json'),
    Path('tests/generated/test_generated.py'),
)
"
```

`expected_status`가 아직 확정되지 않은(`null`) 케이스는 `pytest.skip()`으로 생성되어, 매트릭스의 미해결 지점이 테스트 결과에서도 그대로 드러납니다. 경로에 `{user_id}` 같은 path parameter가 있는 케이스는 `path_params` 필드값으로 실제 URL이 채워집니다.

#### 3. 생성된 테스트 실행

```bash
uv run pytest tests/generated/test_generated.py -v
```

`tests/conftest.py`의 `client` fixture가 `dependency_overrides`로 실제 DB를 인메모리 스토어로 교체해주기 때문에, 외부 인프라 없이 바로 실행됩니다. (`tests/fixtures/demo_app/`은 이 fixture를 검증하기 위한 최소 스텁 앱으로, 실제 분석 대상 프로젝트가 아닙니다.)

## 프로젝트 구조

```
src/testweaver/
├── __init__.py                # CLI 진입점 (analyze / generate / test / run)
├── pipeline.py                # analyze → matrix → pytest 전체 파이프라인 오케스트레이션
├── loader.py                  # 매트릭스 JSON 로딩
├── selection.py               # 인터랙티브 케이스 선택
├── render.py                  # 매트릭스 콘솔 출력
├── writer.py                  # 매트릭스 JSON 저장
├── schema.py                  # TestCase / TestCaseMatrix 스키마
├── analyzer/
│   └── models.py               # Feature/Endpoint/Constraint 등 분석 결과 스키마
├── case_generator/
│   ├── matrix.py                # build_case_matrix: 4관점 케이스 종합
│   ├── payload.py               # 유효/무효 요청 payload 생성
│   └── rules/                   # normal/boundary/failure/security 도출 규칙
├── generator.py                # 매트릭스 JSON → pytest 코드 생성기
└── templates/
    └── test_case.py.j2          # 생성기가 사용하는 jinja2 템플릿

tests/
├── conftest.py                 # client fixture (TestClient + dependency_overrides)
├── fixtures/
│   ├── mock_matrix.json        # 테스트 케이스 매트릭스 샘플
│   └── demo_app/                # 검증 전용 스텁 FastAPI 앱
├── test_case_matrix.py         # 규칙 기반 케이스 도출 단위 테스트
├── test_payload.py             # payload 빌더 단위 테스트
├── test_cli.py                 # CLI 명령어 단위 테스트
└── generated/                    # 생성기 출력 (git에 커밋되지 않음)
```

## 테스트

```bash
uv run pytest
```

## 기여하기

버그 제보, 기능 제안, 코드 기여 모두 환영합니다. 시작하기 전에 [CONTRIBUTING.md](./CONTRIBUTING.md)를 먼저 읽어주세요.

## 라이선스

[MIT](./LICENSE)