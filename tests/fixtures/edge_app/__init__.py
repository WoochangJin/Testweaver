"""까다로운 선언 방식만 모아 놓은 두 번째 샘플 앱.

`sample_app` 은 흔한 구조를 담아 기본 동작을 고정한다. 여기는 반대로
"이렇게도 쓴다"는 것들만 모았다. 실제로 이 앱을 분석해 보고 나서야
드러난 결함이 다섯 개 있었고, 그 회귀를 막는 게 이 픽스처의 목적이다.

  · include_router(prefix=모듈상수)   경로 전체가 어긋났다
  · Header 인자 이름                  x_api_key 가 아니라 x-api-key 로 나가야 한다
  · {file_path:path}                  경로 변환기가 URL 에 남았다
  · Depends(호출가능한 클래스 인스턴스) __call__ 의 파라미터를 놓쳤다
  · "Node | None" 문자열 어노테이션    전방 참조를 따라가지 못했다

이 앱도 import 가능한 유효한 FastAPI 앱이라 `app.openapi()` 를 정답지로 쓴다.
"""
