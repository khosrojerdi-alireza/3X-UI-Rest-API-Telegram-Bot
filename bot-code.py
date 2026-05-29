import os, json, uuid, logging, qrcode, io, datetime, urllib3, re, time
from dotenv import load_dotenv
import requests

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
#  مراحل مکالمه
# ══════════════════════════════════════════════════════════════════
(
    SETUP_URL, SETUP_USER, SETUP_PASS,
    ADMIN_ADD_EMAIL, ADMIN_ADD_TRAFFIC, ADMIN_ADD_EXPIRE,
    ADMIN_DEL_EMAIL, ADMIN_RESET_EMAIL, ADMIN_SEARCH_EMAIL,
    USER_REG_EMAIL,
    BUY_RECEIPT,
    PLAN_NAME, PLAN_PRICE, PLAN_DAYS, PLAN_GB,
    SET_CARD,
) = range(16)

# ══════════════════════════════════════════════════════════════════
#  ذخیره‌سازی
# ══════════════════════════════════════════════════════════════════
SETTINGS:    dict = {}
SESSIONS:    dict = {}
ADMINS:      set  = set()   # chat_id هایی که setup کرده‌اند و مجاز هستند
ALLOWED_IDS: set  = set()   # از .env — اگه خالی باشد هیچ‌کس نمی‌تواند setup کند
USER_EMAILS: dict = {}
PLANS:       dict = {}
ORDERS:      dict = {}
CARD_NUMBER: str  = ""
CARD_OWNER:  str  = ""

# rate-limit: آخرین زمان ارسال رسید هر کاربر
LAST_RECEIPT: dict = {}   # cid -> timestamp
RECEIPT_COOLDOWN = 60     # ثانیه

# ══════════════════════════════════════════════════════════════════
#  گارد امنیتی
# ══════════════════════════════════════════════════════════════════

def is_admin(cid: int) -> bool:
    """آیا این chat_id مجاز به عملیات ادمین است؟"""
    return cid in ADMINS and cid in SETTINGS

def is_allowed_to_setup(cid: int) -> bool:
    """آیا این chat_id می‌تواند /setup بزند؟"""
    if not ALLOWED_IDS:
        # اگه لیست خالی باشد → هیچ‌کس مجاز نیست (باید در .env تنظیم شود)
        return False
    return cid in ALLOWED_IDS

def sanitize_email(email: str) -> str:
    """پاک‌سازی ورودی ایمیل/نام کاربری — فقط حروف، اعداد، نقطه، خط تیره، زیرخط"""
    return re.sub(r"[^\w\.\-@]", "", email.strip())[:64]

def safe_int(val, default=0) -> int:
    try:    return int(val)
    except: return default

def safe_float(val, default=0.0) -> float:
    try:    return float(val)
    except: return default

# ══════════════════════════════════════════════════════════════════
#  لایه API
# ══════════════════════════════════════════════════════════════════

def _base(cid): return SETTINGS[cid]["url"].rstrip("/")
def _s(cid):    return SESSIONS.get(cid)

def api_login(cid):
    cfg = SETTINGS[cid]
    s = requests.Session()
    s.verify = False
    try:
        r = s.post(f"{_base(cid)}/login",
                   json={"username": cfg["user"], "password": cfg["pass"]}, timeout=10)
        d = r.json()
        if d.get("success"):
            SESSIONS[cid] = s
            logger.info(f"[LOGIN] admin {cid} logged in to panel")
            return {"ok": True}
        return {"ok": False, "msg": d.get("msg", "خطا")}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

def _get(cid, path):
    s = _s(cid)
    if not s: return {"success": False, "msg": "احراز هویت نشده"}
    try:    return s.get(f"{_base(cid)}{path}", timeout=15).json()
    except Exception as e: return {"success": False, "msg": str(e)}

def _post(cid, path, payload=None):
    s = _s(cid)
    if not s: return {"success": False, "msg": "احراز هویت نشده"}
    try:    return s.post(f"{_base(cid)}{path}", json=payload or {}, timeout=15).json()
    except Exception as e: return {"success": False, "msg": str(e)}

def api_inbounds(cid):           return _get(cid, "/panel/api/inbounds/list")
def api_inbound(cid, iid):       return _get(cid, f"/panel/api/inbounds/get/{safe_int(iid)}")
def api_status(cid):             return _get(cid, "/panel/api/server/status")
def api_client_traffic(cid, em): return _get(cid, f"/panel/api/inbounds/getClientTraffics/{em}")
def api_client_ips(cid, em):     return _get(cid, f"/panel/api/inbounds/clientIps/{em}")
def api_online(cid):             return _post(cid, "/panel/api/inbounds/onlines")
def api_backup(cid):             return _get(cid, "/panel/api/inbounds/createbackup")
def api_reset_all(cid, iid):     return _post(cid, f"/panel/api/inbounds/resetAllTraffics/{safe_int(iid)}")
def api_del_depleted(cid, iid):  return _post(cid, f"/panel/api/inbounds/delDepletedClients/{safe_int(iid)}")
def api_reset_client(cid, iid, em): return _post(cid, f"/panel/api/inbounds/{safe_int(iid)}/resetClientTraffic/{em}")
def api_del_client(cid, iid, uid):  return _post(cid, f"/panel/api/inbounds/{safe_int(iid)}/delClient/{uid}")

def api_add_client(cid, iid, email, total_gb, expire_days, flow="xtls-rprx-vision"):
    expire_ms = 0
    if expire_days > 0:
        expire_ms = int((datetime.datetime.now() + datetime.timedelta(days=expire_days)).timestamp() * 1000)
    cl = {
        "id": str(uuid.uuid4()), "alterId": 0, "email": email,
        "limitIp": 0, "totalGB": int(total_gb * 1024 ** 3),
        "expiryTime": expire_ms, "enable": True,
        "tgId": "", "subId": uuid.uuid4().hex[:16], "flow": flow, "comment": ""
    }
    logger.info(f"[ADD_CLIENT] inbound={iid} email={email} gb={total_gb} days={expire_days}")
    return _post(cid, "/panel/api/inbounds/addClient",
                 {"id": iid, "settings": json.dumps({"clients": [cl]})})

def api_update_client(cid, iid, client_uuid, email, total_gb, new_expire_ms, flow="xtls-rprx-vision"):
    cl = {
        "id": client_uuid, "alterId": 0, "email": email,
        "limitIp": 0, "totalGB": int(total_gb * 1024 ** 3),
        "expiryTime": new_expire_ms, "enable": True,
        "tgId": "", "subId": uuid.uuid4().hex[:16], "flow": flow, "comment": ""
    }
    logger.info(f"[UPDATE_CLIENT] inbound={iid} email={email} new_expire={new_expire_ms}")
    return _post(cid, f"/panel/api/inbounds/updateClient/{client_uuid}",
                 {"id": iid, "settings": json.dumps({"clients": [cl]})})

# ══════════════════════════════════════════════════════════════════
#  ابزارهای کمکی
# ══════════════════════════════════════════════════════════════════

def b2s(b):
    if b == 0: return "۰ B"
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024.0: return f"{b:.2f} {u}"
        b /= 1024.0
    return f"{b:.2f} PB"

def ms2d(ms):
    if ms == 0: return "♾️ نامحدود"
    try:    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")
    except: return "نامعلوم"

def days_left(ms):
    if ms == 0: return "نامحدود"
    rem = (ms / 1000) - datetime.datetime.now().timestamp()
    if rem <= 0: return "❌ منقضی"
    return f"{int(rem // 86400)} روز"

