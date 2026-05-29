"""
strings.py — رشته‌های متنی فارسی ربات 3X-UI
"""

_S: dict = {}  # placeholder — متن‌ها مستقیم در bot.py هستند

def t(cid: int, key: str, **kwargs) -> str:
    """دریافت متن از دیکشنری — fallback به key اگه پیدا نشد"""
    text = STRINGS.get(key, key)
    if kwargs:
        try:    return text.format(**kwargs)
        except: return text
    return text

def get_lang(cid: int) -> str:
    return "fa"

def set_lang(cid: int, lang: str):
    pass  # فعلاً فقط فارسی

USER_LANG: dict = {}

STRINGS = {


    # ── عمومی ─────────────────────────────────────────────────────
    "back":               "🔙 بازگشت",
    "yes_confirm":        "✅ بله",
    "no_cancel":          "❌ انصراف",
    "loading":            "⏳ در حال دریافت...",
    "success":            "✅ موفق",
    "error":              "❌ خطا: {msg}",
    "unauthorized":       "⛔ دسترسی ندارید.",
    "connection_lost":    "❌ اتصال قطع است. /reconnect را بزنید.",
    "invalid_input":      "❌ ورودی نامعتبر.",
    "invalid_number":     "❌ عدد معتبری وارد کنید:",
    "invalid_positive":   "❌ عدد مثبت وارد کنید:",
    "invalid_json":       "❌ JSON نامعتبر است. مجدداً وارد کنید:",
    "invalid_email":      "❌ ایمیل نامعتبر است.",
    "invalid_card":       "❌ شماره کارت باید ۱۶ رقم باشد.",
    "cancelled":          "❌ عملیات لغو شد.",
    "not_found":          "❌ مورد یافت نشد.",
    "change_lang":        "🌐 تغییر زبان",

    # ── انتخاب زبان ───────────────────────────────────────────────
    "choose_lang":        "🌐 لطفاً زبان خود را انتخاب کنید:\nPlease choose your language:",
    "lang_set":           "✅ زبان فارسی فعال شد.",
    "btn_lang_fa":        "🇮🇷 فارسی",
    "btn_lang_en":        "🇬🇧 English",

    # ── /start ────────────────────────────────────────────────────
    "welcome":            "🤖 *ربات مدیریت پنل 3X-UI*\n\nنقش خود را انتخاب کنید:",
    "btn_admin":          "👑 ورود ادمین",
    "btn_user":           "👤 ورود مشتری",

    # ── ورود ادمین ────────────────────────────────────────────────
    "admin_welcome":      "✅ به پنل ادمین خوش آمدید!",
    "admin_menu":         "منوی ادمین:",
    "admin_no_allowed":   "⛔ `ALLOWED_ADMINS` در فایل `.env` تنظیم نشده است.",
    "admin_not_allowed":  "⛔ شما مجاز به ورود ادمین نیستید.",
    "admin_do_setup":     "⚙️ برای تنظیم پنل دستور /setup را بزنید.",

    # ── Setup ─────────────────────────────────────────────────────
    "setup_ask_url":      "⚙️ *تنظیم پنل 3X-UI*\n\nآدرس پنل را وارد کنید:\nمثال: `http://1.2.3.4:54321`",
    "setup_ask_user":     "👤 نام کاربری پنل:",
    "setup_ask_pass":     "🔑 رمز عبور پنل:",
    "setup_connecting":   "🔄 در حال اتصال به پنل...",
    "setup_ok":           "✅ اتصال برقرار شد!",
    "setup_fail":         "❌ خطا در اتصال: {msg}\nمجدداً /setup را بزنید.",
    "setup_not_allowed":  "⛔ شما مجاز به اجرای این دستور نیستید.",
    "setup_no_allowed_ids": "⛔ `ALLOWED_ADMINS` در `.env` خالی است.\nتا زمانی که این مقدار تنظیم نشود، هیچ‌کس نمی‌تواند ادمین شود.",

    # ── setcard ───────────────────────────────────────────────────
    "setcard_ask":        "💳 شماره کارت را وارد کنید:\n(خط دوم اختیاری: نام صاحب کارت)\n\nمثال:\n`6037991234567890\nعلی محمدی`",
    "setcard_ok":         "✅ کارت ثبت شد:\n💳 `{number}`\n👤 {owner}",

    # ── reconnect ─────────────────────────────────────────────────
    "reconnect_ok":       "✅ اتصال مجدد برقرار شد!",
    "reconnect_fail":     "❌ اتصال ناموفق: {msg}",

    # ── منوی ادمین (keyboard) ─────────────────────────────────────
    "menu_status":        "📊 وضعیت سرور",
    "menu_inbounds":      "🔗 اینباندها",
    "menu_clients":       "👥 کلاینت‌ها",
    "menu_traffic":       "📈 ترافیک کلاینت",
    "menu_online":        "🌐 آنلاین‌ها",
    "menu_backup":        "💾 بکاپ",
    "menu_ib_mgmt":       "🛠 مدیریت اینباندها",
    "menu_sales":         "🛒 فروش",
    "menu_settings":      "⚙️ تنظیمات پنل",
    "menu_xray":          "🔧 Xray / سرور",
    "menu_tokens":        "🔑 API Token ها",
    "menu_nodes":         "📡 نودها",

    # ── منوی مشتری (keyboard) ─────────────────────────────────────
    "menu_my_status":     "📊 وضعیت اشتراک",
    "menu_buy":           "🛒 خرید / تمدید",
    "menu_qr":            "📱 QR کد",
    "menu_conn_info":     "📋 اطلاعات اتصال",
    "menu_links":         "🔗 لینک‌های اتصال",
    "menu_orders":        "🔔 وضعیت سفارش‌ها",
    "menu_change_email":  "🔄 تغییر ایمیل",

    # ── وضعیت سرور ───────────────────────────────────────────────
    "server_status_title": "🖥️ *وضعیت سرور*",
    "server_cpu":         "🔲 CPU: `{val}%`",
    "server_ram":         "💾 RAM: `{cur}/{total}`",
    "server_uptime":      "⏱ آپتایم: `{h}h {m}m`",
    "server_net_rt":      "📡 *ترافیک لحظه‌ای*",
    "server_net_total":   "📊 *کل ترافیک*",
    "server_up":          "↑`{val}/s`",
    "server_down":        "↓`{val}/s`",
    "server_xray":        "⚡ Xray: `{state}` v`{ver}`",
    "btn_panel_log":      "📜 لاگ پنل",
    "btn_xray_log":       "📜 لاگ Xray",
    "btn_restart_xray":   "🔄 ری‌استارت Xray",
    "btn_stop_xray":      "⛔ توقف Xray",
    "btn_restart_panel":  "🔄 ری‌استارت پنل",
    "btn_update_panel":   "🔄 آپدیت پنل",
    "btn_update_geo":     "🌍 آپدیت GeoFile",
    "btn_xray_versions":  "📦 نسخه‌های Xray",
    "btn_new_uuid":       "🔑 UUID جدید",
    "btn_new_x25519":     "🔑 X25519 جدید",
    "btn_get_db":         "🗄 دریافت DB",
    "btn_config":         "⚡ Config فعلی",
    "btn_observatory":    "🔭 Xray Observatory",
    "btn_metrics":        "📊 Xray Metrics",

    # ── اینباندها ─────────────────────────────────────────────────
    "inbounds_title":     "🔗 *اینباندها* ({count} عدد)",
    "inbound_detail":     "📋 جزئیات",
    "inbound_clients_label": "*کلاینت‌ها:*",
    "inbound_more":       "  ...و {n} دیگر",
    "inbound_enabled":    "✅ فعال",
    "inbound_disabled":   "❌ غیرفعال",
    "no_inbounds":        "⚠️ اینباندی یافت نشد.",
    "btn_ib_list":        "📋 لیست اینباندها",
    "btn_ib_add":         "➕ افزودن اینباند",
    "btn_ib_import":      "📥 ایمپورت اینباند",
    "btn_ib_edit":        "✏️ ویرایش اینباند",
    "btn_ib_del":         "🗑 حذف اینباند",
    "btn_ib_toggle":      "🔛 فعال/غیرفعال",
    "btn_ib_reset":       "🔄 ریست ترافیک",
    "btn_ib_del_clients": "🗑 حذف همه کلاینت‌ها",
    "btn_ib_reset_all":   "🔄 ریست همه اینباندها",

    # ── عملیات اینباند ────────────────────────────────────────────
    "ib_add_ask":         "➕ JSON اینباند جدید را وارد کنید:\n(مثال: `{{\"remark\":\"test\",\"port\":443,\"protocol\":\"vless\",...}}`)",
    "ib_import_ask":      "📥 JSON اینباند برای ایمپورت را وارد کنید:",
    "ib_edit_ask":        "✏️ JSON جدید برای *{remark}*:",
    "ib_del_confirm":     "⚠️ حذف اینباند *{remark}*؟\nتمام کلاینت‌های آن هم حذف می‌شوند!",
    "ib_del_ok":          "✅ اینباند حذف شد.",
    "ib_reset_ok":        "✅ ترافیک اینباند ریست شد.",
    "ib_reset_all_ok":    "✅ ترافیک همه اینباندها ریست شد.",
    "ib_toggle_on":       "✅ اینباند فعال شد.",
    "ib_toggle_off":      "✅ اینباند غیرفعال شد.",
    "ib_add_ok":          "✅ اینباند افزوده شد!",
    "ib_import_ok":       "✅ ایمپورت شد!",
    "ib_edit_ok":         "✅ ویرایش شد!",
    "ib_del_clients_ok":  "✅ همه کلاینت‌ها حذف شدند.",
    "ib_del_clients_confirm": "⚠️ حذف همه کلاینت‌های این اینباند؟",
    "btn_ib_reset_traffic": "🔄 ریست ترافیک",
    "btn_ib_toggle_en":   "🔛 فعال/غیرفعال",
    "btn_ib_fallbacks":   "🔗 Fallbacks",
    "btn_ib_del_confirm": "🗑 حذف اینباند",
    "ib_select_edit":     "اینباندی که می‌خواهید ویرایش کنید را انتخاب کنید:",
    "ib_select_del":      "⚠️ اینباندی که می‌خواهید حذف کنید را انتخاب کنید:",
    "ib_select_toggle":   "اینباند را انتخاب کنید:",
    "ib_select_reset":    "اینباند را انتخاب کنید:",
    "ib_select_delclients": "اینباند را انتخاب کنید:",

    # ── کلاینت‌ها ─────────────────────────────────────────────────
    "clients_title":      "👥 *مدیریت کلاینت‌ها*",
    "clients_list_title": "👥 *کلاینت‌ها* ({count})",
    "clients_more":       "...و {n} دیگر",
    "client_not_found":   "❌ کلاینت `{email}` یافت نشد.",
    "client_ask_email":   "✏️ ایمیل کلاینت جدید:",
    "client_ask_gb":      "📦 حجم ترافیک GB (0 = نامحدود):",
    "client_ask_days":    "📅 روز انقضا (0 = نامحدود):",
    "client_add_ok":      "✅ کلاینت `{email}` ساخته شد\n📦 {gb} | 📅 {days}",
    "client_del_confirm": "⚠️ حذف کلاینت `{email}`؟",
    "client_del_ok":      "✅ کلاینت حذف شد.",
    "client_update_ask":  "✏️ ایمیل کلاینت برای آپدیت:",
    "client_reset_ask":   "🔄 ایمیل کلاینت:",
    "client_reset_ok":    "✅ ترافیک ریست شد.",
    "client_reset_all_confirm": "⚠️ ریست ترافیک همه کلاینت‌ها؟",
    "client_reset_all_ok":      "✅ همه ریست شدند.",
    "client_del_depleted_ok":   "✅ کلاینت‌های منقضی حذف شدند.",
    "client_clearips_ask":      "🚫 ایمیل کلاینت:",
    "client_clearips_ok":       "✅ IP‌های `{email}` پاک شد.",
    "client_links_ask":         "🔗 ایمیل کلاینت:",
    "client_links_title":       "🔗 *لینک‌های {email}:*",
    "client_links_empty":       "❌ لینکی یافت نشد.",
    "client_del_ask":           "🗑 ایمیل کلاینت برای حذف:",
    "no_online":          "😴 هیچ کلاینتی آنلاین نیست.",
    "online_title":       "🌐 *آنلاین‌ها* ({count})",
    "last_online_title":  "⏰ *آخرین آنلاین:*",
    "btn_cl_list":        "📋 لیست همه کلاینت‌ها",
    "btn_cl_search":      "🔍 جستجو با ایمیل",
    "btn_cl_add":         "➕ افزودن کلاینت",
    "btn_cl_update":      "✏️ آپدیت کلاینت",
    "btn_cl_del":         "🗑 حذف کلاینت",
    "btn_cl_reset":       "🔄 ریست ترافیک",
    "btn_cl_reset_all":   "♻️ ریست همه",
    "btn_cl_del_dep":     "🧹 حذف منقضی‌ها",
    "btn_cl_clear_ips":   "🚫 پاک IP ها",
    "btn_cl_links":       "🔗 لینک‌های اتصال",
    "btn_cl_last_online": "⏰ آخرین آنلاین",
    "btn_cl_bulk_adj":    "📦 Bulk Adjust",
    "btn_cl_bulk_del":    "🗑 Bulk Delete",
    "btn_cl_groups":      "👥 مدیریت گروه‌ها",

    # ── ترافیک کلاینت ────────────────────────────────────────────
    "traffic_title":      "📊 *{email}*",
    "traffic_enabled":    "✅ فعال",
    "traffic_disabled":   "❌ غیرفعال",
    "traffic_up":         "↑`{val}`",
    "traffic_down":       "↓`{val}`",
    "traffic_total":      "کل: `{val}`",
    "traffic_unlimited":  "♾️ نامحدود",
    "traffic_expiry":     "انقضا: `{date}` ({left})",

    # ── Bulk ──────────────────────────────────────────────────────
    "bulk_adj_ask":       "📦 *Bulk Adjust*\n\nفرمت:\n`email1,email2\nروز:30\nGB:50`",
    "bulk_adj_ok":        "✅ {count} کلاینت آپدیت شد.",
    "bulk_del_ask":       "🗑 ایمیل‌ها را با کاما وارد کنید:",
    "bulk_del_ok":        "✅ {count} کلاینت حذف شد.",
    "bulk_bad_format":    "❌ فرمت نادرست.",

    # ── گروه‌ها ───────────────────────────────────────────────────
    "groups_title":       "👥 *گروه‌ها:*",
    "groups_empty":       "📭 گروهی وجود ندارد.",
    "group_member_count": "• `{name}` — {count} نفر",
    "group_create_ask":   "نام گروه جدید:",
    "group_create_ok":    "✅ گروه «{name}» ساخته شد.",
    "group_rename_ask_old": "نام فعلی گروه:",
    "group_rename_ask_new": "نام جدید گروه:",
    "group_rename_ok":    "✅ تغییر نام داده شد.",
    "group_delete_ask":   "نام گروه برای حذف:",
    "group_delete_ok":    "✅ گروه حذف شد.",
    "btn_grp_create":     "➕ گروه جدید",
    "btn_grp_rename":     "✏️ تغییر نام",
    "btn_grp_delete":     "🗑 حذف گروه",

    # ── Xray / سرور ──────────────────────────────────────────────
    "xray_menu_title":    "🔧 *Xray / سرور*",
    "xray_log_title":     "📜 *لاگ Xray (۵۰ خط)*",
    "panel_log_title":    "📜 *لاگ پنل (۵۰ خط)*",
    "xray_restart_ok":    "✅ Xray ری‌استارت شد.",
    "xray_stop_confirm":  "⚠️ توقف Xray؟ تمام اتصال‌ها قطع می‌شوند!",
    "xray_stop_ok":       "✅ Xray متوقف شد.",
    "panel_restart_ok":   "✅ پنل ری‌استارت شد.",
    "panel_update_confirm": "⚠️ آپدیت پنل؟ پنل بعد از آپدیت ری‌استارت می‌شود.",
    "panel_update_ok":    "✅ آپدیت شد. پنل ری‌استارت می‌شود.",
    "geo_update_ok":      "✅ GeoFile آپدیت شد.",
    "xray_versions_title": "📦 *نسخه‌های Xray:*",
    "xray_install_ask":   "نسخه Xray (مثال: v24.9.16 یا latest):",
    "xray_install_ok":    "✅ Xray نسخه {ver} نصب شد!",
    "xray_install_loading": "⏳ در حال نصب Xray {ver}...",
    "uuid_result":        "🔑 UUID جدید:\n`{uuid}`",
    "x25519_result":      "🔑 *X25519 کیپر جدید:*\n\n🔒 Private:\n`{priv}`\n\n🔓 Public:\n`{pub}`",
    "config_title":       "⚡ *Xray Config:*",
    "obs_title":          "🔭 *Observatory:*",
    "metrics_title":      "📊 *Xray Metrics:*",
    "outbound_title":     "📊 *Outbound Traffic:*",
    "outbound_empty":     "📭 داده‌ای نیست.",
    "outbound_reset_ok":  "✅ ترافیک Outbound ریست شد.",
    "db_ok":              "✅ DB دریافت شد.",
    "btn_xray_install":   "🔄 نصب نسخه",
    "btn_outbound_traffic": "📊 ترافیک Outbound",
    "btn_reset_outbound": "🔄 ریست Outbound",

    # ── تنظیمات ──────────────────────────────────────────────────
    "settings_title":     "⚙️ *تنظیمات*",
    "settings_url":       "🌐 `{url}`",
    "settings_user":      "👤 `{user}`",
    "settings_connected": "🔗 ✅ متصل",
    "settings_disconnected": "🔗 ❌ قطع",
    "settings_card":      "💳 `{number}` {owner}",
    "settings_card_empty":"💳 تنظیم نشده",
    "settings_hints":     "/setup — /setcard — /reconnect",
    "settings_all_title": "⚙️ *تنظیمات پنل:*",
    "btn_settings_all":   "📋 همه تنظیمات",
    "btn_settings_user":  "👤 تغییر یوزر/پسورد",

    # ── API Token ها ──────────────────────────────────────────────
    "tokens_title":       "🔑 *API Token ها*",
    "tokens_empty":       "📭 توکنی وجود ندارد.",
    "token_enabled":      "✅",
    "token_disabled":     "❌",
    "token_create_ask":   "نام توکن جدید:",
    "token_create_ok":    "✅ توکن ساخته شد!\n🔑 `{token}`\n📛 {name}",
    "token_del_ask":      "ID توکن برای حذف:",
    "token_del_ok":       "✅ توکن حذف شد.",
    "token_toggle_ask":   "ID توکن و وضعیت (مثال: `5 true`):",
    "token_toggle_ok":    "✅ وضعیت تغییر کرد.",
    "btn_tok_create":     "➕ توکن جدید",
    "btn_tok_del":        "🗑 حذف توکن",
    "btn_tok_toggle":     "🔛 فعال/غیرفعال",

    # ── نودها ─────────────────────────────────────────────────────
    "nodes_title":        "📡 *نودها* ({count} عدد)",
    "nodes_empty":        "📭 نودی وجود ندارد.",
    "node_add_ask":       "JSON نود جدید را وارد کنید:",
    "node_add_ok":        "✅ نود افزوده شد.",
    "node_test_ask":      "JSON اطلاعات اتصال نود را وارد کنید:",
    "btn_node_add":       "➕ افزودن نود",
    "btn_node_test":      "🔭 تست نود",

    # ── بکاپ ─────────────────────────────────────────────────────
    "backup_title":       "💾 *پشتیبان‌گیری*",
    "backup_tg_loading":  "⏳ در حال ارسال بکاپ به تلگرام...",
    "backup_tg_ok":       "✅ بکاپ به تلگرام ارسال شد.",
    "backup_db_loading":  "⏳ در حال دریافت DB...",
    "btn_backup_tg":      "📨 ارسال DB به تلگرام",
    "btn_backup_db":      "🗄 دانلود DB",

    # ── فروش ─────────────────────────────────────────────────────
    "sales_title":        "🛒 *مدیریت فروش*",
    "plans_title":        "📋 *تعرفه‌ها:*",
    "plans_empty":        "📭 تعرفه‌ای نیست.",
    "plan_item":          "🔹 *{name}* | {days}روز | {gb} | {price}",
    "plan_add_name":      "نام تعرفه جدید:",
    "plan_add_price":     "💰 قیمت به تومان:",
    "plan_add_days":      "📅 تعداد روز:",
    "plan_add_gb":        "📦 حجم GB (0 = نامحدود):",
    "plan_add_ib":        "🔌 اینباند پیش‌فرض این تعرفه را انتخاب کنید:",
    "plan_add_ok":        "✅ تعرفه افزوده شد!\n📦 {name} | {days}روز | {gb}\n💰 {price}",
    "plan_del_ok":        "🗑 تعرفه «{name}» حذف شد.",
    "plan_not_found":     "❌ تعرفه پیدا نشد.",
    "pending_empty":      "✅ رسید در انتظاری وجود ندارد.",
    "pending_title":      "⏳ *در انتظار:*",
    "orders_empty":       "📭 سفارشی ثبت نشده.",
    "orders_title":       "📊 *سفارش‌ها:*",
    "btn_plans":          "📋 تعرفه‌ها ({count})",
    "btn_pending":        "⏳ در انتظار ({count})",
    "btn_all_orders":     "📊 همه سفارش‌ها",
    "btn_add_plan":       "➕ افزودن تعرفه",
    "btn_set_card":       "💳 تنظیم کارت",
    "btn_del_plan":       "🗑 {name}",
    "order_status_pending":  "⏳ در انتظار",
    "order_status_approved": "✅ تأیید شده",
    "order_status_rejected": "❌ رد شده",

    # ── خرید مشتری ───────────────────────────────────────────────
    "buy_title":          "🛒 *خرید / تمدید اشتراک*\n\nتعرفه مورد نظر را انتخاب کنید:",
    "buy_no_plans":       "😔 در حال حاضر تعرفه‌ای فعال نیست.\nبعداً مراجعه کنید.",
    "buy_no_card":        "⚠️ سیستم پرداخت هنوز راه‌اندازی نشده.\nبا ادمین تماس بگیرید.",
    "buy_plan_btn":       "🔹 {name} — {days}روز {gb} — {price}",
    "buy_invoice":        (
        "🧾 *{kind}*\n\n"
        "📦 تعرفه: *{name}*\n"
        "⏱ مدت: {days} روز\n"
        "💾 حجم: {gb}\n"
        "💰 مبلغ: *{price}*\n\n"
        "━━━━━━━━━━━\n"
        "💳 *شماره کارت برای واریز:*\n`{card}`\n"
        "👤 به نام: *{owner}*\n"
        "━━━━━━━━━━━\n\n"
        "📸 پس از واریز، *تصویر رسید* را ارسال کنید. ✅"
    ),
    "buy_kind_new":       "خرید اشتراک جدید",
    "buy_kind_renew":     "تمدید اشتراک",
    "receipt_ask":        "📸 لطفاً تصویر رسید را ارسال کنید.",
    "receipt_cooldown":   "⏳ {sec} ثانیه صبر کنید و سپس رسید ارسال کنید.",
    "receipt_too_many":   "⚠️ شما ۳ سفارش در انتظار تأیید دارید.\nلطفاً منتظر بررسی بمانید.",
    "receipt_ok":         "✅ *رسید شما دریافت شد!*\n\n🔖 `#{oid}`\n📦 {name}\n⏳ در حال بررسی توسط ادمین...",
    "receipt_invalid_plan": "❌ تعرفه انتخابی دیگر معتبر نیست. لطفاً مجدداً خرید کنید.",

    # ── نوتیف ادمین ──────────────────────────────────────────────
    "order_notify_admin": (
        "🔔 *سفارش جدید!*\n\n"
        "🔖 #{oid}\n👤 `{cid}`\n📧 `{email}`\n"
        "📦 {name} — {days}روز — {gb}\n"
        "💰 {price}\n"
        "🕐 {time}"
    ),
    "btn_approve":        "✅ تأیید و فعال‌سازی",
    "btn_reject":         "❌ رد کردن",

    # ── تأیید/رد سفارش ───────────────────────────────────────────
    "order_already_done": "⚠️ این سفارش قبلاً «{status}» شده.",
    "order_no_inbound":   "❌ اینباند تعرفه تنظیم نشده است.",
    "order_no_email":     "❌ ایمیل کاربر ثبت نشده است.",
    "order_processing":   "⏳ در حال پردازش سفارش #{oid}...",
    "order_panel_error":  "❌ خطا در پنل: {msg}",
    "order_approved_admin": "✅ سفارش #{oid} تأیید شد\n{action}",
    "order_rejected_admin": "❌ سفارش #{oid} رد شد.",
    "order_approved_user":  (
        "🎉 *اشتراک شما فعال شد!*\n\n"
        "🔖 `#{oid}`\n📦 {name}\n{action}\n\n"
        "🔗 لینک اشتراک:\n`{sub}`"
    ),
    "order_rejected_user":  "❌ *سفارش شما رد شد*\n\n🔖 #{oid} — {name}\n\nدر صورت سوال با پشتیبانی تماس بگیرید.",
    "action_renewed":     "🔄 تمدید تا {date}",
    "action_new_client":  "✅ کلاینت جدید | {days}روز",
    "order_no_plan":      "❌ تعرفه این سفارش حذف شده است.",
    "order_not_found":    "❌ سفارش یافت نشد.",

    # ── پنل مشتری ────────────────────────────────────────────────
    "user_menu":          "منوی مشتری:",
    "user_welcome":       "✅ خوش آمدید!\nایمیل: `{email}`",
    "user_ask_email":     "👤 *ورود مشتری*\n\nایمیل اشتراک VPN خود را وارد کنید:",
    "user_email_ok":      "✅ *ورود موفق!*\nایمیل `{email}` شناسایی شد.",
    "user_email_not_found": "❌ ایمیل `{email}` در پنل پیدا نشد.\nمی‌توانید اشتراک جدید خریداری کنید:",
    "user_change_email":  "🔄 ایمیل جدید اشتراک خود را وارد کنید:",
    "btn_buy_new":        "🛒 خرید اشتراک",
    "user_status_title":  "📊 *وضعیت اشتراک*",
    "user_status_email":  "📧 `{email}`",
    "user_status_used":   "📦 مصرف: `{val}`",
    "user_status_remain": "باقی: `{val}`",
    "user_status_total":  "کل: `{val}`",
    "user_status_expiry": "📅 `{date}` ({left})",
    "user_conn_uuid":     "🆔 `{uuid}`",
    "user_conn_sub":      "🔗 sub:\n`{link}`",
    "user_conn_title":    "📋 *اطلاعات اتصال*",
    "user_conn_not_found":"❌ کلاینت `{email}` پیدا نشد.",
    "user_links_title":   "🔗 *لینک‌های اتصال:*",
    "user_links_empty":   "❌ لینکی یافت نشد.",
    "user_orders_title":  "📦 *سفارش‌های شما:*",
    "user_orders_empty":  "📭 سفارشی ثبت نشده.",
    "user_server_unavail":"⚠️ سرور در دسترس نیست.",
    "user_no_login":      "❌ ابتدا /start بزنید و ایمیل خود را ثبت کنید.",

    # ── fallbacks ─────────────────────────────────────────────────
    "fallbacks_title":    "🔗 Fallbacks اینباند {iid}:",

    # ── /help ─────────────────────────────────────────────────────
    "help_text": (
        "📖 *ربات 3X-UI — راهنما*\n\n"
        "*دستورات:*\n"
        "/start — انتخاب نقش\n"
        "/setup — تنظیم پنل (فقط ادمین‌های مجاز)\n"
        "/setcard — تنظیم شماره کارت\n"
        "/reconnect — اتصال مجدد\n"
        "/help — راهنما\n\n"
        "*پنل ادمین:* وضعیت سرور، اینباندها، کلاینت‌ها، Xray، تنظیمات، نودها، API Token، فروش\n"
        "*پنل مشتری:* وضعیت، خرید/تمدید، QR کد، لینک‌ها، سفارش‌ها\n\n"
        "🌐 برای تغییر زبان: /language"
    ),

    # ── /language ─────────────────────────────────────────────────
    "language_cmd":       "🌐 *تغییر زبان*\n\nزبان فعال: 🇮🇷 فارسی\nPlease choose your language:",
}
