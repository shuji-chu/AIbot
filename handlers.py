import re, time, random
from config import (QUOTA, BOT_NAME, BOT_USERNAME, ADMIN_IDS, MIN_RECHARGE,
                    COST_DRAW, COST_DRAW4, COST_CHAT, COST_VIDEO, COST_GIF,
                    COST_WEATHER, COST_IP, COST_QR, COST_MD5, COST_TIMESTAMP,
                    COST_SAYING, COST_WALLPAPER, COST_HOTBOARD, COST_EPIC,
                    COST_BILI_LIVE, COST_BILI_USER, COST_QQ_USER, COST_QQ_GROUP,
                    COST_DNS, COST_EXPRESS,
                    COST_ICP, COST_WHOIS, COST_ICP_UNIT, COST_BAIDU_INDEX,
                    COST_BAIDU_WEIGHT, COST_QQ_BLOCK, COST_WX_BLOCK,
                    COST_PHONE, COST_PHONE_TWO, COST_PHONE_THREE,
                    COST_PHONE_STATUS, COST_PHONE_AGE, COST_PHONE_BALANCE,
                    COST_IDCARD_AREA, COST_IDCARD_REAL, COST_BANK_AREA,
                    COST_CAR_5, COST_CAR_INFO, COST_VIN, COST_CAR_INSURANCE,
                    COST_CAR_TRANSFER,
                    COST_COMPANY_NAME, COST_COMPANY_FUZZY, COST_COMPANY_STD,
                    COST_COMPANY_RECORD, COST_SHIXIN, COST_XIANGAO,
                    COST_JUDICIAL, COST_BADRECORD,
                    COST_EXCHANGE, COST_LOTTERY,
                    CUSTOMER_SERVICE, WELCOME_TEXT,
                    ROLE_PRESETS)

from database import (ensure_user, get_user, get_balance, update_balance,
                      add_spent, add_record, get_user_records,
                      create_recharge, get_admins)
from ai_service import (generate_image, generate_image_4, generate_image_edit,
                       generate_video, convert_video_to_gif, generate_text)
from safew_api import (send_message, send_photo, send_long_message,
                       delete_message, get_file_bytes, answer_callback,
                       send_video, send_animation, download_url)
import uapi_service
import apitg_service

NL = chr(10)

# ========== 群发草稿 ==========
PUSH_DRAFT = {}

# 缓存每个用户最后查询的钱包地址
WALLET_CACHE = {}

# ========== 限流检查 ==========
def check_rate(uid, cid, rtype):
    """检查限流。管理员豁免。返回 True 表示通过，False 表示被拦截"""
    if uid in ADMIN_IDS: return True
    import database as _db
    # 画图 30 分钟，视频/GIF 24 小时
    window = {"draw": 1800, "video": 86400, "gif": 86400}.get(rtype, 60)
    remaining = _db.check_rate_limit(uid, rtype, window)
    if remaining > 0:
        m = remaining // 60
        s = remaining % 60
        if m > 0:
            send_message(cid, "⏰ 冷却中，还需等待 " + str(m) + " 分 " + str(s) + " 秒")
        else:
            send_message(cid, "⏰ 冷却中，还需等待 " + str(s) + " 秒")
        return False
    return True

def is_bot(m): return m.get("from", {}).get("is_bot", False)
def uname(m):
    u = m.get("from", {})
    return u.get("username") or u.get("first_name") or "用户"

def is_admin(uid):
    try:
        if int(uid) in ADMIN_IDS: return True
    except: pass
    return str(uid) in get_admins()

def check_balance(cid, uid, un, cost):
    if cost <= 0: return True
    b = get_balance(uid)
    if b < cost:
        send_message(cid, "⚠️ " + un + " 余额不足" + NL +
            "当前：" + ("%.4f" % b) + " USDT" + NL +
            "需要：" + ("%.4f" % cost) + " USDT" + NL + NL +
            "发 /recharge 充值")
        return False
    return True

def check_quota(cid, uid, un, feature, daily_free, cost):
    """
    统一收费检查：
    1. 先看今日免费用了多少
    2. 未用完免费额度 → 通过 + 计数
    3. 用完 → 扣余额
    4. 余额不足 → 拒绝
    返回 True 通过 / False 拦截
    """
    if uid in ADMIN_IDS: return True  # 管理员豁免
    import database as _d
    used = _d.daily_usage(uid, feature)
    if used < daily_free:
        _d.add_daily_usage(uid, feature)
        return True
    # 超额，检查余额
    if cost <= 0:
        return True  # 配置为不收费
    b = get_balance(uid)
    if b < cost:
        send_message(cid, "💰 " + un + " 今日免费额度已用完" + NL + NL +
            "当前余额：" + ("%.4f" % b) + " USDT" + NL +
            "本次需要：" + ("%.4f" % cost) + " USDT" + NL + NL +
            "发 /recharge 充值，或明天再来")
        return False
    # 扣费
    add_spent(uid, cost)
    _d.add_daily_usage(uid, feature)
    send_message(cid, "💰 免费额度已用完，本次扣除 " + ("%.4f" % cost) + " USDT" + NL + "剩余余额：" + ("%.4f" % (b - cost)) + " USDT")
    return True

def main_menu():
    return {"inline_keyboard": [
        [{"text": "🎨 AI创作", "callback_data": "menu_ai"},
         {"text": "🔍 日常查询", "callback_data": "menu_daily"}],
        [{"text": "🌐 域名工具", "callback_data": "menu_domain"},
         {"text": "📱 手机工具", "callback_data": "menu_phone"}],
        [{"text": "🆔 身份工具", "callback_data": "menu_idcard"},
         {"text": "🚗 车辆工具", "callback_data": "menu_car"}],
        [{"text": "🏢 企业工具", "callback_data": "menu_company"},
         {"text": "🎲 趣味工具", "callback_data": "menu_fun"}],
        [{"text": "💰 我的钱包", "callback_data": "menu_wallet"}],
    ]}

