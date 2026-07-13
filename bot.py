#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import json
import time
import uuid
import hashlib
import os
import sys
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from dotenv import load_dotenv

# ==========================================================
# CONFIGURATION
# ==========================================================

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

# ==========================================================
# SITE CONFIGURATION
# ==========================================================

SITE_CONFIGS = {
    '777BIGWIN': {
        'base_url': 'https://api.bigwinqaz.com/api/webapi',
        'ar_origin': 'https://www.777bigwingame.app',
        'origin': 'https://www.777bigwingame.app',
        'referer': 'https://www.777bigwingame.app/',
        'authority': 'api.bigwinqaz.com',
        'min_bet': 10,
        'select_type_big': 13,
        'select_type_small': 14,
    },
    '6LOTTERY': {
        'base_url': 'https://6lotteryapi.com/api/webapi',
        'ar_origin': 'https://www.6win566.com',
        'origin': 'https://www.6win566.com',
        'referer': 'https://www.6win566.com/',
        'authority': '6lotteryapi.com',
        'min_bet': 100,
        'select_type_big': 13,
        'select_type_small': 14,
    }
}

# ==========================================================
# SIGNATURE GENERATOR
# ==========================================================

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

# ==========================================================
# API CLIENT
# ==========================================================

class APIClient:
    def __init__(self, site: str = '777BIGWIN', token: str = "", language: int = 7):
        self.site = site
        self.site_config = SITE_CONFIGS.get(site, SITE_CONFIGS['777BIGWIN'])
        self.base_url = self.site_config['base_url']
        self.token = token
        self.language = language
        self.sig_gen = SignatureGenerator(language)
        self.session = requests.Session()
        self._last_request_time = 0
        self._min_request_interval = 2.0
        self._setup_headers()
    
    def _setup_headers(self):
        config = self.site_config
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'pragma': 'no-cache',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        }
        
        headers.update({
            'authority': config.get('authority', 'api.bigwinqaz.com'),
            'ar-origin': config.get('ar_origin', 'https://www.777bigwingame.app'),
            'ar-real-ip': '',
            'origin': config.get('origin', 'https://www.777bigwingame.app'),
            'referer': config.get('referer', 'https://www.777bigwingame.app/'),
        })
        
        self.session.headers.update(headers)
    
    def get_min_bet(self) -> int:
        return self.site_config.get('min_bet', 10)
    
    def get_select_type_big(self) -> int:
        return self.site_config.get('select_type_big', 13)
    
    def get_select_type_small(self) -> int:
        return self.site_config.get('select_type_small', 14)
    
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
                    f"{self.base_url}/{endpoint}",
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
    
    def get_noaverage_emergd_list(self, type_id: int = 30, page_size: int = 10, page_no: int = 1) -> List[Dict]:
        try:
            result = self._post('GetNoaverageEmerdList', {
                'typeId': type_id,
                'pageSize': page_size,
                'pageNo': page_no
            })
            
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return data.get('list', [])
                elif isinstance(data, list):
                    return data
            return []
            
        except Exception as e:
            logger.error(f"GetNoaverageEmerdList error: {e}")
            return []
    
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

# ==========================================================
# AI PREDICTION (Simple Version)
# ==========================================================

def get_ai_prediction(history_docs: List[Dict]) -> str:
    """Simple AI prediction - returns 'BIG' or 'SMALL'"""
    if not history_docs:
        return "BIG"
    
    # Count BIG and SMALL
    big_count = 0
    small_count = 0
    
    for item in history_docs:
        size = item.get('size', '').upper()
        if size == 'BIG':
            big_count += 1
        elif size == 'SMALL':
            small_count += 1
    
    # Predict based on majority
    if big_count > small_count:
        return "BIG"
    elif small_count > big_count:
        return "SMALL"
    else:
        # Default to BIG if equal
        return "BIG"

# ==========================================================
# TELEGRAM BOT
# ==========================================================

