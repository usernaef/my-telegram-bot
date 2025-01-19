import os
import random
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()

# ذخیره‌سازی اطلاعات
games = {}  # {chat_id: Game}
user_private_chats = set()  # کاربرانی که ربات را استارت کرده‌اند

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
        self.players = {}  # {user_id: user_name}
        self.started = False
        self.word = None
        self.spy = None
        self.message_id = None
        self.start_time = None
        self.current_player_index = 0
        self.game_duration = None
        self.current_turn_message = None
        self.turn_timer = None

    @property
    def current_player(self):
        player_ids = list(self.players.keys())
        return player_ids[self.current_player_index]

    def get_next_player(self):
        player_ids = list(self.players.keys())
        self.current_player_index = (self.current_player_index + 1) % len(player_ids)
        return player_ids[self.current_player_index]

    async def update_player_list(self, context):
        keyboard = [
            [InlineKeyboardButton("پیوستن به بازی 🎮", callback_data="join_game")]
        ]
        if len(self.players) >= 3:
            keyboard.append([InlineKeyboardButton("شروع بازی 🎯", callback_data="start_game")])
        if not self.started:
            keyboard.append([InlineKeyboardButton("لغو بازی ❌", callback_data="cancel_game")])

        text = f"بازیکنان ({len(self.players)}/{self.max_players}):\n"
        for user_id, player_name in self.players.items():
            text += f"• {player_name}\n"

        if self.message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Error updating message: {e}")
        else:
            message = await context.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.message_id = message.message_id

    def assign_roles(self):
        self.word = random.choice(WORDS)
        self.spy = random.choice(list(self.players.keys()))

    def calculate_game_duration(self):
        return len(self.players)  # هر نفر یک دقیقه

    def is_game_over(self):
        current_time = datetime.now()
        return current_time - self.start_time >= timedelta(minutes=self.game_duration)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == 'private':
        user_private_chats.add(user_id)
        await update.message.reply_text(
            "سلام! من ربات بازی Spyfall هستم. من را به گروه خود اضافه کنید تا بازی را شروع کنیم!"
        )
        return

    if chat_id in games:
        await update.message.reply_text("یک بازی در حال حاضر در حال اجراست!")
        return

    games[chat_id] = SpyfallGame(chat_id, max_players=10, creator_id=user_id)
    games[chat_id].players[user_id] = update.effective_user.full_name
    await games[chat_id].update_player_list(context)

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in games:
        await query.answer("بازی وجود ندارد!")
        return

    game = games[chat_id]
    
    if game.started:
        await query.answer("بازی قبلاً شروع شده است!")
        return

    if user_id in game.players:
        await query.answer("شما قبلاً به بازی پیوسته‌اید!")
        return

    if len(game.players) >= game.max_players:
        await query.answer("بازی پر است!")
        return

    game.players[user_id] = query.from_user.full_name
    await game.update_player_list(context)
    await query.answer("شما به بازی پیوستید!")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in games:
        await query.answer("بازی وجود ندارد!")
        return

    game = games[chat_id]

    if user_id != game.creator_id:
        await query.answer("فقط سازنده بازی می‌تواند بازی را شروع کند!")
        return

    if len(game.players) < 3:
        await query.answer("حداقل 3 بازیکن برای شروع بازی نیاز است!")
        return

    if game.started:
        await query.answer("بازی قبلاً شروع شده است!")
        return

    game.started = True
    game.assign_roles()
    game.start_time = datetime.now()
    game.game_duration = game.calculate_game_duration()

    # ارسال نقش‌ها به بازیکنان
    for player_id in game.players:
        if player_id in user_private_chats:
            try:
                if player_id == game.spy:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text="شما جاسوس هستید! سعی کنید مکان را حدس بزنید."
                    )
                else:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=f"مکان: {game.word}"
                    )
            except Exception as e:
                logger.error(f"Error sending role to player {player_id}: {e}")

    # شروع نوبت‌ها
    await start_turn(context, chat_id)
    await query.answer("بازی شروع شد!")

async def start_turn(context, chat_id):
    game = games[chat_id]
    current_player = game.current_player
    player_name = game.players[current_player]

    if game.current_turn_message:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=game.current_turn_message)
        except Exception as e:
            logger.error(f"Error deleting turn message: {e}")

    keyboard = [[InlineKeyboardButton("نوبت بعدی ➡️", callback_data="next_turn")]]
    message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"نوبت {player_name} است که سؤال بپرسد!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    game.current_turn_message = message.message_id

async def next_turn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in games:
        await query.answer("بازی وجود ندارد!")
        return

    game = games[chat_id]

    if not game.started:
        await query.answer("بازی هنوز شروع نشده است!")
        return

    # بررسی زمان بازی
    elapsed_time = datetime.now() - game.start_time
    if elapsed_time.total_seconds() >= game.game_duration * 60:  # تبدیل دقیقه به ثانیه
        await end_game(context, chat_id, "جاسوس برنده شد! زمان تمام شد.")
        await query.answer("بازی به پایان رسید!")
        return

    game.get_next_player()
    await start_turn(context, chat_id)
    await query.answer("نوبت به بازیکن بعدی رسید!")

async def accuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("بازی وجود ندارد!")
        return

    game = games[chat_id]

    if not game.started:
        await update.message.reply_text("بازی هنوز شروع نشده است!")
        return

    if user_id not in game.players:
        await update.message.reply_text("شما در این بازی نیستید!")
        return

    keyboard = []
    row = []
    for player_id, player_name in game.players.items():
        if player_id != user_id:
            button = InlineKeyboardButton(
                player_name, 
                callback_data=f"suspect_{player_id}"
            )
            row.append(button)
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "چه کسی را به جاسوس بودن متهم می‌کنید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_accusation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    accuser_id = query.from_user.id
    suspect_id = int(query.data.split('_')[1])

    game = games[chat_id]

    if suspect_id == game.spy:
        await end_game(context, chat_id, f"بازی تمام شد! {game.players[accuser_id]} جاسوس را پیدا کرد!")
    else:
        await end_game(context, chat_id, f"جاسوس برنده شد! {game.players[accuser_id]} اشتباه حدس زد.")

    await query.answer()

async def end_game(context, chat_id, message):
    if chat_id in games:
        game = games[chat_id]
        spy_name = game.players[game.spy]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{message}\nجاسوس {spy_name} بود و مکان {game.word} بود."
        )
        del games[chat_id]

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

async def setup_webhook():
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

@app.on_event("startup")
async def on_startup():
    await setup_webhook()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("accuse", accuse))
    application.add_handler(CallbackQueryHandler(join_game, pattern="^join_game$"))
    application.add_handler(CallbackQueryHandler(start_game, pattern="^start_game$"))
    application.add_handler(CallbackQueryHandler(next_turn, pattern="^next_turn$"))
    application.add_handler(CallbackQueryHandler(handle_accusation, pattern="^suspect_"))

@app.on_event("shutdown")
async def on_shutdown():
    await application.bot.delete_webhook()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)