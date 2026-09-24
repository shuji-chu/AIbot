# -*- coding: utf-8 -*-
"""AI 意图识别：用户自然语言 → 自动调用对应功能"""
import json, re


# 意图映射表
INTENT_MAP = {
    # 天气
    "weather": {"func": "free_weather", "params": ["city"], "desc": "查询城市天气"},
    # 加密货币
    "crypto": {"func": "free_crypto", "params": ["coin"], "desc": "查加密货币价格"},
    # 画图
    "draw": {"func": "gen_image", "params": ["prompt"], "desc": "画图"},
    # 翻译
    "translate": {"func": "translate_text", "params": ["lang", "text"], "desc": "翻译"},
    # 搜索
    "search": {"func": "search_and_answer", "params": ["query"], "desc": "搜索信息"},
    # 维基
    "wiki": {"func": "free_wiki", "params": ["keyword"], "desc": "百科查询"},
    # 国家
    "country": {"func": "free_country", "params": ["name"], "desc": "国家信息"},
    # 汇率
    "fx": {"func": "free_fx", "params": ["from", "to"], "desc": "汇率查询"},
    # IP
    "ip": {"func": "free_ip", "params": ["ip"], "desc": "IP查询"},
    # 动漫
    "anime": {"func": "free_anime", "params": ["keyword"], "desc": "动漫查询"},
    # 笑话
    "joke": {"func": "free_fact", "params": [], "desc": "冷知识"},
    # 密码
    "password": {"func": "gen_password", "params": ["length"], "desc": "生成密码"},
    # 年龄
    "age": {"func": "age_calc", "params": ["birthday"], "desc": "年龄计算"},
    # 哈希
    "hash": {"func": "hash_text", "params": ["text", "algo"], "desc": "哈希计算"},
    # 算命
    "fortune": {"func": "fortune_telling", "params": ["birthday", "question"], "desc": "算命"},
    # 解梦
    "dream": {"func": "dream_analysis", "params": ["dream"], "desc": "解梦"},
    # 塔罗
    "tarot": {"func": "tarot_reading", "params": ["question"], "desc": "塔罗牌"},
    # 星座
    "horoscope": {"func": "horoscope", "params": ["sign"], "desc": "星座运势"},
    # 情话
    "love": {"func": "love_words", "params": [], "desc": "情话"},
    # 藏头诗
    "poem": {"func": "acrostic_poem", "params": ["word"], "desc": "藏头诗"},
    # 起名
    "name": {"func": "ai_name", "params": ["kind"], "desc": "起名"},
    # 解压
    "roast": {"func": "roast_words", "params": ["target"], "desc": "吐槽"},
    # 脑筋急转弯
    "riddle": {"func": "brain_riddle", "params": [], "desc": "脑筋急转弯"},
    # 数学
    "math": {"func": "solve_math", "params": ["problem"], "desc": "数学解题"},
    # 菜谱
    "recipe": {"func": "get_recipe", "params": ["ingredient"], "desc": "菜谱"},
    # 旅游
    "travel": {"func": "gen_travel", "params": ["city_days"], "desc": "旅游攻略"},
    # 减肥
    "diet": {"func": "gen_diet", "params": ["goal"], "desc": "饮食计划"},
    # 健身
    "workout": {"func": "gen_workout", "params": ["body"], "desc": "健身动作"},
    # 购物
    "shopping": {"func": "gen_shopping", "params": ["need"], "desc": "购物推荐"},
    # 邮件
    "email": {"func": "gen_email", "params": ["topic"], "desc": "邮件"},
    # 简历
    "resume": {"func": "gen_resume", "params": ["exp"], "desc": "简历"},
    # 面试
    "interview": {"func": "gen_interview", "params": ["job"], "desc": "面试题"},
    # 文案
    "write": {"func": "write_copy", "params": ["topic"], "desc": "文案"},
    # 标题
    "title": {"func": "generate_titles", "params": ["content"], "desc": "标题"},
    # 总结
    "summarize": {"func": "summarize_text", "params": ["text"], "desc": "总结"},
    # 润色
    "polish": {"func": "polish_text", "params": ["text"], "desc": "润色"},
    # 情感分析
    "emotion": {"func": "analyze_emotion", "params": ["text"], "desc": "情感分析"},
    # 周报
    "weekly": {"func": "generate_weekly", "params": ["report"], "desc": "周报"},
    # 代码
    "code": {"func": "explain_code", "params": ["code"], "desc": "代码解释"},
    # SQL
    "sql": {"func": "generate_sql", "params": ["requirement"], "desc": "SQL"},
    # 正则
    "regex": {"func": "generate_regex", "params": ["requirement"], "desc": "正则"},
    # 短链接
    "short": {"func": "free_short", "params": ["url"], "desc": "短链接"},
    # 搜索新闻
    "news": {"func": "search_news", "params": ["query"], "desc": "搜索新闻"},
}


