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
⚠️ Unable to complete quote

Reason:
{result.get("message")}
"""

    missing_text = ""
    explain_text = ""
    warning_text = ""
    follow_text = ""

    if parsed.get("length_mm") and parsed.get("width_mm"):
        size_text = f'{parsed.get("length_mm")} x {parsed.get("width_mm")} mm'

        dimension_text = f"""
Length: {parsed.get("length_mm")} mm = {result.get("length_inch")} inch
Width: {parsed.get("width_mm")} mm = {result.get("width_inch")} inch
Area: {result.get("area_inch")} sq.inch
"""
    else:
        size_text = f'{parsed.get("area_inch")} sq.inch'

        dimension_text = f"""
Area: {result.get("area_inch")} sq.inch
Source: Area provided directly by customer
"""

    if result.get("explanations"):
        explain_text += "\n[Surcharge Reasons]\n"

        for item in result.get("explanations"):
            explain_text += f"- {item}\n"
    
    if result.get("cam_warnings"):
        warning_text += "\n【CAM Warning】\n"

        for item in result.get("cam_warnings"):
            warning_text += f"- {item}\n"

    if result.get("suggest_missing"):
        missing_text += "\n⚠️ Recommended additional information:\n"

        for item in result.get("suggest_missing"):
            missing_text += f"- {item}\n"
    
    if result.get("follow_up_questions"):

        follow_text += "\n[AI Follow-up Questions]\n"

        for item in result.get("follow_up_questions"):
            follow_text += f"- {item}\n"

    return f"""
📋 Preliminary PCB Quote

[Parsed Specifications]
Layer：{parsed.get("layer")}L
Material：{parsed.get("material")}
Size：{size_text}
Qty：{parsed.get("qty")} pcs

{missing_text}
{follow_text}

[Process]
ENIG：{"Yes" if parsed.get("enig") else "No"}
ENIG Thickness：{parsed.get("enig_thickness_uinch")} u"
VIP：{"Yes" if parsed.get("vip") else "No"}
Impedance：{"Yes" if parsed.get("impedance") else "No"}
Back Drill：{"Yes" if parsed.get("back_drill") else "No"}
BVH：{"Yes" if parsed.get("bvh") else "No"}

[Calculation Details]
{dimension_text}
Difficulty level: {result.get("difficulty_level")}
Difficulty score: {result.get("difficulty_score")}
Engineering fee: {result.get("engineering_fee")}
Base board unit price: {result.get("base_material_price")} / sq.inch
Adjusted board unit price: {result.get("material_price")} / sq.inch
Customer requested quantity: {parsed.get("qty")} pcs
Issue ratio: {result.get("issue_ratio")}
Production quantity: {result.get("production_qty")} pcs
Board material cost: {result.get("material_cost")}
Special process cost: {result.get("process_cost")}
Subtotal: {result.get("subtotal")}
Quantity discount: {result.get("discount")}
{warning_text}
{explain_text}
Lead time: {
f"{result.get('delivery_days')} days"
if result.get("delivery_days") is not None
else "Not provided"
}

Lead-time multiplier: {result.get("delivery_multiplier")}
[Quote Result]
Total: {result.get("total")}
Unit price: {result.get("unit_price")} / pcs

⚠️ This is an AI preliminary quote. Final pricing requires engineering review.
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
            reply_text = "No quote records found"

        else:

            reply_text = "📋 Recent Quote Records\n\n"

            for row in rows:

                created_at, layer, material, total_price = row

                reply_text += (
                    f"Time: {created_at}\n"
                    f"{layer}L | {material}\n"
                    f"Total: {total_price}\n\n"
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

            reply_text = "⚠️ ⚠️ No quote data available"

        else:

            result = calculate_quote(parsed)

            filename = export_quote_excel(parsed, result)

            public_base_url = os.getenv("PUBLIC_BASE_URL")

            download_url = f"{public_base_url}/download/{filename}"

            reply_text = f"""
            ✅ Quote exported

            File:
            {filename}

            Download link:
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
                        TextMessage(text="✅ Previous quote data cleared. You can start a new case.")
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

                reply_text = f"No quote records found for {keyword}"

            else:

                reply_text = (
                    f"📊 {keyword} Average Price\n\n"
                    f"Average total: {round(avg_price, 2)}\n"
                    f"Record count: {count}"
                )

        else:

            reply_text = "Please enter the layer count or material to search"

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

                reply_text = f"No quote records found for {keyword}"

            else:

                reply_text = f"📋 {keyword} Quote Records\n\n"

                for row in rows:

                    created_at, layer, material, total = row

                    reply_text += (
                        f"Time: {created_at}\n"
                        f"{layer}L | {material}\n"
                        f"Total: {total}\n\n"
                    )

        else:

            reply_text = (
                "Please enter the layer count or material to search\n"
                "Example: 46L, FR4, Megtron6"
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
    
    # Manual fallback: ENIG / Gold thickness
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


    # Manual fallback: Copper Weight
    copper_match = re.search(
        r'(銅厚|copper|銅箔|copperweight)?\s*[:：]?\s*(\d+\.?\d*)\s*oz',
        user_text.lower()
    )

    if copper_match:
        parsed["copper_weight"] = f"{copper_match.group(2)}oz"


    # Manual fallback:交期
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

    if user_text == "Formal Quote":

        parsed = user_memory.get(user_id)

        if not parsed:
            reply_text = "⚠️ ⚠️ No quote data available. Please create a quote first."

        else:
            result = calculate_quote(parsed)

            output_path = export_formal_quote(parsed, result)

            filename = os.path.basename(output_path)

            public_base_url = os.getenv("PUBLIC_BASE_URL")

            download_url = f"{public_base_url}/download/exports/{filename}"

            reply_text = f"""
    ✅ 已生成Formal Quote

    File:
    {filename}

    Download link:
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