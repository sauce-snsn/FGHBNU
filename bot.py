import asyncio
import os
import html
import random
import aiohttp
import time
import re
import string
import json
import hashlib
import uuid
from datetime import datetime, timedelta
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

# Database နှင့် AI ကို ချိတ်ဆက်ခြင်း
import database as db 
import ai_engines
from ai_engines import AI_MODES, AI_MODE_EMOJIS

# ==========================================================
# ⚙️ Configuration
# ==========================================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_sessions = {}

# ==========================================================
# 🌐 API Configurations & Universal Signature Function
# ==========================================================
SITE_CONFIGS = {
    "777BIGWIN": {
        "api_url": "https://api.bigwinqaz.com/api/webapi",
        "origin": "https://www.777bigwingame.app"
    },
    "6Lottery": {
        "api_url": "https://6lotteryapi.com/api/webapi",
        "origin": "https://www.6win566.com"
    },
    "CK LOTTERY": {
        "api_url": "https://ckygjf6r.com/api/webapi",
        "origin": "https://cklottery.cc"
    }
}

def get_signed_payload(payload: dict) -> dict:
    """Frontend ၏ Signature တွက်ချက်မှု Logic အတိအကျ"""
    t = {k: v for k, v in payload.items() if k not in ['signature', 'timestamp']}
    
    if 'language' not in t:
        t['language'] = 7
    if 'random' not in t:
        t['random'] = uuid.uuid4().hex
        
    n = {}
    for key in sorted(t.keys()):
        val = t[key]
        if val is not None and val != "":
            n[key] = val
            
    json_str = json.dumps(n, separators=(',', ':'))
    signature = hashlib.md5(json_str.encode('utf-8')).hexdigest().upper()
    
    t['signature'] = signature
    t['timestamp'] = int(time.time())
    return t

def get_headers(site: str, token: str = "") -> dict:
    config = SITE_CONFIGS.get(site, SITE_CONFIGS["777BIGWIN"])
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': config["origin"],
        'referer': f'{config["origin"]}/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    if token:
        headers['authorization'] = f'Bearer {token}'
    return headers

def get_select_type(bet_type: str) -> int:
    b = bet_type.lower()
    if b == "big": return 13
    elif b == "small": return 14
    elif b == "red": return 1
    elif b == "green": return 3
    elif b in ["violet", "purple"]: return 2
    return 13 

# ==========================================================
# 🌟 Premium Emojis + Style for Reply Keyboard 
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
TEXT_VIRTUAL_MODE = "Virtual Mode"
TEXT_REAL_MODE = "Real Mode"
TEXT_UPLOAD_CHANNEL = "Upload Channel"

E_INFO = KeyboardButton(text=TEXT_INFO, icon_custom_emoji_id="5868656545634689320", style="primary")
E_BALANCE = KeyboardButton(text=TEXT_BALANCE, icon_custom_emoji_id="5868108575387671725", style="primary")
E_STATUS = KeyboardButton(text=TEXT_STATUS, icon_custom_emoji_id="5877443460725739250", style="primary")
E_START = KeyboardButton(text=TEXT_START, icon_custom_emoji_id="5884248697980608904", style="success")
E_STOP = KeyboardButton(text=TEXT_STOP, icon_custom_emoji_id="5884289942371401145", style="danger")
E_GAMES = KeyboardButton(text=TEXT_GAMES, icon_custom_emoji_id="5868665489092263539", style="primary")
E_AI = KeyboardButton(text=TEXT_AI, icon_custom_emoji_id="5877652234091891383", style="primary")
E_BETSIZE = KeyboardButton(text=TEXT_BETSIZE, icon_custom_emoji_id="5877260593903177342", style="primary")
E_PROFIT = KeyboardButton(text=TEXT_PROFIT, icon_custom_emoji_id="5967574255670399788", style="primary")
E_HIT = KeyboardButton(text=TEXT_HIT, icon_custom_emoji_id="5869547610204280761", style="primary")
E_PREDICT = KeyboardButton(text=TEXT_PREDICT, icon_custom_emoji_id="5890997763331591703", style="primary")
E_LOGOUT = KeyboardButton(text=TEXT_LOGOUT, icon_custom_emoji_id="5875180111744995604", style="danger")
E_LOGIN = KeyboardButton(text=TEXT_LOGIN, icon_custom_emoji_id="5884041323843955199", style="primary")
E_BACK = KeyboardButton(text=TEXT_BACK, icon_custom_emoji_id="5848119413041431362", style="primary")
E_VIRTUAL = KeyboardButton(text=TEXT_VIRTUAL_MODE, icon_custom_emoji_id="5807868868886009920", style="primary")
E_REAL = KeyboardButton(text=TEXT_REAL_MODE, icon_custom_emoji_id="5868656545634689320", style="primary")
E_UPLOAD = KeyboardButton(text=TEXT_UPLOAD_CHANNEL, icon_custom_emoji_id="5890997763331591703", style="primary")

P_1 = '<tg-emoji emoji-id="5890997763331591703">⚙️</tg-emoji>'
P_2 = '<tg-emoji emoji-id="5875180111744995604">⚙️</tg-emoji>'
P_3 = '<tg-emoji emoji-id="5877443460725739250">⚙️</tg-emoji>'
P_4 = '<tg-emoji emoji-id="5967574255670399788">⚙️</tg-emoji>'
P_5 = '<tg-emoji emoji-id="5807868868886009920">⚙️</tg-emoji>'
P_6 = '<tg-emoji emoji-id="5807461353799030682">⚙️</tg-emoji>'

# ==========================================================
# 🛠️ Helper Functions
# ==========================================================
def extract_balance(bal_str: str) -> float:
    try:
        clean_str = re.sub(r'[^\d.]', '', str(bal_str))
        return float(clean_str) if clean_str else 0.0
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
            if user_id == OWNER_ID:
                return await handler(event, data)
                
            whitelisted = await db.db["whitelist"].find_one({"uid": str(user_id)})
            if whitelisted:
                return await handler(event, data)
                
            if isinstance(event, types.Message) and text.startswith("PSP-") and len(text) == 20:
                return await handler(event, data)
                
            expire_iso = await db.get_user_subscription(user_id)
            is_authorized = False
            
            if expire_iso:
                expire_time = datetime.fromisoformat(expire_iso)
                if get_myanmar_time() < expire_time:
                    is_authorized = True
            
            if not is_authorized:
                if isinstance(event, types.Message):
                    await event.answer("ᴄᴏɴᴛᴀᴄᴛ ᴜꜱ @iwillgoforwardsalone")
                elif isinstance(event, types.CallbackQuery):
                    await event.answer("အသုံးပြုခွင့် သက်တမ်းကုန်သွားပါပြီ။", show_alert=True)
                return 
        
        return await handler(event, data)

dp.message.middleware(AuthMiddleware())
dp.callback_query.middleware(AuthMiddleware())

# ==========================================================
# 🎡 AI Configuration
# ==========================================================
def circle_rnd_predict(history_docs):
    wheel = ["BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL"]
    predicted = random.choice(wheel)
    emoji = "🔴" if predicted == "BIG" else "🟢"
    confidence = round(random.uniform(50.0, 65.0), 1)
    name_str = "အကြီး" if predicted == "BIG" else "အသေး"
    return predicted, f"{predicted} ({name_str}) {emoji}", confidence, "🎡 Circle Rnd: Spinner"

ai_engines.AI_MODES["circle_rnd"] = {
    "func": circle_rnd_predict,
    "name": "🎡 Circle Rnd",
    "desc": "Random Wheel Spin"
}

VALID_AI_NAMES = [m["name"] for m in ai_engines.AI_MODES.values()]

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
    enter_custom_pattern = State() 
    enter_virtual_balance = State() 