def tbar(used, total):
    if total == 0: return "░░░░░░░░░░ نامحدود"
    p = min(used / total, 1.0); f = int(p * 10)
    return f"{'▓'*f}{'░'*(10-f)} {p*100:.0f}%"

def make_qr(text):
    buf = io.BytesIO()
    qrcode.make(text).save(buf, format="PNG")
    buf.seek(0)
    return buf

def fmt_price(p): return f"{p:,} تومان"

def _check(cid):
    """اتصال ادمین را چک و در صورت نیاز تجدید می‌کند"""
    if cid not in SETTINGS: return False
    if cid not in SESSIONS: return api_login(cid)["ok"]
    return True

def any_admin():
    for cid in ADMINS:
        if cid in SESSIONS: return cid
    return None

def ib_kb(ibs, action):
    rows = [[InlineKeyboardButton(
        f"{ib.get('remark','?')} :{ib.get('port','')}",
        callback_data=f"{action}:{ib['id']}"
    )] for ib in ibs]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
    return InlineKeyboardMarkup(rows)

def new_order_id(): return uuid.uuid4().hex[:8].upper()

def pending_count(cid):
    """تعداد سفارش‌های در انتظار یک کاربر"""
    return sum(1 for o in ORDERS.values() if o["user_cid"] == cid and o["status"] == "pending")

# ══════════════════════════════════════════════════════════════════
#  منوها
# ══════════════════════════════════════════════════════════════════

ADMIN_MENU = [
    ["📊 وضعیت سرور", "🔗 اینباندها"],
    ["👥 مدیریت کلاینت‌ها", "📈 ترافیک کلاینت"],
    ["🌐 کلاینت‌های آنلاین", "💾 پشتیبان‌گیری"],
    ["🛒 مدیریت فروش", "⚙️ تنظیمات پنل"],
]
USER_MENU = [
    ["📊 وضعیت اشتراک", "🛒 خرید / تمدید"],
    ["📱 QR کد", "📋 اطلاعات اتصال"],
    ["🔔 وضعیت سفارش‌ها", "🔄 تغییر ایمیل"],
]

def adm_kb(): return ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
def usr_kb(): return ReplyKeyboardMarkup(USER_MENU,  resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 ورود ادمین",  callback_data="mode:admin")],
        [InlineKeyboardButton("👤 ورود مشتری", callback_data="mode:user")],
    ])
    await update.message.reply_text(
        "🤖 *ربات مدیریت پنل 3X-UI*\n\nلطفاً نقش خود را انتخاب کنید:",
        parse_mode="Markdown", reply_markup=kb)

async def mode_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); cid = q.message.chat_id

    if q.data == "mode:admin":
        if is_admin(cid):
            await q.edit_message_text("✅ به پنل ادمین خوش آمدید!")
            await ctx.bot.send_message(cid, "منوی ادمین:", reply_markup=adm_kb())
        elif not ALLOWED_IDS:
            await q.edit_message_text(
                "⛔ دسترسی ادمین غیرفعال است.\n\n"
                "مدیر سیستم باید `ALLOWED_ADMINS` را در فایل `.env` تنظیم کند.",
                parse_mode="Markdown")
        elif cid not in ALLOWED_IDS:
            logger.warning(f"[SECURITY] unauthorized admin attempt: {cid}")
            await q.edit_message_text("⛔ شما مجاز به ورود ادمین نیستید.")
        else:
            await q.edit_message_text("⚙️ برای تنظیم پنل دستور /setup را بزنید.")

    elif q.data == "mode:user":
        if cid in USER_EMAILS:
            await q.edit_message_text(f"✅ خوش برگشتید!\nایمیل: `{USER_EMAILS[cid]}`",
                                      parse_mode="Markdown")
            await ctx.bot.send_message(cid, "منوی مشتری:", reply_markup=usr_kb())
        else:
            await q.edit_message_text(
                "👤 *ورود مشتری*\n\nایمیل اشتراک VPN خود را وارد کنید:",
                parse_mode="Markdown")
            ctx.user_data["conv_state"] = USER_REG_EMAIL

# ══════════════════════════════════════════════════════════════════
#  Setup ادمین — با چک مجوز
# ══════════════════════════════════════════════════════════════════

