#!/usr/bin/env python3
import os
import json
import random
import asyncio
import logging
import re
import time
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
current_game = None  # Store current game
user_data = {}       # Store user progress
# ==================================================

# -------- DATA HELPERS --------
def load_game_data():
    """Load characters data"""
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"characters": []}

def save_game_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_user_data():
    """Load user data"""
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_user_data(data):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# -------- COIN SYSTEM --------
def calculate_coins(strike):
    """Calculate coins earned based on strike"""
    base_coins = 20
    
    # Special milestone bonuses
    if strike == 10:
        return 200
    elif strike == 25:
        return 500
    elif strike == 50:
        return 1000
    elif strike == 59:
        return 1000
    elif strike == 75:
        return 1200
    elif strike == 100:
        return 1500
    elif strike % 10 == 0:  # Every 10th strike bonus
        return base_coins * 5
    else:
        return base_coins

def get_milestone_bonus(strike):
    """Get special milestone message"""
    bonuses = {
        10: "🎉 10-STRIKE BONUS! +200 coins!",
        25: "🌟 25-STRIKE BONUS! +500 coins!",
        50: "✨ 50-STRIKE BONUS! +1000 coins!",
        59: "🔥 59-STRIKE SPECIAL! +1000 coins!",
        75: "💎 75-STRIKE BONUS! +1200 coins!",
        100: "🏆 100-STRIKE LEGEND! +1500 coins!"
    }
    return bonuses.get(strike, "")

# -------- MATCHING SYSTEM --------
def is_correct_guess(user_input, correct_name):
    """Flexible matching system"""
    user_clean = user_input.lower().strip()
    correct_clean = correct_name.lower().strip()
    
    # Remove punctuation
    user_clean = re.sub(r'[^\w\s]', '', user_clean)
    correct_clean = re.sub(r'[^\w\s]', '', correct_clean)
    
    # Exact match
    if user_clean == correct_clean:
        return True
    
    # Word-by-word matching
    user_words = set(user_clean.split())
    correct_words = set(correct_clean.split())
    
    # If any word matches
    if user_words & correct_words:
        return True
    
    # Common nickname mapping
    nicknames = {
        'naruto': ['naruto uzumaki'],
        'sasuke': ['sasuke uchiha'],
        'luffy': ['monkey d luffy'],
        'zoro': ['roronoa zoro'],
        'light': ['light yagami'],
        'eren': ['eren yeager'],
        'levi': ['levi ackerman'],
        'yae': ['yae miko'],
        'miko': ['yae miko'],
        # Add more as needed
    }
    
    # Check nicknames
    for nick, full_names in nicknames.items():
        if user_clean == nick and correct_clean in full_names:
            return True
    
    return False

# -------- COMMAND HANDLERS --------
async def sstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with 's' prefix"""
    user = update.effective_user
    user_id = str(user.id)
    
    # Load user data
    global user_data
    user_data = load_user_data()
    
    # Initialize user if new
    if user_id not in user_data:
        user_data[user_id] = {
            "username": user.username or user.first_name,
            "coins": 0,
            "total_correct": 0,
            "best_strike": 0,
            "current_strike": 0,
            "games_played": 0
        }
        save_user_data(user_data)
    
    stats = user_data[user_id]
    
    await update.message.reply_text(
        f"✨ Welcome {user.first_name} to Anime NGuess! ✨\n\n"
        f"💰 <b>Your Coins:</b> {stats['coins']}\n"
        f"🔥 <b>Current Strike:</b> {stats['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {stats['best_strike']}\n"
        f"✅ <b>Correct Answers:</b> {stats['total_correct']}\n\n"
        
        "🎮 <b>How to Play:</b>\n"
        "1. Use /splay to start game\n"
        "2. Guess the anime character\n"
        "3. Earn coins and build your strike!\n\n"
        
        "💰 <b>Coin System:</b>\n"
        "• +20 coins per correct answer\n"
        "• Special bonuses at milestones!\n\n"
        
        "📜 <b>Commands:</b>\n"
        "/splay - Start new game\n"
        "/sprofile - Check your stats\n"
        "/sleaderboard - Top players\n"
        "/sadd - Add character (Owner)\n"
        "/slist - List all characters\n"
        "/sshop - View shop (Coming Soon)\n",
        parse_mode="HTML"
    )

async def splay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new game"""
    global current_game, user_data
    
    # Check if game already running
    if current_game:
        await update.message.reply_text("⚠️ A game is already running! Guess the character.")
        return
    
    # Load characters
    data = load_game_data()
    if not data.get("characters"):
        await update.message.reply_text("❌ No characters added yet!")
        return
    
    # Pick random character
    character = random.choice(data["characters"])
    
    # Load user data
    user_data = load_user_data()
    user_id = str(update.effective_user.id)
    
    # Initialize user if new
    if user_id not in user_data:
        user_data[user_id] = {
            "username": update.effective_user.username or update.effective_user.first_name,
            "coins": 0,
            "total_correct": 0,
            "best_strike": 0,
            "current_strike": 0,
            "games_played": 0
        }
    
    # Start game
    current_game = {
        "answer": character["name"],
        "chat_id": update.effective_chat.id,
        "user_id": user_id,
        "start_time": time.time()
    }
    
    print(f"\n🎮 Game Started:")
    print(f"Answer: {character['name']}")
    print(f"User: {user_id}")
    print(f"Current Strike: {user_data[user_id]['current_strike']}")
    
    # Send image WITHOUT revealing answer
    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption=f"🎮 <b>Guess the Anime Character!</b>\n"
                   f"⏱️ <b>30 seconds</b>\n"
                   f"🔥 <b>Current Strike:</b> {user_data[user_id]['current_strike']}\n"
                   f"💰 <b>Next Correct:</b> {calculate_coins(user_data[user_id]['current_strike'] + 1)} coins",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error loading image: {e}")
        current_game = None
        return
    
    # 30-second timer
    await asyncio.sleep(30)
    
    # Check if game still active
    if current_game and current_game["chat_id"] == update.effective_chat.id:
        await update.message.reply_text(
            f"⏰ <b>Time's up!</b>\n"
            f"The character was: <b>{character['name']}</b>\n"
            f"❌ Strike reset to 0!",
            parse_mode="HTML"
        )
        # Reset strike
        if user_id in user_data:
            user_data[user_id]["current_strike"] = 0
            save_user_data(user_data)
        current_game = None

