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

# ================= SIMPLE GAME STORAGE =================
# Store only ONE game per chat
active_games = {}
user_stats = {}
# ======================================================

# -------- DATA HELPERS --------
def load_characters():
    try:
        with open("characters.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
    except:
        return []

def save_characters(characters):
    with open("characters.json", "w", encoding="utf-8") as f:
        json.dump(characters, f, indent=2, ensure_ascii=False)

def load_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

# -------- SIMPLE MATCHING --------
def check_guess(guess, answer):
    """Exact matching - SIMPLE AND RELIABLE"""
    return guess.strip().lower() == answer.strip().lower()

# -------- COMMANDS --------
async def sstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Load user stats
    global user_stats
    user_stats = load_users()
    
    if user_id not in user_stats:
        user_stats[user_id] = {
            "name": user.first_name,
            "coins": 0,
            "strike": 0,
            "best_strike": 0,
            "correct": 0
        }
        save_users(user_stats)
    
    stats = user_stats[user_id]
    
    await update.message.reply_text(
        f"✨ Welcome to Anime Guess! ✨\n\n"
        f"💰 Coins: {stats['coins']}\n"
        f"🔥 Current Strike: {stats['strike']}\n"
        f"🏆 Best Strike: {stats['best_strike']}\n\n"
        f"🎮 /splay - Start game (30 seconds)\n"
        f"📊 /sstats - Your stats\n"
        f"🏆 /stop - Leaderboard\n"
        f"➕ /sadd - Add character\n"
        f"📋 /slist - List characters"
    )

async def splay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    
    print(f"\n🔸 /splay called by {user_id} in chat {chat_id}")
    
    # Check if game already active
    if chat_id in active_games:
        print(f"❌ Game already active in chat {chat_id}")
        await update.message.reply_text("Game already running! Guess or wait.")
        return
    
    # Load characters
    characters = load_characters()
    if not characters:
        await update.message.reply_text("No characters! Add with /sadd")
        return
    
    # Pick random character
    character = random.choice(characters)
    print(f"✅ Selected: '{character['name']}'")
    
    # Load user stats
    global user_stats
    user_stats = load_users()
    if user_id not in user_stats:
        user_stats[user_id] = {
            "name": update.effective_user.first_name,
            "coins": 0,
            "strike": 0,
            "best_strike": 0,
            "correct": 0
        }
    
    # Store game
    active_games[chat_id] = {
        "answer": character["name"],
        "user_id": user_id,
        "image": character["image"],
        "timestamp": asyncio.get_event_loop().time()
    }
    
    print(f"✅ Game started. Answer: '{character['name']}'")
    print(f"✅ Active games: {list(active_games.keys())}")
    
    # Send image
    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption=f"🎮 Guess this character!\n⏱️ 30 seconds\n"
                   f"🔥 Your strike: {user_stats[user_id]['strike']}"
        )
    except Exception as e:
        print(f"❌ Error sending image: {e}")
        del active_games[chat_id]
        await update.message.reply_text("Error loading image!")
        return
    
    # Wait 30 seconds
    await asyncio.sleep(30)
    
    # Check if game still exists
    if chat_id in active_games:
        answer = active_games[chat_id]["answer"]
        del active_games[chat_id]
        await context.bot.send_message(
            chat_id,
            f"⏰ Time's up! Answer: {answer}\n"
            f"❌ Strike reset!"
        )
        # Reset strike
        if user_id in user_stats:
            user_stats[user_id]["strike"] = 0
            save_users(user_stats)

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    guess = update.message.text.strip()
    
    print(f"\n🔹 Guess received: '{guess}' from {user_id} in chat {chat_id}")
    print(f"🔹 Active games: {list(active_games.keys())}")
    
    # Check if game exists in this chat
    if chat_id not in active_games:
        print(f"❌ No active game in chat {chat_id}")
        return
    
    game = active_games[chat_id]
    
    # Check if correct user
    if game["user_id"] != user_id:
        print(f"❌ Wrong user. Game belongs to {game['user_id']}")
        await update.message.reply_text("This game was started by someone else!")
        return
    
    answer = game["answer"]
    print(f"✅ Game found! Answer: '{answer}'")
    
    # Check guess
    if check_guess(guess, answer):
        print(f"✅ CORRECT! '{guess}' == '{answer}'")
        
        # Load user stats
        global user_stats
        user_stats = load_users()
        
        # Update stats
        if user_id not in user_stats:
            user_stats[user_id] = {
                "name": update.effective_user.first_name,
                "coins": 0,
                "strike": 0,
                "best_strike": 0,
                "correct": 0
            }
        
        # Calculate coins
        new_strike = user_stats[user_id]["strike"] + 1
        coins_earned = 20
        
        if new_strike == 10:
            coins_earned = 200
        elif new_strike == 25:
            coins_earned = 500
        elif new_strike == 50:
            coins_earned = 1000
        elif new_strike == 59:
            coins_earned = 1000
        elif new_strike == 75:
            coins_earned = 1200
        elif new_strike == 100:
            coins_earned = 1500
        
        # Update user
        user_stats[user_id]["strike"] = new_strike
        user_stats[user_id]["coins"] += coins_earned
        user_stats[user_id]["correct"] += 1
        
        if new_strike > user_stats[user_id]["best_strike"]:
            user_stats[user_id]["best_strike"] = new_strike
        
        save_users(user_stats)
        
        # Send success message
        await update.message.reply_text(
            f"✅ Correct! It was: {answer}\n"
            f"🔥 New strike: {new_strike}\n"
            f"💰 +{coins_earned} coins!\n"
            f"💵 Total: {user_stats[user_id]['coins']}\n\n"
            f"Next round in 3 seconds..."
        )
        
        # Remove game
        del active_games[chat_id]
        
        # Start next round
        await asyncio.sleep(3)
        await splay(update, context)
        
    else:
        print(f"❌ WRONG! '{guess}' != '{answer}'")
        await update.message.reply_text(
            f"❌ Wrong! The answer was: {answer}\n"
            f"❌ Strike reset to 0!"
        )
        # Reset strike
        if user_id in user_stats:
            user_stats[user_id]["strike"] = 0
            save_users(user_stats)
        # Remove game
        if chat_id in active_games:
            del active_games[chat_id]

