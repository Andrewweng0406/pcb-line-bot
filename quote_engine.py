# quote_engine.py

BASE_PRICE_TABLE = {
    2: {"engineering_fee": 15000, "material_price": 15},
    4: {"engineering_fee": 20000, "material_price": 20},
    6: {"engineering_fee": 25000, "material_price": 25},
    8: {"engineering_fee": 30000, "material_price": 30},
    10: {"engineering_fee": 35000, "material_price": 35},
    12: {"engineering_fee": 40000, "material_price": 40},
    14: {"engineering_fee": 45000, "material_price": 45},
    16: {"engineering_fee": 50000, "material_price": 50},
    18: {"engineering_fee": 55000, "material_price": 55},
    20: {"engineering_fee": 70000, "material_price": 60},
    22: {"engineering_fee": 80000, "material_price": 65},
    24: {"engineering_fee": 90000, "material_price": 70},
    26: {"engineering_fee": 100000, "material_price": 75},
    28: {"engineering_fee": 110000, "material_price": 80},
    30: {"engineering_fee": 120000, "material_price": 90},
    32: {"engineering_fee": 140000, "material_price": 100},
    34: {"engineering_fee": 160000, "material_price": 110},
    36: {"engineering_fee": 180000, "material_price": 120},
    38: {"engineering_fee": 200000, "material_price": 130},
    40: {"engineering_fee": 220000, "material_price": 150},
    42: {"engineering_fee": 240000, "material_price": 170},
    44: {"engineering_fee": 260000, "material_price": 190},
    46: {"engineering_fee": 280000, "material_price": 210},
    48: {"engineering_fee": 300000, "material_price": 230},
    50: {"engineering_fee": 350000, "material_price": 250},
    52: {"engineering_fee": 400000, "material_price": 270},
    54: {"engineering_fee": 450000, "material_price": 290},
    56: {"engineering_fee": 500000, "material_price": 310},
    58: {"engineering_fee": 550000, "material_price": 330},
}


DELIVERY_RULES = [
    {"max_days": 2, "multiplier": 2.0, "label": "超急件"},
    {"max_days": 3, "multiplier": 1.7, "label": "急件"},
    {"max_days": 5, "multiplier": 1.4, "label": "快件"},
    {"max_days": 7, "multiplier": 1.2, "label": "一般急件"},
    {"max_days": 14, "multiplier": 1.0, "label": "正常交期"},
]


def get_enig_fee(enig_thickness_uinch=None):
    if enig_thickness_uinch is None:
        return 3000

    enig_thickness_uinch = float(enig_thickness_uinch)

    if enig_thickness_uinch <= 3:
        return 3000
    elif enig_thickness_uinch <= 5:
        return 10000
    elif enig_thickness_uinch <= 10:
        return 20000
    elif enig_thickness_uinch <= 30:
        return 50000
    else:
        return 80000


def get_thickness_extra(thickness):
    if thickness is None:
        return 0

    thickness = float(thickness)

    if 3.6 <= thickness <= 4.5:
        return 5
    elif 4.6 <= thickness <= 5.3:
        return 10
    elif 5.4 <= thickness <= 6.5:
        return 15
    elif thickness > 6.5:
        return 20

    return 0


def get_quantity_discount(qty):
    if qty <= 1:
        return 1.0
    elif qty == 2:
        return 0.9
    elif qty <= 5:
        return 0.85
    elif qty <= 10:
        return 0.8
    else:
        return 0.75


def get_delivery_multiplier(delivery_days):
    if delivery_days is None:
        return 1.0, "未提供交期"

    delivery_days = int(delivery_days)

    for rule in DELIVERY_RULES:
        if delivery_days <= rule["max_days"]:
            return rule["multiplier"], rule["label"]

    return 1.0, "一般交期"


