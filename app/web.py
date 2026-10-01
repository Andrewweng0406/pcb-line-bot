import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload

import app.core.database as db
from app.business_analytics import (
    get_customer_analytics,
    get_outcome_stats,
    get_pricing_trends,
)
from app.ai_parser import parse_pcb_text
from app.core.auth import (
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.storage import file_storage
from app.export_excel import export_quote_excel
from app.formal_quote_export import export_formal_quote
from app.historical_intelligence import find_similar_quotes, historical_pricing_summary
from app.image_parser import parse_pcb_image
from app.import_quotes import confirm_import, preview_import
from app.quote_metrics import (
    calculate_margin,
    to_non_negative_float,
    to_non_negative_int,
)
from app.quote_outcomes import (
    LOST_REASON_LABELS,
    OUTCOME_LABELS,
    normalize_lost_reason,
    normalize_outcome,
)
from app.rfq_completeness import evaluate_rfq_completeness
from app.quote_engine import calculate_quote

TRANSLATIONS = {
    "en": {
        "app_title": "PCB Quote System",
        "new_quote": "New Quote",
        "quote_list": "Quote List",
        "customers": "Customers",
        "import_quotes": "Import Quotes",
        "reports": "Reports",
        "logout": "Log Out",
        "menu": "Menu",
        "language_label": "Language",
        "dashboard": "Dashboard",
        "quotes_today": "Quotes Today",
        "total_quotes": "Total Quotes",
        "average_quote_amount": "Average Quote Amount",
        "view_quote_list": "View Quote List",
        "email": "Email",
        "password": "Password",
        "login": "Log In",
        "register": "Register",
        "create_account": "Create Account",
        "invite_code": "Invite Code",
        "need_account": "Need an account?",
        "register_with_invite": "Register with invite code",
        "already_have_account": "Already have an account?",
        "layers": "Layers",
        "quantity": "Quantity",
        "material": "Material",
        "customer": "Customer",
        "status": "Status",
        "all": "All",
        "pending_review": "Pending Review",
        "approved": "Approved",
        "ordered": "Ordered",
        "filter": "Filter",
        "number": "No.",
        "total": "Total",
        "created_by": "Created By",
        "created_at": "Created At",
        "company_name": "Company Name",
        "contact": "Contact",
        "phone": "Phone",
        "add_customer": "Add Customer",
        "customer_company_name": "Customer Company Name",
        "length_mm": "Length (mm)",
        "width_mm": "Width (mm)",
        "issue_ratio": "Issue Ratio",
        "lead_time_days": "Lead Time (days)",
        "board_thickness_mm": "Board Thickness (mm)",
        "enig_thickness": "ENIG Thickness (u\")",
        "surface_finish": "Surface Finish",
        "copper_thickness": "Copper Thickness",
        "outer_copper": "Outer Copper (oz)",
        "inner_copper": "Inner Copper (oz)",
        "min_hole": "Min Hole (mil)",
        "aspect_ratio": "Aspect Ratio",
        "warpage": "Warpage (mil/inch)",
        "legend_color": "Legend Color",
        "solder_mask_color": "Solder Mask Color",
        "special_requirements": "Special Requirements",
        "ai_form_assist": "AI Form Assist",
        "paste_specs": "Paste Specifications",
        "upload_pcb_image": "Or Upload PCB Image",
        "parse_with_ai": "Parse with AI",
        "save_quote": "Calculate and Save Quote",
        "quote_detail": "Quote Detail",
        "last_updated_by": "Last Updated By",
        "generate_formal_quote": "Generate Formal Quote",
        "download_internal_excel": "Download Internal Excel",
        "sales_next_steps": "Sales Next Steps",
        "pricing_status": "Pricing Status",
        "rfq_quality": "RFQ Data Quality",
        "complete": "Complete",
        "required_before_quoting": "Required Before Quoting",
        "recommended_checks": "Recommended Checks",
        "data_complete": "Data is complete. You can generate the formal quote.",
        "estimate_missing": "Estimate Missing",
        "manual_cost_review": "Manual Cost Review Needed",
        "create_new_quote": "Create New Quote",
        "customer_quote_summary": "Customer Quote Summary",
        "unit_price": "Unit Price",
        "lead_time": "Lead Time",
        "spec_summary": "Specification Summary",
        "size": "Size",
        "gold_thickness": "Gold Thickness",
        "internal_pricing_summary": "Internal Pricing Summary",
        "estimated_cost": "Estimated Cost",
        "estimated_margin": "Estimated Margin",
        "applied_pricing_factors": "Applied Pricing Factors",
        "status_notes": "Status and Internal Notes",
        "internal_notes": "Internal Notes",
        "save": "Save",
        "structured_history": "Structured Data and Historical Analysis",
        "structured_data": "Structured Data",
        "source": "Source",
        "product": "Product",
        "pricing_version": "Pricing Version",
        "area": "Area",
        "layer_distribution": "Layer Distribution",
        "material_distribution": "Material Distribution",
        "quote_count": "Quote Count",
        "recent_rfqs": "Recent RFQs",
        "no_recent_rfqs": "No RFQs yet.",
        "quote_no": "Quote No.",
        "commercial_outcome": "Commercial Outcome",
        "final_price": "Final Price",
        "actual_cost": "Actual Cost",
        "actual_production_days": "Actual Production Days",
        "actual_margin": "Actual Margin",
        "lost_reason": "Lost Reason",
        "competitor": "Competitor",
        "competitor_price": "Competitor Price",
        "lost_reason_note": "Lost reason note",
        "save_commercial_outcome": "Save Commercial Outcome",
        "historical_intelligence": "Historical Intelligence",
        "similar_rfqs": "Similar RFQs",
        "limited_historical_data": "Limited historical data. Use as reference only.",
        "average_quote_unit": "Average Quote / Unit",
        "median_quote_unit": "Median Quote / Unit",
        "won_lost": "Won / Lost",
        "historical_win_rate": "Historical Win Rate",
        "similar_quotes": "Similar Quotes",
        "similarity": "Similarity",
        "outcome": "Outcome",
        "no_comparable_rfqs": "No comparable RFQs yet.",
    },
    "zh": {
        "app_title": "PCB 報價系統",
        "new_quote": "新增報價",
        "quote_list": "報價列表",
        "customers": "客戶管理",
        "import_quotes": "匯入報價",
        "reports": "統計報告",
        "logout": "登出",
        "menu": "選單",
        "language_label": "語言",
        "dashboard": "儀表板",
        "quotes_today": "今日報價數",
        "total_quotes": "歷史總報價數",
        "average_quote_amount": "平均報價金額",
        "view_quote_list": "查看報價列表",
        "email": "帳號 (Email)",
        "password": "密碼",
        "login": "登入",
        "register": "註冊",
        "create_account": "建立帳號",
        "invite_code": "邀請碼",
        "need_account": "還沒有帳號？",
        "register_with_invite": "使用邀請碼註冊",
        "already_have_account": "已經有帳號？",
        "layers": "層數",
        "quantity": "數量",
        "material": "材料",
        "customer": "客戶",
        "status": "狀態",
        "all": "全部",
        "pending_review": "待審核",
        "approved": "已批准",
        "ordered": "已下單",
        "filter": "篩選",
        "number": "編號",
        "total": "總價",
        "created_by": "建立者",
        "created_at": "建立時間",
        "company_name": "公司名稱",
        "contact": "聯絡人",
        "phone": "電話",
        "add_customer": "新增客戶",
        "customer_company_name": "客戶公司名稱",
        "length_mm": "長 (mm)",
        "width_mm": "寬 (mm)",
        "issue_ratio": "投料率",
        "lead_time_days": "交期 (天)",
        "board_thickness_mm": "板厚 (mm)",
        "enig_thickness": "ENIG 厚度 (u\")",
        "surface_finish": "表面處理",
        "copper_thickness": "銅厚",
        "outer_copper": "外層銅厚 (oz)",
        "inner_copper": "內層銅厚 (oz)",
        "min_hole": "最小孔徑 (mil)",
        "aspect_ratio": "縱橫比",
        "warpage": "板翹 (mil/inch)",
        "legend_color": "文字顏色",
        "solder_mask_color": "防焊顏色",
        "special_requirements": "特殊需求",
        "ai_form_assist": "AI 輔助填單",
        "paste_specs": "貼上規格文字",
        "upload_pcb_image": "或上傳 PCB 圖片",
        "parse_with_ai": "AI 解析並帶入表單",
        "save_quote": "計算並儲存報價",
        "quote_detail": "報價詳情",
        "last_updated_by": "最後修改",
        "generate_formal_quote": "產生正式報價單",
        "download_internal_excel": "下載內部 Excel",
        "sales_next_steps": "業務下一步",
        "pricing_status": "價格狀態",
        "rfq_quality": "RFQ 資料完整度",
        "complete": "完整",
        "required_before_quoting": "報價前必補",
        "recommended_checks": "建議確認",
        "data_complete": "資料完整，可以產生正式報價單。",
        "estimate_missing": "價格初估缺少",
        "manual_cost_review": "需人工確認成本",
        "create_new_quote": "建立新報價",
        "customer_quote_summary": "客戶報價摘要",
        "unit_price": "單片價格",
        "lead_time": "交期",
        "spec_summary": "規格摘要",
        "size": "尺寸",
        "gold_thickness": "金厚",
        "internal_pricing_summary": "內部計價摘要",
        "estimated_cost": "預估成本",
        "estimated_margin": "預估毛利",
        "applied_pricing_factors": "已套用價格因子",
        "status_notes": "狀態與內部備註",
        "internal_notes": "內部備註",
        "save": "儲存",
        "structured_history": "結構化資料與歷史分析",
        "structured_data": "結構化資料",
        "source": "來源",
        "product": "產品",
        "pricing_version": "計價版本",
        "area": "面積",
        "layer_distribution": "層數分佈",
        "material_distribution": "材料分佈",
        "quote_count": "報價數",
        "recent_rfqs": "近期 RFQ",
        "no_recent_rfqs": "尚無 RFQ。",
        "quote_no": "報價單號",
        "commercial_outcome": "商務結果",
        "final_price": "最終價格",
        "actual_cost": "實際成本",
        "actual_production_days": "實際生產天數",
        "actual_margin": "實際毛利",
        "lost_reason": "流失原因",
        "competitor": "競爭對手",
        "competitor_price": "競爭對手價格",
        "lost_reason_note": "流失原因備註",
        "save_commercial_outcome": "儲存商務結果",
        "historical_intelligence": "歷史智慧分析",
        "similar_rfqs": "相似 RFQ",
        "limited_historical_data": "歷史資料有限，僅供參考。",
        "average_quote_unit": "平均單片報價",
        "median_quote_unit": "中位數單片報價",
        "won_lost": "成交 / 流失",
        "historical_win_rate": "歷史成交率",
        "similar_quotes": "相似報價",
        "similarity": "相似度",
        "outcome": "結果",
        "no_comparable_rfqs": "尚無可比較 RFQ。",
    },
}


def get_lang(request: Request) -> str:
    lang = request.query_params.get("lang") or request.cookies.get("lang") or "en"
    return "zh" if lang == "zh" else "en"


def tr(request: Request, key: str) -> str:
    lang = get_lang(request)
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))


