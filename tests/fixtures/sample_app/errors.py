"""커스텀 예외.

검증 대상: raise 지점만 봐서는 상태코드를 알 수 없는 예외.
main.py 의 @app.exception_handler 를 함께 인덱싱해야 404로 이어진다는 걸
알 수 있다.
"""


class OrderNotFound(Exception):
    def __init__(self, order_id: int) -> None:
        super().__init__(f"order {order_id} not found")
        self.order_id = order_id
