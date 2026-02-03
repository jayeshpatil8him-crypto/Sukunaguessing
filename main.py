#!/usr/bin/env python3
import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from commands import (
    start, nguess, play, check_answer, score, 
    stop, leaderboard, cupload
)

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Start the bot."""
    # Get token from environment variable
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN environment variable not set!")
        raise ValueError("Please set BOT_TOKEN in .env file or environment variables")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("nguess", nguess))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("cupload", cupload))
    
    # Handle text messages for guessing
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    
    # Start the bot
    logger.info("🎮 Anime NGuess Bot is starting...")
    print("Bot is running... Press Ctrl+C to stop.")
    
    application.run_polling(allowed_updates=None)

if __name__ == '__main__':
    main()
