"""호출 그래프와 경로 형태가 까다로운 네 번째 샘플 앱.

  · 3단 호출 그래프 끝의 예외
  · `from . import svc` 로 가져온 모듈 경유 예외 핸들러
  · yield 의존성, async 서비스
  · prefix 만 있고 경로가 빈 문자열 / 슬래시 하나
  · Request·Response 는 입력이 아니다

`@app.exception_handler(svc.DomainError)` 를 인덱싱하지 못해 커스텀 예외의
상태코드가 통째로 비던 결함이 여기서 드러났다.
"""
