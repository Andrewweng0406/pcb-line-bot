from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
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

configuration = Configuration(
    access_token=settings.LINE_CHANNEL_ACCESS_TOKEN
)

handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)


@app.get("/")
def home():
    logger.info("Home endpoint accessed")
    return {
        "message": f"{settings.APP_NAME} Running",
        "version": settings.APP_VERSION,
        "status": "healthy"
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/download/exports/{filename}")
def download_export_file(filename: str):
    try:
        logger.info(f"Downloading export: {filename}")
        export_path = os.path.join("exports", filename)

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

        # HELP 指令
        if user_text.lower() in ["help", "幫助", "帮助", "说明", "說明"]:
            help_text = """📖 PCB 報價機器人 - 使用指南

🔹 基本指令：
━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 上傳圖片或描述規格
   • 傳送 PCB 設計圖（.jpg, .png）
   • 或用文字描述：「6層，100x100mm，數量9，投料率3」

2️⃣ 回覆詢問
   • 機器人會問：層數、材料、Pitch、交期等
   • 直接回覆即可（例：「0.35mm」「7天」）

3️⃣ 查詢報價
   • 輸入「查詢報價」查看最近的報價記錄

4️⃣ 匯出報價單
   • 輸入「匯出報價單」下載 Excel 報價單

5️⃣ 開始新案件
   • 輸入「新案件」、「結束」或「reset」清除當前報價

━━━━━━━━━━━━━━━━━━━━━━━
📝 報價規格範例：

「6層 FR4 100x100mm 數量9 投料率3
 Pitch 0.4mm 交期7天 ENIG 10u VIP」

━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 交期規則：
• 2-4L：5天  • 6L：6天  • 8-10L：7天
• 12-14L：8天  • 16-30L：10天

💰 表面處理：
• ENIG 5u"：3,000  • ENIG 10u"：6,000
• ENIG 30u"：12,000  • ENIG 50u"：18,000

🔧 額外加工：
• VIP（樹脂塞孔）：5,000
• Back Drill：5,000  • 內層 AOI：600/層

━━━━━━━━━━━━━━━━━━━━━━━
💡 小提示：
✅ 儘量提供完整規格，報價會更準確
✅ Pitch、孔到線距、平坦度會影響價格
✅ 數量 ≥2 時享 9 折優惠

需要幫助嗎？輸入「help」隨時查看說明！"""

            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=help_text)]
                    )
                )
            return

        # STATUS 指令 - 系統狀態面板
        if user_text.lower() in ["status", "狀態", "状态", "系統狀態", "系统状态"]:
            stats = get_system_stats()

            last_quote_str = "未有報價"
            if stats["last_quote_time"]:
                from datetime import datetime
                last_quote = stats["last_quote_time"]
                now = datetime.utcnow()
                diff = now - last_quote

                if diff.seconds < 60:
                    time_str = f"{diff.seconds} 秒前"
                elif diff.seconds < 3600:
                    time_str = f"{diff.seconds // 60} 分鐘前"
                elif diff.days == 0:
                    time_str = f"{diff.seconds // 3600} 小時前"
                else:
                    time_str = last_quote.strftime("%Y-%m-%d %H:%M")
                last_quote_str = time_str

            status_text = f"""📊 PCB 報價機器人 - 系統狀態

━━━━━━━━━━━━━━━━━━━━━━━
✅ 系統狀態：正常運行

━━━━━━━━━━━━━━━━━━━━━━━
📈 今日統計：
• 報價查詢：{stats['today_count']} 次
• 歷史總數：{stats['total_count']} 次
• 平均報價：NT$ {stats['avg_price']:,.0f}

━━━━━━━━━━━━━━━━━━━━━━━
⏱️ 最後活動：
• 最近報價：{last_quote_str}

━━━━━━━━━━━━━━━━━━━━━━━
💾 系統信息：
• 自動備份：每天 00:00
• 同步頻率：實時
• 數據保留：永久

━━━━━━━━━━━━━━━━━━━━━━━
✨ 一切正常，祝你使用愉快！
有任何問題，輸入 help 查看說明"""

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
                        messages=[TextMessage(text=reply_text)]
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
                download_url = f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
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
                        messages=[TextMessage(text="✅ 已清除上一筆報價資料，可以開始新的案件。")]
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

        if user_text == "正式報價單":
            parsed = user_memory.get(user_id)
            if not parsed:
                reply_text = "⚠️ 目前沒有報價資料，請先報價。"
            else:
                result = calculate_quote(parsed)
                output_path = export_formal_quote(parsed, result)
                filename = os.path.basename(output_path)
                download_url = f"{settings.PUBLIC_BASE_URL}/download/exports/{filename}"
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
                        messages=[TextMessage(text="⚠️ 處理訊息時發生錯誤，請稍後再試。")]
                    )
                )
        except:
            pass


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    try:
        user_id = event.source.user_id
        image_id = event.message.id
        image_path = f"data/uploads/upload_{uuid.uuid4().hex}.jpg"

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
                        messages=[TextMessage(text="⚠️ 無法處理圖片，請稍後再試。")]
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
