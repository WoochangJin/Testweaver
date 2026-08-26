# Contributing to TestWeaver

TestWeaver는 FastAPI 프로젝트를 정적분석해서 무엇을 테스트해야 하는지 먼저
설계하고, 선택한 시나리오를 실행 가능한 테스트 코드로 만들어주는 도구입니다.
버그 제보든 기능 제안이든 코드 기여든 환영합니다. 아래는 시작하기 전에 알아두면
좋은 것들입니다.

## 개발 환경 설정

이 프로젝트는 [uv](https://docs.astral.sh/uv/)로 의존성을 관리합니다.

```bash
git clone https://github.com/WoochangJin/testweaver.git
cd testweaver
uv sync --group dev
uv run pytest
```

테스트가 통과하면 준비 끝입니다.

## 이슈부터 만들어주세요

코드를 쓰기 전에 먼저 Issue를 열어서 뭘 하려는지 남겨주세요. 이미 누가 작업
중인 부분과 겹치는 걸 막을 수 있고, 방향이 맞는지 미리 확인할 수 있습니다.
간단한 오타나 문서 수정은 예외입니다.

## 브랜치와 커밋

브랜치는 `feature/<설명>`, `fix/<설명>`, `docs/<설명>` 형식을 씁니다. 설명은
영문 소문자에 하이픈으로 구분합니다 (예: `feature/router-parser`).

커밋 메시지는 [Conventional Commits](https://www.conventionalcommits.org/)를
따릅니다.

```
feat: add router path/method extractor
fix: extract real status_code from HTTPException instead of null
docs: document the test case JSON schema
test: add fixture for constraint parsing edge cases
```

커밋 하나에는 한 가지 변경만 담아주세요. "여러 개 수정"처럼 뭉뚱그린 커밋은
나중에 되짚기 어렵습니다.

## 코드 스타일

- 린트: `uv run ruff check .`
- 테스트: `uv run pytest`
- 새 로직을 추가하면 최소 하나 이상의 테스트를 같이 넣어주세요. 이 프로젝트
  자체가 테스트 도구인 만큼, 우리 코드도 예외는 아닙니다.
- 타입 힌트는 필수는 아니지만 공개 함수/클래스에는 붙여주는 걸 권장합니다.

## Pull Request

- PR은 `main`이 아니라 `develop` 브랜치로 보내주세요.
- 하나의 PR은 하나의 주제만 다루는 게 좋습니다. 여러 기능을 한 번에 묶지
  말아주세요.
- 리뷰어 1명 이상의 승인 후 머지합니다. 작성자 본인이 자신의 PR을 머지하지
  않습니다.
- CI(린트+테스트)가 통과해야 머지 가능합니다.
- PR 설명에는 무엇을, 왜 바꿨는지 간단히 적어주세요. 관련 Issue가 있으면
  번호를 링크해주세요.

## 이슈 리포트

버그를 발견하셨다면 재현 방법과 기대했던 동작, 실제 동작을 적어주세요.
FastAPI 프로젝트 구조나 사용한 Pydantic 버전처럼 환경 정보가 있으면 더
빠르게 원인을 찾을 수 있습니다.

## 라이선스

이 프로젝트에 기여하는 코드는 저장소의 [LICENSE](./LICENSE)(MIT)를 따릅니다.