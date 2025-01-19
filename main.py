import os
import random
import logging
from typing import Dict
from datetime import datetime, timedelta
from asyncio import create_task, sleep
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest
from fastapi import FastAPI, Request

# تنظیمات اولیه
app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

# ذخیره‌سازی اطلاعات
games: Dict = {}
user_private_chats = set()

WORDS = [
    "درخت", "ماهیگیری", "ماه", "خورشید", "دریا", "دندان‌پزشک", "کوه", "رودخانه", 
    "جنگل", "آتش‌نشانی", "باغ‌وحش", "کتابخانه", "پارک", "ساحل", "قطار", 
    "فروشگاه", "آسمان", "گل", "پرنده", "ماشین", "دوچرخه", "تلفن", "رایانه",
    "مدرسه", "بیمارستان", "رستوران", "سینما", "استخر", "فرودگاه", "پارک",
    "موزه", "باشگاه", "کافه", "بازار", "ورزشگاه", "دانشگاه", "کتابفروشی"
]

class SpyfallGame:
    def __init__(self, chat_id: int, max_players: int, creator_id: int):
        self.chat_id = chat_id
        self.max_players = max_players
        self.creator_id = creator_id
        self.players = {}
        self.started = False
        self.word = None
        self.spy = None
        self.message_id = None
        self.start_time = None
        self.current_player_index = 0
        self.game_duration = None
        self.current_turn_message = None
        self.current_asker = None
        self.current_answerer = None
        self.turn_timer = None
        self.question_message = None

    @property
    def current_player(self):
        player_ids = list(self.players.keys())
        return player_ids[self.current_player_index]

    def get_next_player(self):
        player_ids = list(self.players.keys())
        self.current_player_index = (self.current_player_index + 1) % len(player_ids)
        return player_ids[self.current_player_index]

    async def start_turn_timer(self, context):
        if self.turn_timer:
            self.turn_timer.cancel()
        self.turn_timer = create_task(self.auto_next_turn(context))

    async def auto_next_turn(self, context):
        await sleep(30)  # 30 ثانیه زمان برای هر نوبت
        await self.force_next_turn(context)

    async def force_next_turn(self, context):
        if self.current_turn_message:
            try:
                await context.bot.delete_message(
                    chat_id=self.chat_id,
                    message_id=self.current_turn_message
                )
            except BadRequest:
                pass

        self.get_next_player()
        await start_turn(context, self.chat_id)

    async def update_player_list(self, context):
        keyboard = []
        if not self.started:
            keyboard.append([InlineKeyboardButton("پیوستن به بازی 🎮", callback_data="join_game")])
            if len(self.players) >= 3:
                keyboard.append([InlineKeyboardButton("شروع بازی 🎯", callback_data="start_game")])
            keyboard.append([InlineKeyboardButton("لغو بازی ❌", callback_data="cancel_game")])

        text = (
            f"🎲 بازی Spyfall\n\n"
            f"👥 بازیکنان ({len(self.players)}/{self.max_players}):\n"
        )
        for user_id, player_name in self.players.items():
            text += f"• {player_name}\n"

        try:
            if self.message_id:
                await context.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                message = await context.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                self.message_id = message.message_id
        except Exception as e:
            logger.error(f"Error in update_player_list: {e}")

    def assign_roles(self):
        self.word = random.choice(WORDS)
        self.spy = random.choice(list(self.players.keys()))

    def calculate_game_duration(self):
        return len(self.players) * 2  # 2 دقیقه برای هر بازیکن

    def is_game_over(self):
        if not self.start_time:
            return False
        current_time = datetime.now()
        return current_time - self.start_time >= timedelta(minutes=self.game_duration)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if update.effective_chat.type == 'private':
        user_private_chats.add(user_id)
        await update.message.reply_text(
            "🎮 به بازی Spyfall خوش آمدید!\n"
            "لطفاً مرا به گروه خود اضافه کرده و دستور /start را ارسال کنید."
        )
        return

    if chat_id in games:
        await update.message.reply_text("⚠️ یک بازی در حال اجراست!")
        return

    if user_id not in user_private_chats:
        msg = await update.message.reply_text(
            f"⚠️ [کاربر](tg://user?id={user_id}) لطفاً ابتدا ربات را در چت خصوصی /start کنید!",
            parse_mode='Markdown'
        )
        await sleep(3)
        await msg.delete()
        return

    games[chat_id] = SpyfallGame(chat_id, max_players=10, creator_id=user_id)
    games[chat_id].players[user_id] = update.effective_user.full_name
    await games[chat_id].update_player_list(context)

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if user_id not in user_private_chats:
        await query.answer("⚠️ لطفا ابتدا ربات را در چت خصوصی استارت کنید!")
        return

    if chat_id not in games:
        await query.answer("❌ بازی وجود ندارد!")
        return

    game = games[chat_id]
    
    if game.started:
        await query.answer("⚠️ بازی قبلاً شروع شده است!")
        return

    if user_id in game.players:
        await query.answer("⚠️ شما قبلاً به بازی پیوسته‌اید!")
        return

    if len(game.players) >= game.max_players:
        await query.answer("⚠️ بازی پر است!")
        return

    game.players[user_id] = query.from_user.full_name
    await game.update_player_list(context)
    await query.answer("✅ شما به بازی پیوستید!")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id not in games:
        await query.answer("❌ بازی وجود ندارد!")
        return
        
    game = games[chat_id]
    
    if user_id != game.creator_id:
        await query.answer("❌ فقط سازنده بازی می‌تواند بازی را شروع کند!")
        return
        
    if len(game.players) < 3:
        await query.answer("❌ حداقل 3 بازیکن برای شروع بازی نیاز است!")
        return
        
    if game.started:
        await query.answer("❌ بازی قبلاً شروع شده است!")
        return
    
    game.started = True
    game.start_time = datetime.now()
    game.assign_roles()
    game.game_duration = game.calculate_game_duration()
    
    for player_id in game.players:
        try:
            if player_id == game.spy:
                await context.bot.send_message(
                    chat_id=player_id,
                    text="🕵️‍♂️ شما جاسوس هستید!"
                )
            else:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"🎯 کلمه شما: {game.word}"
                )
        except Exception as e:
            logger.error(f"Error sending role to player: {e}")
    
    await query.message.edit_text(
        "🎮 بازی شروع شد!\n"
        "هر بازیکن نوبتی سؤال می‌پرسد."
    )
    
    await start_turn(context, chat_id)
    await query.answer()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        return
        
    game = games[chat_id]
    if not game.started:
        return

    if user_id != game.current_player:
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return

    if game.current_asker == user_id:
        keyboard = []
        for player_id, player_name in game.players.items():
            if player_id != user_id:
                keyboard.append([InlineKeyboardButton(
                    player_name, 
                    callback_data=f"ask_{player_id}"
                )])
        
        game.question_message = await update.message.reply_text(
            "چه کسی را برای پاسخ انتخاب می‌کنید؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif game.current_answerer == user_id:
        await update.message.reply_text(f"{game.players[user_id]} پاسخ داد!")
        game.current_answerer = None
        game.current_asker = user_id
        await game.force_next_turn(context)

async def ask_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    answerer_id = int(query.data.split('_')[1])
    
    game = games[chat_id]
    game.current_answerer = answerer_id
    game.current_asker = None
    
    if game.question_message:
        await game.question_message.delete()
    
    await query.message.reply_text(
        f"نوبت {game.players[answerer_id]} برای پاسخ است!"
    )
    await game.start_turn_timer(context)
    await query.answer()

async def start_turn(context, chat_id):
    game = games[chat_id]
    current_player = game.current_player
    player_name = game.players[current_player]
    game.current_asker = current_player

    if game.current_turn_message:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=game.current_turn_message
            )
        except Exception as e:
            logger.error(f"Error deleting turn message: {e}")

    if game.is_game_over():
        await end_game(context, chat_id, "⏰ زمان بازی تمام شد!")
        return

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎯 نوبت {player_name} است که سؤال بپرسد!"
    )
    game.current_turn_message = message.message_id
    await game.start_turn_timer(context)

