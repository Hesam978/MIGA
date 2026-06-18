# ╔══════════════════════════════════════════════════════════════╗
# ║   Config Collector Bot — v5.0 FULL                           ║
# ║   ✅ کانفیگ رایگان (ویژه/انبوه/ذخیره)                      ║
# ║   ✅ فیلتر کشور هوشمند | اشتراک هوشمند                     ║
# ║   ✅ حذف تکراری + نمایش آمار پردازش                        ║
# ║   ✅ گزارش خودکار ۳ ساعته به ادمین                         ║
# ║   ✅ همه ویژگی‌های قبلی حفظ شده                             ║
# ╚══════════════════════════════════════════════════════════════╝

# ══════════════════════════════════════════════
#  SECTION 1 — Imports & Logging
# ══════════════════════════════════════════════
import os, re, json, asyncio, aiohttp, base64, random
import logging, threading, time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO
from logging.handlers import RotatingFileHandler
from flask import Flask, Response, request, render_template_string, redirect, url_for, jsonify

import nest_asyncio
nest_asyncio.apply()

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
import pytz

LOG_FILE = "bot.log"
_fh = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if not logger.handlers:
    _sh = logging.StreamHandler()
    _sh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(_sh)
    logger.addHandler(_fh)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ══════════════════════════════════════════════
#  SECTION 2 — Env Vars + Constants + NEW MAPS
# ══════════════════════════════════════════════
TOKEN        = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN در Railway Variables تنظیم نشده!")

ADMIN_ID     = int(os.environ.get("ADMIN_ID",     "8136134031"))
CHANNEL_ID   = os.environ.get("CHANNEL_ID",        "@Configcollecter")
BOT_USERNAME = os.environ.get("BOT_USERNAME",       "@ConfigggCollectorBot")
BASE_URL     = os.environ.get("RAILWAY_STATIC_URL",
               os.environ.get("REPLIT_DOMAIN", "http://localhost:8080")).rstrip('/')
PORT         = int(os.environ.get("PORT", 8080))
AI_API_KEY   = os.environ.get("AI_API_KEY", "")
ADMIN_PASS   = os.environ.get("ADMIN_PASS",         "admin2026")
TEHRAN_TZ    = pytz.timezone('Asia/Tehran')

if not BOT_USERNAME.startswith("@"):
    BOT_USERNAME = "@" + BOT_USERNAME

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "stats":          os.path.join(DATA_DIR, "stats.json"),
    "users":          os.path.join(DATA_DIR, "users.json"),
    "groups":         os.path.join(DATA_DIR, "groups.json"),
    "settings":       os.path.join(DATA_DIR, "settings.json"),
    "sources":        os.path.join(DATA_DIR, "sources.json"),
    "referrals":      os.path.join(DATA_DIR, "referrals.json"),
    "custom_configs": os.path.join(DATA_DIR, "custom_configs.txt"),
    "vip_users":      os.path.join(DATA_DIR, "vip_users.json"),
}
LOCKS = {k: threading.Lock() for k in FILES}

DEFAULT_STATS    = {"users": 0, "total_configs_sent": 0, "total_requests": 0, "errors": 0, "daily": {}}
DEFAULT_SETTINGS = {"channel_interval": 600, "group_interval": 10800, "cache_interval": 1800}
PROTOCOLS        = ["vless", "vmess", "trojan", "ss", "hysteria2", "tuic"]
RATE_LIMIT_SECS  = 4.0
CONFIG_CACHE: Dict[str, Any] = {"configs": [], "last_update": 0}
USER_LAST_REQ: Dict[int, float] = {}
FETCH_SEMAPHORE  = asyncio.Semaphore(10)

CONFIG_PATTERN = re.compile(
    r'(vless|vmess|trojan|ss|hysteria2|tuic)://[^\s\n\r,\"\'<>]+',
    re.IGNORECASE
)

# ── منابع ویژه (⚡ سریع و گزیده) ──
SPECIAL_SOURCES = [
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub2.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub3.txt",
]

# ── نقشه کشور ──
COUNTRY_MAP: Dict[str, Tuple[str, str]] = {
    'de': ('🇩🇪', 'آلمان'),
    'nl': ('🇳🇱', 'هلند'),
    'fi': ('🇫🇮', 'فنلاند'),
    'se': ('🇸🇪', 'سوئد'),
    'fr': ('🇫🇷', 'فرانسه'),
    'gb': ('🇬🇧', 'انگلیس'),
    'at': ('🇦🇹', 'اتریش'),
    'ch': ('🇨🇭', 'سوئیس'),
    'pl': ('🇵🇱', 'لهستان'),
    'cz': ('🇨🇿', 'چک'),
    'ro': ('🇷🇴', 'رومانی'),
    'hu': ('🇭🇺', 'مجارستان'),
    'lt': ('🇱🇹', 'لیتوانی'),
    'us': ('🇺🇸', 'آمریکا'),
    'ca': ('🇨🇦', 'کانادا'),
    'jp': ('🇯🇵', 'ژاپن'),
    'sg': ('🇸🇬', 'سنگاپور'),
    'tr': ('🇹🇷', 'ترکیه'),
    'ru': ('🇷🇺', 'روسیه'),
    'ua': ('🇺🇦', 'اوکراین'),
}

# ══════════════════════════════════════════════
#  SECTION 3 — DEFAULT_SOURCES
# ══════════════════════════════════════════════
DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt",
    "https://raw.githubusercontent.com/Mosifree/-FREE2CONFIG/refs/heads/main/FRAGMENT",
    "https://raw.githubusercontent.com/ShadowException/VPN/refs/heads/main/configs/VPN-cat",
    "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub1.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub2.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub3.txt",
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha.txt",
    "https://raw.githubusercontent.com/MohammadBahemmat/V2ray-Collector/main/subscriptions/all.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix.txt",
    "https://c6et83fe1u99lr8j5w4s9iwik9565bqx.pages.dev/sub/fragment/g4lWgI*%40zehfoOEK?app=xray",
    "http://main.pythash.tr/FRkh99yBGCllN/01736620-2086-4c0b-a86e-52ebfe64dd12/",
]

# ══════════════════════════════════════════════
#  SECTION 4 — Database Functions
# ══════════════════════════════════════════════
def load_json(key: str, default: Any) -> Any:
    with LOCKS[key]:
        path = FILES[key]
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"load_json error [{key}]: {e}")
            return default

def save_json(key: str, data: Any):
    with LOCKS[key]:
        path = FILES[key]
        tmp  = path + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"save_json error [{key}]: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)

def load_custom_configs() -> List[str]:
    with LOCKS["custom_configs"]:
        p = FILES["custom_configs"]
        if not os.path.exists(p):
            return []
        with open(p, 'r', encoding='utf-8') as f:
            return [l.strip() for l in f if l.strip()]

def save_custom_configs(configs: List[str]):
    with LOCKS["custom_configs"]:
        with open(FILES["custom_configs"], 'w', encoding='utf-8') as f:
            f.write("\n".join(configs) + ("\n" if configs else ""))

def add_stat(key: str, amount: int = 1):
    stats = load_json("stats", DEFAULT_STATS)
    stats[key] = stats.get(key, 0) + amount
    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    stats.setdefault("daily", {})[today] = stats["daily"].get(today, 0) + amount
    save_json("stats", stats)

# ══════════════════════════════════════════════
#  SECTION 5 — Config Engine + Country Detection
# ══════════════════════════════════════════════
def extract_configs(text: str) -> List[str]:
    if not text:
        return []
    cleaned = text.strip()
    if len(cleaned) < 50000:
        try:
            if not any(cleaned.startswith(p + "://") for p in PROTOCOLS):
                decoded = base64.b64decode(cleaned + "==").decode('utf-8', errors='ignore')
                if any(p + "://" in decoded for p in PROTOCOLS):
                    text = decoded
        except Exception:
            pass
    matches = list(set(CONFIG_PATTERN.findall(text)))
    valid = []
    for m in matches:
        if m.startswith("vmess://"):
            try:
                b64 = m[8:]
                decoded = base64.b64decode(b64 + "==").decode()
                if '"add"' in decoded or '"host"' in decoded:
                    valid.append(m)
            except Exception:
                valid.append(m)
        else:
            valid.append(m)
    return valid

def filter_configs(configs: List[str], protocol: str) -> List[str]:
    if not protocol or protocol == "ALL":
        return configs
    return [c for c in configs if c.lower().startswith(f"{protocol.lower()}://")]

def detect_country(config_str: str) -> Optional[str]:
    """تشخیص کشور از hostname کانفیگ"""
    try:
        host = ""
        if "@" in config_str:
            host_part = config_str.split("@", 1)[1]
            host = host_part.split(":")[0].split("?")[0].split("/")[0].lower()
        elif "://" in config_str:
            rest = config_str.split("://", 1)[1]
            host = rest.split(":")[0].split("?")[0].lower()

        if not host:
            return None

        for cc in COUNTRY_MAP:
            patterns = [
                f'.{cc}.', f'-{cc}.', f'.{cc}-', f'-{cc}-',
                f'{cc}.', f'.{cc}', f'-{cc}', f'{cc}-',
            ]
            if any(p in f'.{host}.' for p in patterns):
                return cc
    except Exception:
        pass
    return None

def filter_by_country(configs: List[str], cc: str) -> List[str]:
    return [c for c in configs if detect_country(c) == cc]

def get_available_countries(configs: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in configs:
        cc = detect_country(c)
        if cc and cc in COUNTRY_MAP:
            counts[cc] = counts.get(cc, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

async def fetch_one_source(session: aiohttp.ClientSession, url: str) -> List[str]:
    async with FETCH_SEMAPHORE:
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with session.get(url, timeout=timeout, ssl=False) as resp:
                if resp.status == 200:
                    text = await resp.text(errors='ignore')
                    return extract_configs(text)
        except asyncio.TimeoutError:
            logger.debug(f"Timeout: {url[:50]}")
        except Exception as e:
            logger.debug(f"Fetch error {url[:50]}: {e}")
    return []

async def update_cache(sources: Optional[List[str]] = None):
    """آپدیت کش اصلی از منابع"""
    if sources is None:
        db = load_json("sources", {"list": DEFAULT_SOURCES})
        sources = db.get("list", DEFAULT_SOURCES)
    logger.info(f"🔄 Fetching {len(sources)} sources...")
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [fetch_one_source(session, url) for url in sources]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=60.0
                )
            except asyncio.TimeoutError:
                logger.warning("Cache update timed out after 60s")
                results = []
        all_cfgs = []
        for r in results:
            if isinstance(r, list):
                all_cfgs.extend(r)
        unique = list(set(all_cfgs))
        CONFIG_CACHE['configs']     = unique
        CONFIG_CACHE['last_update'] = time.time()
        logger.info(f"✅ Cache updated: {len(unique)} unique configs")
    except Exception as e:
        logger.error(f"update_cache error: {e}")
        add_stat("errors")

async def fetch_configs_fresh(sources: List[str]) -> List[str]:
    """دریافت کانفیگ از منابع بدون آپدیت کش اصلی"""
    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [fetch_one_source(session, url) for url in sources]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=35.0
                )
            except asyncio.TimeoutError:
                return []
        all_cfgs = []
        for r in results:
            if isinstance(r, list):
                all_cfgs.extend(r)
        return list(set(all_cfgs))
    except Exception as e:
        logger.error(f"fetch_configs_fresh error: {e}")
        return []