async def setup_start(u, ctx):
    cid = u.effective_chat.id

    if not ALLOWED_IDS:
        await u.message.reply_text(
            "⛔ *دسترسی غیرمجاز*\n\n"
            "`ALLOWED_ADMINS` در فایل `.env` تنظیم نشده.\n"
            "تا زمانی که این مقدار خالی باشد، هیچ‌کس نمی‌تواند ادمین شود.",
            parse_mode="Markdown")
        return ConversationHandler.END

    if cid not in ALLOWED_IDS:
        logger.warning(f"[SECURITY] unauthorized /setup attempt from {cid}")
        await u.message.reply_text("⛔ شما مجاز به اجرای این دستور نیستید.")
        return ConversationHandler.END

    await u.message.reply_text(
        "⚙️ *تنظیم پنل 3X-UI*\n\nآدرس پنل را وارد کنید:\nمثال: `http://1.2.3.4:54321`",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return SETUP_URL

async def setup_url(u, ctx):
    ctx.user_data["su"] = u.message.text.strip()
    await u.message.reply_text("👤 نام کاربری:")
    return SETUP_USER

async def setup_user(u, ctx):
    ctx.user_data["su2"] = u.message.text.strip()
    await u.message.reply_text("🔑 رمز عبور:")
    return SETUP_PASS

async def setup_pass(u, ctx):
    cid = u.effective_chat.id
    # چک دوباره — جلوگیری از race condition
    if cid not in ALLOWED_IDS:
        await u.message.reply_text("⛔ دسترسی غیرمجاز.")
        return ConversationHandler.END

    SETTINGS[cid] = {
        "url":  ctx.user_data["su"],
        "user": ctx.user_data["su2"],
        "pass": u.message.text.strip()
    }
    await u.message.reply_text("🔄 در حال اتصال...")
    res = api_login(cid)
    if res["ok"]:
        ADMINS.add(cid)
        logger.info(f"[SETUP] admin {cid} configured panel: {ctx.user_data['su']}")
        await u.message.reply_text("✅ اتصال برقرار شد!", reply_markup=adm_kb())
    else:
        del SETTINGS[cid]
        await u.message.reply_text(f"❌ خطا: {res['msg']}\nمجدداً /setup بزنید.")
    return ConversationHandler.END

async def setup_cancel(u, ctx):
    await u.message.reply_text("❌ لغو شد.")
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════
#  ══ پنل ادمین ══
# ══════════════════════════════════════════════════════════════════

def _adm_guard(cid):
    """True اگه ادمین معتبر و متصل باشد"""
    return is_admin(cid) and _check(cid)

async def adm_status(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    await u.message.reply_text("⏳ دریافت اطلاعات...")
    res = api_status(cid)
    if not res.get("success"): await u.message.reply_text(f"❌ {res.get('msg')}"); return
    o = res.get("obj", {})
    cpu = o.get("cpu", 0); mem = o.get("mem", {})
    ni = o.get("netIO", {}); nt = o.get("netTraffic", {})
    xr = o.get("xray", {}); up = o.get("uptime", 0)
    h, r = divmod(up, 3600); m = r // 60
    await u.message.reply_text(
        f"🖥️ *وضعیت سرور*\n\n"
        f"🔲 CPU: `{cpu:.1f}%`\n"
        f"💾 RAM: `{b2s(mem.get('current',0))} / {b2s(mem.get('total',0))}`\n"
        f"⏱ آپتایم: `{h}h {m}m`\n\n"
        f"📡 *ترافیک لحظه‌ای*\n  ↑`{b2s(ni.get('up',0))}/s` ↓`{b2s(ni.get('down',0))}/s`\n\n"
        f"📊 *کل ترافیک*\n  ↑`{b2s(nt.get('sent',0))}` ↓`{b2s(nt.get('recv',0))}`\n\n"
        f"⚡ Xray: `{xr.get('state','?')}` v`{xr.get('version','?')}`",
        parse_mode="Markdown")

async def adm_inbounds(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    res = api_inbounds(cid)
    if not res.get("success"): await u.message.reply_text(f"❌ {res.get('msg')}"); return
    ibs = res.get("obj", [])
    if not ibs: await u.message.reply_text("⚠️ اینباندی یافت نشد."); return
    txt = f"🔗 *اینباندها* ({len(ibs)} عدد)\n\n"
    for ib in ibs:
        try: cls = json.loads(ib.get("settings", "{}")).get("clients", [])
        except: cls = []
        st = "✅" if ib.get("enable") else "❌"
        txt += (f"{st} *{ib.get('remark','?')}*\n"
                f"  🔌 `{ib.get('port','?')}` | `{ib.get('protocol','?')}`\n"
                f"  👥 `{len(cls)}` | ↑`{b2s(ib.get('up',0))}` ↓`{b2s(ib.get('down',0))}`\n\n")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 جزئیات اینباند", callback_data="ib:pick")]])
    await u.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

async def adm_clients(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن کلاینت",         callback_data="cl:add")],
        [InlineKeyboardButton("🔍 جستجوی کلاینت",         callback_data="cl:search")],
        [InlineKeyboardButton("🗑 حذف کلاینت",             callback_data="cl:del")],
        [InlineKeyboardButton("🔄 ریست ترافیک کلاینت",    callback_data="cl:reset")],
        [InlineKeyboardButton("♻️ ریست ترافیک همه",       callback_data="cl:resetall")],
        [InlineKeyboardButton("🧹 حذف کلاینت‌های منقضی", callback_data="cl:deldep")],
    ])
    await u.message.reply_text("👥 *مدیریت کلاینت‌ها*", parse_mode="Markdown", reply_markup=kb)

async def adm_traffic_ask(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    await u.message.reply_text("📈 ایمیل کلاینت:")
    ctx.user_data["conv_state"] = ADMIN_SEARCH_EMAIL

async def adm_online(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    res = api_online(cid)
    if not res.get("success"): await u.message.reply_text(f"❌ {res.get('msg')}"); return
    cls = res.get("obj") or []
    if not cls: await u.message.reply_text("😴 هیچ کلاینتی آنلاین نیست."); return
    txt = f"🌐 *آنلاین‌ها* ({len(cls)})\n\n" + "\n".join(f"  • `{c}`" for c in cls)
    await u.message.reply_text(txt, parse_mode="Markdown")

async def adm_backup(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    await u.message.reply_text("⏳ در حال ایجاد بکاپ...")
    res = api_backup(cid)
    logger.info(f"[BACKUP] admin {cid} — success={res.get('success')}")
    await u.message.reply_text("✅ بکاپ ایجاد شد." if res.get("success") else f"❌ {res.get('msg')}")

async def adm_settings(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    cfg = SETTINGS.get(cid, {})
    await u.message.reply_text(
        f"⚙️ *تنظیمات*\n\n"
        f"🌐 `{cfg.get('url','—')}`\n👤 `{cfg.get('user','—')}`\n"
        f"🔗 {'✅ متصل' if cid in SESSIONS else '❌ قطع'}\n"
        f"💳 کارت: `{CARD_NUMBER or 'تنظیم نشده'}` — {CARD_OWNER or ''}\n\n"
        f"/setup — تغییر پنل\n/setcard — تنظیم کارت\n/reconnect — اتصال مجدد",
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════
#  مدیریت فروش (ادمین)
# ══════════════════════════════════════════════════════════════════

async def adm_sales(u, ctx):
    cid = u.effective_chat.id
    if not _adm_guard(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    pending = [oid for oid, o in ORDERS.items() if o["status"] == "pending"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 تعرفه‌ها ({len(PLANS)})",            callback_data="sales:plans")],
        [InlineKeyboardButton(f"⏳ رسیدهای در انتظار ({len(pending)})", callback_data="sales:pending")],
        [InlineKeyboardButton("📊 همه سفارش‌ها",                        callback_data="sales:all")],
        [InlineKeyboardButton("➕ افزودن تعرفه",                        callback_data="sales:addplan")],
        [InlineKeyboardButton("💳 تنظیم شماره کارت",                   callback_data="sales:setcard")],
    ])
    await u.message.reply_text("🛒 *مدیریت فروش*", parse_mode="Markdown", reply_markup=kb)

# ══════════════════════════════════════════════════════════════════
#  setcard
# ══════════════════════════════════════════════════════════════════

async def setcard_start(u, ctx):
    cid = u.effective_chat.id
    if not is_admin(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return ConversationHandler.END
    await u.message.reply_text(
        "💳 شماره کارت را وارد کنید:\n(خط دوم اختیاری: نام صاحب کارت)\n\nمثال:\n`6037991234567890\nعلی محمدی`",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return SET_CARD

async def setcard_done(u, ctx):
    global CARD_NUMBER, CARD_OWNER
    cid = u.effective_chat.id
    if not is_admin(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return ConversationHandler.END
    parts = u.message.text.strip().split("\n")
    CARD_NUMBER = re.sub(r"\D", "", parts[0])   # فقط اعداد
    CARD_OWNER  = parts[1].strip() if len(parts) > 1 else ""
    if len(CARD_NUMBER) not in (16, 19):
        await u.message.reply_text("❌ شماره کارت باید ۱۶ رقم باشد.")
        return SET_CARD
    logger.info(f"[CARD] admin {cid} updated card: {CARD_NUMBER[:4]}****")
    await u.message.reply_text(
        f"✅ کارت ثبت شد:\n💳 `{CARD_NUMBER}`\n👤 {CARD_OWNER}",
        parse_mode="Markdown", reply_markup=adm_kb())
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════
#  تعرفه‌ها
# ══════════════════════════════════════════════════════════════════

def plans_text():
    if not PLANS: return "📭 هیچ تعرفه‌ای تعریف نشده."
    txt = "📋 *تعرفه‌های فعلی:*\n\n"
    for pid, p in PLANS.items():
        gb = "نامحدود" if p["gb"] == 0 else f"{p['gb']} GB"
        txt += (f"🔹 *{p['name']}*\n"
                f"  ⏱ {p['days']} روز | 📦 {gb}\n"
                f"  💰 {fmt_price(p['price'])}\n\n")
    return txt

async def show_plans_admin(q, ctx):
    kb = InlineKeyboardMarkup([
        *[[InlineKeyboardButton(f"🗑 حذف: {p['name']}", callback_data=f"sales:delplan:{pid}")]
          for pid, p in PLANS.items()],
        [InlineKeyboardButton("➕ افزودن تعرفه", callback_data="sales:addplan")],
        [InlineKeyboardButton("🔙 بازگشت",        callback_data="back")],
    ])
    await q.edit_message_text(plans_text(), parse_mode="Markdown", reply_markup=kb)

async def plan_add_start(q, ctx):
    await q.edit_message_text(
        "➕ *افزودن تعرفه جدید*\n\nنام تعرفه را وارد کنید:\nمثال: یک ماهه",
        parse_mode="Markdown")
    ctx.user_data["conv_state"] = PLAN_NAME

async def plan_name_recv(u, ctx):
    ctx.user_data["pn"] = u.message.text.strip()[:50]
    await u.message.reply_text("💰 قیمت به تومان:")
    ctx.user_data["conv_state"] = PLAN_PRICE

async def plan_price_recv(u, ctx):
    v = safe_int(u.message.text.replace(",","").replace("،","").strip(), -1)
    if v < 0:
        await u.message.reply_text("❌ عدد معتبر وارد کنید:"); return
    ctx.user_data["pp"] = v
    await u.message.reply_text("📅 تعداد روز:")
    ctx.user_data["conv_state"] = PLAN_DAYS

async def plan_days_recv(u, ctx):
    v = safe_int(u.message.text.strip(), -1)
    if v <= 0:
        await u.message.reply_text("❌ عدد مثبت وارد کنید:"); return
    ctx.user_data["pd"] = v
    await u.message.reply_text("📦 حجم GB (برای نامحدود: 0):")
    ctx.user_data["conv_state"] = PLAN_GB

async def plan_gb_recv(u, ctx):
    cid = u.effective_chat.id
    v = safe_float(u.message.text.strip(), -1)
    if v < 0:
        await u.message.reply_text("❌ عدد معتبر (0 یا بیشتر):"); return
    ctx.user_data["pgb"] = v
    if not _adm_guard(cid):
        await u.message.reply_text("⛔ دسترسی ندارید."); ctx.user_data.pop("conv_state", None); return
    res = api_inbounds(cid)
    if not res.get("success"):
        await u.message.reply_text(f"❌ {res.get('msg')}"); return
    ibs = res.get("obj", [])
    if not ibs:
        await u.message.reply_text("❌ هیچ اینباندی در پنل نیست."); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{ib.get('remark','?')} :{ib.get('port','')}",
         callback_data=f"pickib:{ib['id']}")] for ib in ibs
    ])
    await u.message.reply_text("🔌 اینباند پیش‌فرض این تعرفه را انتخاب کنید:", reply_markup=kb)
    # conv_state را پاک می‌کنیم تا callback انتخاب اینباند کار کند
    ctx.user_data.pop("conv_state", None)

# ══════════════════════════════════════════════════════════════════
#  پنل مشتری
# ══════════════════════════════════════════════════════════════════

def _userinfo(email):
    admin = any_admin()
    if not admin: return None
    res = api_client_traffic(admin, email)
    return res.get("obj") if res.get("success") and res.get("obj") else None

def _sub_link(email):
    admin = any_admin()
    if not admin: return None
    return f"{SETTINGS[admin]['url'].rstrip('/')}/sub/{email}"

async def usr_status(u, ctx):
    cid = u.effective_chat.id
    email = USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    c = _userinfo(email)
    if not c: await u.message.reply_text(f"❌ ایمیل `{email}` یافت نشد.", parse_mode="Markdown"); return
    up = c.get("up", 0); dn = c.get("down", 0); used = up+dn
    tot = c.get("total", 0); exp = c.get("expiryTime", 0)
    rem = max(0, tot-used) if tot > 0 else 0
    await u.message.reply_text(
        f"📊 *وضعیت اشتراک*\n\n"
        f"📧 `{email}`\n"
        f"🔘 {'✅ فعال' if c.get('enable') else '❌ غیرفعال'}\n\n"
        f"📦 *ترافیک*\n"
        f"  مصرف: `{b2s(used)}`\n"
        f"  باقی: `{b2s(rem) if tot>0 else '♾️ نامحدود'}`\n"
        f"  کل: `{b2s(tot) if tot>0 else '♾️ نامحدود'}`\n"
        f"  {tbar(used,tot)}\n\n"
        f"📅 انقضا: `{ms2d(exp)}` ({days_left(exp)})\n"
        f"↑`{b2s(up)}` ↓`{b2s(dn)}`",
        parse_mode="Markdown")

async def usr_qr(u, ctx):
    cid = u.effective_chat.id
    email = USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    link = _sub_link(email)
    if not link: await u.message.reply_text("⚠️ سرور در دسترس نیست."); return
    await ctx.bot.send_photo(cid, make_qr(link),
        caption=f"📱 *QR کد اشتراک*\n\n🔗 `{link}`\n\nبا اپ VPN اسکن کنید.",
        parse_mode="Markdown")

async def usr_conn(u, ctx):
    cid = u.effective_chat.id
    email = USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    admin = any_admin()
    if not admin: await u.message.reply_text("⚠️ سرور در دسترس نیست."); return
    res = api_inbounds(admin)
    if not res.get("success"): await u.message.reply_text("❌ خطا"); return
    fib = fcl = None
    for ib in res.get("obj", []):
        try:
            cls = json.loads(ib.get("settings","{}")).get("clients",[])
            for cl in cls:
                if cl.get("email") == email: fib=ib; fcl=cl; break
        except: pass
        if fib: break
    if not fib:
        await u.message.reply_text(f"❌ کلاینت `{email}` پیدا نشد.", parse_mode="Markdown"); return
    ip = SETTINGS[admin]["url"].split(":")[1].lstrip("/")
    await u.message.reply_text(
        f"📋 *اطلاعات اتصال*\n\n"
        f"📧 `{email}`\n🌐 `{ip}`\n"
        f"🔌 پورت: `{fib.get('port','?')}`\n"
        f"🔒 پروتکل: `{fib.get('protocol','?')}`\n"
        f"🆔 UUID: `{fcl.get('id','?')}`\n\n"
        f"🔗 لینک sub:\n`{_sub_link(email)}`",
        parse_mode="Markdown")

async def usr_orders(u, ctx):
    cid = u.effective_chat.id
    my = [o for o in ORDERS.values() if o["user_cid"] == cid]
    if not my: await u.message.reply_text("📭 سفارشی ثبت نشده."); return
    st_map = {"pending":"⏳ در انتظار","approved":"✅ تأیید شده","rejected":"❌ رد شده"}
    txt = "📦 *سفارش‌های شما:*\n\n"
    for o in sorted(my, key=lambda x: x["ts"], reverse=True)[:10]:
        p = PLANS.get(o["plan_id"], {})
        ts = datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
        txt += (f"🔹 #{o['id']} — {p.get('name','?')}\n"
                f"  {st_map.get(o['status'],'?')} | {ts}\n\n")
    await u.message.reply_text(txt, parse_mode="Markdown")

async def usr_change_email(u, ctx):
    await u.message.reply_text("🔄 ایمیل جدید اشتراک خود را وارد کنید:",
                                reply_markup=ReplyKeyboardRemove())
    ctx.user_data["conv_state"] = USER_REG_EMAIL

# ══════════════════════════════════════════════════════════════════
#  جریان خرید
# ══════════════════════════════════════════════════════════════════

async def usr_buy(u, ctx):
    cid = u.effective_chat.id
    if not PLANS:
        await u.message.reply_text("😔 در حال حاضر تعرفه‌ای فعال نیست."); return
    if not CARD_NUMBER:
        await u.message.reply_text("⚠️ سیستم پرداخت هنوز راه‌اندازی نشده."); return
    rows = []
    for pid, p in PLANS.items():
        gb = "∞" if p["gb"] == 0 else f"{p['gb']}GB"
        rows.append([InlineKeyboardButton(
            f"🔹 {p['name']} — {p['days']}روز {gb} — {fmt_price(p['price'])}",
            callback_data=f"buy:{pid}")])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="back")])
    await u.message.reply_text("🛒 *خرید / تمدید اشتراک*\n\nتعرفه مورد نظر را انتخاب کنید:",
                                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

async def buy_plan_selected(q, ctx, pid):
    cid = q.message.chat_id
    # چک وجود plan_id در دیکشنری (نه trust blindly از callback)
    p = PLANS.get(pid)
    if not p:
        await q.edit_message_text("❌ تعرفه پیدا نشد یا حذف شده.")
        return
    ctx.user_data["buy_plan"] = pid
    gb = "نامحدود" if p["gb"] == 0 else f"{p['gb']} GB"
    email = USER_EMAILS.get(cid)
    kind = "تمدید اشتراک" if (email and _userinfo(email)) else "خرید اشتراک جدید"
    card_fmt = " - ".join([CARD_NUMBER[i:i+4] for i in range(0, len(CARD_NUMBER), 4)])
    await q.edit_message_text(
        f"🧾 *{kind}*\n\n"
        f"📦 تعرفه: *{p['name']}*\n"
        f"⏱ مدت: {p['days']} روز\n💾 حجم: {gb}\n"
        f"💰 مبلغ: *{fmt_price(p['price'])}*\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"💳 *شماره کارت برای واریز:*\n`{card_fmt}`\n"
        f"👤 به نام: *{CARD_OWNER}*\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"پس از واریز، *تصویر رسید* را ارسال کنید. ✅",
        parse_mode="Markdown")
    ctx.user_data["conv_state"] = BUY_RECEIPT

async def receipt_received(u, ctx):
    cid = u.effective_chat.id
    pid = ctx.user_data.get("buy_plan")
    if not pid: return

    # چک وجود تعرفه
    p = PLANS.get(pid)
    if not p:
        await u.message.reply_text("❌ تعرفه انتخابی دیگر معتبر نیست. لطفاً مجدداً خرید کنید.")
        ctx.user_data.pop("conv_state", None); ctx.user_data.pop("buy_plan", None); return

    # rate-limit: جلوگیری از اسپم رسید
    now = time.time()
    last = LAST_RECEIPT.get(cid, 0)
    if now - last < RECEIPT_COOLDOWN:
        wait = int(RECEIPT_COOLDOWN - (now - last))
        await u.message.reply_text(f"⏳ لطفاً {wait} ثانیه صبر کنید و سپس رسید ارسال کنید.")
        return

    # حداکثر ۳ سفارش در انتظار برای هر کاربر
    if pending_count(cid) >= 3:
        await u.message.reply_text("⚠️ شما ۳ سفارش در انتظار تأیید دارید.\nلطفاً منتظر بررسی بمانید.")
        return

    # دریافت file_id
    if u.message.photo:
        file_id = u.message.photo[-1].file_id
    elif u.message.document:
        file_id = u.message.document.file_id
    else:
        await u.message.reply_text("📸 لطفاً تصویر رسید را ارسال کنید."); return

    LAST_RECEIPT[cid] = now
    oid = new_order_id()
    email = USER_EMAILS.get(cid, "ثبت‌نشده")
    ORDERS[oid] = {
        "id": oid, "user_cid": cid, "plan_id": pid,
        "ts": now, "status": "pending",
        "receipt_file_id": file_id, "email": email,
    }
    ctx.user_data.pop("conv_state", None)
    ctx.user_data.pop("buy_plan", None)

    logger.info(f"[ORDER] new order {oid} from user {cid} email={email} plan={pid}")

    await u.message.reply_text(
        f"✅ *رسید شما دریافت شد!*\n\n"
        f"🔖 شماره سفارش: `#{oid}`\n"
        f"📦 تعرفه: {p['name']}\n"
        f"⏳ در حال بررسی توسط ادمین...",
        parse_mode="Markdown", reply_markup=usr_kb())

    # ارسال به همه ادمین‌ها (فقط ادمین‌های واقعی)
    gb = "نامحدود" if p.get("gb",0)==0 else f"{p['gb']} GB"
    admin_txt = (
        f"🔔 *سفارش جدید!*\n\n"
        f"🔖 #{oid}\n👤 `{cid}`\n📧 `{email}`\n"
        f"📦 {p['name']} — {p['days']} روز — {gb}\n"
        f"💰 {fmt_price(p['price'])}\n"
        f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و فعال‌سازی", callback_data=f"order:approve:{oid}")],
        [InlineKeyboardButton("❌ رد کردن",            callback_data=f"order:reject:{oid}")],
    ])
    for admin_cid in ADMINS:
        try:
            await ctx.bot.send_photo(admin_cid, photo=file_id,
                                     caption=admin_txt, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.warning(f"[ORDER] send to admin {admin_cid} failed: {e}")

# ══════════════════════════════════════════════════════════════════
#  پردازش سفارش توسط ادمین
# ══════════════════════════════════════════════════════════════════

async def order_approve(q, ctx, oid):
    cid = q.message.chat_id

    # ✅ چک ادمین بودن — مهم‌ترین چک امنیتی
    if not is_admin(cid):
        logger.warning(f"[SECURITY] non-admin {cid} tried to approve order {oid}")
        await q.answer("⛔ شما مجاز به این عملیات نیستید.", show_alert=True)
        return

    o = ORDERS.get(oid)
    if not o:
        await q.edit_message_caption("❌ سفارش یافت نشد."); return
    if o["status"] != "pending":
        await q.edit_message_caption(f"⚠️ این سفارش قبلاً «{o['status']}» شده."); return

    p = PLANS.get(o["plan_id"])
    if not p:
        await q.edit_message_caption("❌ تعرفه این سفارش دیگر وجود ندارد."); return

    email = o.get("email", "")
    if not email or email == "ثبت‌نشده":
        await q.edit_message_caption("❌ ایمیل کاربر ثبت نشده."); return

    user_cid = o["user_cid"]
    days = p.get("days", 30)
    gb   = p.get("gb", 0)
    iid  = p.get("inbound_id")

    if not iid:
        await q.edit_message_caption("❌ اینباند تعرفه مشخص نیست."); return

    await q.edit_message_caption(f"⏳ در حال پردازش #{oid}...")

    # بررسی کلاینت موجود
    existing = existing_ib = None
    res_ibs = api_inbounds(cid)
    if res_ibs.get("success"):
        for ib in res_ibs.get("obj", []):
            try:
                cls = json.loads(ib.get("settings","{}")).get("clients",[])
                for cl in cls:
                    if cl.get("email") == email:
                        existing = cl; existing_ib = ib; break
            except: pass
            if existing: break

    now_ms = int(datetime.datetime.now().timestamp() * 1000)
    new_expire_ms = now_ms + int(days * 86400 * 1000)

    if existing and existing_ib:
        old_exp = existing.get("expiryTime", 0)
        if old_exp > now_ms:   # هنوز وقت داره → از انتها تمدید کن
            new_expire_ms = old_exp + int(days * 86400 * 1000)
        old_gb = existing.get("totalGB", 0)
        new_gb_bytes = (old_gb + int(gb * 1024**3)) if gb > 0 else 0
        res = api_update_client(cid, existing_ib["id"], existing["id"],
                                email, new_gb_bytes / 1024**3, new_expire_ms)
        action_txt = f"🔄 تمدید شد\n📅 تا: {ms2d(new_expire_ms)}"
    else:
        res = api_add_client(cid, iid, email, gb, days)
        action_txt = f"✅ کلاینت جدید ساخته شد\n📅 {days} روز"

    if not res.get("success"):
        logger.error(f"[ORDER] panel error for order {oid}: {res.get('msg')}")
        await ctx.bot.send_message(cid, f"❌ خطا در پنل: {res.get('msg')}")
        return

    ORDERS[oid]["status"] = "approved"
    ORDERS[oid]["approved_by"] = cid
    ORDERS[oid]["approved_at"] = time.time()
    logger.info(f"[ORDER] {oid} approved by admin {cid}")

    await q.edit_message_caption(
        f"✅ *سفارش #{oid} تأیید شد*\n\n{action_txt}",
        parse_mode="Markdown")

    sub = _sub_link(email)
    await ctx.bot.send_message(user_cid,
        f"🎉 *اشتراک شما فعال شد!*\n\n"
        f"🔖 سفارش: `#{oid}`\n📦 {p['name']}\n{action_txt}\n\n"
        f"🔗 لینک اشتراک:\n`{sub}`",
        parse_mode="Markdown")

async def order_reject(q, ctx, oid):
    cid = q.message.chat_id

    # ✅ چک ادمین بودن
    if not is_admin(cid):
        logger.warning(f"[SECURITY] non-admin {cid} tried to reject order {oid}")
        await q.answer("⛔ شما مجاز به این عملیات نیستید.", show_alert=True)
        return

    o = ORDERS.get(oid)
    if not o:
        await q.edit_message_caption("❌ سفارش یافت نشد."); return
    if o["status"] != "pending":
        await q.edit_message_caption(f"⚠️ این سفارش قبلاً «{o['status']}» شده."); return

    ORDERS[oid]["status"] = "rejected"
    ORDERS[oid]["rejected_by"] = cid
    ORDERS[oid]["rejected_at"] = time.time()
    logger.info(f"[ORDER] {oid} rejected by admin {cid}")

    p = PLANS.get(o["plan_id"], {})
    await q.edit_message_caption(f"❌ سفارش #{oid} رد شد.")
    await ctx.bot.send_message(o["user_cid"],
        f"❌ *سفارش شما رد شد*\n\n🔖 #{oid} — {p.get('name','?')}\n\n"
        f"در صورت سوال با پشتیبانی تماس بگیرید.",
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════
#  Callback مرکزی
# ══════════════════════════════════════════════════════════════════

async def cb_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat_id
    d   = q.data or ""

    # ── انتخاب نقش ──────────────────────────────────────────────
    if d in ("mode:admin", "mode:user"):
        return await mode_cb(update, ctx)

    if d == "back":
        await q.edit_message_text("🏠 بازگشت."); return

    # ── خرید (همه کاربران) ──────────────────────────────────────
    if d.startswith("buy:"):
        pid = d[4:]
        return await buy_plan_selected(q, ctx, pid)

    # ── سفارش‌ها — فقط ادمین واقعی ─────────────────────────────
    if d.startswith("order:approve:"):
        return await order_approve(q, ctx, d.split(":")[-1])
    if d.startswith("order:reject:"):
        return await order_reject(q, ctx, d.split(":")[-1])

    # ── از اینجا به بعد همه عملیات ادمین هستند ──────────────────
    if not is_admin(cid):
        logger.warning(f"[SECURITY] non-admin {cid} tried callback: {d}")
        await q.edit_message_text("⛔ دسترسی ندارید.")
        return

    if not _check(cid):
        await q.edit_message_text("❌ اتصال قطع است. /reconnect بزنید.")
        return

    # ── اینباند ─────────────────────────────────────────────────
    if d == "ib:pick":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند را انتخاب کنید:", reply_markup=ib_kb(res["obj"], "ib:show"))
        return

    if d.startswith("ib:show:"):
        iid = safe_int(d.split(":")[2])
        res = api_inbound(cid, iid)
        if not res.get("success"): await q.edit_message_text(f"❌ {res.get('msg')}"); return
        ib = res["obj"]
        try: cls = json.loads(ib.get("settings","{}")).get("clients",[])
        except: cls = []
        txt = (f"📋 *{ib.get('remark','?')}*\n\n"
               f"🔌 `{ib.get('port')}` | `{ib.get('protocol')}`\n"
               f"👥 {len(cls)} | ↑`{b2s(ib.get('up',0))}` ↓`{b2s(ib.get('down',0))}`\n"
               f"{'✅ فعال' if ib.get('enable') else '❌ غیرفعال'}\n\n*کلاینت‌ها:*\n")
        for c in cls[:25]:
            used = c.get("up",0)+c.get("down",0)
            tot  = b2s(c.get("totalGB",0)) if c.get("totalGB",0) > 0 else "∞"
            en   = "✅" if c.get("enable") else "❌"
            txt += f"  {en} `{c.get('email','?')}` | {b2s(used)}/{tot} | {ms2d(c.get('expiryTime',0))}\n"
        if len(cls) > 25: txt += f"  ...و {len(cls)-25} دیگر\n"
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="ib:pick")]]))
        return

    # ── کلاینت ──────────────────────────────────────────────────
    if d == "cl:add":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند مقصد:", reply_markup=ib_kb(res["obj"], "cl:add_ib"))
        return
    if d.startswith("cl:add_ib:"):
        ctx.user_data["tib"] = safe_int(d.split(":")[2])
        await q.edit_message_text("✏️ ایمیل کلاینت جدید:")
        ctx.user_data["conv_state"] = ADMIN_ADD_EMAIL; return
    if d == "cl:search":
        await q.edit_message_text("🔍 ایمیل:"); ctx.user_data["conv_state"] = ADMIN_SEARCH_EMAIL; return
    if d == "cl:del":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند:", reply_markup=ib_kb(res["obj"], "cl:del_ib"))
        return
    if d.startswith("cl:del_ib:"):
        ctx.user_data["tib"] = safe_int(d.split(":")[2])
        await q.edit_message_text("🗑 ایمیل:"); ctx.user_data["conv_state"] = ADMIN_DEL_EMAIL; return
    if d == "cl:reset":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند:", reply_markup=ib_kb(res["obj"], "cl:reset_ib"))
        return
    if d.startswith("cl:reset_ib:"):
        ctx.user_data["tib"] = safe_int(d.split(":")[2])
        await q.edit_message_text("🔄 ایمیل:"); ctx.user_data["conv_state"] = ADMIN_RESET_EMAIL; return
    if d == "cl:resetall":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند:", reply_markup=ib_kb(res["obj"], "cl:resetall_ib"))
        return
    if d.startswith("cl:resetall_ib:"):
        iid = safe_int(d.split(":")[2]); res = api_reset_all(cid, iid)
        await q.edit_message_text("✅ ریست شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d == "cl:deldep":
        res = api_inbounds(cid)
        if res.get("success"):
            await q.edit_message_text("اینباند:", reply_markup=ib_kb(res["obj"], "cl:deldep_ib"))
        return
    if d.startswith("cl:deldep_ib:"):
        iid = safe_int(d.split(":")[2]); res = api_del_depleted(cid, iid)
        await q.edit_message_text("✅ حذف شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d.startswith("okdel:"):
        parts = d.split(":"); iid = safe_int(parts[1]); uid = parts[2]
        # اعتبارسنجی uid — باید UUID باشد
        if not re.match(r"^[0-9a-f\-]{32,36}$", uid):
            await q.edit_message_text("❌ شناسه نامعتبر."); return
        res = api_del_client(cid, iid, uid)
        logger.info(f"[DEL_CLIENT] admin {cid} deleted client uuid={uid} from inbound {iid}")
        await q.edit_message_text("✅ حذف شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d.startswith("nodels:"):
        await q.edit_message_text("❌ لغو شد."); return

    # ── فروش ────────────────────────────────────────────────────
    if d == "sales:plans":   return await show_plans_admin(q, ctx)
    if d == "sales:addplan": return await plan_add_start(q, ctx)
    if d.startswith("sales:delplan:"):
        pid = d.split(":")[-1]
        if pid in PLANS:
            name = PLANS[pid]["name"]; del PLANS[pid]
            logger.info(f"[PLAN] admin {cid} deleted plan {pid}")
            await q.edit_message_text(f"🗑 تعرفه «{name}» حذف شد.")
        else:
            await q.edit_message_text("❌ تعرفه پیدا نشد.")
        return
    if d == "sales:setcard":
        await q.edit_message_text("💳 شماره کارت:\n(خط دوم: نام صاحب کارت)")
        ctx.user_data["conv_state"] = SET_CARD; return
    if d == "sales:pending":
        pending = {oid: o for oid, o in ORDERS.items() if o["status"] == "pending"}
        if not pending: await q.edit_message_text("✅ رسید در انتظاری وجود ندارد."); return
        txt = "⏳ *رسیدهای در انتظار:*\n\n"
        rows = []
        for oid, o in list(pending.items()):
            p = PLANS.get(o["plan_id"], {})
            ts = datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
            txt += f"🔹 #{oid} | `{o.get('email','?')}` | {p.get('name','?')} | {ts}\n"
            rows.append([
                InlineKeyboardButton(f"✅ #{oid}", callback_data=f"order:approve:{oid}"),
                InlineKeyboardButton(f"❌ #{oid}", callback_data=f"order:reject:{oid}"),
            ])
        rows.append([InlineKeyboardButton("🔙", callback_data="back")])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))
        return
    if d == "sales:all":
        if not ORDERS: await q.edit_message_text("📭 سفارشی ثبت نشده."); return
        st_ic = {"pending":"⏳","approved":"✅","rejected":"❌"}
        txt = "📊 *همه سفارش‌ها:*\n\n"
        for o in sorted(ORDERS.values(), key=lambda x: x["ts"], reverse=True)[:20]:
            p  = PLANS.get(o["plan_id"], {})
            ts = datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
            txt += f"{st_ic.get(o['status'],'?')} #{o['id']} | `{o.get('email','?')}` | {p.get('name','?')} | {ts}\n"
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back")]]))
        return

    # ── انتخاب اینباند برای تعرفه جدید ─────────────────────────
    if d.startswith("pickib:"):
        iid = safe_int(d.split(":")[1])
        pid = uuid.uuid4().hex[:6]
        PLANS[pid] = {
            "name": ctx.user_data.get("pn", "?"),
            "price": ctx.user_data.get("pp", 0),
            "days":  ctx.user_data.get("pd", 30),
            "gb":    ctx.user_data.get("pgb", 0),
            "inbound_id": iid,
        }
        p = PLANS[pid]; gb = "نامحدود" if p["gb"]==0 else f"{p['gb']} GB"
        logger.info(f"[PLAN] admin {cid} added plan {pid}: {p['name']}")
        await q.edit_message_text(
            f"✅ *تعرفه افزوده شد!*\n\n"
            f"📦 {p['name']} | {p['days']} روز | {gb}\n"
            f"💰 {fmt_price(p['price'])}",
            parse_mode="Markdown")
        return

# ══════════════════════════════════════════════════════════════════
#  هندلر متن مرکزی
# ══════════════════════════════════════════════════════════════════

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    txt  = update.message.text.strip()
    state = ctx.user_data.get("conv_state")

    # ── منوی ادمین ──────────────────────────────────────────────
    if txt == "📊 وضعیت سرور":        return await adm_status(update, ctx)
    if txt == "🔗 اینباندها":          return await adm_inbounds(update, ctx)
    if txt == "👥 مدیریت کلاینت‌ها":  return await adm_clients(update, ctx)
    if txt == "📈 ترافیک کلاینت":      return await adm_traffic_ask(update, ctx)
    if txt == "🌐 کلاینت‌های آنلاین":  return await adm_online(update, ctx)
    if txt == "💾 پشتیبان‌گیری":       return await adm_backup(update, ctx)
    if txt == "🛒 مدیریت فروش":        return await adm_sales(update, ctx)
    if txt == "⚙️ تنظیمات پنل":       return await adm_settings(update, ctx)

    # ── منوی مشتری ──────────────────────────────────────────────
    if txt == "📊 وضعیت اشتراک":      return await usr_status(update, ctx)
    if txt == "🛒 خرید / تمدید":       return await usr_buy(update, ctx)
    if txt == "📱 QR کد":              return await usr_qr(update, ctx)
    if txt == "📋 اطلاعات اتصال":     return await usr_conn(update, ctx)
    if txt == "🔔 وضعیت سفارش‌ها":    return await usr_orders(update, ctx)
    if txt == "🔄 تغییر ایمیل":        return await usr_change_email(update, ctx)

    # ── مراحل مکالمه ────────────────────────────────────────────

    # ثبت ایمیل مشتری
    if state == USER_REG_EMAIL:
        email = sanitize_email(txt)
        if not email:
            await update.message.reply_text("❌ ایمیل نامعتبر است."); return
        admin = any_admin()
        if not admin:
            await update.message.reply_text("⚠️ سرور پیکربندی نشده."); return
        c = _userinfo(email)
        if not c:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 خرید اشتراک", callback_data="buy_now")]])
            await update.message.reply_text(
                f"❌ ایمیل `{email}` در پنل پیدا نشد.\n\nمی‌توانید اشتراک جدید خریداری کنید:",
                parse_mode="Markdown", reply_markup=kb)
            return
        USER_EMAILS[cid] = email
        ctx.user_data.pop("conv_state", None)
        logger.info(f"[USER] {cid} registered email: {email}")
        await update.message.reply_text(
            f"✅ *ورود موفق!*\nایمیل `{email}` شناسایی شد.",
            parse_mode="Markdown", reply_markup=usr_kb())
        return

    # تعرفه‌ها
    if state == PLAN_NAME:  return await plan_name_recv(update, ctx)
    if state == PLAN_PRICE: return await plan_price_recv(update, ctx)
    if state == PLAN_DAYS:  return await plan_days_recv(update, ctx)
    if state == PLAN_GB:    return await plan_gb_recv(update, ctx)

    # کارت (از callback sales:setcard)
    if state == SET_CARD:
        global CARD_NUMBER, CARD_OWNER
        if not is_admin(cid): return
        parts = txt.split("\n")
        CARD_NUMBER = re.sub(r"\D", "", parts[0])
        CARD_OWNER  = parts[1].strip() if len(parts) > 1 else ""
        if len(CARD_NUMBER) not in (16, 19):
            await update.message.reply_text("❌ شماره کارت باید ۱۶ رقم باشد."); return
        ctx.user_data.pop("conv_state", None)
        logger.info(f"[CARD] admin {cid} set card {CARD_NUMBER[:4]}****")
        await update.message.reply_text(
            f"✅ کارت ثبت شد:\n💳 `{CARD_NUMBER}`\n👤 {CARD_OWNER}",
            parse_mode="Markdown", reply_markup=adm_kb())
        return

    # رسید خرید
    if state == BUY_RECEIPT:
        await update.message.reply_text("📸 لطفاً تصویر رسید را ارسال کنید.")
        return

    # عملیات ادمین (متن)
    if not is_admin(cid) or not _check(cid): return

    if state == ADMIN_ADD_EMAIL:
        email = sanitize_email(txt)
        if not email: await update.message.reply_text("❌ ایمیل نامعتبر:"); return
        ctx.user_data["ne"] = email
        await update.message.reply_text("📦 حجم GB (0=نامحدود):")
        ctx.user_data["conv_state"] = ADMIN_ADD_TRAFFIC; return

    if state == ADMIN_ADD_TRAFFIC:
        v = safe_float(txt, -1)
        if v < 0: await update.message.reply_text("❌ عدد معتبر:"); return
        ctx.user_data["nt"] = v
        await update.message.reply_text("📅 روز انقضا (0=نامحدود):")
        ctx.user_data["conv_state"] = ADMIN_ADD_EXPIRE; return

    if state == ADMIN_ADD_EXPIRE:
        days = safe_int(txt, -1)
        if days < 0: await update.message.reply_text("❌ عدد صحیح:"); return
        res = api_add_client(cid, ctx.user_data["tib"], ctx.user_data["ne"], ctx.user_data["nt"], days)
        if res.get("success"):
            exp = f"{days} روز" if days > 0 else "نامحدود"
            trf = f"{ctx.user_data['nt']} GB" if ctx.user_data["nt"] > 0 else "نامحدود"
            await update.message.reply_text(
                f"✅ کلاینت ساخته شد\n📧 `{ctx.user_data['ne']}`\n📦 {trf}\n📅 {exp}",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state", None); return

    if state == ADMIN_SEARCH_EMAIL:
        email = sanitize_email(txt)
        res = api_client_traffic(cid, email)
        if not res.get("success") or not res.get("obj"):
            await update.message.reply_text(f"❌ `{email}` پیدا نشد.", parse_mode="Markdown")
            ctx.user_data.pop("conv_state", None); return
        c = res["obj"]; used = c.get("up",0)+c.get("down",0); tot = c.get("total",0)
        ip_res = api_client_ips(cid, email); ips = ip_res.get("obj") or []
        await update.message.reply_text(
            f"📊 *{email}*\n\n"
            f"{'✅' if c.get('enable') else '❌'} | ↑`{b2s(c.get('up',0))}` ↓`{b2s(c.get('down',0))}`\n"
            f"کل: `{b2s(tot) if tot>0 else '♾️'}` | {tbar(used,tot)}\n"
            f"انقضا: `{ms2d(c.get('expiryTime',0))}` ({days_left(c.get('expiryTime',0))})\n"
            + (f"IP: {', '.join(ips[:5])}" if ips else ""),
            parse_mode="Markdown")
        ctx.user_data.pop("conv_state", None); return

    if state == ADMIN_DEL_EMAIL:
        email = sanitize_email(txt); iid = ctx.user_data.get("tib")
        res = api_inbound(cid, iid)
        if not res.get("success"):
            await update.message.reply_text(f"❌ {res.get('msg')}"); ctx.user_data.pop("conv_state",None); return
        try: cls = json.loads(res["obj"].get("settings","{}")).get("clients",[])
        except: cls = []
        cl = next((c for c in cls if c.get("email") == email), None)
        if not cl:
            await update.message.reply_text(f"❌ `{email}` یافت نشد.", parse_mode="Markdown")
            ctx.user_data.pop("conv_state", None); return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله حذف شود", callback_data=f"okdel:{iid}:{cl['id']}")],
            [InlineKeyboardButton("❌ انصراف",       callback_data=f"nodels:{iid}")],
        ])
        await update.message.reply_text(f"⚠️ حذف `{email}`؟", parse_mode="Markdown", reply_markup=kb)
        ctx.user_data.pop("conv_state", None); return

    if state == ADMIN_RESET_EMAIL:
        email = sanitize_email(txt); iid = ctx.user_data.get("tib")
        res = api_reset_client(cid, iid, email)
        await update.message.reply_text("✅ ریست شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state", None); return

