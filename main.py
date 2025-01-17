import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from game_manager import GameManager
from messages import *

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ.get('RENDER_URL', '')
PORT = int(os.environ.get('PORT', 8080))

application = ApplicationBuilder().token(TOKEN).build()
game_manager = GameManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🕹 شروع بازی آنلاین")],
        [
            KeyboardButton("👥 دوستانه"),
            KeyboardButton("🎭 سناریو"),
            KeyboardButton("⚡️ چالش")
        ],
        [
            KeyboardButton("💰 سکه"),
            KeyboardButton("🌟 امتیازات"), 
            KeyboardButton("👤 پروفایل")
        ],
        [
            KeyboardButton("📣 مزایده"),
            KeyboardButton("🌐 سرور"),
            KeyboardButton("📚 راهنما")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_text = f"سلام {update.effective_user.first_name}! به ربات خوش آمدید."
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    username = update.effective_user.first_name

    if text == "🕹 شروع بازی آنلاین":
        success = game_manager.add_player(chat_id, user_id, username)
        if success:
            await send_game_status(update, context)
        else:
            await update.message.reply_text("شما قبلاً در یک بازی حضور دارید!")
async def send_game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game = game_manager.get_game_by_player(update.effective_user.id)
    if not game:
        return

    status_message = game.get_waiting_message()
    await update.message.reply_text(status_message)
    
    if game.is_full():
        await start_game(game)

async def start_game(game):
    game.assign_roles()
    game.start_game()
    
    for player in game.players:
        role_message = game.get_role_message(player)
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=role_message
        )
    
    await start_night(game)

async def start_night(game):
    game.start_night()
    
    for player in game.players:
        night_message = game.get_night_message(player)
        
        if game.can_player_kill(player):
            keyboard = game.get_kill_keyboard()
            await application.bot.send_message(
                chat_id=player.chat_id,
                text=night_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await application.bot.send_message(
                chat_id=player.chat_id,
                text=night_message
            )

async def handle_kill_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game = game_manager.get_game_by_player(query.from_user.id)
    
    if not game or not game.is_night:
        await query.answer("این عملیات دیگر معتبر نیست!")
        return

    target_id = int(query.data.split('_')[1])
    success = game.set_kill_target(query.from_user.id, target_id)
    
    if success:
        await notify_mafia_team(game, query.from_user.id, target_id)
        await query.answer("هدف با موفقیت انتخاب شد!")
    else:
        await query.answer("شما نمیتوانید این عملیات را انجام دهید!")

async def notify_mafia_team(game, killer_id, target_id):
    killer = game.get_player(killer_id)
    target = game.get_player(target_id)
    message = f"‏{killer.username} ({killer.role}) : ‏{target.username} را انتخاب کرد."
    
    for player in game.get_mafia_team():
        if player.user_id != killer_id:
            await application.bot.send_message(
                chat_id=player.chat_id,
                text=message
            )
async def check_night_end(game):
    if game.are_all_actions_complete():
        await end_night(game)

async def end_night(game):
    game.end_night()
    results = game.process_night_actions()
    
    for player in game.players:
        night_results = results.get_player_results(player)
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=night_results
        )
    
    if game.check_game_end():
        await end_game(game)
    else:
        await start_day(game)

async def start_day(game):
    game.start_day()
    day_message = game.get_day_message()
    
    for player in game.alive_players:
        keyboard = game.get_vote_keyboard()
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=day_message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game = game_manager.get_game_by_player(query.from_user.id)
    
    if not game or game.is_night:
        await query.answer("این عملیات دیگر معتبر نیست!")
        return

    target_id = int(query.data.split('_')[1])
    success = game.set_vote(query.from_user.id, target_id)
    
    if success:
        await notify_all_players_vote(game, query.from_user.id, target_id)
        await query.answer("رای شما ثبت شد!")
        
        if game.are_all_votes_complete():
            await end_day(game)
    else:
        await query.answer("شما نمیتوانید رای دهید!")

async def notify_all_players_vote(game, voter_id, target_id):
    voter = game.get_player(voter_id)
    target = game.get_player(target_id)
    message = f"‏{voter.username} به ‏{target.username} رای داد."
    
    for player in game.alive_players:
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=message
        )
async def end_day(game):
    execution_results = game.end_day()
    
    for player in game.players:
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=execution_results
        )
    
    if game.check_game_end():
        await end_game(game)
    else:
        await start_night(game)

async def end_game(game):
    end_message = game.get_end_game_message()
    
    for player in game.players:
        await application.bot.send_message(
            chat_id=player.chat_id,
            text=end_message
        )
    
    game_manager.end_game(game.group_id)

def main():
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newgame", new_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("startgame", start_game))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_role_action_callback, 
                                               pattern='^role_action_'))
    application.add_handler(CallbackQueryHandler(handle_vote_callback, 
                                               pattern='^vote_'))
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

# Error handling decorator
def handle_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            chat_id = args[0].effective_chat.id
            await application.bot.send_message(
                chat_id=chat_id,
                text="متاسفانه خطایی رخ داد. لطفا دوباره تلاش کنید."
            )
    return wrapper