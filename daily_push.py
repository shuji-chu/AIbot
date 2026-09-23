import time, json, os, datetime
import threading

SUB_FILE = "/root/AIbot/subscriptions.json"
PUSH_HOUR = 9

def _load_subs():
    if not os.path.exists(SUB_FILE): return []
    try:
        with open(SUB_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return [k for k, v in d.items() if v]
    except: return []

def _push_once():
    import uapi_service
    from safew_api import send_message, send_photo
    subs = _load_subs()
    if not subs: return
    try: img = uapi_service.get_wallpaper()
    except: img = None
    try: saying = uapi_service.query_saying()
    except: saying = "新的一天，加油！"
    for uid in subs:
        try:
            if img:
                send_photo(uid, img, caption="🌅 每日壁纸 · " + saying[:80])
            else:
                send_message(uid, "🌅 每日推送\n" + saying)
        except Exception as e:
            print("推送失败 " + str(uid) + ": " + str(e)[:80])
        time.sleep(0.5)
    print("✅ 每日推送完成 " + str(len(subs)) + " 人")

def start_daily_push():
    def loop():
        last_date = ""
        while True:
            try:
                now = datetime.datetime.now()
                today = now.strftime("%Y-%m-%d")
                if now.hour == PUSH_HOUR and last_date != today:
                    last_date = today
                    _push_once()
            except Exception as e:
                print("定时错: " + str(e)[:100])
            time.sleep(60)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("✅ 每日推送已启动（9:00）")
