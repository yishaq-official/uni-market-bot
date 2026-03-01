from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
# 1. ADDED count_recent_posts to imports
from src.database import get_user, create_post, count_recent_posts
from src.config import ADMIN_GROUP_ID

PHOTO, TITLE, PRICE, CONDITION, CATEGORY, DESCRIPTION, CONFIRM = range(7)

async def start_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Check 1: Is Registered?
    if not user or not user['is_seller']:
        await update.message.reply_text("⛔ Please Register first from the main menu.")
        return ConversationHandler.END

    # Check 2: Rate Limit (New Feature)
    post_count = count_recent_posts(user_id)
    if post_count >= 3:
        await update.message.reply_text(
            "⏳ **Daily Limit Reached**\n\n"
            "You have reached your limit of 3 posts per 24 hours.\n"
            "Please try again tomorrow!"
        )
        return ConversationHandler.END

    await update.message.reply_text("📸 Send a Photo of the item.")
    return PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Safety check: ensure a photo was actually sent
    if not update.message.photo:
        await update.message.reply_text("⚠️ Please send a valid photo.")
        return PHOTO

    context.user_data['photo_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("📝 What is the Item Name?")
    return TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("💰 Price (e.g. 500 ETB):")
    return PRICE

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text.strip()
    
    # VALIDATION: Check if it is a number
    if not price_text.isdigit():
        await update.message.reply_text(
            "⚠️ Invalid Price!!\n"
            "Please enter numbers only (e.g., 500).\n"
            "Do not add 'ETB' or text."
        )
        return PRICE # Stay in the same state

    context.user_data['price'] = price_text
    
    # Condition Buttons
    markup = ReplyKeyboardMarkup([['🆕 New', '👌 Used']], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Is it New or Used?", reply_markup=markup)
    return CONDITION

async def receive_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['condition'] = update.message.text
    # Category Buttons
    cats = [['📚 Books', '💻 Electronics'], ['🔧 Tools', '🏠 Dorm Essentials']]
    markup = ReplyKeyboardMarkup(cats, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📂 Select Category:", reply_markup=markup)
    return CATEGORY

async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['category'] = update.message.text
    await update.message.reply_text(
        "📝 Description:  \nInclude reason for selling, defects, specs, etc.",
        reply_markup=ReplyKeyboardRemove()
    )
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    
    # Summary
    data = context.user_data
    user = get_user(update.effective_user.id)
    
    summary = (
        f"📦 {data['title']}\n"
        f"💰 {data['price']} | {data['condition']}\n"
        f"📍 {user['location']}\n"
        f"📝 {data['desc']}"
    )
    markup = ReplyKeyboardMarkup([['✅ Submit'], ['❌ Cancel']], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_photo(data['photo_id'], caption=summary, reply_markup=markup)
    return CONFIRM

# ... imports ...

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '✅ Submit':
        user = update.effective_user
        db_user = get_user(user.id)
        data = context.user_data
        
        # 1. Save to DB
        post_id = create_post(
            user.id, 'SELL', data['category'], data['condition'],
            f"{data['title']}\n{data['desc']}", 
            data['price'], data['photo_id']
        )
        
        # 2. ENHANCED Admin Notification (Fix for Point #3)
        admin_text = (
            f"🚨 NEW POST APPROVAL\n\n"
            f"👤 Seller: {db_user['real_name']}\n"
            f"📞 Phone: `{db_user['phone_number']}`\n"
            f"🆔 ID: `{db_user['id_number']}`\n"
            f"📍 Loc: {db_user['location']}\n"
            f"---------------------------\n"
            f"📦 Item: {data['title']}\n"
            f"💰 Price: {data['price']} ({data['condition']})\n"
            f"📂 Cat: {data['category']}\n"
            f"📝 Desc: {data['desc']}\n"
        )
        
        # Admin Buttons
        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")]
        ]
        
        await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=data['photo_id'],
            caption=admin_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # 3. FIX NAVIGATION (Fix for Point #1)
        # Give them buttons to continue using the bot
        nav_buttons = [['➕ Sell Item'], ['🔙 Main Menu']]
        markup = ReplyKeyboardMarkup(nav_buttons, resize_keyboard=True)
        
        await update.message.reply_text(
            "✅ Post Submitted!\n"
            "Admins are reviewing your ID and Item.\n"
            "You will be notified soon.\n\n"
            "What next?", 
            reply_markup=markup
        )
        
    else:
        # Cancel Logic
        nav_buttons = [['➕ Sell Item'], ['🔙 Main Menu']]
        markup = ReplyKeyboardMarkup(nav_buttons, resize_keyboard=True)
        await update.message.reply_text("❌ Cancelled.", reply_markup=markup)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Return user to the Marketplace menu instead of leaving them with no buttons
    buttons = [['➕ Sell Item'], ['🔙 Main Menu']]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("❌ Post cancelled.", reply_markup=markup)
    return ConversationHandler.END

selling_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Sell Item$"), start_sell)],
    states={
        PHOTO: [MessageHandler(filters.PHOTO, receive_photo)],
        TITLE: [MessageHandler(filters.TEXT, receive_title)],
        PRICE: [MessageHandler(filters.TEXT, receive_price)],
        CONDITION: [MessageHandler(filters.TEXT, receive_condition)],
        CATEGORY: [MessageHandler(filters.TEXT, receive_category)],
        DESCRIPTION: [MessageHandler(filters.TEXT, receive_description)],
        CONFIRM: [MessageHandler(filters.Regex("^(✅ Submit|❌ Cancel)$"), confirm_post)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)