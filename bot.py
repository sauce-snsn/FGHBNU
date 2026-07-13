#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import logging
import random
import time
import re
import html
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)

from api_client import APIClient
from config import Config
from database import init_db, get_user, save_user_login, get_user_subscription, update_user_ai_mode, update_user_balance
import ai_engines
from ai_engines import AI_MODES, AI_MODE_EMOJIS

# ==========================================================
# LOAD ENVIRONMENT & SETUP LOGGING
# ==========================================================
load_dotenv()

LOG_LEVEL_NAME = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURATION
# ==========================================================
BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
OWNER_ID = Config.OWNER_ID

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_sessions = {}

# ==========================================================
# TEXT CONSTANTS
# ==========================================================
TEXT_INFO = "Info"
TEXT_BALANCE = "Balance"
TEXT_STATUS = "Status"
TEXT_START = "Start Auto-Bet"
TEXT_STOP = "Stop Auto-Bet"
TEXT_GAMES = "Games"
TEXT_AI = "AI Mode"
TEXT_BETSIZE = "Set Bet-Size"
TEXT_PROFIT = "Profit Target"
TEXT_HIT = "Hit Betting"
TEXT_PREDICT = "AI Prediction"
TEXT_LOGOUT = "Logout"
TEXT_LOGIN = "Login"
TEXT_BACK = "Back"

# ==========================================================
# PREMIUM EMOJI IDs
# ==========================================================
PREMIUM_EMOJIS = {
    "info": "5868656545634689320",
    "balance": "5868108575387671725",
    "status": "5877443460725739250",
    "games": "5868665489092263539",
    "ai": "5877652234091891383",
    "betsize": "5877260593903177342",
    "profit": "5967574255670399788",
    "hit": "5869547610204280761",
    "predict": "5890997763331591703",
    "login": "5884041323843955199",
    "back": "5848119413041431362",
    "start": "5884248697980608904",
    "stop": "5884289942371401145",
    "logout": "5875180111744995604",
}

# ==========================================================
# KEYBOARD BUTTONS WITH PREMIUM EMOJIS & COLOR STYLES
# ==========================================================
E_INFO = KeyboardButton(
    text=TEXT_INFO,
    icon_custom_emoji_id=PREMIUM_EMOJIS["info"],
    style="primary"
)
E_BALANCE = KeyboardButton(
    text=TEXT_BALANCE,
    icon_custom_emoji_id=PREMIUM_EMOJIS["balance"],
    style="primary"
)
E_STATUS = KeyboardButton(
    text=TEXT_STATUS,
    icon_custom_emoji_id=PREMIUM_EMOJIS["status"],
    style="primary"
)
E_START = KeyboardButton(
    text=TEXT_START,
    icon_custom_emoji_id=PREMIUM_EMOJIS["start"],
    style="success"
)
E_STOP = KeyboardButton(
    text=TEXT_STOP,
    icon_custom_emoji_id=PREMIUM_EMOJIS["stop"],
    style="danger"
)
E_GAMES = KeyboardButton(
    text=TEXT_GAMES,
    icon_custom_emoji_id=PREMIUM_EMOJIS["games"],
    style="primary"
)
E_AI = KeyboardButton(
    text=TEXT_AI,
    icon_custom_emoji_id=PREMIUM_EMOJIS["ai"],
    style="primary"
)
E_BETSIZE = KeyboardButton(
    text=TEXT_BETSIZE,
    icon_custom_emoji_id=PREMIUM_EMOJIS["betsize"],
    style="primary"
)
E_PROFIT = KeyboardButton(
    text=TEXT_PROFIT,
    icon_custom_emoji_id=PREMIUM_EMOJIS["profit"],
    style="primary"
)
E_HIT = KeyboardButton(
    text=TEXT_HIT,
    icon_custom_emoji_id=PREMIUM_EMOJIS["hit"],
    style="primary"
)
E_PREDICT = KeyboardButton(
    text=TEXT_PREDICT,
    icon_custom_emoji_id=PREMIUM_EMOJIS["predict"],
    style="primary"
)
E_LOGOUT = KeyboardButton(
    text=TEXT_LOGOUT,
    icon_custom_emoji_id=PREMIUM_EMOJIS["logout"],
    style="danger"
)
E_LOGIN = KeyboardButton(
    text=TEXT_LOGIN,
    icon_custom_emoji_id=PREMIUM_EMOJIS["login"],
    style="primary"
)
E_BACK = KeyboardButton(
    text=TEXT_BACK,
    icon_custom_emoji_id=PREMIUM_EMOJIS["back"],
    style="primary"
)

