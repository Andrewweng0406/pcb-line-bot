# quote_engine_v2.py
# 完整符合客戶報價規則的版本

# ============================================================================
# 基礎費用表 (根據客戶 Excel)
# ============================================================================

# 按層數的基礎工程費 (Setup Fee)
SETUP_FEE_TABLE = {
    2: 10000,
    4: 20000,
    6: 25000,
    8: 30000,
    10: 35000,
    12: 40000,
    14: 45000,
    16: 50000,
    18: 55000,
    20: 70000,
    22: 80000,
    24: 90000,
    26: 100000,
    28: 110000,
    30: 120000,
    32: 140000,
    34: 160000,
    36: 180000,
    38: 200000,
    40: 220000,
    42: 240000,
    44: 260000,
    46: 280000,
    48: 300000,
    50: 350000,
}

# 按層數的 Board Charge (NT$ / in²)
BOARD_CHARGE_TABLE = {
    2: 4,
    4: 6,
    6: 9,
    8: 11,
    10: 15,
    12: 20,
    14: 25,
    16: 35.0,
    18: 40,
    20: 45,
    22: 50,
}

# ============================================================================
# 額外費用函數
# ============================================================================

def get_enig_fee(enig_thickness_uinch=None):
    """獲得 ENIG 鍍金費用"""
    if enig_thickness_uinch is None:
        return 0

    thickness = float(enig_thickness_uinch)

    if thickness <= 5:
        return 3000
    elif thickness <= 10:
        return 6000
    elif thickness <= 30:
        return 12000
    else:
        return 18000


def get_trace_to_hole_multiplier(trace_to_hole_mil=None):
    """孔到線距加費倍數 (Trace to Hole)"""
    if trace_to_hole_mil is None:
        return 1.0, "未提供孔到線距"

    mil = float(trace_to_hole_mil)

    if mil >= 5:
        return 1.0, "5mil 以上 (+0%)"
    elif mil >= 4.3:
        return 1.2, "4.3-5mil (+20%)"
    else:
        return 1.45, "3-4.2mil (+45%)"


def get_pitch_multiplier(pitch_mm=None):
    """Pitch 加費倍數"""
    if pitch_mm is None:
        return 1.0, "未提供 Pitch"

    pitch = float(pitch_mm)

    if pitch <= 0.35:
        return 1.45, "≤0.35mm (×1.45)"
    elif pitch <= 0.46:
        return 1.45, "0.4-0.46mm (×1.45)"
    elif pitch <= 0.55:
        return 1.2, "0.47-0.55mm (×1.2)"
    else:
        return 1.0, "0.55mm 以上 (+0%)"


def get_flatness_multiplier(flatness_unit=None):
    """平坦度加費倍數 (Flatness)"""
    if flatness_unit is None:
        return 1.0, "未提供平坦度"

    # flatness_unit: "5/1000" 或 "2/1000"
    if "2" in str(flatness_unit):
        return 1.4, "2/1000 (+40%)"
    elif "5" in str(flatness_unit):
        return 1.2, "5/1000 (+20%)"
    else:
        return 1.0, "標準平坦度"


def get_aspect_ratio_multiplier(aspect_ratio=None):
    """縱深比加費倍數 (Aspect Ratio)"""
    if aspect_ratio is None:
        return 1.0, "未計算縱深比"

    ar = float(aspect_ratio)

    if ar <= 20:
        return 1.2, "12-20 (+20%)"
    elif ar <= 30:
        return 1.4, "21-30 (+40%)"
    elif ar <= 40:
        return 1.6, "31-40 (+60%)"
    else:
        return 1.0, "縱深比 > 40"


def get_thickness_multiplier(thickness_mm=None):
    """板厚加費倍數 (Thickness)"""
    if thickness_mm is None:
        return 1.0, "未提供板厚"

    thickness = float(thickness_mm)

    if 3.6 <= thickness <= 4.5:
        return 1.2, "3.6-4.5mm (+20%)"
    elif 4.6 <= thickness <= 5.3:
        return 1.3, "4.6-5.3mm (+30%)"
    elif 5.4 <= thickness <= 6.5:
        return 1.4, "5.4-6.5mm (+40%)"
    else:
        return 1.0, "標準板厚 (1.6mm)"


def get_aoi_fee(internal_layer_count=None):
    """內層 AOI 費用 (NT$ per layer)"""
    if internal_layer_count is None or internal_layer_count <= 0:
        return 0

    return 600 * internal_layer_count


def get_press_multiplier(press_count=None):
    """壓合加費倍數 (Press Count)"""
    if press_count is None:
        return 1.0, "單次壓合"

    if press_count == 2:
        return 2.25, "二次壓合 (+125%)"
    elif press_count == 3:
        return 3.5, "三次壓合 (+250%)"
    else:
        return 1.0, "單次壓合"