async def check_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user's guess"""
    global current_game, user_data
    
    if not current_game:
        return
    
    # Check if guess is for current game
    if current_game["chat_id"] != update.effective_chat.id:
        return
    
    user_guess = update.message.text.strip()
    correct_answer = current_game["answer"]
    user_id = str(update.effective_user.id)
    
    # Only allow the user who started the game to guess
    if current_game["user_id"] != user_id:
        await update.message.reply_text("⚠️ This game was started by someone else!")
        return
    
    # Load user data
    user_data = load_user_data()
    if user_id not in user_data:
        user_data[user_id] = {
            "username": update.effective_user.username or update.effective_user.first_name,
            "coins": 0,
            "total_correct": 0,
            "best_strike": 0,
            "current_strike": 0,
            "games_played": 0
        }
    
    # Check if guess is correct
    if is_correct_guess(user_guess, correct_answer):
        # Update user stats
        user_data[user_id]["total_correct"] += 1
        user_data[user_id]["games_played"] += 1
        
        # Calculate new strike and coins
        new_strike = user_data[user_id]["current_strike"] + 1
        coins_earned = calculate_coins(new_strike)
        
        user_data[user_id]["current_strike"] = new_strike
        user_data[user_id]["coins"] += coins_earned
        
        # Update best strike
        if new_strike > user_data[user_id]["best_strike"]:
            user_data[user_id]["best_strike"] = new_strike
        
        # Save user data
        save_user_data(user_data)
        
        # Get milestone message
        milestone_msg = get_milestone_bonus(new_strike)
        
        # Send success message
        await update.message.reply_text(
            f"✅ <b>Correct!</b> It was <b>{correct_answer}</b>\n\n"
            f"🔥 <b>Strike:</b> {new_strike}\n"
            f"💰 <b>+{coins_earned} coins!</b> Total: {user_data[user_id]['coins']}\n"
            f"{milestone_msg}\n\n"
            f"🎮 <i>Next character in 3 seconds...</i>",
            parse_mode="HTML"
        )
        
        # End current game
        current_game = None
        
        # Start next round after delay
        await asyncio.sleep(3)
        await splay(update, context)
    else:
        # Wrong guess
        await update.message.reply_text(
            f"❌ <b>Wrong guess!</b> Try again.\n"
            f"💡 Hint: Name has {len(correct_answer.split())} word(s)",
            parse_mode="HTML"
        )

async def sprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user_id = str(update.effective_user.id)
    user_data = load_user_data()
    
    if user_id not in user_data:
        await update.message.reply_text("You haven't played yet! Use /splay to start!")
        return
    
    stats = user_data[user_id]
    
    await update.message.reply_text(
        f"👤 <b>Player Profile</b>\n\n"
        f"🎮 <b>Username:</b> {stats['username']}\n"
        f"💰 <b>Coins:</b> {stats['coins']}\n"
        f"🔥 <b>Current Strike:</b> {stats['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {stats['best_strike']}\n"
        f"✅ <b>Correct Answers:</b> {stats['total_correct']}\n"
        f"🎯 <b>Games Played:</b> {stats['games_played']}\n\n"
        
        "🎁 <b>Next Milestones:</b>\n"
        "• 10 strikes: 200 coins 🎉\n"
        "• 25 strikes: 500 coins 🌟\n"
        "• 50 strikes: 1000 coins ✨\n"
        "• 59 strikes: 1000 coins 🔥\n"
        "• 75 strikes: 1200 coins 💎\n"
        "• 100 strikes: 1500 coins 🏆",
        parse_mode="HTML"
    )