INTENT_SYSTEM_PROMPT = """你是意图识别助手。分析用户消息，判断他想做什么，提取参数。

可选意图（必须从下面选一个，否则返回 "chat"）：
""" + "\\n".join([f"- {k}: {v['desc']}（参数：{v['params']}）" for k, v in INTENT_MAP.items()]) + """

输出严格的 JSON 格式：
{"intent": "意图名", "params": {"参数名": "参数值"}}

规则：
1. 天气：用户问某地天气 → {"intent":"weather","params":{"city":"北京"}}
2. 画图：用户说"画XX"、"帮我画XX" → {"intent":"draw","params":{"prompt":"一只猫"}}
3. 搜索：用户问"XX是什么"、"最新XX" → {"intent":"search","params":{"query":"XX"}}
4. 翻译：用户说"翻译XX"、"把XX翻译成英文" → {"intent":"translate","params":{"lang":"en","text":"XX"}}
5. 不知道 → {"intent":"chat","params":{}}

只输出 JSON，不要其他内容。"""


def detect_intent(user_text):
    """用 AI 识别意图"""
    import ai_service as _a
    try:
        raw = _a.stable_ai(INTENT_SYSTEM_PROMPT, user_text, 0.1)
        # 提取 JSON
        raw = raw.strip()
        # 去掉 markdown 代码块
        raw = re.sub(r'^```(?:json)?\\s*', '', raw)
        raw = re.sub(r'\\s*```$', '', raw)
        # 找第一个 { 到最后一个 }
        start = raw.find('{')
        end = raw.rfind('}')
        if start == -1 or end == -1:
            return {"intent": "chat", "params": {}}
        data = json.loads(raw[start:end+1])
        if "intent" not in data:
            return {"intent": "chat", "params": {}}
        if "params" not in data:
            data["params"] = {}
        return data
    except Exception as e:
        print("[意图] 识别失败: " + str(e)[:100])
        return {"intent": "chat", "params": {}}


def execute_intent(intent_data):
    """执行意图，返回结果文本。执行失败返回 None"""
    intent = intent_data.get("intent", "chat")
    params = intent_data.get("params", {})
    
    if intent == "chat" or intent not in INTENT_MAP:
        return None
    
    import ai_service as _a
    try:
        if intent == "weather":
            return _a.free_weather(params.get("city", "北京"))
        elif intent == "crypto":
            coin = params.get("coin", "bitcoin").lower()
            coin_map = {"比特币": "bitcoin", "以太坊": "ethereum", "btc": "bitcoin", 
                       "eth": "ethereum", "狗狗币": "dogecoin", "doge": "dogecoin"}
            coin = coin_map.get(coin, coin)
            return _a.free_crypto(coin)
        elif intent == "draw":
            return ("__IMAGE__", _a.generate_image(params.get("prompt", "")))
        elif intent == "translate":
            return _a.translate_text(params.get("lang", "zh"), params.get("text", ""))
        elif intent == "search":
            import search_service as _ss
            return _ss.search_and_answer(params.get("query", ""))
        elif intent == "wiki":
            return _a.free_wiki(params.get("keyword", ""))
        elif intent == "country":
            return _a.free_country(params.get("name", ""))
        elif intent == "fx":
            return _a.free_fx(params.get("from", "USD"), params.get("to", "CNY"))
        elif intent == "ip":
            return _a.free_ip(params.get("ip", ""))
        elif intent == "anime":
            return _a.free_anime(params.get("keyword", ""))
        elif intent == "joke":
            return _a.free_fact()
        elif intent == "password":
            return "🔐 密码：" + _a.gen_password(int(params.get("length", 16)))
        elif intent == "age":
            return _a.age_calc(params.get("birthday", ""))
        elif intent == "hash":
            return "🔐 " + _a.hash_text(params.get("text", ""), params.get("algo", "sha256"))
        elif intent == "fortune":
            return _a.fortune_telling(params.get("birthday", ""), params.get("question", ""))
        elif intent == "dream":
            return _a.dream_analysis(params.get("dream", ""))
        elif intent == "tarot":
            return _a.tarot_reading(params.get("question", ""))
        elif intent == "horoscope":
            return _a.horoscope(params.get("sign", ""))
        elif intent == "love":
            return _a.love_words()
        elif intent == "poem":
            return _a.acrostic_poem(params.get("word", ""))
        elif intent == "name":
            return _a.ai_name(params.get("kind", ""))
        elif intent == "roast":
            return _a.roast_words(params.get("target", "我"))
        elif intent == "riddle":
            return _a.brain_riddle()
        elif intent == "math":
            return _a.solve_math(params.get("problem", ""))
        elif intent == "recipe":
            return _a.get_recipe(params.get("ingredient", ""))
        elif intent == "travel":
            return _a.gen_travel(params.get("city_days", ""))
        elif intent == "diet":
            return _a.gen_diet(params.get("goal", ""))
        elif intent == "workout":
            return _a.gen_workout(params.get("body", ""))
        elif intent == "shopping":
            return _a.gen_shopping(params.get("need", ""))
        elif intent == "email":
            return _a.gen_email(params.get("topic", ""))
        elif intent == "resume":
            return _a.gen_resume(params.get("exp", ""))
        elif intent == "interview":
            return _a.gen_interview(params.get("job", ""))
        elif intent == "write":
            return _a.write_copy(params.get("topic", ""))
        elif intent == "title":
            return _a.generate_titles(params.get("content", ""))
        elif intent == "summarize":
            return _a.summarize_text(params.get("text", ""))
        elif intent == "polish":
            return _a.polish_text(params.get("text", ""))
        elif intent == "emotion":
            return _a.analyze_emotion(params.get("text", ""))
        elif intent == "weekly":
            return _a.generate_weekly(params.get("report", ""))
        elif intent == "code":
            return _a.explain_code(params.get("code", ""))
        elif intent == "sql":
            return _a.generate_sql(params.get("requirement", ""))
        elif intent == "regex":
            return _a.generate_regex(params.get("requirement", ""))
        elif intent == "short":
            return _a.free_short(params.get("url", ""))
        elif intent == "news":
            import search_service as _ss
            results = _ss.search_news(params.get("query", ""))
            if results:
                return "📰 新闻\\n━━━━━━━━━━━━\\n" + "\\n".join([f"• {r['title']}\\n  {r['url']}" for r in results[:5]])
            return None
        return None
    except Exception as e:
        print("[意图] 执行失败: " + str(e)[:100])
        return None


