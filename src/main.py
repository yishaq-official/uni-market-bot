import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from src.config import BOT_TOKEN
# 1. UPDATED IMPORTS: Added add_to_blacklist, is_blacklisted
from src.database import init_db, get_user, get_all_users, delete_user_data, add_to_blacklist, is_blacklisted
from src.handlers.auth import registration_handler
from src.handlers.selling import selling_handler
from src.handlers.lost_found import lost_found_handler
from src.handlers.feedback import feedback_handler
from src.keep_alive import keep_alive
from src.handlers.admin import handle_approval, handle_sold_status

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- MENU NAVIGATION ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Shows the Main Menu."""
    user_id = update.effective_user.id
    
    # 2. CHECK BLACKLIST (Security)
    if is_blacklisted(user_id):
        await update.message.reply_text("⛔ You have been permanently banned from this bot.")
        return

    # Updated keyboard to include Feedback
    keyboard = [
        ['🛒 Marketplace', '🔍 Lost & Found'],
        ['📝 Feedback']
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Welcome to Uni Market!\nChoose an option:", 
        reply_markup=markup
    )

async def marketplace_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows Marketplace options (Register vs Sell)."""
    user_id = update.effective_user.id
    
    # Check Blacklist
    if is_blacklisted(user_id):
        await update.message.reply_text("⛔ You are banned.")
        return

    user = get_user(user_id)
    
    if user and user['is_seller']:
        # REGISTERED USER VIEW
        buttons = [['➕ Sell Item'], ['🔙 Main Menu']]
        msg = f"👤 Seller: {user['real_name']}\n📍 {user['location']}\n\nWhat would you like to do?"
    else:
        # GUEST VIEW
        buttons = [['📝 Register'], ['🔙 Main Menu']]
        msg = "🔒 Marketplace Access\nYou need to register to sell items."
        
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(msg, reply_markup=markup)

async def lost_found_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows Lost & Found options."""
    # Check Blacklist
    if is_blacklisted(update.effective_user.id):
        return

    buttons = [['📢 I Lost', '🙋‍♂️ I Found'], ['🔙 Main Menu']]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("🔍 Lost & Found Section", reply_markup=markup)

# --- ADMIN COMMANDS ---
ADMIN_IDS = [7775309813, 6112723745, 1836483387] 

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Access Denied.")
        return

    users = get_all_users()
    if not users:
        await update.message.reply_text("👥 Total Users: 0\n(Database is empty)")
        return

    text = f"👥 Total Users: {len(users)}\n\n"
    for u in users:
        text += f"ID: `{u['user_id']}` | {u['real_name']} | {u['phone_number']}\n"
    await update.message.reply_text(text)

# 3. SEPARATE DELETE COMMAND (Soft Reset)
async def delete_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /delete [user_id] - Removes data but allows re-registration."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Access Denied.")
        return

    try:
        if not context.args:
             await update.message.reply_text("⚠️ Usage: /delete [user_id]")
             return
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid ID.")
        return

    delete_user_data(target_id)
    await update.message.reply_text(f"🗑️ User `{target_id}` deleted (Data removed). They can re-register.", parse_mode='Markdown')

# 4. UPDATED BAN COMMAND (Hard Ban + Blacklist)
async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /ban [user_id] - Deletes data AND Blacklists forever."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Access Denied.")
        return

    try:
        if not context.args:
             await update.message.reply_text("⚠️ Usage: /ban [user_id]")
             return
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid ID.")
        return

    # Perform Both Actions
    delete_user_data(target_id)   # 1. Clean up
    add_to_blacklist(target_id)   # 2. Block forever
    
    await update.message.reply_text(f"🚫 User `{target_id}` has been **PERMANENTLY BANNED** and data wiped.", parse_mode='Markdown')

if __name__ == '__main__':
    keep_alive()
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- HANDLERS ---
    app.add_handler(CallbackQueryHandler(handle_approval, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(handle_sold_status, pattern="^sold_"))

    app.add_handler(registration_handler)
    app.add_handler(selling_handler)
    app.add_handler(lost_found_handler)
    app.add_handler(feedback_handler)
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('users', list_users))
    
    # 5. REGISTER NEW COMMANDS
    app.add_handler(CommandHandler('ban', ban_user_cmd))
    app.add_handler(CommandHandler('delete', delete_user_cmd))
    
    app.add_handler(MessageHandler(filters.Regex("^🛒 Marketplace$"), marketplace_menu))
    app.add_handler(MessageHandler(filters.Regex("^🔍 Lost & Found$"), lost_found_menu))
    app.add_handler(MessageHandler(filters.Regex("^🔙 Main Menu$"), start))

    print("Bot is polling...")
    app.run_polling()