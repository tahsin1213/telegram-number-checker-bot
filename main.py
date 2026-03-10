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

# ============================================
# YOUR CREDENTIALS - KEEP PRIVATE!
# ============================================
BOT_TOKEN = "8632730905:AAHql-0pOElg8eKkfEHLLBh7yVIxmzwCA7s"
API_ID = 35774757
API_HASH = "94713b7d31460226915720d581f98ad9"

# ============================================
# YOUR TELEGRAM USER ID - CHANGE THIS!
# ============================================
ADMIN_IDS = [123456789]  # <-- PUT YOUR TELEGRAM ID HERE

# ============================================
# LOGGING SETUP
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# TELEGRAM CLIENT
# ============================================
telegram_client = None

async def get_telegram_client():
    global telegram_client
    if not telegram_client:
        telegram_client = TelegramClient('admin_session', API_ID, API_HASH)
        await telegram_client.start()
    return telegram_client

async def check_phone_number(phone):
    try:
        client = await get_telegram_client()
        
        if phone.startswith('0'):
            phone = '+88' + phone
        elif not phone.startswith('+'):
            phone = '+' + phone
            
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
            return result
            
        except errors.UsernameNotOccupiedError:
            return {"found": False, "phone": phone, "error": "Not found on Telegram"}
        except errors.FloodWaitError as e:
            return {"found": False, "phone": phone, "error": f"Flood wait {e.seconds}s"}
        except Exception as e:
            return {"found": False, "phone": phone, "error": str(e)}
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"found": False, "phone": phone, "error": "Server error"}

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
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
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Use: /check 01712345678")
        return
    
    phone = context.args[0]
    wait_msg = await update.message.reply_text("🔍 Checking...")
    
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

async def bulk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    
    if not is_admin(user_id) or not context.user_data.get('awaiting_file'):
        return
    
    try:
        file = await update.message.document.get_file()
        await file.download_to_drive('numbers.txt')
        
        with open('numbers.txt', 'r') as f:
            numbers = [line.strip() for line in f if line.strip()]
        
        if not numbers:
            await update.message.reply_text("❌ Empty file!")
            return
        
        status_msg = await update.message.reply_text(f"📋 Processing {len(numbers)} numbers...")
        
        results = []
        for i, num in enumerate(numbers, 1):
            result = await check_phone_number(num)
            results.append(result)
            
            if i % 5 == 0:
                await status_msg.edit_text(f"📋 Progress: {i}/{len(numbers)}")
            
            await asyncio.sleep(1)
        
        found_count = sum(1 for r in results if r.get('found'))
        
        report = (
            f"📊 **BULK REPORT**\n\n"
            f"Total: {len(numbers)}\n"
            f"✅ Found: {found_count}\n"
            f"❌ Not Found: {len(numbers) - found_count}\n\n"
            f"**Details:**\n"
        )
        
        for r in results:
            status = "✅" if r.get('found') else "❌"
            name = f" - {r.get('first_name', '')}" if r.get('found') else ""
            report += f"\n{status} {r['phone']}{name}"
        
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            f.write(report.replace('**', ''))
        
        if len(report) <= 4000:
            await update.message.reply_text(report, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"✅ Complete! Found: {found_count}/{len(numbers)}")
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(f, filename=filename)
        
        os.remove('numbers.txt')
        os.remove(filename)
        context.user_data['awaiting_file'] = False
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        context.user_data['awaiting_file'] = False

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    text = update.message.text.strip()
    
    if text.replace('+', '').replace('-', '').replace(' ', '').isdigit():
        wait_msg = await update.message.reply_text("🔍 Checking...")
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

def main():
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("Missing credentials!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("bulk", bulk_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
