import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.database import get_user, register_seller

PHONE, NAME, LOCATION, ID_TYPE, ID_INPUT = range(5)

async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    if db_user and db_user['is_seller']:
        await update.message.reply_text("✅ You are already registered.")
        return ConversationHandler.END

    contact_btn = KeyboardButton("📱 Share My Phone Number", request_contact=True)
    markup = ReplyKeyboardMarkup([[contact_btn], ['❌ Cancel']], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("👋 Registration\nClick the button to share your phone number. your number is just for verification purpose. it will not be shown for anyone. you can hide your phone number in your telegram privacy settings if you don't want to show it when someone visit your profile.", reply_markup=markup)
    return PHONE

async def save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact.user_id != update.effective_user.id:
        await update.message.reply_text("❌ Please share YOUR own contact.")
        return PHONE
    context.user_data['phone'] = update.message.contact.phone_number
    await update.message.reply_text("✅ Phone Saved.\n\nEnter your Full Name:", reply_markup=ReplyKeyboardRemove())
    return NAME

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(update.message.text) < 3:
        await update.message.reply_text("❌ Name too short.")
        return NAME
    context.user_data['real_name'] = update.message.text
    
    locations = [['🏫 Main Campus', '🏥 Health Campus'], ['🏗️ Mehal Meda', '🏠 Outside']]
    markup = ReplyKeyboardMarkup(locations, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📍 Where are you located?", reply_markup=markup)
    return LOCATION

async def save_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    
    id_types = [['🎓 University ID'], ['🆔 National ID']]
    markup = ReplyKeyboardMarkup(id_types, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Which ID will you use for verification?", reply_markup=markup)
    return ID_TYPE

async def save_id_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selection = update.message.text
    context.user_data['id_type'] = selection
    
    if "University" in selection:
        await update.message.reply_text("Enter your ID (Must start with DBU and be 10 chars).\nExample: `DBU1234567`", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Enter your National ID (16 digits).", reply_markup=ReplyKeyboardRemove())
    return ID_INPUT

async def validate_id_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    id_val = update.message.text.strip().upper()
    id_type = context.user_data['id_type']
    
    # VALIDATION
    if "University" in id_type:
        if not (id_val.startswith("DBU") and len(id_val) == 10):
            await update.message.reply_text("❌ Invalid ID Number. Try again.")
            return ID_INPUT
    else:
        if not (id_val.isdigit() and len(id_val) == 16):
            await update.message.reply_text("❌ Invalid National ID. Must be 16 digits. Try again.")
            return ID_INPUT

    # SAVE TO DB
    user = update.effective_user
    register_seller(
        user.id, user.username, 
        context.user_data['real_name'], 
        context.user_data['phone'], 
        id_val, 
        context.user_data['location']
    )
    
    # --- FIX: Show the Marketplace Menu Immediately ---
    buttons = [['➕ Sell Item'], ['🔙 Main Menu']]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎉 Registration Successful!\n"
        "You can now post items for sale.\n"
        "Use the menu below:", 
        reply_markup=markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If they cancel, send them back to Main Menu
    buttons = [['🛒 Marketplace', '🔍 Lost & Found']]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text("❌ Registration cancelled.", reply_markup=markup)
    return ConversationHandler.END

registration_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📝 Register$"), start_register)],
    states={
        PHONE: [MessageHandler(filters.CONTACT, save_phone)],
        NAME: [MessageHandler(filters.TEXT, save_name)],
        LOCATION: [MessageHandler(filters.TEXT, save_location)],
        ID_TYPE: [MessageHandler(filters.TEXT, save_id_type)],
        ID_INPUT: [MessageHandler(filters.TEXT, validate_id_and_finish)]
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel)]
)