def get_quantity_discount(qty):
    """數量折扣"""
    qty = int(qty)
    if qty >= 2:
        return 0.9  # Re-Order 打 9 折
    else:
        return 1.0


def get_delivery_days_by_layer(layer):
    """按層數決定最快交期"""
    layer = int(layer)
    if layer <= 4:
        return 5
    elif layer == 6:
        return 6
    elif layer <= 10:
        return 7
    elif layer <= 14:
        return 8
    else:
        return 10


def get_delivery_multiplier(requested_days, actual_min_days):
    """交貨天數加費倍數"""
    if requested_days is None:
        return 1.0, "標準交期"

    requested_days = int(requested_days)

    if requested_days < actual_min_days:
        # 比最快交期還快，不可能，返回最快的
        return 1.0, f"加急交期 {actual_min_days} 天"

    elif requested_days == actual_min_days:
        return 1.0, f"標準交期 {actual_min_days} 天"
    else:
        # 可以放寬交期，暫時不給折扣（客戶表中沒有定義）
        return 1.0, f"放寬交期 {requested_days} 天"


# ============================================================================
# 主計算函數
# ============================================================================

def calculate_quote(data):
    """
    完整的報價計算，符合客戶 Excel 規則

    Input: {
        'layer': 6,
        'qty': 9,
        'issue_ratio': 3.0,
        'length_mm': 100,
        'width_mm': 100,
        'thickness_mm': 1.6,
        'pitch_mm': 0.4,
        'trace_to_hole_mil': None,
        'aspect_ratio': None,
        'flatness': None,
        'enig': True,
        'enig_thickness_uinch': 10,
        'vip': False,
        'back_drill': False,
        'press_count': 1,
        'internal_layers': 4,
        'delivery_days': 7,
    }
    """

    explanations = []
    warnings = []
    follow_up = []

    # ========================================================================
    # 1. 驗證必需欄位
    # ========================================================================
    required = ["layer", "qty"]
    missing = [f for f in required if data.get(f) is None]

    if missing:
        return {
            "status": "error",
            "message": f"缺少必要欄位: {', '.join(missing)}",
            "missing_fields": missing,
        }

    layer = int(data["layer"])
    qty = int(data["qty"])

    if layer not in SETUP_FEE_TABLE:
        return {
            "status": "error",
            "message": f"{layer}L 暫不支持，目前支持 2-50L",
        }

    # ========================================================================
    # 2. 投料率計算
    # ========================================================================
    issue_ratio = float(data.get("issue_ratio") or 1.0)
    production_qty = qty * issue_ratio

    if issue_ratio > 1:
        explanations.append(f"投料率: {issue_ratio} (投料 {int(production_qty)} 片)")

    # ========================================================================
    # 3. 尺寸與面積計算
    # ========================================================================
    if data.get("length_mm") and data.get("width_mm"):
        length_mm = float(data["length_mm"])
        width_mm = float(data["width_mm"])
        area_inch = (length_mm / 25.4) * (width_mm / 25.4)
    elif data.get("area_inch"):
        area_inch = float(data["area_inch"])
        length_mm = None
        width_mm = None
    else:
        return {
            "status": "error",
            "message": "缺少尺寸資訊：請提供長寬 (mm) 或面積 (in²)",
        }

    # ========================================================================
    # 4. 基礎工程費 (Setup Fee)
    # ========================================================================
    setup_fee = SETUP_FEE_TABLE[layer]
    explanations.append(f"基礎工程費 ({layer}L): {setup_fee:,}")

    # ========================================================================
    # 5. Board Charge (單位面積費用)
    # ========================================================================
    board_charge_per_inch = BOARD_CHARGE_TABLE.get(layer, 35)
    board_charge_total = area_inch * board_charge_per_inch * production_qty

    explanations.append(
        f"Board Charge: {board_charge_per_inch} NT$/in² × {area_inch:.2f} in² × {production_qty:.0f} 片 = {board_charge_total:,.0f}"
    )

    # ========================================================================
    # 6. 規格加費倍數（應用於工程費和材料費）
    # ========================================================================
    multiplier = 1.0
    details = []

    # Pitch 加費
    pitch_mult, pitch_desc = get_pitch_multiplier(data.get("pitch_mm"))
    if pitch_mult > 1:
        multiplier *= pitch_mult
        details.append(pitch_desc)
        warnings.append(f"⚠️ {pitch_desc}")

    # 孔到線距加費
    tth_mult, tth_desc = get_trace_to_hole_multiplier(data.get("trace_to_hole_mil"))
    if tth_mult > 1:
        multiplier *= tth_mult
        details.append(tth_desc)
        warnings.append(f"⚠️ {tth_desc}")

    # 平坦度加費
    flat_mult, flat_desc = get_flatness_multiplier(data.get("flatness"))
    if flat_mult > 1:
        multiplier *= flat_mult
        details.append(flat_desc)

    # 縱深比加費
    ar = data.get("aspect_ratio")
    if ar is None and data.get("hole_size_mil") and data.get("thickness_mm"):
        # 自動計算縱深比: 板厚 / 孔徑
        hole_mm = float(data["hole_size_mil"]) * 0.0254
        ar = float(data["thickness_mm"]) / hole_mm

    ar_mult, ar_desc = get_aspect_ratio_multiplier(ar)
    if ar_mult > 1:
        multiplier *= ar_mult
        details.append(ar_desc)
        warnings.append(f"⚠️ {ar_desc}")

    # 板厚加費
    thick_mult, thick_desc = get_thickness_multiplier(data.get("thickness_mm"))
    if thick_mult > 1:
        multiplier *= thick_mult
        details.append(thick_desc)

    if details:
        explanations.append(f"規格加費倍數: {' × '.join(str(m) for m in [p for p in [pitch_mult, tth_mult, flat_mult, ar_mult, thick_mult] if p > 1])} = ×{multiplier:.2f}")

    # ========================================================================
    # 7. 材料費（Board Charge + 規格加費）
    # ========================================================================
    material_cost = board_charge_total * multiplier

    # ========================================================================
    # 8. 額外加工費用
    # ========================================================================
    extra_fee = 0

    # ENIG 鍍金
    if data.get("enig"):
        enig_fee = get_enig_fee(data.get("enig_thickness_uinch"))
        extra_fee += enig_fee
        explanations.append(f"ENIG 鍍金: {enig_fee:,}")

    # 樹脂塞孔 (VIP)
    if data.get("vip"):
        extra_fee += 5000
        explanations.append("樹脂塞孔 (VIP): 5,000")
        warnings.append("⚠️ VIP 製程，需確認塞孔要求")

    # 背鑽
    if data.get("back_drill"):
        back_drill_fee = int(data.get("back_drill_fee", 5000))
        extra_fee += back_drill_fee
        explanations.append(f"背鑽: {back_drill_fee:,}")
        warnings.append("⚠️ 背鑽製程，需注意對位精度")

    # 內層 AOI
    internal_layers = int(data.get("internal_layers", 0))
    if internal_layers > 0:
        aoi_fee = get_aoi_fee(internal_layers)
        extra_fee += aoi_fee
        explanations.append(f"內層 AOI ({internal_layers} 層): {aoi_fee:,}")

    # ========================================================================
    # 9. 壓合加費
    # ========================================================================
    press_mult, press_desc = get_press_multiplier(data.get("press_count"))
    if press_mult > 1:
        extra_fee = extra_fee * press_mult + setup_fee * (press_mult - 1)
        explanations.append(f"壓合加費: {press_desc}")
        warnings.append(f"⚠️ {press_desc}")

    # ========================================================================
    # 10. 小計（工程費 + 材料費 + 加工費）
    # ========================================================================
    subtotal = setup_fee + material_cost + extra_fee

    # ========================================================================
    # 11. 數量折扣
    # ========================================================================
    discount = get_quantity_discount(qty)
    if discount < 1:
        explanations.append(f"數量折扣: ×{discount} (Re-Order)")

    # ========================================================================
    # 12. 交貨天數加費
    # ========================================================================
    min_delivery_days = get_delivery_days_by_layer(layer)
    delivery_mult, delivery_desc = get_delivery_multiplier(
        data.get("delivery_days"), min_delivery_days
    )

    # ========================================================================
    # 13. 最終報價
    # ========================================================================
    total = subtotal * discount * delivery_mult
    unit_price = total / qty

    # ========================================================================
    # 14. 後續詢問
    # ========================================================================
    if data.get("pitch_mm") is None:
        follow_up.append("請問 Pitch 是多少 mm？")

    if data.get("trace_to_hole_mil") is None:
        follow_up.append("請問孔到線距是多少 mil？")

    if data.get("flatness") is None:
        follow_up.append("請問平坦度規格是多少？")

    if data.get("thickness_mm") is None:
        follow_up.append("請問板厚是多少 mm？")

    if data.get("enig") is None and not data.get("vip"):
        follow_up.append("請問表面處理是 ENIG 還是其他？")

    # ========================================================================
    # 15. 返回結果
    # ========================================================================
    return {
        "status": "success",
        "layer": layer,
        "qty": qty,
        "issue_ratio": issue_ratio,
        "production_qty": production_qty,
        "area_inch": round(area_inch, 2),
        "setup_fee": round(setup_fee, 2),
        "board_charge_per_inch": board_charge_per_inch,
        "board_charge_total": round(board_charge_total, 2),
        "specification_multiplier": round(multiplier, 2),
        "material_cost": round(material_cost, 2),
        "extra_fee": round(extra_fee, 2),
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "delivery_multiplier": delivery_mult,
        "min_delivery_days": min_delivery_days,
        "total": round(total, 2),
        "unit_price": round(unit_price, 2),
        "explanations": explanations,
        "warnings": warnings,
        "follow_up_questions": follow_up,
    }
