import requests
UAPI_KEY = "uapi-y2bqsrm0hxFWdKe4iJemKfLLUpc3itD2C53elDEk"
BASE = "https://uapis.cn/api/v1"
SEP = "━━━━━━━━━━━━━━"
NL = chr(10)

def _h(): return {"Authorization": "Bearer " + UAPI_KEY}

def _get(url, params, retry=3):
    for i in range(retry):
        try:
            r = requests.get(url, headers=_h(), params=params, timeout=30)
            return r.json()
        except:
            if i < retry - 1:
                import time; time.sleep(2)
    return {"code": "NETWORK_ERROR"}

def query_weather(city):
    d = _get(BASE + "/misc/weather", {"city": city, "extended": "true"})
    if d.get("code") == "NETWORK_ERROR":
        return "❌ 接口繁忙"
    if "code" in d and d.get("code") not in (200, None):
        return "❌ " + str(d.get("message", "查询失败"))
    return ("🌤 " + str(d.get("city", "")) + " 天气" + NL + SEP + NL +
            "🌡 天气：" + str(d.get("weather", "")) + NL +
            "🌡 温度：" + str(d.get("temperature", "")) + "°C" + NL +
            "🌬 体感：" + str(d.get("feels_like", "")) + "°C" + NL +
            "💨 风向：" + str(d.get("wind_direction", "")) + " " + str(d.get("wind_power", "")) + NL +
            "💧 湿度：" + str(d.get("humidity", "")) + "%" + NL +
            "👁 能见度：" + str(d.get("visibility", "")) + "km" + NL +
            "🌫 AQI：" + str(d.get("aqi", "")) + " " + str(d.get("aqi_category", "")) + NL +
            SEP + NL +
            "🕐 " + str(d.get("report_time", "")))

def query_ip(ip):
    d = _get(BASE + "/network/ipinfo", {"ip": ip})
    if "message" in d and "code" in d: return "❌ " + str(d.get("message"))
    return ("🌐 IP" + NL + SEP + NL + "📍 " + str(d.get("ip", ip)) + NL +
            "🗺 " + str(d.get("region", "")) + NL + "📡 " + str(d.get("isp", "")))

def generate_qrcode(text, size=512):
    try:
        r = requests.get(BASE + "/image/qrcode", headers=_h(), params={"text": text, "size": size, "format": "image"}, timeout=30)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
            return r.content
    except: pass
    return None

def query_md5(text):
    d = _get(BASE + "/misc/md5", {"text": text})
    return "🔐 " + str(d.get("md5", ""))

def query_timestamp():
    d = _get(BASE + "/misc/timestamp", {})
    return "⏰ " + str(d.get("datetime", "")) + NL + "秒:" + str(d.get("timestamp", ""))

def query_saying():
    d = _get(BASE + "/saying", {})
    return "💬 " + str(d.get("text", ""))

def get_wallpaper():
    """返回壁纸图片二进制"""
    try:
        r = requests.get(BASE + "/image/bing-daily", headers=_h(), timeout=30)
        # 如果直接返回图片
        if r.headers.get("Content-Type", "").startswith("image"):
            return r.content
        # 如果返回 JSON，里面有 URL
        d = r.json()
        url = d.get("url") or d.get("data", {}).get("url") or d.get("image")
        if url:
            return requests.get(url, timeout=60).content
    except Exception as e:
        print("壁纸失败：" + str(e)[:80])
    return None

def query_hotboard(p="weibo"):
    d = _get(BASE + "/misc/hotboard", {"type": p})
    if "code" in d: return "❌ 获取失败"
    lines = ["🔥 " + p + "热榜", SEP]
    for it in d.get("list", [])[:10]:
        lines.append(str(it.get("index", "")) + ". " + str(it.get("title", "")))
    return NL.join(lines)

def query_epic():
    d = _get(BASE + "/misc/epic", {})
    lines = ["🎮 Epic 免费游戏", SEP]
    for it in d.get("list", [])[:5]:
        lines.append("· " + str(it.get("title", "")))
    return NL.join(lines) if len(lines) > 2 else "暂无"

def query_bili_live(roomid):
    d = _get(BASE + "/social/bilibili/live", {"roomid": roomid})
    return "📺 " + str(d.get("title", "")) + NL + "主播:" + str(d.get("uname", "")) + NL + "人气:" + str(d.get("online", 0))

def query_bilibili_user(uid):
    d = _get(BASE + "/social/bilibili/userinfo", {"uid": str(uid)})
    if "code" in d and d.get("code") != 200: return "❌ " + str(d.get("message", ""))
    return "📺 " + str(d.get("name", "")) + " Lv" + str(d.get("level", 0)) + NL + "粉丝:" + str(d.get("follower", 0))

def query_qq_user(qq):
    d = _get(BASE + "/social/qq/userinfo", {"qq": str(qq)})
    if "error" in d: return "❌ " + str(d["error"])
    return "👤 " + str(d.get("nickname", "")) + NL + "年龄:" + str(d.get("age", ""))

def query_qq_group(group_id):
    d = _get(BASE + "/social/qq/groupinfo", {"group_id": str(group_id)})
    if "error" in d: return "❌ " + str(d["error"])
    return "📊 " + str(d.get("group_name", "")) + NL + "人数:" + str(d.get("member_count", 0))

def query_dns(domain):
    d = _get(BASE + "/network/dns", {"domain": domain})
    lines = ["🌐 DNS " + domain, SEP]
    for it in d.get("list", [])[:10]:
        lines.append(str(it.get("type", "")) + " " + str(it.get("value", "")))
    return NL.join(lines) if len(lines) > 2 else "❌ 无结果"
