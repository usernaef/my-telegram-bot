import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import asyncio
import json

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

# ذخیره وضعیت بازی‌ها
games = {}
target_group_id = None

async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception:
        return False

async def check_links_periodically():
    while True:
        await asyncio.sleep(600)  # هر 10 دقیقه
        try:
            if target_group_id:
                try:
                    async for message in application.bot.get_chat_history(target_group_id, limit=100):
                        if message.text and any(domain in message.text.lower() 
                            for domain in ['http', 'www', '.com', '.ir', 't.me']):
                            if not await is_admin(target_group_id, message.from_user.id):
                                try:
                                    await message.delete()
                                except Exception as e:
                                    logger.error(f"Error deleting message: {e}")
                except Exception as e:
                    logger.error(f"Error checking group: {e}")
        except Exception as e:
            logger.error(f"Error in periodic check: {e}")

def create_board():
    return [[" " for _ in range(3)] for _ in range(3)]

def create_keyboard(game_id):
    board = games[game_id]["board"]
    keyboard = []
    for i in range(3):
        row = []
        for j in range(3):
            row.append(InlineKeyboardButton(
                board[i][j] if board[i][j] != " " else "⬜️",
                callback_data=f"move_{game_id}_{i}_{j}"
            ))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def check_winner(board):
    # بررسی سطرها
    for row in board:
        if row[0] == row[1] == row[2] != " ":
            return row[0]
    
    # بررسی ستون‌ها
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] != " ":
            return board[0][col]
    
    # بررسی قطرها
    if board[0][0] == board[1][1] == board[2][2] != " ":
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != " ":
        return board[0][2]
    
    # بررسی مساوی
    if all(cell != " " for row in board for cell in row):
        return "tie"
    
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        game_id = str(update.effective_user.id)
        games[game_id] = {
            "board": create_board(),
            "current_player": "X",
            "players": {"X": update.effective_user.id}
        }
        
        await update.message.reply_text(
            "بازی دوز شروع شد! منتظر حریف باشید...\nبرای پیوستن به بازی روی دکمه‌ها کلیک کنید:",
            reply_markup=create_keyboard(game_id)
        )
    else:
        await update.message.reply_text("""
🤖 سلام! من ربات ضد لینک و بازی دوز هستم.

برای استفاده از قابلیت ضد لینک:
1️⃣ من را به گروه خود اضافه کنید
2️⃣ من را ادمین کنید

برای بازی دوز:
در چت خصوصی /start را بزنید

قابلیت‌ها:
• حذف خودکار لینک‌ها هر 10 دقیقه
• بازی دوز دو نفره
""")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    
    global target_group_id
    if target_group_id is None and update.effective_chat.type != 'private':
        target_group_id = chat_id

    if update.effective_chat.type == 'private':
        return

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, game_id, row, col = query.data.split("_")
    row, col = int(row), int(col)
    
    if game_id not in games:
        await query.answer("این بازی دیگر معتبر نیست!")
        return
    
    game = games[game_id]
    
    # اگر بازیکن دوم هنوز نپیوسته و این بازیکن اول نیست
    if "O" not in game["players"] and query.from_user.id != game["players"]["X"]:
        game["players"]["O"] = query.from_user.id
    
    # بررسی نوبت بازیکن
    if query.from_user.id != game["players"][game["current_player"]]:
        await query.answer("الان نوبت شما نیست!")
        return
    
    # بررسی خالی بودن خانه
    if game["board"][row][col] != " ":
        await query.answer("این خانه قبلاً پر شده!")
        return
    
    # انجام حرکت
    game["board"][row][col] = game["current_player"]
    
    # بررسی برنده
    winner = check_winner(game["board"])
    if winner:
        if winner == "tie":
            await query.edit_message_text(
                "بازی مساوی شد!",
                reply_markup=create_keyboard(game_id)
            )
        else:
            await query.edit_message_text(
                f"بازیکن {winner} برنده شد!",
                reply_markup=create_keyboard(game_id)
            )
        del games[game_id]
    else:
        game["current_player"] = "O" if game["current_player"] == "X" else "X"
        await query.edit_message_text(
            f"نوبت بازیکن {game['current_player']} است",
            reply_markup=create_keyboard(game_id)
        )

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_bot():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_move, pattern="^move_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(check_links_periodically())
    
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_bot()
    logger.info("Bot started!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot stopped!")