# رسید عکسی
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("conv_state") == BUY_RECEIPT:
        await receipt_received(update, ctx)

# ══════════════════════════════════════════════════════════════════
#  دستورات عمومی
# ══════════════════════════════════════════════════════════════════

async def reconnect(u, ctx):
    cid = u.effective_chat.id
    if not is_admin(cid): await u.message.reply_text("⛔ دسترسی ندارید."); return
    res = api_login(cid)
    await u.message.reply_text("✅ متصل شد!" if res["ok"] else f"❌ {res['msg']}")

async def help_cmd(u, ctx):
    await u.message.reply_text(
        "📖 *راهنمای ربات 3X-UI*\n\n"
        "*دستورات:*\n"
        "/start — انتخاب نقش\n"
        "/setup — تنظیم پنل (فقط ادمین‌های مجاز)\n"
        "/setcard — تنظیم شماره کارت\n"
        "/reconnect — اتصال مجدد\n"
        "/help — راهنما\n\n"
        "*پنل ادمین:* وضعیت سرور، اینباندها، کلاینت‌ها، فروش\n"
        "*پنل مشتری:* اشتراک، خرید، QR کد، سفارش‌ها",
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════
#  اجرا
# ══════════════════════════════════════════════════════════════════

def main():
    global CARD_NUMBER, CARD_OWNER

    token       = os.environ.get("BOT_TOKEN",    "").strip()
    CARD_NUMBER = os.environ.get("CARD_NUMBER",  "").strip()
    CARD_OWNER  = os.environ.get("CARD_OWNER",   "").strip()
    allowed_raw = os.environ.get("ALLOWED_ADMINS","").strip()

    # بارگذاری ادمین‌های مجاز از .env
    if allowed_raw:
        for aid in allowed_raw.split(","):
            aid = aid.strip()
            if aid.lstrip("-").isdigit():
                ALLOWED_IDS.add(int(aid))

    if not token:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        print("━"*50)
        print("❌  BOT_TOKEN یافت نشد!\n")
        print(f"📝  فایل .env را بسازید:\n    {env_path}\n")
        print("  BOT_TOKEN=توکن_ربات")
        print("  CARD_NUMBER=6037991234567890")
        print("  CARD_OWNER=نام صاحب کارت")
        print("  ALLOWED_ADMINS=chat_id_شما")
        print("━"*50)
        print("\n💡  cp .env.example .env")
        return

    if not ALLOWED_IDS:
        print("⚠️  هشدار: ALLOWED_ADMINS در .env تنظیم نشده!")
        print("   هیچ‌کس نمی‌تواند ادمین شود تا زمانی که این مقدار تنظیم شود.")

    app = Application.builder().token(token).build()

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", setup_start)],
        states={
            SETUP_URL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_url)],
            SETUP_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_user)],
            SETUP_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_pass)],
        },
        fallbacks=[CommandHandler("cancel", setup_cancel)],
    )
    setcard_conv = ConversationHandler(
        entry_points=[CommandHandler("setcard", setcard_start)],
        states={SET_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, setcard_done)]},
        fallbacks=[CommandHandler("cancel", setup_cancel)],
    )

    app.add_handler(setup_conv)
    app.add_handler(setcard_conv)
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_cmd))
    app.add_handler(CommandHandler("reconnect", reconnect))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("🤖 ربات 3X-UI راه‌اندازی شد.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