# ==========================================================
# ⌨️ Keyboards
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[E_LOGIN]], resize_keyboard=True)

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="777BIGWIN", style="success"),
             KeyboardButton(text="6Lottery", style="danger")],
            [KeyboardButton(text="CK LOTTERY", style="primary")],
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
            [E_VIRTUAL, E_REAL],  
            [E_UPLOAD, E_LOGOUT]
        ],
        resize_keyboard=True
    )

def get_upload_toggle_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Upload ON", style="success"),
             KeyboardButton(text="❌ Upload OFF", style="danger")],
            [E_BACK]
        ],
        resize_keyboard=True
    )

def get_ai_mode_keyboard():
    standard_modes = [m for k, m in AI_MODES.items() if not k.startswith("pro_")]
    keyboard = []
    row = []
    
    for mode in standard_modes:
        mode_name = mode["name"]
        emoji_id = AI_MODE_EMOJIS.get(mode_name, "5868656545634689320")
        btn = KeyboardButton(text=mode_name, icon_custom_emoji_id=emoji_id, style="primary")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    pro_btn = KeyboardButton(text="Pro AI Features", icon_custom_emoji_id="5807868868886009920", style="success")
    back_btn = KeyboardButton(text="BACK", icon_custom_emoji_id="5848119413041431362", style="primary")
    keyboard.append([pro_btn])
    keyboard.append([back_btn])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_pro_ai_mode_keyboard():
    pro_modes = [m for k, m in AI_MODES.items() if k.startswith("pro_")]
    keyboard = []
    row = []
    
    for mode in pro_modes:
        mode_name = mode["name"]
        btn = KeyboardButton(text=mode_name, icon_custom_emoji_id="5807868868886009920", style="primary")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    back_btn = KeyboardButton(text="BACK", icon_custom_emoji_id="5848119413041431362", style="danger")
    keyboard.append([back_btn])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_hit_betting_inline_keyboard(current_wait: int = 0):
    keyboard = []
    number_buttons = []
    for i in range(1, 10):
        btn_style = "success" if current_wait == i else "primary"
        number_buttons.append(InlineKeyboardButton(text=str(i), callback_data=f"hitbet_{i}", style=btn_style))
        
    for i in range(0, 9, 3): 
        keyboard.append(number_buttons[i:i+3])
        
    disable_text = "0 (Disabled)" if current_wait == 0 else "0 (Disable)"
    keyboard.append([InlineKeyboardButton(text=disable_text, callback_data="hitbet_0", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_ai_prediction_toggle_keyboard(is_enabled: bool):
    btn = InlineKeyboardButton(
        text="🟢 Enabled" if is_enabled else "🔴 Disabled", 
        callback_data="toggle_aipred", 
        style="success" if is_enabled else "danger"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Cancel")]], resize_keyboard=True)

# ==========================================================
# 👑 Owner Commands (Keys & Whitelist)
# ==========================================================
@dp.message(F.text.startswith(".key "))
async def cmd_generate_key(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split(" ")
    if len(parts) < 2:
        return await message.answer("⚠️ Format မှားနေပါသည်။\nအသုံးပြုရန်: <code>.key 2H</code>, <code>.key 5D</code>")
        
    duration = parts[1].strip().upper()
    if not parse_duration(duration):
        return await message.answer("⚠️ အချိန်သတ်မှတ်ချက် မှားနေပါသည်။\nဥပမာ: <code>2H</code>, <code>5D</code>")
    
    date_prefix = get_myanmar_time().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    key_str = f"PSP-{date_prefix}{random_str}"
    
    await db.create_key(key_str, duration)
    await message.answer(f"✅ <b>Key အသစ် ဖန်တီးပြီးပါပြီ။</b>\n\n🔑 Key: <code>{key_str}</code>\n⏱️ Duration: <b>{duration}</b>")

@dp.message(F.text.startswith(".gen "))
async def cmd_gen_keys(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split(" ")
    if len(parts) < 3:
        return await message.answer("⚠️ Format မှားနေပါသည်။\nအသုံးပြုရန်: <code>.gen 5 2H</code>, <code>.gen 10 5D</code>")
        
    try:
        count = int(parts[1])
        duration = parts[2].strip().upper()
        if not parse_duration(duration): raise ValueError
    except:
        return await message.answer("⚠️ အချိန်သတ်မှတ်ချက် သို့မဟုတ် အရေအတွက် မှားနေပါသည်။\nဥပမာ: <code>.gen 5 2H</code>")
        
    date_prefix = get_myanmar_time().strftime("%Y%m%d")
    keys = []
    
    for _ in range(count):
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        key_str = f"PSP-{date_prefix}{random_str}"
        await db.create_key(key_str, duration)
        keys.append(key_str)
        
    keys_text = "\n".join([f"<code>{k}</code>" for k in keys])
    await message.answer(f"✅ <b>Keys {count} ခု ဖန်တီးပြီးပါပြီ။</b>\n\n{keys_text}\n\n⏱️ Duration: <b>{duration}</b>")

@dp.message(F.text.startswith(".add "))
async def cmd_add_uid(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split(" ")
    if len(parts) < 2:
        return await message.answer("⚠️ ဥပမာ: <code>.add 123456789</code>")
        
    target_id = parts[1].strip()
    await db.db["whitelist"].update_one({"uid": target_id}, {"$set": {"uid": target_id}}, upsert=True)
    await message.answer(f"✅ Telegram UID: <code>{target_id}</code> ကို Whitelist ထဲသို့ ထည့်သွင်းပြီးပါပြီ။\n(Key မလိုဘဲ သုံးနိုင်ပါသည်)")

@dp.message(F.text.startswith(".del "))
async def cmd_del_uid(message: types.Message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split(" ")
    if len(parts) < 2:
        return await message.answer("⚠️ ဥပမာ: <code>.del 123456789</code>")
        
    target_id = parts[1].strip()
    await db.db["whitelist"].delete_one({"uid": target_id})
    await message.answer(f"🗑️ Telegram UID: <code>{target_id}</code> ကို Whitelist မှ ပယ်ဖျက်လိုက်ပါပြီ။")

@dp.message(lambda msg: msg.text and msg.text.startswith("PSP-") and len(msg.text) == 20)
async def process_key_redemption(message: types.Message):
    key_str = message.text.strip()
    key_data = await db.get_key(key_str)
    
    if key_data:
        td = parse_duration(key_data["duration"]) or timedelta(days=1)
        user_id = message.from_user.id
        current_expire = get_myanmar_time()
        
        existing_expire_iso = await db.get_user_subscription(user_id)
        if existing_expire_iso:
            old_expire = datetime.fromisoformat(existing_expire_iso)
            if old_expire > get_myanmar_time():
                current_expire = old_expire
                
        new_expire = current_expire + td
        await db.update_user_subscription(user_id, new_expire.isoformat())
        await db.delete_key(key_str)
        
        await message.answer(
            f"ʟɪᴄᴇɴꜱᴇ ᴋᴇʏ ᴀᴄᴛɪᴠᴇ\n"
            f"ᴇxᴘɪʀᴇ ᴛɪᴍᴇ <b>{new_expire.strftime('%Y-%m-%d %I:%M %p')}</b> (MMT) \n"
            f"ᴄʟɪᴄᴋ /start ᴛᴏ ᴘʟᴀʏ."
        )
    else:
        await message.answer("ɪɴᴄᴏʀʀᴇᴄᴛ ᴋᴇʏ ᴏʀ ᴋᴇʏ ɪꜱ ᴇxᴘɪʀᴇᴅ.")

# ==========================================================
# 🤖 Standard Bot Handlers
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("ᴄʟɪᴄᴋ ᴛᴏ ʟᴏɢɪɴ", reply_markup=get_main_keyboard())

@dp.message(F.text == TEXT_LOGIN)
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.select_site)
    await message.answer("ᴘʟᴇᴀꜱᴇ ꜱᴇʟᴇᴄᴛ ᴀ ꜱɪᴛᴇ ᴛᴏ ʟᴏɢɪɴ", reply_markup=get_site_keyboard())

@dp.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "Back":
        await state.clear()
        return await message.answer("Cancelled.", reply_markup=get_main_keyboard())
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer("ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ", reply_markup=ReplyKeyboardRemove())

@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer("ᴘʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴘᴀꜱꜱᴡᴏʀᴅ", reply_markup=ReplyKeyboardRemove())

# ==========================================================
# 📡 Custom API Calls
# ==========================================================
async def api_get_user_info(site: str, token: str):
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetUserInfo"
    
    payload = {'language': 7}
    signed_payload = get_signed_payload(payload)
    headers = get_headers(site, token)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=signed_payload) as response:
            result = await response.json()
            return result

# ==========================================================
# 🔥 API Logic: Login & Database Save
# ==========================================================
@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get('phone')
    site_name = data.get('site', '777BIGWIN')
    user_tg_id = message.from_user.id
    
    loading_msg = await message.answer("🔄 <b>API မှတစ်ဆင့် Login ဝင်နေပါသည်...</b>")

    try:
        config = SITE_CONFIGS.get(site_name)
        login_url = f"{config['api_url']}/Login"
        
        login_payload = {
            'username': username,
            'pwd': password,
            'phonetype': 1,
            'logintype': 'mobile',
            'packId': '',
            'deviceId': uuid.uuid4().hex,
            'pixelId': '',
            'fbcId': '',
            'fbc': '',
            'fbp': '',
            'adId': '',
            'language': 7
        }
        
        signed_login_payload = get_signed_payload(login_payload)
        headers = get_headers(site_name)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(login_url, headers=headers, json=signed_login_payload) as response:
                api_result = await response.json()
                
        if api_result.get("code") == 0 or api_result.get("msg") == "success":
            user_data = api_result.get("data", {})
            token = user_data.get("token", "") if isinstance(user_data, dict) else str(user_data)
        
            user_info_res = await api_get_user_info(site_name, token)
            
            user_id = "N/A"
            nickname = "Unknown"
            balance_text = "0.00 Ks"
            
            if user_info_res.get("code") == 0:
                info_data = user_info_res.get("data", {})
                user_id = str(info_data.get("userId", info_data.get("id", "N/A")))
                nickname = info_data.get("nickName", "Unknown")
                balance_val = info_data.get("balance", info_data.get("amount", 0.0))
                balance_text = f"{balance_val} Ks"
            
            site_login_time = get_myanmar_time().strftime("%Y-%m-%d %H:%M:%S")

            db_user = await db.get_user(user_tg_id)
            ai_mode = db_user.get("ai_mode", "🎯 Pattern AI") if db_user else "🎯 Pattern AI"
            if ai_mode not in VALID_AI_NAMES: ai_mode = "🎯 Pattern AI"

            await db.save_user_login(user_tg_id, username, user_id, nickname, balance_text, site_login_time, ai_mode)

            await state.update_data(
                is_logged_in=True, 
                username=username, 
                user_id=user_id,
                nickname=nickname, 
                balance=balance_text, 
                login_time=site_login_time
            )

            active_sessions[user_tg_id] = {
                "site": site_name,
                "token": token,
                "is_auto_betting": False,
                "ai_mode": ai_mode,
                "bet_sequence": [10],           
                "current_bet_step": 0,          
                "profit_target": 0,             
                "start_balance": extract_balance(balance_text),
                "session_profit": 0.0, 
                "hit_wait": 0,
                "current_misses": 0,
                "is_ai_prediction_enabled": False, 
                "last_predicted_issue": None,
                "is_virtual_mode": False,
                "virtual_balance": 0.0,
                "virtual_session_profit": 0.0,
                "upload_channel": False
            }

            caption_text = (
                "🏆 <b>LOGIN SUCCESSFUL!</b>\n"
                "━━━━━━━━━━━━━━━\n\n"
                f"🌐 <b>Site:</b> <code>{site_name}</code>\n\n"
                "👤 <b>User Information:</b>\n"
                "┌──────────────────\n"
                f"├─ 🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"├─ 📱 <b>Username:</b> <code>{username}</code>\n"
                f"├─ 🏷️ <b>Nickname:</b> {nickname}\n"
                f"├─ 💰 <b>Balance:</b> <code>{balance_text}</code>\n"
                f"└─ 📅 <b>Login Date:</b> {site_login_time}\n"
                "━━━━━━━━━━━━━━━\n"
                "<b>PSP-AUTO BETTING | API CONNECTED VERIFIED</b>"
            )

            await loading_msg.delete()
            await message.answer(caption_text, reply_markup=get_logged_in_keyboard())
            await state.set_state(LoginForm.main_menu)
            
        else:
            await loading_msg.delete()
            err_msg = api_result.get("msg", "Unknown API Error")
            await message.answer(f"❌ ʟᴏɢɪɴ ꜰᴀɪʟᴇᴅ: {err_msg}", reply_markup=get_main_keyboard())
            await state.clear()

    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"⚠️ <b>Error:</b> {html.escape(str(e))}", reply_markup=get_main_keyboard())
        await state.clear()

# ==========================================================
# 📊 API Fetching Data
# ==========================================================
async def get_latest_game_result(target_issue, user_tg_id):
    session_data = active_sessions.get(user_tg_id, {})
    site = session_data.get("site", "777BIGWIN")
    token = session_data.get("token", "")
    
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetNoaverageEmerdList"
    
    payload = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7
    }
    signed_payload = get_signed_payload(payload)
    headers = get_headers(site, token)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=signed_payload) as response:
                api_result = await response.json()
                
        records = api_result.get('data', {}).get('list', [])
        for item in records:
            if str(item['issueNumber']) == str(target_issue):
                num = int(item['number'])
                size = "BIG" if num >= 5 else "SMALL"
                return f"{num} | {size}"
    except Exception: 
        pass
        
    return "? | ?"

async def get_ai_prediction(user_tg_id):
    session_data = active_sessions.get(user_tg_id, {})
    site = session_data.get("site", "777BIGWIN")
    token = session_data.get("token", "")
    
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetNoaverageEmerdList"
    
    payload = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7
    }
    signed_payload = get_signed_payload(payload)
    headers = get_headers(site, token)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=signed_payload) as response:
                api_result = await response.json()
                
        records = api_result.get('data', {}).get('list', [])
        if records:
            last_completed_issue = records[0]['issueNumber']
            next_issue = str(int(last_completed_issue) + 1)
            
            history_docs = []
            for item in records:
                num = int(item['number'])
                size_text = "BIG" if num >= 5 else "SMALL"
                history_docs.append({"size": size_text, "number": num})
            
            user_ai_name = session_data.get("ai_mode", "🎯 Pattern AI")
            
            # --- Custom Pattern အတွက် ထပ်တိုး Logic ---
            if user_ai_name == "Set Pattern":
                pat = session_data.get("custom_pattern", ["BIG"])
                step = session_data.get("custom_pattern_step", 0)
                target_bet = pat[step]

                if step == 0:
                    last_actual_num = int(records[0]['number'])
                    last_actual_size = "BIG" if last_actual_num >= 5 else "SMALL"
                    trigger = "SMALL" if target_bet == "BIG" else "BIG"

                    if last_actual_size != trigger:
                        return "wait", 100, next_issue, user_ai_name

                return target_bet.lower(), 100, next_issue, user_ai_name
            else:
                mode_key = "pattern"
                for key, val in ai_engines.AI_MODES.items():
                    if val["name"] == user_ai_name:
                        mode_key = key
                        break
                        
                predicted_size, display_name, confidence, desc = ai_engines.get_prediction(history_docs, mode_key)
                return predicted_size.lower(), confidence, next_issue, user_ai_name
        else:
            return None, 0, None, None
            
    except Exception as e:
        print(f"Prediction Fetch Error: {e}")
        return None, 0, None, None

# ==========================================================
# 🚀 API Core Functions for Auto Bet
# ==========================================================
async def place_auto_bet(user_tg_id: int, current_issue: str, bet_type: str, total_amount: int = 10, silent: bool = False):
    try:
        session_data = active_sessions.get(user_tg_id)
        if not session_data or "token" not in session_data:
            return False
            
        site = session_data["site"]
        token = session_data["token"]
        config = SITE_CONFIGS.get(site)
        url = f"{config['api_url']}/GameBetting"
        
        select_type = get_select_type(bet_type)
        
        if total_amount >= 10000:
            base_amount = 10000
            bet_count = total_amount // 10000
        elif total_amount >= 1000:
            base_amount = 1000
            bet_count = total_amount // 1000
        elif total_amount >= 100:
            base_amount = 100
            bet_count = total_amount // 100
        else:
            base_amount = 10
            bet_count = total_amount // 10
        
        payload = {
            'typeId': 30,
            'issuenumber': current_issue,
            'amount': base_amount,
            'betCount': bet_count,
            'gameType': 2,
            'selectType': select_type,
            'language': 7
        }
        
        signed_payload = get_signed_payload(payload)
        headers = get_headers(site, token)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=signed_payload) as response:
                result = await response.json()
                
        if result.get("code") == 0 or result.get("msg") == "success":
            return True
        else:
            if not silent: print(f"Betting failed API response: {result}")
            return False

    except Exception as e:
        if not silent: print(f"Betting Request Error: {e}")
        return False

