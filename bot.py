"""
ربات تلگرام 3X-UI — پوشش کامل API (بر اساس داکیومنت رسمی Postman)
نسخه: کامل
"""

import os, json, uuid, re, time, logging, io, datetime, urllib3
from dotenv import load_dotenv
import requests, qrcode

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from forms import (
    form_start, form_get, form_clear, form_set, form_next,
    form_data, is_form_done, current_step, step_question,
    make_choice_buttons, get_active_steps,
    build_inbound_payload, build_client_payload, build_client_edit_payload,
    build_plan_payload, build_node_payload, build_bulk_adjust_payload,
    FORM_DEFS, process_input,
)

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
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO,
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  مراحل مکالمه
# ══════════════════════════════════════════════════════
(
    SETUP_URL, SETUP_USER, SETUP_PASS,
    SET_CARD,
    # کلاینت
    CL_EMAIL, CL_GB, CL_DAYS,
    CL_DEL_EMAIL, CL_RESET_EMAIL, CL_SEARCH_EMAIL, CL_SEARCH_UUID,
    CL_CLEAR_IPS, CL_UPDATE_EMAIL,
    # اینباند
    IB_ADD_JSON, IB_EDIT_JSON,
    # تعرفه
    PLAN_NAME, PLAN_PRICE, PLAN_DAYS, PLAN_GB,
    # مشتری
    USER_EMAIL,
    # خرید
    BUY_RECEIPT,
    # سرور
    SRV_INSTALL_VER,
    # خرید اینباند
    IB_IMPORT_JSON,
) = range(23)

# ══════════════════════════════════════════════════════
#  ذخیره‌سازی
# ══════════════════════════════════════════════════════
SETTINGS:     dict = {}
SESSIONS:     dict = {}
ADMINS:       set  = set()
ALLOWED_IDS:  set  = set()
USER_EMAILS:  dict = {}
PLANS:        dict = {}
ORDERS:       dict = {}
CARD_NUMBER:  str  = ""
CARD_OWNER:   str  = ""
LAST_RECEIPT: dict = {}
RECEIPT_COOLDOWN = 60

# ══════════════════════════════════════════════════════
#  گاردها
# ══════════════════════════════════════════════════════
def is_admin(cid):    return cid in ADMINS and cid in SETTINGS
def is_allowed(cid):  return bool(ALLOWED_IDS) and cid in ALLOWED_IDS
def sanitize(s):      return re.sub(r"[^\w.\-@]", "", str(s).strip())[:64]
def safe_int(v, d=0):
    try:    return int(v)
    except: return d
def safe_float(v, d=0.0):
    try:    return float(v)
    except: return d
def pending_count(cid): return sum(1 for o in ORDERS.values() if o["user_cid"]==cid and o["status"]=="pending")
def new_oid():          return uuid.uuid4().hex[:8].upper()
def fmt_price(p):       return f"{p:,} تومان"

# ══════════════════════════════════════════════════════
#  لایه API
# ══════════════════════════════════════════════════════
def _base(cid):  return SETTINGS[cid]["url"].rstrip("/")
def _s(cid):     return SESSIONS.get(cid)

def api_login(cid):
    cfg = SETTINGS[cid]; s = requests.Session(); s.verify = False
    try:
        r = s.post(f"{_base(cid)}/login",
            json={"username":cfg["user"],"password":cfg["pass"],"twoFactorCode":""}, timeout=10)
        d = r.json()
        if d.get("success"): SESSIONS[cid]=s; logger.info(f"[LOGIN] {cid}"); return {"ok":True}
        return {"ok":False,"msg":d.get("msg","خطا")}
    except Exception as e: return {"ok":False,"msg":str(e)}

def _get(cid,path):
    s=_s(cid)
    if not s: return {"success":False,"msg":"احراز هویت نشده"}
    try: return s.get(f"{_base(cid)}{path}",timeout=15).json()
    except Exception as e: return {"success":False,"msg":str(e)}

def _post(cid,path,payload=None,form=False):
    s=_s(cid)
    if not s: return {"success":False,"msg":"احراز هویت نشده"}
    try:
        if form: r=s.post(f"{_base(cid)}{path}",data=payload or {},timeout=15)
        else:    r=s.post(f"{_base(cid)}{path}",json=payload or {},timeout=15)
        return r.json()
    except Exception as e: return {"success":False,"msg":str(e)}

def _check(cid):
    if cid not in SETTINGS: return False
    if cid not in SESSIONS: return api_login(cid)["ok"]
    return True

def _adm(cid): return is_admin(cid) and _check(cid)

def any_admin():
    for c in ADMINS:
        if c in SESSIONS: return c
    return None

# ── AUTH ──────────────────────────────────────────────
def api_logout(cid):       return _post(cid,"/logout")
def api_get_2fa(cid):      return _post(cid,"/getTwoFactorEnable")

# ── INBOUNDS ──────────────────────────────────────────
def api_ibs(cid):               return _get(cid,"/panel/api/inbounds/list")
def api_ibs_slim(cid):          return _get(cid,"/panel/api/inbounds/list/slim")
def api_ibs_options(cid):       return _get(cid,"/panel/api/inbounds/options")
def api_ib(cid,iid):            return _get(cid,f"/panel/api/inbounds/get/{safe_int(iid)}")
def api_ib_add(cid,p):          return _post(cid,"/panel/api/inbounds/add",p)
def api_ib_del(cid,iid):        return _post(cid,f"/panel/api/inbounds/del/{safe_int(iid)}")
def api_ib_update(cid,iid,p):   return _post(cid,f"/panel/api/inbounds/update/{safe_int(iid)}",p)
def api_ib_enable(cid,iid,en):  return _post(cid,f"/panel/api/inbounds/setEnable/{safe_int(iid)}",{"enable":en})
def api_ib_reset_traffic(cid,iid): return _post(cid,f"/panel/api/inbounds/{safe_int(iid)}/resetTraffic")
def api_ib_del_all_clients(cid,iid): return _post(cid,f"/panel/api/inbounds/{safe_int(iid)}/delAllClients")
def api_ib_fallbacks_get(cid,iid):   return _get(cid,f"/panel/api/inbounds/{safe_int(iid)}/fallbacks")
def api_ib_fallbacks_set(cid,iid,p): return _post(cid,f"/panel/api/inbounds/{safe_int(iid)}/fallbacks",p)
def api_ibs_reset_all(cid):     return _post(cid,"/panel/api/inbounds/resetAllTraffics")
def api_ib_import(cid,data_str):return _post(cid,"/panel/api/inbounds/import",{"data":data_str},form=True)

# ── SERVER ────────────────────────────────────────────
def api_status(cid):                      return _get(cid,"/panel/api/server/status")
def api_cpu_history(cid,bucket):          return _get(cid,f"/panel/api/server/cpuHistory/{bucket}")
def api_history(cid,metric,bucket):       return _get(cid,f"/panel/api/server/history/{metric}/{bucket}")
def api_xray_metrics(cid):                return _get(cid,"/panel/api/server/xrayMetricsState")
def api_xray_obs(cid):                    return _get(cid,"/panel/api/server/xrayObservatory")
def api_get_xray_versions(cid):           return _get(cid,"/panel/api/server/getXrayVersion")
def api_check_panel_update(cid):          return _get(cid,"/panel/api/server/getPanelUpdateInfo")
def api_get_config_json(cid):             return _get(cid,"/panel/api/server/getConfigJson")
def api_get_db(cid):                      return _get(cid,"/panel/api/server/getDb")
def api_new_uuid(cid):                    return _get(cid,"/panel/api/server/getNewUUID")
def api_new_x25519(cid):                  return _get(cid,"/panel/api/server/getNewX25519Cert")
def api_stop_xray(cid):                   return _post(cid,"/panel/api/server/stopXrayService")
def api_restart_xray(cid):               return _post(cid,"/panel/api/server/restartXrayService")
def api_install_xray(cid,ver):            return _post(cid,f"/panel/api/server/installXray/{ver}")
def api_update_panel(cid):               return _post(cid,"/panel/api/server/updatePanel")
def api_update_geofile(cid,fname=""):
    if fname: return _post(cid,f"/panel/api/server/updateGeofile/{fname}")
    return _post(cid,"/panel/api/server/updateGeofile",{})
def api_logs(cid,count=100):             return _post(cid,f"/panel/api/server/logs/{count}",{"level":"info","syslog":False})
def api_xray_logs(cid,count=100):        return _post(cid,f"/panel/api/server/xraylogs/{count}",{})

# ── CLIENTS (نسخه جدید /panel/api/clients/) ──────────
def api_cl_list(cid):                       return _get(cid,"/panel/api/clients/list")
def api_cl_list_paged(cid,page=1,size=25,search="",filt="",proto="",sort="",order=""):
    q=f"page={page}&pageSize={size}&search={search}&filter={filt}&protocol={proto}&sort={sort}&order={order}"
    return _get(cid,f"/panel/api/clients/list/paged?{q}")
def api_cl_get(cid,email):                  return _get(cid,f"/panel/api/clients/get/{email}")
def api_cl_add(cid,client,inbound_ids):     return _post(cid,"/panel/api/clients/add",{"client":client,"inboundIds":inbound_ids})
def api_cl_update(cid,email,client):        return _post(cid,f"/panel/api/clients/update/{email}",client)
def api_cl_del(cid,email,keep=False):       return _post(cid,f"/panel/api/clients/del/{email}?keepTraffic={1 if keep else 0}")
def api_cl_attach(cid,email,iids):          return _post(cid,f"/panel/api/clients/{email}/attach",{"inboundIds":iids})
def api_cl_detach(cid,email,iids):          return _post(cid,f"/panel/api/clients/{email}/detach",{"inboundIds":iids})
def api_cl_reset_all(cid):                  return _post(cid,"/panel/api/clients/resetAllTraffics")
def api_cl_del_depleted(cid):               return _post(cid,"/panel/api/clients/delDepleted")
def api_cl_bulk_adjust(cid,emails,days,gb): return _post(cid,"/panel/api/clients/bulkAdjust",{"emails":emails,"addDays":days,"addBytes":int(gb*1024**3)})
def api_cl_bulk_del(cid,emails,keep=False): return _post(cid,"/panel/api/clients/bulkDel",{"emails":emails,"keepTraffic":keep})
def api_cl_bulk_create(cid,items):          return _post(cid,"/panel/api/clients/bulkCreate",items)
def api_cl_bulk_attach(cid,emails,iids):    return _post(cid,"/panel/api/clients/bulkAttach",{"emails":emails,"inboundIds":iids})
def api_cl_bulk_detach(cid,emails,iids):    return _post(cid,"/panel/api/clients/bulkDetach",{"emails":emails,"inboundIds":iids})
def api_cl_bulk_reset(cid,emails):          return _post(cid,"/panel/api/clients/bulkResetTraffic",{"emails":emails})
def api_cl_reset_traffic(cid,email):        return _post(cid,f"/panel/api/clients/resetTraffic/{email}")
def api_cl_update_traffic(cid,email,up,dn): return _post(cid,f"/panel/api/clients/updateTraffic/{email}",{"upload":up,"download":dn})
def api_cl_ips(cid,email):                  return _post(cid,f"/panel/api/clients/ips/{email}")
def api_cl_clear_ips(cid,email):            return _post(cid,f"/panel/api/clients/clearIps/{email}")
def api_cl_onlines(cid):                    return _post(cid,"/panel/api/clients/onlines")
def api_cl_last_online(cid):                return _post(cid,"/panel/api/clients/lastOnline")
def api_cl_traffic(cid,email):              return _get(cid,f"/panel/api/clients/traffic/{email}")
def api_cl_sub_links(cid,subid):            return _get(cid,f"/panel/api/clients/subLinks/{subid}")
def api_cl_links(cid,email):                return _get(cid,f"/panel/api/clients/links/{email}")
# groups
def api_grp_list(cid):                   return _get(cid,"/panel/api/clients/groups")
def api_grp_emails(cid,name):            return _get(cid,f"/panel/api/clients/groups/{name}/emails")
def api_grp_create(cid,name):            return _post(cid,"/panel/api/clients/groups/create",{"name":name})
def api_grp_rename(cid,old,new):         return _post(cid,"/panel/api/clients/groups/rename",{"oldName":old,"newName":new})
def api_grp_delete(cid,name):            return _post(cid,"/panel/api/clients/groups/delete",{"name":name})
def api_grp_bulk_add(cid,emails,grp):    return _post(cid,"/panel/api/clients/groups/bulkAdd",{"emails":emails,"group":grp})
def api_grp_bulk_remove(cid,emails):     return _post(cid,"/panel/api/clients/groups/bulkRemove",{"emails":emails})

