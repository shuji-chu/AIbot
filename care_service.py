# -*- coding: utf-8 -*-
"""主动关怀：生日祝福 + 久未活跃召回 + 每日问候"""
import time, datetime, json, os, threading
import database as _d


def _send(uid, text):
    try:
        from safew_api import send_message
        send_message(uid, text)
        return True
    except: return False


def check_birthdays():
    """检查今天有没有用户生日"""
    try:
        import sqlite3
        conn = sqlite3.connect('/root/AIbot/aibot.db')
        c = conn.cursor()
        today = datetime.datetime.now().strftime("%m-%d")
        c.execute("SELECT uid, name FROM user_profile WHERE birthday LIKE ?", ("%-" + today,))
        rows = c.fetchall()
        conn.close()
        for uid, name in rows:
            text = ("🎂 生日快乐" + (("，" + name) if name else "") + "！\n"
                    "━━━━━━━━━━━━━\n"
                    "祝你生日快乐，事事顺心 🎉\n"
                    "今天想聊点什么？或者让我帮你做点什么？")
            _send(uid, text)
            print("[关怀] 生日祝福 → " + str(uid))
    except Exception as e:
        print("[关怀] 生日检查失败：" + str(e)[:80])


def check_inactive():
    """检查 7 天未活跃的用户"""
    try:
        import sqlite3
        conn = sqlite3.connect('/root/AIbot/aibot.db')
        c = conn.cursor()
        # 7 天前的时间戳
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT uid, name FROM user_profile WHERE last_active < ? AND last_active IS NOT NULL LIMIT 20", (cutoff,))
        rows = c.fetchall()
        conn.close()
        for uid, name in rows:
            text = ("👋 好久不见" + (("，" + name) if name else "") + "！\n"
                    "最近怎么样？我一直在等你回来~\n"
                    "试试 /help 看看有什么新功能")
            _send(uid, text)
            print("[关怀] 召回 → " + str(uid))
    except Exception as e:
        print("[关怀] 召回检查失败：" + str(e)[:80])


def daily_greeting():
    """每日问候（给活跃用户）"""
    try:
        import sqlite3
        conn = sqlite3.connect('/root/AIbot/aibot.db')
        c = conn.cursor()
        # 24 小时内活跃的用户
        cutoff = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT uid FROM user_profile WHERE last_active > ? LIMIT 50", (cutoff,))
        rows = c.fetchall()
        conn.close()
        # 早上 8 点问候
        hour = datetime.datetime.now().hour
        if hour == 8:
            for (uid,) in rows:
                text = "🌅 早上好！新的一天，加油！"
                _send(uid, text)
    except Exception as e:
        print("[关怀] 问候失败：" + str(e)[:80])


def start_care():
    """启动关怀循环"""
    def loop():
        last_birthday_check = ""
        last_inactive_check = ""
        while True:
            try:
                now = datetime.datetime.now()
                today = now.strftime("%Y-%m-%d")
                # 每天检查一次生日
                if now.hour == 9 and last_birthday_check != today:
                    last_birthday_check = today
                    check_birthdays()
                # 每周一检查召回
                if now.weekday() == 0 and now.hour == 10 and last_inactive_check != today:
                    last_inactive_check = today
                    check_inactive()
                # 每天 8 点问候
                if now.hour == 8:
                    daily_greeting()
            except Exception as e:
                print("[关怀] 循环错：" + str(e)[:80])
            time.sleep(3600)  # 每小时检查
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("✅ 主动关怀已启动")
