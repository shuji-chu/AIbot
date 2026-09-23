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
