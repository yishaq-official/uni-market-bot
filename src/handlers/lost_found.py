from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
# 1. ADDED count_recent_posts to imports
from src.database import get_user, create_post, register_seller, count_recent_posts
from src.config import ADMIN_GROUP_ID

# --- STATES ---
# Standard Lost/Found States
NAME, CAMPUS, SPECIFIC_LOC, DESCRIPTION, PHOTO, CONFIRM = range(6)

# Internal Registration States (Prefixed to avoid confusion)
AUTH_PHONE, AUTH_NAME, AUTH_LOCATION, AUTH_ID_TYPE, AUTH_ID_INPUT = range(6, 11)

async def start_lost_found(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    db_user = get_user(user.id)

    # 2. CHECK RATE LIMIT (New Feature)
    post_count = count_recent_posts(user.id)
    if post_count >= 3:
        await update.message.reply_text(
            "⏳ **Daily Limit Reached**\n\n"
            "You have reached your limit of 3 posts per 24 hours.\n"
            "Please try again tomorrow!"
        )
        return ConversationHandler.END

    # CASE 1: I LOST (No Registration Needed)
    if "I Lost" in text:
        context.user_data['type'] = 'LOST'
        await update.message.reply_text("📢 Report Lost Item\n\nWhat is the Item Name? (e.g. Blue Wallet)")
        return NAME

    # CASE 2: I FOUND (Registration Required)
    else:
        context.user_data['type'] = 'FOUND'
        
        # If Registered -> Proceed
        if db_user and db_user['is_seller']:
            await update.message.reply_text("🙋‍♂️ Report Found Item\n\nWhat is the Item Name? (e.g. Keys)")
            return NAME
        
        # If NOT Registered -> Start Internal Registration
        else:
            contact_btn = KeyboardButton("📱 Share My Phone Number", request_contact=True)
            markup = ReplyKeyboardMarkup([[contact_btn]], one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                "🔒 Verification Required\n\n"
                "To report a Found item, we need to verify your identity first.\n"
                "Please click the button to share your phone number.",
                reply_markup=markup
            )
            return AUTH_PHONE

# ==========================================
#      INTERNAL REGISTRATION FLOW
# ==========================================

async def auth_save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact.user_id != update.effective_user.id:
        await update.message.reply_text("❌ Please share YOUR own contact.")
        return AUTH_PHONE
    context.user_data['reg_phone'] = update.message.contact.phone_number
    await update.message.reply_text("✅ Phone Saved.\n\nEnter your Full Name:", reply_markup=ReplyKeyboardRemove())
    return AUTH_NAME

async def auth_save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_name'] = update.message.text
    locations = [['🏫 Main Campus', '🏥 Health Campus'], ['🏗️ Mehal Meda', '🏠 Outside']]
    markup = ReplyKeyboardMarkup(locations, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📍 Where are you located?", reply_markup=markup)
    return AUTH_LOCATION

async def auth_save_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_location'] = update.message.text
    id_types = [['🎓 University ID'], ['🆔 National ID']]
    markup = ReplyKeyboardMarkup(id_types, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Which ID will you use?", reply_markup=markup)
    return AUTH_ID_TYPE

async def auth_save_id_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_id_type'] = update.message.text
    if "University" in update.message.text:
        await update.message.reply_text("Enter ID (Start with **DBU**, 10 chars):", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Enter National ID (16 digits):", reply_markup=ReplyKeyboardRemove())
    return AUTH_ID_INPUT

async def auth_finish_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Simplified validation for speed, can add strict checks if needed)
    id_val = update.message.text.strip().upper()
    user = update.effective_user
    
    # Save to DB
    register_seller(
        user.id, user.username, 
        context.user_data['reg_name'], 
        context.user_data['reg_phone'], 
        id_val, 
        context.user_data['reg_location']
    )
    
    # AUTO-REDIRECT: Jump straight to the "I Found" flow
    await update.message.reply_text(
        "🎉 Registration Complete!\n\n"
        "Now, let's continue with your report.\n"
        "What is the Item Name? (e.g. Keys)"
    )
    return NAME

# ==========================================
#      STANDARD LOST/FOUND FLOW
# ==========================================

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    
    locs = [['🏫 Main Campus', '🏥 Health Campus'], ['🏗️ Mehal Meda', '🏠 Outside']]
    markup = ReplyKeyboardMarkup(locs, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text("📍 **Step 1:** Select the Campus/Area:", reply_markup=markup)
    return CAMPUS

async def receive_campus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['campus'] = update.message.text
    
    if context.user_data['type'] == 'LOST':
        msg = "📍 Step 2: Exact Location\n\nWhere did you see it last? (e.g. 'Near Block 204')"
    else:
        msg = "📍 Step 2: Exact Location\n\nWhere exactly did you find it? (e.g. 'Library 2nd floor')"

    await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    return SPECIFIC_LOC

async def receive_specific_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    campus = context.user_data['campus']
    specific = update.message.text
    context.user_data['final_location'] = f"{campus} - {specific}"
    
    if context.user_data['type'] == 'LOST':
        msg = "📝 Description:\nDescribe the item details."
    else:
        msg = "📝 Abstract Description:\nDescribe briefly without revealing secrets."

    await update.message.reply_text(msg)
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    
    markup = ReplyKeyboardMarkup([['⏩ Skip Photo']], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📸 **Add a Photo?** (Optional)\nSend picture or Skip.", reply_markup=markup)
    return PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['photo_id'] = update.message.photo[-1].file_id
    else:
        context.user_data['photo_id'] = 'skipped'
    
    return await confirm_page(update, context)

async def confirm_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    icon = "🔴" if data['type'] == 'LOST' else "🟢"
    lbl = data['type']

    summary = (
        f"{icon} CONFIRM {lbl} REPORT\n\n"
        f"📦 Item: {data['name']}\n"
        f"📍 Loc: {data['final_location']}\n"
        f"📝 Desc: {data['desc']}\n"
        f"📸 Photo: {'Yes' if data['photo_id'] != 'skipped' else 'No'}"
    )
    
    markup = ReplyKeyboardMarkup([['✅ Submit'], ['❌ Cancel']], one_time_keyboard=True, resize_keyboard=True)
    if data['photo_id'] != 'skipped':
        await update.message.reply_photo(data['photo_id'], caption=summary, reply_markup=markup)
    else:
        await update.message.reply_text(summary, reply_markup=markup)
    return CONFIRM

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '✅ Submit':
        data = context.user_data
        user = update.effective_user
        
        # NOTE: db_user fetch must happen HERE to ensure we catch newly registered users
        db_user = get_user(user.id)
        
        # Fallback for "I Lost" users who are guests
        if not db_user:
            user_name = "Guest User"
            user_phone = "Hidden"
        else:
            user_name = db_user['real_name']
            user_phone = db_user['phone_number']

        # Save to DB
        post_id = create_post(
            user_id=user.id,
            type=data['type'],
            category='LostFound',
            condition='N/A',
            content=f"{data['name']}\nLocation: {data['final_location']}\n{data['desc']}",
            price="N/A",
            photo_id=data['photo_id']
        )
        
        # Admin Notification
        admin_text = (
            f"🚨 NEW {data['type']} REPORT\n"
            f"👤 User: {user_name} ({user_phone})\n"
            f"📦 Item: {data['name']}\n"
            f"📍 Loc: {data['final_location']}\n"
            f"📝 Desc: {data['desc']}"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")]
        ]
        
        if data['photo_id'] != 'skipped':
            await context.bot.send_photo(ADMIN_GROUP_ID, data['photo_id'], caption=admin_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(ADMIN_GROUP_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        await update.message.reply_text("✅ Sent to Admins!", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())

    from src.main import start
    await start(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    from src.main import start
    await start(update, context)
    return ConversationHandler.END

# HANDLER DEFINITION
lost_found_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^(📢 I Lost|🙋‍♂️ I Found)$"), start_lost_found)],
    states={
        # Internal Auth Steps
        AUTH_PHONE: [MessageHandler(filters.CONTACT, auth_save_phone)],
        AUTH_NAME: [MessageHandler(filters.TEXT, auth_save_name)],
        AUTH_LOCATION: [MessageHandler(filters.TEXT, auth_save_location)],
        AUTH_ID_TYPE: [MessageHandler(filters.TEXT, auth_save_id_type)],
        AUTH_ID_INPUT: [MessageHandler(filters.TEXT, auth_finish_reg)],

        # Lost/Found Steps
        NAME: [MessageHandler(filters.TEXT, receive_name)],
        CAMPUS: [MessageHandler(filters.TEXT, receive_campus)],
        SPECIFIC_LOC: [MessageHandler(filters.TEXT, receive_specific_loc)],
        DESCRIPTION: [MessageHandler(filters.TEXT, receive_description)],
        PHOTO: [MessageHandler(filters.PHOTO | filters.Regex("^⏩ Skip Photo$"), receive_photo)],
        CONFIRM: [MessageHandler(filters.Regex("^(✅ Submit|❌ Cancel)$"), submit_report)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)