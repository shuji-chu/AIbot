# -*- coding: utf-8 -*-
"""监控告警系统：机器人挂了通知管理员"""
import time, threading, requests
from config import SAFEW_TOKEN, ADMIN_IDS
import datetime as _dt
def _log(*args):
    print("[" + _dt.datetime.now().strftime("%H:%M:%S") + "]", *args)



def _send_alert(text):
    """给所有管理员发告警"""
    for uid in ADMIN_IDS:
        try:
            url = "https://api.safew.bot/bot" + SAFEW_TOKEN + "/sendMessage"
            requests.post(url, json={"chat_id": uid, "text": text}, timeout=10)
        except: pass


def start_monitor():
    """心跳监控：每分钟检查一次，长时间无响应报警"""
    def loop():
        fail_count = 0
        while True:
            try:
                url = "https://api.safew.bot/bot" + SAFEW_TOKEN + "/getMe"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    fail_count = 0
                else:
                    fail_count += 1
            except:
                fail_count += 1
            
            # 连续 3 次失败报警
            if fail_count == 3:
                _send_alert("🚨 SAFW AI 告警\n机器人可能挂了\n连续 3 次心跳失败\n请检查服务器")
                _log("🚨 已发送告警")
            
            time.sleep(60)
    
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _log("✅ 监控告警已启动")
