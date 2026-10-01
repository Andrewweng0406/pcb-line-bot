# quote_engine_v2.py
# Version that fully matches the customer's quotation rules

# ============================================================================
# Base fee tables (based on the customer's Excel file)
# ============================================================================

# Base setup fee by layer count
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

# Board charge by layer count (NT$ / in²)
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
# Extra fee functions
# ============================================================================

def get_enig_fee(enig_thickness_uinch=None):
    """Get the ENIG plating fee."""
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
    """Get the trace-to-hole surcharge multiplier."""
    if trace_to_hole_mil is None:
        return 1.0, "Trace-to-hole spacing not provided"

    mil = float(trace_to_hole_mil)

    if mil >= 5:
        return 1.0, "5mil or above (+0%)"
    elif mil >= 4.3:
        return 1.2, "4.3-5mil (+20%)"
    else:
        return 1.45, "3-4.2mil (+45%)"


def get_pitch_multiplier(pitch_mm=None):
    """Get the pitch surcharge multiplier."""
    if pitch_mm is None:
        return 1.0, "Pitch not provided"

    pitch = float(pitch_mm)

    if pitch <= 0.35:
        return 1.45, "≤0.35mm (×1.45)"
    elif pitch <= 0.46:
        return 1.45, "0.4-0.46mm (×1.45)"
    elif pitch <= 0.55:
        return 1.2, "0.47-0.55mm (×1.2)"
    else:
        return 1.0, "0.55mm or above (+0%)"


def get_flatness_multiplier(flatness_unit=None):
    """Get the flatness surcharge multiplier."""
    if flatness_unit is None:
        return 1.0, "Flatness not provided"

    # flatness_unit: "5/1000" or "2/1000"
    if "2" in str(flatness_unit):
        return 1.4, "2/1000 (+40%)"
    elif "5" in str(flatness_unit):
        return 1.2, "5/1000 (+20%)"
    else:
        return 1.0, "Standard flatness"


def get_aspect_ratio_multiplier(aspect_ratio=None):
    """Get the aspect ratio surcharge multiplier."""
    if aspect_ratio is None:
        return 1.0, "Aspect ratio not calculated"

    ar = float(aspect_ratio)

    if ar <= 20:
        return 1.2, "12-20 (+20%)"
    elif ar <= 30:
        return 1.4, "21-30 (+40%)"
    elif ar <= 40:
        return 1.6, "31-40 (+60%)"
    else:
        return 1.0, "Aspect ratio > 40"


def get_thickness_multiplier(thickness_mm=None):
    """Get the thickness surcharge multiplier."""
    if thickness_mm is None:
        return 1.0, "Board thickness not provided"

    thickness = float(thickness_mm)

    if 3.6 <= thickness <= 4.5:
        return 1.2, "3.6-4.5mm (+20%)"
    elif 4.6 <= thickness <= 5.3:
        return 1.3, "4.6-5.3mm (+30%)"
    elif 5.4 <= thickness <= 6.5:
        return 1.4, "5.4-6.5mm (+40%)"
    else:
        return 1.0, "Standard board thickness (1.6mm)"


def get_aoi_fee(internal_layer_count=None):
    """Get the inner-layer AOI fee (NT$ per layer)."""
    if internal_layer_count is None or internal_layer_count <= 0:
        return 0

    return 600 * internal_layer_count


def get_press_multiplier(press_count=None):
    """Get the lamination surcharge multiplier."""
    if press_count is None:
        return 1.0, "Single lamination"

    if press_count == 2:
        return 2.25, "Double lamination (+125%)"
    elif press_count == 3:
        return 3.5, "Triple lamination (+250%)"
    else:
        return 1.0, "Single lamination"


def get_quantity_discount(qty):
    """Get the quantity discount."""
    qty = int(qty)
    if qty >= 2:
        return 0.9  # 10% discount for re-orders
    else:
        return 1.0


def get_delivery_days_by_layer(layer):
    """Determine the fastest delivery lead time by layer count."""
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
    """Get the delivery lead-time surcharge multiplier."""
    if requested_days is None:
        return 1.0, "Standard lead time"

    requested_days = int(requested_days)

    if requested_days < actual_min_days:
        # Requested lead time is faster than the minimum; return the fastest available.
        return 1.0, f"Expedited lead time {actual_min_days} days"

    elif requested_days == actual_min_days:
        return 1.0, f"Standard lead time {actual_min_days} days"
    else:
        # Longer lead times are allowed, but no discount is defined in the customer's table.
        return 1.0, f"Relaxed lead time {requested_days} days"


# ============================================================================
# Main calculation function
# ============================================================================