# ==========================================================
# 🔮 AI Prediction Broadcast Loop
# ==========================================================
@dp.message(F.text == TEXT_PREDICT)
async def btn_ai_prediction_toggle(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("အရင်ဆုံး Login ဝင်ပေးပါ။")
    is_enabled = active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    await message.answer("AI Prediction Broadcast", reply_markup=get_ai_prediction_toggle_keyboard(is_enabled))

@dp.callback_query(F.data == "toggle_aipred")
async def process_toggle_aipred(callback: types.CallbackQuery):
    user_tg_id = callback.from_user.id
    if user_tg_id not in active_sessions: return await callback.answer("Session Expired.", show_alert=True)
    new_state = not active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    active_sessions[user_tg_id]["is_ai_prediction_enabled"] = new_state
    
    await callback.message.edit_reply_markup(reply_markup=get_ai_prediction_toggle_keyboard(new_state))
    if new_state:
        await callback.answer("AI Prediction ပြသခြင်းကို ဖွင့်လိုက်ပါပြီ။", show_alert=True)
        asyncio.create_task(prediction_broadcast_loop(user_tg_id, callback.message))
    else:
        await callback.answer("AI Prediction ပြသခြင်းကို ပိတ်လိုက်ပါပြီ။", show_alert=True)

async def prediction_broadcast_loop(user_tg_id, message: types.Message):
    api_error_count = 0
    if "current_win_streak" not in active_sessions.get(user_tg_id, {}):
        active_sessions[user_tg_id].update({"current_win_streak": 0, "current_lose_streak": 0, "longest_win_streak": 0, "longest_lose_streak": 0})

    while active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False):
        try:
            predicted_bet, confidence, current_issue, ai_name = await get_ai_prediction(user_tg_id)
            if predicted_bet == "wait":
                await asyncio.sleep(2)
                continue

            last_issue = active_sessions[user_tg_id].get("last_predicted_issue")

            if current_issue and current_issue != last_issue:
                active_sessions[user_tg_id]["last_predicted_issue"] = current_issue
                long_w, long_l = active_sessions[user_tg_id]["longest_win_streak"], active_sessions[user_tg_id]["longest_lose_streak"]
                
                # --------------------------------------------------
                # 🚀 (၁) ခန့်မှန်းချက်ကို အရင်ဆုံးထုတ်ပြီး Channel ကို ချက်ချင်း ကြိုပို့ထားမည်
                # --------------------------------------------------
                initial_pred_text = (
                    "<blockquote>"
                    f"{P_1} Ai Prediction - Live\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"{P_2} WINGO_30S : <code>{current_issue}</code>\n"
                    f"{P_3} Prediction : <b>{predicted_bet.upper()}</b> "
                    f"〔 {long_w} 〕|〔 {long_l} 〕\n"
                    f"{P_4} Status : Waiting for result..."
                    "</blockquote>"
                )
                
                # ပုံမှန် User ဆီကို ပို့ခြင်း
                pred_msg = await message.answer(initial_pred_text)
                
                # Upload Channel ဖွင့်ထားပါက Channel ကိုပါ ခန့်မှန်းချက် ချက်ချင်း ကြိုပို့ခြင်း
                channel_msg_id = None
                if active_sessions[user_tg_id].get("upload_channel", False) and CHANNEL_ID:
                    try:
                        channel_msg = await bot.send_message(chat_id=CHANNEL_ID, text=initial_pred_text)
                        channel_msg_id = channel_msg.message_id
                    except Exception as e:
                        print(f"Channel Send Error: {e}")

                # --------------------------------------------------
                # 🔄 Result ထွက်အောင် စောင့်ခြင်း
                # --------------------------------------------------
                actual_result = "? | ?"
                for _ in range(20):
                    if not active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False): break
                    await asyncio.sleep(2)
                    actual_result = await get_latest_game_result(current_issue, user_tg_id)
                    if actual_result != "? | ?": break
                
                if actual_result != "? | ?":
                    if predicted_bet.lower() == actual_result.split(" | ")[1].strip().lower():
                        status_text = f"{P_5}WIN{actual_result}"
                        active_sessions[user_tg_id]["current_win_streak"] += 1
                        active_sessions[user_tg_id]["current_lose_streak"] = 0
                        active_sessions[user_tg_id]["longest_win_streak"] = max(active_sessions[user_tg_id]["longest_win_streak"], active_sessions[user_tg_id]["current_win_streak"])
                    else:
                        status_text = f"{P_6} LOSE{actual_result}"
                        active_sessions[user_tg_id]["current_lose_streak"] += 1
                        active_sessions[user_tg_id]["current_win_streak"] = 0
                        active_sessions[user_tg_id]["longest_lose_streak"] = max(active_sessions[user_tg_id]["longest_lose_streak"], active_sessions[user_tg_id]["current_lose_streak"])
                else:
                    status_text = "⚖️ <b>DRAW (Timeout)</b>"
                  
                long_w, long_l = active_sessions[user_tg_id]["longest_win_streak"], active_sessions[user_tg_id]["longest_lose_streak"]
                
                # --------------------------------------------------
                # 🚀 (၂) ရလဒ်ထွက်လာတဲ့အခါ စာကို Edit သွားလုပ်ခြင်း
                # --------------------------------------------------
                try:
                    final_pred_text = (
                        "<blockquote>"
                        f"{P_1} Ai Prediction - Live\n"
                        "━━━━━━━━━━━━━━━\n"
                        f"{P_2} WINGO_30S : <code>{current_issue}</code>\n"
                        f"{P_3} Prediction : <b>{predicted_bet.upper()}</b> "
                        f"〔 {long_w} 〕|〔 {long_l} 〕\n"
                        f"{P_4} Status : {status_text}"
                        "</blockquote>"
                    )
                    
                    # User ဆီကစာကို Edit လုပ်ခြင်း
                    await pred_msg.edit_text(final_pred_text)
                    
                    # Upload Channel ဖွင့်ထားပါက Channel မှာ ကြိုပို့ထားတဲ့စာကိုပါ အလိုအလျောက် Edit သွားလုပ်ခြင်း
                    if channel_msg_id and active_sessions[user_tg_id].get("upload_channel", False) and CHANNEL_ID:
                        try:
                            await bot.edit_message_text(chat_id=CHANNEL_ID, message_id=channel_msg_id, text=final_pred_text)
                        except Exception as e:
                            print(f"Channel Edit Error: {e}")
                            
                except: pass
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(2)
        except Exception: 
            await asyncio.sleep(5)

