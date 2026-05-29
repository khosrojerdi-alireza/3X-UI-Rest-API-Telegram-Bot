"""
forms.py — فرم‌های تعاملی قدم‌به‌قدم برای ربات 3X-UI
هر فرم یک ماشین حالت است که داده‌های لازم را جمع‌آوری کرده
و در پایان payload آماده برای API می‌سازد.
"""

import uuid, json, time, datetime

# ══════════════════════════════════════════════════════════════════
#  ذخیره وضعیت فرم‌های در حال اجرا
#  { cid: {"form": "inbound"|"client"|..., "step": int, "data": dict} }
# ══════════════════════════════════════════════════════════════════
FORMS: dict = {}

def form_start(cid: int, form_name: str):
    FORMS[cid] = {"form": form_name, "step": 0, "data": {}}

def form_get(cid: int) -> dict | None:
    return FORMS.get(cid)

def form_clear(cid: int):
    FORMS.pop(cid, None)

def form_set(cid: int, key: str, value):
    if cid in FORMS:
        FORMS[cid]["data"][key] = value

def form_next(cid: int):
    if cid in FORMS:
        FORMS[cid]["step"] += 1

def form_data(cid: int) -> dict:
    return FORMS.get(cid, {}).get("data", {})

# ══════════════════════════════════════════════════════════════════
#  ابزارهای کمکی
# ══════════════════════════════════════════════════════════════════

def sanitize_username(name: str) -> str:
    """فقط حروف انگلیسی کوچک، اعداد، خط تیره و زیرخط — بدون فاصله"""
    import re
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_\-]", "", name)   # حذف کاراکترهای غیرمجاز
    return name[:32]                              # حداکثر ۳۲ کاراکتر


def build_email(username: str, tg_id: int) -> str:
    """ساختن ایمیل یکتا: نام@ایدی‌تلگرام"""
    return f"{username}@{tg_id}"


def is_valid_username(name: str) -> bool:
    """بررسی معتبر بودن نام کاربری"""
    import re
    return bool(re.match(r"^[a-z0-9_\-]{1,32}$", name))


def days_to_ms(days: int) -> int:
    if days <= 0: return 0
    return int((datetime.datetime.now() + datetime.timedelta(days=days)).timestamp() * 1000)

def gb_to_bytes(gb: float) -> int:
    if gb <= 0: return 0
    return int(gb * 1024 ** 3)