def calculate_quote(data):
    """
    Complete quote calculation that follows the customer's Excel rules.

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
    # 1. Validate required fields
    # ========================================================================
    required = ["layer", "qty"]
    missing = [f for f in required if data.get(f) is None]

    if missing:
        return {
            "status": "error",
            "message": f"Missing required fields: {', '.join(missing)}",
            "missing_fields": missing,
        }

    layer = int(data["layer"])
    qty = int(data["qty"])

    if layer not in SETUP_FEE_TABLE:
        return {
            "status": "error",
            "message": f"{layer}L is not supported. Supported range: 2-50L",
        }

    # ========================================================================
    # 2. Issue ratio calculation
    # ========================================================================
    issue_ratio = float(data.get("issue_ratio") or 1.0)
    production_qty = qty * issue_ratio

    if issue_ratio > 1:
        explanations.append(f"Issue ratio: {issue_ratio} (production {int(production_qty)} pcs)")

    # ========================================================================
    # 3. Size and area calculation
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
            "message": "Missing size information: provide length/width (mm) or area (in²)",
        }

    # ========================================================================
    # 4. Base setup fee
    # ========================================================================
    setup_fee = SETUP_FEE_TABLE[layer]
    explanations.append(f"Base setup fee ({layer}L): {setup_fee:,}")

    # ========================================================================
    # 5. Board charge (unit area cost)
    # ========================================================================
    board_charge_per_inch = BOARD_CHARGE_TABLE.get(layer, 35)
    board_charge_total = area_inch * board_charge_per_inch * production_qty

    explanations.append(
        f"Board Charge: {board_charge_per_inch} NT$/in² × {area_inch:.2f} in² × {production_qty:.0f} pcs = {board_charge_total:,.0f}"
    )

    # ========================================================================
    # 6. Specification surcharge multipliers applied to setup and material fees
    # ========================================================================
    multiplier = 1.0
    details = []

    # Pitch surcharge
    pitch_mult, pitch_desc = get_pitch_multiplier(data.get("pitch_mm"))
    if pitch_mult > 1:
        multiplier *= pitch_mult
        details.append(pitch_desc)
        warnings.append(f"⚠️ {pitch_desc}")

    # Trace-to-hole surcharge
    tth_mult, tth_desc = get_trace_to_hole_multiplier(data.get("trace_to_hole_mil"))
    if tth_mult > 1:
        multiplier *= tth_mult
        details.append(tth_desc)
        warnings.append(f"⚠️ {tth_desc}")

    # Flatness surcharge
    flat_mult, flat_desc = get_flatness_multiplier(data.get("flatness"))
    if flat_mult > 1:
        multiplier *= flat_mult
        details.append(flat_desc)

    # Aspect ratio surcharge
    ar = data.get("aspect_ratio")
    if ar is None and data.get("hole_size_mil") and data.get("thickness_mm"):
        # Automatically calculate aspect ratio: board thickness / hole diameter
        hole_mm = float(data["hole_size_mil"]) * 0.0254
        ar = float(data["thickness_mm"]) / hole_mm

    ar_mult, ar_desc = get_aspect_ratio_multiplier(ar)
    if ar_mult > 1:
        multiplier *= ar_mult
        details.append(ar_desc)
        warnings.append(f"⚠️ {ar_desc}")

    # Thickness surcharge
    thick_mult, thick_desc = get_thickness_multiplier(data.get("thickness_mm"))
    if thick_mult > 1:
        multiplier *= thick_mult
        details.append(thick_desc)

    if details:
        explanations.append(f"Specification surcharge multiplier: {' × '.join(str(m) for m in [p for p in [pitch_mult, tth_mult, flat_mult, ar_mult, thick_mult] if p > 1])} = ×{multiplier:.2f}")

    # ========================================================================
    # 7. Material cost (board charge + specification surcharges)
    # ========================================================================
    material_cost = board_charge_total * multiplier

    # ========================================================================
    # 8. Extra processing fees
    # ========================================================================
    extra_fee = 0

    # ENIG plating
    if data.get("enig"):
        enig_fee = get_enig_fee(data.get("enig_thickness_uinch"))
        extra_fee += enig_fee
        explanations.append(f"ENIG plating: {enig_fee:,}")

    # Via-in-pad resin plugging (VIP)
    if data.get("vip"):
        extra_fee += 5000
        explanations.append("Resin plugged via (VIP): 5,000")
        warnings.append("⚠️ VIP process; confirm via plugging requirements")

    # Back drilling
    if data.get("back_drill"):
        back_drill_fee = int(data.get("back_drill_fee", 5000))
        extra_fee += back_drill_fee
        explanations.append(f"Back Drill: {back_drill_fee:,}")
        warnings.append("⚠️ Back Drill process; verify registration accuracy")

    # Inner-layer AOI
    internal_layers = int(data.get("internal_layers", 0))
    if internal_layers > 0:
        aoi_fee = get_aoi_fee(internal_layers)
        extra_fee += aoi_fee
        explanations.append(f"Inner-layer AOI ({internal_layers} layers): {aoi_fee:,}")

    # ========================================================================
    # 9. Lamination surcharge
    # ========================================================================
    press_mult, press_desc = get_press_multiplier(data.get("press_count"))
    if press_mult > 1:
        extra_fee = extra_fee * press_mult + setup_fee * (press_mult - 1)
        explanations.append(f"Lamination surcharge: {press_desc}")
        warnings.append(f"⚠️ {press_desc}")

    # ========================================================================
    # 10. Subtotal (setup fee + material cost + processing fees)
    # ========================================================================
    subtotal = setup_fee + material_cost + extra_fee

    # ========================================================================
    # 11. Quantity discount
    # ========================================================================
    discount = get_quantity_discount(qty)
    if discount < 1:
        explanations.append(f"Quantity discount: ×{discount} (Re-Order)")

    # ========================================================================
    # 12. Delivery lead-time surcharge
    # ========================================================================
    min_delivery_days = get_delivery_days_by_layer(layer)
    delivery_mult, delivery_desc = get_delivery_multiplier(
        data.get("delivery_days"), min_delivery_days
    )

    # ========================================================================
    # 13. Final quote
    # ========================================================================
    total = subtotal * discount * delivery_mult
    unit_price = total / qty

    # ========================================================================
    # 14. Follow-up questions
    # ========================================================================
    if data.get("pitch_mm") is None:
        follow_up.append("What is the pitch in mm?")

    if data.get("trace_to_hole_mil") is None:
        follow_up.append("What is the trace-to-hole spacing in mil?")

    if data.get("flatness") is None:
        follow_up.append("What is the flatness requirement?")

    if data.get("thickness_mm") is None:
        follow_up.append("What is the board thickness in mm?")

    if data.get("enig") is None and not data.get("vip"):
        follow_up.append("Is the surface finish ENIG or another finish?")

    # ========================================================================
    # 15. Return result
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
