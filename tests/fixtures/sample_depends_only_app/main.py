from typing import Any

from fastapi import Depends, FastAPI, HTTPException

app = FastAPI(title="Demo Login API")

_USERS: dict[str, dict[str, Any]] = {
    "1": {"id": 1, "email": "user@example.com", "password": "correct-pw"},
}


def get_db() -> dict[str, dict[str, Any]]:
    return _USERS


@app.get("/users/{user_id}")
def get_user_profile(user_id: str, db: dict[str, Any] = Depends(get_db)) -> dict:
    user = db.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="not found")
    return user