def menu_ai():
    return {"inline_keyboard": [
        [{"text": "🎨 绘画（免费）", "callback_data": "ai_draw"},
         {"text": "🎬 视频", "callback_data": "ai_video"}],
        [{"text": "🎞️ GIF", "callback_data": "ai_gif"},
         {"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_daily():
    return {"inline_keyboard": [
        [{"text": "🌤 天气", "callback_data": "q_weather"},
         {"text": "🌐 IP", "callback_data": "q_ip"}],
        [{"text": "📦 快递", "callback_data": "q_express"},
         {"text": "🔥 热榜", "callback_data": "q_hotboard"}],
        [{"text": "💬 一言", "callback_data": "q_saying"},
         {"text": "🖼 壁纸", "callback_data": "q_wallpaper"}],
        [{"text": "🎮 Epic", "callback_data": "q_epic"},
         {"text": "📷 二维码", "callback_data": "q_qr"}],
        [{"text": "📺 B站", "callback_data": "q_bili"},
         {"text": "📺 B站直播", "callback_data": "q_bililive"}],
        [{"text": "👤 QQ", "callback_data": "q_qq"},
         {"text": "👥 QQ群", "callback_data": "q_qqgroup"}],
        [{"text": "🌐 DNS", "callback_data": "q_dns"},
         {"text": "🔐 MD5", "callback_data": "q_md5"}],
        [{"text": "⏰ 时间戳", "callback_data": "q_timestamp"},
         {"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_domain():
    return {"inline_keyboard": [
        [{"text": "📋 ICP备案", "callback_data": "d_icp"},
         {"text": "🌐 WHOIS", "callback_data": "d_whois"}],
        [{"text": "🏢 主办单位", "callback_data": "d_icpunit"},
         {"text": "📌 TDK", "callback_data": "d_tdk"}],
        [{"text": "📊 百度收录", "callback_data": "d_baiduindex"},
         {"text": "📊 百度权重", "callback_data": "d_baiduweight"}],
        [{"text": "🛡 QQ拦截", "callback_data": "d_qqblock"},
         {"text": "🛡 微信拦截", "callback_data": "d_wxblock"}],
        [{"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_phone():
    return {"inline_keyboard": [
        [{"text": "📱 归属地", "callback_data": "m_phone"},
         {"text": "✅ 二要素", "callback_data": "m_two"}],
        [{"text": "✅ 三要素", "callback_data": "m_three"},
         {"text": "📡 在网状态", "callback_data": "m_status"}],
        [{"text": "⏱ 使用时长", "callback_data": "m_age"},
         {"text": "💰 话费余额", "callback_data": "m_balance"}],
        [{"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_idcard():
    return {"inline_keyboard": [
        [{"text": "🆔 归属地", "callback_data": "i_area"},
         {"text": "✅ 实名检验", "callback_data": "i_real"}],
        [{"text": "💳 银行卡", "callback_data": "i_bank"},
         {"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_car():
    return {"inline_keyboard": [
        [{"text": "🚗 车牌五项", "callback_data": "c_5"},
         {"text": "🚗 车牌解析", "callback_data": "c_plate"}],
        [{"text": "🔢 VIN解析", "callback_data": "c_vin"},
         {"text": "📋 上险信息", "callback_data": "c_insurance"}],
        [{"text": "🔄 过户次数", "callback_data": "c_transfer"},
         {"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_company():
    return {"inline_keyboard": [
        [{"text": "🏢 名称查询", "callback_data": "b_name"},
         {"text": "🏢 工商模糊", "callback_data": "b_fuzzy"}],
        [{"text": "🏢 工商标准", "callback_data": "b_std"},
         {"text": "👤 任职记录", "callback_data": "b_record"}],
        [{"text": "🚨 失信", "callback_data": "b_shixin"},
         {"text": "🚫 限高", "callback_data": "b_xiangao"}],
        [{"text": "⚖️ 司法", "callback_data": "b_judicial"},
         {"text": "📋 不良记录", "callback_data": "b_badrecord"}],
        [{"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_fun():
    return {"inline_keyboard": [
        [{"text": "💱 汇率", "callback_data": "f_exchange"},
         {"text": "🎰 彩票", "callback_data": "f_lottery"}],
        [{"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def menu_wallet():
    return {"inline_keyboard": [
        [{"text": "📊 余额", "callback_data": "w_balance"},
         {"text": "💳 充值", "callback_data": "w_recharge"}],
        [{"text": "📜 记录", "callback_data": "w_records"},
         {"text": "← 返回", "callback_data": "menu_home"}],
    ]}

def recharge_menu():
    return {"inline_keyboard": [
        [{"text": "💵 1 USDT", "callback_data": "rc_1"},
         {"text": "💵 5 USDT", "callback_data": "rc_5"}],
        [{"text": "💵 10 USDT", "callback_data": "rc_10"},
         {"text": "💵 20 USDT", "callback_data": "rc_20"}],
        [{"text": "✏️ 自定义", "callback_data": "rc_custom"}],
    ]}

def welcome_text(uid, un):
    u = get_user(uid)
    b = u["balance"] if u else 0
    return WELCOME_TEXT.format(username=un, uid=uid, balance=("%.4f" % b))

def handle_callback(cq):
    from admin import handle_admin_callback
    if handle_admin_callback(cq): return
    cid = cq.get("message", {}).get("chat", {}).get("id")
    uid = cq.get("from", {}).get("id")
    un = cq.get("from", {}).get("username") or cq.get("from", {}).get("first_name") or "用户"
    data = cq.get("data", "")
    mid = cq.get("message", {}).get("message_id")
    try: answer_callback(cq.get("id"))
    except: pass
    ensure_user(uid, un)

    if data == "wallet_usdt":
        addr = WALLET_CACHE.get(str(uid), "")
        if not addr:
            send_message(cid, "❌ 请先发 /wallet 地址"); return
        import tron_service as _ts
        try:
            r = _ts.get_usdt_history(addr, 10)
            markup = {"inline_keyboard": [
                [{"text": "💎 查询TRX历史", "callback_data": "wallet_trx"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            send_message(cid, "❌ " + str(e)[:100])
        return
    if data == "wallet_trx":
        addr = WALLET_CACHE.get(str(uid), "")
        if not addr:
            send_message(cid, "❌ 请先发 /wallet 地址"); return
        import tron_service as _ts
        try:
            r = _ts.get_trx_history(addr, 10)
            markup = {"inline_keyboard": [
                [{"text": "📜 查询USDT历史", "callback_data": "wallet_usdt"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            send_message(cid, "❌ " + str(e)[:100])
        return
    if data == "wallet_refresh":
        addr = WALLET_CACHE.get(str(uid), "")
        if not addr:
            send_message(cid, "❌ 请先发 /wallet 地址"); return
        import tron_service as _ts
        try:
            r = _ts.get_wallet_info(addr)
            markup = {"inline_keyboard": [
                [{"text": "📜 查询USDT历史", "callback_data": "wallet_usdt"},
                 {"text": "💎 查询TRX历史", "callback_data": "wallet_trx"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            send_message(cid, "❌ " + str(e)[:100])
        return
    if data == "menu_home":
        delete_message(cid, mid)
        send_message(cid, welcome_text(uid, un), custom_markup=main_menu()); return
    if data == "menu_ai":
        delete_message(cid, mid); send_message(cid, "🎨 AI创作", custom_markup=menu_ai()); return
    if data == "menu_daily":
        delete_message(cid, mid); send_message(cid, "🔍 日常查询", custom_markup=menu_daily()); return
    if data == "menu_domain":
        delete_message(cid, mid); send_message(cid, "🌐 域名工具", custom_markup=menu_domain()); return
    if data == "menu_phone":
        delete_message(cid, mid); send_message(cid, "📱 手机工具", custom_markup=menu_phone()); return
    if data == "menu_idcard":
        delete_message(cid, mid); send_message(cid, "🆔 身份工具", custom_markup=menu_idcard()); return
    if data == "menu_car":
        delete_message(cid, mid); send_message(cid, "🚗 车辆工具", custom_markup=menu_car()); return
    if data == "menu_company":
        delete_message(cid, mid); send_message(cid, "🏢 企业工具", custom_markup=menu_company()); return
    if data == "menu_fun":
        delete_message(cid, mid); send_message(cid, "🎲 趣味工具", custom_markup=menu_fun()); return
    if data == "menu_wallet":
        delete_message(cid, mid); send_message(cid, "💰 我的钱包", custom_markup=menu_wallet()); return

    if data == "ai_draw":
        delete_message(cid, mid); send_message(cid, "🎨 格式：/draw 描述"); return
    if data == "ai_video":
        delete_message(cid, mid); send_message(cid, "🎬 格式：/video 描述"); return
    if data == "ai_gif":
        delete_message(cid, mid); send_message(cid, "🎞️ 格式：/gif 描述"); return

    guides = {
        "q_weather": "格式：/weather 城市",
        "q_ip": "格式：/ip IP或域名",
        "q_express": "格式：/express 快递单号",
        "q_hotboard": "格式：/hotboard 平台",
        "q_saying": "格式：/saying",
        "q_wallpaper": "格式：/wallpaper",
        "q_epic": "格式：/epic",
        "q_qr": "格式：/qr 文本或链接",
        "q_bili": "格式：/bili UID",
        "q_bililive": "格式：/bili_live 房间号",
        "q_qq": "格式：/qq QQ号",
        "q_qqgroup": "格式：/qqgroup 群号",
        "q_dns": "格式：/dns 域名",
        "q_md5": "格式：/md5 文本",
        "q_timestamp": "格式：/timestamp",
        "d_icp": "格式：/icp 域名",
        "d_whois": "格式：/whois 域名",
        "d_icpunit": "格式：/icpunit 单位名",
        "d_tdk": "格式：/tdk URL",
        "d_baiduindex": "格式：/baiduindex 域名",
        "d_baiduweight": "格式：/baiduweight 域名",
        "d_qqblock": "格式：/qqblock URL",
        "d_wxblock": "格式：/wxblock URL",
        "m_phone": "格式：/phone 手机号",
        "m_two": "格式：/phone_two 姓名 手机号",
        "m_three": "格式：/phone_three 姓名 手机号 身份证号",
        "m_status": "格式：/phone_status 手机号",
        "m_age": "格式：/phone_age 手机号",
        "m_balance": "格式：/phone_balance 手机号",
        "i_area": "格式：/idcardarea 身份证号",
        "i_real": "格式：/idcardreal 姓名 身份证号",
        "i_bank": "格式：/bankarea 银行卡号",
        "c_5": "格式：/car5 车牌号",
        "c_plate": "格式：/carplate 车牌号",
        "c_vin": "格式：/vin VIN码",
        "c_insurance": "格式：/carinsurance 身份证号",
        "c_transfer": "格式：/cartransfer 身份证号",
        "b_name": "格式：/companyname 关键词",
        "b_fuzzy": "格式：/companyfuzzy 关键词",
        "b_std": "格式：/companystd 公司名",
        "b_record": "格式：/companyrecord 身份证号 [姓名]",
        "b_shixin": "格式：/shixin 姓名 [身份证号]",
        "b_xiangao": "格式：/xiangao 姓名 [身份证号]",
        "b_judicial": "格式：/judicial 姓名 身份证号",
        "b_badrecord": "格式：/badrecord 姓名 身份证号",
        "f_exchange": "格式：/exchange 金额 币种",
        "f_lottery": "格式：/lottery 类型",
    }
    if data in guides:
        delete_message(cid, mid); send_message(cid, guides[data]); return

    if data == "w_balance":
        u = get_user(uid); delete_message(cid, mid)
        send_message(cid, "💰 余额：" + ("%.4f" % u["balance"]) + " USDT"); return
    if data == "w_recharge":
        delete_message(cid, mid)
        send_message(cid, "💳 充值 USDT" + NL + "最低：" + str(MIN_RECHARGE) + " USDT" + NL + "网络：TRC20" + NL + "请选择：", custom_markup=recharge_menu()); return
    if data == "w_records":
        recs = get_user_records(uid, 10); delete_message(cid, mid)
        if not recs: send_message(cid, "📜 暂无记录"); return
        lines = ["📜 最近记录", "━━━━━━━━━━━━"]
        for r in recs: lines.append(str(r[0]) + " · " + str(r[1])[:30] + " · -" + str(r[2]) + " USDT · " + str(r[3]))
        send_message(cid, NL.join(lines)); return
    if data.startswith("rc_"):
        amount = data.replace("rc_", "")
        if amount == "custom":
            delete_message(cid, mid); send_message(cid, "✏️ 请发送 /recharge 金额"); return
        try:
            amt = float(amount); delete_message(cid, mid); _recharge(cid, uid, amt)
        except: send_message(cid, "❌ 金额格式错误")
        return

def _recharge(cid, uid, amount):
    if amount < MIN_RECHARGE:
        send_message(cid, "❌ 最低充值 " + str(MIN_RECHARGE) + " USDT"); return
    rand = random.randint(1, 9999) / 10000.0
    ua = round(amount + rand, 4)
    on = "R" + str(int(time.time())) + str(random.randint(100, 999))
    create_recharge(on, uid, ua)
    msg = ("💳 充值订单已创建" + NL + "━━━━━━━━━━━━" + NL +
        "订单编号　" + on + NL +
        "请转账　　" + ("%.4f" % ua) + " USDT" + NL +
        "网络　　　TRC20" + NL + NL +
        "收款地址" + NL + "TTT5MV8xeZqKaPDxUcDjR8bPFz2ce5kmBr" + NL + NL +
        "⚠️ 必须精确转账（含尾数）" + NL + "到账后自动通知你" + NL + NL +
        "微信/支付宝请联系人工客服 " + CUSTOMER_SERVICE)
    send_message(cid, msg)

def _run(cid, uid, un, cost, t, q, f):
    if not check_balance(cid, uid, un, cost): return True
    if cost > 0: add_spent(uid, cost)
    nid = send_message(cid, "🔍 查询中...")
    try: result = f()
    except Exception as e:
        delete_message(cid, nid)
        if cost > 0: update_balance(uid, cost)
        send_message(cid, "❌ 查询异常：" + str(e)[:80]); return True
    delete_message(cid, nid)
    send_long_message(cid, str(result))
    add_record(uid, t, q[:50], cost); return True

def _draw(cid, uid, un, prompt, size, mid=None, group=False):
    if not prompt: send_message(cid, "🎨 格式：/draw 描述"); return
    nid = send_message(cid, "🎨 " + un + " 正在绘制..." + NL + "提示：" + prompt)
    img = generate_image(prompt, size=size)
    delete_message(cid, nid)
    if img:
        send_photo(cid, img, caption="🎨 " + un + " 的作品" + NL + prompt[:100], reply_to_msg_id=mid if group else None)
        add_record(uid, "draw", prompt[:50], 0)
    else:
        send_message(cid, "❌ 绘画失败")

def handle_message(m):
    cid = m.get("chat", {}).get("id")
    uid = m.get("from", {}).get("id")
    un = uname(m)
    txt = (m.get("text") or "").strip()

    # ========== 多行命令：如果用户一次发多条命令，只处理第一行 ==========
    if "\n" in txt:
        _first_line = txt.split("\n")[0].strip()
        if _first_line.startswith("/"):
            txt = _first_line

    # ========== AI 命令无参数自动补默认值 ==========
    AUTO_DEFAULTS = {
        "/draw": " 一只可爱的猫，高清插画，温暖色调",
        "/draw_h": " 壮丽的山水风景，电影感横构图",
        "/draw_v": " 赛博朋克城市夜景，竖构图",
        "/agimg": " 梦幻的场景，艺术风格",
        "/video": " 云朵在蓝天缓缓飘动，电影感",
        "/agvideo": " 一个温暖治愈的小故事",
        "/tts": " 你好，我是全能AI助手",
        "/poem": " 春暖花开",
        "/name": " 女孩",
        "/fortune": " 今天",
        "/dream": " 我梦见自己变成了一条鱼",
        "/story": " 一个温暖治愈的故事",
        "/write": " 生活中的小确幸",
        "/script": " 介绍一款好用的产品",
        "/roast": " 我自己",
        "/tarot": " 我最近的运势",
        "/horoscope": " 今天",
        "/meme": " 今天也是努力的一天",
        "/riddle": "",
        "/love": "",
        "/saying": "",
    }
    if txt in AUTO_DEFAULTS:
        txt = txt + AUTO_DEFAULTS[txt]
    # 也处理 /horoscope 无星座时给随机
    if txt == "/horoscope":
        import random as _rd
        txt = "/horoscope " + _rd.choice(["白羊座","金牛座","双子座","巨蟹座","狮子座","处女座","天秤座","天蝎座","射手座","摩羯座","水瓶座","双鱼座"])
    ph = m.get("photo")
    mid = m.get("message_id")
    if not cid or not uid or is_bot(m): return
    ensure_user(uid, un)
    group = cid < 0

    # ========== 群聊里，非命令消息必须 @ 机器人 ==========
    if group:
        is_cmd = txt.startswith("/")
        if not is_cmd:
            mention_ok = False
            for _n in ["@" + BOT_USERNAME, "@" + BOT_NAME]:
                if _n in txt:
                    mention_ok = True
                    txt = txt.replace(_n, "").strip()
                    break
            if not mention_ok:
                return
            if not txt:
                return

    if ph:
        ib = get_file_bytes(ph[-1]["file_id"])
        if not ib:
            send_message(cid, "❌ 图片下载失败"); return
        import ai_service as _ai2
        if txt.startswith("/img2video"):
            prompt = txt.replace("/img2video", "", 1).strip()
            nid = send_message(cid, "🎬 图生视频中，约1-2分钟...")
            video_url, err = _ai2.generate_video_from_image(ib, prompt)
            delete_message(cid, nid)
            if video_url:
                import requests as _rq
                nid2 = send_message(cid, "📥 下载视频中...")
                try:
                    vb = _rq.get(video_url, timeout=120).content
                    delete_message(cid, nid2)
                    send_video(cid, vb, caption="🎬 " + BOT_NAME)
                except Exception as e:
                    delete_message(cid, nid2)
                    send_message(cid, "❌ 下载失败：" + str(e)[:80])
            else:
                send_message(cid, "❌ " + str(err))
            return
        if txt.startswith("/style"):
            style = txt.replace("/style", "", 1).strip() or "动漫"
            nid = send_message(cid, "🎨 " + style + "风格转换中...")
            res = _ai2.style_transfer(ib, style)
            delete_message(cid, nid)
            if res: send_photo(cid, res, caption="🎨 " + style + "风格 · " + BOT_NAME)
            else: send_message(cid, "❌ 转换失败")
            return
        if txt.startswith("/draw"):
            if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
            prompt = txt.replace("/draw", "", 1).strip()
            if not prompt:
                send_message(cid, "🖼️ " + un + "，请附上描述"); return
            nid = send_message(cid, "🖼️ 正在修改图片...")
            res = generate_image_edit(prompt, ib)
            delete_message(cid, nid)
            if res: send_photo(cid, res, caption="🖼️ " + prompt[:80])
            else: send_message(cid, "❌ 修改失败")
            return
        nid = send_message(cid, "🔍 智能识别中...")
        q = txt.replace("/scan", "", 1).strip() if txt.startswith("/scan") else (txt or "")
        reply = _ai2.recognize_image(ib, q)
        delete_message(cid, nid)
        send_long_message(cid, "📷 " + reply)
        return

    if not txt: return

    if txt.startswith("/start"):
        send_message(cid, welcome_text(uid, un), custom_markup=main_menu()); return
    if txt.startswith("/balance"):
        u = get_user(uid); send_message(cid, "💰 余额：" + ("%.4f" % u["balance"]) + " USDT"); return
    if txt.startswith("/recharge"):
        p = txt.split()
        if len(p) < 2:
            send_message(cid, "💳 充值 USDT" + NL + "格式：/recharge 金额", custom_markup=recharge_menu()); return
        try: _recharge(cid, uid, float(p[1]))
        except: send_message(cid, "❌ 金额格式错误")
        return
    if txt.startswith("/draw_h"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        if not check_rate(uid, cid, "draw"): return
        _draw(cid, uid, un, txt.replace("/draw_h", "", 1).strip(), "1792x1024", mid, group); return
    if txt.startswith("/draw_v"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        if not check_rate(uid, cid, "draw"): return
        _draw(cid, uid, un, txt.replace("/draw_v", "", 1).strip(), "1024x1792", mid, group); return
    if txt.startswith("/draw"):
        if not check_rate(uid, cid, "draw"): return
        _draw(cid, uid, un, txt.replace("/draw", "", 1).strip(), "1024x1024", mid, group); return
    if txt.startswith("/video"):
        if not check_quota(cid, uid, un, "video", QUOTA["video"][0], QUOTA["video"][1]): return
        if not check_rate(uid, cid, "video"): return
        prompt = txt.replace("/video", "", 1).strip()
        if not prompt: send_message(cid, "🎬 格式：/video 描述"); return
        nid = send_message(cid, "🎬 正在生成视频...")
        vurl = generate_video(prompt)
        delete_message(cid, nid)
        if vurl:
            nid2 = send_message(cid, "🎬 发送中...")
            vb = download_url(vurl); delete_message(cid, nid2)
            if vb: send_video(cid, vb, caption="🎬 " + prompt[:80])
            else: send_message(cid, "❌ 下载失败")
        else: send_message(cid, "❌ 视频失败")
        return
    if txt.startswith("/gif"):
        if not check_quota(cid, uid, un, "video", QUOTA["video"][0], QUOTA["video"][1]): return
        if not check_rate(uid, cid, "gif"): return
        prompt = txt.replace("/gif", "", 1).strip()
        if not prompt: send_message(cid, "🎞️ 格式：/gif 描述"); return
        nid = send_message(cid, "🎞️ 生成中...")
        vurl = generate_video(prompt)
        delete_message(cid, nid)
        if vurl:
            nid2 = send_message(cid, "🎞️ 转换中...")
            vb = download_url(vurl)
            g = convert_video_to_gif(vb) if vb else None
            delete_message(cid, nid2)
            if g: send_animation(cid, g, caption="🎞️ " + prompt[:80])
            else: send_message(cid, "❌ GIF失败")
        else: send_message(cid, "❌ 视频失败")
        return
    if txt.startswith("/admin"):
        from admin import handle_admin
        handle_admin(m, txt); return

    # 查询命令
    if txt.startswith("/weather"):
        c = txt.replace("/weather", "", 1).strip()
        if not c: send_message(cid, "☁️ 格式：/weather 城市"); return
        return _run(cid, uid, un, COST_WEATHER, "weather", c, lambda: uapi_service.query_weather(c))
    if txt.startswith("/ip"):
        c = txt.replace("/ip", "", 1).strip()
        if not c: send_message(cid, "🌐 格式：/ip IP"); return
        return _run(cid, uid, un, COST_IP, "ip", c, lambda: uapi_service.query_ip(c))
    if txt.startswith("/qr"):
        c = txt.replace("/qr", "", 1).strip()
        if not c: send_message(cid, "📷 格式：/qr 文本"); return
        return _run(cid, uid, un, COST_QR, "qr", c[:30], lambda: "已生成" if uapi_service.generate_qrcode(c) else "失败")
    if txt.startswith("/md5"):
        c = txt.replace("/md5", "", 1).strip()
        if not c: send_message(cid, "🔐 格式：/md5 文本"); return
        return _run(cid, uid, un, COST_MD5, "md5", c[:30], lambda: uapi_service.query_md5(c))
    if txt.startswith("/timestamp"):
        return _run(cid, uid, un, COST_TIMESTAMP, "ts", "", lambda: uapi_service.query_timestamp())
    if txt.startswith("/saying"):
        return _run(cid, uid, un, COST_SAYING, "saying", "", lambda: uapi_service.query_saying())
    if txt.startswith("/agvideo"):
        if not check_quota(cid, uid, un, "video", QUOTA["video"][0], QUOTA["video"][1]): return
        if not check_rate(uid, cid, "video"): return
        import ai_service, requests
        c = txt.replace("/agvideo", "", 1).strip()
        if not c: send_message(cid, "🎬 格式：/agvideo 视频描述"); return
        nid = send_message(cid, "🎬 视频生成中，约1-2分钟...")
        video_url = ai_service.generate_video(c)
        delete_message(cid, nid)
        if video_url:
            nid2 = send_message(cid, "📥 正在下载视频...")
            try:
                vb = requests.get(video_url, timeout=120).content
                delete_message(cid, nid2)
                send_video(cid, vb, caption="🎬 " + BOT_NAME)
            except Exception as e:
                delete_message(cid, nid2)
                send_message(cid, "❌ 下载失败：" + str(e)[:100] + "\n链接：" + video_url)
        else:
            send_message(cid, "❌ 生成失败，请稍后重试")
        return

    if txt.startswith("/gtext"):
        import ai_service
        c = txt.replace("/gtext", "", 1).strip()
        if not c: send_message(cid, "📝 格式：/gtext 你的问题"); return
        send_message(cid, ai_service.generate_text_zhipu(c))
        return

    if txt.startswith("/cftext"):
        import ai_service
        c = txt.replace("/cftext", "", 1).strip()
        if not c: send_message(cid, "📝 格式：/cftext 你的问题"); return
        send_message(cid, ai_service.generate_text_cf(c))
        return

    if txt.startswith("/agimg"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        if not check_rate(uid, cid, "draw"): return
        import ai_service
        c = txt.replace("/agimg", "", 1).strip()
        if not c: send_message(cid, "🎨 格式：/agimg 图片描述"); return
        nid = send_message(cid, "🎨 Agnes 绘图中...")
        img = ai_service.generate_image_agnes(c)
        delete_message(cid, nid)
        if img:
            send_photo(cid, img, caption="🎨 " + BOT_NAME)
        else:
            send_message(cid, "❌ 绘图失败")
        return

    if txt.startswith("/tts"):
        if not check_quota(cid, uid, un, "tts", QUOTA["tts"][0], QUOTA["tts"][1]): return
        import ai_service
        from safew_api import send_voice
        c = txt.replace("/tts", "", 1).strip()
        if not c: send_message(cid, "🎙 格式：/tts 要转语音的文字"); return
        nid = send_message(cid, "🎙 语音合成中...")
        audio = ai_service.text_to_speech(c)
        delete_message(cid, nid)
        if audio:
            send_voice(cid, audio)
        else:
            send_message(cid, "❌ 语音合成失败")
        return

    if txt.startswith("/role"):
        import json, os, re as _re
        c = txt.replace("/role", "", 1)
        c = _re.sub(r'[\s\u3000]+', '', c)
        print("ROLE_DEBUG c=" + repr(c))
        role_file = "/root/AIbot/user_roles.json"
        roles_db = {}
        if os.path.exists(role_file):
            try:
                with open(role_file, "r", encoding="utf-8") as f:
                    roles_db = json.load(f)
            except: roles_db = {}
        if not c:
            lines = ["🎭 角色列表："]
            for k, (name, _) in ROLE_PRESETS.items():
                cur = " ✅" if roles_db.get(str(uid)) == k else ""
                lines.append(k + ". " + name + cur)
            lines.append("")
            lines.append("格式：/role 编号    （如 /role 1）")
            lines.append("发送 /role 0 恢复普通模式")
            send_message(cid, chr(10).join(lines)); return
        if c == "0":
            roles_db.pop(str(uid), None)
            with open(role_file, "w", encoding="utf-8") as f:
                json.dump(roles_db, f, ensure_ascii=False)
            send_message(cid, "✅ 已恢复普通模式"); return
        if c in ROLE_PRESETS:
            roles_db[str(uid)] = c
            with open(role_file, "w", encoding="utf-8") as f:
                json.dump(roles_db, f, ensure_ascii=False)
            send_message(cid, "✅ 已切换到角色：" + ROLE_PRESETS[c][0] + chr(10) + "现在开始和我说说话吧～")
        else:
            send_message(cid, "❌ 没有这个角色编号，发 /role 查看列表")
        return

    if txt.startswith("/voice"):
        import json, os
        c = txt.replace("/voice", "", 1).strip().lower()
        vf = "/root/AIbot/user_voice_mode.json"
        vm = {}
        if os.path.exists(vf):
            try:
                with open(vf, "r", encoding="utf-8") as f:
                    vm = json.load(f)
            except: vm = {}
        if c in ("on", "1", "开", "开启"):
            vm[str(uid)] = True
            with open(vf, "w", encoding="utf-8") as f:
                json.dump(vm, f, ensure_ascii=False)
            send_message(cid, "🔊 语音模式已开启" + chr(10) + "现在起我会用语音回复你")
        elif c in ("off", "0", "关", "关闭"):
            vm.pop(str(uid), None)
            with open(vf, "w", encoding="utf-8") as f:
                json.dump(vm, f, ensure_ascii=False)
            send_message(cid, "🔇 语音模式已关闭" + chr(10) + "恢复文字回复")
        else:
            cur = "开启" if vm.get(str(uid)) else "关闭"
            send_message(cid, "🎙 当前语音模式：" + cur + chr(10) + "用法：" + chr(10) + "/voice on 开启" + chr(10) + "/voice off 关闭")
        return

    if txt.startswith("/help") or txt.startswith("/menu"):
        help_text = """🤖 SAFW AI 功能菜单

🎨 AI 创作
 /draw /draw_h /draw_v — 绘画
 /agimg — Agnes绘画
 /video /agvideo — AI视频
 /poster /logo /product — 海报/LOGO/商品图
 /pixel — 像素画
 /tts — 语音合成
 /read — 多语言朗读
 /voice — 语音模式开关

💬 智能对话
 直接发消息即可，自动记忆+联网

🎭 角色扮演
 /role — 8种角色切换

📷 拍照识别
 发图片 → 自动识别文字/名片/菜单
 /scan — 智能识别
 /style 风格 — 风格转换（动漫/油画等）

✍️ AI 写作
 /sum — 文章总结
 /polish — 文字润色
 /write — 文案生成
 /script — 短视频脚本
 /title — 爆款标题
 /email — 邮件
 /resume — 简历优化
 /ppt — PPT大纲

📚 AI 学习
 /word — 每日单词
 /grammar — 语法纠错
 /essay — 英语作文
 /quiz — 出题练习
 /math — 数学解题

🔮 趣味娱乐
 /tarot — 塔罗牌
 /horoscope — 星座运势
 /fortune — 算命
 /dream — 解梦
 /love — 情话
 /poem — 藏头诗
 /meme — 表情包
 /story — 讲故事
 /riddle — 脑筋急转弯
 /couple — 姓名配对

💼 职场工具
 /interview — 面试题
 /mindmap — 思维导图
 /contract — 合同审查

🏠 生活助手
 /recipe — 菜谱
 /travel — 旅游攻略
 /diet — 饮食计划
 /workout — 健身动作
 /shopping — 购物推荐

🎨 创意文案
 /slogan — 广告语
 /brand — 品牌起名
 /tagline — 一句话签名
 /hashtag — 爆款标签
 /bio — 个人简介

💻 开发工具
 /explain — 代码解释
 /regex — 正则生成
 /sql — SQL生成
 /translate — 翻译

🔍 日常查询
 /weather — 天气
 /hotboard — 热搜
 /wallpaper — 壁纸
 /ip — IP归属
 /exchange — 汇率
 /qr — 二维码
 /saying — 每日一句
 /md5 — MD5
 /dns — DNS解析

🌐 域名工具
 /icp — ICP备案
 /whois — WHOIS
 /tdk — 网站TDK
 /baiduindex — 百度收录
 /baiduweight — 百度权重

📱 身份工具
 /phone — 手机归属
 /idcardarea — 身份证归属
 /bankarea — 银行卡归属

🚗 车辆工具
 /vin — VIN解析
 /car5 — 车牌查询
 /carplate — 车辆信息

🏢 企业工具
 /companyname — 企业查询
 /companystd — 企业标准
 /shixin — 失信查询
 /judicial — 司法查询

💰 钱包
 /balance — 查余额
 /recharge — 充值

📊 用户工具
 /feedback — 反馈建议
 /export — 导出对话
 /clear — 清空记忆
 /today — 今日额度
 /sub — 订阅每日推送

━━━━━━━━━━━━
📞 客服 @qishe77
🌐 https://sfw.bar/qishe77"""
        send_long_message(cid, help_text); return

    if txt.startswith("/fortune"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service
        c = txt.replace("/fortune", "", 1).strip()
        if not c: send_message(cid, "🔮 格式：/fortune 1995-06-15 [想问的事]"); return
        parts = c.split(" ", 1)
        nid = send_message(cid, "🔮 正在推演命运...")
        reply = ai_service.fortune_telling(parts[0], parts[1] if len(parts) > 1 else "")
        delete_message(cid, nid)
        send_message(cid, "🔮 命理解读" + chr(10) + "━━━━━━━━━━━━" + chr(10) + reply); return

    if txt.startswith("/dream"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service
        c = txt.replace("/dream", "", 1).strip()
        if not c: send_message(cid, "💭 格式：/dream 我梦见自己飞"); return
        nid = send_message(cid, "💭 正在解析梦境...")
        reply = ai_service.dream_analysis(c)
        delete_message(cid, nid)
        send_message(cid, "💭 梦境解析" + chr(10) + "━━━━━━━━━━━━" + chr(10) + reply); return

    if txt.startswith("/story"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service
        from safew_api import send_voice
        c = txt.replace("/story", "", 1).strip()
        if not c: send_message(cid, "📖 格式：/story 主题 [风格]"); return
        nid = send_message(cid, "📖 正在创作故事...")
        reply = ai_service.tell_story(c)
        delete_message(cid, nid)
        send_message(cid, "📖 " + reply)
        nid2 = send_message(cid, "🎙 正在合成语音...")
        audio = ai_service.text_to_speech(reply[:280])
        delete_message(cid, nid2)
        if audio:
            send_voice(cid, audio)
        return

    if txt.startswith("/avatar"):
        import ai_service
        c = txt.replace("/avatar", "", 1).strip()
        if not c: send_message(cid, "🖼 格式：/avatar 风格关键词（如：赛博朋克 机甲战士）"); return
        nid = send_message(cid, "🖼 正在生成头像...")
        img = ai_service.generate_image("用户头像，" + c + "，简洁方构图，居中")
        delete_message(cid, nid)
        if img:
            send_photo(cid, img, caption="🖼 你的专属头像")
        else:
            send_message(cid, "❌ 生成失败")
        return

    if txt.startswith("/clear"):
        import ai_service as _ai3
        _ai3.clear_history(uid)
        send_message(cid, "✅ 对话记忆已清空"); return

    if txt.startswith("/setid"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能改"); return
        new_content = txt.replace("/setid", "", 1).strip()
        if not new_content:
            try:
                with open("/root/AIbot/identity.txt", "r", encoding="utf-8") as f:
                    current = f.read()
                send_message(cid, "📄 当前身份设定：\n━━━━━━━━━━━━\n" + current[:1500] + "\n━━━━━━━━━━━━\n\n修改：/setid 新内容")
            except:
                send_message(cid, "❌ 读取身份文件失败")
            return
        try:
            with open("/root/AIbot/identity.txt", "w", encoding="utf-8") as f:
                f.write(new_content)
            send_message(cid, "✅ 身份已更新，下次对话立即生效")
        except Exception as e:
            send_message(cid, "❌ 保存失败：" + str(e)[:80])
        return

    if txt.startswith("/tarot"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        q = txt.replace("/tarot", "", 1).strip()
        nid = send_message(cid, "🔮 正在洗牌...")
        r = _a.tarot_reading(q)
        delete_message(cid, nid)
        send_message(cid, "🔮 塔罗占卜" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/horoscope"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        sign = txt.replace("/horoscope", "", 1).strip()
        if not sign: send_message(cid, "♈ 格式：/horoscope 摩羯座"); return
        nid = send_message(cid, "✨ 正在测算...")
        r = _a.horoscope(sign)
        delete_message(cid, nid)
        send_message(cid, "✨ " + sign + " 今日运势" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/love"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        send_message(cid, "💕 " + _a.love_words()); return

    if txt.startswith("/poem"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        w = txt.replace("/poem", "", 1).strip()
        if not w: send_message(cid, "📝 格式：/poem 恭喜发财"); return
        nid = send_message(cid, "📝 创作中...")
        r = _a.acrostic_poem(w)
        delete_message(cid, nid)
        send_message(cid, "📝 " + r); return

    if txt.startswith("/name"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        k = txt.replace("/name", "", 1).strip()
        if not k: send_message(cid, "📛 格式：/name 女孩"); return
        nid = send_message(cid, "📛 起名中...")
        r = _a.ai_name(k)
        delete_message(cid, nid)
        send_message(cid, "📛 " + r); return

    if txt.startswith("/translate"):
        import ai_service as _a
        c = txt.replace("/translate", "", 1).strip()
        parts = c.split(" ", 1)
        if len(parts) < 2: send_message(cid, "🌐 格式：/translate en 你好"); return
        send_message(cid, "🌐 " + _a.translate_text(parts[0], parts[1])); return

    if txt.startswith("/roast"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        t = txt.replace("/roast", "", 1).strip() or "我"
        send_message(cid, "😂 " + _a.roast_words(t)); return

    if txt.startswith("/riddle"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        send_message(cid, "🧠 " + _a.brain_riddle()); return

    if txt.startswith("/couple"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/couple", "", 1).strip()
        parts = c.split()
        if len(parts) < 2: send_message(cid, "💑 格式：/couple 小明 小红"); return
        send_message(cid, "💑 " + _a.couple_match(parts[0], parts[1])); return

    if txt.startswith("/push_cancel"):
        if uid not in ADMIN_IDS: return
        PUSH_DRAFT.pop(uid, None)
        send_message(cid, "❌ 已取消推送"); return

    if txt.startswith("/push_confirm"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        if uid not in PUSH_DRAFT:
            send_message(cid, "❌ 没有待发送的推送，请先用 /push 创建"); return
        draft = PUSH_DRAFT.pop(uid)
        import threading, database as _db, safew_api as _api, time as _t, requests as _rq
        send_message(cid, "🚀 开始推送...")
        def _do_push():
            users = _db.get_all_uids()
            ok = 0; fail = 0
            markup = None
            if draft.get("buttons"):
                markup = {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}] for b in draft["buttons"]]}
            img_bytes = None
            if draft.get("img_url"):
                try:
                    img_bytes = _rq.get(draft["img_url"], timeout=20).content
                except: img_bytes = None
            for i, u in enumerate(users):
                try:
                    if img_bytes:
                        _api.send_photo(u, img_bytes, caption=draft["text"], custom_markup=markup)
                    else:
                        _api.send_message(u, draft["text"], custom_markup=markup)
                    ok += 1
                except Exception as e:
                    fail += 1
                if i % 30 == 29:
                    _t.sleep(1)
            try:
                send_message(cid, "✅ 推送完成\n成功：" + str(ok) + "\n失败：" + str(fail))
            except: pass
        threading.Thread(target=_do_push, daemon=True).start()
        return

    if txt.startswith("/push"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        body = txt.replace("/push", "", 1).strip()
        if not body:
            send_message(cid, """📢 群发推送
━━━━━━━━━━━━
格式：/push 文案 || 图片URL || 按钮

示例：
• 纯文字：
/push 你好

• 带图：
/push 今晚8点上线 || https://xxx.jpg

• 带按钮：
/push 新品上线 || || 立即抢购|https://buy.com;联系客服|https://t.me/xxx

• 全都有：
/push 🎉 新品上线 || https://xxx.jpg || 立即抢购|https://buy.com;联系客服|https://t.me/xxx

━━━━━━━━━━━━
支持多个按钮，用 ; 分隔""")
            return
        parts = [p.strip() for p in body.split("||")]
        text = parts[0] if len(parts) > 0 else ""
        img_url = parts[1] if len(parts) > 1 else ""
        btns_str = parts[2] if len(parts) > 2 else ""
        buttons = []
        if btns_str:
            for b in btns_str.split(";"):
                if "|" in b:
                    t_, u_ = b.split("|", 1)
                    buttons.append({"text": t_.strip(), "url": u_.strip()})
        PUSH_DRAFT[uid] = {"text": text, "img_url": img_url, "buttons": buttons}
        import database as _db2
        try:
            count = len(_db2.get_all_uids())
        except: count = 0
        preview = "📢 推送预览\n━━━━━━━━━━━━\n"
        preview += "文案：\n" + (text if text else "(空)") + "\n"
        if img_url:
            preview += "\n🖼 图片：" + img_url + "\n"
        if buttons:
            preview += "\n🔘 按钮：\n"
            for b in buttons:
                preview += "  • " + b["text"] + " → " + b["url"] + "\n"
        preview += "\n━━━━━━━━━━━━\n"
        preview += "👥 将发送给 " + str(count) + " 个用户\n\n"
        preview += "确认发送：/push_confirm\n取消：/push_cancel"
        send_message(cid, preview)
        return

    if txt.startswith("/stats"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        import database as _d
        try:
            s = _d.get_stats()
            top = ""
            for t, n in s["top_funcs"]:
                top += "  • /" + str(t) + "：" + str(n) + " 次" + chr(10)
            msg = "📊 SAFW AI 运营数据" + chr(10) + "━━━━━━━━━━━━" + chr(10)
            msg += "👥 总用户：" + str(s["total_users"]) + chr(10)
            msg += "📈 今日新增：" + str(s["today_new"]) + chr(10)
            msg += "🟢 今日活跃：" + str(s["today_active"]) + chr(10)
            msg += "💰 总充值：" + str(round(s["total_recharge"], 2)) + " USDT" + chr(10)
            msg += "💵 今日充值：" + str(round(s["today_recharge"], 2)) + " USDT" + chr(10)
            msg += "📉 今日消费：" + str(round(s["today_cost"], 2)) + " USDT" + chr(10)
            msg += chr(10) + "🔥 最热功能 TOP5：" + chr(10) + (top if top else "  (暂无)")
            msg += chr(10) + "📮 待处理反馈：" + str(s["pending_fb"]) + " 条"
            send_message(cid, msg)
        except Exception as e:
            send_message(cid, "❌ 获取失败：" + str(e)[:80])
        return

    if txt.startswith("/feedback"):
        c = txt.replace("/feedback", "", 1).strip()
        if not c:
            send_message(cid, "📮 用法：/feedback 你的问题或建议" + chr(10) + "例如：/feedback 语音条偶尔听不了")
            return
        import database as _d
        _d.add_feedback(uid, un, c)
        send_message(cid, "✅ 反馈已提交，感谢你的建议！" + chr(10) + "有问题可联系 @qishe77")
        return

    if txt.startswith("/fb_list"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        import database as _d
        rows = _d.list_feedback(20)
        if not rows:
            send_message(cid, "📭 暂无反馈"); return
        msg = "📮 最近 20 条反馈" + chr(10) + "━━━━━━━━━━━━" + chr(10)
        for rid, _fb_user, content, ts in rows:
            msg += "#" + str(rid) + " " + str(_fb_user) + " · " + str(ts) + chr(10)
            msg += "  " + str(content)[:120] + chr(10) + chr(10)
        send_long_message(cid, msg)
        return

    if txt.startswith("/export"):
        import json as _j, os as _o, io
        hist_file = "/root/AIbot/histories/" + str(uid) + ".json"
        if not _o.path.exists(hist_file):
            send_message(cid, "📭 你还没有对话记录"); return
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                hist = _j.load(f)
            lines = ["SAFW AI 对话记录", "用户UID：" + str(uid), "导出时间：" + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "=" * 30, ""]
            for m in hist:
                role = "你" if m.get("role") == "user" else "SAFW AI"
                lines.append("[" + role + "]")
                lines.append(str(m.get("content", "")))
                lines.append("")
            content = "\n".join(lines)
            if len(content) > 3000:
                content = content[-3000:]
            send_message(cid, "📄 对话记录（最近部分）" + chr(10) + "━━━━━━━━━━━━" + chr(10) + content)
        except Exception as e:
            send_message(cid, "❌ 导出失败：" + str(e)[:80])
        return

    if txt.startswith("/wallet"):
        import tron_service as _ts
        addr = txt.replace("/wallet", "", 1).strip()
        if not addr:
            send_message(cid, "💼 用法：/wallet Tron地址\n例如：/wallet TTT5MV8xeZqKaPDxUcDjR8bPFz2ce5kmBr")
            return
        WALLET_CACHE[str(uid)] = addr
        nid = send_message(cid, "🔍 查询中...")
        try:
            r = _ts.get_wallet_info(addr)
            delete_message(cid, nid)
            markup = {"inline_keyboard": [
                [{"text": "📜 查询USDT历史", "callback_data": "wallet_usdt"},
                 {"text": "💎 查询TRX历史", "callback_data": "wallet_trx"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ " + str(e)[:100])
        return

    if txt.startswith("/usdt"):
        import tron_service as _ts
        addr = txt.replace("/usdt", "", 1).strip()
        if not addr:
            addr = WALLET_CACHE.get(str(uid), "")
        if not addr:
            send_message(cid, "💵 用法：/usdt Tron地址"); return
        WALLET_CACHE[str(uid)] = addr
        nid = send_message(cid, "🔍 查询 USDT 历史中...")
        try:
            r = _ts.get_usdt_history(addr, 10)
            delete_message(cid, nid)
            markup = {"inline_keyboard": [
                [{"text": "💎 查询TRX历史", "callback_data": "wallet_trx"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ " + str(e)[:100])
        return

    if txt.startswith("/trx"):
        import tron_service as _ts
        addr = txt.replace("/trx", "", 1).strip()
        if not addr:
            addr = WALLET_CACHE.get(str(uid), "")
        if not addr:
            send_message(cid, "💎 用法：/trx Tron地址"); return
        WALLET_CACHE[str(uid)] = addr
        nid = send_message(cid, "🔍 查询 TRX 历史中...")
        try:
            r = _ts.get_trx_history(addr, 10)
            delete_message(cid, nid)
            markup = {"inline_keyboard": [
                [{"text": "📜 查询USDT历史", "callback_data": "wallet_usdt"}],
                [{"text": "🔄 刷新钱包", "callback_data": "wallet_refresh"}]
            ]}
            send_message(cid, r, custom_markup=markup)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ " + str(e)[:100])
        return

    if txt.startswith("/write"):
        import ai_service as _a
        topic = txt.replace("/write", "", 1).strip()
        if not topic: send_message(cid, "✍️ 格式：/write 主题\n例如：/write 我去三亚旅游了"); return
        nid = send_message(cid, "✍️ 生成文案中...")
        r = _a.write_copy(topic)
        delete_message(cid, nid)
        send_long_message(cid, "✍️ 文案生成" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/title"):
        import ai_service as _a
        c = txt.replace("/title", "", 1).strip()
        if not c: send_message(cid, "📝 格式：/title 你的内容"); return
        nid = send_message(cid, "📝 生成标题中...")
        r = _a.generate_titles(c)
        delete_message(cid, nid)
        send_long_message(cid, "📝 标题候选" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/sub"):
        import json as _j3, os as _o3
        sub_file = "/root/AIbot/subscriptions.json"
        subs = {}
        if _o3.path.exists(sub_file):
            try:
                with open(sub_file, "r", encoding="utf-8") as f:
                    subs = _j3.load(f)
            except: subs = {}
        subs[str(uid)] = True
        with open(sub_file, "w", encoding="utf-8") as f:
            _j3.dump(subs, f, ensure_ascii=False)
        send_message(cid, "✅ 已订阅每日推送" + chr(10) + "每天 9:00 推送壁纸+每日一句" + chr(10) + "取消：/unsub"); return

    if txt.startswith("/unsub"):
        import json as _j3, os as _o3
        sub_file = "/root/AIbot/subscriptions.json"
        subs = {}
        if _o3.path.exists(sub_file):
            try:
                with open(sub_file, "r", encoding="utf-8") as f:
                    subs = _j3.load(f)
            except: subs = {}
        subs.pop(str(uid), None)
        with open(sub_file, "w", encoding="utf-8") as f:
            _j3.dump(subs, f, ensure_ascii=False)
        send_message(cid, "🔕 已取消订阅"); return

    if txt.startswith("/meme"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import meme_service as _ms
        c = txt.replace("/meme", "").replace(chr(10), " ").strip()
        if not c: send_message(cid, "🎭 格式：/meme 文字内容 [风格]\n风格：classic/dark/pink/yellow/green/blue"); return
        parts = c.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in ("classic","dark","pink","yellow","green","blue"):
            text, style = parts[0], parts[1]
        else:
            text, style = c, "classic"
        nid = send_message(cid, "🎭 生成中...")
        try:
            img = _ms.make_meme(text, style)
            delete_message(cid, nid)
            send_photo(cid, img, caption="🎭 表情包 · " + BOT_NAME)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ 生成失败：" + str(e)[:80])
        return

    if txt.startswith("/script"):
        import ai_service as _a
        topic = txt.replace("/script", "", 1).strip()
        if not topic: send_message(cid, "🎬 格式：/script 主题\n例如：/script 介绍一款减肥产品"); return
        nid = send_message(cid, "🎬 生成脚本中...")
        r = _a.generate_script(topic)
        delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/meeting"):
        send_message(cid, "🎙 请发一段录音（会议/课堂）并带上 /meeting 描述\n或发送 /meeting 文字内容"); return

    if txt.startswith("/sum"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/sum", "", 1).strip()
        if not c: send_message(cid, "📄 用法：/sum 文章内容"); return
        nid = send_message(cid, "📄 总结中...")
        r = _a.summarize_text(c); delete_message(cid, nid)
        send_long_message(cid, "📄 内容总结" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/polish"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/polish", "", 1).strip()
        if not c: send_message(cid, "✍️ 用法：/polish 要润色的文字"); return
        nid = send_message(cid, "✍️ 润色中...")
        r = _a.polish_text(c); delete_message(cid, nid)
        send_message(cid, "✍️ " + r); return

    if txt.startswith("/explain"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/explain", "", 1).strip()
        if not c: send_message(cid, "💻 用法：/explain 代码"); return
        nid = send_message(cid, "💻 分析中...")
        r = _a.explain_code(c); delete_message(cid, nid)
        send_long_message(cid, "💻 代码解释" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/regex"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/regex", "", 1).strip()
        if not c: send_message(cid, "🔤 用法：/regex 匹配手机号"); return
        send_message(cid, "🔤 " + _a.generate_regex(c)); return

    if txt.startswith("/sql"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/sql", "", 1).strip()
        if not c: send_message(cid, "🗄 用法：/sql 查最近7天订单"); return
        send_message(cid, "🗄 " + _a.generate_sql(c)); return

    if txt.startswith("/weekly"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/weekly", "", 1).strip()
        if not c: send_message(cid, "📊 用法：/weekly 本周工作内容"); return
        nid = send_message(cid, "📊 生成周报中...")
        r = _a.generate_weekly(c); delete_message(cid, nid)
        send_long_message(cid, "📊 周报" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/contract"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/contract", "", 1).strip()
        if not c: send_message(cid, "📜 用法：/contract 合同文本"); return
        nid = send_message(cid, "📜 审查中...")
        r = _a.review_contract(c); delete_message(cid, nid)
        send_long_message(cid, "📜 合同审查" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/emotion"):
        import ai_service as _a
        c = txt.replace("/emotion", "", 1).strip()
        if not c: send_message(cid, "😊 用法：/emotion 要分析的文字"); return
        send_message(cid, "😊 " + _a.analyze_emotion(c)); return

    # ===== 图像类 =====
    if txt.startswith("/poster"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        import ai_service as _a
        c = txt.replace("/poster", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/poster 描述"); return
        nid = send_message(cid, "🎨 生成海报中...")
        img = _a.gen_poster(c); delete_message(cid, nid)
        if img: send_photo(cid, img, caption="🎨 海报 · " + BOT_NAME)
        else: send_message(cid, "❌ 生成失败")
        return

    if txt.startswith("/logo"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        import ai_service as _a
        c = txt.replace("/logo", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/logo 品牌名"); return
        nid = send_message(cid, "🎨 设计LOGO中...")
        img = _a.gen_logo(c); delete_message(cid, nid)
        if img: send_photo(cid, img, caption="🎨 LOGO · " + BOT_NAME)
        else: send_message(cid, "❌ 生成失败")
        return

    if txt.startswith("/product"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        import ai_service as _a
        c = txt.replace("/product", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/product 商品描述"); return
        nid = send_message(cid, "🎨 生成商品图中...")
        img = _a.gen_product(c); delete_message(cid, nid)
        if img: send_photo(cid, img, caption="🎨 商品图 · " + BOT_NAME)
        else: send_message(cid, "❌ 生成失败")
        return

    if txt.startswith("/comic"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/comic", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/comic 故事"); return
        nid = send_message(cid, "🎨 生成分镜中...")
        r = _a.gen_comic(c); delete_message(cid, nid)
        send_long_message(cid, "🎨 漫画分镜" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/pixel"):
        if not check_quota(cid, uid, un, "draw", QUOTA["draw"][0], QUOTA["draw"][1]): return
        import ai_service as _a
        c = txt.replace("/pixel", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/pixel 描述"); return
        nid = send_message(cid, "🎨 生成像素画中...")
        img = _a.gen_pixel(c); delete_message(cid, nid)
        if img: send_photo(cid, img, caption="🎨 像素画 · " + BOT_NAME)
        else: send_message(cid, "❌ 生成失败")
        return

    # ===== 语音类 =====
    if txt.startswith("/read"):
        import ai_service as _a
        from safew_api import send_voice
        c = txt.replace("/read", "", 1).strip()
        if not c: send_message(cid, "🎙 用法：/read [en/ja/ko] 文字（默认中文）"); return
        lang = "zh"
        for _l in ["en", "ja", "ko"]:
            if c.startswith(_l + " "):
                lang = _l; c = c[3:].strip(); break
        nid = send_message(cid, "🎙 合成中...")
        audio = _a.read_multilang(c, lang); delete_message(cid, nid)
        if audio: send_voice(cid, audio)
        else: send_message(cid, "❌ 合成失败")
        return

    if txt.startswith("/audiobook"):
        import ai_service as _a
        from safew_api import send_voice
        c = txt.replace("/audiobook", "", 1).strip()
        if not c: send_message(cid, "🎙 用法：/audiobook 长文（限500字）"); return
        nid = send_message(cid, "🎙 合成有声书中...")
        audio = _a.make_audiobook(c); delete_message(cid, nid)
        if audio: send_voice(cid, audio)
        else: send_message(cid, "❌ 失败")
        return

    # ===== 职场类 =====
    if txt.startswith("/email"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/email", "", 1).strip()
        if not c: send_message(cid, "📧 用法：/email 主题"); return
        nid = send_message(cid, "📧 生成中...")
        r = _a.gen_email(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/resume"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/resume", "", 1).strip()
        if not c: send_message(cid, "📄 用法：/resume 经历"); return
        nid = send_message(cid, "📄 优化中...")
        r = _a.gen_resume(c); delete_message(cid, nid)
        send_long_message(cid, "📄 简历优化" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/interview"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/interview", "", 1).strip()
        if not c: send_message(cid, "💼 用法：/interview 岗位"); return
        nid = send_message(cid, "💼 准备中...")
        r = _a.gen_interview(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/ppt"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/ppt", "", 1).strip()
        if not c: send_message(cid, "📊 用法：/ppt 主题"); return
        nid = send_message(cid, "📊 生成中...")
        r = _a.gen_ppt(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/mindmap"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/mindmap", "", 1).strip()
        if not c: send_message(cid, "🧠 用法：/mindmap 主题"); return
        nid = send_message(cid, "🧠 生成中...")
        r = _a.gen_mindmap(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    # ===== 学习类 =====
    if txt.startswith("/word"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        nid = send_message(cid, "📚 查询单词中...")
        r = _a.daily_word(); delete_message(cid, nid)
        send_long_message(cid, "📚 每日单词" + chr(10) + "━━━━━━━━━━━━" + chr(10) + r); return

    if txt.startswith("/grammar"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/grammar", "", 1).strip()
        if not c: send_message(cid, "📝 用法：/grammar 英文句子"); return
        send_message(cid, "📝 " + _a.check_grammar(c)); return

    if txt.startswith("/essay"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/essay", "", 1).strip()
        if not c: send_message(cid, "📝 用法：/essay 题目"); return
        nid = send_message(cid, "📝 写作中...")
        r = _a.gen_essay(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/quiz"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/quiz", "", 1).strip()
        if not c: send_message(cid, "❓ 用法：/quiz 学科"); return
        nid = send_message(cid, "❓ 出题中...")
        r = _a.make_quiz(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/math"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/math", "", 1).strip()
        if not c: send_message(cid, "🔢 用法：/math 题目"); return
        nid = send_message(cid, "🔢 解题中...")
        r = _a.solve_math(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    # ===== 生活类 =====
    if txt.startswith("/recipe"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/recipe", "", 1).strip()
        if not c: send_message(cid, "🍳 用法：/recipe 食材"); return
        nid = send_message(cid, "🍳 生成菜谱中...")
        r = _a.get_recipe(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/travel"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/travel", "", 1).strip()
        if not c: send_message(cid, "✈️ 用法：/travel 城市 天数"); return
        nid = send_message(cid, "✈️ 规划中...")
        r = _a.gen_travel(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/diet"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/diet", "", 1).strip()
        if not c: send_message(cid, "🥗 用法：/diet 减肥/增肌"); return
        nid = send_message(cid, "🥗 生成计划中...")
        r = _a.gen_diet(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/workout"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/workout", "", 1).strip()
        if not c: send_message(cid, "💪 用法：/workout 胸/背/腿"); return
        nid = send_message(cid, "💪 生成中...")
        r = _a.gen_workout(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/shopping"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/shopping", "", 1).strip()
        if not c: send_message(cid, "🛍 用法：/shopping 需求"); return
        nid = send_message(cid, "🛍 推荐中...")
        r = _a.gen_shopping(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    # ===== 娱乐类 =====
    if txt.startswith("/story2"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/story2", "", 1).strip()
        if not c: send_message(cid, "📖 用法：/story2 故事开头"); return
        nid = send_message(cid, "📖 创作中...")
        r = _a.start_story(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/character"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/character", "", 1).strip()
        if not c: send_message(cid, "🎭 用法：/character 角色设定"); return
        nid = send_message(cid, "🎭 生成中...")
        r = _a.gen_character(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/trivia"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/trivia", "", 1).strip()
        if not c: send_message(cid, "🧠 用法：/trivia 主题"); return
        nid = send_message(cid, "🧠 生成中...")
        r = _a.make_trivia(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/debate"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/debate", "", 1).strip()
        if not c: send_message(cid, "⚖️ 用法：/debate 话题"); return
        nid = send_message(cid, "⚖️ 生成中...")
        r = _a.make_debate(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/fortune_daily"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/fortune_daily", "", 1).strip()
        if not c: send_message(cid, "🔮 用法：/fortune_daily 1995-06-15"); return
        nid = send_message(cid, "🔮 测算中...")
        r = _a.fortune_daily(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    # ===== 创意类 =====
    if txt.startswith("/slogan"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/slogan", "", 1).strip()
        if not c: send_message(cid, "✨ 用法：/slogan 产品"); return
        nid = send_message(cid, "✨ 生成中...")
        r = _a.gen_slogan(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/brand"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/brand", "", 1).strip()
        if not c: send_message(cid, "🏷 用法：/brand 行业"); return
        nid = send_message(cid, "🏷 生成中...")
        r = _a.gen_brand(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/tagline"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/tagline", "", 1).strip()
        if not c: send_message(cid, "✍️ 用法：/tagline 主题"); return
        send_message(cid, "✍️ " + _a.gen_tagline(c)); return

    if txt.startswith("/hashtag"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/hashtag", "", 1).strip()
        if not c: send_message(cid, "#️⃣ 用法：/hashtag 内容"); return
        nid = send_message(cid, "生成中...")
        r = _a.gen_hashtag(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/bio"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/bio", "", 1).strip()
        if not c: send_message(cid, "👤 用法：/bio 身份"); return
        nid = send_message(cid, "👤 生成中...")
        r = _a.gen_bio(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/wallpaper"):
        nid = send_message(cid, "🖼 获取壁纸中...")
        img = uapi_service.get_wallpaper()
        delete_message(cid, nid)
        if img:
            send_photo(cid, img, caption="🖼 今日壁纸")
            add_record(uid, "wallpaper", "", COST_WALLPAPER)
        else:
            send_message(cid, "❌ 获取失败")
        return
    if txt.startswith("/hotboard"):
        p = txt.replace("/hotboard", "", 1).strip() or "weibo"
        return _run(cid, uid, un, COST_HOTBOARD, "hot", p, lambda: uapi_service.query_hotboard(p))
    if txt.startswith("/epic"):
        return _run(cid, uid, un, COST_EPIC, "epic", "", lambda: uapi_service.query_epic())
    if txt.startswith("/bili_live"):
        c = txt.replace("/bili_live", "", 1).strip()
        if not c: send_message(cid, "📺 格式：/bili_live 房间号"); return
        return _run(cid, uid, un, COST_BILI_LIVE, "blive", c, lambda: uapi_service.query_bili_live(c))
    if txt.startswith("/bili"):
        c = txt.replace("/bili", "", 1).strip()
        if not c: send_message(cid, "📺 格式：/bili UID"); return
        return _run(cid, uid, un, COST_BILI_USER, "bili", c, lambda: uapi_service.query_bilibili_user(c))
    if txt.startswith("/qqgroup"):
        c = txt.replace("/qqgroup", "", 1).strip()
        if not c: send_message(cid, "👥 格式：/qqgroup 群号"); return
        return _run(cid, uid, un, COST_QQ_GROUP, "qqgroup", c, lambda: uapi_service.query_qq_group(c))
    if txt.startswith("/qq"):
        c = txt.replace("/qq", "", 1).strip()
        if not c: send_message(cid, "👤 格式：/qq QQ号"); return
        return _run(cid, uid, un, COST_QQ_USER, "qq", c, lambda: uapi_service.query_qq_user(c))
    if txt.startswith("/dns"):
        c = txt.replace("/dns", "", 1).strip()
        if not c: send_message(cid, "🌐 格式：/dns 域名"); return
        return _run(cid, uid, un, COST_DNS, "dns", c, lambda: uapi_service.query_dns(c))

    if txt.startswith("/icpunit"):
        c = txt.replace("/icpunit", "", 1).strip()
        if not c: send_message(cid, "🏢 格式：/icpunit 单位名"); return
        return _run(cid, uid, un, COST_ICP_UNIT, "icpunit", c, lambda: apitg_service.icp_unit(c))
    if txt.startswith("/icp"):
        c = txt.replace("/icp", "", 1).strip()
        if not c: send_message(cid, "📋 格式：/icp 域名"); return
        return _run(cid, uid, un, COST_ICP, "icp", c, lambda: apitg_service.icp_query(c))
    if txt.startswith("/whois"):
        c = txt.replace("/whois", "", 1).strip()
        if not c: send_message(cid, "🌐 格式：/whois 域名"); return
        return _run(cid, uid, un, COST_WHOIS, "whois", c, lambda: apitg_service.whois_query(c))
    if txt.startswith("/tdk"):
        c = txt.replace("/tdk", "", 1).strip()
        if not c: send_message(cid, "📌 格式：/tdk URL"); return
        return _run(cid, uid, un, 0, "tdk", c, lambda: apitg_service.site_tdk(c))
    if txt.startswith("/baiduindex"):
        c = txt.replace("/baiduindex", "", 1).strip()
        if not c: send_message(cid, "📊 格式：/baiduindex 域名"); return
        return _run(cid, uid, un, COST_BAIDU_INDEX, "bdi", c, lambda: apitg_service.baidu_index(c))
    if txt.startswith("/baiduweight"):
        c = txt.replace("/baiduweight", "", 1).strip()
        if not c: send_message(cid, "📊 格式：/baiduweight 域名"); return
        return _run(cid, uid, un, COST_BAIDU_WEIGHT, "bdw", c, lambda: apitg_service.baidu_weight(c))
    if txt.startswith("/qqblock"):
        c = txt.replace("/qqblock", "", 1).strip()
        if not c: send_message(cid, "🛡 格式：/qqblock URL"); return
        return _run(cid, uid, un, COST_QQ_BLOCK, "qqb", c, lambda: apitg_service.qq_block(c))
    if txt.startswith("/wxblock"):
        c = txt.replace("/wxblock", "", 1).strip()
        if not c: send_message(cid, "🛡 格式：/wxblock URL"); return
        return _run(cid, uid, un, COST_WX_BLOCK, "wxb", c, lambda: apitg_service.wx_block(c))

    if txt.startswith("/phone_two"):
        p = txt.replace("/phone_two", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "📱 格式：/phone_two 姓名 手机号"); return
        return _run(cid, uid, un, COST_PHONE_TWO, "two", p[0], lambda: apitg_service.phone_two(p[0], p[1]))
    if txt.startswith("/phone_three"):
        p = txt.replace("/phone_three", "", 1).strip().split()
        if len(p) < 3: send_message(cid, "📱 格式：/phone_three 姓名 手机号 身份证"); return
        return _run(cid, uid, un, COST_PHONE_THREE, "three", p[0], lambda: apitg_service.phone_three(p[0], p[1], p[2]))
    if txt.startswith("/phone_status"):
        c = txt.replace("/phone_status", "", 1).strip()
        if not c: send_message(cid, "📱 格式：/phone_status 手机号"); return
        return _run(cid, uid, un, COST_PHONE_STATUS, "stat", c, lambda: apitg_service.phone_status(c))
    if txt.startswith("/phone_age"):
        c = txt.replace("/phone_age", "", 1).strip()
        if not c: send_message(cid, "📱 格式：/phone_age 手机号"); return
        return _run(cid, uid, un, COST_PHONE_AGE, "age", c, lambda: apitg_service.phone_age(c))
    if txt.startswith("/phone_balance"):
        c = txt.replace("/phone_balance", "", 1).strip()
        if not c: send_message(cid, "📱 格式：/phone_balance 手机号"); return
        return _run(cid, uid, un, COST_PHONE_BALANCE, "bal", c, lambda: apitg_service.phone_balance(c))
    if txt.startswith("/phone"):
        c = txt.replace("/phone", "", 1).strip()
        if not c: send_message(cid, "📱 格式：/phone 手机号"); return
        return _run(cid, uid, un, COST_PHONE, "phone", c, lambda: apitg_service.phone_area(c))

    if txt.startswith("/idcardreal"):
        p = txt.replace("/idcardreal", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "🆔 格式：/idcardreal 姓名 身份证"); return
        return _run(cid, uid, un, COST_IDCARD_REAL, "real", p[0], lambda: apitg_service.idcard_real(p[0], p[1]))
    if txt.startswith("/idcardarea"):
        c = txt.replace("/idcardarea", "", 1).strip()
        if not c: send_message(cid, "🆔 格式：/idcardarea 身份证"); return
        return _run(cid, uid, un, COST_IDCARD_AREA, "area", c, lambda: apitg_service.idcard_area(c))
    if txt.startswith("/bankarea"):
        c = txt.replace("/bankarea", "", 1).strip()
        if not c: send_message(cid, "💳 格式：/bankarea 卡号"); return
        return _run(cid, uid, un, COST_BANK_AREA, "bank", c, lambda: apitg_service.bank_area(c))

    if txt.startswith("/car5"):
        c = txt.replace("/car5", "", 1).strip()
        if not c: send_message(cid, "🚗 格式：/car5 车牌号"); return
        return _run(cid, uid, un, COST_CAR_5, "car5", c, lambda: apitg_service.car_5(c))
    if txt.startswith("/carplate"):
        c = txt.replace("/carplate", "", 1).strip()
        if not c: send_message(cid, "🚗 格式：/carplate 车牌号"); return
        return _run(cid, uid, un, COST_CAR_INFO, "plate", c, lambda: apitg_service.car_plate(c))
    if txt.startswith("/vin"):
        c = txt.replace("/vin", "", 1).strip()
        if not c: send_message(cid, "🔢 格式：/vin VIN码"); return
        return _run(cid, uid, un, COST_VIN, "vin", c, lambda: apitg_service.vin_query(c))
    if txt.startswith("/carinsurance"):
        c = txt.replace("/carinsurance", "", 1).strip()
        if not c: send_message(cid, "📋 格式：/carinsurance 身份证"); return
        return _run(cid, uid, un, COST_CAR_INSURANCE, "cins", c, lambda: apitg_service.car_insurance(c))
    if txt.startswith("/cartransfer"):
        c = txt.replace("/cartransfer", "", 1).strip()
        if not c: send_message(cid, "🔄 格式：/cartransfer 身份证"); return
        return _run(cid, uid, un, COST_CAR_TRANSFER, "ctr", c, lambda: apitg_service.car_transfer(c))

    if txt.startswith("/companyname"):
        c = txt.replace("/companyname", "", 1).strip()
        if not c: send_message(cid, "🏢 格式：/companyname 关键词"); return
        return _run(cid, uid, un, COST_COMPANY_NAME, "cn", c, lambda: apitg_service.company_name("1", c))
    if txt.startswith("/companyfuzzy"):
        c = txt.replace("/companyfuzzy", "", 1).strip()
        if not c: send_message(cid, "🏢 格式：/companyfuzzy 关键词"); return
        return _run(cid, uid, un, COST_COMPANY_FUZZY, "cf", c, lambda: apitg_service.company_fuzzy("1", c))
    if txt.startswith("/companystd"):
        c = txt.replace("/companystd", "", 1).strip()
        if not c: send_message(cid, "🏢 格式：/companystd 公司名"); return
        return _run(cid, uid, un, COST_COMPANY_STD, "cs", c, lambda: apitg_service.company_std(c))
    if txt.startswith("/companyrecord"):
        p = txt.replace("/companyrecord", "", 1).strip().split()
        if len(p) < 1: send_message(cid, "👤 格式：/companyrecord 身份证 [姓名]"); return
        nm = p[1] if len(p) >= 2 else None
        return _run(cid, uid, un, COST_COMPANY_RECORD, "cr", p[0], lambda: apitg_service.company_record(p[0], nm))
    if txt.startswith("/shixin"):
        p = txt.replace("/shixin", "", 1).strip().split()
        if len(p) < 1: send_message(cid, "🚨 格式：/shixin 姓名 [身份证]"); return
        ic = p[1] if len(p) >= 2 else None
        return _run(cid, uid, un, COST_SHIXIN, "sx", p[0], lambda: apitg_service.shixin(p[0], ic))
    if txt.startswith("/xiangao"):
        p = txt.replace("/xiangao", "", 1).strip().split()
        if len(p) < 1: send_message(cid, "🚫 格式：/xiangao 姓名 [身份证]"); return
        ic = p[1] if len(p) >= 2 else None
        return _run(cid, uid, un, COST_XIANGAO, "xg", p[0], lambda: apitg_service.xiangao(p[0], ic))
    if txt.startswith("/judicial"):
        p = txt.replace("/judicial", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "⚖️ 格式：/judicial 姓名 身份证"); return
        return _run(cid, uid, un, COST_JUDICIAL, "jd", p[0], lambda: apitg_service.judicial(p[0], p[1]))
    if txt.startswith("/badrecord"):
        p = txt.replace("/badrecord", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "📋 格式：/badrecord 姓名 身份证"); return
        return _run(cid, uid, un, COST_BADRECORD, "br", p[0], lambda: apitg_service.bad_record(p[0], p[1]))

    if txt.startswith("/exchange"):
        p = txt.replace("/exchange", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "💱 格式：/exchange 金额 币种"); return
        return _run(cid, uid, un, COST_EXCHANGE, "ex", p[0], lambda: apitg_service.exchange(p[0], p[1]))
    if txt.startswith("/lottery"):
        c = txt.replace("/lottery", "", 1).strip()
        if not c: send_message(cid, "🎰 格式：/lottery 类型"); return
        return _run(cid, uid, un, COST_LOTTERY, "lot", c, lambda: apitg_service.lottery(c))

    nid = send_message(cid, "💬 思考中...")
    import json as _json, os as _os
    import ai_service as _ai
    _link_match = re.search(r'https?://[^\s]+', txt)
    _role_file = "/root/AIbot/user_roles.json"
    _roles = {}
    if _os.path.exists(_role_file):
        try:
            with open(_role_file, "r", encoding="utf-8") as f:
                _roles = _json.load(f)
        except: _roles = {}
    _r = _roles.get(str(uid))
    # ========== 智能判断任务类型 ==========
    _reason_kw = ["为什么", "推理", "证明", "计算", "分析", "逻辑", "对比", "优缺点",
                  "详细解释", "深入", "原理", "推导", "论证", "评估", "判断"]
    _task = "auto"
    if any(k in txt for k in _reason_kw) and len(txt) > 10:
        _task = "reason"

    if _r and _r in ROLE_PRESETS:
        _system = ROLE_PRESETS[_r][1]
        reply = _ai.generate_text_role(txt, _system)
    elif _link_match:
        reply = _ai.summarize_url(_link_match.group(0))
    else:
        # 用智能路由（智谱优先，失败切 OpenRouter）
        reply = _ai.smart_chat(txt, uid=uid, task_type=_task)
    delete_message(cid, nid)

    # 检查语音模式
    import json as _j2, os as _o2
    _vf = "/root/AIbot/user_voice_mode.json"
    _vm = {}
    if _o2.path.exists(_vf):
        try:
            with open(_vf, "r", encoding="utf-8") as f:
                _vm = _j2.load(f)
        except: _vm = {}
    _voice_on = _vm.get(str(uid), False)

    if _voice_on:
        import ai_service
        from safew_api import send_voice
        _tts_text = reply[:200]
        _audio = ai_service.text_to_speech(_tts_text)
        if _audio:
            send_voice(cid, _audio)
        else:
            if group and mid:
                reply = "@" + un + " " + reply
            send_long_message(cid, reply, reply_to_msg_id=mid if group else None)
    else:
        if group and mid:
            reply = "@" + un + " " + reply
        send_long_message(cid, reply, reply_to_msg_id=mid if group else None)
