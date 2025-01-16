import os
import telebot
import time

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
    
    for i in range(11):  # 0 to 10
        animation = loading_animations[i]
        percentage = i * 10
        status = "⏳ Loading..." if i < 10 else "✅ Complete!"
        
        text = f"{status}\n{animation} {percentage}%"
        if i == 10:
            text += "\n\n🎉 Process finished successfully!"
            
        bot.edit_message_text(
            text,
            chat_id=loading_msg.chat.id,
            message_id=loading_msg.message_id
        )
        time.sleep(0.5)

bot.polling()