# ==========================================================
# PREMIUM EMOJIS FOR MESSAGES
# ==========================================================
P_1 = '<tg-emoji emoji-id="5890997763331591703">🔮</tg-emoji>'
P_2 = '<tg-emoji emoji-id="5875180111744995604">🚪</tg-emoji>'
P_3 = '<tg-emoji emoji-id="5877443460725739250">📊</tg-emoji>'
P_4 = '<tg-emoji emoji-id="5967574255670399788">🎯</tg-emoji>'
P_5 = '<tg-emoji emoji-id="5807868868886009920">⭐</tg-emoji>'
P_6 = '<tg-emoji emoji-id="5807461353799030682">🌟</tg-emoji>'

# ==========================================================
# KEYBOARD FUNCTIONS
# ==========================================================

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [E_LOGIN]
        ],
        resize_keyboard=True
    )

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="777BIGWIN",
                    icon_custom_emoji_id=PREMIUM_EMOJIS["login"],
                    style="success"
                ),
                KeyboardButton(
                    text="6LOTTERY",
                    icon_custom_emoji_id=PREMIUM_EMOJIS["login"],
                    style="danger"
                )
            ],
            [E_BACK]
        ],
        resize_keyboard=True
    )

def get_logged_in_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [E_INFO, E_BALANCE, E_STATUS],
            [E_START, E_STOP],
            [E_GAMES, E_AI],
            [E_BETSIZE, E_PROFIT],
            [E_HIT, E_PREDICT],
            [E_LOGOUT]
        ],
        resize_keyboard=True
    )

def get_ai_mode_keyboard():
    """AI Mode keyboard with premium emojis and color styles"""
    keyboard = []
    row = []
    
    for key, mode in ai_engines.AI_MODES.items():
        mode_name = mode["name"]
        emoji_id = ai_engines.AI_MODE_EMOJIS.get(mode_name, PREMIUM_EMOJIS["ai"])
        
        btn = KeyboardButton(
            text=mode_name,
            icon_custom_emoji_id=emoji_id,
            style="primary"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([E_BACK])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Cancel")]],
        resize_keyboard=True
    )