# ==================== 本地快速预判（0秒）====================
import re as _re
import time as _time

_intent_cache = {}
_intent_cache_ttl = 300  # 5 分钟


def quick_detect(text):
    """本地正则快速识别（0 API 调用）"""
    text = text.strip()
    t_low = text.lower()

    # 天气
    if "天气" in text or "气温" in text:
        city = text.replace("天气", "").replace("怎么样", "").replace("如何", "")
        for w in ["今天", "明天", "现在", "后天", "现在"]:
            city = city.replace(w, "")
        city = city.replace("的", "").strip()
        return {"intent": "weather", "params": {"city": city or "北京"}}

    # 加密货币
    crypto_map = [("btc", "bitcoin"), ("比特币", "bitcoin"),
                  ("eth", "ethereum"), ("以太坊", "ethereum"),
                  ("doge", "dogecoin"), ("狗狗币", "dogecoin"),
                  ("sol", "solana"), ("bnb", "binancecoin")]
    for k, v in crypto_map:
        if k in t_low:
            return {"intent": "crypto", "params": {"coin": v}}

    # 翻译
    if "翻译" in text:
        if "英文" in text or "英语" in text or "en" in t_low:
            t = re.sub(r'(翻译成?)?(英文|英语|en)', '', text, flags=re.I).strip()
            return {"intent": "translate", "params": {"lang": "en", "text": t}}
        if "中文" in text or "汉语" in text or "zh" in t_low:
            t = re.sub(r'(翻译成?)?(中文|汉语|zh)', '', text, flags=re.I).strip()
            return {"intent": "translate", "params": {"lang": "zh", "text": t}}

    # 短链接
    m = re.search(r'https?://\S+', text)
    if m and len(text) < 200:
        return {"intent": "short", "params": {"url": m.group(1)}}

    # 笑话
    if text in ["讲个笑话", "来个笑话", "说个笑话", "说个段子"]:
        return {"intent": "joke", "params": {}}

    # 纯算术
    if re.match(r'^[0-9+\-*/×÷()（）.\s]+$', text) and any(c in text for c in "+-*/×÷"):
        return {"intent": "math", "params": {"problem": text}}

    return None


def detect_intent_cached(user_text):
    """带缓存的意图识别"""
    key = user_text[:100]
    now = _time.time()

    # 检查缓存
    if key in _intent_cache:
        data, ts = _intent_cache[key]
        if now - ts < _intent_cache_ttl:
            return data

    # 本地快速预判
    quick = quick_detect(user_text)
    if quick:
        _intent_cache[key] = (quick, now)
        return quick

    # AI 识别（慢路径）
    data = detect_intent(user_text)
    _intent_cache[key] = (data, now)
    return data