# ── NODES ─────────────────────────────────────────────
def api_nodes(cid):                return _get(cid,"/panel/api/nodes/list")
def api_node(cid,nid):             return _get(cid,f"/panel/api/nodes/get/{safe_int(nid)}")
def api_node_add(cid,p):           return _post(cid,"/panel/api/nodes/add",p)
def api_node_update(cid,nid,p):    return _post(cid,f"/panel/api/nodes/update/{safe_int(nid)}",p)
def api_node_del(cid,nid):         return _post(cid,f"/panel/api/nodes/del/{safe_int(nid)}")
def api_node_enable(cid,nid,en):   return _post(cid,f"/panel/api/nodes/setEnable/{safe_int(nid)}",{"enable":en})
def api_node_test(cid,p):          return _post(cid,"/panel/api/nodes/test",p)
def api_node_probe(cid,nid):       return _post(cid,f"/panel/api/nodes/probe/{safe_int(nid)}")

# ── SETTING ───────────────────────────────────────────
def api_settings_all(cid):          return _post(cid,"/panel/setting/all")
def api_settings_update(cid,p):     return _post(cid,"/panel/setting/update",p)
def api_settings_user(cid,p):       return _post(cid,"/panel/setting/updateUser",p)
def api_restart_panel(cid):         return _post(cid,"/panel/setting/restartPanel")
def api_tokens_list(cid):           return _get(cid,"/panel/setting/apiTokens")
def api_token_create(cid,name):     return _post(cid,"/panel/setting/apiTokens/create",{"name":name})
def api_token_del(cid,tid):         return _post(cid,f"/panel/setting/apiTokens/delete/{safe_int(tid)}")
def api_token_enable(cid,tid,en):   return _post(cid,f"/panel/setting/apiTokens/setEnabled/{safe_int(tid)}",{"enabled":en})

# ── XRAY ──────────────────────────────────────────────
def api_xray_outbound_traffic(cid):         return _get(cid,"/panel/xray/getOutboundsTraffic")
def api_xray_result(cid):                   return _get(cid,"/panel/xray/getXrayResult")
def api_xray_reset_outbound(cid,tag=""):    return _post(cid,"/panel/xray/resetOutboundsTraffic",{"tag":tag} if tag else {})

# ── BACKUP ────────────────────────────────────────────
def api_backup_tg(cid): return _post(cid,"/panel/api/backuptotgbot")

# ── SUBSCRIPTION (مشتری) ──────────────────────────────
def _sub_link(email):
    a=any_admin()
    if not a: return None
    return f"{SETTINGS[a]['url'].rstrip('/')}/sub/{email}"

# ══════════════════════════════════════════════════════
#  ابزارهای کمکی
# ══════════════════════════════════════════════════════
def b2s(b):
    if b==0: return "۰ B"
    for u in ["B","KB","MB","GB","TB"]:
        if abs(b)<1024: return f"{b:.2f} {u}"
        b/=1024
    return f"{b:.2f} PB"
def ms2d(ms):
    if ms==0: return "♾️ نامحدود"
    try: return datetime.datetime.fromtimestamp(ms/1000).strftime("%Y-%m-%d")
    except: return "?"
def days_left(ms):
    if ms==0: return "نامحدود"
    r=(ms/1000)-time.time()
    return f"❌ منقضی" if r<=0 else f"{int(r//86400)} روز"
def tbar(u,t):
    if t==0: return "░░░░░░░░░░ نامحدود"
    p=min(u/t,1); f=int(p*10)
    return f"{'▓'*f}{'░'*(10-f)} {p*100:.0f}%"
def make_qr(text):
    buf=io.BytesIO(); qrcode.make(text).save(buf,format="PNG"); buf.seek(0); return buf
def ib_kb(ibs,action):
    rows=[[InlineKeyboardButton(f"{ib.get('remark','?')} :{ib.get('port','')}",callback_data=f"{action}:{ib['id']}")] for ib in ibs]
    rows.append([InlineKeyboardButton("🔙",callback_data="back")]); return InlineKeyboardMarkup(rows)

# ══════════════════════════════════════════════════════
#  منوها
# ══════════════════════════════════════════════════════
def adm_kb(cid=0):
    return ReplyKeyboardMarkup([
        [t(cid,"menu_status"),   t(cid,"menu_inbounds")],
        [t(cid,"menu_clients"),  t(cid,"menu_traffic")],
        [t(cid,"menu_online"),   t(cid,"menu_backup")],
        [t(cid,"menu_ib_mgmt"),  t(cid,"menu_sales")],
        [t(cid,"menu_settings"), t(cid,"menu_xray")],
        [t(cid,"menu_tokens"),   t(cid,"menu_nodes")],
    ],resize_keyboard=True)

def usr_kb(cid=0):
    return ReplyKeyboardMarkup([
        [t(cid,"menu_my_status"),  t(cid,"menu_buy")],
        [t(cid,"menu_qr"),         t(cid,"menu_conn_info")],
        [t(cid,"menu_links"),      t(cid,"menu_orders")],
        [t(cid,"menu_change_email")],
    ],resize_keyboard=True)

# ══════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════
async def start(u,ctx):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 ورود ادمین",callback_data="mode:admin")],
        [InlineKeyboardButton("👤 ورود مشتری",callback_data="mode:user")],
    ])
    await u.message.reply_text("🤖 *ربات 3X-UI*\n\nنقش خود را انتخاب کنید:",parse_mode="Markdown",reply_markup=kb)

# ══════════════════════════════════════════════════════════════════
#  موتور فرم — هندلرهای تعاملی
# ══════════════════════════════════════════════════════════════════

async def _ask_step(cid: int, ctx, edit_msg=None):
    """سوال قدم فعلی فرم را می‌فرستد"""
    from telegram import InlineKeyboardMarkup
    step = current_step(cid)
    if not step:
        return
    lang = get_lang(cid)
    question = step_question(step, lang, cid)
    typ = step.get("type")

    if typ == "choice":
        rows = make_choice_buttons(step, form_get(cid)["form"], lang)
        kb = InlineKeyboardMarkup(rows)
        if edit_msg:
            try: await edit_msg.edit_text(question, parse_mode="Markdown", reply_markup=kb)
            except: await ctx.bot.send_message(cid, question, parse_mode="Markdown", reply_markup=kb)
        else:
            await ctx.bot.send_message(cid, question, parse_mode="Markdown", reply_markup=kb)
    else:
        cancel_txt = "❌ لغو فرم" if lang == "fa" else "❌ Cancel Form"
        from telegram import InlineKeyboardButton
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(cancel_txt, callback_data="form_cancel")]])
        if edit_msg:
            try: await edit_msg.edit_text(question, parse_mode="Markdown", reply_markup=kb)
            except: await ctx.bot.send_message(cid, question, parse_mode="Markdown", reply_markup=kb)
        else:
            await ctx.bot.send_message(cid, question, parse_mode="Markdown", reply_markup=kb)


async def form_choice_cb(u, ctx):
    """callback انتخاب یک گزینه در فرم"""
    q = u.callback_query; await q.answer(); cid = q.message.chat_id
    # form_choice:{form_name}:{key}:{value}
    parts = q.data.split(":", 3)
    if len(parts) < 4: return
    _, form_name, key, value = parts

    f = form_get(cid)
    if not f or f["form"] != form_name:
        await q.edit_message_text("❌ فرم منقضی شده. دوباره شروع کنید." if get_lang(cid)=="fa"
                                  else "❌ Form expired. Please start again.")
        return

    # ذخیره انتخاب و رفتن به قدم بعد
    form_set(cid, key, value)
    form_next(cid)

    # چک inbound_pick برای تعرفه
    step = current_step(cid)

    if is_form_done(cid):
        await q.edit_message_text("✅ ..." if get_lang(cid)=="fa" else "✅ ...")
        await _finish_form(cid, ctx, q.message)
    elif step and step.get("type") == "inbound_pick":
        await _ask_inbound_pick(cid, ctx, q.message)
    else:
        await _ask_step(cid, ctx, q.message)


async def form_cancel_cb(u, ctx):
    """لغو فرم"""
    q = u.callback_query; await q.answer(); cid = q.message.chat_id
    form_clear(cid)
    lang = get_lang(cid)
    await q.edit_message_text("❌ فرم لغو شد." if lang=="fa" else "❌ Form cancelled.")