async def cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id not in games:
        await query.answer("❌ بازی وجود ندارد!")
        return
        
    game = games[chat_id]
    
    if user_id != game.creator_id:
        await query.answer("❌ فقط سازنده بازی می‌تواند بازی را لغو کند!")
        return
    
    del games[chat_id]
    await query.message.edit_text("❌ بازی لغو شد!")
    await query.answer()

async def accuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ بازی در حال اجرا نیست!")
        return
        
    game = games[chat_id]
    
    if not game.started:
        await update.message.reply_text("❌ بازی هنوز شروع نشده است!")
        return
        
    if user_id not in game.players:
        await update.message.reply_text("❌ شما در این بازی نیستید!")
        return
    
    keyboard = []
    for player_id, player_name in game.players.items():
        if player_id != user_id:
            keyboard.append([InlineKeyboardButton(
                player_name,
                callback_data=f"suspect_{player_id}"
            )])
    
    await update.message.reply_text(
        "چه کسی را به عنوان جاسوس متهم می‌کنید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_accusation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    accuser_id = query.from_user.id
    suspect_id = int(query.data.split('_')[1])
    
    game = games[chat_id]
    
    if suspect_id == game.spy:
        await end_game(context, chat_id, 
            f"🎉 تبریک! {game.players[accuser_id]} جاسوس را پیدا کرد!")
    else:
        await query.message.edit_text(
            f"❌ اشتباه! {game.players[suspect_id]} جاسوس نبود!"
        )
    
    await query.answer()

async def end_game(context, chat_id, message):
    if chat_id in games:
        game = games[chat_id]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{message}\n\n"
                 f"🕵️‍♂️ جاسوس {game.players[game.spy]} بود\n"
                 f"📝 کلمه: {game.word}"
        )
        del games[chat_id]

@app.get("/")
async def root():
    return {"status": "running", "app": "Spyfall Bot"}

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_webhook():
    webhook_url = f"https://{RENDER_URL}/{TOKEN}"
    try:
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await setup_webhook()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("accuse", accuse))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(join_game, pattern="^join_game$"))
    application.add_handler(CallbackQueryHandler(start_game, pattern="^start_game$"))
    application.add_handler(CallbackQueryHandler(cancel_game, pattern="^cancel_game$"))
    application.add_handler(CallbackQueryHandler(ask_player, pattern="^ask_"))
    application.add_handler(CallbackQueryHandler(handle_accusation, pattern="^suspect_"))
    
    logger.info("Bot started successfully!")

@app.on_event("shutdown")
async def on_shutdown():
    await application.shutdown()
    await application.bot.delete_webhook()
    logger.info("Bot shut down successfully!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)