#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import json
import time
import uuid
import hashlib
import os
from typing import Optional, Dict, Any

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
USERNAME = os.getenv('USERNAME', '959680090540')
PASSWORD = os.getenv('PASSWORD', 'Bbynnds8825')
BET_AMOUNT = int(os.getenv('BET_AMOUNT', 10))
GAME_TYPE_ID = int(os.getenv('GAME_TYPE_ID', 30))
SELECT_TYPE = int(os.getenv('SELECT_TYPE', 13))
INTERVAL_SECONDS = int(os.getenv('INTERVAL_SECONDS', 15))
API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.bigwinqaz.com/api/webapi')
LANGUAGE = int(os.getenv('LANGUAGE', 7))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# SIGNATURE GENERATOR
# ============================================================

class SignatureGenerator:
    def __init__(self, language: int = 7):
        self.language = language
    
    def generate_random(self) -> str:
        return uuid.uuid4().hex
    
    def generate_signature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        clean_data = {k: v for k, v in data.items() 
                     if k not in ['signature', 'timestamp']}
        clean_data['language'] = self.language
        clean_data['random'] = self.generate_random()
        
        sorted_data = {}
        for key in sorted(clean_data.keys()):
            value = clean_data[key]
            if value is not None and value != '':
                sorted_data[key] = value
        
        json_string = json.dumps(sorted_data, separators=(',', ':'))
        signature = hashlib.md5(json_string.encode()).hexdigest().upper()
        timestamp = int(time.time())
        
        return {
            **clean_data,
            'signature': signature,
            'timestamp': timestamp
        }

# ============================================================
# API CLIENT
# ============================================================