def localized_status_labels(request: Request):
    return {
        "pending": tr(request, "pending_review"),
        "approved": tr(request, "approved"),
        "ordered": tr(request, "ordered"),
    }


templates = Jinja2Templates(directory="templates")
templates.env.globals["tr"] = tr
templates.env.globals["get_lang"] = get_lang
templates.env.globals["other_lang"] = lambda request: "zh" if get_lang(request) == "en" else "en"
templates.env.globals["lang_name"] = lambda lang: "中文" if lang == "zh" else "EN"
logger = get_logger(__name__)

router = APIRouter(tags=["web"])

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
            {"request": request, "error": "Incorrect email or password"},
            status_code=401,
        )

    token = create_session_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True, max_age=60 * 60 * 24 * 7
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html", {"request": request, "error": None, "email": ""}
    )


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    invite_code: str = Form(...),
):
    if invite_code != settings.INVITE_CODE:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Invalid invite code", "email": email},
            status_code=400,
        )

    query_db = db.SessionLocal()
    existing = query_db.query(db.User).filter(db.User.email == email).first()
    if existing is not None:
        query_db.close()
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "This account is already registered", "email": email},
            status_code=400,
        )

    user = db.User(email=email, password_hash=hash_password(password))
    query_db.add(user)
    query_db.commit()
    query_db.refresh(user)
    query_db.close()

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


