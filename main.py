#!/usr/bin/env python3
import os
import json
import random
import asyncio
import logging
import re
from difflib import SequenceMatcher
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
user_data = {}      # user_id -> {score, coins, strikes, username}
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

def load_user_data():
    USER_FILE = "users.json"
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_data(data):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_random_character():
    data = load_data()
    if not data["characters"]:
        return None
    return random.choice(data["characters"])

# -------- TEXT MATCHING HELPERS --------
def clean_text(text):
    """Remove special characters and extra spaces"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)     # Remove extra spaces
    return text

def similarity(a, b):
    """Calculate similarity between two strings (0 to 1)"""
    a = clean_text(a)
    b = clean_text(b)
    return SequenceMatcher(None, a, b).ratio()

def is_correct_guess(guess, correct_answer):
    """Check if guess matches answer with fuzzy matching"""
    guess = clean_text(guess)
    correct = clean_text(correct_answer)
    
    # Direct match
    if guess == correct:
        return True
    
    # Similarity check (85% match)
    if similarity(guess, correct) >= 0.85:
        return True
    
    # Check if guess is in answer or answer is in guess
    if guess in correct or correct in guess:
        return True
    
    # Common variations
    variations = {
        'naruto uzumaki': ['naruto'],
        'sasuke uchiha': ['sasuke'],
        'monkey d luffy': ['luffy'],
        'roronoa zoro': ['zoro'],
        'light yagami': ['light'],
        'eren yeager': ['eren'],
        'levi ackerman': ['levi'],
        # Add more common variations as needed
    }
    
    for full_name, shorts in variations.items():
        if correct == clean_text(full_name) and guess in [clean_text(s) for s in shorts]:
            return True
    
    return False

# -------- COIN CALCULATION --------
def calculate_coins(strike_count):
    """Calculate coins earned based on strike"""
    base_coins = 20
    
    # Special bonuses for milestone strikes
    if strike_count == 10:
        return 200
    elif strike_count == 25:
        return 500
    elif strike_count == 50:
        return 1000
    elif strike_count == 59:  # Special 59th strike
        return 1000
    elif strike_count == 75:
        return 1200
    elif strike_count == 100:
        return 1500
    elif strike_count % 10 == 0:  # Every 10th strike
        return base_coins * 5
    else:
        return base_coins

# -------- COMMAND HANDLERS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Load user data
    global user_data
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            "username": user.username or user.first_name,
            "total_games": 0,
            "correct_answers": 0,
            "total_coins": 0,
            "best_strike": 0,
            "current_strike": 0
        }
        save_user_data(user_data)
    
    user_stats = user_data[str(user_id)]
    
    await update.message.reply_text(
        f"🎮 Welcome {user.first_name} to Anime Guess Bot!\n\n"
        f"💰 Your coins: {user_stats['total_coins']}\n"
        f"🏆 Best strike: {user_stats['best_strike']}\n"
        f"✅ Correct answers: {user_stats['correct_answers']}\n\n"
        "I'll show you anime character images and you have 15 seconds to guess!\n"
        "💰 Earn 20 coins per correct answer!\n"
        "🔥 Special bonuses at milestone strikes!\n\n"
        "📝 You can type just the first name (e.g., 'Naruto' for 'Naruto Uzumaki')\n\n"
        "Commands:\n"
        "/play - Start a new game\n"
        "/myprofile - Check your stats\n"
        "/shop - View shop\n"
        "/buy - Buy items\n"
        "/stop - Stop current game\n"
        "/leaderboard - Global leaderboard\n"
        "/addcharacter - Add new character (Owner only)"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new guessing game."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id in game_sessions:
        await update.message.reply_text("⚠️ A game is already running in this chat!")
        return

    character = get_random_character()
    if not character:
        await update.message.reply_text("❌ No characters added yet. Use /addcharacter to add some!")
        return

    # Load user data
    global user_data
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            "username": update.effective_user.username or update.effective_user.first_name,
            "total_games": 0,
            "correct_answers": 0,
            "total_coins": 0,
            "best_strike": 0,
            "current_strike": 0
        }

    game_sessions[chat_id] = {
        "answer": character["name"],
        "image_path": character["image"],
        "active": True,
        "user_id": user_id,
        "current_strike": user_data[str(user_id)]["current_strike"],
        "start_time": asyncio.get_event_loop().time()
    }

    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption=f"🎮 Guess this anime character!\n⏱️ 15 seconds\n"
                   f"🔥 Current strike: {user_data[str(user_id)]['current_strike']}\n"
                   f"💰 Next correct: {calculate_coins(user_data[str(user_id)]['current_strike'] + 1)} coins"
        )
    except FileNotFoundError:
        await update.message.reply_text("❌ Image not found! Skipping...")
        game_sessions.pop(chat_id, None)
        await play(update, context)
        return

    # Start timer
    await asyncio.sleep(15)

    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        game_sessions.pop(chat_id, None)
        user_data[str(user_id)]["current_strike"] = 0
        save_user_data(user_data)
        await context.bot.send_message(
            chat_id,
            "⏰ Time's up! Game over. Strike reset to 0."
        )

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in game_sessions:
        return

    guess = update.message.text.strip()
    correct = game_sessions[chat_id]["answer"]
    user_id = game_sessions[chat_id]["user_id"]
    
    if is_correct_guess(guess, correct):
        # Update user data
        current_strike = user_data[str(user_id)]["current_strike"] + 1
        coins_earned = calculate_coins(current_strike)
        
        user_data[str(user_id)]["correct_answers"] += 1
        user_data[str(user_id)]["total_coins"] += coins_earned
        user_data[str(user_id)]["current_strike"] = current_strike
        
        if current_strike > user_data[str(user_id)]["best_strike"]:
            user_data[str(user_id)]["best_strike"] = current_strike
        
        # Save updated data
        save_user_data(user_data)
        
        # Check for special milestones
        special_message = ""
        if current_strike == 10:
            special_message = "\n🎉 10-STRIKE BONUS! +200 coins!"
        elif current_strike == 25:
            special_message = "\n🌟 25-STRIKE BONUS! +500 coins!"
        elif current_strike == 50:
            special_message = "\n✨ 50-STRIKE BONUS! +1000 coins!"
        elif current_strike == 59:
            special_message = "\n🔥 59-STRIKE SPECIAL BONUS! +1000 coins!"
        elif current_strike == 75:
            special_message = "\n💎 75-STRIKE BONUS! +1200 coins!"
        elif current_strike == 100:
            special_message = "\n🏆 100-STRIKE LEGEND BONUS! +1500 coins!"
        
        await update.message.reply_text(
            f"✅ Correct! It was {correct.title()}!\n"
            f"🔥 Strike: {current_strike}\n"
            f"💰 +{coins_earned} coins! Total: {user_data[str(user_id)]['total_coins']}"
            f"{special_message}\n\n"
            f"Next character coming up..."
        )
        
        # End current game session
        game_sessions.pop(chat_id, None)
        
        # Start next round after short delay
        await asyncio.sleep(2)
        await play(update, context)
    else:
        # Wrong guess - show hint
        await update.message.reply_text(
            f"❌ Wrong! Try again.\n"
            f"Hint: The name starts with '{correct[0].upper()}'"
        )

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile and stats."""
    user = update.effective_user
    user_id = user.id
    
    global user_data
    if str(user_id) not in user_data:
        await update.message.reply_text("You haven't played yet! Use /play to start!")
        return
    
    stats = user_data[str(user_id)]
    
    await update.message.reply_text(
        f"👤 Profile: {stats['username']}\n\n"
        f"💰 Coins: {stats['total_coins']}\n"
        f"🔥 Current Strike: {stats['current_strike']}\n"
        f"🏆 Best Strike: {stats['best_strike']}\n"
        f"✅ Correct Answers: {stats['correct_answers']}\n"
        f"🎮 Total Games: {stats.get('total_games', 0)}\n\n"
        f"Next milestone rewards:\n"
        f"• 10 strikes: 200 coins\n"
        f"• 25 strikes: 500 coins\n"
        f"• 50 strikes: 1000 coins\n"
        f"• 59 strikes: 1000 coins\n"
        f"• 75 strikes: 1200 coins\n"
        f"• 100 strikes: 1500 coins"
    )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show shop items."""
    await update.message.reply_text(
        "🛒 Shop (Coming Soon!)\n\n"
        "Items will be added here!\n"
        "Use /buy <item> to purchase.\n\n"
        "Check back later for updates!"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy items from shop."""
    await update.message.reply_text(
        "🛒 Purchase system coming soon!\n"
        "Check /shop for available items."
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current game."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id in game_sessions:
        strike = user_data[str(user_id)]["current_strike"]
        game_sessions.pop(chat_id, None)
        user_data[str(user_id)]["current_strike"] = 0
        save_user_data(user_data)
        await update.message.reply_text(
            f"🛑 Game stopped!\n"
            f"Final strike: {strike}\n"
            f"Coins earned this session: {strike * 20}"
        )
    else:
        await update.message.reply_text("⚠️ No active game to stop.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard."""
    global user_data
    if not user_data:
        await update.message.reply_text("📊 No scores yet! Be the first to play!")
        return
    
    # Sort by coins
    sorted_users = sorted(user_data.items(), 
                         key=lambda x: x[1]["total_coins"], 
                         reverse=True)[:10]
    
    leaderboard_text = "🏆 Top 10 Players (by coins):\n\n"
    for i, (user_id, data) in enumerate(sorted_users, 1):
        username = data["username"][:15]  # Limit username length
        leaderboard_text += f"{i}. {username}\n"
        leaderboard_text += f"   💰 {data['total_coins']} coins | "
        leaderboard_text += f"🔥 {data['best_strike']} strikes\n\n"
    
    await update.message.reply_text(leaderboard_text)

async def addcharacter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload new character (Owner only)."""
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("❌ You are not allowed to add characters.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\nReply to an image with:\n/addcharacter <character name>\n\n"
            "Example:\n/addcharacter Naruto Uzumaki"
        )
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text(
            "❌ Reply to an IMAGE with:\n/addcharacter <character name>"
        )
        return

    char_name = " ".join(context.args).strip()
    
    # Create images directory
    os.makedirs("images", exist_ok=True)

    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()

    # Clean filename
    safe_name = re.sub(r'[^\w\s-]', '', char_name.lower())
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    
    image_path = f"images/{safe_name}.jpg"
    await file.download_to_drive(image_path)

    data = load_data()

    # Prevent duplicates (case insensitive)
    for c in data["characters"]:
        if c["name"].lower() == char_name.lower():
            await update.message.reply_text("⚠️ Character already exists!")
            return

    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    save_data(data)

    await update.message.reply_text(
        f"✅ Character '{char_name}' added successfully!\n"
        f"Saved as: {safe_name}.jpg"
    )

def main() -> None:
    """Start the bot."""
    # Get token from environment variable
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN environment variable not set!")
        raise ValueError("Please set BOT_TOKEN in .env file or environment variables")
    
    # Load user data at startup
    global user_data
    user_data = load_user_data()
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("myprofile", myprofile))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("addcharacter", addcharacter))
    
    # Handle text messages for guessing
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    
    # Start the bot
    logger.info("🎮 Anime NGuess Bot is starting...")
    print("Bot is running... Press Ctrl+C to stop.")
    
    application.run_polling(allowed_updates=None)

if __name__ == '__main__':
    main()
