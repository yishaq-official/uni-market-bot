from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from src.config import ADMIN_GROUP_ID
# 1. IMPORT DATABASE FUNCTIONS
from src.database import log_feedback, count_recent_feedback

# State for the conversation
FEEDBACK_TEXT = 0

async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Asks user for feedback."""
    user = update.effective_user
    
    # 2. CHECK RATE LIMIT (1 per 24 hours)
    if count_recent_feedback(user.id) >= 1:
        await update.message.reply_text(
            "⏳ **Feedback Limit Reached**\n\n"
            "To prevent spam, you can only send feedback once every 24 hours.\n"
            "Please try again later!",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 Feedback & Suggestions\n\n"
        "Please type your message below (suggestions, bugs, or comments).\n"
        "Type /cancel to go back.",
        reply_markup=ReplyKeyboardRemove()
    )
    return FEEDBACK_TEXT

async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the text and forwards to Admin Group."""
    user = update.effective_user
    feedback_msg = update.message.text
    
    # 3. LOG TO DATABASE (To trigger the limit next time)
    log_feedback(user.id, feedback_msg)
    
    # Prepare message for Admin Group
    admin_text = (
        f"📩 NEW FEEDBACK\n\n"
        f"👤 From: {user.full_name} (`{user.id}`)\n"
        f"🔗 Username: @{user.username if user.username else 'N/A'}\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"{feedback_msg}"
    )
    
    # Send to Admin Group
    try:
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_text, parse_mode='Markdown')
    except Exception as e:
        # If admin group ID is wrong or bot kicked, just log it
        print(f"Failed to send feedback to admin: {e}")

    # Reply to User
    await update.message.reply_text("✅ **Thank you!** Your feedback has been sent to the admins.")
    
    # Return to Main Menu
    from src.main import start
    await start(update, context)
    return ConversationHandler.END

async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the feedback operation."""
    await update.message.reply_text("❌ Cancelled.")
    
    from src.main import start
    await start(update, context)
    return ConversationHandler.END

# Handler Definition
feedback_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📝 Feedback$"), start_feedback)],
    states={
        FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback)]
    },
    fallbacks=[CommandHandler('cancel', cancel_feedback)]
)