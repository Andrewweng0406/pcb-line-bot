import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=30.0, max_retries=1)


def parse_pcb_text(text):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    prompt = """
你是 PCB 報價助理。
請從客戶文字中抽取 PCB 規格或修改指令。

只回傳 JSON，不要 markdown，不要解釋。

JSON 格式：
{
  "layer": null,
  "material": null,
  "length_mm": null,
  "width_mm": null,
  "area_inch": null,
  "qty": null,
  "enig": null,
  "enig_thickness_uinch": null,
  "vip": null,
  "impedance": null,
  "back_drill": null,
  "bvh": null,
  "is_reorder": null,
  "hard_gold": null,
  "countersunk": null,
  "counterbored": null,
  "inspection_report_required": null,
  "thickness": null,
  "pitch_mm": null,
  "copper_weight": null,
  "copper_outer_oz": null,
  "copper_inner_oz": null,
  "surface_finish": null,
  "min_hole_mil": null,
  "line_space_mil": null,
  "hole_land_mil": null,
  "aspect_ratio": null,
  "warpage_mil_per_inch": null,
  "legend_color": null,
  "solder_mask_color": null,
  "special_requirements": null,
  "issue_ratio": null,
  "delivery_days": null
}

規則：
如果使用者說「不要鍍金」「取消鍍金」「不要 ENIG」，enig = false, enig_thickness_uinch = null
如果使用者說「要鍍金」「ENIG」，enig = true
如果使用者說「鍍金改 5u」「Gold 5u」「ENIG 5u」「化金 5u」，enig = true, enig_thickness_uinch = 5

材料請保留使用者原文，例如 FR4_HTG、FR4-HTG、M6 FR4-HTG 不要簡化成 FR4。

如果使用者說「Hard Gold 20μ」「Gold 20μ」「20um」「20μm」，enig = true。
如果單位是 u" 或 uinch，直接當成 enig_thickness_uinch。
如果單位是 um、μm、μ，請換算成 uinch：1um = 39.37uinch。
例如 0.635um = 25u"，20um = 787.4u"。

如果使用者說「不要 BVH」「取消 BVH」，bvh = false
如果使用者說「不要 Back Drill」「取消 Back Drill」，back_drill = false
如果使用者說「不要 VIP」「取消 VIP」，vip = false

如果使用者說「改成 4 pcs」「數量改 4」，qty = 4
如果使用者說「投料率改 2」「4片產出2片」，issue_ratio = 2
如果使用者說「Re-order」「復投」「舊案重下」，is_reorder = true
如果使用者說「New Version」「新版」「新案」，is_reorder = false

沒有提到的欄位保持 null，不要自己填 false。

如果使用者說「7天」「交期7天」「需要7天」，delivery_days = 7
如果使用者說「3天急件」「3天」，delivery_days = 3
如果沒有提到交期，delivery_days = null

如果使用者說「板厚 5mm」「厚度 5mm」「Thickness 5mm」，thickness = 5
如果使用者說「Pitch 0.5mm」「最小 Pitch 0.5」，pitch_mm = 0.5

如果使用者說「銅厚 1oz」「Copper 1oz」「1 oz」，copper_weight = "1oz"
如果使用者說「外層 1oz 內層 1oz」「External 1 oz Inner 1 oz」，copper_outer_oz = 1, copper_inner_oz = 1
如果使用者說「half oz & one oz」但不能分辨內外層，copper_weight = "half oz & one oz"

如果使用者說「交期 7天」「7天」「Lead time 7 days」，delivery_days = 7

如果使用者說「鍍金 20u」「Gold 20u」「Hard Gold 20u」「化金 20u」，enig = true, surface_finish = "Hard Gold", hard_gold = true, enig_thickness_uinch = 20

如果使用者說「不要鍍金」「取消鍍金」「不要 ENIG」，enig = false, surface_finish = null, enig_thickness_uinch = null

如果使用者說「要 VIP」「VIP yes」「有 VIP」，vip = true
如果使用者說「不要 VIP」「取消 VIP」，vip = false

如果使用者說「要 BVH」「有 BVH」，bvh = true
如果使用者說「不要 BVH」「取消 BVH」，bvh = false

如果使用者說「要 Back Drill」「有 Back Drill」，back_drill = true
如果使用者說「不要 Back Drill」「取消 Back Drill」，back_drill = false

如果使用者說「要阻抗」「有阻抗」「Impedance yes」，impedance = true
如果使用者說「不要阻抗」「取消阻抗」，impedance = false

如果使用者說「最小孔徑 8mil」「Min Hole 8mil」，min_hole_mil = 8
如果使用者說「Line/Space 3mil」，line_space_mil = 3
如果使用者說「Hole/Land 8mil」，hole_land_mil = 8
如果使用者說「縱橫比 25」「Aspect Ratio 25」，aspect_ratio = 25
如果使用者說「板翹 4 mil/inch」「Warpage 4 mil/inch」，warpage_mil_per_inch = 4
如果使用者說「白色文字」「Legend Color White」，legend_color = "White"
如果使用者說「綠油」「防焊綠色」「S/M Color Green」，solder_mask_color = "Green"
如果使用者說「要皿孔」「Countersunk YES」，countersunk = true
如果使用者說「Counterbored YES」，counterbored = true
如果使用者說「請附檢驗報告」「Please provide inspection report」，inspection_report_required = true, special_requirements = "Please provide inspection report."

客戶文字：
""" + text

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content.strip()

    result = result.replace("```json", "").replace("```", "").strip()

    parsed = json.loads(result)

    if not isinstance(parsed, dict):
        raise ValueError("AI extraction must return a JSON object")

    return parsed
