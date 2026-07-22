from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import app.core.database as db
from app.core.auth import (
    create_session_token,
    read_session_token,
    verify_password,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="templates")

SESSION_COOKIE_NAME = "session"


def get_current_user_optional(
    session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)
):
    # `db` is accessed via module attributes (not `from ... import X`) so
    # this keeps working correctly under tests that reload
    # app.core.database against a temporary database.
    if not session:
        return None
    user_id = read_session_token(session)
    if user_id is None:
        return None
    query_db = db.SessionLocal()
    user = query_db.query(db.User).filter(db.User.id == user_id).first()
    query_db.close()
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    query_db = db.SessionLocal()
    user = query_db.query(db.User).filter(db.User.email == email).first()
    query_db.close()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "帳號或密碼錯誤"},
            status_code=401,
        )

    token = create_session_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True, max_age=60 * 60 * 24 * 7
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    stats = db.get_system_stats()
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "stats": stats}
    )
