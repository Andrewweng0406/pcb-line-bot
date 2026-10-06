import uuid
import math
import json
import re
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
    monetary_summary,
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
from app.extraction_review import (
    attach_extraction_review,
    build_extraction_review,
    extraction_review_from_spec,
    sign_review,
    read_review,
    reconcile_review,
    confirm_review,
    clarification_draft,
)
from app.formal_quote_export import export_formal_quote
from app.historical_intelligence import find_similar_quotes, historical_pricing_summary
from app.price_assessment import assess_quote_price
from app.image_parser import parse_pcb_image
from app.import_quotes import confirm_import, preview_import, OPTIONAL_MAPPING, DEFAULT_MAPPING
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
from app.quote_workflow import customer_export_readiness, validate_status_transition
from app.upload_validation import read_image_upload, read_upload
from starlette.concurrency import run_in_threadpool
from app.core.rate_limit import rate_limiter, client_identity
from app.core.permissions import can, require_permission, authorize_quote_update
from app.core.auth import request_origin
from app.rfq_completeness import evaluate_rfq_completeness
from app.quote_engine import calculate_quote

TRANSLATIONS = {
    "en": {
        "app_title": "PCB Quote System",
        "business_status": "Business Status",
        "release_readiness": "Data Review / Formal Export",
        "data_review_clear": "No pending extraction confirmations.",
        "review_pending_fields": "Review Pending Fields",
        "show_all_fields": "Show All Fields",
        "historical_basis": "Only records preceding this quote; one eligible record per revision family.",
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
        "data_complete": "RFQ completeness checks passed. Formal release checks are separate.",
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
        "pipeline_snapshot": "Pipeline Snapshot",
        "active_quotes": "Active Quotes",
        "pipeline_value": "Pipeline Value",
        "won_quotes": "Won Quotes",
        "lost_quotes": "Lost Quotes",
        "win_rate": "Win Rate",
        "no_response": "No Response",
        "cancelled": "Cancelled",
        "ai_extraction_review": "AI Extraction Review",
        "conflict": "Conflict",
        "evidence": "Source Evidence",
        "confirm_field": "Confirm field",
        "review_note": "Review Note",
        "confirm_selected": "Confirm Selected Fields",
        "original_value": "Extracted Value",
        "final_value": "Current Value",
        "review_history": "Review History",
        "confirmed": "Confirmed",
        "awaiting_confirmation": "Awaiting Confirmation",
        "clarification_draft": "Customer Clarification Draft",
        "original_rfq": "Original RFQ",
        "release_blocked": "Confirm the pending extraction fields before approval or formal export.",
        "download_estimate": "Download Estimate",
        "formal_release_ready": "Approved for formal export",
        "formal_release_blocked": "Formal export blocked",
        "estimate_document_notice": "Estimate only - not an official quotation",
        "export_pending_review": "Confirm pending extraction fields before customer export.",
        "export_invalid_calculation": "Saved calculation is missing or inconsistent. Create a revision and recalculate.",
        "export_unknown_currency": "An explicit three-letter currency code is required for customer export.",
        "export_missing_specs": "Complete these specifications in a revision:",
        "export_missing_pricing_review": "Pricing review is unavailable. Create a revision and recalculate.",
        "export_pricing_not_ready": "Pricing is still an estimate or requires review; unresolved pricing factors block formal export.",
        "export_process_conflict": "Surface finish and priced plating options disagree. Correct them in a revision.",
        "export_approval_required": "Manager approval is required before formal export.",
        "create_revision": "Create Revision",
        "revision_of": "Revision Of",
        "review_required": "Review Required",
        "field": "Field",
        "value": "Value",
        "source": "Source",
        "confidence": "Confidence",
        "reason": "Reason",
        "explicit": "Explicit",
        "inferred": "Inferred",
        "default": "Default",
        "missing": "Missing",
        "image": "Image",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "review_before_quote": "Review highlighted fields before sending this quote.",
        "all_extracted_fields_clear": "All extracted fields look ready for review.",
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
        "comparison_current": "Current RFQ",
        "comparison_history": "Historical RFQ",
        "comparison_field": "Specification",
        "comparison_delta": "Difference",
        "comparison_same": "Same",
        "comparison_different": "Different",
        "comparison_unknown": "Unknown",
        "comparison_eligible": "Eligible reference",
        "comparison_excluded": "Excluded from benchmark",
        "comparison_details": "Specification comparison",
        "evidence_quoted": "Quoted / Unit",
        "evidence_accepted": "Accepted / Unit",
        "evidence_cost": "Actual Cost / Unit",
        "evidence_samples": "valid samples",
        "evidence_insufficient": "Insufficient evidence",
        "evidence_median": "Median",
        "evidence_eligible": "eligible references",
        "evidence_excluded": "excluded",
        "evidence_window": "Latest 200 candidates; minimum 5 independent references per metric",
        "price_review": "Price Review",
        "price_above_band": "Above historical band",
        "price_below_band": "Below historical band",
        "price_within_band": "Within historical band",
        "price_insufficient_evidence": "Insufficient evidence",
        "price_review_pending": "Confirm extracted specifications first",
        "price_invalid_current_price": "Current unit price unavailable",
        "price_missing_quote_date": "Quote date unavailable",
        "price_band": "Historical review band / Unit",
        "price_deviation": "Deviation from quoted median",
        "price_current": "Current Quote / Unit",
        "price_reference_count": "independent historical quoted prices",
        "price_action_above_band": "Review pricing inputs and commercial terms before sending.",
        "price_action_below_band": "Review pricing inputs and recorded costs before sending.",
        "price_action_within_band": "Historical comparison available for staff review.",
        "price_action_insufficient_evidence": "At least 5 eligible earlier quotes are required.",
        "price_action_review_pending": "Complete the extraction review before assessing price.",
        "price_action_invalid_current_price": "Record a positive finite unit price to assess this quote.",
        "price_action_missing_quote_date": "Record the quote date to identify earlier references.",
        "price_context": "Specification differences to review",
        "price_context_note": "These differences may affect comparability; their price impact has not been calculated.",
        "price_rule": "Median ± the greater of 20% of median or 3 × 1.4826 × MAD",
        "price_rule_note": "Review threshold; not a recommended selling price or a calibrated probability.",
        "price_basis": "Price Review Evidence",
        "price_as_of": "Reference cutoff",
        "price_mad": "Median Absolute Deviation",
        "price_exclusions": "Excluded from price review",
        "price_no_differences": "Area, quantity and lead time match",
        "reason_ineligible_reference": "Reference eligibility not confirmed",
        "reason_missing_reference_date": "Historical quote date not recorded",
        "reason_not_historical": "Quote is not earlier than this RFQ",
        "reason_invalid_reference_price": "Quoted unit price is invalid or missing",
        "reason_missing_currency": "Currency not recorded",
        "reason_different_currency": "Different currency",
        "reason_missing_pricing_version": "Pricing version not recorded",
        "reason_different_pricing_version": "Different pricing version",
        "reason_review_pending": "Extraction review pending",
        "reason_missing_specification": "Incomplete specification",
        "reason_different_specification": "Different manufacturing specification",
        "reason_scale_difference": "Area, quantity or lead time differs by more than 2x",
        "reason_unknown_processes": "Special processes not fully recorded",
        "reason_low_similarity": "Similarity below 75",
        "reason_related_revision": "Same RFQ revision family",
        "reason_unknown_lineage": "Revision lineage incomplete",
        "compare_layer": "Layers",
        "compare_material": "Material",
        "compare_area_in2": "Area (in²)",
        "compare_qty": "Quantity",
        "compare_board_thickness_mm": "Thickness (mm)",
        "compare_copper_weight_oz": "Copper (oz)",
        "compare_surface_finish": "Surface Finish",
        "compare_gold_thickness_uin": "Gold Thickness (µin)",
        "compare_delivery_days": "Lead Time (days)",
        "compare_enig": "ENIG",
        "compare_vip": "Via in Pad",
        "compare_impedance": "Controlled Impedance",
        "compare_back_drill": "Back Drill",
        "compare_bvh": "Blind / Buried Vias",
        "compare_currency": "Currency",
        "compare_pricing_version": "Pricing Version",
        "comparison_yes": "Yes",
        "comparison_no": "No",
    },
    "zh": {
        "app_title": "PCB 報價系統",
        "business_status": "商務狀態",
        "release_readiness": "資料覆核／正式匯出",
        "data_review_clear": "目前沒有待確認的解析欄位。",
        "review_pending_fields": "覆核待確認欄位",
        "show_all_fields": "顯示全部欄位",
        "historical_basis": "僅使用本報價之前的紀錄；每個修訂家族取一筆有效資料。",
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
        "data_complete": "詢價資料完整度檢查通過；正式放行條件另行檢查。",
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
        "pipeline_snapshot": "案件狀態總覽",
        "active_quotes": "進行中報價",
        "pipeline_value": "案件金額",
        "won_quotes": "成交報價",
        "lost_quotes": "流失報價",
        "win_rate": "成交率",
        "no_response": "無回覆",
        "cancelled": "已取消",
        "ai_extraction_review": "AI 解析覆核",
        "conflict": "規格衝突",
        "evidence": "原文證據",
        "confirm_field": "確認欄位",
        "review_note": "覆核備註",
        "confirm_selected": "確認勾選欄位",
        "original_value": "解析值",
        "final_value": "目前值",
        "review_history": "覆核歷程",
        "confirmed": "已確認",
        "awaiting_confirmation": "待確認",
        "clarification_draft": "客戶規格確認信草稿",
        "original_rfq": "原始詢價內容",
        "release_blocked": "請先確認待覆核欄位，再批准或匯出正式報價。",
        "download_estimate": "下載估價單",
        "formal_release_ready": "可匯出正式報價",
        "formal_release_blocked": "正式報價尚未放行",
        "estimate_document_notice": "僅供估價，非正式報價單",
        "export_pending_review": "對外匯出前請先確認待覆核欄位。",
        "export_invalid_calculation": "計算資料缺失或不一致，請建立修訂版重新計算。",
        "export_unknown_currency": "對外匯出需要明確的幣別。",
        "export_missing_specs": "請在修訂版補齊下列規格：",
        "export_missing_pricing_review": "缺少價格檢查紀錄，請建立修訂版重新計算。",
        "export_pricing_not_ready": "目前仍為估價或需要價格覆核，未解決的計價因素會阻擋正式匯出。",
        "export_process_conflict": "表面處理與計價製程選項不一致，請建立修訂版修正。",
        "export_approval_required": "正式匯出前需要主管核准。",
        "create_revision": "建立修訂版",
        "revision_of": "修訂來源",
        "review_required": "需要覆核",
        "field": "欄位",
        "value": "值",
        "source": "來源",
        "confidence": "信心度",
        "reason": "原因",
        "explicit": "明確提供",
        "inferred": "推斷",
        "default": "預設",
        "missing": "缺失",
        "image": "圖片",
        "high": "高",
        "medium": "中",
        "low": "低",
        "review_before_quote": "送出報價前請覆核標示欄位。",
        "all_extracted_fields_clear": "AI 解析欄位可進入人工覆核。",
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
        "comparison_current": "目前 RFQ",
        "comparison_history": "歷史 RFQ",
        "comparison_field": "規格",
        "comparison_delta": "差異",
        "comparison_same": "相同",
        "comparison_different": "不同",
        "comparison_unknown": "未知",
        "comparison_eligible": "有效參考",
        "comparison_excluded": "不納入基準",
        "comparison_details": "規格差異比較",
        "evidence_quoted": "單片報價",
        "evidence_accepted": "單片成交價",
        "evidence_cost": "單片實際成本",
        "evidence_samples": "有效樣本",
        "evidence_insufficient": "依據不足",
        "evidence_median": "中位數",
        "evidence_eligible": "有效參考",
        "evidence_excluded": "已排除",
        "evidence_window": "最近 200 筆候選；每項指標至少 5 筆獨立參考",
        "price_review": "價格覆核",
        "price_above_band": "高於歷史區間",
        "price_below_band": "低於歷史區間",
        "price_within_band": "位於歷史區間",
        "price_insufficient_evidence": "依據不足",
        "price_review_pending": "請先確認解析規格",
        "price_invalid_current_price": "目前單價無法判定",
        "price_missing_quote_date": "缺少報價日期",
        "price_band": "歷史覆核區間／單片",
        "price_deviation": "相對報價中位數偏差",
        "price_current": "目前單片報價",
        "price_reference_count": "筆獨立歷史單價",
        "price_action_above_band": "送出前請覆核定價輸入與商務條件。",
        "price_action_below_band": "送出前請覆核定價輸入與已記錄的成本。",
        "price_action_within_band": "歷史比較可供業務覆核。",
        "price_action_insufficient_evidence": "至少需要 5 筆符合條件且較早的歷史報價。",
        "price_action_review_pending": "完成解析覆核後再判定價格。",
        "price_action_invalid_current_price": "請記錄有效且大於零的單價。",
        "price_action_missing_quote_date": "請記錄報價日期以辨識較早的參考資料。",
        "price_context": "需覆核的規格差異",
        "price_context_note": "這些差異可能影響可比性；尚未計算其價格影響。",
        "price_rule": "中位數 ±「中位數的 20%」與「3 × 1.4826 × MAD」兩者較大值",
        "price_rule_note": "人工覆核門檻；並非建議售價或經校準的機率。",
        "price_basis": "價格覆核依據",
        "price_as_of": "參考資料截止時間",
        "price_mad": "中位數絕對偏差",
        "price_exclusions": "不納入價格覆核",
        "price_no_differences": "面積、數量與交期相同",
        "reason_ineligible_reference": "未確認參考資格",
        "reason_missing_reference_date": "未記錄歷史報價日期",
        "reason_not_historical": "報價時間未早於目前 RFQ",
        "reason_invalid_reference_price": "歷史單價無效或缺漏",
        "reason_missing_currency": "未記錄幣別",
        "reason_different_currency": "幣別不同",
        "reason_missing_pricing_version": "未記錄定價版本",
        "reason_different_pricing_version": "定價版本不同",
        "reason_review_pending": "解析結果待覆核",
        "reason_missing_specification": "規格不完整",
        "reason_different_specification": "製造規格不同",
        "reason_scale_difference": "面積、數量或交期差距超過兩倍",
        "reason_unknown_processes": "特殊製程記錄不完整",
        "reason_low_similarity": "相似度低於 75",
        "reason_related_revision": "同一 RFQ 修訂系列",
        "reason_unknown_lineage": "修訂來源不完整",
        "compare_layer": "層數",
        "compare_material": "材料",
        "compare_area_in2": "面積（平方英吋）",
        "compare_qty": "數量",
        "compare_board_thickness_mm": "板厚（mm）",
        "compare_copper_weight_oz": "銅厚（oz）",
        "compare_surface_finish": "表面處理",
        "compare_gold_thickness_uin": "金厚（µin）",
        "compare_delivery_days": "交期（天）",
        "compare_enig": "化學鎳金",
        "compare_vip": "盤中孔",
        "compare_impedance": "阻抗控制",
        "compare_back_drill": "背鑽",
        "compare_bvh": "盲埋孔",
        "compare_currency": "幣別",
        "compare_pricing_version": "定價版本",
        "comparison_yes": "是",
        "comparison_no": "否",
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


def localized_outcome_labels(request: Request):
    return {
        "pending": tr(request, "pending_review"),
        "won": tr(request, "won_quotes"),
        "lost": tr(request, "lost_quotes"),
        "no_response": tr(request, "no_response"),
        "cancelled": tr(request, "cancelled"),
    }


templates = Jinja2Templates(directory="templates")
templates.env.globals["tr"] = tr
templates.env.globals["can"] = can
templates.env.globals["import_optional_mapping"] = OPTIONAL_MAPPING
templates.env.globals["import_default_mapping"] = DEFAULT_MAPPING
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
    if user is not None and not can(user, "read"):
        return None
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        rate_limiter.consume("login", client_identity(request), settings.LOGIN_RATE_LIMIT)
    except HTTPException as exc:
        return templates.TemplateResponse("login.html", {"request": request, "error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
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
        SESSION_COOKIE_NAME, token, httponly=True, secure=request_origin(request)[0] == "https", samesite="lax", max_age=60 * 60 * 24 * 7
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
    try:
        rate_limiter.consume("register", client_identity(request), settings.REGISTER_RATE_LIMIT)
    except HTTPException as exc:
        return templates.TemplateResponse("register.html", {"request": request, "error": exc.detail, "email": email}, status_code=exc.status_code, headers=exc.headers)
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

    user = db.User(email=email, password_hash=hash_password(password), role="staff")
    query_db.add(user)
    query_db.commit()
    query_db.refresh(user)
    query_db.close()

    token = create_session_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME, token, httponly=True, secure=request_origin(request)[0] == "https", samesite="lax", max_age=60 * 60 * 24 * 7
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
    status_counts = dict(
        query_db.query(db.QuoteHistory.status, db.func.count(db.QuoteHistory.id))
        .group_by(db.QuoteHistory.status)
        .all()
    )
    outcome_counts = dict(
        query_db.query(db.QuoteHistory.quote_outcome, db.func.count(db.QuoteHistory.id))
        .group_by(db.QuoteHistory.quote_outcome)
        .all()
    )
    active_quotes = (
        query_db.query(db.QuoteHistory)
        .filter(db.QuoteHistory.status.in_(["pending", "approved"]))
        .all()
    )
    quote_amounts = monetary_summary(query_db.query(db.QuoteHistory).all())
    query_db.close()
    won_count = outcome_counts.get("won", 0)
    lost_count = outcome_counts.get("lost", 0)
    decided_count = won_count + lost_count
    pipeline_snapshot = {
        "active_count": status_counts.get("pending", 0) + status_counts.get("approved", 0),
        "amounts_by_currency": monetary_summary(active_quotes),
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate": (won_count / decided_count) if decided_count else None,
    }
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "recent_quotes": recent_quotes,
            "pipeline_snapshot": pipeline_snapshot,
            "quote_amounts": quote_amounts,
            "status_labels": localized_status_labels(request),
            "outcome_labels": localized_outcome_labels(request),
        },
    )


@router.get("/quotes/new", response_class=HTMLResponse)
def new_quote_page(request: Request, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    require_permission(user, "edit")
    return templates.TemplateResponse(
        "quote_new.html", {"request": request, "user": user, "error": None, "form": {}}
    )


def _optional_float(value: str) -> Optional[float]:
    # A browser submits an empty text input as "" (not omitted), which
    # FastAPI/Pydantic won't coerce to a plain Optional[float] Form field —
    # it 422s. Take the field as a raw string and convert by hand instead.
    if not value or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid numeric specification")
    if not math.isfinite(parsed):
        raise HTTPException(status_code=400, detail="Numeric specifications must be finite")
    return parsed


def _optional_int(value: str) -> Optional[int]:
    try:
        return int(value) if value and value.strip() else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integer specification")


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
    extraction_review_json: str = Form(""),
    area_inch: str = Form(""),
    trace_to_hole_mil: str = Form(""),
    press_count: str = Form(""),
    internal_layers: str = Form(""),
    flatness: str = Form(""),
    hole_size_mil: str = Form(""),
    copper_weight_oz: str = Form(""),
    back_drill_fee: str = Form(""),
    extraction_review_token: str = Form(""),
    reviewed_fields: list[str] = Form([]),
    review_note: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    require_permission(user, "edit")
    if back_drill_fee.strip():
        require_permission(user, "financial")
    if not math.isfinite(issue_ratio) or issue_ratio <= 0:
        raise HTTPException(status_code=400, detail="Issue ratio must be positive and finite")

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
        "area_inch": _optional_float(area_inch),
        "trace_to_hole_mil": _optional_float(trace_to_hole_mil),
        "flatness": flatness or None,
        "hole_size_mil": _optional_float(hole_size_mil),
        "copper_weight_oz": _optional_float(copper_weight_oz),
    }
    for field, raw_value in (("press_count", press_count), ("internal_layers", internal_layers), ("back_drill_fee", back_drill_fee)):
        value = _optional_int(raw_value)
        if value is not None:
            parsed[field] = value
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    for field in ("length_mm", "width_mm", "area_inch", "thickness_mm", "hole_size_mil", "press_count"):
        if parsed.get(field) is not None and parsed[field] <= 0:
            raise HTTPException(status_code=400, detail=f"{field} must be positive")
    for field in ("internal_layers", "back_drill_fee"):
        if parsed.get(field) is not None and parsed[field] < 0:
            raise HTTPException(status_code=400, detail=f"{field} must not be negative")
    if not parsed["copper_weight"] and parsed["copper_outer_oz"] and parsed["copper_inner_oz"]:
        if parsed["copper_outer_oz"] == parsed["copper_inner_oz"]:
            parsed["copper_weight"] = f'{parsed["copper_outer_oz"]:g}oz'
        else:
            parsed["copper_weight"] = (
                f'outer {parsed["copper_outer_oz"]:g}oz / '
                f'inner {parsed["copper_inner_oz"]:g}oz'
            )
    extraction_review = None
    if extraction_review_token:
        try:
            original_review = read_review(extraction_review_token, user.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        extraction_review = reconcile_review(original_review, parsed)
        try:
            extraction_review = confirm_review(extraction_review, reviewed_fields, user.id, user.email, review_note)
        except ValueError as exc:
            return templates.TemplateResponse("quote_new.html", {
                "request": request, "user": user, "error": str(exc), "form": parsed,
                "extraction_review": extraction_review,
                "extraction_review_token": extraction_review_token,
                "clarification_draft": clarification_draft(extraction_review),
                "revision_of": extraction_review.get("revision_of"),
            }, status_code=400)
    elif extraction_review_json.strip():
        raise HTTPException(status_code=400, detail="Unsigned extraction review. Parse the RFQ again.")
    parsed = attach_extraction_review(parsed, extraction_review)

    result = calculate_quote(parsed)

    if result.get("status") != "success":
        return templates.TemplateResponse(
            "quote_new.html",
            {
                "request": request,
                "user": user,
                "error": result.get("message"),
                "form": parsed,
                "extraction_review": extraction_review,
                "extraction_review_token": extraction_review_token,
                "clarification_draft": clarification_draft(extraction_review),
                "revision_of": (extraction_review or {}).get("revision_of"),
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

    saved = db.save_quote(
        source_channel_id=f"web:{user.id}",
        parsed=parsed,
        result=result,
        customer_id=customer_id,
        created_by_user_id=user.id,
    )
    if not saved:
        return templates.TemplateResponse("quote_new.html", {
            "request": request, "user": user, "form": parsed,
            "error": "The quote could not be saved. Please try again.",
            "extraction_review": extraction_review,
            "extraction_review_token": extraction_review_token,
            "clarification_draft": clarification_draft(extraction_review),
            "revision_of": (extraction_review or {}).get("revision_of"),
        }, status_code=503)

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
    require_permission(user, "ai")

    await run_in_threadpool(rate_limiter.consume, "ai", str(user.id), settings.AI_RATE_LIMIT)

    parsed = {}
    extraction_review = None
    ai_error = None
    source_image = None
    if len(spec_text) > 20000:
        raise HTTPException(status_code=413, detail="RFQ text exceeds 20,000 characters.")
    try:
        input_type = "text"
        if photo is not None and photo.filename:
            input_type = "image"
            upload_dir = settings.UPLOAD_DIR
            import os as _os

            _os.makedirs(upload_dir, exist_ok=True)
            image_bytes, extension = await read_image_upload(photo)
            source_image = f"web_{user.id}_{uuid.uuid4().hex}{extension}"
            image_path = _os.path.join(upload_dir, source_image)
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            parsed = await run_in_threadpool(parse_pcb_image, image_path)
        elif spec_text.strip():
            parsed = await run_in_threadpool(parse_pcb_text, spec_text)

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
        if parsed.get("copper_outer_oz") and parsed.get("copper_inner_oz") and not parsed.get("copper_weight"):
            if parsed["copper_outer_oz"] == parsed["copper_inner_oz"]:
                parsed["copper_weight"] = f'{parsed["copper_outer_oz"]:g}oz'
            else:
                parsed["copper_weight"] = (
                    f'outer {parsed["copper_outer_oz"]:g}oz / '
                    f'inner {parsed["copper_inner_oz"]:g}oz'
                )
        extraction_review = build_extraction_review(
            parsed,
            raw_input=spec_text if input_type == "text" else "",
            input_type=input_type,
        )
        if source_image:
            extraction_review["source_image"] = source_image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI assist failed: {e}")
        ai_error = "AI parsing failed. Please enter the specifications manually."
        parsed = {}

    return templates.TemplateResponse(
        "_quote_form_fields.html",
        {
            "request": request,
            "form": parsed,
            "ai_error": ai_error,
            "user": user,
            "extraction_review": extraction_review,
            "extraction_review_token": sign_review(extraction_review, user.id) if extraction_review else "",
            "clarification_draft": clarification_draft(extraction_review),
        },
        headers={"HX-Reswap": "none", "HX-Trigger": json.dumps({"aiParseFailed": {"message": ai_error}})} if ai_error else None,
    )


@router.get("/rfq-images/{filename}")
def rfq_image(filename: str, user=Depends(get_current_user_optional)):
    from pathlib import Path
    from fastapi.responses import FileResponse
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    require_permission(user, "review")
    root = Path(settings.UPLOAD_DIR).resolve()
    path = (root / filename).resolve()
    if path.parent != root or not re.fullmatch(r"web_\d+_[0-9a-f]{32}\.(?:jpg|png|webp)", filename) or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    if not filename.startswith(f"web_{user.id}_") and not can(user, "approve"):
        with db.SessionLocal() as session:
            linked = session.query(db.QuoteHistory.id).filter(db.QuoteHistory.spec_json["_extraction_review"]["source_image"].as_string() == filename).first()
        if linked is None:
            raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


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

    historical_candidates = find_similar_quotes(query_db, db.QuoteHistory, quote, limit=200, historical_only=True)
    historical_summary = historical_pricing_summary(historical_candidates)
    price_assessment = assess_quote_price(quote, historical_candidates)
    similar_quotes = historical_candidates[:8]
    review = extraction_review_from_spec(quote.spec_json)
    if review:
        review = reconcile_review(review, quote.spec_json)
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
            "export_readiness": customer_export_readiness(quote),
            "extraction_review": review,
            "clarification_draft": clarification_draft(review),
            "similar_quotes": similar_quotes,
            "historical_summary": historical_summary,
            "price_assessment": price_assessment,
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

    try:
        updates = {field: value for field, value in {"final_price": final_price, "actual_cost": actual_cost, "competitor_price": competitor_price}.items() if value is not None}
        authorize_quote_update(user, quote, {"status": status, **updates})
    except HTTPException:
        query_db.close()
        raise
    try:
        validate_status_transition(quote, status)
    except ValueError as exc:
        query_db.close()
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        query_db.close()
        raise HTTPException(status_code=409, detail=str(exc))
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
    require_permission(user, "export_internal")

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

    filename = export_quote_excel(quote.spec_json, quote.breakdown_json, currency=quote.currency or "UNKNOWN")
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.get("/quotes/{quote_id}/export/formal")
def quote_export_formal(quote_id: int, user=Depends(get_current_user_optional)):
    return _export_customer_quote(quote_id, user, "formal")


@router.get("/quotes/{quote_id}/export/estimate")
def quote_export_estimate(quote_id: int, user=Depends(get_current_user_optional)):
    return _export_customer_quote(quote_id, user, "estimate")


def _export_customer_quote(quote_id, user, document_kind):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    require_permission(user, "export_formal")

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

    readiness = customer_export_readiness(quote)
    blockers = readiness[f"{document_kind}_blockers"]
    if blockers:
        raise HTTPException(status_code=409, detail={"document_kind": document_kind, "blockers": blockers})

    output_path = export_formal_quote(
        quote.spec_json,
        quote.breakdown_json,
        {
            "document_kind": document_kind,
            "release_blockers": readiness["formal_blockers"] if document_kind == "estimate" else [],
            "quote_no": quote.quote_no,
            "currency": quote.currency or "UNKNOWN",
            "customer_name": quote.customer.company_name if quote.customer else None,
            "quote_date": quote.created_at.strftime("%Y/%m/%d") if quote.created_at else None,
        },
    )
    import os as _os

    filename = _os.path.basename(output_path)
    return RedirectResponse(url=f"/download/exports/{filename}", status_code=303)


@router.post("/quotes/{quote_id}/review")
def review_quote(
    quote_id: int,
    reviewed_fields: list[str] = Form([]),
    review_note: str = Form(""),
    user=Depends(get_current_user_optional),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    require_permission(user, "review")
    with db.SessionLocal() as session:
        quote = session.query(db.QuoteHistory).filter(db.QuoteHistory.id == quote_id).with_for_update().first()
        if quote is None:
            raise HTTPException(status_code=404, detail="Quote not found")
        review = extraction_review_from_spec(quote.spec_json)
        if review is None:
            raise HTTPException(status_code=400, detail="This quote has no extraction review.")
        review = reconcile_review(review, quote.spec_json)
        try:
            review = confirm_review(review, reviewed_fields, user.id, user.email, review_note)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        quote.spec_json = attach_extraction_review(quote.spec_json, review)
        quote.updated_by_user_id = user.id
        session.commit()
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.get("/quotes/{quote_id}/revise", response_class=HTMLResponse)
def revise_quote(request: Request, quote_id: int, user=Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    require_permission(user, "edit")
    with db.SessionLocal() as session:
        quote = session.get(db.QuoteHistory, quote_id)
        if quote is None or not quote.spec_json:
            raise HTTPException(status_code=404, detail="Quote not found or missing spec data")
        form = dict(quote.spec_json)
        if quote.customer:
            form["company_name"] = quote.customer.company_name
        review = extraction_review_from_spec(form) or build_extraction_review(form)
        review = reconcile_review(review, form)
        review["revision_of"] = quote.id
        return templates.TemplateResponse("quote_new.html", {
            "request": request, "user": user, "error": None, "form": form,
            "extraction_review": review, "extraction_review_token": sign_review(review, user.id),
            "clarification_draft": clarification_draft(review), "revision_of": quote.id,
        })


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
    require_permission(user, "edit")

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
    require_permission(user, "preview_import")
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
    require_permission(user, "import" if action == "confirm" else "preview_import")
    if action not in {"preview", "confirm"}:
        raise HTTPException(status_code=400, detail="Invalid import action")

    try:
        file_bytes = await read_upload(file)
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
        form = await request.form()
        mapping.update({field: form.get(field + "_col", column) for field, column in OPTIONAL_MAPPING.items()})
        if action == "confirm":
            query_db = db.SessionLocal()
            try:
                result = await run_in_threadpool(confirm_import, query_db, db, file_bytes, mapping, user_id=user.id)
            finally:
                query_db.close()
            if result["status"] == "error":
                return templates.TemplateResponse(
                    "import_quotes.html",
                    {"request": request, "user": user, "result": result, "error": "Invalid rows must be fixed before import."},
                    status_code=400,
                )
        else:
            result = await run_in_threadpool(preview_import, file_bytes, mapping)
    except HTTPException:
        raise
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