async def _ask_inbound_pick(cid: int, ctx, msg=None):
    """نمایش لیست اینباندها برای انتخاب در فرم"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    lang = get_lang(cid)
    admin = any_admin()
    if not admin: return
    r = api_ibs(admin)
    if not r.get("success"): return
    ibs = r.get("obj", [])
    f = form_get(cid)
    form_name = f["form"] if f else "plan"
    rows = [[InlineKeyboardButton(
        f"{ib.get('remark','?')} :{ib.get('port','')}",
        callback_data=f"form_choice:{form_name}:inbound_id:{ib['id']}"
    )] for ib in ibs]
    cancel_txt = "❌ لغو فرم" if lang=="fa" else "❌ Cancel Form"
    rows.append([InlineKeyboardButton(cancel_txt, callback_data="form_cancel")])
    kb = InlineKeyboardMarkup(rows)
    step = current_step(cid)
    q_text = step_question(step, lang, cid) if step else (
        "🔌 اینباند را انتخاب کنید:" if lang=="fa" else "🔌 Select inbound:"
    )
    if msg:
        try: await msg.edit_text(q_text, parse_mode="Markdown", reply_markup=kb)
        except: await ctx.bot.send_message(cid, q_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await ctx.bot.send_message(cid, q_text, parse_mode="Markdown", reply_markup=kb)


async def form_text_input(u, ctx) -> bool:
    """
    اگه کاربر در حال پر کردن فرم بود، ورودی را پردازش کن.
    True: ورودی توسط فرم پردازش شد
    False: فرمی فعال نبود
    """
    cid = u.effective_chat.id
    f = form_get(cid)
    if not f: return False

    lang = get_lang(cid)
    step = current_step(cid)
    if not step: return False

    # قدم‌های choice/inbound_pick نیازی به text ندارند
    if step.get("type") in ("choice", "inbound_pick"):
        return True  # منتظر callback هستیم

    result = process_input(cid, u.message.text.strip(), lang)

    if not result["ok"]:
        await u.message.reply_text(result.get("err", "❌"))
        return True

    if result.get("done"):
        await _finish_form(cid, ctx, None)
    else:
        # چک کن قدم بعد inbound_pick هست؟
        next_step = current_step(cid)
        if next_step and next_step.get("type") == "inbound_pick":
            await _ask_inbound_pick(cid, ctx)
        elif next_step and next_step.get("type") == "choice":
            await _ask_step(cid, ctx)
        else:
            await _ask_step(cid, ctx)
    return True


async def _finish_form(cid: int, ctx, msg=None):
    """پس از تکمیل فرم، عملیات مناسب را انجام بده"""
    f = form_get(cid)
    if not f: return
    form_name = f["form"]
    data      = f["data"]
    lang      = get_lang(cid)
    admin     = cid if is_admin(cid) else any_admin()
    form_clear(cid)

    async def reply(text, kb=None):
        if msg:
            try:
                if kb: await msg.edit_text(text, parse_mode="Markdown", reply_markup=kb)
                else:  await msg.edit_text(text, parse_mode="Markdown")
                return
            except: pass
        await ctx.bot.send_message(cid, text, parse_mode="Markdown", reply_markup=kb)

    # ─────────────────────────────────────────────────────────
    if form_name == "inbound":
        payload = build_inbound_payload(data)
        await reply("⏳ در حال ساخت اینباند..." if lang=="fa" else "⏳ Creating inbound...")
        res = api_ib_add(admin, payload)
        if res.get("success"):
            await ctx.bot.send_message(cid,
                ("✅ اینباند" if lang=="fa" else "✅ Inbound") + f" *{payload['remark']}* " +
                ("ساخته شد!" if lang=="fa" else "created!") + f"\n🔌 `{payload['port']}` | `{payload['protocol']}`",
                parse_mode="Markdown")
        else:
            await ctx.bot.send_message(cid, t(cid,"error",msg=res.get("msg","")))

    elif form_name == "client":
        # tg_id کاربر سفارش‌دهنده را ارسال می‌کنیم تا ایمیل یکتا بشه
        # اگه ادمین داره می‌سازه → tg_id = 0 (ایمیل خام)
        # اگه مشتری داره می‌خره → tg_id از user_cid می‌آید (در order_approve)
        requester_tg_id = data.get("_requester_tg_id", 0)
        client, iids = build_client_payload(data, tg_id=requester_tg_id)
        await reply("⏳ در حال ساخت کلاینت...")
        res = api_cl_add(admin, client, iids)
        if res.get("success"):
            gb  = f"{data.get('total_gb',0)} GB" if data.get("total_gb",0)>0 else "نامحدود"
            exp = f"{data.get('expiry_days',0)} روز" if data.get("expiry_days",0)>0 else "نامحدود"
            await ctx.bot.send_message(cid,
                "✅ کلاینت ساخته شد!\n📧 `" + client["email"] + "`\n📦 " + gb + " | 📅 " + exp,
                parse_mode="Markdown")
        else:
            await ctx.bot.send_message(cid, t(cid,"error",msg=res.get("msg","")))

    elif form_name == "client_edit":
        email    = data.get("_email","")
        original = data.get("_original",{})
        payload  = build_client_edit_payload(original, data)
        res = api_cl_update(admin, email, payload)
        await ctx.bot.send_message(cid,
            "✅ کلاینت آپدیت شد." if res.get("success") else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "plan":
        import uuid as _uuid
        plan = build_plan_payload(data)
        pid  = _uuid.uuid4().hex[:6]
        # PLANS در bot.py تعریف شده — از global می‌گیریم
        import bot as _bot
        _bot.PLANS[pid] = plan
        gb  = "نامحدود" if plan["gb"]==0 else f"{plan['gb']} GB"
        await ctx.bot.send_message(cid, t(cid,"plan_add_ok",
            name=plan["name"], days=plan["days"], gb=gb,
            price=f"{plan['price']:,} {'تومان' if lang=='fa' else ''}"))

    elif form_name == "node":
        payload = build_node_payload(data)
        res = api_node_add(admin, payload)
        await ctx.bot.send_message(cid,
            ("✅ نود افزوده شد." if lang=="fa" else "✅ Node added.") if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "bulk_adjust":
        emails, add_days, add_gb = build_bulk_adjust_payload(data)
        res = api_cl_bulk_adjust(admin, emails, add_days, add_gb)
        await ctx.bot.send_message(cid,
            t(cid,"bulk_adj_ok",count=len(emails)) if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "change_user":
        res = api_settings_user(admin, {
            "oldUsername": data.get("old_username",""),
            "oldPassword": data.get("old_password",""),
            "newUsername": data.get("new_username",""),
            "newPassword": data.get("new_password",""),
        })
        await ctx.bot.send_message(cid,
            ("✅ اطلاعات ورود تغییر کرد." if lang=="fa" else "✅ Credentials updated.") if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "card":
        import bot as _bot, re as _re
        _bot.CARD_NUMBER = _re.sub(r"\D","",data.get("card_number",""))
        _bot.CARD_OWNER  = data.get("card_owner","")
        await ctx.bot.send_message(cid, t(cid,"setcard_ok",
            number=_bot.CARD_NUMBER, owner=_bot.CARD_OWNER))

    elif form_name == "xray_install":
        ver = data.get("version","latest")
        await ctx.bot.send_message(cid, t(cid,"xray_install_loading",ver=ver))
        res = api_install_xray(admin, ver)
        await ctx.bot.send_message(cid,
            t(cid,"xray_install_ok",ver=ver) if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "token":
        res = api_token_create(admin, data.get("name",""))
        if res.get("success"):
            obj = res.get("obj",{})
            await ctx.bot.send_message(cid, t(cid,"token_create_ok",
                token=obj.get("token","?"), name=obj.get("name","?")))
        else:
            await ctx.bot.send_message(cid, t(cid,"error",msg=res.get("msg","")))

    elif form_name == "group":
        res = api_grp_create(admin, data.get("name",""))
        await ctx.bot.send_message(cid,
            t(cid,"group_create_ok",name=data.get("name","")) if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))

    elif form_name == "group_rename":
        res = api_grp_rename(admin, data.get("old_name",""), data.get("new_name",""))
        await ctx.bot.send_message(cid,
            t(cid,"group_rename_ok") if res.get("success")
            else t(cid,"error",msg=res.get("msg","")))


async def mode_cb(u,ctx):
    q=u.callback_query; await q.answer(); cid=q.message.chat_id
    if q.data=="mode:admin":
        if is_admin(cid):
            await q.edit_message_text("✅ پنل ادمین")
            await ctx.bot.send_message(cid,"منو:",reply_markup=adm_kb())
        elif not ALLOWED_IDS:
            await q.edit_message_text("⛔ ALLOWED_ADMINS تنظیم نشده.")
        elif cid not in ALLOWED_IDS:
            logger.warning(f"[SEC] unauthorized admin attempt: {cid}")
            await q.edit_message_text("⛔ مجاز نیستید.")
        else:
            await q.edit_message_text("⚙️ /setup را بزنید.")
    else:
        if cid in USER_EMAILS:
            await q.edit_message_text(f"✅ خوش آمدید!\nایمیل: `{USER_EMAILS[cid]}`",parse_mode="Markdown")
            await ctx.bot.send_message(cid,"منو:",reply_markup=usr_kb())
        else:
            await q.edit_message_text("👤 ایمیل اشتراک VPN خود را وارد کنید:")
            ctx.user_data["conv_state"]=USER_EMAIL

# ══════════════════════════════════════════════════════
#  Setup
# ══════════════════════════════════════════════════════
async def setup_start(u,ctx):
    cid=u.effective_chat.id
    if not ALLOWED_IDS:
        await u.message.reply_text("⛔ ALLOWED_ADMINS در .env خالی است."); return ConversationHandler.END
    if cid not in ALLOWED_IDS:
        logger.warning(f"[SEC] unauthorized /setup: {cid}")
        await u.message.reply_text("⛔ مجاز نیستید."); return ConversationHandler.END
    await u.message.reply_text("🌐 آدرس پنل:\nمثال: `http://1.2.3.4:54321`",
        parse_mode="Markdown",reply_markup=ReplyKeyboardRemove()); return SETUP_URL

async def setup_url(u,ctx):
    ctx.user_data["su"]=u.message.text.strip(); await u.message.reply_text("👤 نام کاربری:"); return SETUP_USER

async def setup_user(u,ctx):
    ctx.user_data["su2"]=u.message.text.strip(); await u.message.reply_text("🔑 رمز عبور:"); return SETUP_PASS

async def setup_pass(u,ctx):
    cid=u.effective_chat.id
    if cid not in ALLOWED_IDS: await u.message.reply_text("⛔"); return ConversationHandler.END
    SETTINGS[cid]={"url":ctx.user_data["su"],"user":ctx.user_data["su2"],"pass":u.message.text.strip()}
    await u.message.reply_text("🔄 در حال اتصال...")
    res=api_login(cid)
    if res["ok"]: ADMINS.add(cid); await u.message.reply_text("✅ متصل شد!",reply_markup=adm_kb())
    else: del SETTINGS[cid]; await u.message.reply_text(f"❌ {res['msg']}")
    return ConversationHandler.END

async def setup_cancel(u,ctx): await u.message.reply_text("❌ لغو."); return ConversationHandler.END

# ══════════════════════════════════════════════════════
#  setcard
# ══════════════════════════════════════════════════════
async def setcard_start(u,ctx):
    cid=u.effective_chat.id
    if not is_admin(cid): await u.message.reply_text("⛔"); return ConversationHandler.END
    await u.message.reply_text("💳 شماره کارت:\n(خط دوم اختیاری: نام صاحب کارت)",reply_markup=ReplyKeyboardRemove())
    return SET_CARD

async def setcard_done(u,ctx):
    global CARD_NUMBER,CARD_OWNER
    cid=u.effective_chat.id
    if not is_admin(cid): return ConversationHandler.END
    parts=u.message.text.strip().split("\n")
    CARD_NUMBER=re.sub(r"\D","",parts[0])
    CARD_OWNER=parts[1].strip() if len(parts)>1 else ""
    if len(CARD_NUMBER) not in (16,19):
        await u.message.reply_text("❌ شماره کارت باید ۱۶ رقم باشد."); return SET_CARD
    logger.info(f"[CARD] {cid} set card {CARD_NUMBER[:4]}****")
    await u.message.reply_text(f"✅ کارت ثبت شد:\n💳 `{CARD_NUMBER}`\n👤 {CARD_OWNER}",
        parse_mode="Markdown",reply_markup=adm_kb()); return ConversationHandler.END

# ══════════════════════════════════════════════════════
#  ── پنل ادمین ──
# ══════════════════════════════════════════════════════

async def adm_status(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    r=api_status(cid)
    if not r.get("success"): await u.message.reply_text(f"❌ {r.get('msg')}"); return
    o=r.get("obj",{}); cpu=o.get("cpu",0); mem=o.get("mem",{}); ni=o.get("netIO",{})
    nt=o.get("netTraffic",{}); xr=o.get("xray",{}); up=o.get("uptime",0); h,rem=divmod(up,3600); m=rem//60
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 لاگ پنل",callback_data="srv:logs"),
         InlineKeyboardButton("📜 لاگ Xray",callback_data="srv:xlogs")],
        [InlineKeyboardButton("🔄 ری‌استارت Xray",callback_data="srv:rxray"),
         InlineKeyboardButton("⛔ توقف Xray",callback_data="srv:stopxray")],
        [InlineKeyboardButton("🔄 ری‌استارت پنل",callback_data="srv:rpanel"),
         InlineKeyboardButton("🔄 آپدیت پنل",callback_data="srv:upanel")],
        [InlineKeyboardButton("🌍 آپدیت GeoFile",callback_data="srv:geo"),
         InlineKeyboardButton("📦 نسخه‌های Xray",callback_data="srv:xver")],
        [InlineKeyboardButton("🔑 UUID جدید",callback_data="srv:uuid"),
         InlineKeyboardButton("🔑 X25519 جدید",callback_data="srv:x25519")],
        [InlineKeyboardButton("🗄 دریافت DB",callback_data="srv:getdb"),
         InlineKeyboardButton("⚡ Config فعلی",callback_data="srv:config")],
        [InlineKeyboardButton("🔭 Xray Observatory",callback_data="srv:obs"),
         InlineKeyboardButton("📊 Xray Metrics",callback_data="srv:metrics")],
    ])
    await u.message.reply_text(
        f"🖥️ *وضعیت سرور*\n\n"
        f"🔲 CPU: `{cpu:.1f}%`\n💾 RAM: `{b2s(mem.get('current',0))}/{b2s(mem.get('total',0))}`\n"
        f"⏱ آپتایم: `{h}h {m}m`\n\n"
        f"📡 لحظه‌ای: ↑`{b2s(ni.get('up',0))}/s` ↓`{b2s(ni.get('down',0))}/s`\n"
        f"📊 کل: ↑`{b2s(nt.get('sent',0))}` ↓`{b2s(nt.get('recv',0))}`\n\n"
        f"⚡ Xray: `{xr.get('state','?')}` v`{xr.get('version','?')}`",
        parse_mode="Markdown",reply_markup=kb)

async def adm_inbounds(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    r=api_ibs(cid)
    if not r.get("success"): await u.message.reply_text(f"❌ {r.get('msg')}"); return
    ibs=r.get("obj",[])
    txt=f"🔗 *اینباندها* ({len(ibs)} عدد)\n\n"
    for ib in ibs:
        try: cls=json.loads(ib.get("settings","{}")).get("clients",[]) if isinstance(ib.get("settings"),str) else (ib.get("settings") or {}).get("clients",[])
        except: cls=[]
        st="✅" if ib.get("enable") else "❌"
        txt+=(f"{st} *{ib.get('remark','?')}*\n"
              f"  `{ib.get('port','?')}` | `{ib.get('protocol','?')}` | 👥{len(cls)}\n"
              f"  ↑`{b2s(ib.get('up',0))}` ↓`{b2s(ib.get('down',0))}`\n\n")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("📋 جزئیات",callback_data="ib:pick")]])
    await u.message.reply_text(txt,parse_mode="Markdown",reply_markup=kb)

async def adm_ib_mgmt(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست اینباندها",callback_data="ib:pick")],
        [InlineKeyboardButton("➕ افزودن اینباند",callback_data="ib:add"),
         InlineKeyboardButton("📥 ایمپورت اینباند",callback_data="ib:import")],
        [InlineKeyboardButton("✏️ ویرایش اینباند",callback_data="ib:edit_pick"),
         InlineKeyboardButton("🗑 حذف اینباند",callback_data="ib:del_pick")],
        [InlineKeyboardButton("🔛 فعال/غیرفعال",callback_data="ib:toggle_pick"),
         InlineKeyboardButton("🔄 ریست ترافیک",callback_data="ib:reset_pick")],
        [InlineKeyboardButton("🗑 حذف همه کلاینت‌ها",callback_data="ib:delclients_pick"),
         InlineKeyboardButton("🔄 ریست همه اینباندها",callback_data="ib:resetall")],
    ])
    await u.message.reply_text("🛠 *مدیریت اینباندها*",parse_mode="Markdown",reply_markup=kb)

async def adm_clients(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست همه کلاینت‌ها",callback_data="cl:list")],
        [InlineKeyboardButton("🔍 جستجو با ایمیل",callback_data="cl:search"),
         InlineKeyboardButton("➕ افزودن کلاینت",callback_data="cl:add")],
        [InlineKeyboardButton("🗑 حذف کلاینت",callback_data="cl:del"),
         InlineKeyboardButton("✏️ آپدیت کلاینت",callback_data="cl:update_pick")],
        [InlineKeyboardButton("🔄 ریست ترافیک",callback_data="cl:reset_pick"),
         InlineKeyboardButton("♻️ ریست همه",callback_data="cl:resetall_confirm")],
        [InlineKeyboardButton("🧹 حذف منقضی‌ها",callback_data="cl:deldepleted"),
         InlineKeyboardButton("🚫 پاک IP ها",callback_data="cl:clearips_ask")],
        [InlineKeyboardButton("🔗 لینک‌های اتصال",callback_data="cl:links_ask"),
         InlineKeyboardButton("⏰ آخرین آنلاین",callback_data="cl:lastonline")],
        [InlineKeyboardButton("📦 Bulk Adjust",callback_data="cl:bulk_adjust"),
         InlineKeyboardButton("🗑 Bulk Delete",callback_data="cl:bulk_del")],
        [InlineKeyboardButton("👥 مدیریت گروه‌ها",callback_data="cl:groups")],
    ])
    await u.message.reply_text("👥 *مدیریت کلاینت‌ها*",parse_mode="Markdown",reply_markup=kb)

async def adm_traffic_ask(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    await u.message.reply_text("📈 ایمیل کلاینت:"); ctx.user_data["conv_state"]=CL_SEARCH_EMAIL

async def adm_online(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    r=api_cl_onlines(cid); cls=r.get("obj") or []
    if not cls: await u.message.reply_text("😴 هیچ‌کس آنلاین نیست."); return
    await u.message.reply_text(f"🌐 *آنلاین‌ها* ({len(cls)})\n\n"+"".join(f"• `{c}`\n" for c in cls),parse_mode="Markdown")

async def adm_backup(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 ارسال DB به تلگرام",callback_data="backup:tg")],
        [InlineKeyboardButton("🗄 دانلود DB",callback_data="backup:db")],
    ])
    await u.message.reply_text("💾 *پشتیبان‌گیری*",parse_mode="Markdown",reply_markup=kb)

async def adm_settings(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    cfg=SETTINGS.get(cid,{})
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 همه تنظیمات",callback_data="set:all")],
        [InlineKeyboardButton("👤 تغییر یوزر/پسورد",callback_data="set:user"),
         InlineKeyboardButton("🔄 ری‌استارت پنل",callback_data="srv:rpanel")],
    ])
    await u.message.reply_text(
        f"⚙️ *تنظیمات*\n\n🌐 `{cfg.get('url','—')}`\n👤 `{cfg.get('user','—')}`\n"
        f"🔗 {'✅' if cid in SESSIONS else '❌'}\n"
        f"💳 `{CARD_NUMBER or '—'}` {CARD_OWNER}\n\n/setup — /setcard — /reconnect",
        parse_mode="Markdown",reply_markup=kb)

async def adm_xray_srv(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 لاگ Xray",callback_data="srv:xlogs"),
         InlineKeyboardButton("⚡ Xray Config",callback_data="srv:config")],
        [InlineKeyboardButton("🔄 ری‌استارت Xray",callback_data="srv:rxray"),
         InlineKeyboardButton("⛔ توقف Xray",callback_data="srv:stopxray")],
        [InlineKeyboardButton("📦 نصب نسخه Xray",callback_data="srv:install_xray"),
         InlineKeyboardButton("📦 لیست نسخه‌ها",callback_data="srv:xver")],
        [InlineKeyboardButton("📊 ترافیک Outbound",callback_data="srv:outbound_traffic"),
         InlineKeyboardButton("🔄 ریست Outbound",callback_data="srv:reset_outbound")],
        [InlineKeyboardButton("🌍 آپدیت GeoFile",callback_data="srv:geo"),
         InlineKeyboardButton("🔭 Observatory",callback_data="srv:obs")],
        [InlineKeyboardButton("🔑 UUID جدید",callback_data="srv:uuid"),
         InlineKeyboardButton("🔑 X25519 جدید",callback_data="srv:x25519")],
    ])
    await u.message.reply_text("🔧 *Xray / سرور*",parse_mode="Markdown",reply_markup=kb)

async def adm_tokens(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    r=api_tokens_list(cid)
    if not r.get("success"): await u.message.reply_text(f"❌ {r.get('msg')}"); return
    tokens=r.get("obj",[]) or []
    txt="🔑 *API Token ها*\n\n"
    for t in tokens:
        en="✅" if t.get("enabled") else "❌"
        txt+=f"{en} `{t.get('name','?')}` — ID:`{t.get('id','?')}`\n"
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ توکن جدید",callback_data="tok:create"),
         InlineKeyboardButton("🗑 حذف توکن",callback_data="tok:del_ask")],
        [InlineKeyboardButton("🔛 فعال/غیرفعال",callback_data="tok:toggle_ask")],
    ])
    await u.message.reply_text(txt or "📭 توکنی وجود ندارد.",parse_mode="Markdown",reply_markup=kb)

async def adm_nodes(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    r=api_nodes(cid)
    if not r.get("success"): await u.message.reply_text(f"❌ {r.get('msg')}"); return
    nodes=r.get("obj",[]) or []
    txt=f"📡 *نودها* ({len(nodes)} عدد)\n\n"
    for n in nodes:
        h="✅" if n.get("enable") else "❌"
        txt+=f"{h} *{n.get('name','?')}* — `{n.get('address','?')}:{n.get('port','?')}`\n"
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن نود",callback_data="node:add_ask"),
         InlineKeyboardButton("🔭 تست نود",callback_data="node:test_ask")],
    ])
    await u.message.reply_text(txt or "📭 نودی وجود ندارد.",parse_mode="Markdown",reply_markup=kb)

# ══════════════════════════════════════════════════════
#  مدیریت فروش
# ══════════════════════════════════════════════════════
async def adm_sales(u,ctx):
    cid=u.effective_chat.id
    if not _adm(cid): await u.message.reply_text("⛔"); return
    pending=[oid for oid,o in ORDERS.items() if o["status"]=="pending"]
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 تعرفه‌ها ({len(PLANS)})",callback_data="sales:plans")],
        [InlineKeyboardButton(f"⏳ در انتظار ({len(pending)})",callback_data="sales:pending"),
         InlineKeyboardButton("📊 همه سفارش‌ها",callback_data="sales:all")],
        [InlineKeyboardButton("➕ افزودن تعرفه",callback_data="sales:addplan"),
         InlineKeyboardButton("💳 تنظیم کارت",callback_data="sales:setcard")],
    ])
    await u.message.reply_text("🛒 *مدیریت فروش*",parse_mode="Markdown",reply_markup=kb)

def plans_text():
    if not PLANS: return "📭 تعرفه‌ای نیست."
    t="📋 *تعرفه‌ها:*\n\n"
    for pid,p in PLANS.items():
        gb="نامحدود" if p["gb"]==0 else f"{p['gb']}GB"
        t+=f"🔹 *{p['name']}* | {p['days']}روز | {gb} | {fmt_price(p['price'])}\n"
    return t

# ══════════════════════════════════════════════════════
#  پنل مشتری
# ══════════════════════════════════════════════════════
def _userinfo(email):
    a=any_admin(); return None if not a else (lambda r: r.get("obj") if r.get("success") and r.get("obj") else None)(api_cl_traffic(a,email))

async def usr_status(u,ctx):
    cid=u.effective_chat.id; email=USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    c=_userinfo(email)
    if not c: await u.message.reply_text(f"❌ `{email}` یافت نشد.",parse_mode="Markdown"); return
    up=c.get("up",0); dn=c.get("down",0); used=up+dn; tot=c.get("total",0); exp=c.get("expiryTime",0)
    await u.message.reply_text(
        f"📊 *وضعیت اشتراک*\n\n📧 `{email}`\n{'✅' if c.get('enable') else '❌'}\n\n"
        f"📦 مصرف: `{b2s(used)}`\nباقی: `{b2s(max(0,tot-used)) if tot>0 else '♾️'}`\n"
        f"کل: `{b2s(tot) if tot>0 else '♾️'}`\n{tbar(used,tot)}\n\n"
        f"📅 `{ms2d(exp)}` ({days_left(exp)})\n↑`{b2s(up)}` ↓`{b2s(dn)}`",
        parse_mode="Markdown")

async def usr_qr(u,ctx):
    cid=u.effective_chat.id; email=USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    lnk=_sub_link(email)
    if not lnk: await u.message.reply_text("⚠️ سرور در دسترس نیست."); return
    await ctx.bot.send_photo(cid,make_qr(lnk),caption=f"📱 `{lnk}`",parse_mode="Markdown")

async def usr_conn(u,ctx):
    cid=u.effective_chat.id; email=USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    a=any_admin()
    if not a: await u.message.reply_text("⚠️ سرور در دسترس نیست."); return
    r=api_cl_get(a,email)
    if not r.get("success") or not r.get("obj"):
        await u.message.reply_text(f"❌ `{email}` یافت نشد.",parse_mode="Markdown"); return
    c=r["obj"]
    await u.message.reply_text(
        f"📋 *اطلاعات اتصال*\n\n📧 `{email}`\n🆔 `{c.get('id','?')}`\n"
        f"🔗 sub:\n`{_sub_link(email)}`",
        parse_mode="Markdown")

async def usr_links(u,ctx):
    cid=u.effective_chat.id; email=USER_EMAILS.get(cid)
    if not email: await u.message.reply_text("❌ /start → ورود مشتری"); return
    a=any_admin()
    if not a: await u.message.reply_text("⚠️ سرور در دسترس نیست."); return
    r=api_cl_links(a,email)
    if not r.get("success") or not r.get("obj"):
        await u.message.reply_text("❌ لینکی یافت نشد."); return
    links=r["obj"] if isinstance(r["obj"],list) else [r["obj"]]
    txt="🔗 *لینک‌های اتصال:*\n\n"
    for l in links[:10]: txt+=f"`{l}`\n\n"
    await u.message.reply_text(txt,parse_mode="Markdown")

async def usr_orders(u,ctx):
    cid=u.effective_chat.id
    my=[o for o in ORDERS.values() if o["user_cid"]==cid]
    if not my: await u.message.reply_text("📭 سفارشی ندارید."); return
    st={"pending":"⏳","approved":"✅","rejected":"❌"}
    txt="📦 *سفارش‌های شما:*\n\n"
    for o in sorted(my,key=lambda x:x["ts"],reverse=True)[:10]:
        p=PLANS.get(o["plan_id"],{}); ts=datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
        txt+=f"{st.get(o['status'],'?')} #{o['id']} — {p.get('name','?')} | {ts}\n"
    await u.message.reply_text(txt,parse_mode="Markdown")

async def usr_change_email(u,ctx):
    await u.message.reply_text("🔄 ایمیل جدید:",reply_markup=ReplyKeyboardRemove())
    ctx.user_data["conv_state"]=USER_EMAIL

# ══════════════════════════════════════════════════════
#  جریان خرید
# ══════════════════════════════════════════════════════
async def usr_buy(u,ctx):
    cid=u.effective_chat.id
    if not PLANS: await u.message.reply_text("😔 تعرفه‌ای فعال نیست."); return
    if not CARD_NUMBER: await u.message.reply_text("⚠️ سیستم پرداخت راه‌اندازی نشده."); return
    rows=[[InlineKeyboardButton(
        f"🔹 {p['name']} — {p['days']}روز {'∞' if p['gb']==0 else str(p['gb'])+'GB'} — {fmt_price(p['price'])}",
        callback_data=f"buy:{pid}")] for pid,p in PLANS.items()]
    rows.append([InlineKeyboardButton("❌ انصراف",callback_data="back")])
    await u.message.reply_text("🛒 *خرید / تمدید*\n\nتعرفه انتخاب کنید:",parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows))

async def buy_plan_selected(q,ctx,pid):
    cid=q.message.chat_id; p=PLANS.get(pid)
    if not p: await q.edit_message_text("❌ تعرفه یافت نشد."); return
    ctx.user_data["buy_plan"]=pid
    gb="نامحدود" if p["gb"]==0 else f"{p['gb']} GB"
    email=USER_EMAILS.get(cid); kind="تمدید اشتراک" if (email and _userinfo(email)) else "خرید اشتراک جدید"
    cf=" - ".join([CARD_NUMBER[i:i+4] for i in range(0,len(CARD_NUMBER),4)])
    await q.edit_message_text(
        f"🧾 *{kind}*\n\n📦 {p['name']} | {p['days']}روز | {gb}\n💰 *{fmt_price(p['price'])}*\n\n"
        f"━━━━━━━━━━━\n💳 `{cf}`\n👤 {CARD_OWNER}\n━━━━━━━━━━━\n\n📸 تصویر رسید را ارسال کنید.",
        parse_mode="Markdown")
    ctx.user_data["conv_state"]=BUY_RECEIPT

async def receipt_received(u,ctx):
    cid=u.effective_chat.id; pid=ctx.user_data.get("buy_plan")
    if not pid: return
    p=PLANS.get(pid)
    if not p: await u.message.reply_text("❌ تعرفه دیگر معتبر نیست."); ctx.user_data.pop("conv_state",None); return
    now=time.time()
    if now-LAST_RECEIPT.get(cid,0)<RECEIPT_COOLDOWN:
        await u.message.reply_text(f"⏳ {int(RECEIPT_COOLDOWN-(now-LAST_RECEIPT.get(cid,0)))} ثانیه صبر کنید."); return
    if pending_count(cid)>=3:
        await u.message.reply_text("⚠️ ۳ سفارش در انتظار دارید."); return
    file_id=u.message.photo[-1].file_id if u.message.photo else (u.message.document.file_id if u.message.document else None)
    if not file_id: await u.message.reply_text("📸 تصویر رسید ارسال کنید."); return
    LAST_RECEIPT[cid]=now; oid=new_oid(); email=USER_EMAILS.get(cid,"ثبت‌نشده")
    ORDERS[oid]={"id":oid,"user_cid":cid,"plan_id":pid,"ts":now,"status":"pending","receipt_file_id":file_id,"email":email}
    ctx.user_data.pop("conv_state",None); ctx.user_data.pop("buy_plan",None)
    logger.info(f"[ORDER] {oid} from {cid} email={email} plan={pid}")
    await u.message.reply_text(
        f"✅ *رسید دریافت شد!*\n\n🔖 `#{oid}`\n📦 {p['name']}\n⏳ در حال بررسی...",
        parse_mode="Markdown",reply_markup=usr_kb())
    gb="نامحدود" if p.get("gb",0)==0 else f"{p['gb']}GB"
    admin_txt=(f"🔔 *سفارش جدید!*\n\n🔖 #{oid}\n👤 `{cid}`\n📧 `{email}`\n"
               f"📦 {p['name']} — {p['days']}روز — {gb}\n💰 {fmt_price(p['price'])}\n"
               f"🕐 {datetime.datetime.now().strftime('%H:%M:%S')}")
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و فعال‌سازی",callback_data=f"order:approve:{oid}")],
        [InlineKeyboardButton("❌ رد کردن",callback_data=f"order:reject:{oid}")],
    ])
    for ac in ADMINS:
        try: await ctx.bot.send_photo(ac,photo=file_id,caption=admin_txt,parse_mode="Markdown",reply_markup=kb)
        except Exception as e: logger.warning(f"send admin {ac}: {e}")

# ══════════════════════════════════════════════════════
#  تأیید/رد سفارش
# ══════════════════════════════════════════════════════
async def order_approve(q,ctx,oid):
    cid=q.message.chat_id
    if not is_admin(cid): await q.answer("⛔",show_alert=True); return
    o=ORDERS.get(oid)
    if not o: await q.edit_message_caption("❌ یافت نشد."); return
    if o["status"]!="pending": await q.edit_message_caption(f"⚠️ قبلاً {o['status']} شده."); return
    p=PLANS.get(o["plan_id"])
    if not p: await q.edit_message_caption("❌ تعرفه حذف شده."); return
    email=o.get("email",""); user_cid=o["user_cid"]
    if not email or email=="ثبت‌نشده": await q.edit_message_caption("❌ ایمیل ثبت نشده."); return
    await q.edit_message_caption(f"⏳ پردازش #{oid}...")
    # بررسی کلاینت موجود
    existing=None
    r=api_cl_get(cid,email)
    if r.get("success") and r.get("obj"): existing=r["obj"]
    days=p.get("days",30); gb=p.get("gb",0); iid=p.get("inbound_id")
    now_ms=int(time.time()*1000); new_exp=now_ms+int(days*86400*1000)
    if existing:
        old_exp=existing.get("expiryTime",0)
        if old_exp>now_ms: new_exp=old_exp+int(days*86400*1000)
        old_total=existing.get("totalGB",0)
        new_total=(old_total+int(gb*1024**3)) if gb>0 else 0
        res=api_cl_update(cid,email,{
            "email":email,"totalGB":new_total,"expiryTime":new_exp,
            "enable":True,"tgId":existing.get("tgId",0),"limitIp":existing.get("limitIp",0)
        }); action=f"🔄 تمدید تا {ms2d(new_exp)}"
    else:
        if not iid: await ctx.bot.send_message(cid,"❌ اینباند تعرفه تنظیم نشده."); return
        # ایمیل یکتا: username@tgid_مشتری
        from forms import build_email, sanitize_username
        raw_name = email.split("@")[0] if "@" in email else email
        unique_email = build_email(sanitize_username(raw_name), user_cid)
        client={"email":unique_email,"totalGB":int(gb*1024**3),"expiryTime":new_exp,
                "enable":True,"tgId":user_cid,"limitIp":0}
        res=api_cl_add(cid,client,[iid]); action=f"✅ کلاینت جدید | {days}روز"
    if not res.get("success"):
        logger.error(f"[ORDER] {oid} panel error: {res.get('msg')}")
        await ctx.bot.send_message(cid,f"❌ خطا پنل: {res.get('msg')}"); return
    ORDERS[oid]["status"]="approved"; ORDERS[oid]["approved_by"]=cid; ORDERS[oid]["approved_at"]=time.time()
    logger.info(f"[ORDER] {oid} approved by {cid}")
    await q.edit_message_caption(f"✅ سفارش #{oid} تأیید شد\n{action}",parse_mode="Markdown")
    await ctx.bot.send_message(user_cid,
        f"🎉 *اشتراک فعال شد!*\n\n🔖 `#{oid}`\n📦 {p['name']}\n{action}\n\n🔗 `{_sub_link(email)}`",
        parse_mode="Markdown")

async def order_reject(q,ctx,oid):
    cid=q.message.chat_id
    if not is_admin(cid): await q.answer("⛔",show_alert=True); return
    o=ORDERS.get(oid)
    if not o: await q.edit_message_caption("❌"); return
    if o["status"]!="pending": await q.edit_message_caption(f"⚠️ قبلاً {o['status']} شده."); return
    ORDERS[oid]["status"]="rejected"; ORDERS[oid]["rejected_by"]=cid
    logger.info(f"[ORDER] {oid} rejected by {cid}")
    await q.edit_message_caption(f"❌ سفارش #{oid} رد شد.")
    p=PLANS.get(o["plan_id"],{})
    await ctx.bot.send_message(o["user_cid"],
        f"❌ *سفارش رد شد*\n\n🔖 #{oid} — {p.get('name','?')}",parse_mode="Markdown")

# ══════════════════════════════════════════════════════
#  Callback مرکزی
# ══════════════════════════════════════════════════════
async def cb_handler(u,ctx):
    q=u.callback_query; await q.answer(); cid=q.message.chat_id; d=q.data or ""

    if d.startswith("form_choice:"): return await form_choice_cb(u,ctx)
    if d == "form_cancel":           return await form_cancel_cb(u,ctx)
    if d in("mode:admin","mode:user"): return await mode_cb(u,ctx)
    if d=="back": await q.edit_message_text("🏠"); return
    if d.startswith("buy:"): return await buy_plan_selected(q,ctx,d[4:])
    if d.startswith("order:approve:"): return await order_approve(q,ctx,d.split(":")[-1])
    if d.startswith("order:reject:"):  return await order_reject(q,ctx,d.split(":")[-1])

    if not is_admin(cid):
        logger.warning(f"[SEC] non-admin {cid} callback: {d}")
        await q.edit_message_text("⛔"); return
    if not _check(cid): await q.edit_message_text("❌ اتصال قطع. /reconnect"); return

    # ── اینباند ──────────────────────────────────────
    if d=="ib:pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("انتخاب:",reply_markup=ib_kb(r["obj"],"ib:show"))
        return
    if d.startswith("ib:show:"):
        iid=safe_int(d.split(":")[2]); r=api_ib(cid,iid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        ib=r["obj"]
        try:
            s=ib.get("settings","{}"); cls=(json.loads(s) if isinstance(s,str) else s).get("clients",[])
        except: cls=[]
        txt=(f"📋 *{ib.get('remark','?')}*\n`{ib.get('port')}` | `{ib.get('protocol')}`\n"
             f"👥{len(cls)} | ↑`{b2s(ib.get('up',0))}` ↓`{b2s(ib.get('down',0))}`\n"
             f"{'✅' if ib.get('enable') else '❌'}\n\n*کلاینت‌ها:*\n")
        for c in cls[:20]:
            used=c.get("up",0)+c.get("down",0)
            tot=b2s(c.get("totalGB",0)) if c.get("totalGB",0)>0 else "∞"
            txt+=f"  {'✅' if c.get('enable') else '❌'} `{c.get('email','?')}` | {b2s(used)}/{tot} | {ms2d(c.get('expiryTime',0))}\n"
        if len(cls)>20: txt+=f"  ...و {len(cls)-20} دیگر\n"
        await q.edit_message_text(txt,parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 ریست ترافیک",callback_data=f"ib:reset:{iid}"),
                 InlineKeyboardButton("🔛 فعال/غیرفعال",callback_data=f"ib:toggle:{iid}")],
                [InlineKeyboardButton("🗑 حذف همه کلاینت‌ها",callback_data=f"ib:delclients:{iid}"),
                 InlineKeyboardButton("🔗 Fallbacks",callback_data=f"ib:fallbacks:{iid}")],
                [InlineKeyboardButton("🗑 حذف اینباند",callback_data=f"ib:del_confirm:{iid}")],
                [InlineKeyboardButton("🔙",callback_data="ib:pick")]
            ]))
        return
    if d=="ib:add":
        form_start(cid, "inbound")
        await _ask_step(cid, ctx, q.message); return
    if d=="ib:import":
        await q.edit_message_text("📥 JSON اینباند برای ایمپورت را وارد کنید:")
        ctx.user_data["conv_state"]=IB_IMPORT_JSON; return
    if d=="ib:edit_pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("ویرایش:",reply_markup=ib_kb(r["obj"],"ib:edit")); return
    if d.startswith("ib:edit:"):
        iid=safe_int(d.split(":")[2]); ctx.user_data["tib"]=iid
        r=api_ib(cid,iid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        await q.edit_message_text(f"✏️ JSON جدید برای *{r['obj'].get('remark','?')}*:",parse_mode="Markdown")
        ctx.user_data["conv_state"]=IB_EDIT_JSON; return
    if d=="ib:del_pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("حذف:",reply_markup=ib_kb(r["obj"],"ib:del_confirm")); return
    if d.startswith("ib:del_confirm:"):
        iid=safe_int(d.split(":")[2]); r=api_ib(cid,iid)
        remark=r["obj"].get("remark","?") if r.get("success") else "?"
        await q.edit_message_text(f"⚠️ حذف *{remark}*؟",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله",callback_data=f"ib:del_ok:{iid}"),
             InlineKeyboardButton("❌ انصراف",callback_data="back")]
        ])); return
    if d.startswith("ib:del_ok:"):
        iid=safe_int(d.split(":")[2]); res=api_ib_del(cid,iid)
        logger.info(f"[DEL_IB] {cid} deleted inbound {iid}")
        await q.edit_message_text("✅ حذف شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d.startswith("ib:reset:"):
        iid=safe_int(d.split(":")[2]); res=api_ib_reset_traffic(cid,iid)
        await q.edit_message_text("✅ ترافیک اینباند ریست شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="ib:resetall":
        res=api_ibs_reset_all(cid)
        await q.edit_message_text("✅ ترافیک همه اینباندها ریست شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d.startswith("ib:toggle:"):
        iid=safe_int(d.split(":")[2]); r=api_ib(cid,iid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        cur=r["obj"].get("enable",True); res=api_ib_enable(cid,iid,not cur)
        await q.edit_message_text(f"✅ {'فعال' if not cur else 'غیرفعال'} شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="ib:toggle_pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("انتخاب:",reply_markup=ib_kb(r["obj"],"ib:toggle")); return
    if d=="ib:reset_pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("انتخاب:",reply_markup=ib_kb(r["obj"],"ib:reset")); return
    if d.startswith("ib:delclients:"):
        iid=safe_int(d.split(":")[2])
        await q.edit_message_text("⚠️ حذف همه کلاینت‌های این اینباند؟",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله",callback_data=f"ib:delclients_ok:{iid}"),
             InlineKeyboardButton("❌ انصراف",callback_data="back")]
        ])); return
    if d.startswith("ib:delclients_ok:"):
        iid=safe_int(d.split(":")[2]); res=api_ib_del_all_clients(cid,iid)
        await q.edit_message_text("✅ همه کلاینت‌ها حذف شدند." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="ib:delclients_pick":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("انتخاب:",reply_markup=ib_kb(r["obj"],"ib:delclients")); return
    if d.startswith("ib:fallbacks:"):
        iid=safe_int(d.split(":")[2]); r=api_ib_fallbacks_get(cid,iid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        await q.edit_message_text(f"🔗 Fallbacks اینباند {iid}:\n```\n{json.dumps(r.get('obj',{}),ensure_ascii=False,indent=2)}\n```",parse_mode="Markdown"); return

    # ── کلاینت ───────────────────────────────────────
    if d=="cl:list":
        r=api_cl_list(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        clients=r.get("obj",[]) or []
        txt=f"👥 *کلاینت‌ها* ({len(clients)})\n\n"
        for c in clients[:30]:
            used=c.get("up",0)+c.get("down",0)
            tot=b2s(c.get("totalGB",0)) if c.get("totalGB",0)>0 else "∞"
            en="✅" if c.get("enable") else "❌"
            txt+=f"{en} `{c.get('email','?')}` | {b2s(used)}/{tot} | {ms2d(c.get('expiryTime',0))}\n"
        if len(clients)>30: txt+=f"...و {len(clients)-30} دیگر\n"
        await q.edit_message_text(txt,parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="cl:search":
        await q.edit_message_text("🔍 ایمیل:"); ctx.user_data["conv_state"]=CL_SEARCH_EMAIL; return
    if d=="cl:add":
        r=api_ibs(cid)
        if r.get("success"): await q.edit_message_text("اینباند:",reply_markup=ib_kb(r["obj"],"cl:add_ib")); return
    if d.startswith("cl:add_ib:"):
        form_start(cid, "client")
        form_set(cid, "inbound_id", safe_int(d.split(":")[2]))
        await _ask_step(cid, ctx, q.message); return
    if d=="cl:del":
        await q.edit_message_text("🗑 ایمیل کلاینت برای حذف:"); ctx.user_data["conv_state"]=CL_DEL_EMAIL; return
    if d.startswith("cl:del_ok:"):
        email=d.split(":",2)[2]; res=api_cl_del(cid,email)
        logger.info(f"[DEL_CL] {cid} deleted {email}")
        await q.edit_message_text("✅ حذف شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d.startswith("cl:del_cancel:"): await q.edit_message_text("❌ لغو شد."); return
    if d=="cl:update_pick":
        await q.edit_message_text(t(cid,"client_update_ask"), parse_mode="Markdown")
        ctx.user_data["conv_state"]=CL_UPDATE_EMAIL; return
    if d=="cl:reset_pick":
        await q.edit_message_text("🔄 ایمیل کلاینت:"); ctx.user_data["conv_state"]=CL_RESET_EMAIL; return
    if d=="cl:resetall_confirm":
        await q.edit_message_text("⚠️ ریست ترافیک همه کلاینت‌ها؟",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله",callback_data="cl:resetall_ok"),
             InlineKeyboardButton("❌ خیر",callback_data="back")]
        ])); return
    if d=="cl:resetall_ok":
        res=api_cl_reset_all(cid)
        await q.edit_message_text("✅ همه ریست شدند." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="cl:deldepleted":
        res=api_cl_del_depleted(cid)
        await q.edit_message_text("✅ منقضی‌ها حذف شدند." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="cl:clearips_ask":
        await q.edit_message_text("🚫 ایمیل کلاینت:"); ctx.user_data["conv_state"]=CL_CLEAR_IPS; return
    if d=="cl:links_ask":
        await q.edit_message_text("🔗 ایمیل کلاینت:"); ctx.user_data["conv_state"]=CL_SEARCH_EMAIL; ctx.user_data["cl_action"]="links"; return
    if d=="cl:lastonline":
        r=api_cl_last_online(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        obj=r.get("obj") or {}
        txt="⏰ *آخرین آنلاین:*\n\n"
        for email,ts in list(obj.items())[:20]:
            dt=datetime.datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else "?"
            txt+=f"• `{email}` — {dt}\n"
        await q.edit_message_text(txt,parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="cl:bulk_adjust":
        form_start(cid, "bulk_adjust")
        await _ask_step(cid, ctx, q.message); return
    if d=="cl:bulk_del":
        await q.edit_message_text("🗑 ایمیل‌ها را با کاما وارد کنید:")
        ctx.user_data["conv_state"]="BULK_DEL"; return
    if d=="cl:groups":
        r=api_grp_list(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        grps=r.get("obj",[]) or []
        txt="👥 *گروه‌ها:*\n\n"
        for g in grps: txt+=f"• `{g.get('name','?')}` — {g.get('count',0)} نفر\n"
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ گروه جدید",callback_data="grp:create"),
             InlineKeyboardButton("✏️ تغییر نام",callback_data="grp:rename")],
            [InlineKeyboardButton("🗑 حذف گروه",callback_data="grp:delete")],
            [InlineKeyboardButton("🔙",callback_data="back")]
        ])
        await q.edit_message_text(txt or "📭 گروهی نیست.",parse_mode="Markdown",reply_markup=kb); return
    if d=="grp:create":
        form_start(cid, "group")
        await _ask_step(cid, ctx, q.message); return
    if d=="grp:rename":
        form_start(cid, "group_rename")
        await _ask_step(cid, ctx, q.message); return
    if d=="grp:delete":
        await q.edit_message_text("نام گروه برای حذف:"); ctx.user_data["conv_state"]="GRP_DELETE"; return

    # ── سرور ─────────────────────────────────────────
    if d=="srv:logs":
        await q.edit_message_text("⏳ دریافت لاگ...")
        r=api_logs(cid,50)
        lines=(r.get("obj") or "")[:3000]
        await q.edit_message_text(f"📜 *لاگ پنل (۵۰ خط)*\n```\n{lines}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:xlogs":
        await q.edit_message_text("⏳ دریافت لاگ Xray...")
        r=api_xray_logs(cid,50)
        lines=(r.get("obj") or "")[:3000]
        await q.edit_message_text(f"📜 *لاگ Xray (۵۰ خط)*\n```\n{lines}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:rxray":
        res=api_restart_xray(cid)
        await q.edit_message_text("✅ Xray ری‌استارت شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="srv:stopxray":
        await q.edit_message_text("⚠️ توقف Xray؟",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله",callback_data="srv:stopxray_ok"),
             InlineKeyboardButton("❌ خیر",callback_data="back")]
        ])); return
    if d=="srv:stopxray_ok":
        res=api_stop_xray(cid)
        await q.edit_message_text("✅ Xray متوقف شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="srv:rpanel":
        res=api_restart_panel(cid)
        await q.edit_message_text("✅ پنل ری‌استارت شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="srv:upanel":
        await q.edit_message_text("⚠️ آپدیت پنل؟",reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله",callback_data="srv:upanel_ok"),
             InlineKeyboardButton("❌ خیر",callback_data="back")]
        ])); return
    if d=="srv:upanel_ok":
        res=api_update_panel(cid)
        await q.edit_message_text("✅ آپدیت شد. پنل ری‌استارت می‌شود." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="srv:geo":
        await q.edit_message_text("⏳ آپدیت GeoFile...")
        res=api_update_geofile(cid)
        await q.edit_message_text("✅ GeoFile آپدیت شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="srv:xver":
        r=api_get_xray_versions(cid)
        versions=r.get("obj",[]) if r.get("success") else []
        if isinstance(versions,list): txt="📦 *نسخه‌های Xray:*\n\n"+"".join(f"• `{v}`\n" for v in versions[:20])
        else: txt=str(versions)[:500]
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 نصب نسخه",callback_data="srv:install_xray"),InlineKeyboardButton("🔙",callback_data="back")]])
        await q.edit_message_text(txt,parse_mode="Markdown",reply_markup=kb); return
    if d=="srv:install_xray":
        form_start(cid, "xray_install")
        await _ask_step(cid, ctx, q.message); return
    if d=="srv:uuid":
        r=api_new_uuid(cid)
        obj=r.get("obj",{}) if r.get("success") else {}
        uuid_val=obj.get("uuid",obj) if isinstance(obj,dict) else str(obj)
        await q.edit_message_text(f"🔑 UUID جدید:\n`{uuid_val}`",parse_mode="Markdown"); return
    if d=="srv:x25519":
        r=api_new_x25519(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        obj=r.get("obj",{}) or {}
        await q.edit_message_text(
            f"🔑 *X25519 کیپر جدید:*\n\n🔒 Private:\n`{obj.get('privateKey','?')}`\n\n🔓 Public:\n`{obj.get('publicKey','?')}`",
            parse_mode="Markdown"); return
    if d=="srv:getdb":
        await q.edit_message_text("⏳ دریافت DB..."); r=api_get_db(cid)
        await q.edit_message_text("✅ DB دریافت شد." if r.get("success") else f"❌ {r.get('msg')}"); return
    if d=="srv:config":
        r=api_get_config_json(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        cfg=json.dumps(r.get("obj",{}),ensure_ascii=False,indent=2)[:3000]
        await q.edit_message_text(f"⚡ *Xray Config:*\n```json\n{cfg}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:obs":
        r=api_xray_obs(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        txt=json.dumps(r.get("obj",{}),ensure_ascii=False,indent=2)[:2000]
        await q.edit_message_text(f"🔭 *Observatory:*\n```\n{txt}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:metrics":
        r=api_xray_metrics(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        txt=json.dumps(r.get("obj",{}),ensure_ascii=False,indent=2)[:2000]
        await q.edit_message_text(f"📊 *Xray Metrics:*\n```\n{txt}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:outbound_traffic":
        r=api_xray_outbound_traffic(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        obs=r.get("obj",[]) or []
        txt="📊 *Outbound Traffic:*\n\n"
        for o in obs: txt+=f"• `{o.get('tag','?')}` ↑`{b2s(o.get('up',0))}` ↓`{b2s(o.get('down',0))}`\n"
        await q.edit_message_text(txt or "📭 داده‌ای نیست.",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return
    if d=="srv:reset_outbound":
        res=api_xray_reset_outbound(cid)
        await q.edit_message_text("✅ ریست شد." if res.get("success") else f"❌ {res.get('msg')}"); return

    # ── بکاپ ─────────────────────────────────────────
    if d=="backup:tg":
        await q.edit_message_text("⏳ ارسال بکاپ..."); res=api_backup_tg(cid)
        await q.edit_message_text("✅ بکاپ به تلگرام ارسال شد." if res.get("success") else f"❌ {res.get('msg')}"); return
    if d=="backup:db":
        await q.edit_message_text("⏳ دریافت DB..."); r=api_get_db(cid)
        await q.edit_message_text("✅ DB دریافت شد." if r.get("success") else f"❌ {r.get('msg')}"); return

    # ── تنظیمات ──────────────────────────────────────
    if d=="set:user":
        form_start(cid, "change_user")
        await _ask_step(cid, ctx, q.message); return
    if d=="set:all":
        r=api_settings_all(cid)
        if not r.get("success"): await q.edit_message_text(f"❌ {r.get('msg')}"); return
        txt=json.dumps(r.get("obj",{}),ensure_ascii=False,indent=2)[:3000]
        await q.edit_message_text(f"⚙️ *تنظیمات پنل:*\n```json\n{txt}\n```",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return

    # ── API Token ها ──────────────────────────────────
    if d=="tok:create":
        form_start(cid, "token")
        await _ask_step(cid, ctx, q.message); return
    if d=="tok:del_ask":
        await q.edit_message_text("ID توکن برای حذف:"); ctx.user_data["conv_state"]="TOK_DEL"; return
    if d=="tok:toggle_ask":
        await q.edit_message_text("ID توکن (و وضعیت true/false):"); ctx.user_data["conv_state"]="TOK_TOGGLE"; return

    # ── فروش ─────────────────────────────────────────
    if d=="sales:plans":
        kb=InlineKeyboardMarkup([
            *[[InlineKeyboardButton(f"🗑 {p['name']}",callback_data=f"sales:delplan:{pid}")] for pid,p in PLANS.items()],
            [InlineKeyboardButton("➕ افزودن",callback_data="sales:addplan"),
             InlineKeyboardButton("🔙",callback_data="back")]
        ])
        await q.edit_message_text(plans_text(),parse_mode="Markdown",reply_markup=kb); return
    if d=="sales:addplan":
        form_start(cid, "plan")
        await _ask_step(cid, ctx, q.message); return
    if d.startswith("sales:delplan:"):
        pid=d.split(":")[-1]
        if pid in PLANS: name=PLANS.pop(pid)["name"]; await q.edit_message_text(f"🗑 «{name}» حذف شد.")
        else: await q.edit_message_text("❌ یافت نشد.")
        return
    if d=="sales:setcard":
        form_start(cid, "card")
        await _ask_step(cid, ctx, q.message); return
    if d=="sales:pending":
        pending={oid:o for oid,o in ORDERS.items() if o["status"]=="pending"}
        if not pending: await q.edit_message_text("✅ رسید در انتظاری نیست."); return
        txt="⏳ *در انتظار:*\n\n"; rows=[]
        for oid,o in pending.items():
            p=PLANS.get(o["plan_id"],{}); ts=datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
            txt+=f"🔹 #{oid} | `{o.get('email','?')}` | {p.get('name','?')} | {ts}\n"
            rows.append([InlineKeyboardButton(f"✅ #{oid}",callback_data=f"order:approve:{oid}"),
                         InlineKeyboardButton(f"❌ #{oid}",callback_data=f"order:reject:{oid}")])
        rows.append([InlineKeyboardButton("🔙",callback_data="back")])
        await q.edit_message_text(txt,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(rows)); return
    if d=="sales:all":
        if not ORDERS: await q.edit_message_text("📭 سفارشی نیست."); return
        st={"pending":"⏳","approved":"✅","rejected":"❌"}; txt="📊 *سفارش‌ها:*\n\n"
        for o in sorted(ORDERS.values(),key=lambda x:x["ts"],reverse=True)[:20]:
            p=PLANS.get(o["plan_id"],{}); ts=datetime.datetime.fromtimestamp(o["ts"]).strftime("%m/%d %H:%M")
            txt+=f"{st.get(o['status'],'?')} #{o['id']} | `{o.get('email','?')}` | {p.get('name','?')} | {ts}\n"
        await q.edit_message_text(txt,parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙",callback_data="back")]])); return

    # ── انتخاب اینباند برای تعرفه ─────────────────────
    if d.startswith("pickib:"):
        iid=safe_int(d.split(":")[1])
        pid=uuid.uuid4().hex[:6]
        PLANS[pid]={"name":ctx.user_data.get("pn","?"),"price":ctx.user_data.get("pp",0),
                    "days":ctx.user_data.get("pd",30),"gb":ctx.user_data.get("pgb",0),"inbound_id":iid}
        p=PLANS[pid]; gb="نامحدود" if p["gb"]==0 else f"{p['gb']}GB"
        logger.info(f"[PLAN] {cid} added {pid}: {p['name']}")
        await q.edit_message_text(f"✅ تعرفه افزوده شد!\n📦 {p['name']} | {p['days']}روز | {gb}\n💰 {fmt_price(p['price'])}",
            parse_mode="Markdown"); return

# ══════════════════════════════════════════════════════
#  هندلر متن مرکزی
# ══════════════════════════════════════════════════════
async def text_handler(u,ctx):
    cid=u.effective_chat.id; txt=u.message.text.strip(); state=ctx.user_data.get("conv_state")

    # ── فرم تعاملی ───────────────────────────────────
    if await form_text_input(u, ctx):
        return

    # ── منوی ادمین ────────────────────────────────────
    if txt==t(cid,"menu_status"):        return await adm_status(u,ctx)
    if txt==t(cid,"menu_inbounds"):          return await adm_inbounds(u,ctx)
    if txt==t(cid,"menu_clients"):          return await adm_clients(u,ctx)
    if txt==t(cid,"menu_traffic"):      return await adm_traffic_ask(u,ctx)
    if txt==t(cid,"menu_online"):           return await adm_online(u,ctx)
    if txt==t(cid,"menu_backup"):               return await adm_backup(u,ctx)
    if txt==t(cid,"menu_ib_mgmt"):   return await adm_ib_mgmt(u,ctx)
    if txt==t(cid,"menu_sales"):               return await adm_sales(u,ctx)
    if txt==t(cid,"menu_settings"):       return await adm_settings(u,ctx)
    if txt==t(cid,"menu_xray"):        return await adm_xray_srv(u,ctx)
    if txt==t(cid,"menu_tokens"):       return await adm_tokens(u,ctx)
    if txt==t(cid,"menu_nodes"):              return await adm_nodes(u,ctx)

    # ── منوی مشتری ────────────────────────────────────
    if txt==t(cid,"menu_my_status"):      return await usr_status(u,ctx)
    if txt==t(cid,"menu_buy"):       return await usr_buy(u,ctx)
    if txt==t(cid,"menu_qr"):              return await usr_qr(u,ctx)
    if txt==t(cid,"menu_conn_info"):     return await usr_conn(u,ctx)
    if txt==t(cid,"menu_links"):    return await usr_links(u,ctx)
    if txt==t(cid,"menu_orders"):    return await usr_orders(u,ctx)
    if txt==t(cid,"menu_change_email"):        return await usr_change_email(u,ctx)

    # ── رسید خرید (پیام متنی اشتباه) ─────────────────
    if state==BUY_RECEIPT:
        await u.message.reply_text("📸 لطفاً تصویر رسید را ارسال کنید."); return

    # ── ثبت ایمیل مشتری ──────────────────────────────
    if state==USER_EMAIL:
        from forms import sanitize_username, build_email, is_valid_username
        raw = txt.strip().lower()
        # جدا کردن بخش نام (قبل از @ اگه کاربر خودش @ زده)
        raw = raw.split("@")[0]
        username = sanitize_username(raw)
        if not is_valid_username(username):
            await u.message.reply_text(
                "❌ نام کاربری نامعتبر!\n\n"
                "• فقط حروف انگلیسی کوچک مجاز است\n"
                "• اعداد، _ و - هم قابل استفاده‌اند\n"
                "• بدون فاصله\n\n"
                "مثال: `ali` یا `user123`",
                parse_mode="Markdown")
            return
        # ساختن ایمیل یکتا با TG ID کاربر
        email = build_email(username, cid)
        a=any_admin()
        if not a: await u.message.reply_text("⚠️ سرور پیکربندی نشده."); return
        c=_userinfo(email)
        if not c:
            # شاید با ایمیل خام (بدون @tgid) موجود باشه — برای کاربرهای قدیمی
            c_old = _userinfo(username)
            if c_old:
                # کاربر قدیمی — ایمیل قدیمی رو نگه می‌داریم
                email = username
                c = c_old
        if not c:
            kb=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 خرید اشتراک",callback_data="buy_now")]])
            await u.message.reply_text(
                f"❌ اشتراکی با نام `{username}` پیدا نشد.\n\n"
                f"_(ایمیل جستجو‌شده: `{email}`)_\n\n"
                "اشتراک خریداری کنید:",
                parse_mode="Markdown", reply_markup=kb)
            return
        USER_EMAILS[cid]=email; ctx.user_data.pop("conv_state",None)
        logger.info(f"[USER] {cid} registered {email}")
        await u.message.reply_text(
            f"✅ ورود موفق!\n📧 `{email}`",
            parse_mode="Markdown", reply_markup=usr_kb(cid)); return

    # ── تعرفه‌ها ──────────────────────────────────────
    if state==PLAN_NAME:  ctx.user_data["pn"]=txt[:50]; await u.message.reply_text("💰 قیمت به تومان:"); ctx.user_data["conv_state"]=PLAN_PRICE; return
    if state==PLAN_PRICE:
        v=safe_int(txt.replace(",","").replace("،",""),-1)
        if v<0: await u.message.reply_text("❌ عدد معتبر:"); return
        ctx.user_data["pp"]=v; await u.message.reply_text("📅 روز:"); ctx.user_data["conv_state"]=PLAN_DAYS; return
    if state==PLAN_DAYS:
        v=safe_int(txt,-1)
        if v<=0: await u.message.reply_text("❌ عدد مثبت:"); return
        ctx.user_data["pd"]=v; await u.message.reply_text("📦 GB (0=نامحدود):"); ctx.user_data["conv_state"]=PLAN_GB; return
    if state==PLAN_GB:
        if not _adm(cid): return
        v=safe_float(txt,-1)
        if v<0: await u.message.reply_text("❌ عدد (0 یا بیشتر):"); return
        ctx.user_data["pgb"]=v
        r=api_ibs(cid)
        if not r.get("success"): await u.message.reply_text(f"❌ {r.get('msg')}"); return
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"{ib.get('remark','?')} :{ib.get('port','')}",callback_data=f"pickib:{ib['id']}")] for ib in r.get("obj",[])])
        await u.message.reply_text("🔌 اینباند پیش‌فرض تعرفه:",reply_markup=kb)
        ctx.user_data.pop("conv_state",None); return

    # ── کارت ─────────────────────────────────────────
    if state==SET_CARD:
        global CARD_NUMBER,CARD_OWNER
        if not is_admin(cid): return
        parts=txt.split("\n"); CARD_NUMBER=re.sub(r"\D","",parts[0]); CARD_OWNER=parts[1].strip() if len(parts)>1 else ""
        if len(CARD_NUMBER) not in (16,19): await u.message.reply_text("❌ ۱۶ رقم:"); return
        ctx.user_data.pop("conv_state",None); logger.info(f"[CARD] {cid} {CARD_NUMBER[:4]}****")
        await u.message.reply_text(f"✅ `{CARD_NUMBER}` | {CARD_OWNER}",parse_mode="Markdown",reply_markup=adm_kb()); return

    # ── عملیات ادمین روی کلاینت ──────────────────────
    if not is_admin(cid) or not _check(cid): return

    if state==CL_EMAIL:
        email=sanitize(txt)
        if not email: await u.message.reply_text("❌ ایمیل نامعتبر:"); return
        ctx.user_data["cl_email"]=email; await u.message.reply_text("📦 حجم GB (0=نامحدود):"); ctx.user_data["conv_state"]=CL_GB; return
    if state==CL_GB:
        v=safe_float(txt,-1)
        if v<0: await u.message.reply_text("❌ عدد:"); return
        ctx.user_data["cl_gb"]=v; await u.message.reply_text("📅 روز انقضا (0=نامحدود):"); ctx.user_data["conv_state"]=CL_DAYS; return
    if state==CL_DAYS:
        days=safe_int(txt,-1)
        if days<0: await u.message.reply_text("❌ عدد:"); return
        email=ctx.user_data.get("cl_email",""); gb=ctx.user_data.get("cl_gb",0); iid=ctx.user_data.get("tib")
        exp=0
        if days>0: exp=int((time.time()+days*86400)*1000)
        client={"email":email,"totalGB":int(gb*1024**3),"expiryTime":exp,"enable":True,"tgId":0,"limitIp":0}
        res=api_cl_add(cid,client,[iid] if iid else [])
        if res.get("success"):
            await u.message.reply_text(f"✅ کلاینت `{email}` ساخته شد\n📦 {gb or '∞'}GB | 📅 {days or '∞'}روز",parse_mode="Markdown")
        else: await u.message.reply_text(f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    if state==CL_SEARCH_EMAIL:
        email=sanitize(txt); action=ctx.user_data.pop("cl_action","search")
        if action=="links":
            r=api_cl_links(cid,email)
            if not r.get("success") or not r.get("obj"): await u.message.reply_text(f"❌ `{email}` یافت نشد.",parse_mode="Markdown")
            else:
                links=r["obj"] if isinstance(r["obj"],list) else [r["obj"]]
                txt_out=f"🔗 *لینک‌های {email}:*\n\n"+"".join(f"`{l}`\n\n" for l in links[:10])
                await u.message.reply_text(txt_out,parse_mode="Markdown")
        else:
            r=api_cl_traffic(cid,email)
            if not r.get("success") or not r.get("obj"):
                await u.message.reply_text(f"❌ `{email}` یافت نشد.",parse_mode="Markdown")
            else:
                c=r["obj"]; used=c.get("up",0)+c.get("down",0); tot=c.get("total",0)
                r2=api_cl_ips(cid,email); ips=r2.get("obj") or []
                await u.message.reply_text(
                    f"📊 *{email}*\n\n{'✅' if c.get('enable') else '❌'}\n"
                    f"↑`{b2s(c.get('up',0))}` ↓`{b2s(c.get('down',0))}`\n"
                    f"کل: `{b2s(tot) if tot>0 else '♾️'}` | {tbar(used,tot)}\n"
                    f"انقضا: `{ms2d(c.get('expiryTime',0))}` ({days_left(c.get('expiryTime',0))})\n"
                    +( f"IP‌ها: {', '.join(ips[:5])}" if ips else ""),
                    parse_mode="Markdown")
        ctx.user_data.pop("conv_state",None); return

    if state==CL_DEL_EMAIL:
        email=sanitize(txt)
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ حذف شود",callback_data=f"cl:del_ok:{email}"),
             InlineKeyboardButton("❌ انصراف",callback_data=f"cl:del_cancel:{email}")]
        ])
        await u.message.reply_text(f"⚠️ حذف `{email}`؟",parse_mode="Markdown",reply_markup=kb)
        ctx.user_data.pop("conv_state",None); return

    if state==CL_UPDATE_EMAIL:
        email=sanitize(txt)
        r=api_cl_get(cid,email)
        if not r.get("success") or not r.get("obj"):
            await u.message.reply_text(t(cid,"client_not_found",email=email), parse_mode="Markdown")
            ctx.user_data.pop("conv_state",None); return
        c=r["obj"]
        # شروع فرم ویرایش با ذخیره اطلاعات اصلی
        form_start(cid, "client_edit")
        form_set(cid, "_email",    email)
        form_set(cid, "_original", c)
        ctx.user_data.pop("conv_state",None)
        await _ask_step(cid, ctx); return

    if state==CL_RESET_EMAIL:
        email=sanitize(txt); res=api_cl_reset_traffic(cid,email)
        await u.message.reply_text("✅ ریست شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    if state==CL_CLEAR_IPS:
        email=sanitize(txt); res=api_cl_clear_ips(cid,email)
        await u.message.reply_text(f"✅ IP‌های `{email}` پاک شد." if res.get("success") else f"❌ {res.get('msg')}",parse_mode="Markdown")
        ctx.user_data.pop("conv_state",None); return

    # ── اینباند ───────────────────────────────────────
    if state==IB_ADD_JSON:
        try: payload=json.loads(txt)
        except: await u.message.reply_text("❌ JSON نامعتبر:"); return
        res=api_ib_add(cid,payload); logger.info(f"[ADD_IB] {cid}")
        await u.message.reply_text("✅ اینباند افزوده شد!" if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    if state==IB_IMPORT_JSON:
        res=api_ib_import(cid,txt); logger.info(f"[IMPORT_IB] {cid}")
        await u.message.reply_text("✅ ایمپورت شد!" if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    if state==IB_EDIT_JSON:
        try: payload=json.loads(txt)
        except: await u.message.reply_text("❌ JSON نامعتبر:"); return
        iid=ctx.user_data.get("tib"); res=api_ib_update(cid,iid,payload)
        logger.info(f"[UPDATE_IB] {cid} inbound {iid}")
        await u.message.reply_text("✅ ویرایش شد!" if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    # ── سرور ──────────────────────────────────────────
    if state==SRV_INSTALL_VER:
        ver=txt.strip()
        await u.message.reply_text(f"⏳ نصب Xray {ver}...")
        res=api_install_xray(cid,ver)
        await u.message.reply_text("✅ نصب شد!" if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    # ── Bulk ──────────────────────────────────────────
    if state=="BULK_ADJUST":
        lines=txt.split("\n")
        if len(lines)<2: await u.message.reply_text("❌ فرمت نادرست."); return
        emails=[e.strip() for e in lines[0].split(",") if e.strip()]
        days=gb=0
        for l in lines[1:]:
            if "روز:" in l: days=safe_int(l.split(":")[1])
            if "GB:" in l: gb=safe_float(l.split(":")[1])
        res=api_cl_bulk_adjust(cid,emails,days,gb)
        await u.message.reply_text(f"✅ {len(emails)} کلاینت آپدیت شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    if state=="BULK_DEL":
        emails=[e.strip() for e in txt.split(",") if e.strip()]
        res=api_cl_bulk_del(cid,emails)
        await u.message.reply_text(f"✅ {len(emails)} کلاینت حذف شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    # ── گروه‌ها ───────────────────────────────────────
    if state=="GRP_CREATE":
        res=api_grp_create(cid,txt.strip())
        await u.message.reply_text(f"✅ گروه «{txt}» ساخته شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return
    if state=="GRP_RENAME_OLD":
        ctx.user_data["grp_old"]=txt.strip(); await u.message.reply_text("نام جدید گروه:")
        ctx.user_data["conv_state"]="GRP_RENAME_NEW"; return
    if state=="GRP_RENAME_NEW":
        res=api_grp_rename(cid,ctx.user_data.get("grp_old",""),txt.strip())
        await u.message.reply_text("✅ تغییر نام داده شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return
    if state=="GRP_DELETE":
        res=api_grp_delete(cid,txt.strip())
        await u.message.reply_text("✅ گروه حذف شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

    # ── توکن ──────────────────────────────────────────
    if state=="TOK_CREATE":
        res=api_token_create(cid,txt.strip())
        if res.get("success"):
            t=res.get("obj",{}); await u.message.reply_text(f"✅ توکن ساخته شد!\n🔑 `{t.get('token','?')}`\n📛 {t.get('name','?')}",parse_mode="Markdown")
        else: await u.message.reply_text(f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return
    if state=="TOK_DEL":
        res=api_token_del(cid,safe_int(txt))
        await u.message.reply_text("✅ توکن حذف شد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return
    if state=="TOK_TOGGLE":
        parts=txt.split(); tid=safe_int(parts[0]); en=parts[1].lower()=="true" if len(parts)>1 else True
        res=api_token_enable(cid,tid,en)
        await u.message.reply_text("✅ وضعیت تغییر کرد." if res.get("success") else f"❌ {res.get('msg')}")
        ctx.user_data.pop("conv_state",None); return

# رسید عکسی
async def photo_handler(u,ctx):
    if ctx.user_data.get("conv_state")==BUY_RECEIPT: await receipt_received(u,ctx)

# ══════════════════════════════════════════════════════
#  دستورات عمومی
# ══════════════════════════════════════════════════════
async def reconnect(u,ctx):
    cid=u.effective_chat.id
    if not is_admin(cid): await u.message.reply_text("⛔"); return
    res=api_login(cid)
    await u.message.reply_text("✅ متصل شد!" if res["ok"] else f"❌ {res['msg']}")

async def help_cmd(u,ctx):
    await u.message.reply_text(
        "📖 *ربات 3X-UI — راهنما*\n\n"
        "/start — انتخاب نقش\n/setup — تنظیم پنل (فقط ادمین‌های مجاز)\n"
        "/setcard — تنظیم شماره کارت\n/reconnect — اتصال مجدد\n/help — راهنما\n\n"
        "*ادمین:* وضعیت سرور، اینباندها، کلاینت‌ها، Xray، تنظیمات، نودها، API Tokenها، فروش\n"
        "*مشتری:* وضعیت، خرید، QR، لینک، سفارش‌ها",
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════
#  اجرا
# ══════════════════════════════════════════════════════
def main():
    global CARD_NUMBER,CARD_OWNER
    token=os.environ.get("BOT_TOKEN","").strip()
    CARD_NUMBER=os.environ.get("CARD_NUMBER","").strip()
    CARD_OWNER=os.environ.get("CARD_OWNER","").strip()
    allowed_raw=os.environ.get("ALLOWED_ADMINS","").strip()
    if allowed_raw:
        for a in allowed_raw.split(","):
            a=a.strip()
            if a.lstrip("-").isdigit(): ALLOWED_IDS.add(int(a))
    if not token:
        ep=os.path.join(os.path.dirname(__file__),".env")
        print("━"*50,"\n❌ BOT_TOKEN یافت نشد!\n")
        print(f"📝 فایل .env:\n   {ep}\n")
        print("  BOT_TOKEN=...\n  CARD_NUMBER=...\n  CARD_OWNER=...\n  ALLOWED_ADMINS=chat_id_شما")
        print("━"*50,"\n💡 cp .env.example .env"); return
    if not ALLOWED_IDS: print("⚠️  ALLOWED_ADMINS تنظیم نشده — هیچ‌کس نمی‌تواند ادمین شود.")
    app=Application.builder().token(token).build()
    setup_conv=ConversationHandler(
        entry_points=[CommandHandler("setup",setup_start)],
        states={SETUP_URL:[MessageHandler(filters.TEXT&~filters.COMMAND,setup_url)],
                SETUP_USER:[MessageHandler(filters.TEXT&~filters.COMMAND,setup_user)],
                SETUP_PASS:[MessageHandler(filters.TEXT&~filters.COMMAND,setup_pass)]},
        fallbacks=[CommandHandler("cancel",setup_cancel)])
    setcard_conv=ConversationHandler(
        entry_points=[CommandHandler("setcard",setcard_start)],
        states={SET_CARD:[MessageHandler(filters.TEXT&~filters.COMMAND,setcard_done)]},
        fallbacks=[CommandHandler("cancel",setup_cancel)])
    app.add_handler(setup_conv); app.add_handler(setcard_conv)
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("reconnect",reconnect))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,photo_handler))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,text_handler))
    logger.info("🤖 ربات 3X-UI (نسخه کامل) راه‌اندازی شد.")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