class AutoBetBot:
    def __init__(self, username: str = None, password: str = None):
        self.username = username or USERNAME
        self.password = password or PASSWORD
        self.api = None
        self.site = '777BIGWIN'
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
        self.history = []  # For AI prediction
    
    def get_min_bet(self) -> int:
        if self.site == '6LOTTERY':
            return 100
        else:
            return 10
    
    def get_select_type_for_bet(self, bet_type: str) -> int:
        """Get select type based on bet type (BIG or SMALL)"""
        if bet_type.upper() == 'BIG':
            if self.site == '6LOTTERY':
                return 13  # 6LOTTERY BIG = 13
            else:
                return 13  # 777BIGWIN BIG = 13
        else:  # SMALL
            if self.site == '6LOTTERY':
                return 14  # 6LOTTERY SMALL = 14
            else:
                return 14  # 777BIGWIN SMALL = 14
    
    async def login(self, site: str = '777BIGWIN') -> bool:
        self.site = site
        self.api = APIClient(site=site)
        
        try:
            result = self.api.login(self.username, self.password)
            if result.get('code') == 0:
                token = result['data']['token']
                self.api.set_token(token)
                
                # Check and adjust bet amount
                min_bet = self.get_min_bet()
                if self.bet_config['amount'] < min_bet:
                    self.bet_config['amount'] = min_bet
                    logger.info(f"💰 Bet amount auto-adjusted to {min_bet} for {site}")
                
                logger.info(f"✅ Login successful! Site: {site}")
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
                    return issue
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Get issue attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2)
        
        return None
    
    async def get_history(self) -> List[Dict]:
        """Get betting history for AI prediction"""
        try:
            result = self.api.get_noaverage_emergd_list(type_id=30, page_size=10)
            if result:
                return result
            return []
        except Exception as e:
            logger.error(f"Get history error: {e}")
            return []
    
    async def place_bet(self) -> bool:
        type_id = self.bet_config['type_id']
        
        # Get current issue
        issue = await self.get_current_issue()
        if not issue:
            logger.warning("❌ No issue number available")
            return False
        
        if issue == self.current_issue:
            logger.info(f"⏳ Already bet on issue {issue}, waiting for next...")
            return False
        
        # Get AI prediction
        history = await self.get_history()
        prediction = get_ai_prediction(history)
        
        # Get select type based on prediction
        select_type = self.get_select_type_for_bet(prediction)
        
        logger.info(f"🤖 AI Prediction: {prediction} (select_type: {select_type})")
        
        try:
            result = self.api.place_bet(
                type_id=type_id,
                issue=issue,
                select_type=select_type,
                amount=self.bet_config['amount'],
                bet_count=self.bet_config['bet_count'],
                game_type=self.bet_config['game_type']
            )
            
            if result.get('code') == 0:
                self.current_issue = issue
                self.stats['total_bets'] += 1
                self.consecutive_failures = 0
                logger.info(f"✅ Bet placed on issue {issue} - {prediction}")
                return True
            else:
                msg = result.get('msg', 'Unknown error')
                logger.warning(f"❌ Bet failed: {msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Place bet error: {e}")
            return False
    
    async def run_auto_bet(self):
        if self.api is None:
            logger.error("❌ Not logged in")
            return
        
        self.is_running = True
        
        logger.info(f"🔄 Auto betting started - Site: {self.site}, Min Bet: {self.get_min_bet()}")
        logger.info(f"💰 Bet Amount: {self.bet_config['amount']}")
        
        while self.is_running:
            try:
                success = await self.place_bet()
                
                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                
                wait_time = INTERVAL_SECONDS
                if self.consecutive_failures > 5:
                    wait_time = 30
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
            f"🌐 *Site:* {self.site}\n"
            f"💰 *Min Bet:* {self.get_min_bet()} Kyats\n"
            f"🎯 *Total Bets:* {total}\n"
            f"✅ *Wins:* {wins}\n"
            f"❌ *Losses:* {self.stats['losses']}\n"
            f"💰 *Profit:* {self.stats['profit']} USDT\n"
            f"📈 *Win Rate:* {win_rate:.1f}%"
        )
    
    def get_balance_text(self) -> str:
        if self.api is None:
            return "❌ Not logged in"
        balance = self.api.get_balance()
        return f"💰 *Balance:* {balance} USDT\n🌐 *Site:* {self.site}"