async def sstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_stats = load_users()
    
    if user_id not in user_stats:
        await update.message.reply_text("Play first with /splay!")
        return
    
    stats = user_stats[user_id]
    
    await update.message.reply_text(
        f"📊 Your Stats:\n\n"
        f"💰 Coins: {stats['coins']}\n"
        f"🔥 Current Strike: {stats['strike']}\n"
        f"🏆 Best Strike: {stats['best_strike']}\n"
        f"✅ Correct Answers: {stats['correct']}"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_stats = load_users()
    
    if not user_stats:
        await update.message.reply_text("No players yet!")
        return
    
    # Sort by coins
    top_users = sorted(
        user_stats.items(),
        key=lambda x: x[1]["coins"],
        reverse=True
    )[:10]
    
    leaderboard = "🏆 Top Players:\n\n"
    for i, (uid, stats) in enumerate(top_users, 1):
        leaderboard += f"{i}. {stats['name']}\n"
        leaderboard += f"   💰 {stats['coins']} coins | 🔥 {stats['best_strike']}\n\n"
    
    await update.message.reply_text(leaderboard)

async def sadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add character - SIMPLE VERSION"""
    if not context.args:
        await update.message.reply_text("Reply to image: /sadd <name>")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to an image!")
        return
    
    char_name = " ".join(context.args).strip()
    
    # Create images folder
    os.makedirs("images", exist_ok=True)
    
    # Download image
    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()
    
    # Save image
    safe_name = char_name.lower().replace(" ", "_").replace(".", "")
    image_path = f"images/{safe_name}.jpg"
    await file.download_to_drive(image_path)
    
    # Load characters
    characters = load_characters()
    
    # Check if exists
    for char in characters:
        if char["name"].lower() == char_name.lower():
            await update.message.reply_text("Already exists!")
            return
    
    # Add character
    characters.append({
        "name": char_name,
        "image": image_path
    })
    
    save_characters(characters)
    
    await update.message.reply_text(
        f"✅ Added: {char_name}\n"
        f"Total: {len(characters)} characters"
    )

async def slist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    characters = load_characters()
    
    if not characters:
        await update.message.reply_text("No characters!")
        return
    
    text = f"📋 Characters ({len(characters)}):\n\n"
    for char in characters:
        text += f"• {char['name']}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    
    await update.message.reply_text(text)

async def sdebug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug command"""
    chat_id = update.effective_chat.id
    
    debug_info = f"🔧 Debug Info:\n"
    debug_info += f"Active games: {len(active_games)}\n"
    
    if chat_id in active_games:
        game = active_games[chat_id]
        debug_info += f"Current answer: '{game['answer']}'\n"
        debug_info += f"Started by: {game['user_id']}\n"
        debug_info += f"Image: {game['image']}"
    else:
        debug_info += "No active game in this chat"
    
    await update.message.reply_text(debug_info)

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ No BOT_TOKEN!")
        return
    
    print("🚀 Starting Anime Guess Bot...")
    print(f"Token: {token[:10]}...")
    
    # Load initial data
    chars = load_characters()
    users = load_users()
    print(f"Loaded {len(chars)} characters, {len(users)} users")
    
    # Create app
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("sstart", sstart))
    app.add_handler(CommandHandler("splay", splay))
    app.add_handler(CommandHandler("sstats", sstats))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("sadd", sadd))
    app.add_handler(CommandHandler("slist", slist))
    app.add_handler(CommandHandler("sdebug", sdebug))
    
    # Add message handler (MUST BE LAST!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    
    print("✅ Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
