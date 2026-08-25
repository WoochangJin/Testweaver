from fastapi import HTTPException, status


class DomainError(Exception):
    pass


def level3() -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CONFLICT")


def level2() -> None:
    level3()


def level1() -> None:
    """호출 그래프 3단. 깊이 제한에 걸리는지 본다."""
    level2()


def raises_domain() -> None:
    raise DomainError("nope")


async def async_service() -> None:
    raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="PAY")
