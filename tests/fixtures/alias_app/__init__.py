"""타입 별칭과 반복 등록을 담은 다섯 번째 샘플 앱.

  · `CommonDep = Annotated[dict, Depends(common)]`  FastAPI 문서가 권장하는 형태
  · `for router in (v1, v2): app.include_router(router, prefix=...)`
  · 다이아몬드 상속, 제네릭 모델, Header(alias=...)

별칭을 풀지 못해 의존성과 그 파라미터를, 반복 등록을 읽지 못해 prefix 를
통째로 놓치던 결함이 여기서 드러났다.
"""
