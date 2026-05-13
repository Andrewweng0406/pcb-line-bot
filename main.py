from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)
from linebot.exceptions import InvalidSignatureError

from dotenv import load_dotenv
import os
import uuid
import re

from ai_parser import parse_pcb_text
from image_parser import parse_pcb_image
from quote_engine import calculate_quote
from memory_store import user_memory
from database import (
    init_db,
    save_quote,
    get_recent_quotes,
    search_quotes,
    get_average_price
)
from export_excel import export_quote_excel
from formal_quote_export import export_formal_quote


load_dotenv()

app = FastAPI()
init_db()


@app.get("/")
def home():
    return {"message": "PCB Line Bot Running"}


@app.get("/download/exports/{filename}")
def download_export_file(filename: str):

    path = os.path.join("exports", filename)

    return FileResponse(
        path=path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


configuration = Configuration(
    access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
)

handler = WebhookHandler(
    os.getenv("LINE_CHANNEL_SECRET")
)


def format_quote_reply(parsed, result):

    if result.get("status") != "success":
        return f"""
⚠️ 無法完成報價

原因：
{result.get("message")}
"""

    missing_text = ""
    explain_text = ""
    warning_text = ""
    follow_text = ""

    if parsed.get("length_mm") and parsed.get("width_mm"):
        size_text = f'{parsed.get("length_mm")} x {parsed.get("width_mm")} mm'

        dimension_text = f"""
長：{parsed.get("length_mm")} mm = {result.get("length_inch")} inch
寬：{parsed.get("width_mm")} mm = {result.get("width_inch")} inch
面積：{result.get("area_inch")} sq.inch
"""
    else:
        size_text = f'{parsed.get("area_inch")} sq.inch'

        dimension_text = f"""
面積：{result.get("area_inch")} sq.inch
來源：客戶直接提供 Area
"""

    if result.get("explanations"):
        explain_text += "\n【加價原因】\n"

        for item in result.get("explanations"):
            explain_text += f"- {item}\n"
    
    if result.get("cam_warnings"):
        warning_text += "\n【CAM Warning】\n"

        for item in result.get("cam_warnings"):
            warning_text += f"- {item}\n"

    if result.get("suggest_missing"):
        missing_text += "\n⚠️ 建議補充資料：\n"

        for item in result.get("suggest_missing"):
            missing_text += f"- {item}\n"
    
    if result.get("follow_up_questions"):

        follow_text += "\n【AI 追問】\n"

        for item in result.get("follow_up_questions"):
            follow_text += f"- {item}\n"

    return f"""
📋 PCB 初步報價

【讀取到的規格】
Layer：{parsed.get("layer")}L
Material：{parsed.get("material")}
Size：{size_text}
Qty：{parsed.get("qty")} pcs

{missing_text}
{follow_text}

【製程】
ENIG：{"Yes" if parsed.get("enig") else "No"}
ENIG Thickness：{parsed.get("enig_thickness_uinch")} u"
VIP：{"Yes" if parsed.get("vip") else "No"}
Impedance：{"Yes" if parsed.get("impedance") else "No"}
Back Drill：{"Yes" if parsed.get("back_drill") else "No"}
BVH：{"Yes" if parsed.get("bvh") else "No"}

【計算明細】
{dimension_text}
難度等級：{result.get("difficulty_level")}
難度分數：{result.get("difficulty_score")}
工程費：{result.get("engineering_fee")}
原始板材單價：{result.get("base_material_price")} / sq.inch
加價後板材單價：{result.get("material_price")} / sq.inch
客戶需求數量：{parsed.get("qty")} pcs
投料率：{result.get("issue_ratio")}
實際投料數量：{result.get("production_qty")} pcs
板材費：{result.get("material_cost")}
特殊加工費：{result.get("process_cost")}
小計：{result.get("subtotal")}
數量折扣：{result.get("discount")}
{warning_text}
{explain_text}
交期：{
f"{result.get('delivery_days')} 天"
if result.get("delivery_days") is not None
else "未提供"
}

交期倍率：{result.get("delivery_multiplier")}
【報價結果】
總價：{result.get("total")}
單片價格：{result.get("unit_price")} / pcs

⚠️ 此為 AI 初步報價，最終價格需工程確認。
"""


@app.post("/callback")
async def callback(request: Request):

    signature = request.headers["X-Line-Signature"]
    body = await request.body()

    try:
        handler.handle(body.decode(), signature)

    except InvalidSignatureError:
        return "Invalid signature"

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    
    user_text = event.message.text
    user_text = user_text.strip()

    if user_text == "查詢報價":

        rows = get_recent_quotes()

        if not rows:
            reply_text = "目前沒有報價紀錄"

        else:

            reply_text = "📋 最近報價紀錄\n\n"

            for row in rows:

                created_at, layer, material, total_price = row

                reply_text += (
                    f"時間：{created_at}\n"
                    f"{layer}L | {material}\n"
                    f"總價：{total_price}\n\n"
                )

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_text)
                    ]
                )
            )

        return
    

    if user_text == "匯出報價單":

        parsed = user_memory.get(user_id)

        if not parsed:

            reply_text = "⚠️ 目前沒有報價資料"

        else:

            result = calculate_quote(parsed)

            filename = export_quote_excel(parsed, result)

            public_base_url = os.getenv("PUBLIC_BASE_URL")

            download_url = f"{public_base_url}/download/{filename}"

            reply_text = f"""
            ✅ 已匯出報價單

            檔案：
            {filename}

            下載連結：
            {download_url}
            """

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_text)
                    ]
                )
            )

        return

    if user_text.lower() in ["結束", "reset", "clear", "新案件"]:

        if user_id in user_memory:
            del user_memory[user_id]

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text="✅ 已清除上一筆報價資料，可以開始新的案件。")
                    ]
                )
            )

        return

    old_data = user_memory.get(user_id, {})

    if "平均" in user_text:

        keyword = None

        layer_match = re.search(r'(\d+)\s*(L|層)', user_text)

        if layer_match:
            keyword = layer_match.group(1)

        elif "FR4" in user_text.upper():
            keyword = "FR4"

        elif "MEGTRON" in user_text.upper():
            keyword = "MEGTRON"

        if keyword:

            avg_price, count = get_average_price(keyword)

            if count == 0:

                reply_text = f"找不到 {keyword} 的報價紀錄"

            else:

                reply_text = (
                    f"📊 {keyword} 平均價格\n\n"
                    f"平均總價：{round(avg_price, 2)}\n"
                    f"資料筆數：{count}"
                )

        else:

            reply_text = "請輸入想查詢的 Layer 或材料"

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_text)
                    ]
                )
            )

        return

    query_keywords = [
        "查詢",
        "查",
        "找",
        "歷史",
        "之前",
        "報價紀錄",
        "歷史價格"
    ]

    if any(word in user_text for word in query_keywords):

        keyword = None

        # Layer
        layer_match = re.search(r'(\d+)\s*(L|層)', user_text)

        if layer_match:
            keyword = layer_match.group(1)

        # Material
        elif "FR4" in user_text.upper():
            keyword = "FR4"

        elif "MEGTRON" in user_text.upper():
            keyword = "MEGTRON"

        if keyword:

            rows = search_quotes(keyword)

            if not rows:

                reply_text = f"找不到 {keyword} 的報價紀錄"

            else:

                reply_text = f"📋 {keyword} 報價紀錄\n\n"

                for row in rows:

                    created_at, layer, material, total = row

                    reply_text += (
                        f"時間：{created_at}\n"
                        f"{layer}L | {material}\n"
                        f"總價：{total}\n\n"
                    )

        else:

            reply_text = (
                "請輸入想查詢的 Layer 或材料\n"
                "例如：46L、FR4、Megtron6"
            )

        with ApiClient(configuration) as api_client:

            line_bot_api = MessagingApi(api_client)

            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_text)
                    ]
                )
            )

        return

    parsed = parse_pcb_text(user_text)

    for key, value in old_data.items():
        if parsed.get(key) in [None, ""]:
            parsed[key] = value

    thickness_match = re.search(r'(\d+\.?\d*)\s*mm', user_text.lower())
    if thickness_match:
        parsed["thickness"] = thickness_match.group(1)
    
    # 手動補 ENIG / Gold thickness
    gold_match = re.search(
        r'(鍍金|化金|gold|enig|hard gold)\s*(\d+\.?\d*)\s*(u"|u|uinch)',
        user_text.lower()
    )

    if gold_match:
        parsed["enig"] = True
        parsed["enig_thickness_uinch"] = float(gold_match.group(2))

        if "hard gold" in user_text.lower():
            parsed["surface_finish"] = "Hard Gold"
        else:
            parsed["surface_finish"] = "ENIG"


    # 手動補 Copper Weight
    copper_match = re.search(
        r'(銅厚|copper|銅箔|copperweight)?\s*[:：]?\s*(\d+\.?\d*)\s*oz',
        user_text.lower()
    )

    if copper_match:
        parsed["copper_weight"] = f"{copper_match.group(2)}oz"


    # 手動補交期
    delivery_match = re.search(
        r'(\d+)\s*(天|days|day)',
        user_text.lower()
    )

    if delivery_match:
        parsed["delivery_days"] = int(delivery_match.group(1))

    user_memory[user_id] = parsed

    result = calculate_quote(parsed)

    if result.get("status") == "success":
        save_quote(user_id, parsed, result)

    reply_text = format_quote_reply(parsed, result)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text)
                ]
            )
        )

    if user_text == "正式報價單":

        parsed = user_memory.get(user_id)

        if not parsed:
            reply_text = "⚠️ 目前沒有報價資料，請先報價。"

        else:
            result = calculate_quote(parsed)

            output_path = export_formal_quote(parsed, result)

            filename = os.path.basename(output_path)

            public_base_url = os.getenv("PUBLIC_BASE_URL")

            download_url = f"{public_base_url}/download/exports/{filename}"

            reply_text = f"""
    ✅ 已生成正式報價單

    檔案：
    {filename}

    下載連結：
    {download_url}
    """

        try:

            with ApiClient(configuration) as api_client:

                line_bot_api = MessagingApi(api_client)

                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[
                            TextMessage(text=reply_text)
                        ]
                    )
                )

        except Exception as e:

            print("LINE reply failed:", e)

        return


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):

    image_id = event.message.id
    image_path = f"upload_{uuid.uuid4().hex}.jpg"

    with ApiClient(configuration) as api_client:
        blob_api = MessagingApiBlob(api_client)
        image_content = blob_api.get_message_content(image_id)

        with open(image_path, "wb") as f:
            f.write(image_content)

    parsed = parse_pcb_image(image_path)

    user_id = event.source.user_id
    user_memory[user_id] = parsed

    result = calculate_quote(parsed)

    if result.get("status") == "success":
        save_quote(user_id, parsed, result)

    reply_text = format_quote_reply(parsed, result)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply_text)
                ]
            )
        )


@app.get("/quote_text")
def quote_text(text: str):

    parsed = parse_pcb_text(text)
    result = calculate_quote(parsed)

    return format_quote_reply(parsed, result)


@app.get("/image_test")
def image_test():

    parsed = parse_pcb_image("test.jpg")
    result = calculate_quote(parsed)

    return {
        "parsed": parsed,
        "quote": result
    }