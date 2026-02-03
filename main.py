#!/usr/bin/env python3
import os
import sqlite3
import random
import asyncio
import logging
from datetime import datetime
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

# =============== DATABASE SETUP ===============
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    # Characters table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            image_path TEXT NOT NULL,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0,
            current_strike INTEGER DEFAULT 0,
            best_strike INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            last_played TIMESTAMP
        )
    ''')
    
    # Active games table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_games (
            chat_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            character_name TEXT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters (id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# Initialize database
init_db()

# =============== DATABASE FUNCTIONS ===============
def add_character(name, image_path):
    """Add a new character to database"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO characters (name, image_path) VALUES (?, ?)',
            (name, image_path)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Already exists
    finally:
        conn.close()

def get_random_character():
    """Get a random character from database"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, image_path FROM characters ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'name': result[1],
            'image_path': result[2]
        }
    return None

def get_all_characters():
    """Get all characters"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM characters ORDER BY name')
    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]

def get_user(user_id):
    """Get or create user"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM users WHERE user_id = ?',
        (user_id,)
    )
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            'INSERT INTO users (user_id, username) VALUES (?, ?)',
            (user_id, '')
        )
        conn.commit()
        conn.close()
        return {
            'user_id': user_id,
            'username': '',
            'coins': 0,
            'current_strike': 0,
            'best_strike': 0,
            'total_correct': 0
        }
    
    conn.close()
    return {
        'user_id': user[0],
        'username': user[1] or '',
        'coins': user[2],
        'current_strike': user[3],
        'best_strike': user[4],
        'total_correct': user[5]
    }

def update_user(user_data):
    """Update user stats"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET
            username = ?,
            coins = ?,
            current_strike = ?,
            best_strike = ?,
            total_correct = ?,
            last_played = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (
        user_data['username'],
        user_data['coins'],
        user_data['current_strike'],
        user_data['best_strike'],
        user_data['total_correct'],
        user_data['user_id']
    ))
    
    conn.commit()
    conn.close()

def start_game(chat_id, user_id, character):
    """Start a new game"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    # Remove any existing game in this chat
    cursor.execute('DELETE FROM active_games WHERE chat_id = ?', (chat_id,))
    
    # Add new game
    cursor.execute('''
        INSERT INTO active_games (chat_id, user_id, character_id, character_name)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, user_id, character['id'], character['name']))
    
    conn.commit()
    conn.close()
    return True

def get_active_game(chat_id):
    """Get active game for chat"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ag.character_name, ag.user_id, c.image_path
        FROM active_games ag
        JOIN characters c ON ag.character_id = c.id
        WHERE ag.chat_id = ?
    ''', (chat_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'character_name': result[0],
            'user_id': result[1],
            'image_path': result[2]
        }
    return None

def end_game(chat_id):
    """End active game"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM active_games WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

# =============== GAME LOGIC ===============
def calculate_coins(strike):
    """Calculate coins earned"""
    if strike == 10: return 200
    elif strike == 25: return 500
    elif strike == 50: return 1000
    elif strike == 59: return 1000
    elif strike == 75: return 1200
    elif strike == 100: return 1500
    elif strike % 10 == 0: return 100  # Every 10th strike
    else: return 20  # Base reward

def check_guess(user_guess, correct_name):
    """Check if guess is correct (case-insensitive exact match)"""
    return user_guess.strip().lower() == correct_name.strip().lower()

# =============== COMMAND HANDLERS ===============
async def sstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    user_data = get_user(user.id)
    
    await update.message.reply_text(
        f"✨ Welcome {user.first_name} to Anime NGuess! ✨\n\n"
        f"💰 <b>Coins:</b> {user_data['coins']}\n"
        f"🔥 <b>Current Strike:</b> {user_data['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {user_data['best_strike']}\n\n"
        f"🎮 <b>Commands:</b>\n"
        f"/splay - Start game (30 seconds)\n"
        f"/sprofile - Your stats\n"
        f"/sleaderboard - Top players\n"
        f"/sadd - Add character\n"
        f"/slist - List characters\n"
        f"/sdebug - Debug info",
        parse_mode="HTML"
    )