# ══════════════════════════════════════════════
#  SECTION 6 — User Management
# ══════════════════════════════════════════════
def get_user(user_id: int) -> dict:
    users = load_json("users", {})
    uid   = str(user_id)
    if uid not in users:
        users[uid] = {
            "is_vip":          False,
            "protocol_filter": "ALL",
            "daily_requests":  0,
            "last_reset":      datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d"),
            "bonus_limit":     0,
            "sub_token":       os.urandom(12).hex(),
            "invited_by":      None,
            "username":        "",
            "first_name":      "",
            "join_date":       datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M"),
            "total_requests":  0,
        }
        stats = load_json("stats", DEFAULT_STATS)
        stats["users"] = stats.get("users", 0) + 1
        save_json("stats", stats)
        save_json("users", users)
    u = users[uid]
    for fld, dft in [("sub_token", os.urandom(12).hex()), ("invited_by", None),
                      ("username", ""), ("first_name", ""), ("total_requests", 0),
                      ("join_date", "")]:
        if fld not in u:
            u[fld] = dft
    return u

def save_user(user_id: int, data: dict):
    users = load_json("users", {})
    users[str(user_id)] = data
    save_json("users", users)

def update_user_info(user_id: int, username: str, first_name: str):
    u = get_user(user_id)
    u["username"]   = username or ""
    u["first_name"] = first_name or ""
    save_user(user_id, u)

def check_limit(user_id: int) -> tuple:
    if user_id == ADMIN_ID:
        return True, "VIP"
    u = get_user(user_id)
    if u.get("is_vip"):
        return True, "VIP"
    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    if u.get("last_reset") != today:
        u["daily_requests"] = 0
        u["last_reset"]     = today
        save_user(user_id, u)
    total = 3 + u.get("bonus_limit", 0)
    used  = u.get("daily_requests", 0)
    if used < total:
        u["daily_requests"]  = used + 1
        u["total_requests"]  = u.get("total_requests", 0) + 1
        save_user(user_id, u)
        return True, f"{total - used - 1} درخواست باقیمانده"
    return False, (
        f"❌ سهمیه روزانه ({total} درخواست) تمام شد.\n"
        "⏳ ریست در ساعت ۰۰:۰۰\n"
        "💡 با /invite دوست دعوت کن → سهمیه بیشتر!"
    )

def is_spamming(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return False
    now = time.time()
    if now - USER_LAST_REQ.get(user_id, 0) < RATE_LIMIT_SECS:
        return True
    USER_LAST_REQ[user_id] = now
    return False

def process_referral(new_id: int, inviter_id: int):
    if new_id == inviter_id:
        return False
    u_new = get_user(new_id)
    if u_new.get("invited_by") is not None:
        return False
    refs = load_json("referrals", {})
    key  = str(inviter_id)
    refs.setdefault(key, [])
    if new_id in refs[key]:
        return False
    refs[key].append(new_id)
    save_json("referrals", refs)
    u_new["invited_by"] = inviter_id
    save_user(new_id, u_new)
    inviter = get_user(inviter_id)
    inviter["bonus_limit"] = inviter.get("bonus_limit", 0) + 1
    save_user(inviter_id, inviter)
    return True

def get_all_users_info() -> List[dict]:
    users = load_json("users", {})
    result = []
    for uid, data in users.items():
        result.append({"uid": uid, **data})
    return sorted(result, key=lambda x: x.get("total_requests", 0), reverse=True)

# ══════════════════════════════════════════════
#  SECTION 7 — AI + Ping + ✅ Send Helper با آمار پردازش
# ══════════════════════════════════════════════
def run_async_safe(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def ask_ai_async(prompt: str) -> str:
    if not AI_API_KEY:
        return "❌ کلید AI_API_KEY در Railway Variables تنظیم نشده."
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  BASE_URL,
                    "X-Title":       "Config Collector Bot"
                },
                json={
                    "model":    "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [
                        {"role": "system", "content": "پاسخ را به فارسی، کوتاه و مفید بده."},
                        {"role": "user",   "content": prompt}
                    ],
                    "max_tokens": 600
                },
                timeout=aiohttp.ClientTimeout(total=25)
            ) as resp:
                if resp.status == 200:
                    data    = await resp.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    return content or "❌ پاسخ خالی از سرور AI."
                body = await resp.text()
                logger.warning(f"AI error {resp.status}: {body[:200]}")
                return f"❌ خطای سرور AI: {resp.status}"
    except asyncio.TimeoutError:
        return "⏱ AI timeout — دوباره امتحان کنید."
    except Exception as e:
        return f"❌ خطا در ارتباط با AI: {str(e)[:80]}"

async def ping_host_async(host: str) -> str:
    clean = host.strip().replace("https://", "").replace("http://", "").split("/")[0]
    url   = f"https://{clean}"
    try:
        start = asyncio.get_event_loop().time()
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5),
                                    allow_redirects=True, ssl=False) as resp:
                ms     = int((asyncio.get_event_loop().time() - start) * 1000)
                status = "🟢 عالی" if ms < 150 else "🟠 متوسط" if ms < 300 else "🔴 ضعیف"
                return (f"🏓 پینگ: {ms}ms — {status}\n"
                        f"📡 هدف: {clean}\n🔢 کد: {resp.status}\n\n"
                        "⚠️ پینگ HTTP است، نه ICMP.")
    except asyncio.TimeoutError:
        return f"❌ Timeout — {clean} پاسخ نداد."
    except Exception as e:
        return f"❌ خطا: {str(e)[:80]}"

