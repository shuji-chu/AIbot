import time, requests
from concurrent.futures import ThreadPoolExecutor
from config import SAFEW_TOKEN
from database import init_db
from handlers import handle_message, handle_callback
from safew_api import set_commands
from tron_monitor import start_monitor
from daily_push import start_daily_push
import datetime as _dt
def _log(*args):
    print("[" + _dt.datetime.now().strftime("%H:%M:%S") + "]", *args)


# 监控告警（可选，没有 monitor.py 时跳过）
try:
    from monitor import start_monitor as start_alert_monitor
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    _log("⚠️ monitor.py 不存在，跳过监控")

# 线程池：同时最多处理 30 条消息
executor = ThreadPoolExecutor(max_workers=30)


def safe_handle_message(msg):
    try:
        handle_message(msg)
    except Exception as e:
        _log("消息错:" + str(e)[:200])


def safe_handle_callback(cq):
    try:
        handle_callback(cq)
    except Exception as e:
        _log("按钮错:" + str(e)[:200])


def main():
    init_db()
    set_commands()
    start_monitor()
    start_daily_push()
    if HAS_MONITOR:
        start_alert_monitor()
    offset = 0
    _log("🤖 机器人已启动（多线程模式，30 并发）...")
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
            _log("主循环错:" + str(e)[:200])
            time.sleep(5)


if __name__ == "__main__":
    main()
