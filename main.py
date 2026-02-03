#!/usr/bin/env python3
import os
import json
import random
import asyncio
import logging
import re
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
game_sessions = {}
# ==================================================

# -------- DEBUG HELPER --------
def debug_info(chat_id, guess, correct):
    """Print debug info to console"""
    print("\n" + "="*50)
    print("🎯 DEBUG INFO:")
    print(f"Chat ID: {chat_id}")
    print(f"User Guess: '{guess}'")
    print(f"Correct Answer: '{correct}'")
    print(f"Guess Type: {type(guess)}")
    print(f"Correct Type: {type(correct)}")
    print(f"Guess Lower: '{guess.lower().strip()}'")
    print(f"Correct Lower: '{correct.lower().strip()}'")
    print(f"Are they equal? {guess.lower().strip() == correct.lower().strip()}")
    print("="*50 + "\n")

# -------- DATA HELPERS --------
def load_data():
    """Load character data and print debug info"""
    DATA_FILE = "data.json"
    if not os.path.exists(DATA_FILE):
        print(f"❌ {DATA_FILE} not found!")
        return {"characters": []}
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"\n📁 Loaded {len(data['characters'])} characters from {DATA_FILE}:")
    for i, char in enumerate(data["characters"], 1):
        print(f"{i}. Name: '{char['name']}', Image: '{char['image']}'")
    
    return data

def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved {len(data['characters'])} characters to data.json")

def get_random_character():
    data = load_data()
    if not data["characters"]:
        print("❌ No characters in database!")
        return None
    
    char = random.choice(data["characters"])
    print(f"🎲 Selected random character: '{char['name']}'")
    return char

# -------- SIMPLE MATCHING --------
def is_correct_guess(guess, correct_answer):
    """SUPER SIMPLE matching for testing"""
    # Basic cleaning
    user_guess = str(guess).lower().strip()
    correct = str(correct_answer).lower().strip()
    
    # Remove extra spaces
    user_guess = re.sub(r'\s+', ' ', user_guess)
    correct = re.sub(r'\s+', ' ', correct)
    
    # Remove punctuation
    user_guess = re.sub(r'[^\w\s]', '', user_guess)
    correct = re.sub(r'[^\w\s]', '', correct)
    
    print(f"\n🔍 MATCHING CHECK:")
    print(f"User Guess (cleaned): '{user_guess}'")
    print(f"Correct (cleaned): '{correct}'")
    print(f"Exact match? {user_guess == correct}")
    
    # Direct match
    if user_guess == correct:
        print("✅ MATCH FOUND: Exact match!")
        return True
    
    # Check if any word matches
    guess_words = user_guess.split()
    correct_words = correct.split()
    
    for g_word in guess_words:
        for c_word in correct_words:
            if g_word == c_word:
                print(f"✅ MATCH FOUND: Word '{g_word}' matches!")
                return True
    
    print("❌ NO MATCH FOUND")
    return False

# -------- COMMAND HANDLERS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 Anime Guess Bot (Debug Mode)\n\n"
        "Commands:\n"
        "/play - Start game\n"
        "/add - Add character\n"
        "/list - List all characters\n"
        "/debug - Show current game\n"
        "/test <name> - Test matching"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id in game_sessions:
        await update.message.reply_text("Game already running!")
        return
    
    character = get_random_character()
    if not character:
        await update.message.reply_text("No characters! Use /add first.")
        return
    
    game_sessions[chat_id] = {
        "answer": character["name"],
        "image": character["image"],
        "active": True
    }
    
    print(f"\n🎮 NEW GAME STARTED:")
    print(f"Chat ID: {chat_id}")
    print(f"Answer: '{character['name']}'")
    print(f"Image: '{character['image']}'")
    
    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption=f"Guess this character!\n⏱️ 15 seconds\n\n"
                   f"Answer stored: '{character['name']}'"
        )
    except Exception as e:
        print(f"❌ Error sending photo: {e}")
        await update.message.reply_text(f"Error: {e}")
        return
    
    # Timer
    await asyncio.sleep(15)
    
    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        game_sessions.pop(chat_id, None)
        await context.bot.send_message(chat_id, "⏰ Time's up!")

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in game_sessions:
        return
    
    guess = update.message.text
    correct = game_sessions[chat_id]["answer"]
    
    # Debug output
    debug_info(chat_id, guess, correct)
    
    if is_correct_guess(guess, correct):
        game_sessions.pop(chat_id, None)
        await update.message.reply_text(f"✅ Correct! It was '{correct}'!")
        await asyncio.sleep(2)
        await play(update, context)
    else:
        await update.message.reply_text(
            f"❌ Wrong! The answer was '{correct}'\n"
            f"Your guess: '{guess}'"
        )

async def addcharacter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple add character command"""
    if not context.args:
        await update.message.reply_text("Usage: /add <name> (reply to image)")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to an image!")
        return
    
    char_name = " ".join(context.args)
    
    # Create images folder
    os.makedirs("images", exist_ok=True)
    
    # Download image
    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()
    
    # Simple filename
    safe_name = char_name.lower().replace(" ", "_").replace(".", "")
    image_path = f"images/{safe_name}.jpg"
    
    await file.download_to_drive(image_path)
    
    # Load and update data
    data = load_data()
    
    # Check for duplicates
    for char in data["characters"]:
        if char["name"].lower() == char_name.lower():
            await update.message.reply_text("Already exists!")
            return
    
    # Add new character
    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    
    save_data(data)
    
    await update.message.reply_text(
        f"✅ Added: '{char_name}'\n"
        f"Saved as: {image_path}\n"
        f"Total characters: {len(data['characters'])}"
    )

async def listcharacters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all characters"""
    data = load_data()
    
    if not data["characters"]:
        await update.message.reply_text("No characters yet!")
        return
    
    text = "📋 All Characters:\n\n"
    for i, char in enumerate(data["characters"], 1):
        text += f"{i}. {char['name']}\n"
        text += f"   Image: {char['image']}\n\n"
    
    await update.message.reply_text(text[:4000])  # Telegram limit

async def debugcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug current game"""
    chat_id = update.effective_chat.id
    
    if chat_id in game_sessions:
        game = game_sessions[chat_id]
        await update.message.reply_text(
            f"🔧 DEBUG INFO:\n"
            f"Answer: '{game['answer']}'\n"
            f"Image: {game['image']}\n"
            f"Active: {game['active']}"
        )
    else:
        await update.message.reply_text("No active game in this chat")

async def testmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test matching with a name"""
    if not context.args:
        await update.message.reply_text("Usage: /test <name>")
        return
    
    test_name = " ".join(context.args)
    data = load_data()
    
    if not data["characters"]:
        await update.message.reply_text("No characters to test against!")
        return
    
    results = []
    for char in data["characters"]:
        match = is_correct_guess(test_name, char["name"])
        results.append(f"{char['name']}: {'✅' if match else '❌'}")
    
    await update.message.reply_text(
        f"Testing: '{test_name}'\n\n" +
        "\n".join(results)
    )

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not set!")
        return
    
    print("🚀 Starting Debug Bot...")
    print(f"Token starts with: {token[:10]}...")
    
    # Load data at startup
    load_data()
    
    application = Application.builder().token(token).build()
    
    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("add", addcharacter))
    application.add_handler(CommandHandler("list", listcharacters))
    application.add_handler(CommandHandler("debug", debugcmd))
    application.add_handler(CommandHandler("test", testmatch))
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    
    print("✅ Bot starting...")
    application.run_polling(allowed_updates=None)

if __name__ == '__main__':
    main()
