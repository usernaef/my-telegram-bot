import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import asyncio
import json
from datetime import datetime

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

# ذخیره وضعیت
games = {}
waiting_players = []
player_games = {}
target_group_id = None

async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception:
        return False

async def check_links_periodically():
    while True:
        await asyncio.sleep(600)
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
            cell = board[i][j]
            button_text = "❌" if cell == "X" else "⭕️" if cell == "O" else "⬜️"
            row.append(InlineKeyboardButton(
                text=button_text,
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
        user_id = update.effective_user.id
        
        # اگر کاربر قبلاً در بازی است
        if user_id in player_games:
            await update.message.reply_text("شما در حال حاضر در یک بازی هستید!")
            return
            
        # اگر کاربری منتظر است
        if waiting_players:
            opponent_id = waiting_players.pop(0)
            game_id = f"{opponent_id}_{user_id}"
            
            games[game_id] = {
                "board": create_board(),
                "current_player": "X",
                "players": {
                    "X": opponent_id,
                    "O": user_id
                },
                "chat_history": []
            }
            
            player_games[opponent_id] = game_id
            player_games[user_id] = game_id
            
            # اعلان به هر دو بازیکن
            await application.bot.send_message(
                opponent_id,
                "حریف پیدا شد! شما X هستید. نوبت شماست!",
                reply_markup=create_keyboard(game_id)
            )
            
            await update.message.reply_text(
                "بازی شروع شد! شما O هستید. منتظر حریف باشید!",
                reply_markup=create_keyboard(game_id)
            )
        else:
            waiting_players.append(user_id)
            await update.message.reply_text("در انتظار حریف... لطفاً صبر کنید.")
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
• بازی دوز دو نفره با قابلیت چت
""")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    global target_group_id
    if target_group_id is None and update.effective_chat.type != 'private':
        target_group_id = chat_id
        return

    if update.effective_chat.type == 'private':
        if user_id in player_games:
            game_id = player_games[user_id]
            game = games[game_id]
            
            # پیدا کردن حریف
            opponent_id = game["players"]["X"] if user_id == game["players"]["O"] else game["players"]["O"]
            
            # ذخیره پیام در تاریخچه چت
            game["chat_history"].append({
                "user_id": user_id,
                "message": update.message.text,
                "time": datetime.now().strftime("%H:%M:%S")
            })
            
            # ارسال پیام به حریف
            await application.bot.send_message(
                opponent_id,
                f"پیام از حریف: {update.message.text}"
            )

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    if len(data) != 4:
        return
    
    _, game_id, row, col = data
    row, col = int(row), int(col)
    
    if game_id not in games:
        await query.edit_message_text("این بازی دیگر معتبر نیست!")
        return
    
    game = games[game_id]
    
    # بررسی نوبت بازیکن
    if query.from_user.id != game["players"][game["current_player"]]:
        return
    
    # بررسی خالی بودن خانه
    if game["board"][row][col] != " ":
        return
    
    # انجام حرکت
    game["board"][row][col] = game["current_player"]
    
    # بررسی برنده
    winner = check_winner(game["board"])
    if winner:
        for player_id in game["players"].values():
            if winner == "tie":
                try:
                    await application.bot.edit_message_text(
                        chat_id=player_id,
                        message_id=query.message.message_id,
                        text="بازی مساوی شد!",
                        reply_markup=create_keyboard(game_id)
                    )
                except:
                    await application.bot.send_message(
                        player_id,
                        "بازی مساوی شد!",
                        reply_markup=create_keyboard(game_id)
                    )
            else:
                winner_id = game["players"][winner]
                try:
                    await application.bot.edit_message_text(
                        chat_id=player_id,
                        message_id=query.message.message_id,
                        text=f"{'شما برنده شدید!' if player_id == winner_id else 'شما باختید!'}",
                        reply_markup=create_keyboard(game_id)
                    )
                except:
                    await application.bot.send_message(
                        player_id,
                        f"{'شما برنده شدید!' if player_id == winner_id else 'شما باختید!'}",
                        reply_markup=create_keyboard(game_id)
                    )
            
            if player_id in player_games:
                del player_games[player_id]
        
        del games[game_id]
    else:
        game["current_player"] = "O" if game["current_player"] == "X" else "X"
        next_player_id = game["players"][game["current_player"]]
        
        # آپدیت صفحه برای هر دو بازیکن
        for player_id in game["players"].values():
            try:
                await application.bot.edit_message_text(
                    chat_id=player_id,
                    message_id=query.message.message_id,
                    text=f"{'نوبت شماست!' if player_id == next_player_id else 'نوبت حریف است!'}",
                    reply_markup=create_keyboard(game_id)
                )
            except:
                await application.bot.send_message(
                    player_id,
                    f"{'نوبت شماست!' if player_id == next_player_id else 'نوبت حریف است!'}",
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