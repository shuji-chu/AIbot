import re, time, random
from config import (TRON_WALLET, QUOTA, VIP_QUOTA, VIP_PRICE, VIP_DAYS, BOT_NAME, BOT_USERNAME, ADMIN_IDS, MIN_RECHARGE,
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

# 等待第二张图的用户：{uid: {"type": "face/cloth", "first_url": "..."}}
SWAP_PENDING = {}

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

def friendly_error(e, context=""):
    """友好错误提示"""
    err = str(e)[:150]
    if "timeout" in err.lower() or "timed out" in err.lower():
        return "⏰ 请求超时，请稍后再试"
    if "connection" in err.lower() or "connect" in err.lower():
        return "🌐 网络异常，请稍后再试"
    if "401" in err or "403" in err or "unauthorized" in err.lower():
        return "🔒 服务未授权，请联系客服 @qishe77"
    if "429" in err or "rate" in err.lower():
        return "⏱ 请求过于频繁，请稍后再试"
    if "500" in err or "502" in err or "503" in err:
        return "🔧 服务临时故障，请稍后再试"
    return "❌ 处理失败：请联系客服 @qishe77"

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
    # 会员优先用会员配额
    if _d.is_vip(uid) and feature in VIP_QUOTA:
        daily_free, cost = VIP_QUOTA[feature]
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

# ==================== 菜单系统 ====================
def _load_ads():
    """读取广告位"""
    import json as _j, os as _o
    p = "/root/AIbot/ads.json"
    if not _o.path.exists(p): return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return _j.load(f)
    except: return {}



# ==================== 分页帮助菜单 ====================
HELP_CATEGORIES = {
    "ai": ("🎨 AI 创作", [
        "/draw /draw_h /draw_v — 绘画",
        "/agimg — Agnes绘画",
        "/pixel — 像素画",
        "/poster /logo /product — 海报/LOGO/商品图",
        "/comic — 漫画分镜",
        "/avatar — 头像生成",
        "/video /agvideo — AI视频",
        "/img2video — 图生视频",
        "/gif — GIF生成",
        "/style — 风格转换",
        "/face_swap — 换脸",
        "/cloth_swap — 换衣",
        "/meme — 表情包",
        "/tts — 文字转语音",
        "/read — 多语言朗读",
        "/audiobook — 有声书",
        "/voice — 语音模式开关",
    ]),
    "chat": ("💬 智能对话", [
        "直接发消息即可（无限免费）",
        "/gtext — 智谱对话",
        "/cftext — Cloudflare对话",
        "/role — 8种角色扮演",
        "/clear — 清空记忆",
        "/export — 导出对话",
        "/scan — 拍照识别",
    ]),
    "write": ("✍️ AI 写作", [
        "/sum — 文章总结",
        "/doc — 文档处理",
        "/emotion — 情感分析",
        "/contract — 合同审查",
        "/write — 文案生成",
        "/script — 短视频脚本",
        "/title — 爆款标题",
        "/polish — 文字润色",
        "/email — 邮件生成",
        "/resume — 简历优化",
        "/ppt — PPT大纲",
        "/weekly — 周报生成",
        "/meeting — 会议纪要",
        "/research — 深度研究",
    ]),
    "study": ("📚 AI 学习", [
        "/word — 每日单词",
        "/grammar — 语法纠错",
        "/essay — 英语作文",
        "/quiz — 出题练习",
        "/math — 数学解题",
        "/homework — 作业辅导",
        "/bedtime — 睡前故事",
    ]),
    "fun": ("🔮 趣味娱乐", [
        "/tarot — 塔罗牌",
        "/horoscope — 星座运势",
        "/fortune — 算命",
        "/dream — 解梦",
        "/fortune_daily — 每日运势",
        "/love — 情话",
        "/poem — 藏头诗",
        "/story /story2 — 故事",
        "/riddle — 脑筋急转弯",
        "/saying — 每日一句",
        "/character — 角色卡",
        "/name — 起名",
        "/couple — 姓名配对",
        "/roast — 吐槽",
        "/trivia — 冷知识",
        "/debate — 辩论",
    ]),
    "life": ("🏠 生活助手", [
        "/recipe — 菜谱",
        "/diet — 饮食计划",
        "/travel — 旅游攻略",
        "/workout — 健身动作",
        "/mood — 情绪疏导",
        "/water — 喝水提醒",
        "/sleep — 睡眠建议",
        "/shopping — 购物推荐",
        "/interview — 面试题",
        "/negotiate — 谈判话术",
        "/apology — 道歉信",
        "/complain — 投诉信",
        "/mindmap — 思维导图",
    ]),
    "dev": ("💻 开发工具", [
        "/explain — 代码解释",
        "/regex — 正则生成",
        "/sql — SQL生成",
        "/translate /trans — 翻译",
        "/pwd — 密码生成",
        "/hash — 哈希计算",
        "/md5 — MD5",
        "/b64e /b64d — Base64",
        "/age — 年龄计算",
        "/roman — 罗马数字",
        "/random — 随机数",
        "/count — 字数统计",
        "/pick — 随机选择",
        "/reverse — 反转",
        "/uuid — UUID",
        "/color — 颜色信息",
        "/short — 短链接",
        "/rps — 剪刀石头布",
        "/20q — 20问猜谜",
        "/guess_start — 猜数字",
    ]),
    "data": ("🌐 全球数据（免费）", [
        "/btc — 比特币价格",
        "/eth — 以太坊价格",
        "/crypto — 加密货币",
        "/weather /w — 天气",
        "/weather2 — 天气（备用）",
        "/anime — 动漫查询",
        "/freegame — 免费游戏",
        "/wiki — 维基百科",
        "/news — 科技新闻",
        "/fact — 冷知识",
        "/dog — 随机狗图",
        "/cat — 随机猫图",
        "/iplookup /ipwho — IP查询",
        "/fx — 汇率",
        "/country — 国家信息",
        "/hotboard — 热搜",
        "/wallpaper — 每日壁纸",
        "/bili /bili_live — B站",
        "/epic — Epic免费游戏",
        "/lottery — 彩票",
        "/qq /qqgroup — QQ",
        "/ip — IP归属",
        "/dns — DNS解析",
        "/qr — 二维码",
        "/timestamp — 时间戳",
    ]),
    "domain": ("🌐 域名工具", [
        "/icp — ICP备案",
        "/icpunit — 主办单位",
        "/whois — WHOIS",
        "/tdk — 网站TDK",
        "/baiduindex — 百度收录",
        "/baiduweight — 百度权重",
        "/qqblock — QQ拦截",
        "/wxblock — 微信拦截",
        "/phone — 手机归属",
        "/phone_status — 在网状态",
        "/phone_age — 使用时长",
        "/phone_balance — 话费余额",
        "/phone_two /phone_three — 二/三要素",
        "/idcardarea — 身份证归属",
        "/idcardreal — 实名认证",
        "/bankarea — 银行卡归属",
        "/vin — VIN解析",
        "/car5 — 车牌查询",
        "/carplate — 车辆信息",
        "/carinsurance — 上险",
        "/cartransfer — 过户",
        "/companyname — 企业查询",
        "/companystd — 企业标准",
        "/companyfuzzy — 模糊查询",
        "/companyrecord — 企业记录",
        "/shixin — 失信查询",
        "/judicial — 司法查询",
        "/xiangao — 限高查询",
        "/badrecord — 不良记录",
        "/express — 快递物流",
    ]),
    "wallet": ("💰 钱包会员", [
        "/balance — 查余额",
        "/recharge — 充值",
        "/today — 今日额度",
        "/vip — 会员套餐（$99/月）",
        "/buy_vip — 开通会员",
        "/wallet — 链上钱包",
        "/usdt — USDT交易",
        "/trx — TRX交易",
        "/novel — 开始写小说",
        "/next — 写下一章",
        "/book — 查看进度",
        "/endbook — 结束本书",
        "/hot_style — 热门画风",
        "/like — 点赞画风",
        "/feedback — 反馈建议",
        "/sub — 订阅推送",
        "/unsub — 取消订阅",
    ]),
}


def help_main_menu():
    return {"inline_keyboard": [
        [{"text": "🎨 AI 创作", "callback_data": "help_ai"},
         {"text": "💬 智能对话", "callback_data": "help_chat"}],
        [{"text": "✍️ AI 写作", "callback_data": "help_write"},
         {"text": "📚 AI 学习", "callback_data": "help_study"}],
        [{"text": "🔮 趣味娱乐", "callback_data": "help_fun"},
         {"text": "🏠 生活助手", "callback_data": "help_life"}],
        [{"text": "💻 开发工具", "callback_data": "help_dev"},
         {"text": "🌐 全球数据", "callback_data": "help_data"}],
        [{"text": "🌐 域名工具", "callback_data": "help_domain"},
         {"text": "💰 钱包会员", "callback_data": "help_wallet"}],
        [{"text": "📞 联系客服", "url": "https://sfw.bar/qishe77"}],
    ]}


def help_category_text(cat_key):
    cat = HELP_CATEGORIES.get(cat_key)
    if not cat:
        return None
    title, items = cat
    text = title + "\n" + "━━━━━━━━━━━━━━\n"
    text += "\n".join(items)
    text += "\n━━━━━━━━━━━━━━\n"
    text += "👑 会员 $99/月：全部无限\n"
    text += "📞 客服 @qishe77"
    return text


def help_back_menu():
    return {"inline_keyboard": [
        [{"text": "◀️ 返回主菜单", "callback_data": "help_home"},
         {"text": "📞 联系客服", "url": "https://sfw.bar/qishe77"}],
    ]}


def main_menu():
    menus = [
        [{"text": "🎨 AI创作", "callback_data": "menu_ai"},
         {"text": "💬 对话聊天", "callback_data": "menu_chat"}],
        [{"text": "🔍 查询工具", "callback_data": "menu_tools"},
         {"text": "💰 钱包会员", "callback_data": "menu_wallet"}],
    ]
    # 广告位
    ads = _load_ads()
    if ads.get("enabled"):
        menus.append([{"text": ads.get("btn_text", "📢 广告位招租"), "callback_data": "menu_ad"}])
    return {"inline_keyboard": menus}

def menu_ai():
    return {"inline_keyboard": [
        [{"text": "🎨 绘画", "callback_data": "cmd_draw"},
         {"text": "🖼 横版", "callback_data": "cmd_draw_h"},
         {"text": "📱 竖版", "callback_data": "cmd_draw_v"}],
        [{"text": "🎬 视频", "callback_data": "cmd_video"},
         {"text": "✨ Agnes绘画", "callback_data": "cmd_agimg"}],
        [{"text": "📰 海报", "callback_data": "cmd_poster"},
         {"text": "🎯 LOGO", "callback_data": "cmd_logo"},
         {"text": "🛍 商品图", "callback_data": "cmd_product"}],
        [{"text": "🎭 换脸", "callback_data": "cmd_face_swap"},
         {"text": "👔 换衣", "callback_data": "cmd_cloth_swap"}],
        [{"text": "😂 表情包", "callback_data": "cmd_meme"},
         {"text": "👾 像素画", "callback_data": "cmd_pixel"}],
        [{"text": "🎙 语音合成", "callback_data": "cmd_tts"},
         {"text": "📖 朗读", "callback_data": "cmd_read"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}

def menu_chat():
    return {"inline_keyboard": [
        [{"text": "💬 直接发消息即可", "callback_data": "noop"}],
        [{"text": "🎭 角色扮演", "callback_data": "cmd_role"},
         {"text": "🔊 语音模式", "callback_data": "cmd_voice"}],
        [{"text": "🔄 清空记忆", "callback_data": "cmd_clear"},
         {"text": "📤 导出对话", "callback_data": "cmd_export"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}

def menu_tools():
    return {"inline_keyboard": [
        [{"text": "🔍 日常查询", "callback_data": "menu_daily"},
         {"text": "🌐 域名工具", "callback_data": "menu_domain"}],
        [{"text": "📱 身份工具", "callback_data": "menu_idcard"},
         {"text": "🚗 车辆工具", "callback_data": "menu_car"}],
        [{"text": "🏢 企业工具", "callback_data": "menu_company"},
         {"text": "⛓ 链上查询", "callback_data": "menu_tron"}],
        [{"text": "📷 识别工具", "callback_data": "menu_scan"},
         {"text": "✍️ AI写作", "callback_data": "menu_write"}],
        [{"text": "🔮 趣味娱乐", "callback_data": "menu_fun"},
         {"text": "💼 职场工具", "callback_data": "menu_work"}],
        [{"text": "🏠 生活助手", "callback_data": "menu_life"},
         {"text": "💻 开发工具", "callback_data": "menu_dev"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}

def menu_wallet():
    return {"inline_keyboard": [
        [{"text": "💰 查余额", "callback_data": "cmd_balance"},
         {"text": "💳 充值", "callback_data": "cmd_recharge"}],
        [{"text": "👑 会员套餐", "callback_data": "cmd_vip"},
         {"text": "💎 开通会员", "callback_data": "cmd_buy_vip"}],
        [{"text": "📊 今日额度", "callback_data": "cmd_today"},
         {"text": "📮 反馈建议", "callback_data": "cmd_feedback"}],
        [{"text": "📅 订阅推送", "callback_data": "cmd_sub"},
         {"text": "🔕 取消订阅", "callback_data": "cmd_unsub"}],
        [{"text": "📖 全部命令", "callback_data": "cmd_help"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}

# ===== 二级菜单 =====
def menu_scan():
    return {"inline_keyboard": [
        [{"text": "📷 直接发图片识别", "callback_data": "noop"}],
        [{"text": "🔍 智能识别", "callback_data": "cmd_scan"},
         {"text": "🎨 风格转换", "callback_data": "cmd_style"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_write():
    return {"inline_keyboard": [
        [{"text": "📄 总结", "callback_data": "cmd_sum"},
         {"text": "✍️ 润色", "callback_data": "cmd_polish"}],
        [{"text": "✏️ 文案", "callback_data": "cmd_write"},
         {"text": "📝 标题", "callback_data": "cmd_title"}],
        [{"text": "🎬 脚本", "callback_data": "cmd_script"},
         {"text": "📧 邮件", "callback_data": "cmd_email"}],
        [{"text": "📋 简历", "callback_data": "cmd_resume"},
         {"text": "📊 PPT", "callback_data": "cmd_ppt"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_fun():
    return {"inline_keyboard": [
        [{"text": "🔮 塔罗", "callback_data": "cmd_tarot"},
         {"text": "✨ 星座", "callback_data": "cmd_horoscope"}],
        [{"text": "🎴 算命", "callback_data": "cmd_fortune"},
         {"text": "💭 解梦", "callback_data": "cmd_dream"}],
        [{"text": "💕 情话", "callback_data": "cmd_love"},
         {"text": "📜 藏头诗", "callback_data": "cmd_poem"}],
        [{"text": "📖 故事", "callback_data": "cmd_story"},
         {"text": "🧩 脑筋急转弯", "callback_data": "cmd_riddle"}],
        [{"text": "💬 每日一句", "callback_data": "cmd_saying"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_work():
    return {"inline_keyboard": [
        [{"text": "💼 面试题", "callback_data": "cmd_interview"},
         {"text": "🧠 思维导图", "callback_data": "cmd_mindmap"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_life():
    return {"inline_keyboard": [
        [{"text": "🍳 菜谱", "callback_data": "cmd_recipe"},
         {"text": "✈️ 旅游", "callback_data": "cmd_travel"}],
        [{"text": "🥗 饮食", "callback_data": "cmd_diet"},
         {"text": "💪 健身", "callback_data": "cmd_workout"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_dev():
    return {"inline_keyboard": [
        [{"text": "💻 代码解释", "callback_data": "cmd_explain"},
         {"text": "🔤 正则", "callback_data": "cmd_regex"}],
        [{"text": "🗄 SQL", "callback_data": "cmd_sql"},
         {"text": "🌐 翻译", "callback_data": "cmd_translate"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_daily():
    return {"inline_keyboard": [
        [{"text": "🌤 天气", "callback_data": "cmd_weather"},
         {"text": "🔥 热搜", "callback_data": "cmd_hotboard"}],
        [{"text": "🖼 壁纸", "callback_data": "cmd_wallpaper"},
         {"text": "🌐 IP", "callback_data": "cmd_ip"}],
        [{"text": "💱 汇率", "callback_data": "cmd_exchange"},
         {"text": "📱 二维码", "callback_data": "cmd_qr"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_domain():
    return {"inline_keyboard": [
        [{"text": "📋 ICP", "callback_data": "cmd_icp"},
         {"text": "🌐 WHOIS", "callback_data": "cmd_whois"}],
        [{"text": "📌 TDK", "callback_data": "cmd_tdk"},
         {"text": "📊 百度收录", "callback_data": "cmd_baiduindex"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_idcard():
    return {"inline_keyboard": [
        [{"text": "📱 手机归属", "callback_data": "cmd_phone"},
         {"text": "🆔 身份证归属", "callback_data": "cmd_idcardarea"}],
        [{"text": "💳 银行卡", "callback_data": "cmd_bankarea"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_car():
    return {"inline_keyboard": [
        [{"text": "🚗 VIN解析", "callback_data": "cmd_vin"},
         {"text": "🚙 车牌查询", "callback_data": "cmd_car5"}],
        [{"text": "🚗 车辆信息", "callback_data": "cmd_carplate"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_company():
    return {"inline_keyboard": [
        [{"text": "🏢 企业查询", "callback_data": "cmd_companyname"},
         {"text": "🏢 企业标准", "callback_data": "cmd_companystd"}],
        [{"text": "⚠️ 失信", "callback_data": "cmd_shixin"},
         {"text": "⚖️ 司法", "callback_data": "cmd_judicial"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_tron():
    return {"inline_keyboard": [
        [{"text": "💼 钱包", "callback_data": "cmd_wallet"},
         {"text": "💵 USDT", "callback_data": "cmd_usdt"}],
        [{"text": "💎 TRX", "callback_data": "cmd_trx"}],
        [{"text": "◀️ 返回", "callback_data": "menu_tools"}],
    ]}

def menu_ad():
    """广告位"""
    ads = _load_ads()
    text = ads.get("content", "📢 广告位招租\n\n联系：@qishe77")
    return {"inline_keyboard": [
        [{"text": ads.get("link_text", "💬 联系客服"), "url": ads.get("link_url", "https://sfw.bar/qishe77")}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}


def menu_study():
    return {"inline_keyboard": [
        [{"text": "📚 每日单词", "callback_data": "cmd_word"},
         {"text": "✅ 语法纠错", "callback_data": "cmd_grammar"}],
        [{"text": "📝 英语作文", "callback_data": "cmd_essay"},
         {"text": "❓ 出题练习", "callback_data": "cmd_quiz"}],
        [{"text": "🔢 数学解题", "callback_data": "cmd_math"}],
        [{"text": "◀️ 返回", "callback_data": "menu_write"}],
    ]}

def menu_vip():
    return {"inline_keyboard": [
        [{"text": "👑 会员套餐", "callback_data": "cmd_vip"},
         {"text": "💎 立即开通", "callback_data": "cmd_buy_vip"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
    ]}

def menu_user():
    return {"inline_keyboard": [
        [{"text": "📮 反馈建议", "callback_data": "cmd_feedback"},
         {"text": "📤 导出对话", "callback_data": "cmd_export"}],
        [{"text": "📊 今日额度", "callback_data": "cmd_today"},
         {"text": "🔄 清空记忆", "callback_data": "cmd_clear"}],
        [{"text": "📅 订阅推送", "callback_data": "cmd_sub"},
         {"text": "🔕 取消订阅", "callback_data": "cmd_unsub"}],
        [{"text": "📖 全部命令", "callback_data": "cmd_help"}],
        [{"text": "◀️ 返回", "callback_data": "menu_home"}],
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
    try:
        import database as _ds
        _ds.user_seen(uid, txt.startswith("/"))
    except: pass

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
            send_message(cid, friendly_error(e))
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
            send_message(cid, friendly_error(e))
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
            send_message(cid, friendly_error(e))
        return
    # ===== 通用命令回调 =====
    if data == "noop":
        return
    if data.startswith("cmd_"):
        _cmd = "/" + data[4:]
        try:
            # 构造假消息，复用 handle_message
            _fake_msg = cq.get("message", {}) or {}
            _fake_msg["text"] = _cmd
            _fake_msg["from"] = cq.get("from", {})
            _fake_msg["chat"] = {"id": cid}
            # 有些命令需要参数，简单命令可直接触发
            _no_arg_cmds = ["help","draw","draw_h","draw_v","agimg","pixel","video","agvideo",
                "poster","logo","product","tts","read","role","scan","style",
                "sum","polish","write","title","script","email","resume","ppt","contract",
                "word","grammar","essay","quiz","math",
                "tarot","horoscope","fortune","dream","love","poem","meme","story","riddle","couple","saying",
                "interview","mindmap",
                "recipe","travel","diet","workout","shopping",
                "explain","regex","sql","translate",
                "weather","hotboard","wallpaper","ip","exchange","qr","md5","timestamp",
                "icp","whois","tdk","baiduindex","baiduweight","qqblock",
                "phone","idcardarea","bankarea",
                "vin","car5","carplate",
                "companyname","companystd","shixin","judicial",
                "wallet","usdt","trx",
                "balance","recharge","vip","buy_vip",
                "feedback","export","clear","today","sub","unsub"]
            if data[4:] in _no_arg_cmds:
                handle_message(_fake_msg)
            else:
                send_message(cid, "💡 请直接发送命令：" + _cmd)
        except Exception as e:
            send_message(cid, friendly_error(e))
        return

    if data == "menu_ad":
        ads = _load_ads()
        text = ads.get("content", "📢 广告位招租\n\n联系：@qishe77")
        delete_message(cid, mid)
        send_message(cid, text, custom_markup=menu_ad()); return

    # ===== 帮助菜单回调 =====
    if data == "help_home":
        delete_message(cid, mid)
        send_message(cid,
            "📖 SAFW AI 功能菜单\n"
            "━━━━━━━━━━━━━━\n"
            "👤 " + un + "\n"
            "💰 余额：$" + ("%.4f" % get_balance(uid)) + " USDT\n"
            "━━━━━━━━━━━━━━\n"
            "👇 点击下方分类查看详细功能",
            custom_markup=help_main_menu())
        return
    if data.startswith("help_"):
        cat_key = data[5:]
        text = help_category_text(cat_key)
        if text:
            delete_message(cid, mid)
            send_message(cid, text, custom_markup=help_back_menu())
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

    if data == "menu_chat":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_chat()); return
    if data == "menu_scan":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_scan()); return
    if data == "menu_write":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_write()); return
    if data == "menu_study":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_study()); return
    if data == "menu_work":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_work()); return
    if data == "menu_life":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_life()); return
    if data == "menu_dev":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_dev()); return
    if data == "menu_tron":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_tron()); return
    if data == "menu_vip":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_vip()); return
    if data == "menu_user":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_user()); return

    if data == "menu_tools":
        delete_message(cid, mid)
        send_message(cid, "📋 菜单", custom_markup=menu_tools()); return


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
    nid = send_message(cid, "⏳ 查询中…")
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
    # ===== 输入清洗 =====
    if txt:
        # 去掉多余空格
        txt = re.sub(r'\s+', ' ', txt).strip()
        # 去掉连续标点
        txt = re.sub(r'([!?.!?])\1{2,}', r'\1', txt)
        # 全角转半角（命令部分）
        if txt.startswith("/"):
            txt = txt.replace("／", "/")

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

    doc = m.get("document") or m.get("file")
    if doc:
        import ai_service as _a
        fid = doc.get("file_id")
        fname = doc.get("file_name") or "document"
        ib = get_file_bytes(fid)
        if not ib:
            send_message(cid, "❌ 下载失败"); return
        if not check_quota(cid, uid, un, "doc", QUOTA.get("doc", (0, 0.10))[0], QUOTA.get("doc", (0, 0.10))[1]): return
        nid = send_message(cid, "📄 解析中...")
        r = _a.process_document(ib, fname)
        try:
            text = ib.decode("utf-8", errors="ignore") if fname.endswith(".txt") else r
            _a.doc_save(uid, fname, text)
        except: pass
        delete_message(cid, nid)
        send_long_message(cid, "📄 文档总结\n━━━━━━━━━━━━\n" + r + "\n\n💡 发 /ask 问题 可针对文档提问"); return

    # ===== 视频处理 =====
    vid = m.get("video") or m.get("animation") or m.get("video_note")
    if vid:
        import ai_service as _av
        fid = vid.get("file_id")
        vb = get_file_bytes(fid)
        if not vb:
            send_message(cid, "❌ 视频下载失败"); return
        q = txt or "描述这个视频的内容"
        nid = send_message(cid, "🎬 视频分析中，约 30 秒...")
        r = _av.understand_video(vb, q)
        delete_message(cid, nid)
        send_long_message(cid, "🎬 视频分析\n━━━━━━━━━━━━\n" + r)
        return

    if ph:
        ib = get_file_bytes(ph[-1]["file_id"])
        if not ib:
            send_message(cid, "❌ 图片下载失败"); return
        import ai_service as _ai2

        # ===== 换脸/换衣：先检查是否在等待第二张图 =====
        _swap = SWAP_PENDING.get(str(uid))
        if _swap:
            SWAP_PENDING.pop(str(uid), None)
            nid = send_message(cid, "⏳ 处理中…")
            try:
                # 上传第二张图到临时图床
                import requests as _rq
                # 用 telegraph 上传
                def _up(b):
                    try:
                        r = _rq.post("https://telegra.ph/upload",
                                     files={"file": ("img.jpg", b, "image/jpeg")},
                                     timeout=30)
                        j = r.json()
                        if isinstance(j, list) and j:
                            return "https://telegra.ph" + j[0].get("src", "")
                    except: pass
                    return None

                src_url = _up(ib)
                if not src_url:
                    delete_message(cid, nid)
                    send_message(cid, "❌ 图片上传失败"); return

                if _swap["type"] == "face":
                    result_url, err = _ai2.face_swap(_swap["first_url"], src_url)
                else:
                    result_url, err = _ai2.cloth_swap(_swap["first_url"], src_url)

                delete_message(cid, nid)
                if result_url:
                    img = _rq.get(result_url, timeout=60).content
                    send_photo(cid, img, caption="🎭 " + BOT_NAME)
                    add_record(uid, "swap", _swap["type"], 1.0)
                else:
                    send_message(cid, "❌ 处理失败：" + str(err)[:150])
            except Exception as e:
                delete_message(cid, nid)
                send_message(cid, friendly_error(e))
            return

        # ===== 换脸/换衣：第一次请求 =====
        if txt.startswith("/face_swap") or txt.startswith("/cloth_swap"):
            if not check_quota(cid, uid, un, "swap", QUOTA.get("swap", (0, 1.0))[0], QUOTA.get("swap", (0, 1.0))[1]):
                return
            nid = send_message(cid, "📸 上传目标图中...")
            try:
                import requests as _rq
                r = _rq.post("https://telegra.ph/upload",
                             files={"file": ("img.jpg", ib, "image/jpeg")},
                             timeout=30)
                j = r.json()
                url = "https://telegra.ph" + j[0].get("src", "") if isinstance(j, list) and j else None
                delete_message(cid, nid)
                if not url:
                    send_message(cid, "❌ 上传失败"); return
                stype = "face" if txt.startswith("/face_swap") else "cloth"
                SWAP_PENDING[str(uid)] = {"type": stype, "first_url": url}
                tip = "脸" if stype == "face" else "衣服"
                send_message(cid, "📸 已收到目标图 ✅" + chr(10) + chr(10) +
                             "请再发一张参考图（" + tip + "的来源）" + chr(10) +
                             "发送后自动处理" + chr(10) + chr(10) +
                             "取消：/cancel_swap")
            except Exception as e:
                delete_message(cid, nid)
                send_message(cid, friendly_error(e))
            return

        # ===== 管理员发图设置 /start 欢迎图 =====
        if txt.startswith("/set_welcome"):
            if uid not in ADMIN_IDS:
                send_message(cid, "❌ 只有管理员能用"); return
            try:
                with open("/root/AIbot/welcome.jpg", "wb") as f:
                    f.write(ib)
                send_message(cid, "✅ 欢迎图已更新！所有用户发 /start 都会看到新图")
            except Exception as e:
                send_message(cid, "❌ 保存失败：" + str(e)[:100])
            return

        # ===== 管理员发图设置 /start 文案 =====
        if txt.startswith("/set_welcome_text"):
            if uid not in ADMIN_IDS:
                send_message(cid, "❌ 只有管理员能用"); return
            new_text = txt.replace("/set_welcome_text", "", 1).strip()
            if not new_text:
                send_message(cid, "📝 用法：/set_welcome_text 欢迎文案"); return
            try:
                with open("/root/AIbot/welcome_text.txt", "w", encoding="utf-8") as f:
                    f.write(new_text)
                send_message(cid, "✅ 欢迎文案已更新")
            except Exception as e:
                send_message(cid, "❌ 保存失败：" + str(e)[:100])
            return

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
        import os as _os
        _wtext = None
        if _os.path.exists("/root/AIbot/welcome_text.txt"):
            try:
                with open("/root/AIbot/welcome_text.txt", "r", encoding="utf-8") as _f:
                    _wtext = _f.read().strip()
            except: pass
        if not _wtext:
            _wtext = ("🤖 欢迎使用 SAFW AI\n"
                      "👤 " + un + "\n"
                      "💰 余额：$" + ("%.4f" % get_balance(uid)) + " USDT\n\n"
                      "🎨 绘画 · 🎬 视频 · 🎭 换脸\n"
                      "🔍 查询 · 💰 会员 · 👑 特权\n\n"
                      "👇 点击下方按钮开始使用")
        if _os.path.exists("/root/AIbot/welcome.jpg"):
            try:
                with open("/root/AIbot/welcome.jpg", "rb") as _f:
                    _img = _f.read()
                send_photo(cid, _img, caption=_wtext, custom_markup=main_menu())
                return
            except Exception as _e:
                print("欢迎图发送失败:", str(_e)[:80])
        send_message(cid, _wtext, custom_markup=main_menu()); return

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
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
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

    if txt.startswith("/voice ") or txt == "/voice":
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

    if txt.startswith("/help") or txt.startswith("/menu") or txt.startswith("/hh"):
        send_message(cid,
            "📖 SAFW AI 功能菜单\n"
            "━━━━━━━━━━━━━━\n"
            "👤 " + un + "\n"
            "💰 余额：$" + ("%.4f" % get_balance(uid)) + " USDT\n"
            "━━━━━━━━━━━━━━\n"
            "👇 点击下方分类查看详细功能\n"
            "共 22 大类 · 200+ 命令",
            custom_markup=help_main_menu())
        return
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
        nid = send_message(cid, "⏳ 查询中…")
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
            send_message(cid, friendly_error(e))
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
            send_message(cid, friendly_error(e))
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
            send_message(cid, friendly_error(e))
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
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.gen_ppt(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/mindmap"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/mindmap", "", 1).strip()
        if not c: send_message(cid, "🧠 用法：/mindmap 主题"); return
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.gen_character(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/trivia"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/trivia", "", 1).strip()
        if not c: send_message(cid, "🧠 用法：/trivia 主题"); return
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.make_trivia(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/debate"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/debate", "", 1).strip()
        if not c: send_message(cid, "⚖️ 用法：/debate 话题"); return
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.gen_slogan(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/brand"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/brand", "", 1).strip()
        if not c: send_message(cid, "🏷 用法：/brand 行业"); return
        nid = send_message(cid, "⏳ 生成中…")
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
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.gen_hashtag(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/bio"):
        if not check_quota(cid, uid, un, "fun", QUOTA["fun"][0], QUOTA["fun"][1]): return
        import ai_service as _a
        c = txt.replace("/bio", "", 1).strip()
        if not c: send_message(cid, "👤 用法：/bio 身份"); return
        nid = send_message(cid, "⏳ 生成中…")
        r = _a.gen_bio(c); delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/cancel_swap"):
        if SWAP_PENDING.pop(str(uid), None):
            send_message(cid, "❌ 已取消换脸/换衣")
        else:
            send_message(cid, "ℹ️ 没有进行中的操作")
        return

    if txt.startswith("/vip"):
        import database as _d
        info = _d.get_vip_info(uid)
        if info and _d.is_vip(uid):
            exp, plan = info
            send_message(cid, "👑 会员状态" + chr(10) + "━━━━━━━━━━━━" + chr(10) +
                "类型：月卡会员" + chr(10) +
                "到期：" + str(exp) + chr(10) + chr(10) +
                "💎 会员特权：" + chr(10) +
                "• 每天 10 次免费绘画" + chr(10) +
                "• 每天 3 次免费视频" + chr(10) +
                "• 趣味功能无限" + chr(10) +
                "• 每天 3 次免费换脸" + chr(10) +
                "• 每天 5 次免费文档" + chr(10) +
                "• 语音克隆半价")
        else:
            send_message(cid, "👑 会员套餐" + chr(10) + "━━━━━━━━━━━━" + chr(10) +
                "月卡：" + str(VIP_PRICE) + " USDT / 30 天" + chr(10) + chr(10) +
                "💎 会员特权：" + chr(10) +
                "• 每天 10 次免费绘画（普通 1 次）" + chr(10) +
                "• 每天 3 次免费视频（普通 0 次）" + chr(10) +
                "• 趣味功能无限" + chr(10) +
                "• 每天 3 次免费换脸（普通 $0.10）" + chr(10) +
                "• 每天 5 次免费文档" + chr(10) +
                "• 语音克隆半价" + chr(10) + chr(10) +
                "💰 开通方式：联系客服 @qishe77" + chr(10) +
                "或发 /recharge 充值后开通")
        return

    if txt.startswith("/buy_vip"):
        import database as _d, random, time
        # 检查是否已是会员
        if _d.is_vip(uid):
            info = _d.get_vip_info(uid)
            exp = info[0] if info else "?"
            send_message(cid, "👑 你已是会员，有效期至：" + str(exp) + chr(10) + "续费可叠加天数")
        # 生成订单号
        order_no = "VIP" + str(random.randint(100000, 999999))
        # 随机小数：0.01 ~ 0.10
        delta = round(random.uniform(0.01, 0.10), 4)
        total_price = round(VIP_PRICE + delta, 4)
        expire_time = _d.create_vip_order(order_no, uid, total_price, VIP_DAYS)
        msg = ("👑 会员订单" + chr(10) + "━━━━━━━━━━━━" + chr(10) +
            "订单号：" + order_no + chr(10) +
            "金额：" + ("%.4f" % total_price) + " USDT (TRC20)" + chr(10) +
            "时长：" + str(VIP_DAYS) + " 天" + chr(10) +
            "⏰ 10 分钟内有效（" + expire_time + " 前）" + chr(10) + chr(10) +
            "💳 转账地址：" + chr(10) + TRON_WALLET + chr(10) + chr(10) +
            "⚠️ 必须精确转账 " + ("%.4f" % total_price) + " USDT" + chr(10) +
            "（含随机小数，保证唯一匹配）" + chr(10) + chr(10) +
            "✅ 转账后 1-3 分钟自动开通")
        send_message(cid, msg)
        return

    if txt.startswith("/set_ad"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        import json as _j4, os as _o4
        ads_file = "/root/AIbot/ads.json"
        ads = {}
        if _o4.path.exists(ads_file):
            try:
                with open(ads_file, "r", encoding="utf-8") as f:
                    ads = _j4.load(f)
            except: ads = {}
        body = txt.replace("/set_ad", "", 1).strip()
        if not body or body == "off":
            ads["enabled"] = False
            with open(ads_file, "w", encoding="utf-8") as f:
                _j4.dump(ads, f, ensure_ascii=False)
            send_message(cid, "✅ 广告位已关闭"); return
        # 格式：/set_ad 按钮文字 || 广告内容 || 链接文字 || 链接URL
        parts = [p.strip() for p in body.split("||")]
        ads["enabled"] = True
        ads["btn_text"] = parts[0] if len(parts) > 0 else "📢 广告位招租"
        ads["content"] = parts[1] if len(parts) > 1 else "广告位招租"
        ads["link_text"] = parts[2] if len(parts) > 2 else "💬 联系客服"
        ads["link_url"] = parts[3] if len(parts) > 3 else "https://sfw.bar/qishe77"
        with open(ads_file, "w", encoding="utf-8") as f:
            _j4.dump(ads, f, ensure_ascii=False)
        send_message(cid, "✅ 广告位已更新\n按钮：" + ads["btn_text"] + "\n内容：" + ads["content"][:50])
        return

    # ===== 画风学习 =====
    if txt.startswith("/hot_style") or txt.startswith("/hotstyle"):
        import ai_service as _a
        items = _a.get_hot_prompts(10)
        if not items:
            send_message(cid, "📭 暂无热门画风，先画几张吧"); return
        msg = "🔥 热门画风 TOP10\n━━━━━━━━━━━━\n"
        for i, (k, v) in enumerate(items, 1):
            msg += f"{i}. {k[:40]} （{v.get('score',0)}分·{v.get('uses',0)}次）\n"
        msg += "\n💡 直接复制画风描述发给 /draw 即可"
        send_long_message(cid, msg); return

    if txt.startswith("/like"):
        import ai_service as _a
        c = txt.replace("/like", "", 1).strip()
        if not c: send_message(cid, "👍 用法：/like 画风描述"); return
        _a.record_prompt(c, uid, True)
        send_message(cid, "👍 已记录"); return

    # ===== 文档处理 =====
    if txt.startswith("/doc"):
        send_message(cid, "📄 请直接发送 PDF/Word/txt 文件（带 /doc 描述）"); return

    # ===== 深度研究 =====
    if txt.startswith("/research"):
        import ai_service as _a
        c = txt.replace("/research", "", 1).strip()
        if not c: send_message(cid, "🔍 用法：/research 话题"); return
        if not check_quota(cid, uid, un, "research", QUOTA.get("research", (0, 0.20))[0], QUOTA.get("research", (0, 0.20))[1]): return
        nid = send_message(cid, "🔍 深度研究中... 约 1-2 分钟")
        r = _a.deep_research(c)
        delete_message(cid, nid)
        send_long_message(cid, "🔍 研究报告\n━━━━━━━━━━━━\n" + r); return

    # ===== 数据分析 =====
    if txt.startswith("/analyze"):
        import ai_service as _a
        c = txt.replace("/analyze", "", 1).strip()
        if not c: send_message(cid, "📊 用法：/analyze CSV数据"); return
        nid = send_message(cid, "📊 分析中...")
        r = _a.analyze_data(c)
        delete_message(cid, nid)
        send_long_message(cid, "📊 数据分析\n━━━━━━━━━━━━\n" + r); return

    # ===== 工具类 =====
    if txt.startswith("/pwd"):
        import ai_service as _a
        c = txt.replace("/pwd", "", 1).strip()
        n = int(c) if c.isdigit() else 16
        send_message(cid, "🔐 密码：" + _a.gen_password(n)); return

    if txt.startswith("/b64_encode") or txt.startswith("/b64e"):
        import ai_service as _a
        c = txt.replace("/b64_encode", "").replace("/b64e", "").strip()
        if not c: send_message(cid, "🔤 用法：/b64e 文字"); return
        send_message(cid, "🔤 " + _a.b64_encode(c)); return

    if txt.startswith("/b64_decode") or txt.startswith("/b64d"):
        import ai_service as _a
        c = txt.replace("/b64_decode", "").replace("/b64d", "").strip()
        if not c: send_message(cid, "🔤 用法：/b64d 密文"); return
        send_message(cid, "🔤 " + _a.b64_decode(c)); return

    if txt.startswith("/hash"):
        import ai_service as _a
        p = txt.replace("/hash", "", 1).strip().split()
        if len(p) < 2: send_message(cid, "🔐 用法：/hash sha256 文字"); return
        send_message(cid, "🔐 " + _a.hash_text(" ".join(p[1:]), p[0])); return

    if txt.startswith("/age"):
        import ai_service as _a
        c = txt.replace("/age", "", 1).strip()
        if not c: send_message(cid, "🎂 用法：/age 1995-06-15"); return
        send_message(cid, _a.age_calc(c)); return

    # ===== 游戏/趣味 =====
    if txt.startswith("/rps"):
        import ai_service as _a
        c = txt.replace("/rps", "", 1).strip()
        if not c: send_message(cid, "✊ 用法：/rps 石头"); return
        send_message(cid, "🎮 " + _a.game_rps(c)); return

    if txt.startswith("/20q"):
        import ai_service as _a
        send_message(cid, _a.game_20q_start()); return

    if txt.startswith("/guess_start"):
        import ai_service as _a
        import json as _j, os as _o
        n = _a.game_guess_start()
        p = "/root/AIbot/guess_answers.json"
        d = {}
        if _o.path.exists(p):
            try:
                with open(p) as f: d = _j.load(f)
            except: d = {}
        d[str(uid)] = n
        with open(p, "w") as f: _j.dump(d, f)
        send_message(cid, "🔢 猜一个 1-100 的数字，发 /guess 数字"); return

    if txt.startswith("/guess"):
        import json as _j, os as _o
        c = txt.replace("/guess", "", 1).strip()
        if not c.isdigit(): send_message(cid, "🔢 用法：/guess 50"); return
        p = "/root/AIbot/guess_answers.json"
        d = {}
        if _o.path.exists(p):
            try:
                with open(p) as f: d = _j.load(f)
            except: d = {}
        n = d.get(str(uid))
        if not n: send_message(cid, "❌ 先发 /guess_start"); return
        g = int(c)
        if g == n:
            d.pop(str(uid), None)
            with open(p, "w") as f: _j.dump(d, f)
            send_message(cid, "🎉 猜对了！答案就是 " + str(n))
        elif g < n: send_message(cid, "📈 太小了")
        else: send_message(cid, "📉 太大了")
        return

    # ===== 生活/职场 =====
    if txt.startswith("/mood"):
        import ai_service as _a
        c = txt.replace("/mood", "", 1).strip()
        if not c: send_message(cid, "💭 用法：/mood 今天有点累"); return
        send_message(cid, "💭 " + _a.life_mood(c)); return

    if txt.startswith("/water"):
        import ai_service as _a
        send_message(cid, _a.life_water()); return

    if txt.startswith("/sleep"):
        import ai_service as _a
        send_message(cid, "😴 " + _a.life_sleep()); return

    if txt.startswith("/negotiate"):
        import ai_service as _a
        c = txt.replace("/negotiate", "", 1).strip()
        if not c: send_message(cid, "💼 用法：/negotiate 涨薪"); return
        send_message(cid, "💼 " + _a.work_negotiate(c)); return

    if txt.startswith("/apology"):
        import ai_service as _a
        c = txt.replace("/apology", "", 1).strip()
        if not c: send_message(cid, "🙏 用法：/apology 场景"); return
        send_message(cid, "🙏 " + _a.work_apology(c)); return

    if txt.startswith("/complain"):
        import ai_service as _a
        c = txt.replace("/complain", "", 1).strip()
        if not c: send_message(cid, "📢 用法：/complain 问题"); return
        send_message(cid, "📢 " + _a.work_complain(c)); return

    # ===== 儿童 =====
    if txt.startswith("/bedtime"):
        import ai_service as _a
        c = txt.replace("/bedtime", "", 1).strip() or "小熊"
        nid = send_message(cid, "🌙 讲故事中...")
        r = _a.kid_bedtime(c)
        delete_message(cid, nid)
        send_long_message(cid, "🌙 睡前故事\n━━━━━━━━━━━━\n" + r); return

    if txt.startswith("/homework"):
        import ai_service as _a
        c = txt.replace("/homework", "", 1).strip()
        if not c: send_message(cid, "📚 用法：/homework 数学题"); return
        send_message(cid, "📚 " + _a.kid_homework(c)); return

    # ===== 100% 免费功能 =====
    if txt.startswith("/crypto") or txt.startswith("/btc"):
        import ai_service as _a
        coin = "bitcoin"
        c = txt.replace("/crypto", "").replace("/btc", "").strip().lower()
        if c: coin = c
        send_message(cid, _a.free_crypto(coin)); return

    if txt.startswith("/eth"):
        import ai_service as _a
        send_message(cid, _a.free_crypto("ethereum")); return

    if txt.startswith("/weather2") or txt.startswith("/w"):
        import ai_service as _a
        c = txt.replace("/weather2", "").replace("/w", "").strip()
        if not c: send_message(cid, "🌤 用法：/w 北京"); return
        send_message(cid, _a.free_weather(c)); return

    if txt.startswith("/trans "):
        import ai_service as _a
        c = txt.replace("/trans", "", 1).strip()
        parts = c.split(" ", 1)
        if len(parts) < 2: send_message(cid, "🌐 用法：/trans en 你好"); return
        send_message(cid, _a.free_translate(parts[1], parts[0])); return

    if txt.startswith("/anime"):
        import ai_service as _a
        c = txt.replace("/anime", "", 1).strip()
        if not c: send_message(cid, "🎬 用法：/anime 火影"); return
        nid = send_message(cid, "🔍 搜索中...")
        r = _a.free_anime(c)
        delete_message(cid, nid)
        send_message(cid, r); return

    if txt.startswith("/freegame"):
        import ai_service as _a
        nid = send_message(cid, "⏳ 查询中…")
        r = _a.free_game()
        delete_message(cid, nid)
        send_message(cid, r); return

    if txt.startswith("/dog"):
        import ai_service as _a
        img = _a.free_dog()
        if img: send_photo(cid, img, caption="🐶 随机狗图")
        else: send_message(cid, "❌ 获取失败")
        return

    if txt.startswith("/cat"):
        import ai_service as _a
        img = _a.free_cat()
        if img: send_photo(cid, img, caption="🐱 随机猫图")
        else: send_message(cid, "❌ 获取失败")
        return

    if txt.startswith("/fact"):
        import ai_service as _a
        send_message(cid, _a.free_fact()); return

    if txt.startswith("/wiki"):
        import ai_service as _a
        c = txt.replace("/wiki", "", 1).strip()
        if not c: send_message(cid, "📖 用法：/wiki 人工智能"); return
        nid = send_message(cid, "⏳ 查询中…")
        r = _a.free_wiki(c)
        delete_message(cid, nid)
        send_message(cid, r); return

    if txt.startswith("/news") or txt.startswith("/hn"):
        import ai_service as _a
        nid = send_message(cid, "📰 获取新闻...")
        r = _a.free_hn()
        delete_message(cid, nid)
        send_message(cid, r); return

    if txt.startswith("/uuid"):
        import ai_service as _a
        send_message(cid, _a.free_uuid()); return

    if txt.startswith("/iplookup") or txt.startswith("/ipwho"):
        import ai_service as _a
        c = txt.replace("/iplookup", "").replace("/ipwho", "").strip()
        if not c: send_message(cid, "🌐 用法：/iplookup google.com"); return
        send_message(cid, _a.free_ip(c)); return

    if txt.startswith("/fx"):
        import ai_service as _a
        c = txt.replace("/fx", "", 1).strip().split()
        if len(c) < 2: send_message(cid, "💱 用法：/fx USD CNY"); return
        send_message(cid, _a.free_fx(c[0], c[1])); return

    if txt.startswith("/country"):
        import ai_service as _a
        c = txt.replace("/country", "", 1).strip()
        if not c: send_message(cid, "🌍 用法：/country China"); return
        send_message(cid, _a.free_country(c)); return

    if txt.startswith("/short "):
        import ai_service as _a
        c = txt.replace("/short", "", 1).strip()
        if not c: send_message(cid, "🔗 用法：/short https://xxx.com"); return
        send_message(cid, _a.free_short(c)); return

    if txt.startswith("/roman"):
        import ai_service as _a
        c = txt.replace("/roman", "", 1).strip()
        if not c: send_message(cid, "🏛 用法：/roman 2026"); return
        send_message(cid, _a.local_roman(c)); return

    if txt.startswith("/random"):
        import ai_service as _a
        c = txt.replace("/random", "", 1).strip().split()
        if len(c) < 2: send_message(cid, "🎲 用法：/random 1 100"); return
        send_message(cid, _a.local_random(c[0], c[1])); return

    if txt.startswith("/pick"):
        import ai_service as _a
        c = txt.replace("/pick", "", 1).strip()
        if not c: send_message(cid, "🎯 用法：/pick A,B,C"); return
        send_message(cid, _a.local_pick(c)); return

    if txt.startswith("/count"):
        import ai_service as _a
        c = txt.replace("/count", "", 1).strip()
        if not c: send_message(cid, "📊 用法：/count 文字"); return
        send_message(cid, _a.local_count(c)); return

    if txt.startswith("/reverse"):
        import ai_service as _a
        c = txt.replace("/reverse", "", 1).strip()
        if not c: send_message(cid, "🔄 用法：/reverse 你好"); return
        send_message(cid, _a.local_reverse(c)); return

    if txt.startswith("/color"):
        import ai_service as _a
        c = txt.replace("/color", "", 1).strip()
        if not c: send_message(cid, "🎨 用法：/color #FF0000"); return
        send_message(cid, _a.local_color(c)); return

    if txt.startswith("/license_info"):
        import license as _lic
        send_message(cid, _lic.license_info()); return

    if txt.startswith("/gen_license"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        c = txt.replace("/gen_license", "", 1).strip().split()
        if len(c) < 1:
            send_message(cid, "📝 用法：/gen_license 客户名 [天数] [套餐]"); return
        owner = c[0]
        days = int(c[1]) if len(c) > 1 else 30
        plan = c[2] if len(c) > 2 else "basic"
        import license as _lic
        lic = _lic.generate_license(owner, days, plan)
        send_message(cid, "✅ 授权已生成\n客户：" + lic["owner"] + "\n到期：" + lic["expire_at"] + "\n签名：" + lic["sign"]); return

    if txt.startswith("/novel") and not txt.startswith("/novels"):
        import ai_service as _a
        c = txt.replace("/novel", "", 1).strip()
        if not c:
            send_message(cid, "📖 用法：/novel 主题\n例如：/novel 都市修仙")
            return
        if not check_quota(cid, uid, un, "novel", QUOTA.get("novel", (3, 0.05))[0], QUOTA.get("novel", (3, 0.05))[1]):
            return
        nid = send_message(cid, "📖 正在构思新书，约 60 秒...")
        outline, ch1, err = _a.novel_start_v2(c, uid)
        delete_message(cid, nid)
        if err or not ch1:
            send_message(cid, "❌ " + str(err)); return
        import json as _j, os as _o, datetime
        bf = "/root/AIbot/novels.json"
        books = {}
        if _o.path.exists(bf):
            try:
                with open(bf, "r", encoding="utf-8") as f: books = _j.load(f)
            except: books = {}
        # 生成第1章摘要
        s1 = _a.novel_chapter_summary(ch1)
        books[str(uid)] = {
            "topic": c, "outline": outline, "chapters": 1,
            "summaries": [s1],
            "volume_summary": "",
            "last_chapter_tail": ch1[-1500:],
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(bf, "w", encoding="utf-8") as f: _j.dump(books, f, ensure_ascii=False)
        from safew_api import send_document
        title = "新书"
        for line in outline.split("\n"):
            if "书名" in line: title = line.split("：")[-1].strip(); break
        content = title + "\n" + "=" * 40 + "\n\n【大纲】\n" + outline + "\n\n" + ch1 + "\n\n" + "=" * 40 + "\nSAFW AI 出品 · @qishe77"
        fname = title.replace(" ", "_")[:30] + "_第1章.txt"
        ok = send_document(cid, content.encode("utf-8"), filename=fname, caption="📖 《" + title + "》第1章\n\n📌 发 /next 写下一章")
        if not ok:
            send_long_message(cid, content[:3000])
        return

    if txt.startswith("/next"):
        import ai_service as _a
        import json as _j, os as _o
        bf = "/root/AIbot/novels.json"
        books = {}
        if _o.path.exists(bf):
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    books = _j.load(f)
            except: books = {}
        book = books.get(str(uid))
        if not book:
            send_message(cid, "❌ 你还没开始写书，先发 /novel 主题"); return
        if not check_quota(cid, uid, un, "novel", QUOTA.get("novel", (3, 0.05))[0], QUOTA.get("novel", (3, 0.05))[1]):
            return
        ch_num = book.get("chapters", 1) + 1
        nid = send_message(cid, "📖 正在写第 " + str(ch_num) + " 章，约 60 秒...")
        # 构造长期记忆
        summaries = book.get("summaries", [])
        recent = summaries[-5:] if summaries else []
        volume = book.get("volume_summary", "") or ""
        tail = book.get("last_chapter_tail", "")[:1000]
        context = ""
        if volume: context += "【前卷总结】\n" + volume + "\n\n"
        if recent: context += "【近期剧情】\n" + "\n".join(recent) + "\n\n"
        if tail: context += "【上一章结尾】\n" + tail
        try:
            new_ch, err = _a.novel_next_v2(book.get("outline", ""), context, ch_num, uid)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ 生成失败：" + str(e)[:100])
            return
        delete_message(cid, nid)
        if err or not new_ch:
            send_message(cid, "❌ " + str(err or "生成失败")); return
        # 摘要
        try:
            new_sum = _a.novel_chapter_summary(new_ch)
        except: new_sum = ""
        book["chapters"] = ch_num
        if new_sum:
            book.setdefault("summaries", []).append(new_sum)
        book["last_chapter_tail"] = new_ch[-1500:]
        # 每 10 章更新卷摘要
        if ch_num % 10 == 0:
            try:
                recent_10 = book["summaries"][-10:]
                vol_sum = _a.novel_volume_summary("\n".join(recent_10))
                if vol_sum:
                    book["volume_summary"] = ((book.get("volume_summary") or "") + "\n" + vol_sum)[-1500:]
            except: pass
        books[str(uid)] = book
        with open(bf, "w", encoding="utf-8") as f:
            _j.dump(books, f, ensure_ascii=False)
        # 发文件
        from safew_api import send_document
        title = "新书"
        for line in book.get("outline", "").split("\n"):
            if "书名" in line: title = line.split("：")[-1].strip(); break
        content = title + "\n" + "=" * 40 + "\n\n" + new_ch + "\n\n" + "=" * 40 + "\nSAFW AI 出品"
        fname = title.replace(" ", "_")[:30] + "_第" + str(ch_num) + "章.txt"
        ok = send_document(cid, content.encode("utf-8"), filename=fname,
                           caption="📖 《" + title + "》第" + str(ch_num) + "章\n\n📌 /next 继续")
        if not ok:
            send_long_message(cid, content[:3000])
        return

    if txt.startswith("/book"):
        import json as _j, os as _o
        bf = "/root/AIbot/novels.json"
        books = {}
        if _o.path.exists(bf):
            try:
                with open(bf, "r", encoding="utf-8") as f: books = _j.load(f)
            except: books = {}
        book = books.get(str(uid))
        if not book:
            send_message(cid, "📚 你还没开始写书"); return
        title = "新书"
        for line in book["outline"].split("\n"):
            if "书名" in line: title = line.split("：")[-1].strip(); break
        send_message(cid, "📚 当前进度\n━━━━━━━━━━━━\n📖 " + title + "\n✍️ 已写：" + str(book["chapters"]) + " 章\n🕐 开始：" + book["created_at"] + "\n\n📌 /next 写下一章")
        return

    if txt.startswith("/endbook"):
        import json as _j, os as _o
        bf = "/root/AIbot/novels.json"
        books = {}
        if _o.path.exists(bf):
            try:
                with open(bf, "r", encoding="utf-8") as f: books = _j.load(f)
            except: books = {}
        books.pop(str(uid), None)
        with open(bf, "w", encoding="utf-8") as f: _j.dump(books, f, ensure_ascii=False)
        send_message(cid, "✅ 已结束本书，发 /novel 主题开始新书")
        return

    # ===== 命令别名 =====
    if txt.startswith("/hh"):
        txt = "/help" + txt[3:]

    if txt.startswith("/search") or txt.startswith("/s "):
        import search_service as _ss
        q = txt.replace("/search", "").replace("/s ", "").strip()
        if not q:
            send_message(cid, "🔍 用法：/search 关键词\n例如：/search 2026年AI行业趋势")
            return
        if not check_quota(cid, uid, un, "search", QUOTA.get("search", (5, 0.02))[0], QUOTA.get("search", (5, 0.02))[1]):
            return
        nid = send_message(cid, "🔍 搜索中，约 5-10 秒...")
        try:
            r = _ss.search_and_answer(q)
            delete_message(cid, nid)
            send_long_message(cid, r)
        except Exception as e:
            delete_message(cid, nid)
            send_message(cid, "❌ 搜索失败：" + str(e)[:80])
        return

    if txt.startswith("/pref"):
        import database as _d
        c = txt.replace("/pref", "", 1).strip().lower()
        p = _d.get_user_prefs(uid)
        if not c:
            msg = "⚙️ 个人偏好设置\n━━━━━━━━━━━━━\n"
            msg += "风格：" + p.get("style", "normal") + "\n"
            msg += "语言：" + p.get("lang", "zh") + "\n"
            msg += "回复长度：" + p.get("reply_length", "normal") + "\n"
            msg += "语音：(" + ("开" if p.get("voice_on") else "关") + ")\n"
            msg += "━━━━━━━━━━━━━\n"
            msg += "用法：\n"
            msg += "/pref style 幽默/严谨/简洁\n"
            msg += "/pref length 短/正常/详细\n"
            send_message(cid, msg); return
        parts = c.split(" ", 1)
        if len(parts) < 2:
            send_message(cid, "📝 用法：/pref style 幽默"); return
        key, value = parts[0], parts[1]
        key_map = {"style": "style", "风格": "style",
                   "length": "reply_length", "长度": "reply_length",
                   "lang": "lang", "语言": "lang"}
        k = key_map.get(key)
        if k:
            _d.set_user_pref(uid, k, value)
            send_message(cid, "✅ 已设置 " + key + " = " + value)
        else:
            send_message(cid, "❌ 未知选项：" + key)
        return

    if txt.startswith("/remember"):
        import database as _d
        c = txt.replace("/remember", "", 1).strip()
        if not c:
            send_message(cid, "📝 用法：/remember 喜欢喝咖啡\n下次聊天我会记住")
            return
        # 格式：/remember 键 值 或 /remember 内容
        parts = c.split(" ", 1)
        if len(parts) == 2:
            key, value = parts[0], parts[1]
        else:
            key, value = "note_" + str(int(__import__("time").time())), c
        _d.memory_add(uid, key, value, "user")
        send_message(cid, "✅ 已记住：" + value[:50])
        return

    if txt.startswith("/mymemory") or txt.startswith("/记忆"):
        import database as _d
        rows = _d.memory_get(uid, 30)
        if not rows:
            send_message(cid, "📭 我还不了解你，发 /remember 内容 告诉我吧")
            return
        msg = "🧠 我记住的关于你的事\n━━━━━━━━━━━━━\n"
        for k, v, cat in rows:
            msg += "• " + str(v)[:80] + "\n"
        msg += "━━━━━━━━━━━━━\n"
        msg += "共 " + str(len(rows)) + " 条记忆\n"
        msg += "清空：/forget"
        send_long_message(cid, msg)
        return

    if txt.startswith("/forget"):
        import database as _d
        _d.memory_clear(uid)
        send_message(cid, "🗑 已清空所有记忆")
        return

    if txt.startswith("/profile"):
        import database as _d
        p = _d.profile_get(uid)
        msg = "👤 你的档案\n━━━━━━━━━━━━━\n"
        msg += "姓名：" + (p.get("name") or "未设置") + "\n"
        msg += "生日：" + (p.get("birthday") or "未设置") + "\n"
        msg += "城市：" + (p.get("city") or "未设置") + "\n"
        msg += "职业：" + (p.get("job") or "未设置") + "\n"
        msg += "爱好：" + (p.get("hobby") or "未设置") + "\n"
        msg += "━━━━━━━━━━━━━\n"
        msg += "累计对话：" + str(p.get("total_msgs", 0)) + " 次\n"
        msg += "\n设置：/setname 张三"
        send_message(cid, msg)
        return

    if txt.startswith("/setname"):
        import database as _d
        name = txt.replace("/setname", "", 1).strip()
        if not name: send_message(cid, "📝 用法：/setname 张三"); return
        _d.profile_update(uid, name=name)
        send_message(cid, "✅ 已记住你的名字：" + name)
        return

    if txt.startswith("/setbirthday"):
        import database as _d
        bd = txt.replace("/setbirthday", "", 1).strip()
        if not bd: send_message(cid, "📝 用法：/setbirthday 1995-06-15"); return
        _d.profile_update(uid, birthday=bd)
        send_message(cid, "✅ 已记住你的生日：" + bd + "\n生日当天我会祝福你 🎂")
        return

    # ===== 智力增强命令 =====
    if txt.startswith("/ocr"):
        send_message(cid, "📷 请发一张带文字的图片（自动提取文字）")
        return

    if txt.startswith("/deep"):
        import ai_service as _a
        c = txt.replace("/deep", "", 1).strip()
        if not c: send_message(cid, "🔗 用法：/deep 网页链接"); return
        nid = send_message(cid, "🔗 深度解读中...")
        r = _a.link_deep_read(c)
        delete_message(cid, nid)
        send_long_message(cid, r); return

    if txt.startswith("/ask"):
        import ai_service as _a
        c = txt.replace("/ask", "", 1).strip()
        if not c: send_message(cid, "📄 用法：先发文档，再发 /ask 问题"); return
        nid = send_message(cid, "🔍 查询文档中...")
        r = _a.doc_ask(uid, c)
        delete_message(cid, nid)
        send_long_message(cid, "📄 " + r); return

    if txt.startswith("/ad_list"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        import json as _j, os as _o
        if not _o.path.exists("/root/AIbot/ads.json"):
            send_message(cid, "📭 暂无广告"); return
        with open("/root/AIbot/ads.json", "r", encoding="utf-8") as f:
            ads = _j.load(f)
        lst = ads.get("ads_list", [])
        if not lst:
            send_message(cid, "📭 暂无广告"); return
        msg = "📢 广告列表\n━━━━━━━━━━━━━\n"
        for a in lst:
            msg += "ID：" + a.get("id", "") + "\n"
            msg += "按钮：" + a.get("btn_text", "") + "\n"
            msg += "点击：" + str(a.get("clicks", 0)) + " 次\n"
            msg += "状态：" + ("✅ 开" if a.get("enabled") else "❌ 关") + "\n\n"
        send_long_message(cid, msg); return

    if txt.startswith("/ad_stats"):
        if uid not in ADMIN_IDS:
            send_message(cid, "❌ 只有管理员能用"); return
        import json as _j, os as _o
        if not _o.path.exists("/root/AIbot/ads.json"):
            send_message(cid, "📭 暂无广告"); return
        with open("/root/AIbot/ads.json", "r", encoding="utf-8") as f:
            ads = _j.load(f)
        total = sum(a.get("clicks", 0) for a in ads.get("ads_list", []))
        send_message(cid, "📊 广告统计\n━━━━━━━━━━━━━\n总点击：" + str(total) + " 次"); return

    if txt.startswith("/voice_drama") or txt.startswith("/配音"):
        import voice_drama as _vd
        c = txt.replace("/voice_drama", "").replace("/配音", "").strip()
        if not c:
            send_message(cid,
                "🎙 多角色配音\n"
                "━━━━━━━━━━━━━\n"
                "格式：每行「角色：台词」\n\n"
                "示例：\n"
                "/voice_drama\n"
                "旁白：很久以前有座山\n"
                "小明：我要去冒险！\n"
                "妈妈：路上小心")
            return
        if not check_quota(cid, uid, un, "voice_drama", QUOTA.get("voice_drama", (2, 0.20))[0], QUOTA.get("voice_drama", (2, 0.20))[1]):
            return
        nid = send_message(cid, "🎙 正在配音，约 30-60 秒...")
        audio, err = _vd.make_voice_drama(c, uid)
        delete_message(cid, nid)
        if audio:
            from safew_api import send_voice
            send_voice(cid, audio)
        else:
            send_message(cid, "❌ " + str(err))
        return

    if txt.startswith("/comic"):
        import comic_service as _cs
        c = txt.replace("/comic", "", 1).strip()
        if not c:
            send_message(cid,
                "🎨 AI 漫画生成\n"
                "━━━━━━━━━━━━━\n"
                "用法：/comic 故事描述\n\n"
                "示例：\n"
                "/comic 一只小猫在花园玩，突然下雨，躲进蘑菇下，最后彩虹出现")
            return
        if not check_quota(cid, uid, un, "comic", QUOTA.get("comic", (1, 0.30))[0], QUOTA.get("comic", (1, 0.30))[1]):
            return
        nid = send_message(cid, "🎨 正在画 4 格漫画，约 90-120 秒...")
        img, err = _cs.generate_comic(c)
        delete_message(cid, nid)
        if img:
            send_photo(cid, img, caption="🎨 AI 漫画 · " + BOT_NAME)
        else:
            send_message(cid, "❌ " + str(err))
        return

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

    nid = send_message(cid, "⏳ 正在思考…")
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
        # ===== AI 意图识别：用户说什么自动调用对应功能 =====
        _intent_done = False
        if _task != "reason" and len(txt) > 2:
            try:
                import intent_service as _is
                _intent_data = _is.detect_intent_cached(txt)
                if _intent_data.get("intent") != "chat":
                    _result = _is.execute_intent(_intent_data)
                    if _result:
                        if isinstance(_result, tuple) and _result[0] == "__IMAGE__":
                            delete_message(cid, nid)
                            if _result[1]:
                                send_photo(cid, _result[1], caption="🎨 " + BOT_NAME)
                            else:
                                send_message(cid, "❌ 生成失败")
                            return
                        reply = _result
                        _intent_done = True
                        print("[意图] " + str(_intent_data))
            except Exception as _e:
                print("[意图] " + str(_e)[:80])
        if not _intent_done:
            # 自动注入用户记忆
            try:
                import database as _d
                _mem = _d.memory_get(uid, 10)
                _prof = _d.profile_get(uid)
                if _mem or _prof:
                    _ctx = ""
                    if _prof.get("name"): _ctx += "用户叫" + _prof["name"] + "。"
                    if _prof.get("city"): _ctx += "住在" + _prof["city"] + "。"
                    if _mem:
                        _ctx += "用户说过：" + "；".join([str(v)[:30] for k, v, c in _mem[:5]])
                    reply = _ai.smart_chat(_ctx + "\n用户说：" + txt, uid=uid, task_type=_task)
                else:
                    reply = _ai.smart_chat(txt, uid=uid, task_type=_task)
            except:
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