def get_hit_betting_inline_keyboard(current_wait: int = 0):
    keyboard = []
    number_buttons = []
    for i in range(1, 10):
        btn_style = "success" if current_wait == i else "primary"
        number_buttons.append(
            InlineKeyboardButton(
                text=str(i),
                callback_data=f"hitbet_{i}",
                style=btn_style
            )
        )
    for i in range(0, 9, 3):
        keyboard.append(number_buttons[i:i+3])
    disable_text = "0 (Disabled)" if current_wait == 0 else "0 (Disable)"
    keyboard.append([
        InlineKeyboardButton(
            text=disable_text,
            callback_data="hitbet_0",
            style="danger"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_ai_prediction_toggle_keyboard(is_enabled: bool):
    if is_enabled:
        btn = InlineKeyboardButton(
            text="✅ Enabled",
            callback_data="toggle_aipred",
            style="success"
        )
    else:
        btn = InlineKeyboardButton(
            text="❌ Disabled",
            callback_data="toggle_aipred",
            style="danger"
        )
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])

# ==========================================================
# 🛠️ HELPER FUNCTIONS
# ==========================================================

def extract_balance(bal_str: str) -> float:
    try:
        clean_str = re.sub(r'[^\d.]', '', bal_str)
        if clean_str:
            return float(clean_str)
        return 0.0
    except Exception:
        return 0.0

async def delete_message_later(msg: types.Message, delay: int = 5):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

def parse_duration(duration_str: str):
    duration_str = duration_str.upper()
    if duration_str.endswith('H') and duration_str[:-1].isdigit():
        return timedelta(hours=int(duration_str[:-1]))
    elif duration_str.endswith('D') and duration_str[:-1].isdigit():
        return timedelta(days=int(duration_str[:-1]))
    return None

def get_myanmar_time() -> datetime:
    return datetime.utcnow() + timedelta(hours=6, minutes=30)

# ==========================================================
# 🛡️ AUTH MIDDLEWARE
# ==========================================================

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = None
        text = ""

        if isinstance(event, types.Message):
            user_id = event.from_user.id
            text = event.text or ""
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            if user_id == OWNER_ID:
                return await handler(event, data)

            if isinstance(event, types.Message) and len(text) == 16 and text[:8].isdigit() and text[8:].isupper():
                return await handler(event, data)

            expire_iso = await get_user_subscription(user_id)
            is_authorized = False

            if expire_iso:
                expire_time = datetime.fromisoformat(expire_iso)
                if get_myanmar_time() < expire_time:
                    is_authorized = True

            if not is_authorized:
                if isinstance(event, types.Message):
                    await event.answer(
                        "❌ သင့်အကောင့်သက်တမ်းကုန်ဆုံးသွားပါပြီ။\n"
                        "🔑 Key တစ်ခုထည့်သွင်းရန် သို့မဟုတ် @iwillgoforwardsalone ကိုဆက်သွယ်ပါ။"
                    )
                elif isinstance(event, types.CallbackQuery):
                    await event.answer("❌ သင့်အကောင့်သက်တမ်းကုန်ဆုံးသွားပါပြီ။", show_alert=True)
                return

        return await handler(event, data)

dp.message.middleware(AuthMiddleware())
dp.callback_query.middleware(AuthMiddleware())

# ==========================================================
# 🗂️ FSM STATES
# ==========================================================

class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    enter_bet_sequence = State()
    enter_profit_target = State()

# ==========================================================
# 🔑 OWNER COMMANDS
# ==========================================================

@dp.message(F.text.startswith(".key "))
async def cmd_generate_key(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    from database import create_key

    parts = message.text.split(" ")
    if len(parts) < 2:
        return await message.answer("⚠️ Format မှားနေပါသည်။\nဥပမာ: <code>.key 2H</code>, <code>.key 5D</code>")

    duration = parts[1].strip().upper()
    if not parse_duration(duration):
        return await message.answer("⚠️ မှားယွင်းနေပါသည်။\nဥပမာ: <code>2H</code>, <code>5D</code>, <code>15D</code>")

    date_prefix = get_myanmar_time().strftime("%Y%m%d")
    random_str = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
    key_str = f"{date_prefix}{random_str}"

    await create_key(key_str, duration)

    await message.answer(
        f"✅ <b>Key အောင်မြင်စွာဖန်တီးပြီးပါပြီ</b>\n\n"
        f"🔑 Key: <code>{key_str}</code>\n"
        f"⏱️ Duration: <b>{duration}</b>\n\n"
        f"(User များ ဤ Key ကို Copy ကူးပြီး ထည့်သွင်းနိုင်ပါသည်)"
    )

@dp.message(F.text.startswith(".add "))
async def cmd_add_user(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    from database import update_user_subscription

    parts = message.text.split(" ")
    if len(parts) < 3:
        return await message.answer("⚠️ Format မှားနေပါသည်။\nဥပမာ: <code>.add 123456789 2D</code>")

    target_id = parts[1].strip()
    duration = parts[2].strip().upper()

    td = parse_duration(duration)
    if not td:
        return await message.answer("⚠️ Duration မှားနေပါသည်။ (ဥပမာ: 2H, 5D)")

    new_expire = get_myanmar_time() + td
    await update_user_subscription(int(target_id), new_expire.isoformat())

    await message.answer(
        f"✅ User ID: <code>{target_id}</code> ကို <b>{duration}</b> စာ အသုံးပြုခွင့် ပေးလိုက်ပါပြီ\n"
        f"ကုန်ဆုံးမည့်အချိန်: {new_expire.strftime('%Y-%m-%d %I:%M %p')} (MMT)"
    )

# ==========================================================
# 🔑 USER KEY REDEMPTION HANDLER
# ==========================================================

@dp.message(lambda msg: msg.text and len(msg.text) == 16 and msg.text[:8].isdigit() and msg.text[8:].isupper())
async def process_key_redemption(message: types.Message):
    from database import get_key, delete_key, update_user_subscription, get_user_subscription

    key_str = message.text.strip()
    key_data = await get_key(key_str)

    if key_data:
        duration = key_data["duration"]
        td = parse_duration(duration)
        if not td:
            td = timedelta(days=1)

        user_id = message.from_user.id
        current_expire = get_myanmar_time()

        existing_expire_iso = await get_user_subscription(user_id)
        if existing_expire_iso:
            old_expire = datetime.fromisoformat(existing_expire_iso)
            if old_expire > get_myanmar_time():
                current_expire = old_expire

        new_expire = current_expire + td
        await update_user_subscription(user_id, new_expire.isoformat())

        await delete_key(key_str)

        await message.answer(
            f"✅ Key အောင်မြင်စွာ အသုံးပြုပြီးပါပြီ\n"
            f"⏱️ သက်တမ်း <b>{new_expire.strftime('%Y-%m-%d %I:%M %p')}</b> (MMT) အထိ ရရှိပါပြီ\n"
            f"🔄 /start ကို ပြန်နှိပ်ပါ။"
        )
    else:
        await message.answer("❌ ဤ Key မှားယွင်းနေပါသည် သို့မဟုတ် သက်တမ်းကုန်ဆုံးသွားပါပြီ။")

# ==========================================================
# 🤖 STANDARD BOT HANDLERS
# ==========================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"{P_5} <b>Welcome to Auto Bet Bot!</b>\n\n"
        f"Site ရွေးရန် <b>Login</b> ကိုနှိပ်ပါ။",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == TEXT_LOGIN)
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.select_site)
    await message.answer(
        f"{P_1} သင်ဝင်ရောက်လိုသော Site ကို ရွေးချယ်ပါ",
        reply_markup=get_site_keyboard()
    )

@dp.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "🔙 Back":
        await state.clear()
        return await message.answer("❌ ပယ်ဖျက်လိုက်ပါပြီ", reply_markup=get_main_keyboard())
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer(
        f"{P_1} သင့်ဖုန်းနံပါတ်ကို ရိုက်ထည့်ပါ",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer(
        f"{P_1} သင့်စကားဝှက်ကို ရိုက်ထည့်ပါ",
        reply_markup=ReplyKeyboardRemove()
    )

# ==========================================================
# 🔥 API LOGIN LOGIC - SITE AUTO DETECT
# ==========================================================

@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    site_name = data.get('site', '777BIGWIN')
    user_tg_id = message.from_user.id

    api_client = APIClient(site=site_name)

    try:
        loading_msg = await message.answer(f"{P_1} အကောင့်ဝင်ရန် ကြိုးစားနေပါသည်...")

        result = api_client.login(username, password)

        if result.get('code') != 0:
            await loading_msg.delete()
            await message.answer(
                f"❌ အကောင့်ဝင်ရန် မအောင်မြင်ပါ:\n{result.get('msg', 'Unknown error')}",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        token = result['data']['token']
        api_client.set_token(token)

        user_info = api_client.get_user_info()
        user_data = user_info.get('data', {})
        user_id = user_data.get('userId', 'N/A')
        nickname = user_data.get('nickName', 'Unknown')
        balance = str(user_data.get('amount', 0))

        balance_value = api_client.get_balance()
        site_login_time = get_myanmar_time().strftime("%Y-%m-%d %H:%M:%S")

        db_user = await get_user(user_tg_id)
        ai_mode = db_user.get("ai_mode", "Pattern AI") if db_user else "Pattern AI"

        await save_user_login(
            user_tg_id, username, user_id,
            nickname, balance, site_login_time, ai_mode
        )

        min_bet = 100 if site_name == '6LOTTERY' else 10
        default_sequence = [100, 200, 400, 800] if site_name == '6LOTTERY' else [10, 20, 40, 80]

        await state.update_data(
            is_logged_in=True,
            username=username,
            user_id=user_id,
            nickname=nickname,
            balance=balance,
            login_time=site_login_time,
            token=token
        )

        active_sessions[user_tg_id] = {
            "site": site_name,
            "api_client": api_client,
            "is_auto_betting": False,
            "ai_mode": ai_mode,
            "bet_sequence": default_sequence,
            "current_bet_step": 0,
            "profit_target": 0,
            "start_balance": float(balance) if balance else 0.0,
            "session_profit": 0.0,
            "hit_wait": 0,
            "current_misses": 0,
            "is_ai_prediction_enabled": False,
            "last_predicted_issue": None,
            "current_win_streak": 0,
            "current_lose_streak": 0,
            "longest_win_streak": 0,
            "longest_lose_streak": 0,
            "last_betted_issue": None,
            "token": token,
            "min_bet": min_bet,
            "last_checked_issue": None  # ← FIX: ဒါကို ထည့်ပါ
        }

        await loading_msg.delete()

        caption_text = (
            f"{P_5} <b>LOGIN SUCCESSFUL!</b>\n"
            "─────────────────\n\n"
            f"🌐 <b>Site:</b> <code>{site_name}</code>\n"
            f"💰 <b>Min Bet:</b> <code>{min_bet} Kyats</code>\n\n"
            "👤 <b>User Information:</b>\n"
            f"├─ 🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"├─ 📱 <b>Username:</b> <code>{username}</code>\n"
            f"├─ 🏷️ <b>Nickname:</b> {nickname}\n"
            f"├─ 💰 <b>Balance:</b> <code>{balance}</code>\n"
            f"└─ 📅 <b>Login Date:</b> {site_login_time}\n"
            "─────────────────\n"
            "<b>🤖 AUTO BET BOT | SYSTEM VERIFIED</b>"
        )

        await message.answer(caption_text, reply_markup=get_logged_in_keyboard())
        await state.set_state(LoginForm.main_menu)

    except Exception as e:
        await message.answer(
            f"⚠️ <b>Error:</b> {html.escape(str(e))}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        if 'api_client' in locals():
            await api_client.close()

# ==========================================================
# 🤖 HANDLERS (AI, Hit, Profit, etc.)
# ==========================================================

@dp.message(F.text == TEXT_AI)
async def cmd_ai_mode(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    await message.answer("🧠 <b>AI Mode</b>", reply_markup=get_ai_mode_keyboard())

@dp.message(F.text.in_([m["name"] for m in ai_engines.AI_MODES.values()]))
async def set_ai_mode(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    
    mode_name = message.text
    active_sessions[user_tg_id]["ai_mode"] = mode_name
    await update_user_ai_mode(user_tg_id, mode_name)
    await message.answer(f"✅ AI Mode ကို <b>{mode_name}</b> သို့ပြောင်းလဲလိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_HIT)
async def btn_hit_betting(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    current_wait = active_sessions[user_tg_id].get("hit_wait", 0)
    await message.answer(
        f"{P_1} <b>Hit Betting System</b>",
        reply_markup=get_hit_betting_inline_keyboard(current_wait)
    )

@dp.callback_query(F.data.startswith("hitbet_"))
async def process_hit_bet(callback: types.CallbackQuery):
    user_tg_id = callback.from_user.id
    wait_count = int(callback.data.split("_")[1])
    if user_tg_id in active_sessions:
        active_sessions[user_tg_id]["hit_wait"] = wait_count
        active_sessions[user_tg_id]["current_misses"] = 0
    await callback.message.edit_reply_markup(reply_markup=get_hit_betting_inline_keyboard(wait_count))
    await callback.answer(f"✅ Set to {wait_count}" if wait_count > 0 else "❌ Disabled")

@dp.message(F.text == TEXT_PROFIT)
async def btn_set_profit_target(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    current_target = active_sessions[user_tg_id].get("profit_target", 0)
    await state.set_state(LoginForm.enter_profit_target)
    await message.answer(
        f"{P_4} <b>Auto Bet ရည်မှန်ချက် (Profit Target)</b>\n"
        f"လက်ရှိ Target: <b>{current_target} Ks</b>",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(LoginForm.enter_profit_target)
async def process_profit_target(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    text = message.text.strip()
    if text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ ဖျက်သိမ်းလိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())
    if not text.isdigit():
        return await message.answer("❌ ဂဏန်းသာ ရိုက်ထည့်ပါ")
    target_amount = int(text)
    active_sessions[user_tg_id]["profit_target"] = target_amount
    await state.set_state(LoginForm.main_menu)
    await message.answer(f"✅ <b>Profit Target:</b> {target_amount} Ks", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_BETSIZE)
async def btn_set_betsize(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    site = active_sessions[user_tg_id].get("site", "777BIGWIN")
    min_bet = 100 if site == '6LOTTERY' else 10
    await state.set_state(LoginForm.enter_bet_sequence)
    await message.answer(
        f"{P_1} <b>Bet Size သတ်မှတ်ပါ</b>\n\n"
        f"🌐 <b>Site:</b> {site}\n"
        f"⚠️ <b>Min Bet:</b> {min_bet} Kyats\n\n"
        f"ဥပမာ: {min_bet}-{min_bet*2}-{min_bet*4}",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(LoginForm.enter_bet_sequence)
async def process_bet_sequence(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    text = message.text.strip()
    if text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ ဖျက်သိမ်းလိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())
    site = active_sessions.get(user_tg_id, {}).get("site", "777BIGWIN")
    min_bet = 100 if site == '6LOTTERY' else 10
    try:
        sequence = [int(x.strip()) for x in text.split('-')]
        if len(sequence) == 0 or any(x <= 0 for x in sequence) or any(x < min_bet for x in sequence):
            raise ValueError
        active_sessions[user_tg_id]["bet_sequence"] = sequence
        active_sessions[user_tg_id]["current_bet_step"] = 0
        seq_str = "-".join(map(str, sequence))
        await state.set_state(LoginForm.main_menu)
        await message.answer(f"✅ <b>Bet Size:</b> <code>{seq_str}</code>", reply_markup=get_logged_in_keyboard())
    except Exception:
        await message.answer(f"❌ မှားယွင်းနေပါသည်။ ဥပမာ: {min_bet}-{min_bet*2}-{min_bet*4}")

# ==========================================================
# 🚀 AUTO BET CORE FUNCTIONS (FULLY FIXED)
# ==========================================================

async def get_ai_prediction_for_bet(user_tg_id: int) -> tuple:
    """Get AI prediction (BIG or SMALL) with confidence"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return "BIG", 50.0, "Default"
    
    api_client = session.get("api_client")
    if not api_client:
        return "BIG", 50.0, "Default"
    
    # Get user's AI mode
    ai_mode_name = session.get("ai_mode", "Pattern AI")
    
    # Find mode key
    mode_key = "pattern"
    for key, val in ai_engines.AI_MODES.items():
        if val["name"] == ai_mode_name:
            mode_key = key
            break
    
    try:
        # Get history
        history = api_client.get_noaverage_emergd_list(type_id=30, page_size=10)
        
        if not history:
            return "BIG", 50.0, ai_mode_name
        
        # Build history for AI
        history_docs = []
        for item in history:
            num = int(item.get('number', 0))
            if num >= 5:
                size = "BIG"
            else:
                size = "SMALL"
            history_docs.append({"size": size, "number": num})
        
        # Get prediction from AI engine
        predicted_size, display_name, confidence, desc = ai_engines.get_prediction(history_docs, mode_key)
        
        return predicted_size, confidence, ai_mode_name
        
    except Exception as e:
        logger.error(f"AI prediction error: {e}")
        return "BIG", 50.0, ai_mode_name


async def check_bet_result(user_tg_id: int, issue: str, bet_type: str, amount: int) -> tuple:
    """Check bet result - SIMPLE AND CLEAR"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return None
    
    api_client = session.get("api_client")
    if not api_client:
        return None
    
    try:
        # Get history
        win_result = api_client.get_noaverage_emergd_list(type_id=30, page_size=20)
        
        if win_result:
            for item in win_result:
                if str(item.get('issueNumber', '')) == str(issue):
                    # Get the result number
                    num = item.get('number')
                    if num is None:
                        num = item.get('resultNumber')
                    if num is None:
                        num = item.get('winNumber')
                    
                    if num is not None:
                        num = int(num)
                        
                        # 👇 THIS IS THE KEY LOGIC
                        if num >= 5:
                            actual_result = "BIG"
                        else:
                            actual_result = "SMALL"
                        
                        # 👇 COMPARE: Did we bet correctly?
                        if actual_result == bet_type.upper():
                            # WE WON! 🎉
                            result_status = "WIN 🟢"
                            win_amount = amount * 0.96
                            session["wins"] = session.get("wins", 0) + 1
                            session["session_profit"] = session.get("session_profit", 0) + win_amount
                        else:
                            # WE LOSE! 😢
                            result_status = "LOSE 🔴"
                            session["losses"] = session.get("losses", 0) + 1
                            session["session_profit"] = session.get("session_profit", 0) - amount
                        
                        logger.info(f"✅ Bet: {bet_type} | Result: {num} → {actual_result} → {result_status}")
                        return result_status, win_amount, actual_result, num
                    else:
                        logger.warning(f"⚠️ No number found for issue {issue}")
                        return None
        
        return None
        
    except Exception as e:
        logger.error(f"Check result error: {e}")
        return None



async def place_auto_bet(user_tg_id: int, bet_type: str, amount: int) -> tuple:
    """Place bet and return (success, result, win_amount)"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return False, None, 0
    
    api_client = session.get("api_client")
    if not api_client:
        return False, None, 0
    
    try:
        type_id = 30
        issue = api_client.get_game_issue(type_id)
        if not issue:
            logger.warning("No issue number available")
            return False, None, 0
        
        last_issue = session.get("last_betted_issue")
        if issue == last_issue:
            logger.info(f"Already bet on issue {issue}")
            return False, None, 0
        
        # BIG = 13, SMALL = 14
        select_type = 13 if bet_type.upper() == "BIG" else 14
        
        result = api_client.place_bet(
            type_id=type_id,
            issue=issue,
            select_type=select_type,
            amount=amount
        )
        
        if result.get('code') == 0:
            session["last_betted_issue"] = issue
            session["total_bets"] = session.get("total_bets", 0) + 1
            
            logger.info(f"✅ Bet placed on issue {issue} - {bet_type}")
            return True, "PENDING", 0
        else:
            logger.warning(f"❌ Bet failed: {result.get('msg')}")
            return False, None, 0
            
    except Exception as e:
        logger.error(f"Place bet error: {e}")
        return False, None, 0

async def auto_bet_loop(user_tg_id: int, message: types.Message):
    """Main auto-betting loop - FULLY FIXED"""
    await message.answer(f"{P_5} Auto-Betting စတင်ပါပြီ!")
    
    session = active_sessions.get(user_tg_id)
    if not session:
        return
    
    api_client = session.get("api_client")
    if not api_client:
        return
    
    consecutive_failures = 0
    last_betted_issue = None
    
    while active_sessions.get(user_tg_id, {}).get("is_auto_betting", False):
        try:
            # 1. Get AI prediction
            predicted_bet, confidence, ai_mode = await get_ai_prediction_for_bet(user_tg_id)
            
            # 2. Get current issue
            current_issue = api_client.get_game_issue(30)
            if not current_issue:
                logger.warning("No issue available")
                await asyncio.sleep(5)
                continue
            
            # 3. Check if already bet on this issue
            if current_issue == last_betted_issue:
                logger.info(f"Already bet on issue {current_issue}, waiting for next...")
                await asyncio.sleep(3)
                continue
            
            # 4. Get bet amount from sequence
            sequence = session.get("bet_sequence", [10, 20, 40])
            step = session.get("current_bet_step", 0)
            
            if step >= len(sequence):
                step = 0
                session["current_bet_step"] = 0
            
            current_amount = sequence[step]
            
            # 5. Check min bet
            min_bet = session.get("min_bet", 10)
            if current_amount < min_bet:
                current_amount = min_bet
                sequence = [min_bet, min_bet*2, min_bet*4]
                session["bet_sequence"] = sequence
                session["current_bet_step"] = 0
            
            # 6. Check balance
            balance = api_client.get_balance()
            if balance < current_amount:
                await message.answer(
                    f"⚠️ <b>လက်ကျန်ငွေ မလုံလောက်ပါ</b>\n"
                    f"လိုအပ်သောငွေ: {current_amount} Ks\n"
                    f"လက်ကျန်ငွေ: {balance}\n"
                    f"{P_2} Auto Bet ကို ရပ်လိုက်ပါပြီ"
                )
                session["is_auto_betting"] = False
                break
            
            # 7. 📝 Show betting message
            betting_msg = (
                f"<b>WINGO_30S : {current_issue}</b>\n"
                f"<b>Series : Ai Prediction</b>\n"
                f"<b>Pred : {predicted_bet.upper()} | {current_amount} Ks</b>\n"
                f"<b>Step : {step+1}/{len(sequence)}</b>"
            )
            await message.answer(betting_msg)
            
            # 8. Place bet
            success, _, _ = await place_auto_bet(user_tg_id, predicted_bet, current_amount)
            
            if success:
                last_betted_issue = current_issue
                
                # 9. Wait for result (8 seconds)
                await asyncio.sleep(8)
                
                # 10. Check result
                result_data = await check_bet_result(user_tg_id, current_issue, predicted_bet, current_amount)
                
                if result_data:
                    result_status, win_amount, actual_result, actual_number = result_data
                    
                    # Get current balance and profit
                    new_balance = api_client.get_balance()
                    current_profit = session.get("session_profit", 0.0)
                    
                    # Update balance in DB
                    await update_user_balance(user_tg_id, str(new_balance))
                    
                    if result_status == "WIN 🟢":
                        profit_display = f"+{current_profit:.2f} Ks"
                        
                        result_msg = (
                            f"<b>✅ WIN 🏁 +{win_amount:.2f} Ks</b>\n\n"
                            f"<b>WINGO_30S : {current_issue}</b>\n"
                            f"<b>Result : {actual_number} | {actual_result}</b>\n"
                            f"<b>Balance : K{new_balance:,.2f}</b>\n"
                            f"<b>Total Profit : {profit_display}</b>"
                        )
                        
                        # WIN = Reset to first step
                        session["current_bet_step"] = 0
                        logger.info(f"🔄 WIN! Reset to step 1")
                        
                    elif result_status == "LOSE 🔴":
                        profit_display = f"{current_profit:.2f} Ks"
                        
                        # LOSE = Move to next step
                        next_step = step + 1
                        
                        # If next step is out of range, reset to first
                        if next_step >= len(sequence):
                            next_step = 0
                            next_amount = sequence[0]
                        else:
                            next_amount = sequence[next_step]
                        
                        session["current_bet_step"] = next_step
                        
                        result_msg = (
                            f"<b>❌ LOSE 🏁 {current_amount:.2f} Ks</b>\n\n"
                            f"<b>WINGO_30S : {current_issue}</b>\n"
                            f"<b>Result : {actual_number} | {actual_result}</b>\n"
                            f"<b>Balance : K{new_balance:,.2f}</b>\n"
                            f"<b>Total Profit : {profit_display}</b>\n"
                            f"<b>Next Bet : {next_amount} Ks (Step {next_step+1}/{len(sequence)})</b>"
                        )
                        logger.info(f"🔄 LOSE! Next step: {next_step+1}, amount: {next_amount}")
                    
                    else:
                        result_msg = (
                            f"<b>⏳ PENDING</b>\n\n"
                            f"<b>WINGO_30S : {current_issue}</b>\n"
                            f"<b>Status : Waiting for result...</b>"
                        )
                    
                    await message.answer(result_msg)
                    
                    # Check profit target
                    profit_target = session.get("profit_target", 0)
                    if profit_target > 0 and current_profit >= profit_target:
                        await message.answer(
                            f"🎉 <b>Target ပြည့်သွားပါပြီ!</b>\n"
                            f"Profit: {current_profit:.2f} Ks\n"
                            f"Target: {profit_target} Ks"
                        )
                        session["is_auto_betting"] = False
                        break
                    
                    await asyncio.sleep(INTERVAL_SECONDS)
                else:
                    await message.answer(
                        f"<b>⏳ PENDING</b>\n\n"
                        f"<b>WINGO_30S : {current_issue}</b>\n"
                        f"<b>Status : No result yet...</b>"
                    )
                    await asyncio.sleep(5)
                
            else:
                consecutive_failures += 1
                wait_time = INTERVAL_SECONDS
                if consecutive_failures > 5:
                    wait_time = 30
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            logger.error(f"Auto bet loop error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🤖 MAIN HANDLERS (Start, Stop, Status, Balance, Logout)
# ==========================================================

@dp.message(F.text == TEXT_START)
async def btn_start_auto(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    if active_sessions[user_tg_id].get("is_auto_betting", False):
        return await message.answer("⚠️ Auto Bet လုပ်ဆောင်နေပြီးဖြစ်ပါသည်။")
    
    # Reset last_betted_issue when starting
    active_sessions[user_tg_id]["last_betted_issue"] = None
    active_sessions[user_tg_id]["is_auto_betting"] = True
    asyncio.create_task(auto_bet_loop(user_tg_id, message))

@dp.message(F.text == TEXT_STOP)
async def btn_stop_auto(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    active_sessions[user_tg_id]["is_auto_betting"] = False
    await message.answer(f"{P_2} <b>Auto Bet ကို ရပ်လိုက်ပါပြီ</b>")

@dp.message(F.text == TEXT_STATUS)
async def btn_status(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    
    session = active_sessions[user_tg_id]
    site = session.get("site", "777BIGWIN")
    min_bet = session.get("min_bet", 10)
    ai_mode = session.get("ai_mode", "Pattern AI")
    
    total_bets = session.get("total_bets", 0)
    wins = session.get("wins", 0)
    losses = session.get("losses", 0)
    win_rate = (wins / max(total_bets, 1)) * 100
    profit = session.get("session_profit", 0.0)
    
    current_seq = session.get("bet_sequence", [10])
    seq_str = "-".join(map(str, current_seq))
    current_step = session.get("current_bet_step", 0)
    
    status_text = (
        f"{P_3} <b>Bot Status</b>\n"
        "─────────────────\n"
        f"🌐 <b>Site:</b> {site}\n"
        f"💰 <b>Min Bet:</b> {min_bet} Kyats\n"
        f"🧠 <b>AI Mode:</b> {ai_mode}\n"
        f"🔁 <b>Bet Sequence:</b> <code>{seq_str}</code>\n"
        f"📍 <b>Current Step:</b> {current_step + 1}/{len(current_seq)}\n"
        f"{P_5} <b>Auto-Bet:</b> {'Running 🟢' if session.get('is_auto_betting', False) else 'Stopped 🔴'}\n"
        "─────────────────\n"
        f"🎯 <b>Total Bets:</b> {total_bets}\n"
        f"✅ <b>Wins:</b> {wins}\n"
        f"❌ <b>Losses:</b> {losses}\n"
        f"📈 <b>Win Rate:</b> {win_rate:.1f}%\n"
        f"💰 <b>Profit:</b> {profit:.2f} Ks"
    )
    await message.answer(status_text)

@dp.message(F.text == TEXT_BALANCE)
async def check_balance(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    api_client = active_sessions[user_tg_id].get("api_client")
    if api_client:
        balance = api_client.get_balance()
        await message.answer(f"💰 <b>လက်ကျန်ငွေ:</b> {balance:.2f} Ks", reply_markup=get_logged_in_keyboard())
    else:
        await message.answer("❌ Balance စစ်ဆေးရန် မဖြစ်နိုင်ပါ", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_LOGOUT)
async def logout(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id in active_sessions:
        active_sessions[user_tg_id]["is_auto_betting"] = False
        api_client = active_sessions[user_tg_id].get("api_client")
        if api_client:
            try:
                await api_client.close()
            except Exception:
                pass
        del active_sessions[user_tg_id]
    await state.clear()
    await message.answer(f"{P_2} 👋 အကောင့်မှ ထွက်လိုက်ပါပြီ", reply_markup=get_main_keyboard())

@dp.message(F.text == TEXT_INFO)
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    site_name = active_sessions.get(message.from_user.id, {}).get("site", "Unknown")
    expire_iso = await get_user_subscription(message.from_user.id)
    expire_str = datetime.fromisoformat(expire_iso).strftime('%Y-%m-%d %I:%M %p') if expire_iso else "N/A"
    info_text = (
        f"{P_3} <b>User Information</b>\n"
        f"├─ 🌐 <b>Site:</b> {site_name}\n"
        f"├─ 🆔 <b>User ID:</b> {data.get('user_id', 'N/A')}\n"
        f"├─ 📱 <b>Username:</b> {data.get('username', 'N/A')}\n"
        f"├─ 💰 <b>Balance:</b> {data.get('balance', '0')}\n"
        f"└─ 🔑 <b>Expire:</b> {expire_str}\n"
    )
    await message.answer(info_text, reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_PREDICT)
async def btn_ai_prediction_toggle(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
    is_enabled = active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    await message.answer(
        f"{P_1} <b>AI Prediction</b>",
        reply_markup=get_ai_prediction_toggle_keyboard(is_enabled)
    )

@dp.callback_query(F.data == "toggle_aipred")
async def process_toggle_aipred(callback: types.CallbackQuery):
    user_tg_id = callback.from_user.id
    if user_tg_id not in active_sessions:
        return await callback.answer("⚠️ Session Expired.", show_alert=True)
    current_state = active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    new_state = not current_state
    active_sessions[user_tg_id]["is_ai_prediction_enabled"] = new_state
    await callback.message.edit_reply_markup(reply_markup=get_ai_prediction_toggle_keyboard(new_state))
    await callback.answer("✅ Enabled" if new_state else "❌ Disabled")

# ==========================================================
# 🚀 MAIN
# ==========================================================

async def main():
    init_db()
    logger.info("🚀 Auto-Bot API Version စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot ကို ရပ်လိုက်ပါပြီ")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