@router.get("/language/{lang}")
def set_language(lang: str, request: Request):
    target_lang = "zh" if lang == "zh" else "en"
    redirect_to = request.headers.get("referer") or "/"
    response = RedirectResponse(url=redirect_to, status_code=303)
    response.set_cookie("lang", target_lang, max_age=60 * 60 * 24 * 365)
    return response


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    stats = db.get_system_stats()
    query_db = db.SessionLocal()
    recent_quotes = (
        query_db.query(db.QuoteHistory)
        .options(joinedload(db.QuoteHistory.customer))
        .order_by(db.QuoteHistory.created_at.desc())
        .limit(5)
        .all()
    )
    query_db.close()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "recent_quotes": recent_quotes,
            "status_labels": localized_status_labels(request),
        },
    )


@router.get("/quotes/new", response_class=HTMLResponse)
def new_quote_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "quote_new.html", {"request": request, "user": user, "error": None, "form": {}}
    )


def _optional_float(value: str) -> Optional[float]:
    # A browser submits an empty text input as "" (not omitted), which
    # FastAPI/Pydantic won't coerce to a plain Optional[float] Form field —
    # it 422s. Take the field as a raw string and convert by hand instead.
    return float(value) if value and value.strip() else None


def _optional_int(value: str) -> Optional[int]:
    return int(value) if value and value.strip() else None