async def splay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new game"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    print(f"\n🎮 /splay called by {user_id} in chat {chat_id}")
    
    # Check if game already active
    active_game = get_active_game(chat_id)
    if active_game:
        print(f"❌ Game already active in chat {chat_id}")
        await update.message.reply_text("⚠️ Game already running! Guess the character.")
        return
    
    # Get random character
    character = get_random_character()
    if not character:
        await update.message.reply_text("❌ No characters added! Use /sadd first.")
        return
    
    print(f"✅ Selected character: '{character['name']}'")
    
    # Get user data
    user_data = get_user(user_id)
    user_data['username'] = update.effective_user.username or update.effective_user.first_name
    
    # Start game in database
    start_game(chat_id, user_id, character)
    
    # Send image
    try:
        await update.message.reply_photo(
            photo=open(character['image_path'], 'rb'),
            caption=f"🎮 <b>Guess this Anime Character!</b>\n"
                   f"⏱️ <b>30 seconds</b>\n"
                   f"🔥 <b>Your Strike:</b> {user_data['current_strike']}\n"
                   f"💰 <b>Next Reward:</b> {calculate_coins(user_data['current_strike'] + 1)} coins",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Error sending image: {e}")
        end_game(chat_id)
        await update.message.reply_text("❌ Error loading image!")
        return
    
    print(f"✅ Game started for chat {chat_id}")
    
    # 30-second timer
    await asyncio.sleep(30)
    
    # Check if game still exists
    active_game = get_active_game(chat_id)
    if active_game:
        print(f"⏰ Time's up for chat {chat_id}")
        await context.bot.send_message(
            chat_id,
            f"⏰ <b>Time's up!</b>\n"
            f"The character was: <b>{active_game['character_name']}</b>\n"
            f"❌ <b>Strike reset to 0!</b>",
            parse_mode="HTML"
        )
        # Reset user strike
        user_data = get_user(user_id)
        user_data['current_strike'] = 0
        update_user(user_data)
        end_game(chat_id)

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's guess"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_guess = update.message.text.strip()
    
    print(f"\n🎯 Guess received in chat {chat_id}")
    print(f"User {user_id} guessed: '{user_guess}'")
    
    # Get active game
    active_game = get_active_game(chat_id)
    if not active_game:
        print(f"❌ No active game in chat {chat_id}")
        return
    
    print(f"✅ Active game found! Answer: '{active_game['character_name']}'")
    
    # Check if correct user
    if active_game['user_id'] != user_id:
        print(f"❌ Wrong user. Game started by {active_game['user_id']}")
        await update.message.reply_text("⚠️ This game was started by someone else!")
        return
    
    # Check guess
    if check_guess(user_guess, active_game['character_name']):
        print(f"✅ CORRECT GUESS! '{user_guess}' == '{active_game['character_name']}'")
        
        # Get user data
        user_data = get_user(user_id)
        user_data['username'] = update.effective_user.username or update.effective_user.first_name
        
        # Update stats
        new_strike = user_data['current_strike'] + 1
        coins_earned = calculate_coins(new_strike)
        
        user_data['current_strike'] = new_strike
        user_data['coins'] += coins_earned
        user_data['total_correct'] += 1
        
        if new_strike > user_data['best_strike']:
            user_data['best_strike'] = new_strike
        
        # Save user data
        update_user(user_data)
        
        # End current game
        end_game(chat_id)
        
        # Send success message
        await update.message.reply_text(
            f"✅ <b>Correct!</b> It was <b>{active_game['character_name']}</b>\n\n"
            f"🔥 <b>New Strike:</b> {new_strike}\n"
            f"💰 <b>+{coins_earned} coins!</b>\n"
            f"💵 <b>Total Coins:</b> {user_data['coins']}\n\n"
            f"🎮 <i>Next round in 3 seconds...</i>",
            parse_mode="HTML"
        )
        
        # Start next round
        await asyncio.sleep(3)
        await splay(update, context)
        
    else:
        print(f"❌ WRONG GUESS! '{user_guess}' != '{active_game['character_name']}'")
        
        # Get user data
        user_data = get_user(user_id)
        user_data['current_strike'] = 0
        update_user(user_data)
        
        # End game
        end_game(chat_id)
        
        await update.message.reply_text(
            f"❌ <b>Wrong!</b> The answer was: <b>{active_game['character_name']}</b>\n"
            f"❌ <b>Strike reset to 0!</b>",
            parse_mode="HTML"
        )

async def sprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile"""
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    
    await update.message.reply_text(
        f"📊 <b>Your Stats</b>\n\n"
        f"💰 <b>Coins:</b> {user_data['coins']}\n"
        f"🔥 <b>Current Strike:</b> {user_data['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {user_data['best_strike']}\n"
        f"✅ <b>Correct Answers:</b> {user_data['total_correct']}",
        parse_mode="HTML"
    )

async def sleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, coins, best_strike 
        FROM users 
        WHERE coins > 0 
        ORDER BY coins DESC 
        LIMIT 10
    ''')
    
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text("📊 No players yet!")
        return
    
    leaderboard = "🏆 <b>Top Players</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    
    for i, (username, coins, best_strike) in enumerate(top_users):
        if i < 3:
            leaderboard += f"{medals[i]} <b>{username or 'Player'}</b>\n"
        else:
            leaderboard += f"{medals[i]} {username or 'Player'}\n"
        
        leaderboard += f"   💰 {coins} coins | 🔥 {best_strike} strikes\n\n"
    
    await update.message.reply_text(leaderboard, parse_mode="HTML")

async def sadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new character"""
    if not context.args:
        await update.message.reply_text("Reply to image: /sadd <character name>")
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
    
    # Save image
    safe_name = char_name.lower().replace(" ", "_").replace(".", "")
    image_path = f"images/{safe_name}.jpg"
    await file.download_to_drive(image_path)
    
    # Add to database
    success = add_character(char_name, image_path)
    
    if success:
        await update.message.reply_text(
            f"✅ <b>Character Added!</b>\n"
            f"🎮 <b>Name:</b> {char_name}\n"
            f"📁 <b>Saved as:</b> {image_path}",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ Character already exists!")

async def slist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all characters"""
    characters = get_all_characters()
    
    if not characters:
        await update.message.reply_text("❌ No characters yet!")
        return
    
    text = f"📋 <b>Characters ({len(characters)})</b>\n\n"
    for char in characters:
        text += f"• {char}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    
    await update.message.reply_text(text, parse_mode="HTML")

async def sdebug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug info"""
    chat_id = update.effective_chat.id
    active_game = get_active_game(chat_id)
    
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM characters')
    char_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM active_games')
    active_count = cursor.fetchone()[0]
    
    conn.close()
    
    debug_text = (
        f"🔧 <b>Debug Info</b>\n\n"
        f"📊 Characters: {char_count}\n"
        f"👥 Users: {user_count}\n"
        f"🎮 Active Games: {active_count}\n"
    )
    
    if active_game:
        debug_text += f"\n🎯 Current Game:\n"
        debug_text += f"Answer: '{active_game['character_name']}'\n"
        debug_text += f"Started by: {active_game['user_id']}"
    
    await update.message.reply_text(debug_text, parse_mode="HTML")

# =============== MAIN ===============
def main():
    """Start the bot"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not set!")
        return
    
    print("🚀 Anime NGuess Bot Starting...")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("splay", splay))
    application.add_handler(CommandHandler("sprofile", sprofile))
    application.add_handler(CommandHandler("sleaderboard", sleaderboard))
    application.add_handler(CommandHandler("sadd", sadd))
    application.add_handler(CommandHandler("slist", slist))
    application.add_handler(CommandHandler("sdebug", sdebug))
    
    # Add message handler for guesses
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    
    print("✅ Bot is running...")
    application.run_polling(allowed_updates=None)

if __name__ == "__main__":
    main()
