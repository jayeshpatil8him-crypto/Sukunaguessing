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

# ================= GAME VARIABLES =================
current_game = None  # Just store ONE game for testing
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 TEST BOT\n"
        "/play - Start game\n"
        "/answer - Show current answer\n"
        "Just type your guess!"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_game
    
    # Load characters
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        await update.message.reply_text("No data.json file!")
        return
    
    if not data.get("characters"):
        await update.message.reply_text("No characters! Use /add first.")
        return
    
    # Pick random character
    character = random.choice(data["characters"])
    
    print(f"\n" + "="*50)
    print(f"🎮 GAME STARTED")
    print(f"Selected character: '{character['name']}'")
    print(f"Image path: '{character['image']}'")
    print("="*50)
    
    # Store game
    current_game = {
        "answer": character["name"],
        "chat_id": update.effective_chat.id,
        "user_id": update.effective_user.id
    }
    
    # Send image
    try:
        await update.message.reply_photo(
            photo=open(character["image"], "rb"),
            caption=f"GUESS: Type the name\nAnswer is: '{character['name']}'"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        current_game = None
        return
    
    # Timer
    await asyncio.sleep(15)
    
    if current_game and current_game["chat_id"] == update.effective_chat.id:
        await update.message.reply_text(f"⏰ Time's up! Answer: '{character['name']}'")
        current_game = None

async def check_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_game
    
    if not current_game:
        print("❌ No active game")
        return
    
    user_guess = update.message.text.strip()
    correct_answer = current_game["answer"]
    
    print(f"\n" + "="*50)
    print(f"🎯 GUESS RECEIVED")
    print(f"User typed: '{user_guess}'")
    print(f"Expected: '{correct_answer}'")
    print(f"Comparison: '{user_guess.lower()}' == '{correct_answer.lower()}'")
    print(f"Result: {user_guess.lower() == correct_answer.lower()}")
    print("="*50)
    
    # SIMPLE EXACT MATCH (case-insensitive)
    if user_guess.lower() == correct_answer.lower():
        await update.message.reply_text(f"✅ CORRECT! You guessed: '{user_guess}'")
        current_game = None
        # Start next round
        await asyncio.sleep(2)
        await play(update, context)
    else:
        await update.message.reply_text(
            f"❌ WRONG!\n"
            f"You said: '{user_guess}'\n"
            f"Correct: '{correct_answer}'"
        )

async def show_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_game
    if current_game:
        await update.message.reply_text(f"Current answer: '{current_game['answer']}'")
    else:
        await update.message.reply_text("No active game")

async def add_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Reply to image with: /add <name>")
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
    
    # Save image
    safe_name = char_name.lower().replace(" ", "_").replace(".", "")
    image_path = f"images/{safe_name}.jpg"
    await file.download_to_drive(image_path)
    
    # Load or create data
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
    except:
        data = {"characters": []}
    
    # Add character
    data["characters"].append({
        "name": char_name,
        "image": image_path
    })
    
    # Save
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    
    await update.message.reply_text(f"✅ Added: {char_name}")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ No BOT_TOKEN!")
        return
    
    print("🚀 TEST BOT STARTING...")
    
    app = Application.builder().token(token).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("answer", show_answer))
    app.add_handler(CommandHandler("add", add_char))
    
    # Guess handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_guess))
    
    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
