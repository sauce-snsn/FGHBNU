#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import html
import random
import time
import re
import logging
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

from config import Config
from api_client import APIClient
from database import (
    get_user, save_user_login, update_user_ai_mode, 
    update_user_balance, get_user_subscription,
    create_key, get_key, delete_key, update_user_subscription
)
import ai_engines
from ai_engines import AI_MODES, AI_MODE_EMOJIS

# ==========================================================
# ⚙️ Configuration
# ==========================================================
load_dotenv()

logging.basicConfig(
    LOG_LEVEL = getattr(logging, Config.LOG_LEVEL, logging.INFO)  # 👈 FIX

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
OWNER_ID = Config.OWNER_ID

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_sessions = {}

# ==========================================================
# 🌟 Text Constants
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
# 🛠️ Helper Functions
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
# 🛡️ Auth Middleware
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
            # Owner bypass
            if user_id == OWNER_ID:
                return await handler(event, data)
            
            # Key redemption (16 chars: 8 digits + 8 uppercase)
            if isinstance(event, types.Message) and len(text) == 16 and text[:8].isdigit() and text[8:].isupper():
                return await handler(event, data)
            
            # Check subscription
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
# 🎯 VALID AI NAMES
# ==========================================================
VALID_AI_NAMES = [m["name"] for m in AI_MODES.values()]

# ==========================================================
# 🗂️ FSM States
# ==========================================================
class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    enter_bet_sequence = State() 
    enter_profit_target = State()

# ==========================================================
# ⌨️ Keyboards
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=TEXT_LOGIN)]],
        resize_keyboard=True
    )

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="777BIGWIN"), KeyboardButton(text="6LOTTERY")],
            [KeyboardButton(text="🔙 Back")]
        ],
        resize_keyboard=True
    )

def get_logged_in_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXT_INFO), KeyboardButton(text=TEXT_BALANCE), KeyboardButton(text=TEXT_STATUS)], 
            [KeyboardButton(text=TEXT_START), KeyboardButton(text=TEXT_STOP)],
            [KeyboardButton(text=TEXT_GAMES), KeyboardButton(text=TEXT_AI)],
            [KeyboardButton(text=TEXT_BETSIZE), KeyboardButton(text=TEXT_PROFIT)], 
            [KeyboardButton(text=TEXT_HIT), KeyboardButton(text=TEXT_PREDICT)],
            [KeyboardButton(text=TEXT_LOGOUT)]
        ],
        resize_keyboard=True
    )

def get_ai_mode_keyboard():
    modes = list(AI_MODES.values())
    keyboard = []
    row = []
    
    for mode in modes:
        mode_name = mode["name"]
        btn = KeyboardButton(text=mode_name)
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([KeyboardButton(text="🔙 Back")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_hit_betting_inline_keyboard(current_wait: int = 0):
    keyboard = []
    number_buttons = []
    for i in range(1, 10):
        btn_style = "success" if current_wait == i else "primary"
        number_buttons.append(
            InlineKeyboardButton(text=str(i), callback_data=f"hitbet_{i}")
        )
        
    for i in range(0, 9, 3): 
        keyboard.append(number_buttons[i:i+3])
        
    disable_text = "0 (Disabled)" if current_wait == 0 else "0 (Disable)"
    keyboard.append([InlineKeyboardButton(text=disable_text, callback_data="hitbet_0")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_ai_prediction_toggle_keyboard(is_enabled: bool):
    text = "✅ Enabled" if is_enabled else "❌ Disabled"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="toggle_aipred")]])

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Cancel")]], 
        resize_keyboard=True
    )

# ==========================================================
# 🔑 Owner Commands (.key & .add)
# ==========================================================
@dp.message(F.text.startswith(".key "))
async def cmd_generate_key(message: types.Message):
    if message.from_user.id != OWNER_ID: 
        return
    
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
# 🔑 User Key Redemption Handler
# ==========================================================
@dp.message(lambda msg: msg.text and len(msg.text) == 16 and msg.text[:8].isdigit() and msg.text[8:].isupper())
async def process_key_redemption(message: types.Message):
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
        
        # 1 Key One Time
        await delete_key(key_str)
        
        await message.answer(
            f"✅ Key အောင်မြင်စွာ အသုံးပြုပြီးပါပြီ\n"
            f"⏱️ သက်တမ်း <b>{new_expire.strftime('%Y-%m-%d %I:%M %p')}</b> (MMT) အထိ ရရှိပါပြီ\n"
            f"🔄 /start ကို ပြန်နှိပ်ပါ။"
        )
    else:
        await message.answer("❌ ဤ Key မှားယွင်းနေပါသည် သို့မဟုတ် သက်တမ်းကုန်ဆုံးသွားပါပြီ။")

