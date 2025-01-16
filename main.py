import os
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot import custom_filters
import time
import requests

print("Environment variables:", os.environ)
print("TOKEN value:", os.environ.get('TOKEN'))

TOKEN = os.environ.get('TOKEN')
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

class MyStates(StatesGroup):
    name = State()
    age = State()

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, 'سلام! به ربات خوش آمدید. برای شروع /register را وارد کنید.')

@bot.message_handler(commands=['register'])
def register(message):
    bot.set_state(message.from_user.id, MyStates.name, message.chat.id)
    bot.send_message(message.chat.id, "لطفا نام خود را وارد کنید:")

@bot.message_handler(state=MyStates.name)
def get_name(message):
    bot.send_message(message.chat.id, f'خوش آمدید {message.text}!')
    bot.set_state(message.from_user.id, MyStates.age, message.chat.id)
    bot.send_message(message.chat.id, "لطفا سن خود را وارد کنید:")

@bot.message_handler(state=MyStates.age)
def get_age(message):
    if not message.text.isdigit():
        bot.send_message(message.chat.id, 'لطفا فقط عدد وارد کنید!')
        return
    bot.send_message(message.chat.id, f'سن شما {message.text} است.')
    bot.delete_state(message.from_user.id, message.chat.id)

bot.add_custom_filter(custom_filters.StateFilter(bot))

while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(15)