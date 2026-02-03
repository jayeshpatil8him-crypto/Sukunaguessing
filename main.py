#!/usr/bin/env python3
import os
import json
import random
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= GAME VARIABLES =================
game_sessions = {}  # chat_id -> game data
scores = {}  # user_id -> score data
# ==================================================

# -------- DATA HELPERS --------
def load_data():
    DATA_FILE = "data.json"
    if not os.path.exists(DATA_FILE):
        return {"characters": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_random_character():
    data = load_data()
    if not data["characters"]:
        return None
    return random.choice(data["characters"])

# -------- COMMAND HANDLERS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"🎮 Welcome {user.first_name} to Anime Guess Bot!\n\n"
        "I'll show you anime character images and you have 15 seconds to guess!\n"
        "Try to make the longest strike of correct guesses!\n\n"
        "Commands:\n"
        "/nguess or /play - Start a new game\n"
        "/score - Check your score\n"
        "/stop - Stop current game\n"
        "/leaderboard - Global leaderboard"
    )

async def nguess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id in game_sessions:
        await update.message.reply_text("⚠️ A game is already running!")
        return

    character = get_random_character()
    if not character:
        await update.message.reply_text("❌ No characters added yet.")
        return

    game_sessions[chat_id] = {
        "answer": character["name"],
        "active": True,
        "user_id": user_id,
        "strikes": 0
    }

    # Send the character image
    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption="🎮 Guess the anime character!\n⏱️ 15 seconds"
        )
    except FileNotFoundError:
        await update.message.reply_text("❌ Image not found! Skipping...")
        game_sessions.pop(chat_id, None)
        await nguess(update, context)
        return

    # Start timer
    await asyncio.sleep(15)

    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        game_sessions.pop(chat_id, None)
        await context.bot.send_message(
            chat_id,
            "⏰ Time's up! Game over."
        )

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in game_sessions:
        return

    guess = update.message.text.strip().lower()
    correct = game_sessions[chat_id]["answer"]

    if guess == correct:
        user_id = game_sessions[chat_id]["user_id"]
        strikes = game_sessions[chat_id]["strikes"] + 1
        
        # Update score
        if user_id not in scores:
            scores[user_id] = {"total": 0, "strikes": 0, "username": update.effective_user.username}
        scores[user_id]["total"] += 1
        scores[user_id]["strikes"] = max(scores[user_id]["strikes"], strikes)
        
        game_sessions[chat_id]["strikes"] = strikes
        
        await update.message.reply_text(f"✅ Correct! Strike: {strikes} 🔥")
        # Start next round
        await asyncio.sleep(1)
        await nguess(update, context)

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show player score."""
    user_id = update.effective_user.id
    
    if user_id in scores:
        user_score = scores[user_id]
        await update.message.reply_text(
            f"🏆 Your Score:\n"
            f"Total Correct: {user_score['total']}\n"
            f"Best Strike: {user_score['strikes']} 🔥"
        )
    else:
        await update.message.reply_text("📊 You haven't played yet! Use /nguess to start!")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for nguess."""
    await nguess(update, context)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current game."""
    chat_id = update.effective_chat.id
    
    if chat_id in game_sessions:
        strikes = game_sessions[chat_id]["strikes"]
        game_sessions.pop(chat_id, None)
        await update.message.reply_text(f"🛑 Game stopped! Final strike: {strikes}")
    else:
        await update.message.reply_text("⚠️ No active game to stop.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard."""
    if not scores:
        await update.message.reply_text("📊 No scores yet! Be the first to play!")
        return
    
    # Sort by total score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
    
    leaderboard_text = "🏆 Top 10 Players:\n\n"
    for i, (user_id, data) in enumerate(sorted_scores, 1):
        username = data["username"] or f"User{user_id}"
        leaderboard_text += f"{i}. {username}\n"
        leaderboard_text += f"   Score: {data['total']} | Best Strike: {data['strikes']} 🔥\n\n"
    
    await update.message.reply_text(leaderboard_text)

async def cupload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload new character (Owner only)."""
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not allowed to upload characters.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\nReply to an image with:\n/cupload <character name>"
        )
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text(
            "❌ Reply to an IMAGE with:\n/cupload <character name>"
        )
        return

    char_name = " ".join(context.args).strip().lower()
    
    # Create images directory
    os.makedirs("images", exist_ok=True)

    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()

    image_path = f"images/{char_name.replace(' ', '_')}.jpg"
    await file.download_to_drive(image_path)

    data = load_data()

    # Prevent duplicates
    for c in data["characters"]:
        if c["name"] == char_name:
            await update.message.reply_text("⚠️ Character already exists.")
            return

    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    save_data(data)

    await update.message.reply_text(
        f"✅ Character {char_name.title()} added successfully!"
    )

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