# ==========================================================
# SITE SELECTION KEYBOARD
# ==========================================================

def get_site_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🟢 777BIGWIN", callback_data="site_777BIGWIN"),
            InlineKeyboardButton("🔴 6LOTTERY", callback_data="site_6LOTTERY"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard():
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
    return InlineKeyboardMarkup(keyboard)

# ==========================================================
# TELEGRAM HANDLERS
# ==========================================================

bot = AutoBetBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 *Auto Bet Bot*\n\n"
        f"Welcome! Please select your site:",
        reply_markup=get_site_keyboard(),
        parse_mode='Markdown'
    )

async def site_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    site = query.data.replace("site_", "")
    
    await query.edit_message_text(f"🔄 Logging in to {site}...")
    
    success = await bot.login(site)
    
    if success:
        min_bet = bot.get_min_bet()
        
        await query.edit_message_text(
            f"✅ *Login successful!*\n\n"
            f"🌐 *Site:* {site}\n"
            f"💰 *Min Bet:* {min_bet} Kyats\n"
            f"💵 *Bet Amount:* {bot.bet_config['amount']} Kyats\n\n"
            f"Use the buttons below to control the bot.",
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            f"❌ *Login failed!*\n\n"
            f"Please check your credentials.",
            parse_mode='Markdown'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_bot":
        if bot.is_running:
            await query.edit_message_text("ℹ️ Bot is already running!", parse_mode='Markdown')
            return
        
        if bot.api is None:
            await query.edit_message_text("❌ Please login first using /start", parse_mode='Markdown')
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
        await query.edit_message_text(bot.get_balance_text(), parse_mode='Markdown')
    
    elif query.data == "stats":
        await query.edit_message_text(bot.get_stats(), parse_mode='Markdown')
    
    elif query.data == "refresh":
        await query.edit_message_text("🔄 *Refreshing login...*", parse_mode='Markdown')
        if await bot.login(bot.site):
            await query.edit_message_text("✅ *Login refreshed!*", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ *Login refresh failed!*", parse_mode='Markdown')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "/stop":
        await bot.stop_auto_bet()
        await update.message.reply_text("🔴 Bot stopped!")
    
    elif text == "/status":
        status = "🟢 Running" if bot.is_running else "🔴 Stopped"
        await update.message.reply_text(
            f"🤖 *Status:* {status}\n"
            f"🌐 *Site:* {bot.site}\n"
            f"💰 *Min Bet:* {bot.get_min_bet()} Kyats",
            parse_mode='Markdown'
        )
    
    elif text.startswith("/bet"):
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[1])
                min_bet = bot.get_min_bet()
                if amount < min_bet:
                    await update.message.reply_text(
                        f"❌ {bot.site} requires minimum {min_bet} Kyats!",
                        parse_mode='Markdown'
                    )
                    return
                bot.bet_config['amount'] = amount
                await update.message.reply_text(f"✅ Bet amount set to {amount} Kyats")
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid number")
    
    elif text == "/balance":
        await update.message.reply_text(bot.get_balance_text(), parse_mode='Markdown')

# ==========================================================
# MAIN
# ==========================================================

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN is not set!")
        return
    
    try:
        print("=" * 50)
        print("🤖 Auto Bet Bot Starting...")
        print("=" * 50)
        print(f"🎮 Game Type: {GAME_TYPE_ID}")
        print(f"💰 Bet Amount: {BET_AMOUNT} USDT")
        print("=" * 50)
        
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(site_selection_handler, pattern="^site_"))
        app.add_handler(CallbackQueryHandler(button_handler, pattern="^(start_bot|stop_bot|balance|stats|refresh)$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("🔄 Starting bot polling...")
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