# ══════════════════════════════════════════════════════════════════
#  تعریف قدم‌های هر فرم به صورت داده‌ساختار
#  هر قدم: {"key", "ask_fa", "ask_en", "type", "options"?, "optional"?}
#  type: "text" | "int" | "float" | "choice" | "bool" | "skip"
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
#  فرم اینباند جدید
# ──────────────────────────────────────────────────────────────────
INBOUND_FORM = [
    {
        "key":     "remark",
        "ask_fa":  "📝 *نام اینباند* را وارد کنید:\nمثال: `VPN-Main`",
        "ask_en":  "📝 Enter *inbound name*:\nExample: `VPN-Main`",
        "type":    "text",
    },
    {
        "key":     "port",
        "ask_fa":  "🔌 *پورت* را وارد کنید (1–65535):",
        "ask_en":  "🔌 Enter *port* (1–65535):",
        "type":    "int",
        "validate": lambda v: 1 <= v <= 65535,
        "err_fa":  "❌ پورت باید بین ۱ تا ۶۵۵۳۵ باشد.",
        "err_en":  "❌ Port must be between 1 and 65535.",
    },
    {
        "key":     "protocol",
        "ask_fa":  "🔒 *پروتکل* را انتخاب کنید:",
        "ask_en":  "🔒 Select *protocol*:",
        "type":    "choice",
        "options": ["vless", "vmess", "trojan", "shadowsocks", "hysteria2", "tuic"],
        "btn_cols": 3,
    },
    {
        "key":     "network",
        "ask_fa":  "🌐 *نوع شبکه* را انتخاب کنید:",
        "ask_en":  "🌐 Select *network type*:",
        "type":    "choice",
        "options": ["tcp", "ws", "grpc", "httpupgrade", "splithttp", "xhttp"],
        "btn_cols": 3,
    },
    {
        "key":     "security",
        "ask_fa":  "🛡 *امنیت* را انتخاب کنید:",
        "ask_en":  "🛡 Select *security*:",
        "type":    "choice",
        "options": ["none", "tls", "reality"],
        "btn_cols": 3,
    },
    # ── Reality (فقط اگه security=reality) ──────────────────────
    {
        "key":     "reality_dest",
        "ask_fa":  "🎯 *دامنه هدف Reality* را وارد کنید:\nمثال: `yahoo.com:443`",
        "ask_en":  "🎯 Enter *Reality dest domain*:\nExample: `yahoo.com:443`",
        "type":    "text",
        "condition": lambda d: d.get("security") == "reality",
    },
    {
        "key":     "reality_server_names",
        "ask_fa":  "🌐 *ServerNames* را وارد کنید (با کاما):\nمثال: `yahoo.com,www.yahoo.com`",
        "ask_en":  "🌐 Enter *serverNames* (comma separated):\nExample: `yahoo.com,www.yahoo.com`",
        "type":    "text",
        "condition": lambda d: d.get("security") == "reality",
    },
    {
        "key":     "reality_private_key",
        "ask_fa":  "🔑 *Private Key* را وارد کنید:\n_(از دکمه «X25519 جدید» در منوی سرور بگیرید)_",
        "ask_en":  "🔑 Enter *Private Key*:\n_(Get it from Server menu → New X25519)_",
        "type":    "text",
        "condition": lambda d: d.get("security") == "reality",
    },
    {
        "key":     "reality_short_id",
        "ask_fa":  "🆔 *ShortId* را وارد کنید (8 کاراکتر hex):\nمثال: `abcd1234`",
        "ask_en":  "🆔 Enter *shortId* (8 hex chars):\nExample: `abcd1234`",
        "type":    "text",
        "condition": lambda d: d.get("security") == "reality",
    },
    # ── TLS (فقط اگه security=tls) ──────────────────────────────
    {
        "key":     "tls_sni",
        "ask_fa":  "🌐 *SNI* را وارد کنید:\nمثال: `example.com`",
        "ask_en":  "🌐 Enter *SNI*:\nExample: `example.com`",
        "type":    "text",
        "condition": lambda d: d.get("security") == "tls",
    },
    # ── WebSocket path ───────────────────────────────────────────
    {
        "key":     "ws_path",
        "ask_fa":  "🔗 *WebSocket Path* را وارد کنید:\nمثال: `/vless` (برای پیش‌فرض Enter بزنید)",
        "ask_en":  "🔗 Enter *WebSocket Path*:\nExample: `/vless` (press Enter for default `/`)",
        "type":    "text",
        "default": "/",
        "condition": lambda d: d.get("network") == "ws",
    },
    # ── gRPC serviceName ────────────────────────────────────────
    {
        "key":     "grpc_service",
        "ask_fa":  "🔧 *gRPC Service Name* را وارد کنید:",
        "ask_en":  "🔧 Enter *gRPC Service Name*:",
        "type":    "text",
        "default": "grpc",
        "condition": lambda d: d.get("network") == "grpc",
    },
    # ── flow (VLESS + TCP/Reality) ───────────────────────────────
    {
        "key":     "flow",
        "ask_fa":  "⚡ *Flow* را انتخاب کنید:",
        "ask_en":  "⚡ Select *Flow*:",
        "type":    "choice",
        "options": ["xtls-rprx-vision", "none"],
        "btn_cols": 2,
        "condition": lambda d: d.get("protocol") == "vless" and d.get("network") == "tcp",
    },
    # ── Shadowsocks method ───────────────────────────────────────
    {
        "key":     "ss_method",
        "ask_fa":  "🔐 *روش رمزنگاری* Shadowsocks را انتخاب کنید:",
        "ask_en":  "🔐 Select Shadowsocks *encryption method*:",
        "type":    "choice",
        "options": ["2022-blake3-aes-128-gcm", "2022-blake3-aes-256-gcm", "2022-blake3-chacha20-poly1305", "aes-256-gcm", "chacha20-poly1305"],
        "btn_cols": 1,
        "condition": lambda d: d.get("protocol") == "shadowsocks",
    },
    # ── ترافیک کل اینباند ───────────────────────────────────────
    {
        "key":     "total_gb",
        "ask_fa":  "📦 *حجم کل* اینباند به GB (0 = نامحدود):",
        "ask_en":  "📦 *Total traffic* GB for inbound (0 = unlimited):",
        "type":    "float",
        "default": 0,
    },
    # ── انقضای اینباند ──────────────────────────────────────────
    {
        "key":     "expiry_days",
        "ask_fa":  "📅 *انقضا* به روز (0 = نامحدود):",
        "ask_en":  "📅 *Expiry* in days (0 = unlimited):",
        "type":    "int",
        "default": 0,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم کلاینت جدید
# ──────────────────────────────────────────────────────────────────
CLIENT_FORM = [
    {
        "key":     "username",
        "ask_fa":  (
            "👤 *نام کاربری* را وارد کنید:\n\n"
            "• فقط حروف انگلیسی کوچک، اعداد، `_` و `-`\n"
            "• بدون فاصله\n"
            "• مثال: `ali` یا `user123`\n\n"
            "_ربات خودش ایمیل یکتا می‌سازد_"
        ),
        "ask_en":  "👤 Enter *username*:\n(lowercase letters, numbers, _ and - only)",
        "type":    "text",
        "validate": lambda v: is_valid_username(v),
        "err_fa":  "❌ فقط حروف انگلیسی کوچک، اعداد، _ و - مجاز است.\nمثال: `ali` یا `user_1`",
        "err_en":  "❌ Only lowercase letters, numbers, _ and - are allowed.",
    },
    {
        "key":    "total_gb",
        "ask_fa": "📦 *حجم ترافیک* به GB (0 = نامحدود):",
        "ask_en": "📦 *Traffic limit* in GB (0 = unlimited):",
        "type":   "float",
        "default": 0,
    },
    {
        "key":    "expiry_days",
        "ask_fa": "📅 *روز انقضا* (0 = نامحدود):",
        "ask_en": "📅 *Expiry days* (0 = unlimited):",
        "type":   "int",
        "default": 0,
    },
    {
        "key":    "limit_ip",
        "ask_fa": "🌐 *محدودیت IP همزمان* (0 = نامحدود):",
        "ask_en": "🌐 *IP limit* (0 = unlimited):",
        "type":   "int",
        "default": 0,
    },
    {
        "key":    "tg_id",
        "ask_fa": "📱 *Telegram ID* کاربر (اختیاری، 0 = ندارد):",
        "ask_en": "📱 User *Telegram ID* (optional, 0 = none):",
        "type":   "int",
        "default": 0,
        "optional": True,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم ویرایش کلاینت
# ──────────────────────────────────────────────────────────────────
CLIENT_EDIT_FORM = [
    {
        "key":    "total_gb",
        "ask_fa": "📦 *حجم جدید* به GB (0 = نامحدود، -1 = بدون تغییر):",
        "ask_en": "📦 *New traffic* GB (0 = unlimited, -1 = no change):",
        "type":   "float",
        "default": -1,
    },
    {
        "key":    "expiry_days",
        "ask_fa": "📅 *تمدید* چند روز از الان (0 = نامحدود، -1 = بدون تغییر):",
        "ask_en": "📅 *Extend* how many days from now (0 = unlimited, -1 = no change):",
        "type":   "int",
        "default": -1,
    },
    {
        "key":    "limit_ip",
        "ask_fa": "🌐 *محدودیت IP* جدید (0 = نامحدود، -1 = بدون تغییر):",
        "ask_en": "🌐 *New IP limit* (0 = unlimited, -1 = no change):",
        "type":   "int",
        "default": -1,
    },
    {
        "key":    "enable",
        "ask_fa": "🔘 وضعیت کلاینت:",
        "ask_en": "🔘 Client status:",
        "type":   "choice",
        "options": ["active|✅ فعال / Active", "inactive|❌ غیرفعال / Inactive", "keep|🔄 بدون تغییر / No change"],
        "btn_cols": 1,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم تعرفه فروش
# ──────────────────────────────────────────────────────────────────
PLAN_FORM = [
    {
        "key":    "name",
        "ask_fa": "📝 *نام تعرفه* را وارد کنید:\nمثال: `یک ماهه` یا `30 Days`",
        "ask_en": "📝 Enter *plan name*:\nExample: `One Month` or `30 Days`",
        "type":   "text",
    },
    {
        "key":    "price",
        "ask_fa": "💰 *قیمت* به تومان را وارد کنید:\nمثال: `150000`",
        "ask_en": "💰 Enter *price*:\nExample: `150000`",
        "type":   "int",
    },
    {
        "key":    "days",
        "ask_fa": "📅 *مدت* به روز:",
        "ask_en": "📅 *Duration* in days:",
        "type":   "int",
        "validate": lambda v: v > 0,
        "err_fa": "❌ روز باید بیشتر از صفر باشد.",
        "err_en": "❌ Days must be greater than zero.",
    },
    {
        "key":    "gb",
        "ask_fa": "📦 *حجم* به GB (0 = نامحدود):",
        "ask_en": "📦 *Traffic* in GB (0 = unlimited):",
        "type":   "float",
        "default": 0,
    },
    # ── اینباند از طریق inline keyboard انتخاب می‌شه (نه text) ─
    {
        "key":    "inbound_id",
        "ask_fa": "🔌 *اینباند پیش‌فرض* تعرفه را انتخاب کنید:",
        "ask_en": "🔌 Select *default inbound* for this plan:",
        "type":   "inbound_pick",   # نوع خاص — از inbound list می‌گیره
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم Bulk Adjust
# ──────────────────────────────────────────────────────────────────
BULK_ADJUST_FORM = [
    {
        "key":    "emails",
        "ask_fa": "📧 *ایمیل کلاینت‌ها* را با کاما وارد کنید:\nمثال: `ali,sara,john`",
        "ask_en": "📧 Enter *client emails* separated by comma:\nExample: `ali,sara,john`",
        "type":   "text",
    },
    {
        "key":    "add_days",
        "ask_fa": "📅 *تعداد روز* برای تمدید (0 = بدون تغییر، عدد منفی = کاهش):",
        "ask_en": "📅 *Days to add* (0 = no change, negative = reduce):",
        "type":   "int",
        "default": 0,
    },
    {
        "key":    "add_gb",
        "ask_fa": "📦 *حجم GB* برای افزودن (0 = بدون تغییر، عدد منفی = کاهش):",
        "ask_en": "📦 *GB to add* (0 = no change, negative = reduce):",
        "type":   "float",
        "default": 0,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم نود جدید
# ──────────────────────────────────────────────────────────────────
NODE_FORM = [
    {
        "key":    "name",
        "ask_fa": "📝 *نام نود* را وارد کنید:\nمثال: `DE-Frankfurt-1`",
        "ask_en": "📝 Enter *node name*:\nExample: `DE-Frankfurt-1`",
        "type":   "text",
    },
    {
        "key":    "scheme",
        "ask_fa": "🔒 *پروتکل اتصال* به نود:",
        "ask_en": "🔒 *Connection scheme* to node:",
        "type":   "choice",
        "options": ["https", "http"],
        "btn_cols": 2,
    },
    {
        "key":    "address",
        "ask_fa": "🌐 *آدرس* نود (IP یا دامنه):\nمثال: `node1.example.com` یا `1.2.3.4`",
        "ask_en": "🌐 Node *address* (IP or domain):\nExample: `node1.example.com` or `1.2.3.4`",
        "type":   "text",
    },
    {
        "key":    "port",
        "ask_fa": "🔌 *پورت* پنل نود (معمولاً 2053):",
        "ask_en": "🔌 Node panel *port* (usually 2053):",
        "type":   "int",
        "default": 2053,
    },
    {
        "key":    "base_path",
        "ask_fa": "🔗 *Base Path* (معمولاً `/`):",
        "ask_en": "🔗 *Base Path* (usually `/`):",
        "type":   "text",
        "default": "/",
    },
    {
        "key":    "api_token",
        "ask_fa": "🔑 *API Token* نود را وارد کنید:",
        "ask_en": "🔑 Enter node *API Token*:",
        "type":   "text",
    },
    {
        "key":    "remark",
        "ask_fa": "💬 *توضیحات* (اختیاری، Enter برای رد کردن):",
        "ask_en": "💬 *Remark* (optional, Enter to skip):",
        "type":   "text",
        "default": "",
        "optional": True,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم تغییر یوزر/پسورد پنل
# ──────────────────────────────────────────────────────────────────
CHANGE_USER_FORM = [
    {
        "key":    "old_username",
        "ask_fa": "👤 *نام کاربری فعلی* را وارد کنید:",
        "ask_en": "👤 Enter *current username*:",
        "type":   "text",
    },
    {
        "key":    "old_password",
        "ask_fa": "🔑 *رمز عبور فعلی* را وارد کنید:",
        "ask_en": "🔑 Enter *current password*:",
        "type":   "text",
    },
    {
        "key":    "new_username",
        "ask_fa": "👤 *نام کاربری جدید* را وارد کنید:",
        "ask_en": "👤 Enter *new username*:",
        "type":   "text",
    },
    {
        "key":    "new_password",
        "ask_fa": "🔑 *رمز عبور جدید* را وارد کنید (حداقل ۸ کاراکتر):",
        "ask_en": "🔑 Enter *new password* (min 8 characters):",
        "type":   "text",
        "validate": lambda v: len(v) >= 8,
        "err_fa": "❌ رمز عبور باید حداقل ۸ کاراکتر باشد.",
        "err_en": "❌ Password must be at least 8 characters.",
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم تنظیم کارت (setcard)
# ──────────────────────────────────────────────────────────────────
CARD_FORM = [
    {
        "key":    "card_number",
        "ask_fa": "💳 *شماره کارت* را وارد کنید (۱۶ رقم):",
        "ask_en": "💳 Enter *card number* (16 digits):",
        "type":   "text",
        "validate": lambda v: len(v.replace(" ","").replace("-","").replace("_","")) == 16
                              and v.replace(" ","").replace("-","").isdigit(),
        "err_fa": "❌ شماره کارت باید دقیقاً ۱۶ رقم باشد.",
        "err_en": "❌ Card number must be exactly 16 digits.",
    },
    {
        "key":    "card_owner",
        "ask_fa": "👤 *نام صاحب کارت* را وارد کنید (اختیاری):",
        "ask_en": "👤 Enter *card owner name* (optional):",
        "type":   "text",
        "default": "",
        "optional": True,
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم نصب Xray
# ──────────────────────────────────────────────────────────────────
XRAY_INSTALL_FORM = [
    {
        "key":    "version",
        "ask_fa": "📦 *نسخه Xray* را وارد کنید:\nمثال: `v24.9.16` یا `latest`",
        "ask_en": "📦 Enter *Xray version*:\nExample: `v24.9.16` or `latest`",
        "type":   "text",
        "default": "latest",
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم API Token جدید
# ──────────────────────────────────────────────────────────────────
TOKEN_FORM = [
    {
        "key":    "name",
        "ask_fa": "📝 *نام توکن* را وارد کنید:\nمثال: `central-panel` یا `monitoring`",
        "ask_en": "📝 Enter *token name*:\nExample: `central-panel` or `monitoring`",
        "type":   "text",
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم گروه جدید
# ──────────────────────────────────────────────────────────────────
GROUP_FORM = [
    {
        "key":    "name",
        "ask_fa": "📝 *نام گروه* را وارد کنید:",
        "ask_en": "📝 Enter *group name*:",
        "type":   "text",
    },
]

# ──────────────────────────────────────────────────────────────────
#  فرم تغییر نام گروه
# ──────────────────────────────────────────────────────────────────
GROUP_RENAME_FORM = [
    {
        "key":    "old_name",
        "ask_fa": "📝 *نام فعلی گروه* را وارد کنید:",
        "ask_en": "📝 Enter *current group name*:",
        "type":   "text",
    },
    {
        "key":    "new_name",
        "ask_fa": "📝 *نام جدید گروه* را وارد کنید:",
        "ask_en": "📝 Enter *new group name*:",
        "type":   "text",
    },
]

# ══════════════════════════════════════════════════════════════════
#  موتور فرم — پردازش قدم‌ها
# ══════════════════════════════════════════════════════════════════

FORM_DEFS = {
    "inbound":       INBOUND_FORM,
    "client":        CLIENT_FORM,
    "client_edit":   CLIENT_EDIT_FORM,
    "plan":          PLAN_FORM,
    "bulk_adjust":   BULK_ADJUST_FORM,
    "node":          NODE_FORM,
    "change_user":   CHANGE_USER_FORM,
    "card":          CARD_FORM,
    "xray_install":  XRAY_INSTALL_FORM,
    "token":         TOKEN_FORM,
    "group":         GROUP_FORM,
    "group_rename":  GROUP_RENAME_FORM,
}

def get_active_steps(form_name: str, data: dict) -> list:
    """قدم‌های فعال فرم را با توجه به داده‌های فعلی برمی‌گرداند (condition ها)"""
    steps = FORM_DEFS.get(form_name, [])
    return [s for s in steps if "condition" not in s or s["condition"](data)]

def current_step(cid: int) -> dict | None:
    """قدم جاری فرم کاربر"""
    f = form_get(cid)
    if not f: return None
    active = get_active_steps(f["form"], f["data"])
    idx = f["step"]
    if idx >= len(active): return None
    return active[idx]

def is_form_done(cid: int) -> bool:
    f = form_get(cid)
    if not f: return True
    active = get_active_steps(f["form"], f["data"])
    return f["step"] >= len(active)

def form_progress(cid: int) -> str:
    """نمایش پیشرفت: مرحله X از Y"""
    f = form_get(cid)
    if not f: return ""
    active = get_active_steps(f["form"], f["data"])
    step = f["step"] + 1
    total = len(active)
    bar = "▓" * step + "░" * (total - step)
    return f"`{bar}` {step}/{total}"

# ══════════════════════════════════════════════════════════════════
#  پردازش ورودی کاربر
# ══════════════════════════════════════════════════════════════════

def process_input(cid: int, text: str, lang: str = "fa") -> dict:
    """
    ورودی کاربر را پردازش و به قدم بعد می‌رود.
    برمی‌گرداند:
      {"ok": True}             — قدم موفق، ادامه دارد
      {"ok": True, "done": True} — فرم تمام شد
      {"ok": False, "err": str}  — خطا در ورودی
    """
    f = form_get(cid)
    if not f: return {"ok": False, "err": "no_form"}

    active = get_active_steps(f["form"], f["data"])
    idx = f["step"]
    if idx >= len(active):
        return {"ok": True, "done": True}

    step = active[idx]
    key  = step["key"]
    typ  = step["type"]
    text = text.strip()

    # ── مقدار پیش‌فرض اگه خالی ───────────────────────────────
    if not text and "default" in step:
        value = step["default"]
    elif typ == "text":
        if not text and not step.get("optional"):
            err = step.get(f"err_{lang}", "❌ این فیلد اجباری است." if lang=="fa" else "❌ This field is required.")
            return {"ok": False, "err": err}
        value = text
    elif typ in ("int", "float"):
        try:
            value = int(text) if typ == "int" else float(text)
        except ValueError:
            err = step.get(f"err_{lang}", ("❌ عدد معتبر وارد کنید." if lang=="fa" else "❌ Enter a valid number."))
            return {"ok": False, "err": err}
    elif typ == "bool":
        value = text.lower() in ("true", "yes", "بله", "1", "✅")
    elif typ in ("choice", "inbound_pick"):
        # choice از طریق callback می‌آید، نه text
        value = text
    else:
        value = text

    # ── validation ────────────────────────────────────────────
    if "validate" in step and value != step.get("default"):
        try:
            if not step["validate"](value):
                err = step.get(f"err_{lang}", "❌ مقدار نامعتبر." if lang=="fa" else "❌ Invalid value.")
                return {"ok": False, "err": err}
        except Exception:
            pass

    form_set(cid, key, value)
    form_next(cid)

    # چک کن فرم تمام شده یا نه
    if is_form_done(cid):
        return {"ok": True, "done": True}
    return {"ok": True}

# ══════════════════════════════════════════════════════════════════
#  سازنده‌های payload نهایی
# ══════════════════════════════════════════════════════════════════

def build_inbound_payload(data: dict) -> dict:
    """ساختن payload اینباند برای /panel/api/inbounds/add"""
    protocol = data.get("protocol", "vless")
    network  = data.get("network", "tcp")
    security = data.get("security", "none")

    # ── settings ──────────────────────────────────────────────
    if protocol == "vless":
        settings = {"clients": [], "decryption": "none", "fallbacks": []}
    elif protocol == "vmess":
        settings = {"clients": [], "disableInsecureEncryption": False}
    elif protocol == "trojan":
        settings = {"clients": [], "fallbacks": []}
    elif protocol == "shadowsocks":
        settings = {
            "method":   data.get("ss_method", "2022-blake3-aes-128-gcm"),
            "password": uuid.uuid4().hex,
            "network":  "tcp,udp",
            "clients":  [],
        }
    elif protocol == "hysteria2":
        settings = {
            "clients":  [],
            "masquerade": "https://www.bing.com",
            "ignoreClientBandwidth": False,
        }
    elif protocol == "tuic":
        settings = {"clients": [], "congestion_control": "bbr"}
    else:
        settings = {"clients": []}

    # ── streamSettings ────────────────────────────────────────
    stream = {"network": network, "security": security}

    if security == "reality":
        stream["realitySettings"] = {
            "show":        False,
            "dest":        data.get("reality_dest", "yahoo.com:443"),
            "serverNames": [s.strip() for s in data.get("reality_server_names","yahoo.com").split(",")],
            "privateKey":  data.get("reality_private_key", ""),
            "shortIds":    [data.get("reality_short_id", uuid.uuid4().hex[:8])],
        }
    elif security == "tls":
        stream["tlsSettings"] = {
            "serverName": data.get("tls_sni", ""),
            "allowInsecure": False,
        }

    if network == "ws":
        stream["wsSettings"] = {
            "path":    data.get("ws_path", "/"),
            "headers": {},
        }
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": data.get("grpc_service", "grpc"),
            "multiMode":   False,
        }
    elif network in ("httpupgrade", "xhttp", "splithttp"):
        stream[f"{network}Settings"] = {"path": data.get("ws_path", "/"), "host": ""}

    # ── sniffing ──────────────────────────────────────────────
    sniffing = {
        "enabled":     True,
        "destOverride": ["http", "tls", "quic", "fakedns"],
        "metadataOnly": False,
    }

    # ── expiry ────────────────────────────────────────────────
    expiry_ms = days_to_ms(data.get("expiry_days", 0))
    total_bytes = gb_to_bytes(data.get("total_gb", 0))

    return {
        "enable":         True,
        "remark":         data.get("remark", "New Inbound"),
        "listen":         "",
        "port":           data.get("port", 443),
        "protocol":       protocol,
        "expiryTime":     expiry_ms,
        "total":          total_bytes,
        "settings":       settings,
        "streamSettings": stream,
        "sniffing":       sniffing,
    }


def build_client_payload(data: dict, tg_id: int = 0) -> tuple[dict, list]:
    """
    ساختن client dict و inbound_ids
    ایمیل به فرمت username@tgid ساخته می‌شود تا یکتا باشد
    returns: (client_dict, [inbound_id])
    """
    username = sanitize_username(data.get("username", data.get("email", "user")))
    email    = build_email(username, tg_id) if tg_id else username
    client = {
        "email":      email,
        "totalGB":    gb_to_bytes(data.get("total_gb", 0)),
        "expiryTime": days_to_ms(data.get("expiry_days", 0)),
        "limitIp":    data.get("limit_ip", 0),
        "tgId":       tg_id,
        "enable":     True,
    }
    iid = data.get("inbound_id")
    return client, ([iid] if iid else [])


def build_client_edit_payload(original: dict, data: dict) -> dict:
    """ساختن payload ویرایش کلاینت بر اساس فرم edit"""
    result = dict(original)

    gb = data.get("total_gb", -1)
    if gb != -1:
        result["totalGB"] = gb_to_bytes(gb)

    days = data.get("expiry_days", -1)
    if days != -1:
        if days == 0:
            result["expiryTime"] = 0
        else:
            now_ms = int(time.time() * 1000)
            old_exp = original.get("expiryTime", 0)
            base = old_exp if old_exp > now_ms else now_ms
            result["expiryTime"] = base + int(days * 86400 * 1000)

    ip = data.get("limit_ip", -1)
    if ip != -1:
        result["limitIp"] = ip

    en = data.get("enable", "keep")
    if en == "active":
        result["enable"] = True
    elif en == "inactive":
        result["enable"] = False

    return result


def build_plan_payload(data: dict) -> dict:
    """ساختن تعرفه برای PLANS دیکشنری"""
    return {
        "name":       data.get("name", "Plan"),
        "price":      data.get("price", 0),
        "days":       data.get("days", 30),
        "gb":         data.get("gb", 0),
        "inbound_id": data.get("inbound_id"),
    }


def build_node_payload(data: dict) -> dict:
    """ساختن payload نود برای /panel/api/nodes/add"""
    return {
        "name":               data.get("name", ""),
        "remark":             data.get("remark", ""),
        "scheme":             data.get("scheme", "https"),
        "address":            data.get("address", ""),
        "port":               data.get("port", 2053),
        "basePath":           data.get("base_path", "/"),
        "apiToken":           data.get("api_token", ""),
        "enable":             True,
        "allowPrivateAddress": False,
    }


def build_bulk_adjust_payload(data: dict) -> tuple[list, int, float]:
    """emails, add_days, add_gb"""
    emails = [e.strip() for e in data.get("emails","").split(",") if e.strip()]
    return emails, data.get("add_days", 0), data.get("add_gb", 0)

# ══════════════════════════════════════════════════════════════════
#  ساختن دکمه‌های choice برای inline keyboard
# ══════════════════════════════════════════════════════════════════

def make_choice_buttons(step: dict, form_name: str, lang: str = "fa") -> list:
    """
    لیست ردیف‌های دکمه برای یک قدم choice
    callback_data: form_choice:{form_name}:{key}:{value}
    """
    from telegram import InlineKeyboardButton
    options  = step.get("options", [])
    cols     = step.get("btn_cols", 2)
    key      = step["key"]
    rows     = []
    row      = []
    for opt in options:
        # اگه opt شامل | باشه: value|label
        if "|" in opt:
            val, label = opt.split("|", 1)
        else:
            val = opt; label = opt
        row.append(InlineKeyboardButton(
            label,
            callback_data=f"form_choice:{form_name}:{key}:{val}"
        ))
        if len(row) >= cols:
            rows.append(row); row = []
    if row:
        rows.append(row)
    # دکمه لغو
    cancel_txt = "❌ لغو فرم" if lang == "fa" else "❌ Cancel Form"
    rows.append([InlineKeyboardButton(cancel_txt, callback_data="form_cancel")])
    return rows


def step_question(step: dict, lang: str = "fa", cid: int = 0) -> str:
    """متن سوال یک قدم — فارسی"""
    q = step.get("ask_fa", "?")
    prog = form_progress(cid)
    return f"{prog}\n\n{q}"
