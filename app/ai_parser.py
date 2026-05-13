import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def parse_pcb_text(text):
    if not os.getenv("OPENAI_API_KEY"):
        raise Exception("OPENAI_API_KEY 沒有讀到，請確認 .env 檔名正確")

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
  "thickness": null,
  "copper_weight": null,
  "surface_finish": null,
  "issue_ratio": null,
  "delivery_days": null
}

規則：
如果使用者說「不要鍍金」「取消鍍金」「不要 ENIG」，enig = false, enig_thickness_uinch = null
如果使用者說「要鍍金」「ENIG」，enig = true
如果使用者說「鍍金改 5u」「Gold 5u」「ENIG 5u」「化金 5u」，enig = true, enig_thickness_uinch = 5

如果使用者說「Hard Gold 20μ」「Gold 20μ」「20um」「20μm」，enig = true。
如果單位是 u" 或 uinch，直接當成 enig_thickness_uinch。
如果單位是 um、μm、μ，請換算成 uinch：1um = 39.37uinch。
例如 0.635um = 25u"，20um = 787.4u"。

如果使用者說「不要 BVH」「取消 BVH」，bvh = false
如果使用者說「不要 Back Drill」「取消 Back Drill」，back_drill = false
如果使用者說「不要 VIP」「取消 VIP」，vip = false

如果使用者說「改成 4 pcs」「數量改 4」，qty = 4
如果使用者說「投料率改 2」「4片產出2片」，issue_ratio = 2

沒有提到的欄位保持 null，不要自己填 false。

如果使用者說「7天」「交期7天」「需要7天」，delivery_days = 7
如果使用者說「3天急件」「3天」，delivery_days = 3
如果沒有提到交期，delivery_days = null

如果使用者說「板厚 5mm」「厚度 5mm」「Thickness 5mm」，thickness = 5

如果使用者說「銅厚 1oz」「Copper 1oz」「1 oz」，copper_weight = "1oz"

如果使用者說「交期 7天」「7天」「Lead time 7 days」，delivery_days = 7

如果使用者說「鍍金 20u」「Gold 20u」「Hard Gold 20u」「化金 20u」，enig = true, surface_finish = "Hard Gold", enig_thickness_uinch = 20

如果使用者說「不要鍍金」「取消鍍金」「不要 ENIG」，enig = false, surface_finish = null, enig_thickness_uinch = null

如果使用者說「要 VIP」「VIP yes」「有 VIP」，vip = true
如果使用者說「不要 VIP」「取消 VIP」，vip = false

如果使用者說「要 BVH」「有 BVH」，bvh = true
如果使用者說「不要 BVH」「取消 BVH」，bvh = false

如果使用者說「要 Back Drill」「有 Back Drill」，back_drill = true
如果使用者說「不要 Back Drill」「取消 Back Drill」，back_drill = false

如果使用者說「要阻抗」「有阻抗」「Impedance yes」，impedance = true
如果使用者說「不要阻抗」「取消阻抗」，impedance = false

客戶文字：
""" + text

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    result = response.choices[0].message.content.strip()

    result = result.replace("```json", "").replace("```", "").strip()

    parsed = json.loads(result)

    # ENIG Thickness regex backup
    import re

    clean_text = (
        text.lower()
        .replace(" ", "")
        .replace("μ", "u")
    )

    enig_match = re.search(
        r'(\d+\.?\d*)\s*(u"|uinch|um)',
        clean_text
    )

    if enig_match:
        value = float(enig_match.group(1))
        unit = enig_match.group(2)

        parsed["enig"] = True

        if unit == "um":
            value = round(value * 39.37, 2)

        parsed["enig_thickness_uinch"] = value

    return parsed