class APIClient:
    BASE_URL = API_BASE_URL
    
    def __init__(self, token: str = "", language: int = 7):
        self.token = token
        self.language = language
        self.sig_gen = SignatureGenerator(language)
        self.session = requests.Session()
        self._last_request_time = 0
        self._min_request_interval = 2.0
        self._setup_headers()
    
    def _setup_headers(self):
        self.session.headers.update({
            'authority': 'api.bigwinqaz.com',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'ar-origin': 'https://www.777bigwingame.app',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://www.777bigwingame.app',
            'pragma': 'no-cache',
            'referer': 'https://www.777bigwingame.app/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        })
    
    def set_token(self, token: str):
        self.token = token
        self.session.headers['authorization'] = f'Bearer {token}'
    
    def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _post(self, endpoint: str, data: Dict[str, Any], retry: int = 3) -> Dict[str, Any]:
        self._rate_limit()
        
        for attempt in range(retry):
            try:
                signed_data = self.sig_gen.generate_signature(data)
                response = self.session.post(
                    f"{self.BASE_URL}/{endpoint}",
                    json=signed_data,
                    timeout=30
                )
                result = response.json()
                
                if result.get('code') == 13:
                    logger.warning(f"Rate limited, waiting 5 seconds...")
                    time.sleep(5)
                    continue
                
                return result
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout, retry {attempt+1}/{retry}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt == retry - 1:
                    raise
        
        return {'code': -1, 'msg': 'Max retries exceeded'}
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        data = {
            'username': username,
            'pwd': password,
            'phonetype': 1,
            'logintype': 'mobile',
            'packId': '',
            'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
            'pixelId': '',
            'fbcId': '',
            'fbc': '',
            'fbp': '',
            'adId': '',
        }
        return self._post('Login', data)
    
    def get_game_issue(self, type_id: int) -> Optional[str]:
        try:
            result = self._post('GetGameIssue', {'typeId': type_id})
            
            if result.get('code') != 0:
                return None
            
            data = result.get('data')
            
            if isinstance(data, dict):
                for key in ['issueNo', 'issuenumber', 'issueNumber']:
                    if key in data and data[key]:
                        return str(data[key])
            
            elif isinstance(data, str):
                return data
            
            elif isinstance(data, list) and len(data) > 0:
                return str(data[0])
            
            return None
            
        except Exception as e:
            logger.error(f"GetGameIssue error: {e}")
            return None
    
    def place_bet(self, type_id: int, issue: str, select_type: int, 
                  amount: int, bet_count: int = 1, game_type: int = 2) -> Dict:
        return self._post('GameBetting', {
            'typeId': type_id,
            'issuenumber': issue,
            'amount': amount,
            'betCount': bet_count,
            'gameType': game_type,
            'selectType': select_type,
        })
    
    def get_balance(self) -> float:
        try:
            result = self._post('GetBalance', {})
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return float(data.get('amount', 0))
            return 0.0
        except:
            return 0.0

# ============================================================
# TELEGRAM BOT
# ============================================================

class AutoBetBot:
    def __init__(self, username: str = None, password: str = None):
        self.username = username or USERNAME
        self.password = password or PASSWORD
        self.api = APIClient()
        self.is_running = False
        self.bet_task = None
        
        self.bet_config = {
            'type_id': GAME_TYPE_ID,
            'select_type': SELECT_TYPE,
            'amount': BET_AMOUNT,
            'bet_count': 1,
            'game_type': 2
        }
        
        self.current_issue = None
        self.stats = {
            'total_bets': 0,
            'wins': 0,
            'losses': 0,
            'profit': 0
        }
        self.consecutive_failures = 0
    
    async def login(self) -> bool:
        try:
            result = self.api.login(self.username, self.password)
            if result.get('code') == 0:
                token = result['data']['token']
                self.api.set_token(token)
                logger.info("✅ Login successful!")
                return True
            else:
                logger.error(f"❌ Login failed: {result.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    async def get_current_issue(self) -> Optional[str]:
        type_id = self.bet_config['type_id']
        
        for attempt in range(5):
            try:
                issue = self.api.get_game_issue(type_id)
                if issue:
                    logger.info(f"✅ Got issue: {issue}")
                    return issue
                
                logger.warning(f"⚠️ Attempt {attempt+1}/5 failed, waiting...")
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Get issue attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2)
        
        return None
    
    async def place_bet(self) -> bool:
        type_id = self.bet_config['type_id']
        
        issue = await self.get_current_issue()
        if not issue:
            logger.warning("❌ No issue number available after retries")
            return False
        
        if issue == self.current_issue:
            logger.info(f"⏳ Already bet on issue {issue}, waiting for next...")
            return False
        
        try:
            result = self.api.place_bet(
                type_id=type_id,
                issue=issue,
                select_type=self.bet_config['select_type'],
                amount=self.bet_config['amount'],
                bet_count=self.bet_config['bet_count'],
                game_type=self.bet_config['game_type']
            )
            
            if result.get('code') == 0:
                self.current_issue = issue
                self.stats['total_bets'] += 1
                self.consecutive_failures = 0
                logger.info(f"✅ Bet placed on issue {issue}")
                return True
            else:
                msg = result.get('msg', 'Unknown error')
                logger.warning(f"❌ Bet failed: {msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Place bet error: {e}")
            return False
    
    async def run_auto_bet(self):
        if not await self.login():
            logger.error("❌ Login failed, cannot start auto bet")
            return
        
        self.is_running = True
        interval = INTERVAL_SECONDS
        logger.info(f"🔄 Auto betting started - Interval: {interval}s")
        logger.info(f"💰 Bet Amount: {self.bet_config['amount']} USDT")
        
        while self.is_running:
            try:
                success = await self.place_bet()
                
                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                
                wait_time = interval
                if self.consecutive_failures > 5:
                    wait_time = 30
                    logger.warning(f"⚠️ {self.consecutive_failures} consecutive failures, waiting {wait_time}s")
                elif self.consecutive_failures > 3:
                    wait_time = 20
                
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Auto bet loop error: {e}")
                await asyncio.sleep(10)
    
    async def stop_auto_bet(self):
        self.is_running = False
        if self.bet_task:
            self.bet_task.cancel()
        logger.info("⏹ Auto betting stopped")
    
    def get_stats(self) -> str:
        total = self.stats['total_bets']
        wins = self.stats['wins']
        win_rate = (wins / max(total, 1)) * 100
        
        return (
            f"📊 *Betting Statistics*\n"
            f"─────────────────\n"
            f"🎯 Total Bets: {total}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {self.stats['losses']}\n"
            f"💰 Profit: {self.stats['profit']} USDT\n"
            f"📈 Win Rate: {win_rate:.1f}%"
        )
    
    def get_balance_text(self) -> str:
        balance = self.api.get_balance()
        return f"💰 *Balance*: {balance} USDT"

# ============================================================
# TELEGRAM HANDLERS
# ============================================================

bot = AutoBetBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start Auto Bet", callback_data="start_bot"),
            InlineKeyboardButton("⏹ Stop Auto Bet", callback_data="stop_bot"),
        ],
        [
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Login", callback_data="refresh"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "🟢 Running" if bot.is_running else "🔴 Stopped"
    
    await update.message.reply_text(
        f"🤖 *Auto Bet Bot*\n\n"
        f"Welcome! Use the buttons below to control the bot.\n\n"
        f"Current config:\n"
        f"• Game Type: {GAME_TYPE_ID}\n"
        f"• Amount: {BET_AMOUNT} USDT\n"
        f"• Status: {status}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_bot":
        if bot.is_running:
            await query.edit_message_text("ℹ️ Bot is already running!", parse_mode='Markdown')
            return
        
        bot.bet_task = asyncio.create_task(bot.run_auto_bet())
        await query.edit_message_text("🟢 *Auto bet started!*", parse_mode='Markdown')
    
    elif query.data == "stop_bot":
        if not bot.is_running:
            await query.edit_message_text("ℹ️ Bot is already stopped!", parse_mode='Markdown')
            return
        
        await bot.stop_auto_bet()
        await query.edit_message_text("🔴 *Auto bet stopped!*", parse_mode='Markdown')
    
    elif query.data == "balance":
        balance_text = bot.get_balance_text()
        await query.edit_message_text(balance_text, parse_mode='Markdown')
    
    elif query.data == "stats":
        await query.edit_message_text(bot.get_stats(), parse_mode='Markdown')
    
    elif query.data == "refresh":
        await query.edit_message_text("🔄 *Refreshing login...*", parse_mode='Markdown')
        if await bot.login():
            await query.edit_message_text("✅ *Login refreshed successfully!*", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ *Login refresh failed!*", parse_mode='Markdown')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "/stop":
        await bot.stop_auto_bet()
        await update.message.reply_text("🔴 Bot stopped!")
    
    elif text == "/status":
        status = "🟢 Running" if bot.is_running else "🔴 Stopped"
        await update.message.reply_text(f"🤖 Status: {status}")
    
    elif text.startswith("/bet"):
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[1])
                bot.bet_config['amount'] = amount
                await update.message.reply_text(f"✅ Bet amount set to {amount} USDT")
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number")
    
    elif text == "/balance":
        await update.message.reply_text(bot.get_balance_text(), parse_mode='Markdown')

# ============================================================
# MAIN - FIXED FOR RENDER
# ============================================================

async def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN is not set!")
        print("Please add TELEGRAM_BOT_TOKEN to your .env file")
        return
    
    try:
        print("=" * 50)
        print("🤖 Auto Bet Bot Starting...")
        print("=" * 50)
        
        # Create application
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print(f"🎮 Game Type: {GAME_TYPE_ID}")
        print(f"💰 Bet Amount: {BET_AMOUNT} USDT")
        print("=" * 50)
        
        # Start polling (this will run forever)
        print("🔄 Starting bot polling...")
        await app.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