@router.post("/quotes/new")
def create_quote(
    request: Request,
    layer: int = Form(...),
    qty: int = Form(...),
    material: str = Form(""),
    length_mm: str = Form(""),
    width_mm: str = Form(""),
    issue_ratio: float = Form(1.0),
    enig: Optional[str] = Form(None),
    enig_thickness_uinch: str = Form(""),
    vip: Optional[str] = Form(None),
    impedance: Optional[str] = Form(None),
    back_drill: Optional[str] = Form(None),
    bvh: Optional[str] = Form(None),
    is_reorder: Optional[str] = Form(None),
    hard_gold: Optional[str] = Form(None),
    countersunk: Optional[str] = Form(None),
    counterbored: Optional[str] = Form(None),
    inspection_report_required: Optional[str] = Form(None),
    thickness_mm: str = Form(""),
    pitch_mm: str = Form(""),
    surface_finish: str = Form(""),
    copper_weight: str = Form(""),
    copper_outer_oz: str = Form(""),
    copper_inner_oz: str = Form(""),
    min_hole_mil: str = Form(""),
    line_space_mil: str = Form(""),
    hole_land_mil: str = Form(""),
    aspect_ratio: str = Form(""),
    warpage_mil_per_inch: str = Form(""),
    legend_color: str = Form(""),
    solder_mask_color: str = Form(""),
    special_requirements: str = Form(""),
    delivery_days: str = Form(""),
    company_name: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    parsed = {
        "layer": layer,
        "qty": qty,
        "material": material or None,
        "length_mm": _optional_float(length_mm),
        "width_mm": _optional_float(width_mm),
        "issue_ratio": issue_ratio,
        "enig": enig is not None,
        "enig_thickness_uinch": _optional_float(enig_thickness_uinch),
        "vip": vip is not None,
        "impedance": impedance is not None,
        "back_drill": back_drill is not None,
        "bvh": bvh is not None,
        "is_reorder": is_reorder is not None,
        "hard_gold": hard_gold is not None,
        "countersunk": countersunk is not None,
        "counterbored": counterbored is not None,
        "inspection_report_required": inspection_report_required is not None,
        "thickness_mm": _optional_float(thickness_mm),
        "pitch_mm": _optional_float(pitch_mm),
        "surface_finish": surface_finish or ("Hard Gold" if hard_gold is not None else None),
        "copper_weight": copper_weight or None,
        "copper_outer_oz": _optional_float(copper_outer_oz),
        "copper_inner_oz": _optional_float(copper_inner_oz),
        "min_hole_mil": _optional_float(min_hole_mil),
        "line_space_mil": _optional_float(line_space_mil),
        "hole_land_mil": _optional_float(hole_land_mil),
        "aspect_ratio": _optional_float(aspect_ratio),
        "warpage_mil_per_inch": _optional_float(warpage_mil_per_inch),
        "legend_color": legend_color or None,
        "solder_mask_color": solder_mask_color or None,
        "special_requirements": special_requirements or None,
        "delivery_days": _optional_int(delivery_days),
        "company_name": company_name or None,
    }
    if not parsed["copper_weight"] and parsed["copper_outer_oz"] and parsed["copper_inner_oz"]:
        if parsed["copper_outer_oz"] == parsed["copper_inner_oz"]:
            parsed["copper_weight"] = f'{parsed["copper_outer_oz"]:g}oz'
        else:
            parsed["copper_weight"] = (
                f'outer {parsed["copper_outer_oz"]:g}oz / '
                f'inner {parsed["copper_inner_oz"]:g}oz'
            )

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
            upload_dir = settings.UPLOAD_DIR
            import os as _os

            _os.makedirs(upload_dir, exist_ok=True)
            image_path = _os.path.join(upload_dir, f"web_{uuid.uuid4().hex}.jpg")
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
        if "gold_thickness_uin" in parsed and "enig_thickness_uinch" not in parsed:
            parsed["enig_thickness_uinch"] = parsed["gold_thickness_uin"]
        surface_finish = parsed.get("surface_finish")
        if isinstance(surface_finish, str) and surface_finish.strip().lower() == "hard gold":
            parsed["surface_finish"] = "Hard Gold"
            parsed["hard_gold"] = True
            parsed["enig"] = True
        if parsed.get("copper_outer_oz") and parsed.get("copper_inner_oz") and not parsed.get("copper_weight"):
            if parsed["copper_outer_oz"] == parsed["copper_inner_oz"]:
                parsed["copper_weight"] = f'{parsed["copper_outer_oz"]:g}oz'
            else:
                parsed["copper_weight"] = (
                    f'outer {parsed["copper_outer_oz"]:g}oz / '
                    f'inner {parsed["copper_inner_oz"]:g}oz'
                )
    except Exception as e:
        logger.error(f"AI assist failed: {e}")
        ai_error = "AI parsing failed. Please enter the specifications manually."
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
            "status_labels": localized_status_labels(request),
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

    if quote is None:
        query_db.close()
        raise HTTPException(status_code=404, detail="Quote not found")

    similar_quotes = find_similar_quotes(query_db, db.QuoteHistory, quote, limit=8)
    historical_summary = historical_pricing_summary(similar_quotes)
    query_db.close()

    return templates.TemplateResponse(
        "quote_detail.html",
        {
            "request": request,
            "user": user,
            "quote": quote,
            "status_labels": localized_status_labels(request),
            "outcome_labels": OUTCOME_LABELS,
            "lost_reason_labels": LOST_REASON_LABELS,
            "rfq_completeness": evaluate_rfq_completeness(quote),
            "similar_quotes": similar_quotes,
            "historical_summary": historical_summary,
        },
    )


@router.post("/quotes/{quote_id}/update")
def update_quote(
    quote_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    quote_outcome: Optional[str] = Form(None),
    final_price: Optional[str] = Form(None),
    actual_cost: Optional[str] = Form(None),
    production_lead_time_actual: Optional[str] = Form(None),
    lost_reason: Optional[str] = Form(None),
    lost_reason_note: Optional[str] = Form(None),
    competitor_name: Optional[str] = Form(None),
    competitor_price: Optional[str] = Form(None),
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
    if quote_outcome is not None:
        normalized_outcome = normalize_outcome(quote_outcome)
        if normalized_outcome is None:
            query_db.close()
            raise HTTPException(status_code=400, detail="Invalid quote outcome")
        quote.quote_outcome = normalized_outcome

    numeric_updates = [
        ("final_price", final_price, to_non_negative_float),
        ("actual_cost", actual_cost, to_non_negative_float),
        ("competitor_price", competitor_price, to_non_negative_float),
        ("production_lead_time_actual", production_lead_time_actual, to_non_negative_int),
    ]
    for field_name, raw_value, parser in numeric_updates:
        if raw_value is None:
            continue
        parsed_value = parser(raw_value)
        if raw_value != "" and parsed_value is None:
            query_db.close()
            raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
        setattr(quote, field_name, parsed_value)

    quote.actual_margin_pct = calculate_margin(quote.final_price, quote.actual_cost)

    if lost_reason is not None:
        normalized_lost_reason = normalize_lost_reason(lost_reason)
        if lost_reason and normalized_lost_reason is None:
            query_db.close()
            raise HTTPException(status_code=400, detail="Invalid lost reason")
        quote.lost_reason = normalized_lost_reason
    if lost_reason_note is not None:
        quote.lost_reason_note = lost_reason_note or None
    if competitor_name is not None:
        quote.competitor_name = competitor_name or None
    quote.updated_by_user_id = user.id
    query_db.commit()
    query_db.close()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.get("/quotes/{quote_id}/export/excel")
def quote_export_excel(quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    from sqlalchemy.orm import joinedload

    query_db = db.SessionLocal()
    quote = (
        query_db.query(db.QuoteHistory)
        .options(joinedload(db.QuoteHistory.customer))
        .filter(db.QuoteHistory.id == quote_id)
        .first()
    )
    query_db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    filename = export_quote_excel(quote.spec_json, quote.breakdown_json)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/quotes/{quote_id}/export/formal")
def quote_export_formal(quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    from sqlalchemy.orm import joinedload

    query_db = db.SessionLocal()
    quote = (
        query_db.query(db.QuoteHistory)
        .options(joinedload(db.QuoteHistory.customer))
        .filter(db.QuoteHistory.id == quote_id)
        .first()
    )
    query_db.close()

    if quote is None or not quote.spec_json or not quote.breakdown_json:
        raise HTTPException(status_code=404, detail="Quote not found or missing spec data")

    output_path = export_formal_quote(
        quote.spec_json,
        quote.breakdown_json,
        {
            "quote_no": quote.quote_no,
            "customer_name": quote.customer.company_name if quote.customer else None,
            "quote_date": quote.created_at.strftime("%Y/%m/%d") if quote.created_at else None,
        },
    )
    import os as _os

    filename = _os.path.basename(output_path)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/customers", response_class=HTMLResponse)
def customers_list(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    customers = query_db.query(db.Customer).order_by(db.Customer.company_name).all()
    customer_analytics = {
        item["customer_id"]: item
        for item in get_customer_analytics(query_db, db.Customer, db.QuoteHistory, limit=1000)
    }
    query_db.close()

    return templates.TemplateResponse(
        "customers.html",
        {
            "request": request,
            "user": user,
            "customers": customers,
            "customer_analytics": customer_analytics,
        },
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


def _mapping_from_form(
    customer_col: str,
    layer_col: str,
    material_col: str,
    qty_col: str,
    size_col: str,
    total_col: str,
    quote_date_col: str,
    outcome_col: str,
) -> dict:
    return {
        "customer": customer_col,
        "layer": layer_col,
        "material": material_col,
        "qty": qty_col,
        "size": size_col,
        "total": total_col,
        "quote_date": quote_date_col,
        "quote_outcome": outcome_col,
    }


@router.get("/import/quotes", response_class=HTMLResponse)
def import_quotes_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "import_quotes.html",
        {"request": request, "user": user, "result": None, "error": None},
    )


@router.post("/import/quotes", response_class=HTMLResponse)
async def import_quotes_submit(
    request: Request,
    file: UploadFile = File(...),
    action: str = Form("preview"),
    customer_col: str = Form("Customer Name"),
    layer_col: str = Form("Layers"),
    material_col: str = Form("Material"),
    qty_col: str = Form("Qty"),
    size_col: str = Form("Size"),
    total_col: str = Form("Quote"),
    quote_date_col: str = Form("Date"),
    outcome_col: str = Form("Result"),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    try:
        file_bytes = await file.read()
        mapping = _mapping_from_form(
            customer_col,
            layer_col,
            material_col,
            qty_col,
            size_col,
            total_col,
            quote_date_col,
            outcome_col,
        )
        if action == "confirm":
            query_db = db.SessionLocal()
            try:
                result = confirm_import(query_db, db, file_bytes, mapping, user_id=user.id)
            finally:
                query_db.close()
            if result["status"] == "error":
                return templates.TemplateResponse(
                    "import_quotes.html",
                    {"request": request, "user": user, "result": result, "error": "Invalid rows must be fixed before import."},
                    status_code=400,
                )
        else:
            result = preview_import(file_bytes, mapping)
    except Exception as e:
        return templates.TemplateResponse(
            "import_quotes.html",
            {"request": request, "user": user, "result": None, "error": str(e)},
            status_code=400,
        )

    return templates.TemplateResponse(
        "import_quotes.html",
        {"request": request, "user": user, "result": result, "error": None},
    )


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    query_db = db.SessionLocal()
    outcome_stats = get_outcome_stats(query_db, db.QuoteHistory)
    pricing_trends = get_pricing_trends(query_db, db.QuoteHistory)
    top_customers = get_customer_analytics(query_db, db.Customer, db.QuoteHistory)
    query_db.close()

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "user": user,
            "by_layer": db.get_stats_by_layer(),
            "by_material": db.get_stats_by_material(),
            "outcome_stats": outcome_stats,
            "pricing_trends": pricing_trends,
            "top_customers": top_customers,
        },
    )
