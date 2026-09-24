import time, requests
from concurrent.futures import ThreadPoolExecutor
from config import SAFEW_TOKEN
from database import init_db
from handlers import handle_message, handle_callback
from safew_api import set_commands
from tron_monitor import start_monitor
from daily_push import start_daily_push

try:
    from monitor import start_monitor as start_alert_monitor
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False

try:
    from care_service import start_care
    HAS_CARE = True
except ImportError:
    HAS_CARE = False

executor = ThreadPoolExecutor(max_workers=30)


def safe_handle_message(msg):
    try:
        handle_message(msg)
    except Exception as e:
        print("消息错:" + str(e)[:200])


def safe_handle_callback(cq):
    try:
        handle_callback(cq)
    except Exception as e:
        print("按钮错:" + str(e)[:200])


def main():
    init_db()
    set_commands()
    start_monitor()
    start_daily_push()
    if HAS_MONITOR:
        start_alert_monitor()
    if HAS_CARE:
        try:
            start_care()
        except Exception as e:
            print("关怀启动失败: " + str(e)[:80])
    offset = 0
    print("🤖 机器人已启动（多线程模式，30 并发）...")
    while True:
        try:
            url = "https://api.safew.bot/bot" + SAFEW_TOKEN + "/getUpdates"
            res = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=40)
            updates = res.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message")
                if msg:
                    executor.submit(safe_handle_message, msg)
                cq = u.get("callback_query")
                if cq:
                    executor.submit(safe_handle_callback, cq)
        except Exception as e:
            print("主循环错:" + str(e)[:200])
            time.sleep(5)


if __name__ == "__main__":
    main()
