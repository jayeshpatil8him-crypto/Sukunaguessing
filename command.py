from telebot import TeleBot
from telebot.types import BotCommand
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv('8464370713:AAEB6sOM3pJvBinF09M4vpYuVxrQcM4pFjs')
bot = TeleBot(TOKEN)

def register_commands(bot: TeleBot):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("hello", "Hello"),
        BotCommand("cguess", "ok")
    ]
    
    bot.set_my_commands(commands)

register_commands(bot)
