"""Minimal stub FastAPI app used only to prove the pytest fixture works
end-to-end against the generated tests.

This is NOT the real TestWeaver target project — it's a throwaway app
that implements just enough of /api/login and /api/users/{user_id} to
demonstrate the dependency_overrides + in-memory DB pattern.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Expose {"error_code": ...} at the top level of the response body
    instead of FastAPI's default {"detail": ...} wrapper, matching what
    the matrix's expected_error_code assertions look for.
    """
    body = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=body)


# --- in-memory "DB" -------------------------------------------------

_USERS: dict[str, dict[str, Any]] = {
    "1": {"id": 1, "email": "user@example.com", "password": "correct-pw"},
    "2": {"id": 2, "email": "other@example.com", "password": "whatever"},
}


def get_db() -> dict[str, dict[str, Any]]:
    """Dependency that hands out the in-memory user store.

    In the real project this would open a DB session; overriding this
    single function in tests is what lets us swap in fixture data
    without touching a real database.
    """
    return _USERS


# --- routes -----------------------------------------------------------


@app.post("/api/login")
def login(payload: dict[str, str], db: dict = Depends(get_db)) -> dict:
    email = payload.get("email")
    password = payload.get("password")
    if password is None or email is None:
        raise HTTPException(status_code=422, detail="missing fields")

    user = next((u for u in db.values() if u["email"] == email), None)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "USER_NOT_FOUND"},
        )
    if user["password"] != password:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "INVALID_PASSWORD"},
        )
    return {"access_token": "fake-token"}


@app.get("/api/users/{user_id}")
def get_user_profile(user_id: str, db: dict = Depends(get_db)) -> dict:
    if not user_id.isdigit():
        raise HTTPException(status_code=422, detail="invalid user_id")
    user = db.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "USER_NOT_FOUND"},
        )
    return {"id": user["id"], "email": user["email"]}