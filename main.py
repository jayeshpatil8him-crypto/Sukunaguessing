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
    ContextTypes,
    CallbackContext
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
            games_played INTEGER DEFAULT 0,
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
            FOREIGN KEY (character_id) REFERENCES characters (id)
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
        return False
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
            'total_correct': 0,
            'games_played': 0
        }
    
    conn.close()
    return {
        'user_id': user[0],
        'username': user[1] or '',
        'coins': user[2],
        'current_strike': user[3],
        'best_strike': user[4],
        'total_correct': user[5],
        'games_played': user[6] or 0
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
            games_played = ?,
            last_played = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (
        user_data['username'],
        user_data['coins'],
        user_data['current_strike'],
        user_data['best_strike'],
        user_data['total_correct'],
        user_data['games_played'],
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

def get_top_users(limit=10):
    """Get top users by coins"""
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, coins, best_strike, total_correct 
        FROM users 
        WHERE coins > 0 
        ORDER BY coins DESC 
        LIMIT ?
    ''', (limit,))
    
    results = cursor.fetchall()
    conn.close()
    
    return results

# =============== GAME LOGIC ===============
def calculate_coins(strike):
    """Calculate coins earned"""
    if strike == 10: return 200
    elif strike == 25: return 500
    elif strike == 50: return 1000
    elif strike == 59: return 1000
    elif strike == 75: return 1200
    elif strike == 100: return 1500
    elif strike % 10 == 0: return 100
    else: return 20

def check_guess(user_guess, correct_name):
    """Check if guess is correct (case-insensitive)"""
    return user_guess.strip().lower() == correct_name.strip().lower()

# =============== COMMAND HANDLERS ===============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    print(f"\n🚀 /start command from {user_id}")
    
    user_data = get_user(user_id)
    user_data['username'] = user.username or user.first_name
    update_user(user_data)
    
    await update.message.reply_text(
        f"✨ Welcome {user.first_name} to Anime NGuess! ✨\n\n"
        f"💰 <b>Your Coins:</b> {user_data['coins']}\n"
        f"🔥 <b>Current Strike:</b> {user_data['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {user_data['best_strike']}\n\n"
        f"🎮 <b>How to Play:</b>\n"
        f"1. Use /splay to start a game\n"
        f"2. You'll see an anime character image\n"
        f"3. Type the character name to guess\n"
        f"4. Earn coins for correct guesses!\n\n"
        f"⏱️ <b>Time Limit:</b> 30 seconds per round\n"
        f"💰 <b>Coin Rewards:</b>\n"
        f"• Base: 20 coins per correct guess\n"
        f"• 10 strikes: 200 coins 🎉\n"
        f"• 25 strikes: 500 coins 🌟\n"
        f"• 50 strikes: 1000 coins ✨\n"
        f"• 59 strikes: 1000 coins 🔥\n"
        f"• 75 strikes: 1200 coins 💎\n"
        f"• 100 strikes: 1500 coins 🏆\n\n"
        f"📋 <b>Commands:</b>\n"
        f"• /splay - Start new game\n"
        f"• /sprofile - Your stats\n"
        f"• /sleaderboard - Top players\n"
        f"• /sadd - Add character\n"
        f"• /slist - All characters\n"
        f"• /shelp - Show this help",
        parse_mode="HTML"
    )

async def splay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /splay command"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    print(f"\n🎮 /splay from user {user_id} in chat {chat_id}")
    
    # Check if game already active
    active_game = get_active_game(chat_id)
    if active_game:
        print(f"❌ Game already active")
        await update.message.reply_text("⚠️ A game is already running! Guess the character.")
        return
    
    # Get random character
    character = get_random_character()
    if not character:
        print(f"❌ No characters in database")
        await update.message.reply_text("❌ No characters added yet! Use /sadd to add characters.")
        return
    
    print(f"✅ Character selected: '{character['name']}'")
    
    # Get user data
    user_data = get_user(user_id)
    user_data['username'] = update.effective_user.username or update.effective_user.first_name
    user_data['games_played'] += 1
    
    # Start game in database
    start_game(chat_id, user_id, character)
    
    # Send image
    try:
        await update.message.reply_photo(
            photo=open(character['image_path'], 'rb'),
            caption=f"🎮 <b>Guess the Anime Character!</b>\n"
                   f"⏱️ <b>30 seconds</b>\n\n"
                   f"🔥 <b>Current Strike:</b> {user_data['current_strike']}\n"
                   f"💰 <b>Next Reward:</b> {calculate_coins(user_data['current_strike'] + 1)} coins\n\n"
                   f"💡 <i>Type the character name below...</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Error sending image: {e}")
        end_game(chat_id)
        await update.message.reply_text(f"❌ Error loading image: {str(e)}")
        return
    
    # Save user data
    update_user(user_data)
    
    print(f"✅ Game started successfully")
    
    # Set timeout task
    async def timeout_game():
        await asyncio.sleep(30)
        
        active_game = get_active_game(chat_id)
        if active_game:
            print(f"⏰ Timeout for chat {chat_id}")
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
    
    # Run timeout in background
    asyncio.create_task(timeout_game())

async def sprofile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sprofile command"""
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    
    print(f"\n📊 /sprofile from user {user_id}")
    
    await update.message.reply_text(
        f"📊 <b>Your Stats</b>\n\n"
        f"👤 <b>Player:</b> {user_data['username']}\n"
        f"💰 <b>Coins:</b> {user_data['coins']}\n"
        f"🔥 <b>Current Strike:</b> {user_data['current_strike']}\n"
        f"🏆 <b>Best Strike:</b> {user_data['best_strike']}\n"
        f"✅ <b>Correct Answers:</b> {user_data['total_correct']}\n"
        f"🎮 <b>Games Played:</b> {user_data['games_played']}\n\n"
        f"🎁 <b>Next Milestone:</b>\n",
        parse_mode="HTML"
    )

async def sleaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sleaderboard command"""
    print(f"\n🏆 /sleaderboard command")
    
    top_users = get_top_users(10)
    
    if not top_users:
        await update.message.reply_text("📊 No players yet! Be the first to play!")
        return
    
    leaderboard = "🏆 <b>Top 10 Players</b>\n\n"
    
    for i, (username, coins, best_strike, total_correct) in enumerate(top_users, 1):
        medal = ""
        if i == 1: medal = "🥇"
        elif i == 2: medal = "🥈"
        elif i == 3: medal = "🥉"
        else: medal = f"{i}."
        
        display_name = username or f"Player{i}"
        if len(display_name) > 15:
            display_name = display_name[:12] + "..."
        
        leaderboard += f"{medal} <b>{display_name}</b>\n"
        leaderboard += f"   💰 {coins} coins | 🔥 {best_strike} strikes | ✅ {total_correct}\n\n"
    
    await update.message.reply_text(leaderboard, parse_mode="HTML")

async def sadd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sadd command"""
    user_id = update.effective_user.id
    owner_id = os.getenv("OWNER_ID")
    
    print(f"\n➕ /sadd from user {user_id}")
    
    # Check if user is owner
    if not owner_id or str(user_id) != owner_id:
        await update.message.reply_text("❌ Only the bot owner can add characters!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: Reply to an image with /sadd <character name>")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Please reply to an image!")
        return
    
    char_name = " ".join(context.args).strip()
    
    # Create images directory
    os.makedirs("images", exist_ok=True)
    
    # Download image
    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()
    
    # Create safe filename
    safe_name = char_name.lower().replace(" ", "_").replace(".", "")
    image_path = f"images/{safe_name}.jpg"
    
    try:
        await file.download_to_drive(image_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error downloading image: {str(e)}")
        return
    
    # Add to database
    success = add_character(char_name, image_path)
    
    if success:
        await update.message.reply_text(
            f"✅ <b>Character Added Successfully!</b>\n\n"
            f"🎮 <b>Name:</b> {char_name}\n"
            f"📁 <b>Saved as:</b> {image_path}\n\n"
            f"Now players can guess this character!",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ This character already exists!")

async def slist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /slist command"""
    print(f"\n📋 /slist command")
    
    characters = get_all_characters()
    
    if not characters:
        await update.message.reply_text("❌ No characters added yet!")
        return
    
    total = len(characters)
    text = f"📋 <b>All Characters ({total})</b>\n\n"
    
    # Group by first letter
    char_dict = {}
    for char in characters:
        first_letter = char[0].upper()
        if first_letter not in char_dict:
            char_dict[first_letter] = []
        char_dict[first_letter].append(char)
    
    for letter in sorted(char_dict.keys()):
        text += f"<b>{letter}</b>\n"
        for char in sorted(char_dict[letter]):
            text += f"• {char}\n"
        text += "\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    
    await update.message.reply_text(text, parse_mode="HTML")

async def shelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /shelp command"""
    await start_command(update, context)

# =============== MESSAGE HANDLER ===============
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages (guesses)"""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    print(f"\n📨 Message received: '{text}' from {user_id} in {chat_id}")
    
    # Check if it's a command
    if text.startswith('/'):
        print(f"📝 It's a command, skipping...")
        return
    
    # Check if there's an active game
    active_game = get_active_game(chat_id)
    if not active_game:
        print(f"❌ No active game in this chat")
        return
    
    print(f"✅ Active game found. Answer: '{active_game['character_name']}'")
    
    # Check if this user started the game
    if active_game['user_id'] != user_id:
        print(f"❌ Wrong user. Game started by {active_game['user_id']}")
        await update.message.reply_text("⚠️ This game was started by someone else!")
        return
    
    # Check the guess
    if check_guess(text, active_game['character_name']):
        print(f"✅ CORRECT! User guessed '{text}'")
        
        # Get and update user data
        user_data = get_user(user_id)
        user_data['username'] = update.effective_user.username or update.effective_user.first_name
        
        # Calculate new strike and coins
        new_strike = user_data['current_strike'] + 1
        coins_earned = calculate_coins(new_strike)
        
        user_data['current_strike'] = new_strike
        user_data['coins'] += coins_earned
        user_data['total_correct'] += 1
        
        # Update best strike
        if new_strike > user_data['best_strike']:
            user_data['best_strike'] = new_strike
        
        # Save user data
        update_user(user_data)
        
        # End current game
        end_game(chat_id)
        
        # Send success message
        success_msg = f"✅ <b>Correct!</b> It was <b>{active_game['character_name']}</b>\n\n"
        success_msg += f"🔥 <b>New Strike:</b> {new_strike}\n"
        success_msg += f"💰 <b>+{coins_earned} coins!</b> Total: {user_data['coins']}\n"
        
        # Add milestone message
        if new_strike in [10, 25, 50, 59, 75, 100]:
            milestone_msgs = {
                10: "🎉 10-STRIKE BONUS!",
                25: "🌟 25-STRIKE BONUS!",
                50: "✨ 50-STRIKE BONUS!",
                59: "🔥 59-STRIKE SPECIAL!",
                75: "💎 75-STRIKE BONUS!",
                100: "🏆 100-STRIKE LEGEND!"
            }
            success_msg += f"\n{milestone_msgs[new_strike]}\n"
        
        success_msg += f"\n🎮 <i>Next round in 3 seconds...</i>"
        
        await update.message.reply_text(success_msg, parse_mode="HTML")
        
        # Start next round after delay
        await asyncio.sleep(3)
        await splay_command(update, context)
        
    else:
        print(f"❌ WRONG! User guessed '{text}' but answer is '{active_game['character_name']}'")
        
        # Reset user strike
        user_data = get_user(user_id)
        user_data['current_strike'] = 0
        update_user(user_data)
        
        # End game
        end_game(chat_id)
        
        await update.message.reply_text(
            f"❌ <b>Wrong!</b> The answer was: <b>{active_game['character_name']}</b>\n"
            f"❌ <b>Strike reset to 0!</b>\n\n"
            f"Use /splay to start a new game!",
            parse_mode="HTML"
        )

# =============== MAIN FUNCTION ===============
def main():
    """Start the bot"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ ERROR: BOT_TOKEN not set in environment variables!")
        return
    
    print("🚀 Starting Anime NGuess Bot...")
    print(f"📱 Token: {token[:10]}...")
    
    # Create application
 
