import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import app.core.database as db
from app.ai_parser import parse_pcb_text
from app.core.auth import (
    create_session_token,
    read_session_token,
    verify_password,
)
from app.core.logging import get_logger
from app.core.storage import file_storage
from app.export_excel import export_quote_excel
from app.formal_quote_export import export_formal_quote
from app.image_parser import parse_pcb_image
from app.quote_engine import calculate_quote

STATUS_LABELS = {"pending": "待審核", "approved": "已批准", "ordered": "已下單"}

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


@router.get("/quotes/new", response_class=HTMLResponse)
def new_quote_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "quote_new.html", {"request": request, "user": user, "error": None, "form": {}}
    )


@router.post("/quotes/new")
def create_quote(
    request: Request,
    layer: int = Form(...),
    qty: int = Form(...),
    material: str = Form(""),
    length_mm: Optional[float] = Form(None),
    width_mm: Optional[float] = Form(None),
    issue_ratio: float = Form(1.0),
    enig: Optional[str] = Form(None),
    enig_thickness_uinch: Optional[float] = Form(None),
    vip: Optional[str] = Form(None),
    impedance: Optional[str] = Form(None),
    back_drill: Optional[str] = Form(None),
    bvh: Optional[str] = Form(None),
    thickness_mm: Optional[float] = Form(None),
    pitch_mm: Optional[float] = Form(None),
    delivery_days: Optional[int] = Form(None),
    company_name: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    parsed = {
        "layer": layer,
        "qty": qty,
        "material": material or None,
        "length_mm": length_mm,
        "width_mm": width_mm,
        "issue_ratio": issue_ratio,
        "enig": enig is not None,
        "enig_thickness_uinch": enig_thickness_uinch,
        "vip": vip is not None,
        "impedance": impedance is not None,
        "back_drill": back_drill is not None,
        "bvh": bvh is not None,
        "thickness_mm": thickness_mm,
        "pitch_mm": pitch_mm,
        "delivery_days": delivery_days,
        "company_name": company_name or None,
    }

    result = calculate_quote(parsed)

    if result.get("status") != "success":
        return templates.TemplateResponse(
            "quote_new.html",
            {
                "request": request,
                "user": user,
                "error": result.get("message"),
                "form": parsed,
            },
            status_code=400,
        )

    customer_id = None
    if company_name:
        query_db = db.SessionLocal()
        customer = (
            query_db.query(db.Customer)
            .filter(db.Customer.company_name == company_name)
            .first()
        )
        if customer is None:
            customer = db.Customer(company_name=company_name)
            query_db.add(customer)
            query_db.commit()
            query_db.refresh(customer)
        customer_id = customer.id
        query_db.close()

    db.save_quote(
        source_channel_id=f"web:{user.id}",
        parsed=parsed,
        result=result,
        customer_id=customer_id,
        created_by_user_id=user.id,
    )

    return RedirectResponse(url="/quotes", status_code=303)


@router.post("/quotes/new/ai-assist", response_class=HTMLResponse)
async def ai_assist(
    request: Request,
    spec_text: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    parsed = {}
    ai_error = None
    try:
        if photo is not None and photo.filename:
            image_path = f"data/uploads/web_{uuid.uuid4().hex}.jpg"
            with open(image_path, "wb") as f:
                f.write(await photo.read())
            try:
                parsed = parse_pcb_image(image_path)
            finally:
                file_storage.cleanup(image_path)
        elif spec_text.strip():
            parsed = parse_pcb_text(spec_text)

        # ai_parser/image_parser emit "thickness" (see app/ai_parser.py's
        # JSON schema) but quote_engine.calculate_quote() and this form both
        # key board thickness as "thickness_mm" — normalize so an AI-filled
        # value actually lands in the form field.
        if "thickness" in parsed and "thickness_mm" not in parsed:
            parsed["thickness_mm"] = parsed.pop("thickness")
    except Exception as e:
        logger.error(f"AI assist failed: {e}")
        ai_error = "AI 解析失敗，請手動填寫規格"
        parsed = {}

    return templates.TemplateResponse(
        "_quote_form_fields.html",
        {"request": request, "form": parsed, "ai_error": ai_error},
    )


@router.get("/quotes", response_class=HTMLResponse)
def quotes_list(
    request: Request,
    status: Optional[str] = None,
    layer: Optional[int] = None,
    material: Optional[str] = None,
    customer: Optional[str] = None,
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    from sqlalchemy.orm import joinedload

    query_db = db.SessionLocal()
    query = query_db.query(db.QuoteHistory).options(
        joinedload(db.QuoteHistory.customer), joinedload(db.QuoteHistory.created_by)
    )
    if status:
        query = query.filter(db.QuoteHistory.status == status)
    if layer:
        query = query.filter(db.QuoteHistory.layer == layer)
    if material:
        query = query.filter(db.QuoteHistory.material.ilike(f"%{material}%"))
    if customer:
        query = query.join(db.Customer).filter(
            db.Customer.company_name.ilike(f"%{customer}%")
        )
    quotes = query.order_by(db.QuoteHistory.created_at.desc()).limit(200).all()
    query_db.close()

    return templates.TemplateResponse(
        "quotes_list.html",
        {
            "request": request,
            "user": user,
            "quotes": quotes,
            "filters": {
                "status": status or "",
                "layer": layer or "",
                "material": material or "",
                "customer": customer or "",
            },
        },
    )


@router.get("/quotes/{quote_id}", response_class=HTMLResponse)
def quote_detail(request: Request, quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    from sqlalchemy.orm import joinedload

    query_db = db.SessionLocal()
    quote = (
        query_db.query(db.QuoteHistory)
        .options(
            joinedload(db.QuoteHistory.customer),
            joinedload(db.QuoteHistory.created_by),
            joinedload(db.QuoteHistory.updated_by),
        )
        .filter(db.QuoteHistory.id == quote_id)
        .first()
    )
    query_db.close()

    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")

    return templates.TemplateResponse(
        "quote_detail.html",
        {"request": request, "user": user, "quote": quote, "status_labels": STATUS_LABELS},
    )


@router.post("/quotes/{quote_id}/update")
def update_quote(
    quote_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    quote = query_db.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
    if quote is None:
        query_db.close()
        raise HTTPException(status_code=404, detail="Quote not found")

    quote.status = status
    quote.notes = notes
    quote.updated_by_user_id = user.id
    query_db.commit()
    query_db.close()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.get("/quotes/{quote_id}/export/excel")
def quote_export_excel(quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    quote = query_db.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
    query_db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    filename = export_quote_excel(quote.spec_json, quote.breakdown_json)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/quotes/{quote_id}/export/formal")
def quote_export_formal(quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    quote = query_db.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).first()
    query_db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    output_path = export_formal_quote(quote.spec_json, quote.breakdown_json)
    import os as _os

    filename = _os.path.basename(output_path)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/customers", response_class=HTMLResponse)
def customers_list(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    customers = query_db.query(db.Customer).order_by(db.Customer.company_name).all()
    query_db.close()

    return templates.TemplateResponse(
        "customers.html", {"request": request, "user": user, "customers": customers}
    )


@router.post("/customers")
def customers_create(
    company_name: str = Form(...),
    contact: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    customer = db.Customer(
        company_name=company_name,
        contact=contact or None,
        phone=phone or None,
        email=email or None,
    )
    query_db.add(customer)
    query_db.commit()
    query_db.close()

    return RedirectResponse(url="/customers", status_code=303)


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "user": user,
            "by_layer": db.get_stats_by_layer(),
            "by_material": db.get_stats_by_material(),
        },
    )