async def sleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard"""
    user_data = load_user_data()
    
    if not user_data:
        await update.message.reply_text("📊 No players yet! Be the first!")
        return
    
    # Sort by coins
    sorted_users = sorted(
        user_data.items(),
        key=lambda x: x[1]["coins"],
        reverse=True
    )[:10]
    
    leaderboard_text = "🏆 <b>Top 10 Players (by coins)</b>\n\n"
    
    for i, (user_id, data) in enumerate(sorted_users, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
        username = data["username"][:15]
        
        leaderboard_text += (
            f"{medal} <b>{username}</b>\n"
            f"   💰 {data['coins']} coins | "
            f"🔥 {data['best_strike']} strikes\n\n"
        )
    
    await update.message.reply_text(leaderboard_text, parse_mode="HTML")

async def sadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new character (Owner only)"""
    OWNER_ID = os.getenv("OWNER_ID")
    
    if not OWNER_ID or str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("❌ Owner only command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: Reply to image with /sadd <name>")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Reply to an image!")
        return
    
    char_name = " ".join(context.args).strip()
    
    # Create images directory
    os.makedirs("images", exist_ok=True)
    
    # Download image
    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()
    
    # Create safe filename
    safe_name = char_name.lower()
    safe_name = re.sub(r'[^\w\s]', '', safe_name)  # Remove punctuation
    safe_name = safe_name.replace(" ", "_")
    image_path = f"images/{safe_name}.jpg"
    
    await file.download_to_drive(image_path)
    
    # Load existing data
    data = load_game_data()
    
    # Check for duplicates (case-insensitive)
    for char in data["characters"]:
        if char["name"].lower() == char_name.lower():
            await update.message.reply_text("⚠️ Character already exists!")
            return
    
    # Add new character
    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    
    save_game_data(data)
    
    await update.message.reply_text(
        f"✅ <b>Character Added!</b>\n"
        f"🎮 <b>Name:</b> {char_name}\n"
        f"📁 <b>File:</b> {image_path}\n"
        f"📊 <b>Total Characters:</b> {len(data['characters'])}",
        parse_mode="HTML"
    )

async def slist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all characters"""
    data = load_game_data()
    
    if not data.get("characters"):
        await update.message.reply_text("❌ No characters yet!")
        return
    
    text = f"📋 <b>Total Characters: {len(data['characters'])}</b>\n\n"
    
    # Group by first letter
    chars_by_letter = {}
    for char in data["characters"]:
        first_letter = char["name"][0].upper()
        if first_letter not in chars_by_letter:
            chars_by_letter[first_letter] = []
        chars_by_letter[first_letter].append(char["name"])
    
    for letter in sorted(chars_by_letter.keys()):
        text += f"<b>{letter}</b>\n"
        for name in sorted(chars_by_letter[letter]):
            text += f"• {name}\n"
        text += "\n"
    
    # Telegram has 4096 char limit
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    
    await update.message.reply_text(text, parse_mode="HTML")

async def sshop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shop placeholder"""
    await update.message.reply_text(
        "🛒 <b>Shop System (Coming Soon!)</b>\n\n"
        "🎁 Features in development:\n"
        "• Buy profile badges\n"
        "• Unlock special characters\n"
        "• Purchase hints\n"
        "• Custom themes\n\n"
        "Stay tuned for updates! 💫",
        parse_mode="HTML"
    )

async def sreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user strike (for testing)"""
    user_id = str(update.effective_user.id)
    user_data = load_user_data()
    
    if user_id in user_data:
        user_data[user_id]["current_strike"] = 0
        save_user_data(user_data)
        await update.message.reply_text("🔥 Strike reset to 0!")
    else:
        await update.message.reply_text("You haven't played yet!")

def main():
    """Start the bot"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not set!")
        return
    
    print("🚀 Anime NGuess Bot Starting...")
    
    # Load data at startup
    game_data = load_game_data()
    user_data = load_user_data()
    
    print(f"📁 Characters loaded: {len(game_data.get('characters', []))}")
    print(f"👥 Users loaded: {len(user_data)}")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers (all start with 's')
    application.add_handler(CommandHandler("sstart", sstart))
    application.add_handler(CommandHandler("splay", splay))
    application.add_handler(CommandHandler("sprofile", sprofile))
    application.add_handler(CommandHandler("sleaderboard", sleaderboard))
    application.add_handler(CommandHandler("sadd", sadd))
    application.add_handler(CommandHandler("slist", slist))
    application.add_handler(CommandHandler("sshop", sshop))
    application.add_handler(CommandHandler("sreset", sreset))
    
    # Add message handler for guesses
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_guess))
    
    print("✅ Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