def calculate_quote(data):
    explanations = []
    suggest_missing = []
    follow_up_questions = []
    cam_warnings = []
    difficulty_score = 0

    required_fields = ["layer", "qty"]

    missing = []

    for field in required_fields:
        if data.get(field) is None:
            missing.append(field)

    if missing:
        return {
            "status": "missing_info",
            "missing_fields": missing,
            "message": "缺少必要規格，請補齊後再報價。"
        }

    layer = int(data["layer"])
    qty = int(data["qty"])
    issue_ratio = float(data.get("issue_ratio") or 1)
    production_qty = qty * issue_ratio

    if issue_ratio > 1:
        explanations.append(
            f"投料率：{issue_ratio} ({int(production_qty)}片投料)"
        )

    if layer not in BASE_PRICE_TABLE:
        return {
            "status": "price_not_found",
            "message": f"找不到 {layer}L 的基本報價。"
        }

    base = BASE_PRICE_TABLE[layer]

    engineering_fee = base["engineering_fee"]
    material_price = base["material_price"]

    # CAM Warning: Layer
    if layer >= 20:
        difficulty_score += 2
        cam_warnings.append("⚠️ 高層板，高壓合難度")

    if layer >= 40:
        difficulty_score += 3
        cam_warnings.append("⚠️ 超高層板，良率風險高")

    # CAM Warning: Material
    material = str(data.get("material", "")).upper()

    if "MEGTRON" in material:
        difficulty_score += 2
        cam_warnings.append("⚠️ 高速材料，需注意阻抗控制")

    # Area
    if data.get("length_mm") is not None and data.get("width_mm") is not None:
        length_mm = float(data["length_mm"])
        width_mm = float(data["width_mm"])

        length_inch = length_mm / 25.4
        width_inch = width_mm / 25.4
        area_inch = length_inch * width_inch

    elif data.get("area_inch") is not None:
        length_mm = None
        width_mm = None
        length_inch = None
        width_inch = None
        area_inch = float(data["area_inch"])

    else:
        return {
            "status": "missing_info",
            "missing_fields": ["length_mm/width_mm or area_inch"],
            "message": "缺少尺寸或面積，請補長寬或 Area。"
        }

    # 板厚加價
    thickness_extra = get_thickness_extra(data.get("thickness"))

    if thickness_extra > 0:
        explanations.append(
            f"板厚加價：+{thickness_extra} / sq.inch"
        )

    material_price += thickness_extra

    # Pitch 加價
    pitch = data.get("pitch")

    if pitch is not None:
        pitch = float(pitch)

        if 0.4 <= pitch <= 0.45:
            explanations.append(
                "Pitch 0.4~0.45mm：工程費×1.5、板材費×1.5"
            )

            difficulty_score += 2
            cam_warnings.append("⚠️ Fine Pitch 設計")

            engineering_fee *= 1.5
            material_price *= 1.5

        elif pitch <= 0.35:
            explanations.append(
                "Pitch <=0.35mm：工程費×2、板材費×2"
            )

            difficulty_score += 4
            cam_warnings.append("⚠️ 超細 Pitch，高難度製程")

            engineering_fee *= 2
            material_price *= 2

    # 阻抗加價
    if data.get("impedance"):
        explanations.append("阻抗：板材單價 ×1.5")
        material_price *= 1.5

    material_cost = area_inch * material_price * production_qty

    process_cost = 0

    if data.get("enig"):
        enig_fee = get_enig_fee(data.get("enig_thickness_uinch"))
        process_cost += enig_fee

        explanations.append(
            f"ENIG 表面處理：鍍金加價 {enig_fee}"
        )

    if data.get("vip"):
        process_cost += 6000
        difficulty_score += 1
        cam_warnings.append("⚠️ VIP 製程，需確認塞孔要求")

    if data.get("back_drill"):
        explanations.append("Back Drill 加工")
        process_cost += 5000

        difficulty_score += 2
        cam_warnings.append("⚠️ Back Drill 製程，需注意對位精度")

    if data.get("bvh"):
        explanations.append("BVH 加工")
        process_cost += 5000

        difficulty_score += 2
        cam_warnings.append("⚠️ BVH 製程，良率風險提高")

    if difficulty_score >= 8:
        difficulty_level = "EXTREME"
    elif difficulty_score >= 5:
        difficulty_level = "HIGH"
    elif difficulty_score >= 3:
        difficulty_level = "MEDIUM"
    else:
        difficulty_level = "LOW"

    subtotal = engineering_fee + material_cost + process_cost

    delivery_multiplier, delivery_label = get_delivery_multiplier(
        data.get("delivery_days")
    )

    if delivery_multiplier > 1:
        explanations.append(
            f"{delivery_label}：{data.get('delivery_days')}天，價格 ×{delivery_multiplier}"
        )

    discount = get_quantity_discount(qty)

    total = subtotal * discount * delivery_multiplier

    unit_price = total / qty

    if data.get("thickness") is None:
        suggest_missing.append("Thickness")
        follow_up_questions.append("請問板厚是多少 mm？")

    if data.get("copper_weight") is None:
        suggest_missing.append("Copper Weight")
        follow_up_questions.append("請問銅厚是多少 oz？")

    if not data.get("enig") and data.get("surface_finish") is None:
        suggest_missing.append("Surface Finish")
        follow_up_questions.append("請問表面處理是什麼？例如 ENIG / OSP")

    if data.get("delivery_days") is None:
        suggest_missing.append("Delivery Time")
        follow_up_questions.append("請問交期需要幾天？")

    return {
        "status": "success",
        "suggest_missing": suggest_missing,
        "follow_up_questions": follow_up_questions,

        "length_inch": round(length_inch, 2) if length_inch is not None else None,
        "width_inch": round(width_inch, 2) if width_inch is not None else None,
        "area_inch": round(area_inch, 2),

        "base_engineering_fee": base["engineering_fee"],
        "engineering_fee": round(engineering_fee, 2),

        "base_material_price": base["material_price"],
        "material_price": round(material_price, 2),

        "qty": qty,
        "issue_ratio": issue_ratio,
        "production_qty": production_qty,

        "material_cost": round(material_cost, 2),
        "process_cost": round(process_cost, 2),
        "subtotal": round(subtotal, 2),

        "discount": discount,

        "delivery_days": data.get("delivery_days"),
        "delivery_multiplier": delivery_multiplier,
        "delivery_label": delivery_label,

        "total": round(total, 2),
        "unit_price": round(unit_price, 2),

        "explanations": explanations,

        "difficulty_score": difficulty_score,
        "difficulty_level": difficulty_level,
        "cam_warnings": cam_warnings,
    }