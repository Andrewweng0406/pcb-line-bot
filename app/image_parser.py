import os
import json
import base64

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def encode_image(image_path):

    with open(image_path, "rb") as image_file:
        return base64.b64encode(
            image_file.read()
        ).decode("utf-8")


def parse_pcb_image(image_path):

    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",

        messages=[
            {
                "role": "user",
                "content": [

                    {
                        "type": "text",
                        "text": """
你是 PCB 報價助理，請從圖片中的 PCB Fabrication Specification 抽取規格。

只回傳 JSON，不要 markdown，不要解釋。

判斷規則：
- company_name: 如果看到 PCB 絲印上的公司名稱、Logo、或公司標誌，請填入公司名稱字串。如果看不到，填 null。
- Material 請保留圖片上實際材料文字，不要簡化。例如 FR4_HTG 要輸出 "FR4_HTG"，M6 FR4-HTG 要輸出 "M6 FR4-HTG"。如果看到 MEGTRON 6、MEGTRON6，都輸出 "MEGTRON 6"。
- Surface Plating 如果看到 Ni/Au、Au、ENIG、Immersion Gold，都代表 enig = true
- Surface Finish 如果看到 Hard Gold，請輸出 surface_finish = "Hard Gold" 並 hard_gold = true。看到 ENIG/化金/Immersion Gold 則 surface_finish = "ENIG"。
- 如果看到 VIP、Via in Pad、Resin Plug、Plug Via，代表 vip = true
- 如果看到 Impedance、50 ohm、Ω，代表 impedance = true
- 如果看到 Back Drill、Backdrill，代表 back_drill = true
- 如果看到 BVH、Blind Via Hole，代表 bvh = true
- 如果看到 Re-order 被勾選，代表 is_reorder = true；New Version 被勾選且 Re-order 未勾選，is_reorder = false。
- 如果看到 Countersunk、Counterbored、皿孔、沉頭孔，代表 countersunk = true 或 counterbored = true
- 如果看到 Please provide inspection report、出貨檢驗及量測報告，代表 inspection_report_required = true，並把句子放到 special_requirements。
- 如果找不到欄位，請用 null 或 false，不要猜
- 如果看到 Thickness、厚度，例如 6.6 +/-0.2 mm，請輸出 thickness = 6.6
- 如果看到 Min. Pitch、Device Pitch、最小 Pitch，請輸出 pitch_mm
- 如果看到 Min Hole、最小孔徑，請輸出 min_hole_mil
- 如果看到 Line/Space，請輸出 line_space_mil
- 如果看到 Hole/Land，請輸出 hole_land_mil
- 如果看到 縱橫比、Aspect Ratio，請輸出 aspect_ratio
- 如果看到 Warpage、板翹容忍度，請輸出 warpage_mil_per_inch
- 如果看到 External / Inner 銅厚，請輸出 copper_outer_oz 與 copper_inner_oz。例如 External 1 o.z. = copper_outer_oz 1，Inner 1 o.z. = copper_inner_oz 1。
- 如果看到 Copper thickness 欄位但無法分辨內外層，請原文輸出 copper_weight，不要猜成 1oz。
- 如果看到 Legend Color / 文字顏色，請輸出 legend_color。看到 S/M Color / 防焊顏色，請輸出 solder_mask_color。

- 如果看到 Surface Plating、表面鍍金、Ni/Au、ENIG、Immersion Gold，請輸出:
- enig = true
- surface_finish = "ENIG"

- 如果看到 Au(0.635 um)，請輸出:
- enig_thickness_um = 0.635
- enig_thickness_uinch = 25

- 如果看到 Gold 3u"、Au 3u"、鍍金 3u"，這已經是 uinch，不要再乘 39.37，直接輸出：
- "enig_thickness_uinch": 3

- 如果看到 Hard Gold 20μ、Gold 20μ、Hard Gold 20u、Gold 20u，請輸出：
- "enig": true,
- "surface_finish": "Hard Gold",
- "enig_thickness_uinch": 20

注意：這裡的 20μ 通常代表 20 micro-inch，請先當作 20 uinch，不要換算成 787。
- 如果看到 0.635 um、0.635 μm，這才是微米，才需要乘以 39.37 轉成 uinch。

- 重點：
- u" = uinch，不要換算
- um / μm = micrometer，需要換算

- 換算規則：
- 1 um = 39.37 uinch

- 例如：
- 0.127 um ≈ 5 uinch
- 0.254 um ≈ 10 uinch
- 0.635 um ≈ 25 uinch

如果看到：
Area 12" (Round)
Area 12"
12" Round

這不是長度，這代表面積。
請輸出：
"area_inch": 12

不要因為沒有 length_mm / width_mm 就留空，若有 Area 就一定填 area_inch。

如果圖片裡看到 Delivery、交期、shipping date，請盡量抽取 delivery_days。
如果只有日期但無法判斷天數，delivery_days = null。


JSON 格式：
{
  "company_name": null,
  "layer": null,
  "material": null,
  "length_mm": null,
  "width_mm": null,
  "qty": 1,
  "enig": false,
  "vip": false,
  "impedance": false,
  "back_drill": false,
  "bvh": false,
  "is_reorder": false,
  "hard_gold": false,
  "countersunk": false,
  "counterbored": false,
  "inspection_report_required": false,
  "thickness": null,
  "pitch_mm": null,
  "copper_weight": null,
  "copper_outer_oz": null,
  "copper_inner_oz": null,
  "surface_finish": null,
  "enig_thickness_um": null,
  "enig_thickness_uinch": null,
  "min_hole_mil": null,
  "line_space_mil": null,
  "hole_land_mil": null,
  "aspect_ratio": null,
  "warpage_mil_per_inch": null,
  "legend_color": null,
  "solder_mask_color": null,
  "special_requirements": null,
  "issue_ratio": 1,
  "area_inch": null,
  "delivery_days": null
}
"""
                    },

                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],

        temperature=0
    )

    result = response.choices[0].message.content

    result = result.replace("```json", "")
    result = result.replace("```", "")
    result = result.strip()

    parsed = json.loads(result)


    # ENIG / Gold thickness regex backup from AI response text
    import re

    clean_result = (
        result.lower()
        .replace(" ", "")
        .replace("μ", "u")
    )

    gold_match = re.search(
        r'(gold|enig|au|化金|鍍金).*?(\d+\.?\d*)\s*(u"|uinch|um|u)',
        clean_result
    )

    if gold_match:
        value = float(gold_match.group(2))
        unit = gold_match.group(3)

        parsed["enig"] = True

        if unit == "um":
            value = round(value * 39.37, 2)

        parsed["enig_thickness_uinch"] = value

    return parsed
