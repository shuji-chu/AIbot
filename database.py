import sqlite3, random
from datetime import datetime
DB_PATH = 'aibot.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, total_recharge REAL DEFAULT 0, total_spent REAL DEFAULT 0, created_at TEXT, last_active TEXT)''')
    try: c.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, type TEXT, query TEXT, cost REAL, result TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS recharges (order_no TEXT PRIMARY KEY, uid TEXT, amount_usdt REAL, status TEXT, tx_hash TEXT, created_at TEXT, done_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (uid TEXT PRIMARY KEY)''')
    conn.commit(); conn.close()

def ensure_user(uid, un):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO users (uid, username, balance, created_at, last_active) VALUES (?,?,?,?,?)", (str(uid), un, 0, now, now))
    c.execute("UPDATE users SET username=?, last_active=? WHERE uid=?", (un, now, str(uid)))
    conn.commit(); conn.close()

def get_user(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT uid, username, balance, total_recharge, total_spent FROM users WHERE uid=?", (str(uid),))
    r = c.fetchone(); conn.close()
    if not r: return None
    return {"uid": r[0], "username": r[1], "balance": r[2], "total_recharge": r[3], "total_spent": r[4]}

def get_balance(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE uid=?", (str(uid),))
    r = c.fetchone(); conn.close(); return r[0] if r else 0

def update_balance(uid, amt):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE uid=?", (amt, str(uid)))
    conn.commit(); conn.close()

def add_recharge(uid, amt):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_recharge = total_recharge + ? WHERE uid=?", (amt, amt, str(uid)))
    conn.commit(); conn.close()

def add_spent(uid, amt):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE uid=?", (amt, amt, str(uid)))
    conn.commit(); conn.close()

def add_record(uid, t, q, cost, r=""):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO records (uid, type, query, cost, result, created_at) VALUES (?,?,?,?,?,?)", (str(uid), t, q, cost, r, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def get_user_records(uid, limit=10):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT type, query, cost, created_at FROM records WHERE uid=? ORDER BY id DESC LIMIT ?", (str(uid), limit))
    r = c.fetchall(); conn.close(); return r

def create_recharge(o, uid, amt):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO recharges (order_no, uid, amount_usdt, status, created_at) VALUES (?,?,?,?,?)", (o, str(uid), amt, "pending", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def get_pending_recharges():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT order_no, uid, amount_usdt, created_at FROM recharges WHERE status='pending'")
    r = c.fetchall(); conn.close(); return r

def finish_recharge(o, h):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT uid, amount_usdt FROM recharges WHERE order_no=? AND status='pending'", (o,))
    r = c.fetchone()
    if not r: conn.close(); return False
    uid, amt = r
    c.execute("UPDATE recharges SET status='done', tx_hash=?, done_at=? WHERE order_no=?", (h, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), o))
    conn.commit(); conn.close()
    add_recharge(uid, amt); return True

def get_user_recharges(uid, limit=10):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT order_no, amount_usdt, status, created_at FROM recharges WHERE uid=? ORDER BY created_at DESC LIMIT ?", (str(uid), limit))
    r = c.fetchall(); conn.close(); return r

def get_all_recharges(limit=20):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT order_no, uid, amount_usdt, status, created_at FROM recharges ORDER BY created_at DESC LIMIT ?", (limit,))
    r = c.fetchall(); conn.close(); return r

def get_paid_total():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*), IFNULL(SUM(amount_usdt),0) FROM recharges WHERE status='done'")
    r = c.fetchone(); conn.close(); return r[0], r[1]

def get_stats():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*), IFNULL(SUM(balance),0), IFNULL(SUM(total_recharge),0), IFNULL(SUM(total_spent),0) FROM users")
    r = c.fetchone(); conn.close()
    return {"total_users": r[0], "total_balance": r[1], "total_recharge": r[2], "total_spent": r[3]}

def get_active_users(hours=24):
    from datetime import timedelta
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (since,))
    r = c.fetchone(); conn.close(); return r[0] if r else 0

def get_today_new_users():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE created_at LIKE ?", (today + "%",))
    r = c.fetchone(); conn.close(); return r[0] if r else 0

def get_all_users(limit=20):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT uid, username, balance, total_recharge FROM users ORDER BY total_recharge DESC LIMIT ?", (limit,))
    r = c.fetchall(); conn.close(); return r

def get_usage_stats():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT type, COUNT(*) FROM records GROUP BY type ORDER BY COUNT(*) DESC LIMIT 15")
    r = c.fetchall(); conn.close(); return r

def add_admin(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (uid) VALUES (?)", (str(uid),))
    conn.commit(); conn.close()

def remove_admin(uid):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM admins WHERE uid=?", (str(uid),))
    conn.commit(); conn.close()

def get_admins():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT uid FROM admins")
    r = [x[0] for x in c.fetchall()]; conn.close(); return r


def get_all_uids():
    """返回所有用户的 uid 列表"""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT uid FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def check_rate_limit(uid, rtype, window_seconds):
    """返回剩余秒数（>0 表示冷却中），0 表示通过并记录时间"""
    import time, sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS rate_limits (uid TEXT, type TEXT, last_ts REAL, PRIMARY KEY(uid, type))")
    now = time.time()
    c.execute("SELECT last_ts FROM rate_limits WHERE uid=? AND type=?", (str(uid), rtype))
    row = c.fetchone()
    if row:
        elapsed = now - row[0]
        if elapsed < window_seconds:
            conn.close()
            return int(window_seconds - elapsed)
    c.execute("INSERT OR REPLACE INTO rate_limits (uid, type, last_ts) VALUES (?, ?, ?)", (str(uid), rtype, now))
    conn.commit()
    conn.close()
    return 0


def daily_usage(uid, feature):
    """查该用户今天某功能已用次数"""
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS daily_usage (uid TEXT, feature TEXT, day TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(uid, feature, day))")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM daily_usage WHERE uid=? AND feature=? AND day=?", (str(uid), feature, today))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_daily_usage(uid, feature):
    """该功能今日使用次数 +1"""
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS daily_usage (uid TEXT, feature TEXT, day TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(uid, feature, day))")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO daily_usage (uid, feature, day, count) VALUES (?,?,?,1) ON CONFLICT(uid,feature,day) DO UPDATE SET count = count + 1", (str(uid), feature, today))
    conn.commit(); conn.close()


# ==================== 会员系统 ====================
def create_vip_table():
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS vip (uid TEXT PRIMARY KEY, expire_at TEXT, plan TEXT, created_at TEXT)")
    conn.commit(); conn.close()

def is_vip(uid):
    """判断用户是否会员且未过期"""
    import sqlite3, datetime
    create_vip_table()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT expire_at FROM vip WHERE uid=?", (str(uid),))
    row = c.fetchone(); conn.close()
    if not row or not row[0]: return False
    try:
        exp = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        return exp > datetime.datetime.now()
    except: return False

def add_vip(uid, days=30, plan="monthly"):
    """给用户开会员"""
    import sqlite3, datetime
    create_vip_table()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT expire_at FROM vip WHERE uid=?", (str(uid),))
    row = c.fetchone()
    now = datetime.datetime.now()
    if row and row[0]:
        try:
            base = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if base < now: base = now
        except: base = now
    else:
        base = now
    new_exp = base + datetime.timedelta(days=days)
    c.execute("INSERT OR REPLACE INTO vip (uid, expire_at, plan, created_at) VALUES (?,?,?,?)",
              (str(uid), new_exp.strftime("%Y-%m-%d %H:%M:%S"), plan, now.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return new_exp.strftime("%Y-%m-%d")

def get_vip_info(uid):
    """返回会员信息"""
    import sqlite3
    create_vip_table()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT expire_at, plan FROM vip WHERE uid=?", (str(uid),))
    row = c.fetchone(); conn.close()
    return row  # (expire_at, plan) 或 None


# ==================== VIP 订单 ====================
def create_vip_order(order_no, uid, amount, days=30, expire_minutes=10):
    """创建会员订单（10 分钟过期）"""
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS vip_orders (order_no TEXT PRIMARY KEY, uid TEXT, amount_usdt REAL, days INTEGER, status TEXT DEFAULT 'pending', tx_hash TEXT, created_at TEXT, done_at TEXT)")
    now = datetime.datetime.now()
    expire = now + datetime.timedelta(minutes=expire_minutes)
    c.execute("INSERT OR IGNORE INTO vip_orders (order_no, uid, amount_usdt, days, created_at) VALUES (?,?,?,?,?)",
              (order_no, str(uid), amount, days, now.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return expire.strftime("%H:%M:%S")

def get_pending_vip_orders():
    """待处理的会员订单（10 分钟内有效）"""
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS vip_orders (order_no TEXT PRIMARY KEY, uid TEXT, amount_usdt REAL, days INTEGER, status TEXT DEFAULT 'pending', tx_hash TEXT, created_at TEXT, done_at TEXT)")
    # 把超过 10 分钟未支付的标记为 expired
    cutoff = (datetime.datetime.now() - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE vip_orders SET status='expired' WHERE status='pending' AND created_at < ?", (cutoff,))
    conn.commit()
    # 返回未过期的
    c.execute("SELECT order_no, uid, amount_usdt, days FROM vip_orders WHERE status='pending'")
    r = c.fetchall(); conn.close(); return r

def finish_vip_order(order_no, tx_hash):
    """完成会员订单"""
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE vip_orders SET status='success', tx_hash=?, done_at=? WHERE order_no=?",
              (tx_hash, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_no))
    conn.commit(); conn.close()
    return True

def cancel_vip_order(order_no):
    """手动取消订单"""
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE vip_orders SET status='cancelled' WHERE order_no=? AND status='pending'", (order_no,))
    conn.commit(); conn.close()


# ==================== 用户偏好 ====================
def get_user_prefs(uid):
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_prefs (
        uid TEXT PRIMARY KEY, style TEXT, lang TEXT, reply_length TEXT,
        voice_on INTEGER DEFAULT 0, role TEXT DEFAULT '', updated_at TEXT
    )""")
    c.execute("SELECT style, lang, reply_length, voice_on, role FROM user_prefs WHERE uid=?", (str(uid),))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"style": "normal", "lang": "zh", "reply_length": "normal", "voice_on": 0, "role": ""}
    return {"style": row[0] or "normal", "lang": row[1] or "zh",
            "reply_length": row[2] or "normal", "voice_on": row[3] or 0, "role": row[4] or ""}


def set_user_pref(uid, key, value):
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_prefs (
        uid TEXT PRIMARY KEY, style TEXT, lang TEXT, reply_length TEXT,
        voice_on INTEGER DEFAULT 0, role TEXT DEFAULT '', updated_at TEXT
    )""")
    # 先确保有记录
    c.execute("INSERT OR IGNORE INTO user_prefs (uid, updated_at) VALUES (?,?)",
              (str(uid), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    # 更新指定字段
    if key in ['style', 'lang', 'reply_length', 'role']:
        c.execute(f"UPDATE user_prefs SET {key}=?, updated_at=? WHERE uid=?",
                  (value, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(uid)))
    elif key == 'voice_on':
        c.execute("UPDATE user_prefs SET voice_on=?, updated_at=? WHERE uid=?",
                  (int(value), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(uid)))
    conn.commit(); conn.close()
    return True


# ==================== 长期记忆 ====================
def memory_add(uid, key, value, category="general"):
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, key TEXT, value TEXT,
        category TEXT, created_at TEXT, updated_at TEXT)""")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 查是否已存在同 key
    c.execute("SELECT id FROM user_memory WHERE uid=? AND key=?", (str(uid), key))
    row = c.fetchone()
    if row:
        c.execute("UPDATE user_memory SET value=?, updated_at=? WHERE id=?", (value, now, row[0]))
    else:
        c.execute("INSERT INTO user_memory (uid, key, value, category, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                  (str(uid), key, value, category, now, now))
    conn.commit(); conn.close()
    return True


def memory_get(uid, limit=20):
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, key TEXT, value TEXT,
        category TEXT, created_at TEXT, updated_at TEXT)""")
    c.execute("SELECT key, value, category FROM user_memory WHERE uid=? ORDER BY updated_at DESC LIMIT ?",
              (str(uid), limit))
    rows = c.fetchall()
    conn.close()
    return rows


def memory_clear(uid):
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM user_memory WHERE uid=?", (str(uid),))
    conn.commit(); conn.close()
    return True


def profile_get(uid):
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_profile (
        uid TEXT PRIMARY KEY, name TEXT, birthday TEXT, city TEXT,
        job TEXT, hobby TEXT, likes TEXT, dislikes TEXT,
        notes TEXT, last_active TEXT, total_msgs INTEGER DEFAULT 0)""")
    c.execute("SELECT name, birthday, city, job, hobby, likes, dislikes, notes, total_msgs FROM user_profile WHERE uid=?",
              (str(uid),))
    row = c.fetchone()
    conn.close()
    if not row:
        return {}
    return {"name": row[0], "birthday": row[1], "city": row[2], "job": row[3],
            "hobby": row[4], "likes": row[5], "dislikes": row[6], "notes": row[7],
            "total_msgs": row[8] or 0}


def profile_update(uid, **kwargs):
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_profile (
        uid TEXT PRIMARY KEY, name TEXT, birthday TEXT, city TEXT,
        job TEXT, hobby TEXT, likes TEXT, dislikes TEXT,
        notes TEXT, last_active TEXT, total_msgs INTEGER DEFAULT 0)""")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO user_profile (uid, last_active) VALUES (?,?)", (str(uid), now))
    for k, v in kwargs.items():
        if k in ['name', 'birthday', 'city', 'job', 'hobby', 'likes', 'dislikes', 'notes']:
            c.execute(f"UPDATE user_profile SET {k}=?, last_active=? WHERE uid=?", (v, now, str(uid)))
    c.execute("UPDATE user_profile SET last_active=?, total_msgs=total_msgs+1 WHERE uid=?", (now, str(uid)))
    conn.commit(); conn.close()
    return True


# ==================== 用户统计 ====================
def user_seen(uid, is_command=False):
    import sqlite3, datetime
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS user_stats (
        uid TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT,
        total_msgs INTEGER DEFAULT 0, total_commands INTEGER DEFAULT 0,
        favorite_cmd TEXT, last_greeting TEXT, streak_days INTEGER DEFAULT 0)""")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT first_seen FROM user_stats WHERE uid=?", (str(uid),))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO user_stats (uid, first_seen, last_seen, total_msgs, total_commands) VALUES (?,?,?,1,?)",
                  (str(uid), now, now, 1 if is_command else 0))
    else:
        if is_command:
            c.execute("UPDATE user_stats SET last_seen=?, total_msgs=total_msgs+1, total_commands=total_commands+1 WHERE uid=?",
                      (now, str(uid)))
        else:
            c.execute("UPDATE user_stats SET last_seen=?, total_msgs=total_msgs+1 WHERE uid=?",
                      (now, str(uid)))
    conn.commit(); conn.close()
    return True


def get_user_stats(uid):
    import sqlite3
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT first_seen, last_seen, total_msgs, total_commands FROM user_stats WHERE uid=?", (str(uid),))
    row = c.fetchone()
    conn.close()
    if not row: return {}
    return {"first_seen": row[0], "last_seen": row[1],
            "total_msgs": row[2], "total_commands": row[3]}
