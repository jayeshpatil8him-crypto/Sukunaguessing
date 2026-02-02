import os
import json
import random
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
TOKEN = "8464370713:AAEB6sOM3pJvBinF09M4vpYuVxrQcM4pFjs"
OWNER_ID = 7676723107 ,7974236970 # <-- YOUR TELEGRAM USER ID
DATA_FILE = "data.json"
IMAGE_DIR = "images"

game_sessions = {}  # chat_id -> game data
# =========================================


# -------- DATA HELPERS --------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"characters": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_random_character():
    data = load_data()
    if not data["characters"]:
        return None
    return random.choice(data["characters"])


# -------- GAME COMMAND --------
async def nguess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in game_sessions:
        await update.message.reply_text("⚠️ A game is already running!")
        return

    character = get_random_character()
    if not character:
        await update.message.reply_text("❌ No characters added yet.")
        return

    game_sessions[chat_id] = {
        "answer": character["name"],
        "active": True
    }

    await update.message.reply_photo(
        photo=open(character["image"], "rb"),
        caption="🎮 Guess the anime character!\n⏱️ 15 seconds"
    )

    await asyncio.sleep(15)

    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        game_sessions.pop(chat_id, None)
        await context.bot.send_message(
            chat_id,
            "⏰ Time’s up! Game over."
        )


async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in game_sessions:
        return

    guess = update.message.text.strip().lower()
    correct = game_sessions[chat_id]["answer"]

    if guess == correct:
        game_sessions.pop(chat_id, None)
        await update.message.reply_text("✅ Correct! Next round...")
        await nguess(update, context)


# -------- CHARACTER UPLOAD (OWNER ONLY) --------
async def cupload(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "❗ Reply to an IMAGE with:\n/cupload <character name>"
        )
        return

    char_name = " ".join(context.args).strip().lower()

    os.makedirs(IMAGE_DIR, exist_ok=True)

    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()

    image_path = f"{IMAGE_DIR}/{char_name.replace(' ', '_')}.jpg"
    await file.download_to_drive(image_path)

    data = load_data()

    # prevent duplicates
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
# ================= CONFIG =================


OWNER_IDS = {
    7676723107,   # Your Telegram ID
    7974236970   # Partner's Telegram ID
}



# -------- MAIN --------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("nguess", nguess))
    app.add_handler(CommandHandler("cupload", cupload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))

    print("🤖 Anime NGuess Bot running...")
    app.run_polling()

if name == "main":
    main()
