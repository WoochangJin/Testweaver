from fastapi import APIRouter

router = APIRouter()


@router.get("")
def root_of_sub() -> dict:
    """prefix 만 있고 경로가 빈 문자열."""
    return {}


@router.get("/")
def slash_only() -> dict:
    """경로가 슬래시 하나."""
    return {}
