# Anime NGuess Bot 🎮

A Telegram bot where players guess anime characters from images within 15 seconds!

## Features
- Guess anime characters from images
- 15-second time limit per round
- Strike system (consecutive correct guesses)
- Score tracking

## Setup

1. Clone the repository
2. Install dependencies: `poetry install`
3. Copy `.env.example` to `.env` and add your BOT_TOKEN
4. Run: `python main.py`

## Deployment on Railway

1. Push to GitHub
2. Create Railway project
3. Connect GitHub repository
4. Add environment variable `BOT_TOKEN`
5. Deploy!

## Commands
- `/start` - Start the bot
- `/nguess` or `/play` - Start a new game
- `/score` - Check your score
- `/stop` - Stop current game
- `/leaderboard` - Global leaderboard
- `/cupload` (Owner only) - Upload new character
