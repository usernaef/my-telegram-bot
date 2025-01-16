import os
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import random
import time
import logging
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def main():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    server = Thread(target=run)
    server.start()

TOKEN = os.environ['TOKEN']

global_game = None
player_messages = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(name)

class Player:
    def init(self, user):
        self.user = user
        self.role = None
        self.is_alive = True
        self.has_voted = False
        self.has_used_ability = False
        self.votes = 0
        self.self_save_used = False
        self.wrong_shots = 0
        self.can_chat = True
        self.to_be_killed = False
        self.current_selection = None
        self.last_target = None

class GameRoom:
    def init(self):
        self.players = []
        self.is_started = False
        self.roles = ["پدرخوانده🚬", "دکتر💉", "کارآگاه🕵‍♂", "اسنایپر🔫", "ردگیر👣"]
        self.player_roles = {}
        self.day_count = 0
        self.is_day = True
        self.chat_enabled = True
        self.night_actions = {}
        self.voting_in_progress = False
        self.votes = {}
        self.doctor_save = None
        self.mafia_kill = None
        self.defense_mode = False
        self.defender = None
        self.defense_votes = {}
        self.final_voting = False
        self.chat_lock = False
        self.defense_time = False
        self.night_results = []

    def reset(self):
        self.init()

    def add_player(self, user):
        if len(self.players) < 5 and not any(p.user.id == user.id for p in self.players):
            player = Player(user)
            self.players.append(player)
            return True
        return False

    def assign_roles(self):
        random.shuffle(self.roles)
        for player in self.players:
            player.role = self.roles[self.players.index(player)]
            self.player_roles[player.user.id] = player.role

    def get_player_by_id(self, user_id):
        return next((p for p in self.players if p.user.id == user_id), None)

    def get_player_names(self):
        return [p.user.first_name for p in self.players if p.is_alive]

    def can_chat(self, user_id):
        player = self.get_player_by_id(user_id)
        if not player or not player.is_alive:
            return False
        if self.defense_time and player != self.defender:
            return False
        if self.chat_lock:
            return False
        return self.is_day and player.can_chat
