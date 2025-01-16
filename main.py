import telebot
import time
import os

TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)

loading_animations = [
    "▰▱▱▱▱▱▱▱▱▱",
    "▰▰▱▱▱▱▱▱▱▱", 
    "▰▰▰▱▱▱▱▱▱▱",
    "▰▰▰▰▱▱▱▱▱▱",
    "▰▰▰▰▰▱▱▱▱▱",
    "▰▰▰▰▰▰▱▱▱▱",
    "▰▰▰▰▰▰▰▱▱▱",
    "▰▰▰▰▰▰▰▰▱▱",
    "▰▰▰▰▰▰▰▰▰▱",
    "▰▰▰▰▰▰▰▰▰▰"
]

@bot.message_handler(commands=['start'])
def send_loading(message):
    loading_msg = bot.reply_to(message, "⏳ Starting process...\n▱▱▱▱▱▱▱▱▱▱ 0%")
    
    for i in range(0, 101, 10):
        animation = loading_animations[i//10]
        status = "⏳ Loading..." if i < 100 else "✅ Complete!"
        
        text = f"{status}\n{animation} {i}%"
        if i == 100:
            text += "\n\n🎉 Process finished successfully!"
            
        bot.edit_message_text(
            text,
            chat_id=loading_msg.chat.id,
            message_id=loading_msg.message_id
        )
        time.sleep(0.5)

bot.polling()