import os
import random
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# تنظیمات اولیه
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

# لیست مکان‌ها و نقش‌ها
LOCATIONS = {
    "هواپیما": ["خلبان", "مهماندار", "مسافر درجه یک", "مکانیک پرواز", "مارشال هوایی", "مسافر عادی"],
    "بیمارستان": ["دکتر", "پرستار", "بیمار", "جراح", "داروساز", "مسئول پذیرش"],
    "مدرسه": ["معلم", "دانش‌آموز", "مدیر", "سرایدار", "مشاور", "معاون"],
    "رستوران": ["سرآشپز", "گارسون", "مشتری", "صندوقدار", "ظرفشور", "نظافتچی"],
    "هتل": ["مدیر هتل", "پیشخدمت", "مهمان", "نگهبان", "خدمتکار", "راننده"],
    "سینما": ["فروشنده بلیط", "تماشاگر", "مدیر سالن", "اپراتور فیلم", "فروشنده تنقلات", "نظافتچی"],
    "استخر": ["نجات غریق", "شناگر", "مربی شنا", "مسئول رختکن", "فروشنده بلیط", "تعمیرکار"],
    "بانک": ["رئیس شعبه", "کارمند", "مشتری", "نگهبان", "حسابدار", "صندوقدار"]
}

class SpyfallGame:
    def __init__(self, chat_id: int, max_players: int):
        self.chat_id = chat_id
        self.max_players = max_players
        self.players = {}  # {user_id: user_name}
        self.started = False
        self.location = None
        self.roles = {}  # {user_id: role}
        self.spy = None
        self.message_id = None
        self.start_time = None
        self.votes = {}  # {voter_id: voted_id}
        self.scores = {}  # {user_id: score}
        self.game_duration = None

    async def update_player_list(self, context):
        keyboard = [
            [InlineKeyboardButton("پیوستن به بازی 🎮", callback_data="join_game")]
        ]
        if len(self.players) >= 4:
            keyboard.append([InlineKeyboardButton("شروع بازی 🎯", callback_data="start_game")])

        text = f"بازیکنان ({len(self.players)}/{self.max_players}):\n"
        for player_name in self.players.values():
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
        self.location = random.choice(list(LOCATIONS.keys()))
        available_roles = LOCATIONS[self.location].copy()
        self.spy = random.choice(list(self.players.keys()))
        
        for player_id in self.players:
            if player_id == self.spy:
                self.roles[player_id] = "جاسوس"
            else:
                role = random.choice(available_roles)
                available_roles.remove(role)
                self.roles[player_id] = role

    def calculate_game_duration(self):
        player_count = len(self.players)
        if player_count <= 6:
            return 6
        elif player_count <= 8:
            return 8
        else:
            return 10

    def is_game_over(self):
        current_time = datetime.now()
        return current_time - self.start_time >= timedelta(minutes=self.game_duration)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        user_private_chats.add(update.effective_user.id)
        await update.message.reply_text(
            "🕵️‍♂️ به بازی Spyfall خوش آمدید!\n"
            "شما می‌توانید در گروه‌ها با دستور /newgame بازی جدید ایجاد کنید.\n\n"
            "🎮 قوانین بازی:\n"
            "1. یک نفر جاسوس است و بقیه شهروند هستند\n"
            "2. هر شهروند یک نقش و مکان مشخص دارد\n"
            "3. جاسوس باید مکان را حدس بزند\n"
            "4. شهروندان باید جاسوس را پیدا کنند\n"
            "5. از طریق پرسش و پاسخ باید به هدفتان برسید"
        )
    else:
        await update.message.reply_text(
            "لطفاً ابتدا ربات را در چت خصوصی استارت کنید!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("شروع ربات 🤖", url=f"https://t.me/{context.bot.username}")
            ]])
        )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.message.chat.type == "private":
        await update.message.reply_text("این دستور فقط در گروه‌ها قابل استفاده است!")
        return

    if user_id not in user_private_chats:
        await update.message.reply_text(
            "لطفاً ابتدا ربات را در چت خصوصی استارت کنید!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("شروع ربات 🤖", url=f"https://t.me/{context.bot.username}")
            ]])
        )
        return

    if chat_id in games:
        await update.message.reply_text("یک بازی در حال اجراست! لطفاً صبر کنید تا تمام شود.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{i} نفره", callback_data=f"create_game_{i}") for i in range(4, 9, 2)]
    ]
    await update.message.reply_text(
        "تعداد بازیکنان را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    
    await query.answer()

    if query.data.startswith("create_game_"):
        max_players = int(query.data.split("_")[2])
        games[chat_id] = SpyfallGame(chat_id, max_players)
        await games[chat_id].update_player_list(context)

    elif query.data == "join_game":
        if chat_id not in games:
            await query.message.reply_text("بازی موجود نیست!")
            return

        game = games[chat_id]
        
        if user_id not in user_private_chats:
            await query.message.reply_text(
                "لطفاً ابتدا ربات را در چت خصوصی استارت کنید!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("شروع ربات 🤖", url=f"https://t.me/{context.bot.username}")
                ]])
            )
            return

        if game.started:
            await query.message.reply_text("بازی شروع شده است!")
            return

        if len(game.players) >= game.max_players:
            await query.message.reply_text("بازی پر است!")
            return

        if user_id not in game.players:
            game.players[user_id] = query.from_user.first_name
            await game.update_player_list(context)

    elif query.data == "start_game":
        if chat_id not in games:
            await query.message.reply_text("بازی موجود نیست!")
            return

        game = games[chat_id]
        
        if len(game.players) < 4:
            await query.message.reply_text("حداقل 4 بازیکن نیاز است!")
            return

        if game.started:
            await query.message.reply_text("بازی قبلاً شروع شده است!")
            return

        game.started = True
        game.assign_roles()
        game.start_time = datetime.now()
        game.game_duration = game.calculate_game_duration()

        # ارسال نقش‌ها به بازیکنان
        for player_id, role in game.roles.items():
            if player_id == game.spy:
                await context.bot.send_message(
                    chat_id=player_id,
                    text="🕵️‍♂️ شما جاسوس هستید! باید مکان را حدس بزنید."
                )
            else:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"📍 مکان: {game.location}\n👤 نقش شما: {role}"
                )

        await query.message.edit_text(
            f"🎮 بازی شروع شد!\n"
            f"⏱ زمان بازی: {game.game_duration} دقیقه\n"
            f"تعداد بازیکنان: {len(game.players)}\n\n"
            "از طریق پرسش و پاسخ، جاسوس را پیدا کنید!"
        )

async def setup_webhook():
    if RENDER_URL:
        webhook_url = f"https://{RENDER_URL}/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.warning("RENDER_URL not set")

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await setup_webhook()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newgame", new_game))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Bot started successfully!")

@app.post(f"/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "running"}

@app.on_event("shutdown")
async def shutdown_event():
    await application.shutdown()
    logger.info("Bot shut down successfully!")