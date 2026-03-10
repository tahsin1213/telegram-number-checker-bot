#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from datetime import datetime
from telethon import TelegramClient, errors
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import json
import sys

# ============================================
# YOUR CREDENTIALS - KEEP PRIVATE!
# ============================================
BOT_TOKEN = "8632730905:AAHql-0pOElg8eKkfEHLLBh7yVIxmzwCA7s"
API_ID = 35774757
API_HASH = "94713b7d31460226915720d581f98ad9"

# ============================================
# YOUR TELEGRAM USER ID - CHANGE THIS!
# ============================================
ADMIN_IDS = [8409706278]  # <-- YOUR TELEGRAM ID HERE

# ============================================
# LOGGING SETUP
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/tmp/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# TELEGRAM CLIENT - FIXED FOR RAILWAY
# ============================================
telegram_client = None

async def get_telegram_client():
    """Initialize and return Telegram client - Railway compatible"""
    global telegram_client
    try:
        if telegram_client is None:
            logger.info("Creating new Telegram client...")
            # Use /tmp directory for session files (writable in Railway)
            session_file = '/tmp/admin_session'
            telegram_client = TelegramClient(session_file, API_ID, API_HASH)
            
            # Start client
            await telegram_client.start()
            logger.info("Telegram client started successfully")
            
            # Test client
            me = await telegram_client.get_me()
            logger.info(f"Logged in as: {me.first_name}")
            
        return telegram_client
    except Exception as e:
        logger.error(f"Failed to start Telegram client: {e}")
        raise e