# ==========================================================
# 🌟 Premium Emojis Variables
#===========================================================
E_SETTING = '<tg-emoji emoji-id="5877260593903177342">⚙️</tg-emoji>'
E_CROWN   = '<tg-emoji emoji-id="5807868868886009920">👑</tg-emoji>'
E_LOSS    = '<tg-emoji emoji-id="5807461353799030682">💸</tg-emoji>'
E_GRID    = '<tg-emoji emoji-id="5884290437459480896">🔠</tg-emoji>'
E_EDIT    = '<tg-emoji emoji-id="5985774024968379294">📝</tg-emoji>'
E_DOC     = '<tg-emoji emoji-id="5956561916573782596">📄</tg-emoji>'
E_FLOWER  = '<tg-emoji emoji-id="5967574255670399788">🌸</tg-emoji>'

# ==========================================================
# 🔄 Continuous Auto Bet Loop Task 
# ==========================================================
async def auto_bet_loop(user_tg_id, message: types.Message):
    await message.answer("🚀 Auto-Betting စတင်ပါပြီ! ရပ်တန့်ရန် 🛑 Stop Auto-Bet ကို နှိပ်ပါ။")
    last_betted_issue = None
    api_error_count = 0 
    
    session = active_sessions[user_tg_id]
    is_virtual = session.get("is_virtual_mode", False)
    
    if not is_virtual:
        site = session["site"]
        token = session["token"]
        config = SITE_CONFIGS.get(site)
        balance_url = f"{config['api_url']}/GetBalance"
        bal_headers = get_headers(site, token)

    while active_sessions.get(user_tg_id, {}).get("is_auto_betting", False):
        try:
            predicted_bet, confidence, current_issue, ai_name = await get_ai_prediction(user_tg_id)

            if current_issue:
                api_error_count = 0 
                if current_issue != last_betted_issue:
                    
                    if predicted_bet == "wait":
                        msg = await message.answer(
                             "<blockquote>"
                             f"{E_DOC} <b>Pattern Trigger စောင့်ကြည့်နေပါသည်...</b>\n"
                             f"{E_DOC} WINGO_30S : <code>{current_issue}</code>\n"
                             f"{E_FLOWER} Status : ဆန့်ကျင်ဘက်ရလဒ် ထွက်ရန်စောင့်ဆိုင်းနေပါသည်"
                             "</blockquote>"
                        )
                        last_betted_issue = current_issue
                        asyncio.create_task(delete_message_later(msg, 7))
                        await asyncio.sleep(2)
                        continue 
                    
                    hit_wait = session.get("hit_wait", 0)
                    current_misses = session.get("current_misses", 0)
                    
                    if hit_wait > 0 and current_misses < hit_wait:
                        msg = await message.answer(
                             "<blockquote>"
                             f"{E_DOC} <b>Hit Waiting: {current_misses}/{hit_wait}</b>\n"
                             f"{E_DOC} WINGO_30S : <code>{current_issue}</code>\n"
                             f"{E_FLOWER} Pred : <b>{predicted_bet.upper()}</b> (စောင့်ကြည့်နေပါသည်)"
                             "</blockquote>"
                        )
                        
                        actual_result = "? | ?"
                        for _ in range(20):
                            if not active_sessions.get(user_tg_id, {}).get("is_auto_betting", False): break
                            await asyncio.sleep(2)
                            actual_result = await get_latest_game_result(current_issue, user_tg_id)
                            if actual_result != "? | ?": break
                                
                        try:
                            actual_size = actual_result.split(" | ")[1].strip().lower()
                            if predicted_bet.lower() == actual_size:
                                active_sessions[user_tg_id]["current_misses"] = 0 
                                await msg.edit_text(f"🔄 <b>Hit Reset:</b> AI အမှန်ခန့်မှန်းသွားသဖြင့် အစမှပြန်စောင့်ပါမည်။\nResult: {actual_result}")
                            elif actual_size != "?":
                                active_sessions[user_tg_id]["current_misses"] += 1 
                                new_miss = active_sessions[user_tg_id]["current_misses"]
                                if new_miss >= hit_wait:
                                    await msg.edit_text(f"🎯 <b>Target Reached!</b> {hit_wait} ပွဲဆက်တိုက်လွဲသွားသဖြင့် နောက်ပွဲမှစတင်လောင်းပါမည်။\nResult: {actual_result}")
                                else:
                                    await msg.edit_text(f"❌ <b>Virtual Loss:</b> {new_miss}/{hit_wait} ပွဲလွဲသွားပါပြီ။\nResult: {actual_result}")
                            asyncio.create_task(delete_message_later(msg, 5)) 
                        except Exception: pass
                        last_betted_issue = current_issue
                        await asyncio.sleep(2)
                        continue 

                    sequence = session.get("bet_sequence", [10])
                    step = session.get("current_bet_step", 0)
                    if step >= len(sequence): step = 0
                    current_amount = sequence[step]

                    if is_virtual:
                        current_bal_val = session.get("virtual_balance", 0.0)
                    else:
                        current_bal_val = 0.0
                        async with aiohttp.ClientSession() as http_session:
                            async with http_session.post(balance_url, headers=bal_headers, json=get_signed_payload({'language': 7})) as resp:
                                bal_res = await resp.json()
                                if bal_res.get("code") == 0:
                                    data_field = bal_res.get("data")
                                    if isinstance(data_field, dict):
                                        current_bal_val = float(data_field.get("balance", data_field.get("amount", 0.0)))
                                    else:
                                        current_bal_val = float(data_field)
                    
                    if current_bal_val < current_amount:
                        await message.answer(f"⚠️ <b>လက်ကျန်ငွေ မလုံလောက်တော့ပါ။</b>\nလိုအပ်သောငွေ: {current_amount} Ks\nလက်ကျန်: {current_bal_val:,.2f} Ks\n🛑 Auto Bet ကို ရပ်နားလိုက်ပါသည်။")
                        active_sessions[user_tg_id]["is_auto_betting"] = False
                        break

                    await message.answer(
                        "<blockquote>"
                        f"{E_DOC} WINGO_30S : <code>{current_issue}</code>\n"
                        f"{E_DOC} Series : {ai_name}\n"
                        f"{E_FLOWER} Pred : <b>{predicted_bet.upper()}</b> | {current_amount} Ks"
                        "</blockquote>"
                    )

                    last_betted_issue = current_issue
                    await asyncio.sleep(7) 

                    if is_virtual:
                        actual_result = await get_latest_game_result(current_issue, user_tg_id)
                        if actual_result == "? | ?":
                            simulated_num = random.randint(0, 9)
                            simulated_size = "BIG" if simulated_num >= 5 else "SMALL"
                            actual_result = f"{simulated_num} | {simulated_size}"
                    else:
                        success = await place_auto_bet(user_tg_id, current_issue, predicted_bet, current_amount, silent=True)
                        if not success:
                            await asyncio.sleep(5)
                            continue
                    
                    if not is_virtual:
                        actual_result = "? | ?"
                        for _ in range(20): 
                            if not active_sessions.get(user_tg_id, {}).get("is_auto_betting", False): break 
                            await asyncio.sleep(2)
                            actual_result = await get_latest_game_result(current_issue, user_tg_id)
                            if actual_result != "? | ?": break 
                    
                    if is_virtual:
                        new_bal_val = session.get("virtual_balance", 0.0)
                        try:
                            actual_size = actual_result.split(" | ")[1].strip().lower()
                            if predicted_bet.lower() == actual_size:
                                profit_amount = current_amount * 0.96
                                session["virtual_balance"] += profit_amount
                                session["virtual_session_profit"] += profit_amount
                            else:
                                session["virtual_balance"] -= current_amount
                                session["virtual_session_profit"] -= current_amount
                            new_bal_val = session["virtual_balance"]
                            await db.update_virtual_balance(user_tg_id, new_bal_val)
                        except Exception:
                            pass
                    else:
                        new_bal_val = 0.0
                        async with aiohttp.ClientSession() as http_session:
                            async with http_session.post(balance_url, headers=bal_headers, json=get_signed_payload({'language': 7})) as resp:
                                bal_res = await resp.json()
                                if bal_res.get("code") == 0:
                                    data_field = bal_res.get("data")
                                    if isinstance(data_field, dict):
                                        new_bal_val = float(data_field.get("balance", data_field.get("amount", 0.0)))
                                    else:
                                        new_bal_val = float(data_field)

                    try:
                        actual_size = actual_result.split(" | ")[1].strip().lower() 
                        
                        if predicted_bet.lower() == actual_size:
                            profit_amount = current_amount * 0.96
                            status_title = f"{E_SETTING} <b>WIN</b> {E_CROWN} +{profit_amount:.2f} Ks"
                            if is_virtual:
                                session["virtual_session_profit"] += profit_amount
                            else:
                                active_sessions[user_tg_id]["session_profit"] += profit_amount
                            active_sessions[user_tg_id]["current_bet_step"] = 0 
                            active_sessions[user_tg_id]["current_misses"] = 0 
                        elif actual_size == "?": 
                            status_title = f"⚙️ <b>DRAW</b> (Pending)"
                        else:
                            status_title = f"{E_SETTING} <b>LOSE</b> {E_LOSS} {current_amount:.2f} Ks"
                            if is_virtual:
                                session["virtual_session_profit"] -= current_amount
                            else:
                                active_sessions[user_tg_id]["session_profit"] -= current_amount
                            active_sessions[user_tg_id]["current_bet_step"] = (step + 1) % len(sequence)

                        if ai_name == "Set Pattern" and actual_size != "?":
                            pat = active_sessions[user_tg_id].get("custom_pattern", ["BIG"])
                            current_c_step = active_sessions[user_tg_id].get("custom_pattern_step", 0)
                            active_sessions[user_tg_id]["custom_pattern_step"] = (current_c_step + 1) % len(pat)
                            
                        if is_virtual:
                            current_profit = session.get("virtual_session_profit", 0.0)
                        else:
                            current_profit = active_sessions[user_tg_id].get("session_profit", 0.0)
                        profit_display = f"+{current_profit:,.2f} Ks" if current_profit > 0 else f"{current_profit:,.2f} Ks"
                        
                        await message.answer(
                            "<blockquote>"
                            f"{status_title}\n"
                            "───────────────\n"
                            f"{E_GRID} WINGO_30S : <code>{current_issue}</code>\n"
                            f"{E_GRID} Result : <code>{actual_result}</code>\n"
                            f"{E_EDIT} Balance : K{new_bal_val:,.2f}\n"
                            f"{E_EDIT} Total Profit : {profit_display}"
                            "</blockquote>"
                        )

                        if not is_virtual:
                            await db.update_user_balance(user_tg_id, f"{new_bal_val:.2f} Ks")
                        
                        profit_target = active_sessions[user_tg_id].get("profit_target", 0)
                        if profit_target > 0 and current_profit >= profit_target:
                            await message.answer(f"🎉 <b>Target ပြည့်သွားပါပြီ! ({profit_display})</b>\nAuto Bet ကို အလိုအလျောက် ရပ်နားလိုက်ပါသည်။")
                            active_sessions[user_tg_id]["is_auto_betting"] = False
                            break
                    except Exception: pass
                else: 
                    await asyncio.sleep(2) 
            else:
                api_error_count += 1
                if api_error_count == 3: await message.answer("⚠️ <b>API အမှားအယွင်း:</b> ပွဲစဉ်အချက်အလက်များကို ယူ၍မရပါ။")
                await asyncio.sleep(5) 
        except Exception as e:
            print(f"Auto Loop Error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🎯 Feature Handlers (Hit, Profit, AI Mode, BetSize, Upload Channel)
# ==========================================================
@dp.message(F.text == TEXT_UPLOAD_CHANNEL)
async def cmd_upload_channel_menu(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    
    current_status = active_sessions[user_tg_id].get("upload_channel", False)
    status_text = "ဖွင့်ထားပါသည် (ON) 🟢" if current_status else "ပိတ်ထားပါသည် (OFF) 🔴"
    
    await message.answer(
        f"📡 <b>Upload Channel Setting</b>\n\n"
        f"လက်ရှိအခြေအနေ: <b>{status_text}</b>\n\n"
        f"အောက်ပါခလုတ်များဖြင့် Channel သို့ Prediction ရလဒ်များ ပို့/မပို့ သတ်မှတ်နိုင်ပါသည်။", 
        reply_markup=get_upload_toggle_keyboard()
    )

@dp.message(F.text.in_(["✅ Upload ON", "❌ Upload OFF"]))
async def cmd_toggle_upload(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")

    is_on = message.text == "✅ Upload ON"
    active_sessions[user_tg_id]["upload_channel"] = is_on

    state_str = "ON ဖွင့်" if is_on else "OFF ပိတ်"
    await message.answer(f"✅ Upload Channel စနစ်ကို <b>{state_str}</b> လိုက်ပါပြီ။", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_HIT)
async def btn_hit_betting(message: types.Message):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    current_wait = active_sessions[message.from_user.id].get("hit_wait", 0)
    await message.answer("🎯 <b>Hit Betting System</b>", reply_markup=get_hit_betting_inline_keyboard(current_wait))

@dp.callback_query(F.data.startswith("hitbet_"))
async def process_hit_bet(callback: types.CallbackQuery):
    user_tg_id = callback.from_user.id
    wait_count = int(callback.data.split("_")[1])
    if user_tg_id in active_sessions:
        active_sessions[user_tg_id]["hit_wait"] = wait_count
        active_sessions[user_tg_id]["current_misses"] = 0 
    await callback.message.edit_reply_markup(reply_markup=get_hit_betting_inline_keyboard(wait_count))

@dp.message(F.text == TEXT_PROFIT)
async def btn_set_profit_target(message: types.Message, state: FSMContext):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    current_target = active_sessions[message.from_user.id].get("profit_target", 0)
    await state.set_state(LoginForm.enter_profit_target)
    await message.answer(f"🎯 <b>Auto Bet အမြတ် (Profit Target) ကို သတ်မှတ်ပါ။</b>\nလက်ရှိ Target: <b>{current_target} Ks</b>", reply_markup=get_cancel_keyboard())

@dp.message(LoginForm.enter_profit_target)
async def process_profit_target(message: types.Message, state: FSMContext):
    if message.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ မပြောင်းလဲတော့ပါ။", reply_markup=get_logged_in_keyboard())
    if not message.text.isdigit(): return await message.answer("❌ ဂဏန်းသာ ရိုက်ထည့်ပါ။")
    active_sessions[message.from_user.id]["profit_target"] = int(message.text)
    await state.set_state(LoginForm.main_menu)
    await message.answer(f"✅ <b>Profit Target:</b> {message.text} Ks", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_AI)
async def cmd_ai_mode(message: types.Message):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    current_mode = active_sessions[message.from_user.id].get("ai_mode", "🎯 Pattern AI")
    await message.answer(f"🤖 <b>AI Mode:</b> {current_mode}", reply_markup=get_ai_mode_keyboard())

@dp.message(F.text.in_(VALID_AI_NAMES))
async def set_ai_mode(message: types.Message, state: FSMContext):
    if message.text == "Set Pattern":
        await state.set_state(LoginForm.enter_custom_pattern)
        return await message.answer("🛠️ <b>Custom Pattern သတ်မှတ်ရန်:</b>\n\nB (အကြီး) နှင့် S (အသေး) ကိုသာ အသုံးပြု၍ စာလုံးဆက်တိုက်ရိုက်ပါ။\nဥပမာ: <code>BSBS</code> သို့မဟုတ် <code>BBSS</code>", reply_markup=get_cancel_keyboard())

    active_sessions[message.from_user.id]["ai_mode"] = message.text
    await db.update_user_ai_mode(message.from_user.id, message.text)
    await message.answer(f"✅ AI စနစ်ကို <b>{message.text}</b> သို့ ပြောင်းလဲလိုက်ပါပြီ။", reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.enter_custom_pattern)
async def process_custom_pattern(message: types.Message, state: FSMContext):
    if message.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ မပြောင်းလဲတော့ပါ။", reply_markup=get_logged_in_keyboard())

    raw_pattern = message.text.upper().replace(" ", "")
    if not all(c in ['B', 'S'] for c in raw_pattern) or len(raw_pattern) == 0:
        return await message.answer("❌ မှားယွင်းနေပါသည်။ B နှင့် S ကိုသာ အသုံးပြုပါ။ (ဥပမာ: BSBS)")

    pattern_list = ["BIG" if c == 'B' else "SMALL" for c in raw_pattern]
    user_tg_id = message.from_user.id

    if user_tg_id in active_sessions:
        active_sessions[user_tg_id]["custom_pattern"] = pattern_list
        active_sessions[user_tg_id]["custom_pattern_step"] = 0
        active_sessions[user_tg_id]["ai_mode"] = "Set Pattern"

    await db.update_user_ai_mode(user_tg_id, "Set Pattern")
    await state.set_state(LoginForm.main_menu)

    trigger = "SMALL" if pattern_list[0] == "BIG" else "BIG"
    
    await message.answer(f"✅ <b>Pattern သတ်မှတ်ပြီးပါပြီ:</b> <code>{raw_pattern}</code>\n\n🎯 <b>မှတ်ချက်:</b> အပြင်ရလဒ် <b>{trigger}</b> ထွက်ပေါ်ပြီးမှသာ ပထမဆုံးအကွက် ({pattern_list[0]}) ကို စတင်လောင်းပါမည်။", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == "BACK")
async def back_to_main(message: types.Message):
    await message.answer("ပင်မမီနူးသို့ ရောက်ရှိပါပြီ။", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_BETSIZE)
async def btn_set_betsize(message: types.Message, state: FSMContext):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    seq_str = "-".join(map(str, active_sessions[message.from_user.id].get("bet_sequence", [10])))
    await state.set_state(LoginForm.enter_bet_sequence)
    await message.answer(f"⚙️ <b>Auto Bet လောင်းကြေး (Bet Size) ကို သတ်မှတ်ပါ။</b>\nလက်ရှိ: <code>{seq_str}</code>\nFormat: 10-20-40-80", reply_markup=get_cancel_keyboard())

@dp.message(LoginForm.enter_bet_sequence)
async def process_bet_sequence(message: types.Message, state: FSMContext):
    if message.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ မပြောင်းလဲတော့ပါ။", reply_markup=get_logged_in_keyboard())
    try:
        sequence = [int(x.strip()) for x in message.text.split('-')]
        if not sequence or any(x <= 0 for x in sequence): raise ValueError
        active_sessions[message.from_user.id]["bet_sequence"] = sequence
        active_sessions[message.from_user.id]["current_bet_step"] = 0 
        await state.set_state(LoginForm.main_menu)
        await message.answer(f"✅ <b>Bet Size သတ်မှတ်ပြီးပါပြီ:</b> <code>{'-'.join(map(str, sequence))}</code>", reply_markup=get_logged_in_keyboard())
    except:
        await message.answer("❌ မှားယွင်းနေပါသည်။ ဥပမာ: 10-20-40-80 ဟုသာ တုံးတို (-) ခြား၍ ရိုက်ပါ။")

# ==========================================================
# 🤖 Reply Keyboard Auto Bet & Status Handlers
# ==========================================================
@dp.message(F.text == TEXT_START)
async def btn_start_auto(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    if active_sessions[user_tg_id].get("is_auto_betting", False): return await message.answer("⚠️ Auto Bet အလုပ်လုပ်နေဆဲ ဖြစ်ပါသည်။")

    if "bet_sequence" not in active_sessions[user_tg_id]:
        active_sessions[user_tg_id]["bet_sequence"] = [10]
        active_sessions[user_tg_id]["current_bet_step"] = 0

    active_sessions[user_tg_id]["is_auto_betting"] = True
    asyncio.create_task(auto_bet_loop(user_tg_id, message))

@dp.message(F.text == TEXT_STOP)
async def btn_stop_auto(message: types.Message):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    active_sessions[message.from_user.id]["is_auto_betting"] = False
    await message.answer("🛑 <b>ဆက်တိုက် Auto Bet စနစ်ကို ရပ်တန့်လိုက်ပါပြီ။</b>")

@dp.message(F.text == TEXT_STATUS)
async def btn_status(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")

    session = active_sessions[user_tg_id]
    is_auto = "Running 🟢" if session.get("is_auto_betting") else "Stopped 🔴"
    is_virtual = session.get("is_virtual_mode", False)
    current_seq = session.get("bet_sequence", [10])
    current_step = session.get("current_bet_step", 0)
    
    if is_virtual:
        profit = session.get("virtual_session_profit", 0.0)
        balance = session.get("virtual_balance", 0.0)
    else:
        profit = session.get("session_profit", 0.0)
        balance = session.get("start_balance", 0.0)
    
    profit_str = f"+{profit:g} Ks" if profit >= 0 else f"{profit:g} Ks"

    status_text = (
        "📊 <b>Bot Status</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Active Site:</b> {session.get('site')}\n"
        f"🕹️ <b>Mode:</b> {'Virtual' if is_virtual else 'Real'}\n"
        f"🤖 <b>Auto-Bet State:</b> {is_auto}\n"
        f"🧠 <b>Active AI Mode:</b> {session.get('ai_mode')}\n"
        f"⚙️ <b>Bet Sequence:</b> <code>{'-'.join(map(str, current_seq))}</code>\n"
        f"📍 <b>Current Step:</b> {current_step + 1}/{len(current_seq)} ({current_seq[current_step]} Ks)\n"
        f"🎯 <b>Profit Target:</b> {session.get('profit_target', 0)} Ks\n"
        f"💰 <b>Balance:</b> {balance:,.2f} Ks\n"
        f"📈 <b>Total Profit:</b> {profit_str}\n"
    )
    await message.answer(status_text)

# ==========================================================
# 💰 Check Balance & Other Handlers
# ==========================================================
@dp.message(LoginForm.main_menu, F.text == TEXT_BALANCE)
async def check_balance(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
        
    loading_msg = await message.answer("🔄 <b>လက်ကျန်ငွေ (Balance) ကို စစ်ဆေးနေပါသည်...</b>")
    session = active_sessions[user_tg_id]
    is_virtual = session.get("is_virtual_mode", False)
    
    try:
        if is_virtual:
            balance_val = session.get("virtual_balance", 0.0)
            balance_text = f"{balance_val:,.2f} Ks"
        else:
            config = SITE_CONFIGS.get(session["site"])
            balance_url = f"{config['api_url']}/GetBalance"
            
            signed_bal_payload = get_signed_payload({'language': 7})
            bal_headers = get_headers(session["site"], session["token"])
            
            balance_text = "0.00 Ks"
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(balance_url, headers=bal_headers, json=signed_bal_payload) as resp:
                    bal_res = await resp.json()
                    if bal_res.get("code") == 0:
                        data_field = bal_res.get("data")
                        if isinstance(data_field, dict):
                            balance_val = data_field.get("balance", data_field.get("amount", 0.0))
                        else:
                            balance_val = data_field
                            
                        balance_text = f"{float(balance_val):.2f} Ks"

        await state.update_data(balance=balance_text)
        if not is_virtual:
            await db.update_user_balance(user_tg_id, balance_text)

        await loading_msg.delete()
        await message.answer(f"💰 <b>သင့်ရဲ့ လက်ရှိ လက်ကျန်ငွေ:</b> {balance_text}", reply_markup=get_logged_in_keyboard())
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"⚠️ <b>Error:</b> Balance စစ်ဆေးရာတွင် အခက်အခဲရှိနေပါသည်။", reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_INFO)
async def show_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    site_name = active_sessions.get(message.from_user.id, {}).get("site", "Unknown")
    expire_iso = await db.get_user_subscription(message.from_user.id)
    expire_str = datetime.fromisoformat(expire_iso).strftime('%Y-%m-%d %I:%M %p') if expire_iso else "N/A"

    info_text = (
        "👤 <b>User Information:</b>\n"
        f"├─ 🌐 <b>Site:</b> {site_name}\n"
        f"├─ 🆔 <b>User ID:</b> {data.get('user_id', 'N/A')}\n"
        f"├─ 📱 <b>Username:</b> {data.get('username', 'N/A')}\n"
        f"├─ 🏷️ <b>Nickname:</b> {data.get('nickname', 'Unknown')}\n"
        f"├─ 💰 <b>Balance:</b> {data.get('balance', '0.00 Ks')}\n"
        f"├─ 📅 <b>Login Date:</b> {data.get('login_time', get_myanmar_time().strftime('%Y-%m-%d %H:%M:%S'))}\n"
        f"├─ 🔑 <b>Expire On:</b> {expire_str} (MMT)\n"
        "└─ ✅ <b>Allow Withdraw:</b> Yes\n"
    )
    await message.answer(info_text, reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_LOGOUT)
async def logout(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id in active_sessions:
        del active_sessions[user_tg_id]
    await state.clear()
    await message.answer("👋 အကောင့်ထွက်ပြီးပါပြီ။", reply_markup=get_main_keyboard())


@dp.message(F.text == "Pro AI Features")
async def cmd_pro_ai_menu(message: types.Message):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    
    text = (
        "Pro AI Features (Advanced Machine Learning)\n"
        "━━━━━━━━━━━━━━━\n"
        "အောက်ပါ အဆင့်မြင့် AI/ML Algorithm များကို သင်စိတ်ကြိုက် ရွေးချယ်အသုံးပြုနိုင်ပါသည်။\n\n"
        "<i>(မှတ်ချက် - ထွက်ပေါ်ခဲ့သော Pattern များကို သင်္ချာသီအိုရီများဖြင့် တွက်ချက်ထားခြင်းဖြစ်ပါသည်။)</i>"
    )
    await message.answer(text, reply_markup=get_pro_ai_mode_keyboard())

@dp.message(F.text == "BACK")
async def cmd_back_to_ai_menu(message: types.Message):
    if message.from_user.id not in active_sessions: return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    await message.answer("AI Mode ရွေးချယ်ရန်", reply_markup=get_ai_mode_keyboard())

@dp.message(F.text == TEXT_GAMES)
async def games(message: types.Message):
    await message.answer("🎮 <b>Game ရွေးချယ်ရန်:</b>\nWin Go 30s ကို ရွေးချယ်ထားပါသည်။", reply_markup=get_main_keyboard())

# ==========================================================
# 🧪 Virtual Mode Handlers (NEW)
# ==========================================================
@dp.message(F.text == TEXT_VIRTUAL_MODE)
async def cmd_virtual_mode(message: types.Message, state: FSMContext):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("Login ဝင်ပေးပါ။")
    
    if active_sessions[user_tg_id].get("is_virtual_mode", False):
        await message.answer("✅ သင်သည် Virtual Mode တွင် ရှိနေပြီးဖြစ်ပါသည်။", reply_markup=get_logged_in_keyboard())
        return
    
    await state.set_state(LoginForm.enter_virtual_balance)
    await message.answer(
        "🧪 <b>Virtual Mode ကို စတင်ရန်</b>\n\n"
        "သင်စမ်းသပ်လိုသော Virtual Balance ကို ရိုက်ထည့်ပါ။\n"
        "ဥပမာ: <code>10000</code> (10,000 Ks)\n\n"
        "<i>Virtual Mode တွင် API မှ ရလဒ်များကို အသုံးပြု၍ စမ်းသပ်နိုင်ပြီး၊\n"
        "အမှန်တကယ် ငွေကြေးများ ထိခိုက်မှုမရှိပါ။</i>",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(LoginForm.enter_virtual_balance)
async def process_virtual_balance(message: types.Message, state: FSMContext):
    if message.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        return await message.answer("❌ Virtual Mode ကို မစတင်တော့ပါ။", reply_markup=get_logged_in_keyboard())
    
    try:
        virtual_balance = float(message.text.replace(",", ""))
        if virtual_balance <= 0:
            raise ValueError
        
        user_tg_id = message.from_user.id
        session = active_sessions[user_tg_id]
        
        session["is_virtual_mode"] = True
        session["virtual_balance"] = virtual_balance
        session["virtual_session_profit"] = 0.0
        session["start_balance"] = virtual_balance
        
        await db.set_virtual_balance(user_tg_id, virtual_balance)
        
        await state.set_state(LoginForm.main_menu)
        await message.answer(
            f"🧪 <b>Virtual Mode စတင်ပြီးပါပြီ!</b>\n\n"
            f"💰 Virtual Balance: <b>{virtual_balance:,.2f} Ks</b>\n"
            f"📊 AI Prediction များကို အသုံးပြု၍ စမ်းသပ်နိုင်ပါသည်။\n\n"
            f"<i>Real Mode သို့ ပြန်သွားရန် 'Real Mode' ကို နှိပ်ပါ။</i>",
            reply_markup=get_logged_in_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ မှန်ကန်သော ဂဏန်းတစ်ခုကို ရိုက်ထည့်ပါ။\nဥပမာ: <code>10000</code>", reply_markup=get_cancel_keyboard())

@dp.message(F.text == TEXT_REAL_MODE)
async def cmd_real_mode(message: types.Message):
    user_tg_id = message.from_user.id
    if user_tg_id not in active_sessions:
        return await message.answer("⚠️ Login ဝင်ပေးပါ။")
    
    if not active_sessions[user_tg_id].get("is_virtual_mode", False):
        await message.answer("✅ သင်သည် Real Mode တွင် ရှိနေပြီးဖြစ်ပါသည်။", reply_markup=get_logged_in_keyboard())
        return
    
    active_sessions[user_tg_id]["is_virtual_mode"] = False
    active_sessions[user_tg_id]["session_profit"] = 0.0
    active_sessions[user_tg_id]["start_balance"] = extract_balance(active_sessions[user_tg_id].get("balance", "0.00 Ks"))
    
    await message.answer(
        "🔴 <b>Real Mode သို့ ပြန်လည်ရောက်ရှိပါပြီ။</b>\n\n"
        "အမှန်တကယ် ငွေကြေးဖြင့် ကစားနိုင်ပါသည်။\n"
        "<i>Virtual Mode သို့ ပြန်သွားရန် 'Virtual Mode' ကို နှိပ်ပါ။</i>",
        reply_markup=get_logged_in_keyboard()
    )

# ==========================================================
# 🚀 Main Bot Loop
# ==========================================================
async def main():
    print("🚀 Auto-Bet (API Edition) Bot စတင်နေပါပြီ...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
