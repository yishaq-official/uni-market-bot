from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest, Forbidden
from src.database import get_post, update_post_status, update_post_message_id, get_user
from src.config import CHANNEL_ID
import logging

logger = logging.getLogger(__name__)

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Admin clicks on Approve/Reject."""
    query = update.callback_query
    await query.answer()
    
    # 1. ROBUST PARSING
    data = query.data or ""
    parts = data.split('_')
    action = parts[0]
    
    try:
        post_id = int(parts[-1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data: {data}")
        return

    try:
        post = get_post(post_id)
        if not post:
            await query.edit_message_caption("⚠️ Error: Post not found.")
            return

        # --- PREPARE DATA ---
        lines = post['content'].splitlines()
        title = lines[0]
        
        # Grab the ORIGINAL Admin Message content to preserve it
        # We check if it's a caption (photo) or text (no photo)
        original_content = query.message.caption or query.message.text or f"Item: {title}"

        # ==========================================
        #             REJECT FLOW
        # ==========================================
        if action == "reject":
            update_post_status(post_id, 'REJECTED')
            
            # 1. Hide Admin Buttons (Keep content visible)
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            # 2. Add "REJECTED" Tag to existing message
            updated_content = f"❌ REJECTED ❌\n\n{original_content}"
            
            try:
                if query.message.photo:
                    await query.edit_message_caption(caption=updated_content)
                else:
                    await query.edit_message_text(text=updated_content)
            except Exception as e:
                logger.warning(f"Failed to update admin message text: {e}")

            # 3. Notify User (Plain Text)
            try:
                await context.bot.send_message(
                    chat_id=post['user_id'], 
                    text=f"❌ Your post for '{title}' was declined."
                )
            except Forbidden:
                logger.warning(f"Bot forbidden to message user {post['user_id']}.")
            except Exception as e:
                logger.error(f"Failed to notify user {post['user_id']}: {e}")

        # ==========================================
        #             APPROVE FLOW
        # ==========================================
        elif action == "approve":
            update_post_status(post_id, 'APPROVED')
            
            # 1. Hide Admin Buttons First
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            # 2. Add "APPROVED" Tag to existing message (Immediate Feedback)
            updated_content = f"✅ APPROVED\n\n{original_content}"
            try:
                if query.message.photo:
                    await query.edit_message_caption(caption=updated_content)
                else:
                    await query.edit_message_text(text=updated_content)
            except Exception:
                pass

            # 3. PREPARE PUBLIC CHANNEL POST
            seller = get_user(post['user_id'])
            # Extract location from DB content or User Profile
            location_text = seller['location'] if seller else "Unknown"
            desc_start_index = 1
            if len(lines) > 1 and lines[1].startswith("Location: "):
                location_text = lines[1].replace("Location: ", "")
                desc_start_index = 2
            desc = "\n".join(lines[desc_start_index:]) if len(lines) > desc_start_index else ""

            if post['type'] == 'LOST':
                header = f"🔴 LOST: {title}"
                status_line = f"📢 Help Needed!"
                public_btn_text = "🙋‍♂️ I Found It"
                user_close_btn = "🎉 I Found My Item"
            elif post['type'] == 'FOUND':
                header = f"🟢 FOUND: {title}"
                status_line = f"❓ Is this yours?"
                public_btn_text = "🫵 It's Mine"
                user_close_btn = "🤝 Owner Found / Returned"
            else: # SELL
                header = f"📦 {title}"
                status_line = f"💰 Price: {post['price']} ETB\n🛠 📜Condition: {post['condition']}"
                public_btn_text = "📩 Contact Seller"
                user_close_btn = "🔴 Mark as Sold"

            public_text = (
                f"{header}\n"
                f"➖➖➖➖➖➖➖➖\n"
                f"{status_line}\n"
                f"⛩️ Location: {location_text}\n"
                f"➖➖➖➖➖➖➖➖\n"
                f"📝 {desc}\n"
                f"➖➖➖➖➖➖➖➖\n"
                f"🆔 Post ID: `{post_id}`"
                f"➖➖➖➖➖➖➖➖\n"
                f"@dbumarketersbot : use this link to access the bot\n"
            )
            
            contact_url = f"tg://user?id={post['user_id']}"
            channel_markup = InlineKeyboardMarkup([[InlineKeyboardButton(public_btn_text, url=contact_url)]])
            
            try:
                # Send to Channel
                if post['photo_id'] and post['photo_id'] != 'skipped':
                    msg = await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=post['photo_id'],
                        caption=public_text,
                        reply_markup=channel_markup,
                        parse_mode='Markdown'
                    )
                else:
                    msg = await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=public_text,
                        reply_markup=channel_markup,
                        parse_mode='Markdown'
                    )
                
                update_post_message_id(post_id, msg.message_id)

                # Update Admin Message FINAL confirmation
                # (We already added "APPROVED" above, we can leave it or add "PUBLISHED")
                final_admin_content = f"✅ APPROVED & PUBLISHED\n\n{original_content}"
                if query.message.photo:
                    await query.edit_message_caption(caption=final_admin_content)
                else:
                    await query.edit_message_text(text=final_admin_content)

            except Exception as e:
                logger.error(f"Failed to post to channel: {e}")
                # Try to warn admin if channel post failed
                try:
                    fail_text = f"⚠️ CHANNEL POST FAILED (Check Permissions)\n\n{original_content}"
                    if query.message.photo:
                        await query.edit_message_caption(caption=fail_text)
                    else:
                        await query.edit_message_text(text=fail_text)
                except: pass
                return

            # 4. NOTIFY USER
            control_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(user_close_btn, callback_data=f"sold_{post_id}")]
            ])
            
            try:
                await context.bot.send_message(
                    chat_id=post['user_id'],
                    text=(
                        f"✅ Your Post is Live!\n\n"
                        f"Item: {title}\n"
                        f"Status: Published to Channel\n"
                        f"you can get the channel by: @dbumarketers\n\n"
                        f"👇 Click the button below ONLY when the transaction is finished:"
                    ),
                    reply_markup=control_markup
                )
            except Exception as e:
                logger.error(f"❌ COULD NOT NOTIFY USER {post['user_id']}: {e}")

    except Exception:
        logger.exception(f"Critical error in handle_approval. callback_data={data}")


async def handle_sold_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the User clicking the 'Close Case' button."""
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    parts = data.split('_')
    
    try:
        post_id = int(parts[-1])
        post = get_post(post_id)
        if not post:
            await query.edit_message_text("⚠️ Error: Post no longer exists.")
            return

        update_post_status(post_id, 'SOLD')
        
        # Prepare Channel Update
        lines = post['content'].splitlines()
        title = lines[0]
        
        seller = get_user(post['user_id'])
        location_text = seller['location'] if seller else "Unknown"
        desc_start_index = 1
        if len(lines) > 1 and lines[1].startswith("Location: "):
            location_text = lines[1].replace("Location: ", "")
            desc_start_index = 2
        desc = "\n".join(lines[desc_start_index:]) if len(lines) > desc_start_index else ""
        
        if post['type'] == 'LOST':
            status_label = "✅ Status: FOUND (Case Closed)"
        elif post['type'] == 'FOUND':
            status_label = "🤝 Status: RETURNED (Owner Found)"
        else:
            status_label = "🔴 Status: SOLD"

        updated_text = (
            f"🏁 CASE CLOSED: {title}\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"{status_label}\n"
            f"📍 Location: {location_text}\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"📝 {desc}\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🆔 Post ID: `{post_id}`\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"@dbumarketersbot : use this link to access the bot"
        )
        
        try:
            if post['photo_id'] and post['photo_id'] != 'skipped':
                await context.bot.edit_message_caption(
                    chat_id=CHANNEL_ID,
                    message_id=post['message_id'],
                    caption=updated_text,
                    parse_mode='Markdown',
                    reply_markup=None 
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=post['message_id'],
                    text=updated_text,
                    parse_mode='Markdown',
                    reply_markup=None
                )
        except Exception as e:
            logger.warning(f"Could not update channel message: {e}")

        await query.edit_message_text(f"✅ Success! Channel post updated to:\n{status_label}", parse_mode='Markdown')

    except Exception:
        logger.exception(f"Error in handle_sold_status. data={data}")