# ==========================================================
# 🤖 Standard Bot Handlers
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 ကြိုဆိုပါသည်!", reply_markup=get_main_keyboard())

@dp.message(F.text == TEXT_LOGIN)
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.select_site)
    await message.answer("🌐 သင်ဝင်ရောက်လိုသော Site ကို ရွေးချယ်ပါ", reply_markup=get_site_keyboard())

@dp.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "🔙 Back":
        await state.clear()
        return await message.answer("Cancelled.", reply_markup=get_main_keyboard())
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer("📱 သင့်ဖုန်းနံပါတ်ကို ရိုက်ထည့်ပါ", reply_markup=ReplyKeyboardRemove())

@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer("🔑 သင့်စကားဝှက်ကို ရိုက်ထည့်ပါ", reply_markup=ReplyKeyboardRemove())

# ==========================================================
# 🔥 API Login Logic (No Playwright!)
# ==========================================================
@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    site_name = data.get('site', '777BIGWIN')
    user_tg_id = message.from_user.id
    
    # Create API client
    api_client = APIClient(site=site_name)
    
    try:
        # Show loading
        loading_msg = await message.answer("⏳ အကောင့်ဝင်ရန် ကြိုးစားနေပါသည်...")
        
        # 1. Login via API
        result = api_client.login(username, password)
        logger.info(f"Login result: {result.get('code')}")
        
        if result.get('code') != 0:
            await loading_msg.delete()
            await message.answer(
                f"❌ အကောင့်ဝင်ရန် မအောင်မြင်ပါ:\n{result.get('msg', 'Unknown error')}",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
        
        # 2. Get token and set it
        token = result['data']['token']
        api_client.set_token(token)
        
        # 3. Get user info
        user_info = api_client.get_user_info()
        logger.info(f"User info result: {user_info.get('code')}")
        
        if user_info.get('code') != 0:
            await loading_msg.delete()
            await message.answer(
                f"❌ အချက်အလက်များ ရယူရန် မအောင်မြင်ပါ",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
        
        # 4. Extract user data
        user_data = user_info.get('data', {})
        user_id = user_data.get('userId', 'N/A')
        nickname = user_data.get('nickName', 'Unknown')
        balance = str(user_data.get('amount', 0))
        
        # 5. Get balance
        balance_value = api_client.get_balance()
        
        site_login_time = get_myanmar_time().strftime("%Y-%m-%d %H:%M:%S")
        
        # 6. Get AI mode from DB
        db_user = await get_user(user_tg_id)
        if db_user:
            ai_mode = db_user.get("ai_mode", "Pattern AI")
        else:
            ai_mode = "Pattern AI"
        
        if ai_mode not in VALID_AI_NAMES: 
            ai_mode = "Pattern AI"
        
        # 7. Save to database
        await save_user_login(
            user_tg_id, username, user_id, 
            nickname, balance, site_login_time, ai_mode
        )
        
        # 8. Store in session
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
            "bet_sequence": [10],
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
            "token": token
        }
        
        await loading_msg.delete()
        
        # 9. Show success message
        caption_text = (
            "🏆 <b>LOGIN SUCCESSFUL!</b>\n"
            "─────────────────\n\n"
            f"🌐 <b>Site:</b> <code>{site_name}</code>\n\n"
            "👤 <b>User Information:</b>\n"
            f"├─ 🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"├─ 📱 <b>Username:</b> <code>{username}</code>\n"
            f"├─ 🏷️ <b>Nickname:</b> {nickname}\n"
            f"├─ 💰 <b>Balance:</b> <code>{balance}</code>\n"
            f"└─ 📅 <b>Login Date:</b> {site_login_time}\n"
            "─────────────────\n"
            "<b>🤖 PSP-AUTO BETTING | SYSTEM VERIFIED</b>"
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
# 🔮 AI Prediction Mode Handlers
# ==========================================================
@dp.message(F.text == TEXT_PREDICT)
async def btn_ai_prediction_toggle(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    is_enabled = active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    
    await message.answer(
        "🔮 <b>AI Prediction Broadcast</b>\n\n"
        "AI မှ ကြိုတင်ခန့်မှန်းချက်များကို နောက်ဆက်တွဲအဖြစ် ဖွင့်ပေးနိုင်ပါသည်။",
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
    
    if new_state:
        await callback.answer("✅ AI Prediction ကို ဖွင့်ပေးလိုက်ပါပြီ", show_alert=True)
        asyncio.create_task(prediction_broadcast_loop(user_tg_id, callback.message))
    else:
        await callback.answer("❌ AI Prediction ကို ပိတ်လိုက်ပါပြီ", show_alert=True)

async def prediction_broadcast_loop(user_tg_id, message: types.Message):
    api_error_count = 0
    
    while active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False):
        try:
            predicted_bet, confidence, current_issue, ai_name = await get_ai_prediction(user_tg_id)
            last_issue = active_sessions[user_tg_id].get("last_predicted_issue")

            if current_issue:
                api_error_count = 0
                if current_issue != last_issue:
                    active_sessions[user_tg_id]["last_predicted_issue"] = current_issue
                    
                    long_w = active_sessions[user_tg_id].get("longest_win_streak", 0)
                    long_l = active_sessions[user_tg_id].get("longest_lose_streak", 0)
                    
                    pred_msg = await message.answer(
                        f"<blockquote>"
                        f"🔮 Ai Prediction - Live\n"
                        f"─────────────────\n"
                        f"🎯 WINGO_30S : <code>{current_issue}</code>\n"
                        f"📊 Prediction : <b>{predicted_bet.upper()}</b>【{long_w}】|【{long_l}】\n"
                        f"⏳ Status : Waiting for result..."
                        f"</blockquote>"
                    )
                    
                    actual_result = "? | ?"
                    for _ in range(20):
                        if not active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False): 
                            break
                        await asyncio.sleep(2)
                        actual_result = await get_latest_game_result(current_issue, user_tg_id)
                        if actual_result != "? | ?": 
                            break
                    
                    if actual_result != "? | ?":
                        actual_size = actual_result.split(" | ")[1].strip().lower()
                        if predicted_bet.lower() == actual_size:
                            status_text = f"✅ WIN {actual_result}"
                            active_sessions[user_tg_id]["current_win_streak"] += 1
                            active_sessions[user_tg_id]["current_lose_streak"] = 0
                            if active_sessions[user_tg_id]["current_win_streak"] > active_sessions[user_tg_id]["longest_win_streak"]:
                                active_sessions[user_tg_id]["longest_win_streak"] = active_sessions[user_tg_id]["current_win_streak"]
                        else:
                            status_text = f"❌ LOSE {actual_result}"
                            active_sessions[user_tg_id]["current_lose_streak"] += 1
                            active_sessions[user_tg_id]["current_win_streak"] = 0
                            if active_sessions[user_tg_id]["current_lose_streak"] > active_sessions[user_tg_id]["longest_lose_streak"]:
                                active_sessions[user_tg_id]["longest_lose_streak"] = active_sessions[user_tg_id]["current_lose_streak"]
                    else:
                        status_text = "⚠️ DRAW (Timeout)"
                        
                    new_long_w = active_sessions[user_tg_id].get("longest_win_streak", 0)
                    new_long_l = active_sessions[user_tg_id].get("longest_lose_streak", 0)
                        
                    try:
                        await pred_msg.edit_text(
                            f"<blockquote>"
                            f"🔮 Ai Prediction - Live\n"
                            f"─────────────────\n"
                            f"🎯 WINGO_30S : <code>{current_issue}</code>\n"
                            f"📊 Prediction : <b>{predicted_bet.upper()}</b>【{new_long_w}】|【{new_long_l}】\n"
                            f"📌 Status : {status_text}"
                            f"</blockquote>"
                        )
                    except Exception: 
                        pass
                    
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(2)
            else:
                api_error_count += 1
                if api_error_count == 3: 
                    await message.answer("⚠️ <b>API မှားယွင်းနေသည်:</b> ကြိုတင်ခန့်မှန်းချက်များ ရယူရန် မဖြစ်နိုင်ပါ")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Prediction loop error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🎯 Feature Handlers (Hit, Profit, AI Mode)
# ==========================================================
@dp.message(F.text == TEXT_HIT)
async def btn_hit_betting(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    current_wait = active_sessions[user_tg_id].get("hit_wait", 0)
    await message.answer(
        "🎯 <b>Hit Betting System</b>\n(ဤနေရာတွင် သတ်မှတ်ထားသော ရေတွက်ပြီးမှ '0' ကို နှိပ်ပါ)", 
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
    
    if wait_count > 0: 
        await callback.answer(f"✅ {wait_count} ကြိမ်တိုင်တိုင်း သတ်မှတ်ပြီး အောင်မြင်စွာ သတ်မှတ်လိုက်ပါပြီ", show_alert=True)
    else: 
        await callback.answer("❌ Hit Betting ကို ပိတ်လိုက်ပါပြီ", show_alert=True)

@dp.message(F.text == TEXT_PROFIT)
async def btn_set_profit_target(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    current_target = active_sessions[user_tg_id].get("profit_target", 0)
    await state.set_state(LoginForm.enter_profit_target)
    await message.answer(
        f"🎯 <b>Auto Bet ရည်မှန်ချက် (Profit Target) ကို သတ်မှတ်ပါ</b>\n"
        f"လက်ရှိ သတ်မှတ်ထားသော Target: <b>{current_target} Ks</b>", 
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
    
    if target_amount > 0: 
        await message.answer(f"✅ <b>Profit Target:</b> {target_amount} Ks ရည်မှန်ချက်ကို သတ်မှတ်လိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())
    else: 
        await message.answer("✅ <b>Profit Target ကို ပိတ်လိုက်ပါပြီ</b>", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_AI)
async def cmd_ai_mode(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    current_mode = active_sessions[user_tg_id].get("ai_mode", "Pattern AI")
    await message.answer(f"🧠 <b>AI Mode:</b> {current_mode}", reply_markup=get_ai_mode_keyboard())

@dp.message(F.text.in_(VALID_AI_NAMES))
async def set_ai_mode(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    active_sessions[user_tg_id]["ai_mode"] = message.text
    await update_user_ai_mode(user_tg_id, message.text)
    await message.answer(f"✅ AI ကို <b>{message.text}</b> အဖြစ် ပြောင်းလဲသတ်မှတ်လိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == "🔙 Back")
async def back_to_main(message: types.Message):
    await message.answer("🔙 ပြန်လာပါပြီ", reply_markup=get_logged_in_keyboard())

# ==========================================================
# 🚀 Auto Bet Core Functions (API Version)
# ==========================================================
async def place_auto_bet_api(user_tg_id: int, bet_type: str, amount: int = 10) -> bool:
    """Place bet using API (no browser)"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return False
    
    api_client = session.get("api_client")
    if not api_client:
        return False
    
    try:
        # 1. Get current issue
        type_id = 30
        issue = api_client.get_game_issue(type_id)
        if not issue:
            logger.warning("No issue number available")
            return False
        
        # 2. Check if already bet on this issue
        last_issue = session.get("last_betted_issue")
        if issue == last_issue:
            logger.info(f"Already bet on issue {issue}, waiting for next...")
            return False
        
        # 3. Convert bet type
        select_type = 13  # Default
        if bet_type.lower() == "big":
            select_type = 1
        elif bet_type.lower() == "small":
            select_type = 2
        elif bet_type.lower() == "red":
            select_type = 3
        elif bet_type.lower() == "green":
            select_type = 4
        elif bet_type.lower() in ["violet", "purple"]:
            select_type = 5
        
        # 4. Place bet
        result = api_client.place_bet(
            type_id=type_id,
            issue=issue,
            select_type=select_type,
            amount=amount
        )
        
        logger.info(f"Bet response: {result}")
        
        if result.get('code') == 0:
            session["last_betted_issue"] = issue
            session["total_bets"] = session.get("total_bets", 0) + 1
            logger.info(f"✅ Bet placed on issue {issue}")
            return True
        else:
            logger.warning(f"❌ Bet failed: {result.get('msg')}")
            return False
            
    except Exception as e:
        logger.error(f"Place bet error: {e}")
        return False

# ==========================================================
# 📊 API Fetching Functions (for AI)
# ==========================================================
async def get_latest_game_result(target_issue: str, user_tg_id: int) -> str:
    """Get game result for specific issue using API"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return "? | ?"
    
    api_client = session.get("api_client")
    if not api_client:
        return "? | ?"
    
    try:
        # Get history
        history = api_client.get_noaverage_emergd_list(type_id=30, page_size=10)
        
        for item in history:
            if str(item.get('issueNumber')) == str(target_issue):
                num = int(item.get('number', 0))
                size = "BIG" if num >= 5 else "SMALL"
                return f"{num} | {size}"
    except Exception as e:
        logger.error(f"Get result error: {e}")
        
    return "? | ?"

async def get_ai_prediction(user_tg_id: int):
    """Get AI prediction using API data"""
    session = active_sessions.get(user_tg_id)
    if not session:
        return None, 0, None, None
    
    api_client = session.get("api_client")
    if not api_client:
        return None, 0, None, None
    
    try:
        # Get history
        history = api_client.get_noaverage_emergd_list(type_id=30, page_size=10)
        
        if not history:
            return None, 0, None, None
        
        # Get last completed issue
        last_completed_issue = history[0].get('issueNumber')
        next_issue = str(int(last_completed_issue) + 1)
        
        # Build history for AI
        history_docs = []
        for item in history:
            num = int(item.get('number', 0))
            size = "BIG" if num >= 5 else "SMALL"
            history_docs.append({"size": size, "number": num})
        
        # Get user's AI mode
        user_ai_name = session.get("ai_mode", "Pattern AI")
        
        # Find mode key
        mode_key = "pattern"
        for key, val in ai_engines.AI_MODES.items():
            if val["name"] == user_ai_name:
                mode_key = key
                break
        
        # Get prediction
        predicted_size, display_name, confidence, desc = ai_engines.get_prediction(history_docs, mode_key)
        
        return predicted_size.lower(), confidence, next_issue, user_ai_name
        
    except Exception as e:
        logger.error(f"AI prediction error: {e}")
        return None, 0, None, None

# ==========================================================
# 🔄 Continuous Auto Bet Loop Task (API Version)
# ==========================================================
async def auto_bet_loop(user_tg_id: int, message: types.Message):
    """Main auto-betting loop using API"""
    await message.answer("🚀 Auto-Betting စတင်ပါပြီ! ရပ်လိုပါက 🛑 Stop Auto-Bet ကို နှိပ်ပါ")
    last_betted_issue = None
    api_error_count = 0
    
    session = active_sessions.get(user_tg_id)
    if not session:
        return
    
    api_client = session.get("api_client")
    if not api_client:
        return

    while active_sessions.get(user_tg_id, {}).get("is_auto_betting", False):
        try:
            predicted_bet, confidence, current_issue, ai_name = await get_ai_prediction(user_tg_id)

            if current_issue:
                api_error_count = 0
                if current_issue != last_betted_issue:
                    
                    # --- Hit Betting Logic ---
                    hit_wait = session.get("hit_wait", 0)
                    current_misses = session.get("current_misses", 0)
                    
                    if hit_wait > 0 and current_misses < hit_wait:
                        msg = await message.answer(
                            f"⏳ <b>Hit Waiting: {current_misses}/{hit_wait}</b>\n"
                            f"• WINGO_30S : {current_issue}\n"
                            f"• Pred : {predicted_bet.upper()} (ကြိုတင်ခန့်မှန်းချက်)"
                        )
                        
                        actual_result = "? | ?"
                        for _ in range(20):
                            if not active_sessions.get(user_tg_id, {}).get("is_auto_betting", False): 
                                break
                            await asyncio.sleep(2)
                            actual_result = await get_latest_game_result(current_issue, user_tg_id)
                            if actual_result != "? | ?": 
                                break
                                
                        try:
                            actual_size = actual_result.split(" | ")[1].strip().lower()
                            if predicted_bet.lower() == actual_size:
                                session["current_misses"] = 0 
                                await msg.edit_text(f"🔄 <b>Hit Reset:</b> AI ကြိုတင်ခန့်မှန်းချက် အောင်မြင်ပြီး ရေတွက်မှုကို ပြန်လည်သတ်မှတ်လိုက်ပါပြီ\nResult: {actual_result}")
                                asyncio.create_task(delete_message_later(msg, 5)) 
                                
                            elif actual_size != "?":
                                session["current_misses"] += 1 
                                new_miss = session["current_misses"]
                                if new_miss >= hit_wait:
                                    await msg.edit_text(f"🎯 <b>Target Reached!</b> {hit_wait} ကြိမ်တိုင်တိုင်း သတ်မှတ်ထားသော ရေတွက်မှု ပြည့်သွားပါပြီ\nResult: {actual_result}")
                                    asyncio.create_task(delete_message_later(msg, 5)) 
                                else:
                                    await msg.edit_text(f"❌ <b>Virtual Loss:</b> {new_miss}/{hit_wait} ကြိမ်လွန်သွားပါပြီ\nResult: {actual_result}")
                                    asyncio.create_task(delete_message_later(msg, 5)) 
                                    
                            last_betted_issue = current_issue
                        except Exception: 
                            pass
                            
                        await asyncio.sleep(2)
                        continue 

                    # --- Main betting logic ---
                    sequence = session.get("bet_sequence", [10])
                    step = session.get("current_bet_step", 0)
                    
                    if step >= len(sequence):
                        step = 0
                        session["current_bet_step"] = 0
                        
                    current_amount = sequence[step]

                    # Check balance
                    balance = api_client.get_balance()
                    if balance < current_amount:
                        await message.answer(
                            f"⚠️ <b>လက်ကျန်ငွေ မလုံလောက်ပါ</b>\n"
                            f"လိုအပ်သောငွေ: {current_amount} Ks\n"
                            f"လက်ကျန်ငွေ: {balance}\n"
                            f"🛑 Auto Bet ကို ရပ်လိုက်ပါပြီ"
                        )
                        session["is_auto_betting"] = False
                        break

                    # Place bet
                    betting_msg = (
                        f"<blockquote>"
                        f"📄 WINGO_30S : {current_issue}\n"
                        f"📄 Series : Ai Prediction\n"
                        f"🌸 Pred : {predicted_bet.upper()} | {current_amount} Ks"
                        f"</blockquote>"
                    )
                    await message.answer(betting_msg)

                    last_betted_issue = current_issue
                    await asyncio.sleep(5)

                    success = await place_auto_bet_api(user_tg_id, predicted_bet, current_amount)
                    
                    if success:
                        # Get result
                        actual_result = "? | ?"
                        for _ in range(20): 
                            if not active_sessions.get(user_tg_id, {}).get("is_auto_betting", False): 
                                break 
                            await asyncio.sleep(2)
                            actual_result = await get_latest_game_result(current_issue, user_tg_id)
                            if actual_result != "? | ?": 
                                break 
                        
                        # Get new balance
                        new_balance = api_client.get_balance()
                        
                        try:
                            actual_size = actual_result.split(" | ")[1].strip().lower() 
                            predicted_size = predicted_bet.lower()
                            
                            if predicted_size == actual_size:
                                profit_amount = current_amount * 0.96
                                status_title = f"✅ <b>WIN</b> 🤑 +{profit_amount:.2f} Ks"
                                session["session_profit"] = session.get("session_profit", 0) + profit_amount
                                session["current_bet_step"] = 0 
                                session["current_misses"] = 0 
                                
                            elif actual_size == "?": 
                                status_title = f"⏳ <b>DRAW</b> (Pending)"
                                
                            else:
                                status_title = f"❌ <b>LOSE</b> 💸 {current_amount:.2f} Ks"
                                session["session_profit"] = session.get("session_profit", 0) - current_amount
                                session["current_bet_step"] += 1
                                if session["current_bet_step"] >= len(sequence): 
                                    session["current_bet_step"] = 0
                                
                            current_profit = session.get("session_profit", 0.0)
                            profit_display = f"+{current_profit:,.2f} Ks" if current_profit > 0 else f"{current_profit:,.2f} Ks"
                            
                            result_msg = (
                                f"<blockquote>"
                                f"{status_title}\n"
                                f"─────────────────\n"
                                f"🎯 WINGO_30S : {current_issue}\n"
                                f"🎯 Result : {actual_result}\n"
                                f"💰 Balance : {new_balance:,.2f}\n"
                                f"💰 Total Profit : {profit_display}"
                                f"</blockquote>"
                            )
                            await message.answer(result_msg)
                            
                            # Update balance in DB
                            await update_user_balance(user_tg_id, str(new_balance))
                            
                            # Check profit target
                            profit_target = session.get("profit_target", 0)
                            if profit_target > 0 and current_profit >= profit_target:
                                await message.answer(
                                    f"🎉 <b>Target ပြည့်သွားပါပြီ! ({profit_display})</b>\n"
                                    f"သတ်မှတ်ထားသော ရည်မှန်ချက် {profit_target} Ks နှင့် ပြည့်မီသွားသောကြောင့် Auto Bet ကို ရပ်လိုက်ပါပြီ"
                                )
                                session["is_auto_betting"] = False
                                break
                                
                        except Exception as e:
                            logger.error(f"Result processing error: {e}")
                            
                    else: 
                        await asyncio.sleep(5) 
                        
                else: 
                    await asyncio.sleep(2) 
                    
            else:
                api_error_count += 1
                if api_error_count == 3: 
                    await message.answer("⚠️ <b>API မှားယွင်းနေသည်:</b> ကြိုတင်ခန့်မှန်းချက်များ ရယူရန် မဖြစ်နိုင်ပါ")
                await asyncio.sleep(5) 
                
        except Exception as e:
            logger.error(f"Auto Loop Error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# ⚙️ Set Bet-Size Handlers
# ==========================================================
@dp.message(F.text == TEXT_BETSIZE)
async def btn_set_betsize(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    current_seq = active_sessions[user_tg_id].get("bet_sequence", [10])
    seq_str = "-".join(map(str, current_seq))
    
    await state.set_state(LoginForm.enter_bet_sequence)
    await message.answer(
        f"⚙️ <b>Auto Bet လောင်းကြေးပမာဏ (Bet Size) ကို သတ်မှတ်ပါ</b>\n\n"
        f"လက်ရှိ သတ်မှတ်ထားသော ပုံစံ: <code>{seq_str}</code>\n\n"
        f"<b>Format:</b> 10-20-40-80 (သို့) 100-200-400\n"
        f"ဂဏန်းများကို '-' ခြားပြီး ရိုက်ထည့်ပါ\n"
        f"ဖျက်လိုပါက 'Cancel' ဟုရိုက်ပါ",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(LoginForm.enter_bet_sequence)
async def process_bet_sequence(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    text = message.text.strip()
    
    if text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ ဖျက်သိမ်းလိုက်ပါပြီ", reply_markup=get_logged_in_keyboard())
        
    try:
        sequence = [int(x.strip()) for x in text.split('-')]
        if len(sequence) == 0 or any(x <= 0 for x in sequence):
            raise ValueError
            
        active_sessions[user_tg_id]["bet_sequence"] = sequence
        active_sessions[user_tg_id]["current_bet_step"] = 0 
        
        seq_str = "-".join(map(str, sequence))
        await state.set_state(LoginForm.main_menu)
        await message.answer(
            f"✅ <b>Bet Size အောင်မြင်စွာ သတ်မှတ်လိုက်ပါပြီ:</b> <code>{seq_str}</code>", 
            reply_markup=get_logged_in_keyboard()
        )
    except Exception:
        await message.answer("❌ မှားယွင်းနေပါသည်။ ဥပမာ: 10-20-40-80 ဟု ဂဏန်းများကို '-' ခြားပြီး ရိုက်ထည့်ပါ")

# ==========================================================
# 🤖 Reply Keyboard Auto Bet & Status Handlers
# ==========================================================
@dp.message(F.text == TEXT_START)
async def btn_start_auto(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    if active_sessions[user_tg_id].get("is_auto_betting", False):
        return await message.answer("⚠️ Auto Bet လုပ်ဆောင်နေပြီးဖြစ်ပါသည်။ ရပ်လိုပါက 🛑 Stop Auto-Bet ကိုနှိပ်ပါ")

    if "bet_sequence" not in active_sessions[user_tg_id]:
        active_sessions[user_tg_id]["bet_sequence"] = [10]
        active_sessions[user_tg_id]["current_bet_step"] = 0

    # Get balance
    api_client = active_sessions[user_tg_id].get("api_client")
    if api_client:
        balance = api_client.get_balance()
        active_sessions[user_tg_id]["start_balance"] = balance
    else:
        active_sessions[user_tg_id]["start_balance"] = 0.0

    active_sessions[user_tg_id]["is_auto_betting"] = True
    asyncio.create_task(auto_bet_loop(user_tg_id, message))

@dp.message(F.text == TEXT_STOP)
async def btn_stop_auto(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")

    active_sessions[user_tg_id]["is_auto_betting"] = False
    await message.answer("🛑 <b>Auto Bet ကို ရပ်လိုက်ပါပြီ</b>")

@dp.message(F.text == TEXT_STATUS)
async def btn_status(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")

    session = active_sessions[user_tg_id]
    api_client = session.get("api_client")
    
    if session.get("is_auto_betting", False):
        is_auto = "Running 🟢"
    else:
        is_auto = "Stopped 🔴"
        
    ai_mode = session.get("ai_mode", "Pattern AI")
    site_name = session.get("site", "777BIGWIN")
    
    current_seq = session.get("bet_sequence", [10])
    seq_str = "-".join(map(str, current_seq))
    current_step = session.get("current_bet_step", 0)
    
    profit_target = session.get("profit_target", 0)
    
    if api_client:
        current_balance = api_client.get_balance()
    else:
        current_balance = 0.0
    
    current_profit = session.get("session_profit", 0.0)
    profit_display = f"+{current_profit:g} Ks" if current_profit >= 0 else f"{current_profit:g} Ks"
        
    target_str = f"{profit_target} Ks" if profit_target > 0 else "Not Set"

    status_text = (
        "📊 <b>Bot Status</b>\n"
        "─────────────────\n"
        f"🌐 <b>Active Site:</b> {site_name}\n"
        f"🧠 <b>Auto-Bet State:</b> {is_auto}\n"
        f"🧠 <b>Active AI Mode:</b> {ai_mode}\n"
        f"💰 <b>Current Balance:</b> {current_balance:.2f} Ks\n"
        f"⚙️ <b>Bet Sequence:</b> <code>{seq_str}</code>\n"
        f"📍 <b>Current Step:</b> {current_step + 1}/{len(current_seq)} ({current_seq[current_step] if current_step < len(current_seq) else 'N/A'} Ks)\n"
        f"🎯 <b>Profit Target:</b> {target_str}\n"
        f"📈 <b>Total Profit:</b> {profit_display}\n"
    )
    await message.answer(status_text)

# ==========================================================
# 💰 Check Balance & Other Handlers
# ==========================================================
@dp.message(LoginForm.main_menu, F.text == TEXT_BALANCE)
async def check_balance(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: 
        return await message.answer("⚠️ ကျေးဇူးပြု၍ Login ဦးစွာပြုလုပ်ပါ")
        
    await message.answer("⏳ <b>လက်ကျန်ငွေ (Balance) ကို စစ်ဆေးနေပါသည်...</b>")
    
    api_client = active_sessions[user_tg_id].get("api_client")
    if api_client:
        balance = api_client.get_balance()
        await message.answer(f"💰 <b>သင့်လက်ကျန်ငွေ:</b> {balance:.2f} Ks", reply_markup=get_logged_in_keyboard())
    else:
        await message.answer("❌ Balance စစ်ဆေးရန် မဖြစ်နိုင်ပါ", reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_INFO)
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    user_id = data.get('user_id', 'N/A')
    username = data.get('username', 'N/A')
    nickname = data.get('nickname', 'Unknown')
    balance = data.get('balance', '0.00')
    site_name = active_sessions.get(message.from_user.id, {}).get("site", "Unknown")
    login_time = data.get('login_time', get_myanmar_time().strftime("%Y-%m-%d %H:%M:%S"))
    
    expire_iso = await get_user_subscription(message.from_user.id)
    if expire_iso:
        expire_str = datetime.fromisoformat(expire_iso).strftime('%Y-%m-%d %I:%M %p')
    else:
        expire_str = "N/A"

    info_text = (
        "👤 <b>User Information:</b>\n"
        f"├─ 🌐 <b>Site:</b> {site_name}\n"
        f"├─ 🆔 <b>User ID:</b> {user_id}\n"
        f"├─ 📱 <b>Username:</b> {username}\n"
        f"├─ 🏷️ <b>Nickname:</b> {nickname}\n"
        f"├─ 💰 <b>Balance:</b> {balance}\n"
        f"├─ 📅 <b>Login Date:</b> {login_time}\n"
        f"└─ 🔑 <b>Expire On:</b> {expire_str} (MMT)\n"
    )
    await message.answer(info_text, reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_LOGOUT)
async def logout(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id in active_sessions:
        active_sessions[user_tg_id]["is_auto_betting"] = False 
        active_sessions[user_tg_id]["is_ai_prediction_enabled"] = False 
        
        # Close API session
        api_client = active_sessions[user_tg_id].get("api_client")
        if api_client:
            try:
                await api_client.close()
            except Exception:
                pass
            
        del active_sessions[user_tg_id]
        
    await state.clear()
    await message.answer("👋 အကောင့်မှ ထွက်လိုက်ပါပြီ", reply_markup=get_main_keyboard())

@dp.message(F.text == TEXT_GAMES)
async def games(message: types.Message):
    await message.answer(
        "🎮 <b>Game ရွေးချယ်ရန်:</b>\nWin Go 30s ကို ရွေးချယ်ထားပါသည်။\n\n"
        "🧠 <b>Bot Commands:</b>\n"
        f"<code>{TEXT_START}</code> - Auto Bet စတင်ရန်\n"
        f"<code>{TEXT_STOP}</code> - Auto Bet ရပ်ရန်\n",
        reply_markup=get_main_keyboard()
    )

# ==========================================================
# 🚀 Main Bot Loop
# ==========================================================
async def main():
    logger.info("🚀 Auto-Bot API Version စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot ကို ရပ်လိုက်ပါပြီ")
