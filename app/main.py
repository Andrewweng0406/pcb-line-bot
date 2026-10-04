from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import uuid
import re

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

from app.core import (
    settings,
    init_db,
    user_memory,
    file_storage,
    get_logger
)
from app.core.database import (
    get_recent_quotes,
    search_quotes,
    get_average_price,
    save_quote,
    get_system_stats
)
from app.quote_engine import calculate_quote
from app.ai_parser import parse_pcb_text
from app.image_parser import parse_pcb_image
from app.export_excel import export_quote_excel
from app.formal_quote_export import export_formal_quote
from app.api import router as api_router
from app.web import router as web_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Register API routes
app.include_router(api_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

configuration = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/download/exports/{filename}")
def download_export_file(filename: str):
    try:
        logger.info(f"Downloading export: {filename}")
        export_path = os.path.join(settings.EXPORT_DIR, filename)

        if not os.path.exists(export_path):
            logger.warning(f"Export file not found: {filename}")
            return JSONResponse(
                status_code=404,
                content={"error": "File not found"}
            )

        return FileResponse(
            path=export_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"Error downloading export: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


def format_quote_reply(parsed: dict, result: dict) -> str:
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

    company_section = ""
    if parsed.get("company_name"):
        company_section = f"🏭 Identified company: {parsed.get('company_name')}\n\n"

    return f"""
📋 Preliminary PCB Quote

{company_section}[Parsed Specifications]
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
    try:
        signature = request.headers.get("X-Line-Signature")
        body = await request.body()

        if not signature:
            logger.warning("Missing X-Line-Signature header")
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})

        handler.handle(body.decode(), signature)
        return {"status": "ok"}

    except InvalidSignatureError:
        logger.warning("Invalid LINE signature")
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    except Exception as e:
        logger.error(f"Error processing callback: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_text = event.message.text.strip()

        logger.info(f"Message from {user_id}: {user_text[:50]}")

        # HELP command
        if user_text.lower() in ["help", "幫助", "帮助", "说明", "說明"]:
            help_text = """📖 PCB Quote Bot - User Guide

🔹 Basic Commands:
━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Upload an image or describe the specifications
   • Send a PCB drawing (.jpg, .png)
   • Or describe it in text: "6L, 100x100mm, qty 9, issue ratio 3"

2️⃣ Reply to follow-up questions
   • The bot may ask for layers, material, pitch, lead time, etc.
   • Reply directly, for example: "0.35mm" or "7 days"

3️⃣ Search quotes
   • Type "query quotes" to view recent quote records

4️⃣ Export a quote
   • Type "export quote" to download the Excel quote

5️⃣ Start a new case
   • Type "new case", "clear", or "reset" to clear the current quote

━━━━━━━━━━━━━━━━━━━━━━━
📝 Example RFQ:

"6L FR4 100x100mm qty 9 issue ratio 3
 Pitch 0.4mm lead time 7 days ENIG 10u VIP"

━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Lead-time Rules:
• 2-4L: 5 days  • 6L: 6 days  • 8-10L: 7 days
• 12-14L: 8 days  • 16-30L: 10 days

💰 Surface Finish:
• ENIG 5u": 3,000  • ENIG 10u": 6,000
• ENIG 30u": 12,000  • ENIG 50u": 18,000

🔧 Extra Processes:
• VIP (resin plugged via): 5,000
• Back Drill: 5,000  • Inner-layer AOI: 600/layer

━━━━━━━━━━━━━━━━━━━━━━━
💡 Tips:
✅ Complete specifications produce more accurate quotes
✅ Pitch, trace-to-hole spacing, and flatness can affect price
✅ Re-orders may receive a 10% discount

Need help? Type "help" anytime to view this guide."""

            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=help_text)]
                    )
                )
            return

        # STATUS command - system status panel
        if user_text.lower() in ["status", "狀態", "状态", "系統狀態", "系统状态"]:
            stats = get_system_stats()

            last_quote_str = "No quotes yet"
            if stats["last_quote_time"]:
                from datetime import datetime
                last_quote = stats["last_quote_time"]
                now = datetime.utcnow()
                diff = now - last_quote

                if diff.seconds < 60:
                    time_str = f"{diff.seconds} seconds ago"
                elif diff.seconds < 3600:
                    time_str = f"{diff.seconds // 60} minutes ago"
                elif diff.days == 0:
                    time_str = f"{diff.seconds // 3600} hours ago"
                else:
                    time_str = last_quote.strftime("%Y-%m-%d %H:%M")
                last_quote_str = time_str

            average_quotes = "; ".join(
                f"{amount['currency']} {amount['average']:,.2f}" if amount['average'] is not None else f"{amount['currency']} -"
                for amount in stats.get("amounts_by_currency", [])
            ) or "-"
            status_text = f"""📊 PCB Quote Bot - System Status

━━━━━━━━━━━━━━━━━━━━━━━
✅ System status: Running normally

━━━━━━━━━━━━━━━━━━━━━━━
📈 Today's Stats:
• Quote requests: {stats['today_count']}
• Total history: {stats['total_count']}
• Average quote: {average_quotes}

━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Last Activity:
• Latest quote: {last_quote_str}

━━━━━━━━━━━━━━━━━━━━━━━
💾 System Info:
• Automatic backup: Daily at 00:00
• Sync frequency: Real time
• Data retention: Permanent

━━━━━━━━━━━━━━━━━━━━━━━
✨ Everything looks good.
Type "help" anytime for usage instructions."""

            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=status_text)]
                    )
                )
            return

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
                        messages=[TextMessage(text=reply_text)]
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
                download_url = f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
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
                        messages=[TextMessage(text=reply_text)]
                    )
                )
            return

        if user_text.lower() in ["結束", "reset", "clear", "新案件"]:
            user_memory.delete(user_id)
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="✅ Previous quote data cleared. You can start a new case.")]
                    )
                )
            return

        old_data = user_memory.get(user_id) or {}

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
                        messages=[TextMessage(text=reply_text)]
                    )
                )
            return

        query_keywords = ["查詢", "查", "找", "歷史", "之前", "報價紀錄", "歷史價格"]
        if any(word in user_text for word in query_keywords):
            keyword = None
            layer_match = re.search(r'(\d+)\s*(L|層)', user_text)
            if layer_match:
                keyword = layer_match.group(1)
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
                        messages=[TextMessage(text=reply_text)]
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

        copper_match = re.search(
            r'(銅厚|copper|銅箔|copperweight)?\s*[:：]?\s*(\d+\.?\d*)\s*oz',
            user_text.lower()
        )
        if copper_match:
            parsed["copper_weight"] = f"{copper_match.group(2)}oz"

        delivery_match = re.search(
            r'(\d+)\s*(天|days|day)',
            user_text.lower()
        )
        if delivery_match:
            parsed["delivery_days"] = int(delivery_match.group(1))

        user_memory.set(user_id, parsed)
        result = calculate_quote(parsed)

        if result.get("status") == "success":
            save_quote(user_id, parsed, result)

        reply_text = format_quote_reply(parsed, result)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
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
                download_url = f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
                reply_text = f"""
✅ Formal quote generated

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
                            messages=[TextMessage(text=reply_text)]
                        )
                    )
            except Exception as e:
                logger.error(f"Error pushing message to {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ An error occurred while processing the message. Please try again later.")]
                    )
                )
        except:
            pass


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    try:
        user_id = event.source.user_id
        image_id = event.message.id
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        image_path = os.path.join(settings.UPLOAD_DIR, f"upload_{uuid.uuid4().hex}.jpg")

        logger.info(f"Received image from {user_id}: {image_id}")

        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            image_content = blob_api.get_message_content(image_id)

            with open(image_path, "wb") as f:
                f.write(image_content)

        parsed = parse_pcb_image(image_path)
        user_memory.set(user_id, parsed)

        result = calculate_quote(parsed)
        if result.get("status") == "success":
            save_quote(user_id, parsed, result)

        reply_text = format_quote_reply(parsed, result)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

        file_storage.cleanup(image_path)

    except Exception as e:
        logger.error(f"Error handling image from {user_id}: {e}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ Unable to process the image. Please try again later.")]
                    )
                )
        except:
            pass


@app.get("/quote_text")
def quote_text(text: str):
    try:
        logger.info(f"Quote text endpoint: {text[:50]}")
        parsed = parse_pcb_text(text)
        result = calculate_quote(parsed)
        return format_quote_reply(parsed, result)
    except Exception as e:
        logger.error(f"Error in quote_text: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/image_test")
def image_test():
    try:
        if not os.path.exists("test.jpg"):
            return JSONResponse(
                status_code=404,
                content={"error": "test.jpg not found"}
            )
        parsed = parse_pcb_image("test.jpg")
        result = calculate_quote(parsed)
        return {"parsed": parsed, "quote": result}
    except Exception as e:
        logger.error(f"Error in image_test: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