async def check_phone_number(phone):
    """Check if phone number exists on Telegram"""
    try:
        client = await get_telegram_client()
        
        # Format phone number
        original_phone = phone
        if phone.startswith('0'):
            phone = '+88' + phone
        elif not phone.startswith('+'):
            phone = '+' + phone
            
        logger.info(f"Checking phone: {original_phone} -> {phone}")
        
        try:
            entity = await client.get_entity(phone)
            
            result = {
                "found": True,
                "phone": phone,
                "user_id": entity.id,
                "username": f"@{entity.username}" if entity.username else None,
                "first_name": entity.first_name or "",
                "last_name": entity.last_name or "",
                "verified": getattr(entity, 'verified', False),
                "bot": getattr(entity, 'bot', False),
                "premium": getattr(entity, 'premium', False)
            }
            logger.info(f"Found: {phone} - {entity.first_name}")
            return result
            
        except errors.UsernameNotOccupiedError:
            logger.info(f"Not found: {phone}")
            return {"found": False, "phone": phone, "error": "Not found on Telegram"}
        except errors.FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds}s for {phone}")
            return {"found": False, "phone": phone, "error": f"Flood wait {e.seconds}s"}
        except Exception as e:
            logger.error(f"Error checking {phone}: {e}")
            return {"found": False, "phone": phone, "error": str(e)}
            
    except Exception as e:
        logger.error(f"Fatal error in check_phone_number: {e}")
        return {"found": False, "phone": phone, "error": "Server error"}

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# ============================================
# COMMAND HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    logger.info(f"Start command from user: {user_id}")
    
    if not is_admin(user_id):
        logger.warning(f"Unauthorized access attempt from {user_id}")
        await update.message.reply_text("⛔ Unauthorized. This bot is private.")
        return
    
    keyboard = [
        [InlineKeyboardButton("🔍 Single Check", callback_data="single")],
        [InlineKeyboardButton("📋 Bulk Check", callback_data="bulk")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔐 **Admin Panel**\n\nSelect option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Use: /check 01712345678")
        return
    
    phone = context.args[0]
    wait_msg = await update.message.reply_text("🔍 Checking...")
    
    try:
        result = await check_phone_number(phone)
        
        if result.get("found"):
            reply = (
                f"✅ **FOUND**\n\n"
                f"📞 **Phone:** `{result['phone']}`\n"
                f"🆔 **ID:** `{result['user_id']}`\n"
                f"👤 **Name:** {result['first_name']} {result['last_name']}\n"
                f"🔖 **Username:** {result['username'] or 'None'}\n"
                f"⭐ **Premium:** {'Yes' if result.get('premium') else 'No'}\n"
                f"🤖 **Bot:** {'Yes' if result.get('bot') else 'No'}"
            )
        else:
            reply = (
                f"❌ **NOT FOUND**\n\n"
                f"📞 **Phone:** `{result['phone']}`\n"
                f"⚠️ **Reason:** {result.get('error', 'Unknown')}"
            )
        
        await wait_msg.delete()
        await update.message.reply_text(reply, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in check_command: {e}")
        await wait_msg.delete()
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def bulk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bulk command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    context.user_data['awaiting_file'] = True
    await update.message.reply_text(
        "📤 **Send text file**\n\nOne number per line\nExample:\n01712345678\n01887654321",
        parse_mode='Markdown'
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded files for bulk check"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id) or not context.user_data.get('awaiting_file'):
        return
    
    try:
        file = await update.message.document.get_file()
        file_path = '/tmp/numbers.txt'
        await file.download_to_drive(file_path)
        
        with open(file_path, 'r') as f:
            numbers = [line.strip() for line in f if line.strip()]
        
        if not numbers:
            await update.message.reply_text("❌ Empty file!")
            return
        
        status_msg = await update.message.reply_text(f"📋 Processing {len(numbers)} numbers...")
        
        results = []
        for i, num in enumerate(numbers, 1):
            try:
                result = await check_phone_number(num)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {num}: {e}")
                results.append({"found": False, "phone": num, "error": str(e)})
            
            if i % 5 == 0:
                await status_msg.edit_text(f"📋 Progress: {i}/{len(numbers)}")
            
            await asyncio.sleep(1)
        
        found_count = sum(1 for r in results if r.get('found'))
        
        # Generate report
        report_lines = []
        report_lines.append("📊 BULK CHECK REPORT")
        report_lines.append("")
        report_lines.append(f"Total: {len(numbers)}")
        report_lines.append(f"✅ Found: {found_count}")
        report_lines.append(f"❌ Not Found: {len(numbers) - found_count}")
        report_lines.append("")
        report_lines.append("Details:")
        
        for r in results:
            status = "✅" if r.get('found') else "❌"
            name = f" - {r.get('first_name', '')}" if r.get('found') else ""
            report_lines.append(f"{status} {r['phone']}{name}")
        
        report = "\n".join(report_lines)
        
        # Save report to file
        filename = f"/tmp/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            f.write(report.replace('**', ''))
        
        # Send response
        if len(report) <= 4000:
            await update.message.reply_text(report, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"✅ Complete! Found: {found_count}/{len(numbers)}")
        
        # Send file
        with open(filename, 'rb') as f:
            await update.message.reply_document(f, filename=os.path.basename(filename))
        
        # Cleanup
        os.remove(file_path)
        os.remove(filename)
        context.user_data['awaiting_file'] = False
        
    except Exception as e:
        logger.error(f"Error in handle_document: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        context.user_data['awaiting_file'] = False

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    help_text = (
        "❓ **HELP**\n\n"
        "/start - Open panel\n"
        "/check [number] - Single check\n"
        "/bulk - Bulk check\n"
        "/help - This menu\n\n"
        "**Bulk format:**\n"
        "Send .txt file\n"
        "One number per line"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.edit_message_text("⛔ Unauthorized")
        return
    
    if query.data == "single":
        await query.edit_message_text("🔍 Send phone number")
    elif query.data == "bulk":
        context.user_data['awaiting_file'] = True
        await query.edit_message_text("📤 Send .txt file")
    elif query.data == "help":
        await query.edit_message_text("❓ /check [num] or /bulk")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (phone numbers)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    text = update.message.text.strip()
    
    # Check if it's a phone number
    if text.replace('+', '').replace('-', '').replace(' ', '').isdigit():
        wait_msg = await update.message.reply_text("🔍 Checking...")
        
        try:
            result = await check_phone_number(text)
            
            if result.get("found"):
                reply = (
                    f"✅ **FOUND**\n\n"
                    f"📞 **Phone:** `{result['phone']}`\n"
                    f"🆔 **ID:** `{result['user_id']}`\n"
                    f"👤 **Name:** {result['first_name']} {result['last_name']}\n"
                    f"🔖 **Username:** {result['username'] or 'None'}"
                )
            else:
                reply = (
                    f"❌ **NOT FOUND**\n\n"
                    f"📞 **Phone:** `{result['phone']}`\n"
                    f"⚠️ **Reason:** {result.get('error', 'Unknown')}"
                )
            
            await wait_msg.delete()
            await update.message.reply_text(reply, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await wait_msg.delete()
            await update.message.reply_text(f"❌ Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ An error occurred. Please try again.")
    except:
        pass

def main():
    """Start the bot"""
    logger.info("="*50)
    logger.info("Starting Telegram Number Checker Bot")
    logger.info("="*50)
    
    # Check credentials
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("Missing credentials!")
        return
    
    logger.info(f"Bot Token: {BOT_TOKEN[:10]}...")
    logger.info(f"API ID: {API_ID}")
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    
    try:
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("check", check_command))
        app.add_handler(CommandHandler("bulk", bulk_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        # Add error handler
        app.add_error_handler(error_handler)
        
        logger.info("Bot is running...")
        
        # Start bot
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        raise e

if __name__ == "__main__":
    main()