async def send_configs_to_msg(msg, configs: List[str], count: int = 10,
                               as_json: bool = False, prefix: str = "configs"):
    """
    ✅ FIXED: msg = telegram.Message object
    ✅ NEW: نمایش آمار حذف تکراری + خراب قبل از ارسال فایل
    """
    if not configs:
        await msg.reply_text(
            "⚠️ هیچ کانفیگی یافت نشد.\n"
            "💡 از دکمه ⚡ اسکن لحظه‌ای استفاده کنید."
        )
        return

    total_in = len(configs)

    # ── مرحله ۱: حذف تکراری ──
    seen, unique = set(), []
    for c in configs:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    dupes_removed = total_in - len(unique)

    # ── مرحله ۲: حذف خراب (اعتبارسنجی پایه) ──
    valid, invalid_count = [], 0
    for c in unique:
        if (len(c) > 20 and "://" in c and
                any(c.lower().startswith(p + "://") for p in PROTOCOLS)):
            valid.append(c)
        else:
            invalid_count += 1

    if not valid:
        await msg.reply_text("⚠️ بعد از پردازش کانفیگ معتبری یافت نشد.\n💡 منبع دیگری امتحان کنید.")
        return

    # ── مرحله ۳: انتخاب تصادفی ──
    pool = valid.copy()
    random.shuffle(pool)
    selected = pool[:count] if (count and count < len(pool)) else pool

    # ── نمایش آمار پردازش ──
    await msg.reply_text(
        "🧹 <b>پردازش و تمیزسازی</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📥 کل دریافتی:  <b>{total_in:,}</b>\n"
        f"🔄 حذف تکراری: <b>{dupes_removed:,}</b>\n"
        f"🗑️ حذف خراب:   <b>{invalid_count:,}</b>\n"
        f"✅ خروجی پاک:  <b>{len(selected):,}</b> کانفیگ\n"
        "━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

    # ── ساخت فایل ──
    rnd = random.randint(100, 999)
    if as_json:
        fname   = f"{prefix}_{len(selected)}_{rnd}.json"
        payload = json.dumps({
            "configs":   selected,
            "count":     len(selected),
            "timestamp": datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M"),
            "bot":       BOT_USERNAME,
            "stats":     {"total_in": total_in, "dupes": dupes_removed, "invalid": invalid_count}
        }, ensure_ascii=False, indent=2).encode('utf-8')
        caption = f"📋 <b>{len(selected):,} کانفیگ</b> | JSON\n🤖 {BOT_USERNAME}"
    else:
        fname   = f"{prefix}_{len(selected)}_{rnd}.txt"
        payload = "\n".join(selected).encode('utf-8')
        caption = f"📄 <b>{len(selected):,} کانفیگ</b> | TXT\n🤖 {BOT_USERNAME}"

    buf      = BytesIO(payload)
    buf.name = fname
    try:
        await msg.reply_document(
            document=InputFile(buf, filename=fname),
            caption=caption, parse_mode='HTML'
        )
        add_stat("total_configs_sent", len(selected))
    except Exception as e:
        logger.error(f"send_configs_to_msg error: {e}")
        await msg.reply_text(f"❌ خطا در ارسال فایل: {str(e)[:80]}")

# ══════════════════════════════════════════════
#  SECTION 8 — USER PANEL HTML
# ══════════════════════════════════════════════
flask_app = Flask(__name__)

USER_PANEL_HTML = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>داشبورد | Config Collector</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');
  :root{--bg:#060d1a;--card:#0f1d30;--card2:#162438;--text:#e2eaf6;--muted:#6b7fa3;
    --accent:#00d4ff;--accent2:#7c3aed;--success:#10d97b;--danger:#f43f5e;
    --border:#1e3050;--glow:0 0 20px rgba(0,212,255,.15);}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:'Vazirmatn',Tahoma,sans-serif;min-height:100vh;padding:16px;}
  .container{max-width:860px;margin:auto;}
  .header{text-align:center;padding:24px 0 20px;border-bottom:1px solid var(--border);margin-bottom:24px;}
  .logo{font-size:2rem;margin-bottom:8px;}
  .header h1{font-size:1.4rem;color:var(--accent);font-weight:700;}
  .badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.75rem;font-weight:600;
    background:rgba(0,212,255,.12);color:var(--accent);border:1px solid rgba(0,212,255,.3);margin-top:6px;}
  .badge.vip{background:rgba(124,58,237,.2);color:#a78bfa;border-color:rgba(124,58,237,.4);}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-bottom:20px;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;
    box-shadow:var(--glow);transition:.2s;}
  .card:hover{border-color:var(--accent);transform:translateY(-2px);}
  .card-title{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px;}
  .stat-num{font-size:2rem;font-weight:700;color:var(--accent);}
  .progress-bar{height:6px;background:var(--border);border-radius:3px;margin-top:10px;overflow:hidden;}
  .progress-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:.4s;}
  select,input[type=text]{width:100%;padding:10px 14px;background:#0a1520;border:1px solid var(--border);
    color:var(--text);border-radius:8px;font-family:inherit;font-size:.9rem;margin-bottom:10px;outline:none;}
  select:focus,input:focus{border-color:var(--accent);}
  .btn{display:block;width:100%;padding:11px;border:none;border-radius:8px;font-family:inherit;
    font-size:.9rem;font-weight:600;cursor:pointer;transition:.2s;text-align:center;}
  .btn-primary{background:linear-gradient(135deg,#0096c7,#7c3aed);color:#fff;}
  .btn-outline{background:transparent;border:1px solid var(--accent);color:var(--accent);}
  .btn:hover{opacity:.85;transform:translateY(-1px);}
  pre{background:#040a12;color:var(--success);padding:14px;border-radius:10px;font-size:.78rem;
    max-height:200px;overflow-y:auto;border:1px solid var(--border);white-space:pre-wrap;word-break:break-all;margin-top:10px;}
  .copy-box{display:flex;gap:8px;align-items:center;}
  .copy-box input{margin:0;flex:1;font-size:.75rem;direction:ltr;}
  .copy-btn{padding:10px 14px;background:var(--card2);border:1px solid var(--border);
    color:var(--accent);border-radius:8px;cursor:pointer;font-size:.8rem;white-space:nowrap;}
  .toast{position:fixed;bottom:20px;right:20px;background:var(--success);color:#000;
    padding:10px 20px;border-radius:8px;display:none;font-weight:600;z-index:999;}
  .section-title{font-size:1rem;color:var(--accent);font-weight:600;margin:20px 0 12px;
    padding-bottom:8px;border-bottom:1px solid var(--border);}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">🛡️</div>
    <h1>داشبورد کاربری Config Collector</h1>
    <span class="badge {{ 'vip' if user.is_vip else '' }}">
      {{ '👑 VIP' if user.is_vip else '👤 کاربر عادی' }}
    </span>
    <span class="badge" style="margin-right:8px;">🆔 {{ uid }}</span>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-title">📊 مصرف امروز</div>
      <div class="stat-num">{{ user.daily_requests }}</div>
      <div style="color:var(--muted);font-size:.85rem;margin-top:4px;">
        از {{ 'نامحدود' if user.is_vip else (3 + user.bonus_limit) }} درخواست مجاز
      </div>
      {% if not user.is_vip %}
      <div class="progress-bar">
        <div class="progress-fill" style="width:{{ [user.daily_requests/(3+user.bonus_limit)*100,100]|min }}%"></div>
      </div>
      {% endif %}
    </div>
    <div class="card">
      <div class="card-title">🎁 دعوت دوستان</div>
      <div class="stat-num" style="color:var(--success);">+{{ user.bonus_limit }}</div>
      <div style="color:var(--muted);font-size:.85rem;margin-top:4px;">درخواست اضافی از دعوت‌ها</div>
    </div>
  </div>

  <div class="section-title">🔗 لینک سابسکریپشن</div>
  <div class="card" style="margin-bottom:16px;">
    <div class="card-title">📡 لینک اشتراک هوشمند</div>
    <div class="copy-box">
      <input type="text" value="{{ sub_link }}" readonly id="subLink" dir="ltr">
      <button class="copy-btn" onclick="copy('subLink')">📋 کپی</button>
    </div>
    <div style="color:var(--muted);font-size:.8rem;margin-top:8px;">
      این لینک را در v2rayNG، Nekobox یا Hiddify وارد کنید.
    </div>
  </div>

  <div class="section-title">⚙️ فیلتر پروتکل</div>
  <div class="card" style="margin-bottom:16px;">
    <select id="protoSel">
      <option value="ALL" {{ 'selected' if user.protocol_filter=='ALL' }}>همه پروتکل‌ها</option>
      <option value="vless" {{ 'selected' if user.protocol_filter=='vless' }}>VLESS</option>
      <option value="vmess" {{ 'selected' if user.protocol_filter=='vmess' }}>VMESS</option>
      <option value="trojan" {{ 'selected' if user.protocol_filter=='trojan' }}>TROJAN</option>
      <option value="ss" {{ 'selected' if user.protocol_filter=='ss' }}>Shadowsocks</option>
    </select>
    <button class="btn btn-outline" onclick="saveProto()">💾 ذخیره پروتکل</button>
    <div id="protoMsg" style="color:var(--success);font-size:.85rem;margin-top:8px;display:none;"></div>
  </div>

  <div class="section-title">🛠️ ابزارهای آنلاین</div>
  <div class="grid">
    <div class="card">
      <div class="card-title">🏓 تست پینگ</div>
      <input type="text" id="pingIn" placeholder="مثال: google.com">
      <button class="btn btn-outline" onclick="tool('ping')">🚀 تست کن</button>
      <pre id="pingOut">نتیجه اینجا نمایش داده می‌شود...</pre>
    </div>
    <div class="card">
      <div class="card-title">🤖 هوش مصنوعی</div>
      <input type="text" id="aiIn" placeholder="سوال خود را بنویسید...">
      <button class="btn btn-outline" onclick="tool('ai')">💬 ارسال</button>
      <pre id="aiOut">پاسخ AI اینجا نمایش داده می‌شود...</pre>
    </div>
  </div>

  <div class="section-title">📦 دریافت کانفیگ</div>
  <div class="card">
    <button class="btn btn-primary" onclick="getCfg()">🎲 دریافت کانفیگ تصادفی از کش</button>
    <pre id="cfgOut">کانفیگ اینجا نمایش داده می‌شود...</pre>
  </div>

  <div style="text-align:center;margin-top:20px;padding-bottom:20px;">
    <a href="https://t.me/{{ bot_u }}" style="color:var(--muted);text-decoration:none;font-size:.85rem;">
      🤖 بازگشت به ربات تلگرام
    </a>
  </div>
</div>

<div class="toast" id="toast">✅ کپی شد!</div>

<script>
const API = '/api/panel/{{ uid }}/{{ user.sub_token }}';
async function apiCall(ep, body={}) {
  try {
    const r = await fetch(API+ep, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    return await r.json();
  } catch(e){ return {error: 'خطای شبکه: '+e.message}; }
}
function copy(id) {
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.value).catch(()=>{el.select();document.execCommand('copy');});
  const t = document.getElementById('toast');
  t.style.display='block'; setTimeout(()=>t.style.display='none', 2000);
}
async function saveProto() {
  const p = document.getElementById('protoSel').value;
  const r = await apiCall('/protocol', {protocol: p});
  const m = document.getElementById('protoMsg');
  m.style.display='block';
  m.innerText = r.success ? '✅ ذخیره شد.' : '❌ خطا: '+r.error;
}
async function tool(type) {
  const inp = document.getElementById(type==='ping'?'pingIn':'aiIn').value.trim();
  const out = document.getElementById(type==='ping'?'pingOut':'aiOut');
  if(!inp){out.innerText='⚠️ ورودی خالی است.'; return;}
  out.innerText = '⏳ در حال پردازش...';
  const r = await apiCall('/tool', {type, input: inp});
  out.innerText = r.result || r.error || 'خطای نامشخص';
}
async function getCfg() {
  const out = document.getElementById('cfgOut');
  out.innerText = '⏳ در حال دریافت...';
  const r = await apiCall('/config');
  out.innerText = r.config || r.error || 'خطا';
}
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════
#  SECTION 9 — ADMIN HTML (تغییر نیافته)
# ══════════════════════════════════════════════
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>ADMIN :: Config Collector</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
:root{--bg:#03070f;--panel:#080f1c;--border:#0d2035;--cyan:#00ffff;--green:#00ff88;
  --red:#ff3355;--yellow:#ffcc00;--muted:#3a5570;--text:#c8dff0;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;padding:16px;font-size:13px;}
.term-header{border:1px solid var(--border);padding:14px 20px;margin-bottom:20px;
  background:linear-gradient(135deg,#030d1a,#060f20);
  display:flex;justify-content:space-between;align-items:center;}
.term-title{color:var(--cyan);font-size:1rem;font-weight:700;text-shadow:0 0 10px var(--cyan);}
.online-badge{color:var(--green);font-size:.75rem;border:1px solid var(--green);padding:3px 10px;
  background:rgba(0,255,136,.06);}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:20px;}
.stat-box{background:var(--panel);border:1px solid var(--border);padding:14px;border-left:3px solid var(--cyan);}
.stat-box.err{border-left-color:var(--red);}
.stat-box.warn{border-left-color:var(--yellow);}
.stat-lbl{font-size:.65rem;color:var(--muted);letter-spacing:.1em;margin-bottom:6px;}
.stat-val{font-size:1.6rem;font-weight:700;color:var(--cyan);}
.stat-val.red{color:var(--red);}
.panel{background:var(--panel);border:1px solid var(--border);padding:16px;margin-bottom:16px;}
.panel-title{color:var(--cyan);font-size:.8rem;letter-spacing:.1em;margin-bottom:14px;
  padding-bottom:8px;border-bottom:1px solid var(--border);}
table{width:100%;border-collapse:collapse;}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);font-size:.75rem;}
th{color:var(--cyan);background:#040c18;}
td{color:#8fb0cc;}
.form-row{display:flex;gap:8px;margin-bottom:12px;}
input[type=text]{flex:1;background:#040c18;border:1px solid var(--border);color:var(--cyan);
  padding:8px 12px;font-family:inherit;font-size:.8rem;outline:none;}
input:focus{border-color:var(--cyan);}
.btn{background:transparent;border:1px solid currentColor;padding:6px 14px;cursor:pointer;
  font-family:inherit;font-size:.75rem;font-weight:700;transition:.15s;}
.btn-c{color:var(--cyan);} .btn-c:hover{background:rgba(0,255,255,.08);}
.btn-r{color:var(--red);}  .btn-r:hover{background:rgba(255,51,85,.08);}
.btn-y{color:var(--yellow);} .btn-y:hover{background:rgba(255,204,0,.08);}
.tag-vip{background:rgba(255,204,0,.12);color:var(--yellow);padding:2px 8px;font-size:.7rem;}
.users-table td:first-child{color:var(--green);}
</style>
</head>
<body>
<div class="term-header">
  <div class="term-title">&gt; SYS_CORE :: CONFIG_COLLECTOR_ADMIN</div>
  <div class="online-badge">● ONLINE // {{ last_sync }}</div>
</div>
<div class="stats-grid">
  <div class="stat-box"><div class="stat-lbl">USERS</div><div class="stat-val">{{ stats.users }}</div></div>
  <div class="stat-box"><div class="stat-lbl">REQUESTS</div><div class="stat-val">{{ stats.total_requests }}</div></div>
  <div class="stat-box"><div class="stat-lbl">NODES_SENT</div><div class="stat-val">{{ stats.total_configs_sent }}</div></div>
  <div class="stat-box warn"><div class="stat-lbl">CACHED</div><div class="stat-val" style="color:var(--yellow)">{{ cached }}</div></div>
  <div class="stat-box err"><div class="stat-lbl">ERRORS</div><div class="stat-val red">{{ stats.errors }}</div></div>
  <div class="stat-box"><div class="stat-lbl">SOURCES</div><div class="stat-val">{{ sources|length }}</div></div>
  <div class="stat-box"><div class="stat-lbl">GROUPS</div><div class="stat-val">{{ groups|length }}</div></div>
  <div class="stat-box"><div class="stat-lbl">VIP_USERS</div><div class="stat-val">{{ vip_count }}</div></div>
</div>
<div class="panel">
  <div class="panel-title">&gt; GITHUB_SOURCES [{{ sources|length }}]</div>
  <form method="POST" class="form-row">
    <input type="text" name="source_link" placeholder="https://raw.githubusercontent.com/...">
    <button class="btn btn-c" name="action" value="add_source">+ INJECT</button>
  </form>
  <table>
    <tr><th>#</th><th>URL</th><th>ACTION</th></tr>
    {% for i,s in sources %}
    <tr><td>{{ i+1 }}</td><td>{{ s[:70] }}{% if s|length > 70 %}...{% endif %}</td>
    <td><form method="POST" style="margin:0">
      <input type="hidden" name="src_id" value="{{ i }}">
      <button class="btn btn-r" name="action" value="del_source">PURGE</button>
    </form></td></tr>
    {% endfor %}
  </table>
</div>
<div class="panel">
  <div class="panel-title">&gt; CUSTOM_NODES [{{ custom_configs|length }}]</div>
  <form method="POST" class="form-row">
    <input type="text" name="config_link" placeholder="vless://... OR vmess://...">
    <button class="btn btn-y" name="action" value="add_config">+ ADD_NODE</button>
  </form>
  <table>
    <tr><th>#</th><th>PAYLOAD</th><th>ACTION</th></tr>
    {% for i,c in custom_configs %}
    <tr><td>{{ i+1 }}</td><td style="color:var(--yellow)">{{ c[:80] }}...</td>
    <td><form method="POST" style="margin:0">
      <input type="hidden" name="cfg_id" value="{{ i }}">
      <button class="btn btn-r" name="action" value="del_config">PURGE</button>
    </form></td></tr>
    {% endfor %}
  </table>
</div>
<div class="panel">
  <div class="panel-title">&gt; USER_REGISTRY [TOP 20]</div>
  <table class="users-table">
    <tr><th>USER_ID</th><th>NAME</th><th>STATUS</th><th>REQS</th><th>JOINED</th></tr>
    {% for u in top_users %}
    <tr>
      <td>{{ u.uid }}</td><td>{{ u.first_name or u.username or '—' }}</td>
      <td>{% if u.is_vip %}<span class="tag-vip">VIP</span>{% else %}—{% endif %}</td>
      <td>{{ u.total_requests }}</td><td>{{ u.join_date or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
</div>
<div class="panel">
  <div class="panel-title">&gt; VIP_CTRL</div>
  <form method="POST" class="form-row">
    <input type="text" name="vip_id" placeholder="USER_ID">
    <button class="btn btn-y" name="action" value="add_vip">+ VIP</button>
    <button class="btn btn-r" name="action" value="del_vip">– VIP</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">&gt; CACHE_CTRL</div>
  <form method="POST" style="display:inline">
    <button class="btn btn-c" name="action" value="refresh_cache">⟳ FORCE_SYNC</button>
  </form>
  <form method="POST" style="display:inline;margin-right:8px">
    <button class="btn btn-r" name="action" value="clear_cache">⚠ PURGE_CACHE</button>
  </form>
</div>
</body>
</html>
"""

# ══════════════════════════════════════════════
#  SECTION 10 — Flask User Routes + Smart Sub
# ══════════════════════════════════════════════
@flask_app.route('/')
def index():
    return jsonify({"status": "online", "bot": BOT_USERNAME, "cached": len(CONFIG_CACHE['configs'])})

@flask_app.route('/panel/<int:uid>/<token>')
def user_panel(uid, token):
    u = get_user(uid)
    if u.get('sub_token') != token:
        return Response("401 Unauthorized", status=401)
    sub = f"{BASE_URL}/sub/{uid}/{token}"
    return render_template_string(USER_PANEL_HTML, uid=uid, user=u, sub_link=sub,
                                   bot_u=BOT_USERNAME.lstrip('@'))

@flask_app.route('/api/panel/<int:uid>/<token>/<action>', methods=['POST'])
def api_panel(uid, token, action):
    u = get_user(uid)
    if u.get('sub_token') != token:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    if action == 'protocol':
        proto = data.get('protocol', 'ALL')
        if proto in ["ALL"] + PROTOCOLS:
            u["protocol_filter"] = proto
            save_user(uid, u)
            return jsonify({"success": True})
        return jsonify({"error": "Invalid protocol"})
    elif action == 'tool':
        t   = data.get('type', '')
        inp = data.get('input', '').strip()
        if not inp:
            return jsonify({"error": "Empty input"})
        if t == 'ping':
            result = run_async_safe(ping_host_async(inp))
        elif t == 'ai':
            result = run_async_safe(ask_ai_async(inp))
        else:
            result = "Unknown tool"
        return jsonify({"result": result})
    elif action == 'config':
        if not check_limit(uid)[0]:
            return jsonify({"error": "سهمیه روزانه تمام شد."})
        cfgs    = filter_configs(CONFIG_CACHE['configs'], u["protocol_filter"])
        customs = load_custom_configs()
        pool    = customs + cfgs
        if pool:
            return jsonify({"config": random.choice(pool)})
        return jsonify({"error": "کش خالی است."})
    return jsonify({"error": "Bad request"}), 400

@flask_app.route('/sub/<int:uid>/<token>')
def user_sub(uid, token):
    """ساب‌لینک اختصاصی + ۵ بخش رندوم"""
    u = get_user(uid)
    if u.get('sub_token') != token:
        return Response("401", status=401)
    plain    = request.args.get('plain', '0') == '1'
    customs  = load_custom_configs()
    all_cfgs = filter_configs(CONFIG_CACHE['configs'], u.get("protocol_filter", "ALL"))
    seed_val = sum(ord(c) for c in token) + int(CONFIG_CACHE.get('last_update', 0) // 1800)
    rng      = random.Random(seed_val)
    if len(all_cfgs) > 500:
        cfgs_copy = all_cfgs.copy()
        rng.shuffle(cfgs_copy)
        chunk    = max(1, len(cfgs_copy) // 5)
        selected = []
        for i in range(5):
            start = rng.randint(0, max(0, len(cfgs_copy) - chunk - 1))
            selected.extend(cfgs_copy[start: start + chunk])
        selected = list(dict.fromkeys(selected))[:600]
    else:
        selected = all_cfgs
    final   = list(dict.fromkeys(customs + selected))
    content = "\n".join(final) if final else "# Cache empty"
    if plain:
        return Response(content, mimetype='text/plain; charset=utf-8')
    encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
    return Response(encoded, mimetype='text/plain; charset=utf-8')

@flask_app.route('/metrics')
def metrics():
    """Prometheus-style metrics endpoint"""
    stats = load_json("stats", DEFAULT_STATS)
    lines = [
        f"bot_users {stats.get('users', 0)}",
        f"bot_cached_configs {len(CONFIG_CACHE['configs'])}",
        f"bot_requests_total {stats.get('total_requests', 0)}",
        f"bot_configs_sent_total {stats.get('total_configs_sent', 0)}",
        f"bot_errors_total {stats.get('errors', 0)}",
    ]
    return Response("\n".join(lines), mimetype='text/plain')

@flask_app.route('/dashboard')
def dashboard():
    g = load_json("stats", DEFAULT_STATS)
    return jsonify({"status": "ok", "bot": BOT_USERNAME, "users": g.get("users", 0),
                    "cached": len(CONFIG_CACHE['configs']), "uptime": "running"})

# ══════════════════════════════════════════════
#  SECTION 11 — Flask Admin Routes
# ══════════════════════════════════════════════
@flask_app.route('/admin', methods=['GET', 'POST'])
def admin_web():
    auth = request.authorization
    if not auth or auth.username != "admin" or auth.password != ADMIN_PASS:
        return Response('ADMIN PANEL — Authentication Required', 401,
                        {'WWW-Authenticate': 'Basic realm="Admin"'})
    if request.method == 'POST':
        action = request.form.get("action", "")
        if action == "add_source":
            s = request.form.get("source_link", "").strip()
            if s and s.startswith("http"):
                db = load_json("sources", {"list": DEFAULT_SOURCES})
                if s not in db["list"]:
                    db["list"].append(s)
                    save_json("sources", db)
        elif action == "del_source":
            idx = int(request.form.get("src_id", -1))
            db  = load_json("sources", {"list": DEFAULT_SOURCES})
            if 0 <= idx < len(db["list"]):
                db["list"].pop(idx)
                save_json("sources", db)
        elif action == "add_config":
            c = request.form.get("config_link", "").strip()
            if c and any(c.startswith(p+"://") for p in PROTOCOLS):
                cfgs = load_custom_configs()
                if c not in cfgs:
                    cfgs.append(c)
                    save_custom_configs(cfgs)
        elif action == "del_config":
            idx  = int(request.form.get("cfg_id", -1))
            cfgs = load_custom_configs()
            if 0 <= idx < len(cfgs):
                cfgs.pop(idx)
                save_custom_configs(cfgs)
        elif action == "add_vip":
            vid = request.form.get("vip_id", "").strip()
            if vid:
                u = get_user(int(vid))
                u["is_vip"] = True
                save_user(int(vid), u)
        elif action == "del_vip":
            vid = request.form.get("vip_id", "").strip()
            if vid:
                u = get_user(int(vid))
                u["is_vip"] = False
                save_user(int(vid), u)
        elif action == "refresh_cache":
            threading.Thread(target=lambda: run_async_safe(update_cache()), daemon=True).start()
        elif action == "clear_cache":
            CONFIG_CACHE['configs']     = []
            CONFIG_CACHE['last_update'] = 0
        return redirect(url_for('admin_web'))
    stats     = load_json("stats", DEFAULT_STATS)
    db        = load_json("sources", {"list": DEFAULT_SOURCES})
    customs   = load_custom_configs()
    groups_db = load_json("groups", {"list": []})
    users_all = get_all_users_info()
    vip_count = sum(1 for u in users_all if u.get("is_vip"))
    last_sync = (datetime.fromtimestamp(CONFIG_CACHE['last_update'], TEHRAN_TZ).strftime('%H:%M:%S')
                 if CONFIG_CACHE['last_update'] else "NEVER")
    return render_template_string(ADMIN_HTML, stats=stats,
        cached=len(CONFIG_CACHE['configs']),
        sources=list(enumerate(db["list"])),
        custom_configs=list(enumerate(customs)),
        groups=groups_db.get("list", []),
        top_users=users_all[:20], vip_count=vip_count, last_sync=last_sync)

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False, debug=False)

# ══════════════════════════════════════════════
#  SECTION 12 — All Keyboards (Updated + New)
# ══════════════════════════════════════════════
def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 کانفیگ رایگان",        callback_data="free_config")],
        [
            InlineKeyboardButton("📦 دریافت از کش",        callback_data="get_configs"),
            InlineKeyboardButton("⚡ اسکن لحظه‌ای",        callback_data="live_scan"),
        ],
        [
            InlineKeyboardButton("🎲 کانفیگ تصادفی",       callback_data="random_cfg"),
            InlineKeyboardButton("🔐 کانفیگ ادمین",        callback_data="admin_cfgs"),
        ],
        [
            InlineKeyboardButton("🔧 فیلتر پروتکل",        callback_data="filter_proto"),
            InlineKeyboardButton("🌍 فیلتر کشور",          callback_data="country_filter"),
        ],
        [
            InlineKeyboardButton("🌐 داشبورد وب",           callback_data="web_dash"),
            InlineKeyboardButton("🔗 اشتراک هوشمند",       callback_data="sub_link_smart"),
        ],
        [
            InlineKeyboardButton("📊 آمار من",              callback_data="my_stats"),
            InlineKeyboardButton("🏆 آمار کل",              callback_data="global_stats"),
        ],
        [
            InlineKeyboardButton("🎁 دعوت دوستان",          callback_data="invite"),
            InlineKeyboardButton("📖 راهنمای کامل",         callback_data="help"),
        ],
    ])

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 آمار کامل",   callback_data="adm_stats"),
            InlineKeyboardButton("👥 لیست کاربران", callback_data="adm_users"),
        ],
        [
            InlineKeyboardButton("👑 لیست VIP",    callback_data="adm_viplist"),
            InlineKeyboardButton("📡 لیست گروه‌ها", callback_data="adm_groups"),
        ],
        [
            InlineKeyboardButton("📢 ارسال به کانال", callback_data="adm_postchannel"),
            InlineKeyboardButton("💾 بکاپ دیتابیس",  callback_data="adm_backup"),
        ],
        [
            InlineKeyboardButton("✅ افزودن VIP",   callback_data="adm_addvip"),
            InlineKeyboardButton("❌ حذف VIP",      callback_data="adm_removevip"),
        ],
        [
            InlineKeyboardButton("🗑️ پاک کش",      callback_data="adm_clearcache"),
            InlineKeyboardButton("🔄 آپدیت کش",    callback_data="adm_refreshcache"),
        ],
        [
            InlineKeyboardButton("⚙️ وضعیت سرور",  callback_data="adm_health"),
            InlineKeyboardButton("📋 لاگ‌ها",       callback_data="adm_logs"),
        ],
        [InlineKeyboardButton("🌐 پنل وب ادمین", url=f"{BASE_URL}/admin")],
    ])

def proto_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 ALL",       callback_data="proto_ALL"),
            InlineKeyboardButton("⚡ VLESS",     callback_data="proto_vless"),
        ],
        [
            InlineKeyboardButton("🔵 VMESS",     callback_data="proto_vmess"),
            InlineKeyboardButton("🛡️ TROJAN",    callback_data="proto_trojan"),
        ],
        [
            InlineKeyboardButton("🔒 SS",        callback_data="proto_ss"),
            InlineKeyboardButton("🚀 HYSTERIA2", callback_data="proto_hysteria2"),
        ],
        [InlineKeyboardButton("« بازگشت",       callback_data="back_start")],
    ])

def count_format_keyboard(source: str = "cache") -> InlineKeyboardMarkup:
    """source = 'cache'|'live'|'special'|'bulk'"""
    prefix_map = {'cache': 'gc', 'live': 'ls', 'special': 'gs', 'bulk': 'gb'}
    p = prefix_map.get(source, 'gc')
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("━━ 📄 فرمت TXT ━━", callback_data="noop_info")],
        [
            InlineKeyboardButton("5️⃣",    callback_data=f"{p}_5_t"),
            InlineKeyboardButton("1️⃣0️⃣",  callback_data=f"{p}_10_t"),
            InlineKeyboardButton("2️⃣0️⃣",  callback_data=f"{p}_20_t"),
            InlineKeyboardButton("5️⃣0️⃣",  callback_data=f"{p}_50_t"),
        ],
        [
            InlineKeyboardButton("💯",     callback_data=f"{p}_100_t"),
            InlineKeyboardButton("🔢 ۲۰۰", callback_data=f"{p}_200_t"),
            InlineKeyboardButton("∞ همه",  callback_data=f"{p}_0_t"),
        ],
        [InlineKeyboardButton("━━ 📋 فرمت JSON ━━", callback_data="noop_info")],
        [
            InlineKeyboardButton("5️⃣ JSON",    callback_data=f"{p}_5_j"),
            InlineKeyboardButton("1️⃣0️⃣ JSON",  callback_data=f"{p}_10_j"),
            InlineKeyboardButton("5️⃣0️⃣ JSON",  callback_data=f"{p}_50_j"),
        ],
        [InlineKeyboardButton("« بازگشت", callback_data="back_start")],
    ])

def free_config_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ کانفیگ ویژه",        callback_data="fc_special")],
        [InlineKeyboardButton("🌊 کانفیگ انبوه",        callback_data="fc_bulk")],
        [InlineKeyboardButton("📡 کانفیگ‌های ذخیره‌شده", callback_data="fc_cached")],
        [InlineKeyboardButton("« بازگشت به منو",        callback_data="back_start")],
    ])

def country_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("━━ 🌍 انتخاب کشور ━━", callback_data="noop_info")],
        [
            InlineKeyboardButton("🇩🇪 آلمان",          callback_data="cf_de"),
            InlineKeyboardButton("🇳🇱 هلند",           callback_data="cf_nl"),
        ],
        [
            InlineKeyboardButton("🇫🇮 فنلاند",         callback_data="cf_fi"),
            InlineKeyboardButton("🇸🇪 سوئد",           callback_data="cf_se"),
        ],
        [InlineKeyboardButton("🔍 نمایش همه کشورها",   callback_data="cf_all")],
        [InlineKeyboardButton("« بازگشت به منو",        callback_data="back_start")],
    ])

def all_countries_keyboard(configs: List[str]) -> InlineKeyboardMarkup:
    countries = get_available_countries(configs)
    buttons   = []
    row       = []
    for cc, count in list(countries.items())[:14]:
        flag, name = COUNTRY_MAP.get(cc, ('🌍', cc.upper()))
        row.append(InlineKeyboardButton(
            f"{flag} {name} ({count})", callback_data=f"cf_{cc}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("« بازگشت", callback_data="country_filter")])
    return InlineKeyboardMarkup(buttons)

def country_action_keyboard(cc: str) -> InlineKeyboardMarkup:
    flag, name = COUNTRY_MAP.get(cc, ('🌍', cc.upper()))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"━━ {flag} {name} ━━", callback_data="noop_info")],
        [
            InlineKeyboardButton("5️⃣ TXT",    callback_data=f"cget_{cc}_5_t"),
            InlineKeyboardButton("1️⃣0️⃣ TXT",  callback_data=f"cget_{cc}_10_t"),
            InlineKeyboardButton("∞ همه TXT", callback_data=f"cget_{cc}_0_t"),
        ],
        [
            InlineKeyboardButton("1️⃣0️⃣ JSON", callback_data=f"cget_{cc}_10_j"),
            InlineKeyboardButton("5️⃣0️⃣ JSON", callback_data=f"cget_{cc}_50_j"),
        ],
        [InlineKeyboardButton("« بازگشت",     callback_data="country_filter")],
    ])

def confirm_keyboard(yes_cb: str, no_cb: str = "back_start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ بله", callback_data=yes_cb),
        InlineKeyboardButton("❌ خیر", callback_data=no_cb),
    ]])

# ══════════════════════════════════════════════
#  SECTION 13 — /start  /help
# ══════════════════════════════════════════════
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    update_user_info(user.id, user.username or "", user.first_name or "")

    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].split("ref_")[1])
            if process_referral(user.id, ref_id):
                try:
                    bonus = get_user(ref_id).get("bonus_limit", 0)
                    await context.bot.send_message(
                        chat_id=ref_id,
                        text=f"🎉 یک نفر با لینک دعوت شما عضو شد!\n💡 بونوس: +{bonus} درخواست/روز"
                    )
                except Exception:
                    pass
        except (ValueError, IndexError):
            pass

    g     = load_json("stats", DEFAULT_STATS)
    u     = get_user(user.id)
    limit = "♾️ نامحدود (VIP)" if (u.get("is_vip") or user.id == ADMIN_ID) \
            else f"{3 + u.get('bonus_limit', 0)} درخواست/روز"
    text  = (
        f"✨ <b>Config Collector Bot</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ جمع‌آوری خودکار کانفیگ از منابع معتبر\n\n"
        f"👥 <b>کاربران:</b> {g.get('users', 0)}\n"
        f"📦 <b>کانفیگ کش:</b> {len(CONFIG_CACHE['configs']):,}\n"
        f"🏷️ <b>حساب:</b> {'👑 VIP' if u.get('is_vip') else '👤 عادی'}\n"
        f"🎯 <b>محدودیت:</b> {limit}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 {BOT_USERNAME}"
    )
    if chat.type == "private":
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=start_keyboard())
    else:
        await update.message.reply_text(
            f"👋 سلام! برای دریافت کانفیگ به {BOT_USERNAME} پیام بده."
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>راهنمای کامل ربات</b>\n"
        "همه‌چیز در یک نگاه — تمیز و حرفه‌ای\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆓 <b>کانفیگ رایگان:</b>\n"
        "   ⚡ ویژه → منابع گزیده، سرعت بالا\n"
        "   🌊 انبوه → همه منابع، حجم زیاد\n"
        "   📡 ذخیره‌شده → کش، آپدیت هر ۳۰ دقیقه\n\n"
        "📦 <b>دریافت از کش</b> → کانفیگ‌های آماده\n"
        "⚡ <b>اسکن لحظه‌ای</b> → واقعاً لحظه‌ای از منابع\n"
        "🎲 <b>تصادفی</b> → یک کانفیگ رندوم\n\n"
        "🌍 <b>فیلتر کشور</b> → 🇩🇪 آلمان / 🇳🇱 هلند / همه\n"
        "🔧 <b>فیلتر پروتکل</b> → vless/vmess/trojan/ss\n"
        "🔗 <b>اشتراک هوشمند</b> → یک‌بار ثبت، همیشه آپدیت\n\n"
        "🧹 <b>حذف هوشمند</b> تکراری‌ها و خراب‌ها\n"
        "📊 <b>آمار لحظه‌ای</b> سرور و شخصی\n"
        "🎁 <b>دعوت دوستان</b> → بونوس درخواست\n"
        "🌐 <b>داشبورد وب</b> اختصاصی\n"
        "🤖 <b>هوش مصنوعی:</b> /ask [سوال]\n"
        "🏓 <b>پینگ:</b> /ping [domain]\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 عادی: ۳ درخواست/روز | 👑 VIP: نامحدود"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("« بازگشت به منو", callback_data="back_start")
    ]])
    if update.message:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode='HTML', reply_markup=kb)

# ══════════════════════════════════════════════
#  SECTION 14 — /myid  /invite  /ask  /ping  /health
# ══════════════════════════════════════════════
async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    uname = f"@{u.username}" if u.username else "ندارد"
    await update.message.reply_text(
        f"🆔 <b>آیدی عددی:</b> <code>{u.id}</code>\n"
        f"👤 <b>یوزرنیم:</b> {uname}\n"
        f"📛 <b>نام:</b> {u.first_name or '—'}",
        parse_mode='HTML'
    )

async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    info = await context.bot.get_me()
    link = f"https://t.me/{info.username}?start=ref_{uid}"
    u    = get_user(uid)
    refs = load_json("referrals", {})
    cnt  = len(refs.get(str(uid), []))
    await update.message.reply_text(
        f"🎁 <b>دعوت دوستان</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 لینک اختصاصی:\n<code>{link}</code>\n\n"
        f"👥 دعوت‌های موفق: <b>{cnt}</b>\n"
        f"💡 بونوس: <b>+{u.get('bonus_limit', 0)}</b> درخواست/روز",
        parse_mode='HTML'
    )

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🤖 فرمت: /ask [سوال]"); return
    q   = " ".join(context.args)
    msg = await update.message.reply_text("🤖 در حال پردازش...")
    ans = await ask_ai_async(q)
    await msg.edit_text(f"🤖 <b>پاسخ AI:</b>\n\n{ans}", parse_mode='HTML')

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🏓 فرمت: /ping [domain]"); return
    host = context.args[0]
    msg  = await update.message.reply_text(f"🏓 در حال تست {host}...")
    res  = await ping_host_async(host)
    await msg.edit_text(res)

async def health_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        def bar(p):
            n = int(p / 10)
            return "🟩" * n + "⬜" * (10 - n)
        text = (
            "⚙️ <b>وضعیت سرور</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 CPU:  {cpu:.1f}%  {bar(cpu)}\n"
            f"📟 RAM:  {ram.percent:.1f}%  {bar(ram.percent)}\n"
            f"📦 کش:   {len(CONFIG_CACHE['configs']):,} کانفیگ\n"
            f"🌐 URL:  {BASE_URL}\n🟢 پایدار"
        )
    except ImportError:
        text = (f"⚙️ کش: {len(CONFIG_CACHE['configs']):,}\n🌐 {BASE_URL}\n🟢 آنلاین")
    await update.message.reply_text(text, parse_mode='HTML')

# ══════════════════════════════════════════════
#  SECTION 15 — Admin Commands Part 1
# ══════════════════════════════════════════════
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🔐 <b>پنل ادمین</b>\n━━━━━━━━━━━━━━━━━━━",
                                    parse_mode='HTML', reply_markup=admin_panel_keyboard())

async def makevip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("فرمت: /makevip [user_id]"); return
    try:
        uid = int(context.args[0])
        u   = get_user(uid)
        u["is_vip"] = True
        save_user(uid, u)
        await update.message.reply_text(f"✅ <code>{uid}</code> VIP شد.", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def unvip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("فرمت: /unvip [user_id]"); return
    try:
        uid = int(context.args[0])
        u   = get_user(uid)
        u["is_vip"] = False
        save_user(uid, u)
        await update.message.reply_text(f"✅ <code>{uid}</code> از VIP خارج شد.", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def viplist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    users = get_all_users_info()
    vips  = [u for u in users if u.get("is_vip")]
    if not vips:
        await update.message.reply_text("👑 هیچ VIPی وجود ندارد."); return
    text = "👑 <b>لیست VIP:</b>\n" + "\n".join(
        [f"• <code>{v['uid']}</code> — {v.get('first_name') or '—'}" for v in vips]
    )
    await update.message.reply_text(text, parse_mode='HTML')

async def addconfig_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cfg = " ".join(context.args) if context.args else ""
    if not cfg and update.message.reply_to_message:
        cfg = update.message.reply_to_message.text or ""
    if not cfg or not any(cfg.startswith(p + "://") for p in PROTOCOLS):
        await update.message.reply_text("❌ فرمت: /addconfig vless://..."); return
    cfgs = load_custom_configs()
    if cfg in cfgs:
        await update.message.reply_text("⚠️ قبلاً اضافه شده."); return
    cfgs.append(cfg)
    save_custom_configs(cfgs)
    await update.message.reply_text(f"✅ اضافه شد! ({len(cfgs)} کانفیگ اختصاصی)")

async def postchannel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = await update.message.reply_text("📢 در حال ارسال...")
    ok  = await send_to_channel(context.bot)
    await msg.edit_text("✅ ارسال شد." if ok else "❌ خطا در ارسال.")

# ══════════════════════════════════════════════
#  SECTION 16 — Admin Commands Part 2
# ══════════════════════════════════════════════
async def addgroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cid = update.effective_chat.id
    db  = load_json("groups", {"list": []})
    if cid not in db["list"]:
        db["list"].append(cid)
        save_json("groups", db)
        await update.message.reply_text(f"✅ گروه <code>{cid}</code> اضافه شد.", parse_mode='HTML')
    else:
        await update.message.reply_text("ℹ️ قبلاً ثبت شده.")

async def removegroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    cid = update.effective_chat.id
    db  = load_json("groups", {"list": []})
    if cid in db["list"]:
        db["list"].remove(cid)
        save_json("groups", db)
        await update.message.reply_text("✅ گروه حذف شد.")
    else:
        await update.message.reply_text("❌ در لیست نبود.")

async def grouplist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    db  = load_json("groups", {"list": []})
    lst = db.get("list", [])
    if not lst:
        await update.message.reply_text("📡 هیچ گروهی ثبت نشده."); return
    text = "📡 <b>گروه‌ها:</b>\n" + "\n".join([f"• <code>{g}</code>" for g in lst])
    await update.message.reply_text(text, parse_mode='HTML')

async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    for key in ["stats", "users", "groups", "referrals"]:
        p = FILES[key]
        if os.path.exists(p):
            with open(p, 'rb') as f:
                await context.bot.send_document(chat_id=ADMIN_ID, document=f,
                    filename=os.path.basename(p), caption=f"💾 {key}")

async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'rb') as f:
            await context.bot.send_document(chat_id=ADMIN_ID, document=f,
                filename="bot.log", caption="📋 لاگ‌های ربات")
    else:
        await update.message.reply_text("❌ فایل لاگ یافت نشد.")

# ══════════════════════════════════════════════
#  SECTION 17 — Admin Callback Handler
# ══════════════════════════════════════════════
async def health_cmd_inline(query):
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        def bar(p): return "🟩"*int(p/10) + "⬜"*(10-int(p/10))
        text = (f"⚙️ <b>وضعیت</b>\n"
                f"🧠 CPU: {cpu:.1f}%  {bar(cpu)}\n"
                f"📟 RAM: {ram.percent:.1f}%  {bar(ram.percent)}\n"
                f"📦 کش: {len(CONFIG_CACHE['configs']):,}\n🟢 پایدار")
    except Exception:
        text = f"📦 کش: {len(CONFIG_CACHE['configs']):,}\n🌐 {BASE_URL}\n🟢 آنلاین"
    await query.message.reply_text(text, parse_mode='HTML')

async def handle_admin_callback(query, context: ContextTypes.DEFAULT_TYPE):
    data = query.data
    uid  = query.from_user.id
    if uid != ADMIN_ID:
        await query.answer("⛔ فقط ادمین", show_alert=True); return

    if data == "adm_stats":
        g    = load_json("stats", DEFAULT_STATS)
        h7   = sorted(g.get("daily", {}).items())[-7:]
        hist = "\n".join([f"  {d}: {c}" for d, c in h7]) or "  ندارد"
        await query.message.reply_text(
            f"📊 <b>آمار کامل</b>\n━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کاربران: {g.get('users', 0)}\n"
            f"📤 درخواست‌ها: {g.get('total_requests', 0):,}\n"
            f"📦 ارسالی: {g.get('total_configs_sent', 0):,}\n"
            f"❌ خطاها: {g.get('errors', 0)}\n"
            f"💾 کش: {len(CONFIG_CACHE['configs']):,}\n\n"
            f"📅 <b>۷ روز اخیر:</b>\n{hist}", parse_mode='HTML')

    elif data == "adm_users":
        users = get_all_users_info()[:15]
        lines = [f"{i}. {'👑' if u.get('is_vip') else '👤'} "
                 f"{u.get('first_name') or u.get('username') or '—'} "
                 f"(<code>{u['uid']}</code>) — {u.get('total_requests', 0)} req"
                 for i, u in enumerate(users, 1)]
        await query.message.reply_text(
            "👥 <b>کاربران:</b>\n" + "\n".join(lines), parse_mode='HTML')

    elif data == "adm_viplist":
        vips = [u for u in get_all_users_info() if u.get("is_vip")]
        if not vips:
            await query.message.reply_text("👑 هیچ VIPی ندارید."); return
        lines = [f"• <code>{v['uid']}</code> — {v.get('first_name') or '—'}" for v in vips]
        await query.message.reply_text("👑 <b>VIPها:</b>\n" + "\n".join(lines), parse_mode='HTML')

    elif data == "adm_groups":
        lst  = load_json("groups", {"list": []}).get("list", [])
        text = "📡 <b>گروه‌ها:</b>\n" + ("\n".join([f"• <code>{g}</code>" for g in lst]) or "ندارد")
        await query.message.reply_text(text, parse_mode='HTML')

    elif data == "adm_postchannel":
        await query.message.reply_text("📢 در حال ارسال...")
        ok = await send_to_channel(context.bot)
        await query.message.reply_text("✅ ارسال شد." if ok else "❌ خطا در ارسال.")

    elif data == "adm_backup":
        for key in ["stats", "users", "groups", "referrals"]:
            p = FILES[key]
            if os.path.exists(p):
                with open(p, 'rb') as f:
                    await context.bot.send_document(chat_id=ADMIN_ID, document=f,
                                                    filename=os.path.basename(p))

    elif data == "adm_addvip":
        context.user_data['waiting_for'] = 'add_vip'
        await query.message.reply_text("✅ آیدی عددی کاربر را ارسال کنید:")

    elif data == "adm_removevip":
        context.user_data['waiting_for'] = 'remove_vip'
        await query.message.reply_text("❌ آیدی عددی کاربر را ارسال کنید:")

    elif data == "adm_clearcache":
        CONFIG_CACHE['configs']     = []
        CONFIG_CACHE['last_update'] = 0
        await query.message.reply_text("🗑️ کش پاک شد.")

    elif data == "adm_refreshcache":
        await query.message.reply_text("🔄 در حال آپدیت کش...")
        await update_cache()
        await query.message.reply_text(
            f"✅ کش آپدیت شد: <b>{len(CONFIG_CACHE['configs']):,}</b> کانفیگ", parse_mode='HTML')

    elif data == "adm_health":
        await health_cmd_inline(query)

    elif data == "adm_logs":
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'rb') as f:
                await context.bot.send_document(chat_id=ADMIN_ID, document=f, filename="bot.log")
        else:
            await query.message.reply_text("❌ لاگ یافت نشد.")

# ══════════════════════════════════════════════
#  SECTION 18 — User Callback Handler (FULL — همه callbacks)
# ══════════════════════════════════════════════
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    if data == "noop_info":
        return

    if data.startswith("adm_"):
        await handle_admin_callback(query, context)
        return

    # ═══════════════════════════════════════
    #  🆓 کانفیگ رایگان — منو اصلی
    # ═══════════════════════════════════════
    if data == "free_config":
        await query.message.reply_text(
            "🆓 <b>کانفیگ رایگان</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "یکی از حالت‌های زیر رو انتخاب کن 👇\n\n"
            "⚡ <b>کانفیگ ویژه</b>\n"
            "   └ منابع گزیده و سبک، سرعت بالا\n\n"
            "🌊 <b>کانفیگ انبوه</b>\n"
            "   └ تمامی منابع، تنوع و حجم بالاتر\n\n"
            "📡 <b>کانفیگ‌های ذخیره شده</b>\n"
            "   └ آپدیت هر نیم ساعت — سریع و بدون انتظار",
            parse_mode='HTML',
            reply_markup=free_config_keyboard()
        )
        return

    elif data == "fc_special":
        await query.message.reply_text(
            "⚡ <b>کانفیگ ویژه</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "تعداد و فرمت دلخواه:\n🚀 منابع گزیده، کیفیت بالا",
            parse_mode='HTML', reply_markup=count_format_keyboard("special"))
        return

    elif data == "fc_bulk":
        await query.message.reply_text(
            "🌊 <b>کانفیگ انبوه</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "تعداد و فرمت دلخواه:\n📦 تمامی منابع — حجم بالا",
            parse_mode='HTML', reply_markup=count_format_keyboard("bulk"))
        return

    elif data == "fc_cached":
        await query.message.reply_text(
            "📡 <b>کانفیگ‌های ذخیره شده</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "تعداد و فرمت دلخواه:",
            parse_mode='HTML', reply_markup=count_format_keyboard("cache"))
        return

    # ═══════════════════════════════════════
    #  📦 دریافت از کش + ⚡ اسکن لحظه‌ای
    # ═══════════════════════════════════════
    elif data == "get_configs":
        await query.message.reply_text(
            "📦 <b>دریافت از کش</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
            "تعداد و فرمت دلخواه:",
            parse_mode='HTML', reply_markup=count_format_keyboard("cache"))
        return

    elif data == "live_scan":
        await query.message.reply_text(
            "⚡ <b>اسکن لحظه‌ای</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
            "تعداد و فرمت دلخواه:\n⏳ چند ثانیه منتظر بمان",
            parse_mode='HTML', reply_markup=count_format_keyboard("live"))
        return

    # ═══════════════════════════════════════
    #  ✅ پردازش کانفیگ — gc/ls/gs/gb
    # ═══════════════════════════════════════
    elif (data.startswith("gc_") or data.startswith("ls_") or
          data.startswith("gs_") or data.startswith("gb_")):
        parts = data.split("_")
        if len(parts) != 3:
            await query.answer("❌ خطا", show_alert=True); return
        source_type, count_str, fmt = parts
        try:
            count = int(count_str)
        except ValueError:
            count = 10
        as_json = (fmt == "j")

        if is_spamming(uid):
            await query.message.reply_text(f"⚠️ صبر کنید {RATE_LIMIT_SECS:.0f} ثانیه."); return
        ok, msg_txt = check_limit(uid)
        if not ok:
            await query.message.reply_text(msg_txt); return

        u = get_user(uid)

        if source_type == "gs":
            # ⚡ منابع ویژه
            p_msg = await query.message.reply_text(
                "⚡ در حال دریافت از منابع ویژه...\n🚀 کیفیت بالا، سرعت عالی")
            fresh = await fetch_configs_fresh(SPECIAL_SOURCES)
            await p_msg.delete()
            cfgs     = filter_configs(fresh, u.get("protocol_filter", "ALL"))
            customs  = load_custom_configs()
            all_cfgs = list(dict.fromkeys(customs + cfgs))

        elif source_type == "gb":
            # 🌊 انبوه — تمام منابع
            p_msg = await query.message.reply_text(
                "🌊 در حال اسکن تمام منابع...\n📦 جمع‌آوری انبوه کانفیگ")
            try:
                db = load_json("sources", {"list": DEFAULT_SOURCES})
                await update_cache(db.get("list", DEFAULT_SOURCES))
            except Exception as e:
                logger.error(f"Bulk error: {e}")
            await p_msg.delete()
            cfgs     = filter_configs(CONFIG_CACHE['configs'], u.get("protocol_filter", "ALL"))
            customs  = load_custom_configs()
            all_cfgs = list(dict.fromkeys(customs + cfgs))

        elif source_type == "ls":
            # ⚡ اسکن لحظه‌ای
            p_msg = await query.message.reply_text(
                "⏳ در حال اسکن لحظه‌ای...\n⚡ کانفیگ‌های تازه در راهند")
            try:
                db = load_json("sources", {"list": DEFAULT_SOURCES})
                await update_cache(db.get("list", DEFAULT_SOURCES))
            except Exception as e:
                logger.error(f"Live scan error: {e}")
            await p_msg.delete()
            cfgs     = filter_configs(CONFIG_CACHE['configs'], u.get("protocol_filter", "ALL"))
            customs  = load_custom_configs()
            all_cfgs = list(dict.fromkeys(customs + cfgs))

        else:
            # 📦 از کش
            cfgs     = filter_configs(CONFIG_CACHE['configs'], u.get("protocol_filter", "ALL"))
            customs  = load_custom_configs()
            all_cfgs = list(dict.fromkeys(customs + cfgs))

        await send_configs_to_msg(
            msg=query.message, configs=all_cfgs,
            count=count if count else len(all_cfgs),
            as_json=as_json,
            prefix={"gs": "special", "gb": "bulk", "ls": "live", "gc": "cache"}.get(source_type, "configs")
        )
        return

    # ═══════════════════════════════════════
    #  🌍 فیلتر کشور
    # ═══════════════════════════════════════
    elif data == "country_filter":
        await query.message.reply_text(
            "🌍 <b>فیلتر کشور</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "کشور مورد نظر را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=country_keyboard()
        )
        return

    elif data == "cf_all":
        configs   = CONFIG_CACHE['configs']
        countries = get_available_countries(configs)
        if not countries:
            await query.message.reply_text(
                "❌ هیچ کانفیگ کشور-دار در کش یافت نشد.\n"
                "💡 از ⚡ اسکن لحظه‌ای استفاده کنید.")
            return
        total = sum(countries.values())
        await query.message.reply_text(
            f"🌍 <b>کشورهای موجود در کش</b> ({total:,} کانفیگ):\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "یکی را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=all_countries_keyboard(configs)
        )
        return

    elif data.startswith("cf_"):
        cc   = data[3:]  # 2-letter country code
        flag, name = COUNTRY_MAP.get(cc, ('🌍', cc.upper()))
        avail = filter_by_country(CONFIG_CACHE['configs'], cc)
        if not avail:
            await query.message.reply_text(
                f"❌ کانفیگ {flag} <b>{name}</b> در کش موجود نیست.\n"
                "💡 از ⚡ اسکن لحظه‌ای استفاده کنید.",
                parse_mode='HTML'
            )
            return
        await query.message.reply_text(
            f"{flag} <b>{name}</b> — {len(avail):,} کانفیگ موجود\n"
            "فرمت و تعداد را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=country_action_keyboard(cc)
        )
        return

    elif data.startswith("cget_"):
        # cget_de_10_t  →  ['cget', 'de', '10', 't']
        parts = data.split("_")
        if len(parts) != 4:
            await query.answer("❌ خطا", show_alert=True); return
        _, cc, count_str, fmt = parts
        flag, name = COUNTRY_MAP.get(cc, ('🌍', cc.upper()))
        try:
            count = int(count_str)
        except ValueError:
            count = 10
        as_json = (fmt == "j")

        if is_spamming(uid):
            await query.message.reply_text(f"⚠️ صبر کنید {RATE_LIMIT_SECS:.0f} ثانیه."); return
        ok, msg_txt = check_limit(uid)
        if not ok:
            await query.message.reply_text(msg_txt); return

        filtered = filter_by_country(CONFIG_CACHE['configs'], cc)
        if not filtered:
            await query.message.reply_text(
                f"❌ کانفیگ {flag} {name} یافت نشد.\n💡 ابتدا اسکن لحظه‌ای بزنید.")
            return

        await send_configs_to_msg(
            msg=query.message, configs=filtered,
            count=count if count else len(filtered),
            as_json=as_json, prefix=f"country_{cc}"
        )
        return

    # ═══════════════════════════════════════
    #  🔗 اشتراک هوشمند
    # ═══════════════════════════════════════
    elif data == "sub_link_smart":
        u   = get_user(uid)
        tok = u.get("sub_token", "")
        lnk = f"{BASE_URL}/sub/{uid}/{tok}"
        await query.message.reply_text(
            f"🔗 <b>لینک اشتراک هوشمند</b>\n\n"
            f"<code>{lnk}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>چرا اشتراک؟</b>\n"
            "این لینک را یک‌بار در برنامه‌ات ثبت کن؛ از این به بعد "
            "دیگر لازم نیست هی از ربات کانفیگ بگیری — خودِ برنامه "
            "هر ۳۱ دقیقه به‌صورت خودکار آپدیتش می‌کند. ✅\n\n"
            "📲 <b>چطور؟</b>\n"
            "در v2rayNG/NekoBox ← افزودن اشتراک (Subscription) "
            "← لینک بالا را Paste کن ← Update.\n\n"
            f"🔐 <b>پلین (Nekobox/Hiddify):</b>\n<code>{lnk}?plain=1</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]])
        )
        return

    # ═══════════════════════════════════════
    #  گزینه‌های موجود قبلی
    # ═══════════════════════════════════════
    elif data == "random_cfg":
        ok, msg_txt = check_limit(uid)
        if not ok:
            await query.message.reply_text(msg_txt); return
        u       = get_user(uid)
        cfgs    = filter_configs(CONFIG_CACHE['configs'], u.get("protocol_filter", "ALL"))
        customs = load_custom_configs()
        pool    = customs + cfgs
        if pool:
            cfg = random.choice(pool)
            await query.message.reply_text(
                f"🎲 <b>کانفیگ تصادفی:</b>\n\n<code>{cfg}</code>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 دیگری", callback_data="random_cfg"),
                    InlineKeyboardButton("« بازگشت", callback_data="back_start"),
                ]])
            )
        else:
            await query.message.reply_text("❌ کش خالی.\n💡 ⚡ اسکن لحظه‌ای را امتحان کنید.")

    elif data == "admin_cfgs":
        customs = load_custom_configs()
        if not customs:
            await query.message.reply_text("ℹ️ هیچ کانفیگ اختصاصی ادمین بارگذاری نشده."); return
        txt = "🔐 <b>کانفیگ‌های اختصاصی ادمین:</b>\n\n"
        for i, c in enumerate(customs[:5], 1):
            txt += f"{i}. <code>{c}</code>\n\n"
        await query.message.reply_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]]))

    elif data == "filter_proto":
        u = get_user(uid)
        await query.message.reply_text(
            f"🔧 پروتکل فعلی: <b>{u.get('protocol_filter', 'ALL')}</b>\nیکی را انتخاب کنید:",
            parse_mode='HTML', reply_markup=proto_keyboard())

    elif data.startswith("proto_"):
        proto = data.split("_", 1)[1]
        u = get_user(uid)
        u["protocol_filter"] = proto
        save_user(uid, u)
        await query.message.reply_text(
            f"✅ پروتکل روی <b>{proto}</b> تنظیم شد.", parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]]))

    elif data == "web_dash":
        u   = get_user(uid)
        tok = u.get("sub_token", "")
        url = f"{BASE_URL}/panel/{uid}/{tok}"
        await query.message.reply_text(
            f"🌐 <b>داشبورد:</b>\n{url}\n\n"
            f"🔔 <b>سابسکریپشن:</b>\n<code>{BASE_URL}/sub/{uid}/{tok}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 باز کردن", url=url)
            ]]))

    elif data == "my_stats":
        u   = get_user(uid)
        tot = 3 + u.get("bonus_limit", 0)
        vip = u.get("is_vip") or uid == ADMIN_ID
        await query.message.reply_text(
            f"📊 <b>آمار شما</b>\n━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ حساب: {'👑 VIP' if vip else '👤 عادی'}\n"
            f"📅 امروز: {u.get('daily_requests', 0)} از {'∞' if vip else tot}\n"
            f"📦 کل: {u.get('total_requests', 0):,}\n"
            f"🎁 بونوس: +{u.get('bonus_limit', 0)}\n"
            f"🔧 پروتکل: {u.get('protocol_filter', 'ALL')}\n"
            f"📅 عضویت: {u.get('join_date', '—')}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]]))

    elif data == "global_stats":
        g  = load_json("stats", DEFAULT_STATS)
        lu = (datetime.fromtimestamp(CONFIG_CACHE['last_update'], TEHRAN_TZ).strftime('%H:%M')
              if CONFIG_CACHE['last_update'] else "هنوز نشده")
        await query.message.reply_text(
            f"🏆 <b>آمار کل سرور</b>\n━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کاربران: {g.get('users', 0)}\n"
            f"📦 ارسالی: {g.get('total_configs_sent', 0):,}\n"
            f"📤 درخواست: {g.get('total_requests', 0):,}\n"
            f"💾 کش: {len(CONFIG_CACHE['configs']):,}\n"
            f"🕐 آپدیت: {lu}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]]))

    elif data == "invite":
        info = await context.bot.get_me()
        link = f"https://t.me/{info.username}?start=ref_{uid}"
        u    = get_user(uid)
        refs = load_json("referrals", {})
        cnt  = len(refs.get(str(uid), []))
        await query.message.reply_text(
            f"🎁 <b>دعوت دوستان</b>\n\n"
            f"🔗 لینک: <code>{link}</code>\n"
            f"👥 موفق: {cnt} | 💡 بونوس: +{u.get('bonus_limit', 0)}",
            parse_mode='HTML')

    elif data == "help":
        text = (
            "📖 <b>راهنمای کامل ربات</b>\n"
            "همه‌چیز در یک نگاه — تمیز و حرفه‌ای\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🆓 <b>کانفیگ رایگان:</b>\n"
            "   ⚡ ویژه → منابع گزیده، سرعت بالا\n"
            "   🌊 انبوه → همه منابع، حجم زیاد\n"
            "   📡 ذخیره‌شده → کش، آپدیت هر ۳۰ دقیقه\n\n"
            "📦 دریافت از کش | ⚡ اسکن لحظه‌ای\n"
            "🌍 فیلتر کشور (🇩🇪 آلمان / 🇳🇱 هلند / همه)\n"
            "🔧 فیلتر پروتکل | 🎲 تصادفی\n"
            "🔗 اشتراک هوشمند — یک‌بار ثبت، همیشه آپدیت\n\n"
            "🧹 حذف هوشمند تکراری + خراب\n"
            "🤖 /ask [سوال] | 🏓 /ping [domain]\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 ۳ درخواست/روز | 👑 VIP: نامحدود"
        )
        await query.message.reply_text(text, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« بازگشت", callback_data="back_start")
            ]]))

    elif data == "back_start":
        g   = load_json("stats", DEFAULT_STATS)
        u   = get_user(uid)
        vip = u.get("is_vip") or uid == ADMIN_ID
        lim = "♾️ نامحدود (VIP)" if vip else f"{3+u.get('bonus_limit',0)} درخواست/روز"
        await query.message.reply_text(
            f"✨ <b>Config Collector Bot</b>\n"
            f"📦 کش: {len(CONFIG_CACHE['configs']):,} | 👥 {g.get('users',0)} کاربر\n"
            f"🎯 {lim}",
            parse_mode='HTML', reply_markup=start_keyboard())

# ══════════════════════════════════════════════
#  SECTION 19 — handle_text + Senders + Jobs + main()
# ══════════════════════════════════════════════
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    uid  = update.effective_user.id
    text = update.message.text.strip()

    waiting = context.user_data.get('waiting_for')
    if uid == ADMIN_ID and waiting:
        context.user_data['waiting_for'] = None
        try:
            tid = int(text.strip())
            u   = get_user(tid)
            if waiting == 'add_vip':
                u["is_vip"] = True
                save_user(tid, u)
                await update.message.reply_text(f"✅ <code>{tid}</code> VIP شد.", parse_mode='HTML')
            elif waiting == 'remove_vip':
                u["is_vip"] = False
                save_user(tid, u)
                await update.message.reply_text(f"✅ <code>{tid}</code> از VIP خارج شد.", parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ آیدی نامعتبر.")
        return

    extracted = extract_configs(text)
    if extracted:
        await send_configs_to_msg(update.message, extracted,
                                  count=len(extracted), prefix="extracted")
        return

    if is_spamming(uid):
        await update.message.reply_text(f"⚠️ صبر کنید {RATE_LIMIT_SECS:.0f} ثانیه.")
        return

    add_stat("total_requests")
    update_user_info(uid, update.effective_user.username or "",
                     update.effective_user.first_name or "")
    await update.message.reply_text(
        "💬 دستور ناشناخته. /start برای منو.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_start")
        ]])
    )

async def send_to_channel(bot) -> bool:
    try:
        if not CONFIG_CACHE['configs']:
            return False
        sel  = random.sample(CONFIG_CACHE['configs'], min(10, len(CONFIG_CACHE['configs'])))
        cfgs = "\n\n".join([f"<code>{c}</code>" for c in sel])
        ts   = datetime.now(TEHRAN_TZ).strftime("%H:%M")
        text = (
            "🔥 <b>گلچین کانفیگ‌های تازه</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{cfgs}\n\n"
            f"⏱ {ts} | 🤖 {BOT_USERNAME}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📥 دریافت بیشتر",
                url=f"https://t.me/{BOT_USERNAME.lstrip('@')}")
        ]])
        await bot.send_message(chat_id=CHANNEL_ID, text=text,
                               parse_mode='HTML', reply_markup=kb)
        return True
    except Exception as e:
        logger.warning(f"Channel post error: {e}")
        return False

async def send_to_groups(bot) -> int:
    db     = load_json("groups", {"list": []})
    groups = db.get("list", [])
    if not groups or not CONFIG_CACHE['configs']:
        return 0
    sel  = random.sample(CONFIG_CACHE['configs'], min(5, len(CONFIG_CACHE['configs'])))
    cfgs = "\n\n".join([f"<code>{c}</code>" for c in sel])
    ts   = datetime.now(TEHRAN_TZ).strftime("%H:%M")
    text = (f"🛰️ <b>کانفیگ‌های تازه</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{cfgs}\n\n⏱ {ts} | 🤖 {BOT_USERNAME}")
    ok_count, to_remove = 0, []
    for gid in groups:
        try:
            await bot.send_message(chat_id=gid, text=text, parse_mode='HTML')
            ok_count += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            if any(x in str(e).lower() for x in ["kicked","blocked","forbidden","not found","deactivated"]):
                to_remove.append(gid)
    if to_remove:
        db["list"] = [g for g in groups if g not in to_remove]
        save_json("groups", db)
    return ok_count

async def job_cache_refresh(context: ContextTypes.DEFAULT_TYPE):
    logger.info("⏰ Cache refresh")
    await update_cache()

async def job_auto_channel(context: ContextTypes.DEFAULT_TYPE):
    if CONFIG_CACHE['configs']:
        ok = await send_to_channel(context.bot)
        if ok:
            logger.info("📢 Channel post sent")

async def job_auto_groups(context: ContextTypes.DEFAULT_TYPE):
    cnt = await send_to_groups(context.bot)
    logger.info(f"📡 Group post: {cnt} groups")

async def job_source_report(context: ContextTypes.DEFAULT_TYPE):
    """📊 گزارش خودکار وضعیت منابع هر ۳ ساعت به ادمین"""
    db      = load_json("sources", {"list": DEFAULT_SOURCES})
    sources = db.get("list", DEFAULT_SOURCES)
    stats   = load_json("stats", DEFAULT_STATS)
    ts      = datetime.now(TEHRAN_TZ).strftime("%H:%M")

    active, error_names = 0, []
    connector = aiohttp.TCPConnector(ssl=False, limit=8)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            for url in sources[:15]:
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=6), ssl=False) as r:
                        if r.status < 400:
                            active += 1
                        else:
                            name = url.split('/')[-1][:25] or url[-25:]
                            error_names.append(f"• {name} [{r.status}]")
                except Exception:
                    name = url.split('/')[-1][:25] or url[-25:]
                    error_names.append(f"• {name} ❌")
    except Exception as e:
        logger.error(f"Source report error: {e}")
        return

    err_text = ""
    if error_names:
        err_text = "\n⚠️ <b>منابع مشکل‌دار:</b>\n" + "\n".join(error_names[:6])

    text = (
        f"📊 <b>گزارش وضعیت منابع</b>\n"
        f"🕐 ساعت {ts}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"✅ منابع فعال: <b>{active}/{min(15, len(sources))}</b>\n"
        f"❌ منابع خطا: <b>{len(error_names)}</b>\n"
        f"🆕 کانفیگ در کش: <b>{len(CONFIG_CACHE['configs']):,}</b>\n"
        f"📤 کل درخواست: <b>{stats.get('total_requests', 0):,}</b>\n"
        f"👥 کاربران: <b>{stats.get('users', 0)}</b>"
        + err_text
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Source report send error: {e}")

async def job_daily_backup(context: ContextTypes.DEFAULT_TYPE):
    for key in ["stats", "users", "groups", "referrals"]:
        p = FILES[key]
        if os.path.exists(p):
            try:
                with open(p, 'rb') as f:
                    await context.bot.send_document(chat_id=ADMIN_ID, document=f,
                        filename=os.path.basename(p), caption=f"🗄️ بکاپ — {key}")
            except Exception:
                pass

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask started | URL: {BASE_URL}")

    app = Application.builder().token(TOKEN).build()

    # ── Admin ──
    for cmd, handler in [
        ("admin", admin_cmd), ("makevip", makevip_cmd), ("unvip", unvip_cmd),
        ("viplist", viplist_cmd), ("addconfig", addconfig_cmd),
        ("postchannel", postchannel_cmd), ("addgroup", addgroup_cmd),
        ("removegroup", removegroup_cmd), ("grouplist", grouplist_cmd),
        ("backup", backup_cmd), ("logs", logs_cmd), ("health", health_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    # ── User ──
    for cmd, handler in [
        ("start", start_cmd), ("help", help_cmd), ("myid", myid_cmd),
        ("invite", invite_cmd), ("ask", ask_cmd), ("ping", ping_cmd),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text
    ))

    # ── Jobs ──
    sett = load_json("settings", DEFAULT_SETTINGS)
    app.job_queue.run_once(job_cache_refresh, when=5)
    app.job_queue.run_repeating(job_cache_refresh,
        interval=sett.get("cache_interval", 1800), first=30)
    app.job_queue.run_repeating(job_auto_channel,
        interval=sett.get("channel_interval", 600), first=60)
    app.job_queue.run_repeating(job_auto_groups,
        interval=sett.get("group_interval", 10800), first=120)
    # گزارش منابع هر ۳ ساعت
    app.job_queue.run_repeating(job_source_report, interval=10800, first=300)
    # بکاپ روزانه
    tz = pytz.timezone('Asia/Tehran')
    app.job_queue.run_daily(job_daily_backup,
        time=datetime.now(tz).replace(hour=23, minute=30, second=0).timetz())

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🚀 Config Collector Bot v5.0 — FULL")
    logger.info(f"🔐 Admin: {ADMIN_ID}")
    logger.info(f"📡 Channel: {CHANNEL_ID} (10 min)")
    logger.info(f"📊 Source report: every 3 hours")
    logger.info(f"🌍 Country filter: {len(COUNTRY_MAP)} countries")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