def start(update, context):
    if not global_game.is_started:
        keyboard = [[InlineKeyboardButton("پیوستن به بازی 🎮", callback_data='join_game')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = "🎭 بازی مافیا (5 نفره)\n\nبازیکنان:\n"
        for i, player in enumerate(global_game.players, 1):
            message += f"{i}. {player.user.first_name}\n"
        message += f"\nتعداد بازیکنان: {len(global_game.players)}/5"
        sent_message = update.message.reply_text(message, reply_markup=reply_markup)
        context.chat_data['main_message'] = sent_message

def broadcast_to_players(context, message, exclude_user_id=None, include_sender=True):
    for player in global_game.players:
        if exclude_user_id and player.user.id == exclude_user_id and not include_sender:
            continue
        try:
            context.bot.send_message(chat_id=player.user.id, text=message)
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")

def update_all_messages(context):
    message = "🎭 بازی مافیا (5 نفره)\n\nبازیکنان:\n"
    for i, player in enumerate(global_game.players, 1):
        message += f"{i}. {player.user.first_name}\n"
    message += f"\nتعداد بازیکنان: {len(global_game.players)}/5"
    
    if len(global_game.players) == 5:
        message += "\n\n🎮 بازی به زودی شروع می‌شود!"

    keyboard = [[InlineKeyboardButton("پیوستن به بازی 🎮", callback_data='join_game')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for chat_id, msg in player_messages.items():
        try:
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error updating message: {e}")

def get_player_selection_keyboard(user_id, is_doctor=False):
    keyboard = []
    player = global_game.get_player_by_id(user_id)
    selected_index = player.current_selection if player else None
    
    for i, target in enumerate(global_game.players):
        if target.is_alive and target.user.id != user_id:
            name = target.user.first_name
            if i == selected_index:
                name += " ✅"
            keyboard.append([InlineKeyboardButton(name, callback_data=f'select_{i}')])
            
    if is_doctor:
        doctor = global_game.get_player_by_id(user_id)
        if doctor and not doctor.self_save_used:
            name = "💉 نجات خودم"
            if selected_index == -1:
                name += " ✅"
            keyboard.append([InlineKeyboardButton(name, callback_data='select_self')])
            
    keyboard.append([InlineKeyboardButton("تأیید انتخاب ✅", callback_data='confirm_selection')])
    return InlineKeyboardMarkup(keyboard)

def get_voting_keyboard(voter_id):
    keyboard = []
    voter = global_game.get_player_by_id(voter_id)
    current_vote = global_game.votes.get(voter_id)
    
    for i, player in enumerate(global_game.players):
        if player.is_alive and player.user.id != voter_id:
            name = f"🎗 {player.user.first_name}"
            if current_vote and current_vote == player:
                name += " ✅"
            keyboard.append([InlineKeyboardButton(name, callback_data=f'vote_{i}')])
    return InlineKeyboardMarkup(keyboard)

def get_defense_voting_keyboard(voter_id):
    current_vote = global_game.defense_votes.get(voter_id)
    keyboard = [
        [InlineKeyboardButton(
            f"گناهکار است ⚖️{' ✅' if current_vote else ''}", 
            callback_data='defense_guilty'
        )],
        [InlineKeyboardButton(
            f"بی‌گناه است ✨{' ✅' if current_vote == False else ''}", 
            callback_data='defense_innocent'
        )]
    ]
    return InlineKeyboardMarkup(keyboard)
def handle_role_selection(update, context, target_index):
    query = update.callback_query
    player = global_game.get_player_by_id(query.from_user.id)
    
    if not player or not player.is_alive:
        query.answer("شما نمی‌توانید از قابلیت خود استفاده کنید!")
        return

    if query.data == 'confirm_selection':
        if player.current_selection is None:
            query.answer("لطفاً ابتدا یک هدف انتخاب کنید!")
            return
        player.has_used_ability = True
        query.answer("انتخاب شما تأیید شد!")
        return

    if target_index == -1:
        if player.role != "دکتر💉" or player.self_save_used:
            query.answer("شما نمی‌توانید خود را نجات دهید!")
            return
        global_game.night_actions[player.user.id] = player
        player.self_save_used = True
    else:
        target = global_game.players[target_index]
        if not target.is_alive:
            query.answer("این بازیکن مرده است!")
            return
        global_game.night_actions[player.user.id] = target
        player.last_target = target

player.current_selection = target_index
    
    try:
        context.bot.edit_message_reply_markup(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=get_player_selection_keyboard(player.user.id, player.role == "دکتر💉")
        )
    except Exception as e:
        logger.error(f"Error updating keyboard: {e}")
        
    query.answer("هدف انتخاب شد. برای تأیید نهایی روی دکمه تأیید کلیک کنید.")

def process_night_actions(context):
    killed_players = set()
    saved_player = None
    mafia_target = None
    sniper_target = None
    detective_target = None
    tracker_info = {}
    
    # پردازش اقدام دکتر
    for player in global_game.players:
        if player.is_alive and player.role == "دکتر💉":
            target = global_game.night_actions.get(player.user.id)
            if target:
                saved_player = target
                context.bot.send_message(
                    chat_id=player.user.id,
                    text=f"💉 شما {target.user.first_name} را نجات دادید!"
                )
                break
    
    # پردازش اقدام پدرخوانده
    for player in global_game.players:
        if player.is_alive and player.role == "پدرخوانده🚬":
            target = global_game.night_actions.get(player.user.id)
            if target:
                mafia_target = target
                if target != saved_player:
                    killed_players.add(target)
                    context.bot.send_message(
                        chat_id=player.user.id,
                        text=f"🚬 شما {target.user.first_name} را هدف قرار دادید!"
                    )
                break
    
    # پردازش اقدام اسنایپر (اصلاح شده)
    for player in global_game.players:
        if player.is_alive and player.role == "اسنایپر🔫" and global_game.day_count >= 1:
            target = global_game.night_actions.get(player.user.id)
            if target and target.is_alive:
                sniper_target = target
                if target.role == "پدرخوانده🚬":
                    killed_players.add(target)
                    context.bot.send_message(
                        chat_id=player.user.id,
                        text=f"🎯 شلیک شما موفقیت‌آمیز بود! شما {target.user.first_name} را که مافیا بود، کشتید!"
                    )
                else:
                    player.wrong_shots += 1
                    context.bot.send_message(
                        chat_id=player.user.id,
                        text=f"❌ شلیک شما اشتباه بود! {target.user.first_name} مافیا نبود!"
                    )
                    if player.wrong_shots >= 2:
                        killed_players.add(player)
                        context.bot.send_message(
                            chat_id=player.user.id,
                            text="☠️ شما به دلیل دو اشتباه در شلیک کشته شدید!"
                        )
                break
    
    # پردازش اقدام کارآگاه
    for player in global_game.players:
        if player.is_alive and player.role == "کارآگاه🕵‍♂":
            target = global_game.night_actions.get(player.user.id)
            if target:
                detective_target = target
                is_mafia = "مافیا" if target.role == "پدرخوانده🚬" else "شهروند"
                context.bot.send_message(
                    chat_id=player.user.id,
                    text=f"🔍 نتیجه استعلام شما: {target.user.first_name} {is_mafia} است!"
                )
    
    # پردازش اقدام ردگیر
    for player in global_game.players:
        if player.is_alive and player.role == "ردگیر👣":
            target = global_game.night_actions.get(player.user.id)
            if target and target.last_target:
                tracker_info[player.user.id] = f"👣 {target.user.first_name} دیشب به سراغ {target.last_target.user.first_name} رفته است!"

# اعلام نتایج شب
    deaths_reported = False
    for player in killed_players:
        if player.is_alive:
            player.is_alive = False
            broadcast_to_players(context, f"☠️ {player.user.first_name} کشته شد!")
            deaths_reported = True

    if not deaths_reported:
        broadcast_to_players(context, "🌅 دیشب کسی کشته نشد!")
    
    # ارسال اطلاعات به ردگیر
    for tracker_id, info in tracker_info.items():
        context.bot.send_message(chat_id=tracker_id, text=info)
    
    # پاکسازی اطلاعات شب
    global_game.night_actions.clear()
    for player in global_game.players:
        player.current_selection = None
        player.has_used_ability = False
def handle_vote(update, context, player_index):
    query = update.callback_query
    voter_id = query.from_user.id
    voter = global_game.get_player_by_id(voter_id)
    
    if not voter or not voter.is_alive:
        query.answer("شما نمی‌توانید رای دهید!")
        return
        
    target = global_game.players[player_index]
    if not target.is_alive:
        query.answer("این بازیکن مرده است!")
        return

    if voter.has_voted:
        old_target = global_game.votes.get(voter_id)
        if old_target:
            old_target.votes -= 1
            
    voter.has_voted = True
    target.votes += 1
    global_game.votes[voter_id] = target
    
    try:
        context.bot.edit_message_reply_markup(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=get_voting_keyboard(voter_id)
        )
    except Exception as e:
        logger.error(f"Error updating keyboard: {e}")
        
    broadcast_to_players(context, f"🗳️ {voter.user.first_name} به {target.user.first_name} رای داد!")
    query.answer("رای شما ثبت شد!")

def handle_defense_vote(update, context, vote_type):
    query = update.callback_query
    voter_id = query.from_user.id
    voter = global_game.get_player_by_id(voter_id)
    
    if not voter or not voter.is_alive or voter == global_game.defender:
        query.answer("شما نمی‌توانید رای دهید!")
        return
        
    global_game.defense_votes[voter_id] = vote_type == 'guilty'
    
    try:
        context.bot.edit_message_reply_markup(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=get_defense_voting_keyboard(voter_id)
        )
    except Exception as e:
        logger.error(f"Error updating keyboard: {e}")
        
    query.answer("رای شما ثبت شد!")

def handle_chat(update, context):
    user_id = update.message.from_user.id
    if global_game.defense_time:
        defender = global_game.defender
        if defender and defender.user.id == user_id:
            message = f"🎗 {update.message.from_user.first_name}: {update.message.text}"
            broadcast_to_players(context, message, user_id, True)
            return
            
    if global_game.can_chat(user_id):
        message = f"🎗 {update.message.from_user.first_name}: {update.message.text}"
        broadcast_to_players(context, message, user_id, True)
    else:
        try:
            update.message.delete()
            msg = context.bot.send_message(
                chat_id=user_id,
                text="⚠️ در حال حاضر نمیتوانید صحبت کنید"
            )
            time.sleep(1)
            context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        except:
            pass

def start_voting(context):
    global_game.voting_in_progress = True
    global_game.votes.clear()
    global_game.chat_lock = True
    broadcast_to_players(context, "🗳️ زمان رای‌گیری فرا رسیده است!")
    
    for player in global_game.players:
        if player.is_alive:
            player.has_voted = False
            player.votes = 0

try:
                context.bot.send_message(
                    chat_id=player.user.id,
                    text="🗳️ به چه کسی رای می‌دهید؟",
                    reply_markup=get_voting_keyboard(player.user.id)
                )
            except Exception as e:
                logger.error(f"Error sending voting message: {e}")

def check_voting_threshold():
    max_votes = max((p.votes for p in global_game.players if p.is_alive), default=0)
    if max_votes >= 2:  # حداقل 2 رای برای رفتن به دفاع
        accused_players = [p for p in global_game.players if p.votes == max_votes]
        if len(accused_players) == 1:
            return accused_players[0]
    return None

def night_phase(context):
    global_game.is_day = False
    global_game.chat_lock = True
    broadcast_to_players(context, "🌙 شب فرا رسید...")
    
    for player in global_game.players:
        if player.is_alive:
            player.has_used_ability = False
            player.current_selection = None
            is_doctor = player.role == "دکتر💉"
            context.bot.send_message(
                chat_id=player.user.id,
                text="🎯 هدف خود را انتخاب کنید:",
                reply_markup=get_player_selection_keyboard(player.user.id, is_doctor)
            )
    
    time.sleep(30)
    process_night_actions(context)
def day_phase(context):
    global_game.is_day = True
    global_game.chat_lock = False
    broadcast_to_players(context, f"☀️ روز {global_game.day_count} شروع شد!")
    
    time.sleep(60)  # زمان بحث
    start_voting(context)
    
    voting_end_time = time.time() + 30  # زمان رای‌گیری
    accused = None
    
    while time.time() < voting_end_time:
        accused = check_voting_threshold()
        if accused:
            break
        time.sleep(1)
    
    if accused:
        global_game.defender = accused
        global_game.defense_time = True
        broadcast_to_players(context, f"⚖️ {accused.user.first_name} به دفاع می‌رود!")
        
        time.sleep(30)  # زمان دفاع
        
        global_game.defense_time = False
        global_game.defense_votes.clear()
        
        for player in global_game.players:
            if player.is_alive and player != accused:
                context.bot.send_message(
                    chat_id=player.user.id,
                    text="⚖️ رای نهایی خود را اعلام کنید:",
                    reply_markup=get_defense_voting_keyboard(player.user.id)
                )
        
        time.sleep(20)  # زمان رای‌گیری نهایی
        
        guilty_votes = sum(1 for vote in global_game.defense_votes.values() if vote)
        innocent_votes = sum(1 for vote in global_game.defense_votes.values() if not vote)
        
        if guilty_votes > innocent_votes and guilty_votes >= 2:
            accused.is_alive = False
            broadcast_to_players(context, f"⚰️ {accused.user.first_name} اعدام شد!")
        else:
            broadcast_to_players(context, f"✨ {accused.user.first_name} تبرئه شد!")
    
    global_game.votes.clear()
    global_game.voting_in_progress = False
    for player in global_game.players:
        player.has_voted = False
        player.votes = 0

def check_game_end(context):
    mafia_count = sum(1 for p in global_game.players if p.is_alive and p.role == "پدرخوانده🚬")
    citizen_count = sum(1 for p in global_game.players if p.is_alive and p.role != "پدرخوانده🚬")
    
    if mafia_count == 0:
        broadcast_to_players(context, "🎉 شهروندان پیروز شدند!")
        global_game.reset()
        return True
    elif mafia_count >= citizen_count:
        broadcast_to_players(context, "🎭 مافیا پیروز شد!")
        global_game.reset()
        return True
    return False

def run_game(context):
    global_game.is_started = True
    
    # اعلام نقش‌ها به بازیکنان

for player in global_game.players:
        context.bot.send_message(chat_id=player.user.id, text=f"نقش شما: {player.role}")
    
    broadcast_to_players(context, "👋 25 ثانیه زمان برای آشنایی...")
    time.sleep(25)
    
    while True:
        night_phase(context)
        if check_game_end(context):
            break
            
        global_game.day_count += 1
        day_phase(context)
        if check_game_end(context):
            break

def button_callback(update, context):
    query = update.callback_query
    try:
        if query.data == 'join_game':
            if global_game.add_player(query.from_user):
                player_messages[query.message.chat_id] = query.message
                if len(global_game.players) == 5:
                    global_game.assign_roles()
                    context.job_queue.run_once(lambda ctx: run_game(ctx), 1)
                update_all_messages(context)
                query.answer("به بازی پیوستید!")
            else:
                query.answer("نمی‌توانید به بازی بپیوندید!")
        elif query.data.startswith('select_'):
            if query.data == 'select_self':
                handle_role_selection(update, context, -1)
            else:
                player_index = int(query.data.split('_')[1])
                handle_role_selection(update, context, player_index)
        elif query.data == 'confirm_selection':
            handle_role_selection(update, context, None)
        elif query.data.startswith('vote_'):
            player_index = int(query.data.split('_')[1])
            handle_vote(update, context, player_index)
        elif query.data.startswith('defense_'):
            vote_type = query.data.split('_')[1]
            handle_defense_vote(update, context, vote_type)
    except Exception as e:
        logger.error(f"Error in button callback: {e}")

def main():
    global global_game
    global_game = GameRoom()
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_chat))

    keep_alive()
    updater.start_polling()
    print("Bot started successfully!")
    updater.idle()

if __name__ == "__main__":
    main()