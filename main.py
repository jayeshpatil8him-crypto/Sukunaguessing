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
game_sessions = {}  # chat_id -> {"answer": "name", "user_id": 123}
# ==================================================

# -------- DATA HELPERS --------
def load_data():
    """Load character data"""
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

# -------- SIMPLE MATCHING --------
def is_correct_guess(guess, correct_answer):
    """Simple case-insensitive matching with word checking"""
    # Convert to strings and clean
    guess_str = str(guess).strip()
    correct_str = str(correct_answer).strip()
    
    # Convert to lowercase
    guess_lower = guess_str.lower()
    correct_lower = correct_str.lower()
    
    # Remove punctuation
    guess_clean = re.sub(r'[^\w\s]', '', guess_lower)
    correct_clean = re.sub(r'[^\w\s]', '', correct_lower)
    
    # DEBUG: Print what we're comparing
    print(f"\n🔍 MATCHING DEBUG:")
    print(f"Raw guess: '{guess_str}'")
    print(f"Raw correct: '{correct_str}'")
    print(f"Clean guess: '{guess_clean}'")
    print(f"Clean correct: '{correct_clean}'")
    
    # 1. Exact match (after cleaning)
    if guess_clean == correct_clean:
        print("✅ Exact match!")
        return True
    
    # 2. Check if any word matches
    guess_words = guess_clean.split()
    correct_words = correct_clean.split()
    
    for word in guess_words:
        if word in correct_words:
            print(f"✅ Word match: '{word}' found in correct answer")
            return True
    
    # 3. Check if correct words are in guess
    for word in correct_words:
        if word in guess_words:
            print(f"✅ Word match: '{word}' found in guess")
            return True
    
    print("❌ No match found")
    return False

# -------- COMMAND HANDLERS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎮 Anime Guess Bot\n\n"
        "Guess the anime character in 15 seconds!\n\n"
        "Commands:\n"
        "/play - Start new game\n"
        "/add <name> - Add character (reply to image)\n"
        "/list - Show all characters\n"
        "/test <name> - Test name matching"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Check if game already running
    if chat_id in game_sessions:
        await update.message.reply_text("⚠️ Game already running! Guess or wait for timeout.")
        return
    
    # Get random character
    character = get_random_character()
    if not character:
        await update.message.reply_text("❌ No characters! Use /add to add some first.")
        return
    
    # Store game session
    game_sessions[chat_id] = {
        "answer": character["name"],
        "user_id": update.effective_user.id
    }
    
    print(f"\n🎮 GAME STARTED:")
    print(f"Chat: {chat_id}")
    print(f"Answer stored: '{character['name']}'")
    print(f"Image: {character['image']}")
    
    # Send image
    try:
        if os.path.exists(character["image"]):
            await update.message.reply_photo(
                photo=open(character["image"], "rb"),
                caption="🎮 Guess this character!\n⏱️ You have 15 seconds!\n\n"
                       f"💡 Hint: Name has {len(character['name'].split())} word(s)"
            )
        else:
            await update.message.reply_text(f"❌ Image not found: {character['image']}")
            game_sessions.pop(chat_id, None)
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        game_sessions.pop(chat_id, None)
        return
    
    # 15-second timer
    await asyncio.sleep(15)
    
    # Check if game is still active
    if chat_id in game_sessions:
        answer = game_sessions[chat_id]["answer"]
        game_sessions.pop(chat_id, None)
        await context.bot.send_message(
            chat_id,
            f"⏰ Time's up! The answer was: {answer}"
        )

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_guess = update.message.text
    
    # Check if game is active in this chat
    if chat_id not in game_sessions:
        print(f"❌ No active game in chat {chat_id}")
        return
    
    # Get correct answer
    correct_answer = game_sessions[chat_id]["answer"]
    
    print(f"\n🎯 GUESS ATTEMPT:")
    print(f"Chat: {chat_id}")
    print(f"User guess: '{user_guess}'")
    print(f"Correct answer: '{correct_answer}'")
    
    # Check if guess is correct
    if is_correct_guess(user_guess, correct_answer):
        # Correct guess!
        game_sessions.pop(chat_id, None)
        await update.message.reply_text(
            f"✅ Correct! It was: {correct_answer}\n\n"
            f"Starting next round..."
        )
        # Start next round after delay
        await asyncio.sleep(2)
        await play(update, context)
    else:
        # Wrong guess - give hint
        first_letter = correct_answer[0].upper()
        await update.message.reply_text(
            f"❌ Wrong guess! Try again.\n"
            f"💡 Hint: Name starts with '{first_letter}'"
        )

async def addcharacter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new character - reply to image with /add <name>"""
    if not context.args:
        await update.message.reply_text("Usage: Reply to an image with:\n/add <character name>")
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
    
    # Create filename
    safe_name = char_name.lower().replace(" ", "_")
    safe_name = re.sub(r'[^\w_]', '', safe_name)  # Remove special chars
    image_path = f"images/{safe_name}.jpg"
    
    await file.download_to_drive(image_path)
    
    # Load existing data
    data = load_data()
    
    # Check for duplicates (case-insensitive)
    for char in data["characters"]:
        if char["name"].lower() == char_name.lower():
            await update.message.reply_text(f"⚠️ '{char_name}' already exists!")
            return
    
    # Add new character
    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    
    save_data(data)
    
    await update.message.reply_text(
        f"✅ Character added!\n"
        f"Name: {char_name}\n"
        f"Image: {image_path}\n"
        f"Total characters: {len(data['characters'])}"
    )
    
    print(f"\n➕ CHARACTER ADDED:")
    print(f"Name: '{char_name}'")
    print(f"Image: {image_path}")

async def listcharacters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all characters"""
    data = load_data()
    
    if not data["characters"]:
        await update.message.reply_text("No characters yet! Use /add to add some.")
        return
    
    text = f"📋 Total Characters: {len(data['characters'])}\n\n"
    for i, char in enumerate(data["characters"], 1):
        text += f"{i}. {char['name']}\n"
    
    # Telegram has 4096 char limit
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    
    await update.message.reply_text(text)

async def testmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test name matching"""
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
        if is_correct_guess(test_name, char["name"]):
            results.append(f"✅ {char['name']}")
        else:
            results.append(f"❌ {char['name']}")
    
    response = f"Testing: '{test_name}'\n\n" + "\n".join(results)
    
    # Truncate if too long
    if len(response) > 4000:
        response = response[:4000] + "\n... (truncated)"
    
    await update.message.reply_text(response)

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show debug info about current game"""
    chat_id = update.effective_chat.id
    
    if chat_id in game_sessions:
        game = game_sessions[chat_id]
        await update.message.reply_text(
            f"🔧 Debug Info:\n"
            f"Answer: '{game['answer']}'\n"
            f"User ID: {game['user_id']}\n"
            f"Active games: {len(game_sessions)}"
        )
    else:
        await update.message.reply_text("No active game in this chat")

def main() -> None:
    """Start the bot"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("❌ BOT_TOKEN not set!")
        return
    
    print("🚀 Starting Anime Guess Bot...")
    
    # Load data at startup
    data = load_data()
    print(f"📁 Loaded {len(data['characters'])} characters")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("splay", play))
    application.add_handler(CommandHandler("sadd" , addcharacters))
    application.add_handler(CommandHandler("list", listcharacters))
    application.add_handler(CommandHandler("test", testmatch))
    application.add_handler(CommandHandler("debug", debug))
    
    # Add message handler for guesses (MUST BE LAST!)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    
    print("✅ Bot is running...")
    application.run_polling(allowed_updates=None)

if __name__ == '__main__':
    main()
