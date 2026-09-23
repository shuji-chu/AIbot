from config import ADMIN_IDS
from database import (get_user, get_balance, update_balance,
                      add_admin, remove_admin, get_admins,
                      get_stats, get_all_users, get_active_users,
                      get_today_new_users, get_usage_stats,
                      get_all_recharges, get_paid_total)
from safew_api import send_message, delete_message

NL = chr(10)

RUNTIME_ADMINS = list(ADMIN_IDS)
try:
    for a in get_admins():
        try:
            u = int(a)
            if u not in RUNTIME_ADMINS:
                RUNTIME_ADMINS.append(u)
        except:
            pass
except:
    pass


def is_admin(uid):
    try:
        return int(uid) in RUNTIME_ADMINS
    except:
        return False


def add_admin_runtime(uid):
    try:
        u = int(uid)
        if u not in RUNTIME_ADMINS:
            RUNTIME_ADMINS.append(u)
        add_admin(uid)
        return True
    except:
        return False


def remove_admin_runtime(uid):
    try:
        u = int(uid)
        if u in RUNTIME_ADMINS:
            RUNTIME_ADMINS.remove(u)
        remove_admin(uid)
        return True
    except:
        return False


def admin_menu():
    return {"inline_keyboard": [
        [{"text": "📊 数据统计", "callback_data": "adm_stats"},
         {"text": "👥 使用人数", "callback_data": "adm_users"}],
        [{"text": "💰 充值记录", "callback_data": "adm_orders"},
         {"text": "📈 功能排行", "callback_data": "adm_usage"}],
        [{"text": "🏆 用户排行", "callback_data": "adm_list"},
         {"text": "👤 查用户", "callback_data": "adm_user"}],
        [{"text": "➕ 加余额", "callback_data": "adm_add"},
         {"text": "➖ 扣余额", "callback_data": "adm_sub"}],
        [{"text": "👑 管理员", "callback_data": "adm_admin"},
         {"text": "❌ 关闭", "callback_data": "adm_close"}],
    ]}


def handle_admin(m, text):
    cid = m.get("chat", {}).get("id")
    uid = m.get("from", {}).get("id")
    if not is_admin(uid):
        send_message(cid, "❌ 你没有管理员权限")
        return
    parts = text.split()

    if len(parts) == 1:
        send_message(cid,
            "🛠 管理面板" + NL + "━━━━━━━━━━━━" + NL +
            "/admin stats — 数据统计" + NL +
            "/admin users — 使用人数" + NL +
            "/admin orders — 充值记录" + NL +
            "/admin usage — 功能使用排行" + NL +
            "/admin list — 用户余额排行" + NL +
            "/admin user <ID> — 查用户" + NL +
            "/admin add <ID> <金额> — 加余额" + NL +
            "/admin sub <ID> <金额> — 扣余额" + NL +
            "/admin addadmin <ID> — 加管理员" + NL +
            "/admin deladmin <ID> — 删管理员",
            custom_markup=admin_menu())
        return

    cmd = parts[1]

    if cmd == "stats":
        s = get_stats()
        cnt, total = get_paid_total()
        send_message(cid,
            "📊 数据统计" + NL + "━━━━━━━━━━━━" + NL +
            "👥 总用户：" + str(s["total_users"]) + NL +
            "💰 总余额：" + ("%.4f" % s["total_balance"]) + " USDT" + NL +
            "💵 累计充值：" + ("%.4f" % s["total_recharge"]) + " USDT" + NL +
            "💸 累计消费：" + ("%.4f" % s["total_spent"]) + " USDT" + NL +
            "📋 充值订单：" + str(cnt) + " 笔" + NL +
            "💎 充值总额：" + ("%.4f" % total) + " USDT",
            custom_markup=admin_menu())
        return

    if cmd == "users":
        active = get_active_users(24)
        today = get_today_new_users()
        s = get_stats()
        send_message(cid,
            "👥 使用统计" + NL + "━━━━━━━━━━━━" + NL +
            "📌 总用户：" + str(s["total_users"]) + NL +
            "🆕 今日新增：" + str(today) + NL +
            "🟢 24小时活跃：" + str(active),
            custom_markup=admin_menu())
        return

    if cmd == "orders":
        recs = get_all_recharges(10)
        if not recs:
            send_message(cid, "暂无充值记录", custom_markup=admin_menu())
            return
        lines = ["💰 最近10条充值", "━━━━━━━━━━━━"]
        for r in recs:
            icon = "✅" if r[3] == "done" else "⏳"
            lines.append(icon + " " + str(r[2]) + " USDT · " + str(r[1]) + " · " + str(r[4]))
        send_message(cid, NL.join(lines), custom_markup=admin_menu())
        return

    if cmd == "usage":
        us = get_usage_stats()
        if not us:
            send_message(cid, "暂无使用数据", custom_markup=admin_menu())
            return
        lines = ["📈 功能使用排行", "━━━━━━━━━━━━"]
        for i, row in enumerate(us, 1):
            lines.append(str(i) + ". " + str(row[0]) + " · " + str(row[1]) + " 次")
        send_message(cid, NL.join(lines), custom_markup=admin_menu())
        return

    if cmd == "list":
        users = get_all_users(20)
        if not users:
            send_message(cid, "暂无用户", custom_markup=admin_menu())
            return
        lines = ["🏆 用户余额排行", "━━━━━━━━━━━━"]
        for i, row in enumerate(users, 1):
            lines.append(str(i) + ". " + str(row[1]) + " · " + ("%.4f" % row[2]) + " USDT")
        send_message(cid, NL.join(lines), custom_markup=admin_menu())
        return

    if cmd == "user" and len(parts) >= 3:
        u = get_user(parts[2])
        if not u:
            send_message(cid, "❌ 用户不存在", custom_markup=admin_menu())
            return
        send_message(cid,
            "👤 用户详情" + NL + "━━━━━━━━━━━━" + NL +
            "UID：" + parts[2] + NL +
            "用户名：" + str(u["username"]) + NL +
            "余额：" + ("%.4f" % u["balance"]) + " USDT" + NL +
            "累计充值：" + ("%.4f" % u["total_recharge"]) + " USDT" + NL +
            "累计消费：" + ("%.4f" % u["total_spent"]) + " USDT",
            custom_markup=admin_menu())
        return

    if cmd == "add" and len(parts) >= 4:
        u, n = parts[2], float(parts[3])
        update_balance(u, n)
        send_message(cid, "✅ 已为 " + u + " 加 " + str(n) + " USDT" + NL +
                     "当前：" + ("%.4f" % get_balance(u)), custom_markup=admin_menu())
        return

    if cmd == "sub" and len(parts) >= 4:
        u, n = parts[2], float(parts[3])
        update_balance(u, -n)
        send_message(cid, "✅ 已扣 " + u + " " + str(n) + " USDT" + NL +
                     "当前：" + ("%.4f" % get_balance(u)), custom_markup=admin_menu())
        return

    if cmd == "addadmin" and len(parts) >= 3:
        u = parts[2]
        if add_admin_runtime(u):
            send_message(cid, "✅ 已添加 " + u + " 为管理员", custom_markup=admin_menu())
        else:
            send_message(cid, "❌ 添加失败", custom_markup=admin_menu())
        return

    if cmd == "deladmin" and len(parts) >= 3:
        u = parts[2]
        if remove_admin_runtime(u):
            send_message(cid, "✅ 已移除 " + u + " 的管理员", custom_markup=admin_menu())
        else:
            send_message(cid, "❌ 移除失败", custom_markup=admin_menu())
        return

    send_message(cid, "❌ 未知命令，发 /admin 查看帮助", custom_markup=admin_menu())


def handle_admin_callback(cq):
    cid = cq.get("message", {}).get("chat", {}).get("id")
    uid = cq.get("from", {}).get("id")
    data = cq.get("data", "")
    mid = cq.get("message", {}).get("message_id")
    if not data.startswith("adm_"): return False
    if not is_admin(uid): return True

    if data == "adm_close":
        delete_message(cid, mid); return True

    if data == "adm_stats":
        s = get_stats()
        cnt, total = get_paid_total()
        send_message(cid,
            "📊 数据统计" + NL + "━━━━━━━━━━━━" + NL +
            "👥 总用户：" + str(s["total_users"]) + NL +
            "💰 总余额：" + ("%.4f" % s["total_balance"]) + " USDT" + NL +
            "💵 累计充值：" + ("%.4f" % s["total_recharge"]) + " USDT" + NL +
            "💸 累计消费：" + ("%.4f" % s["total_spent"]) + " USDT" + NL +
            "📋 充值订单：" + str(cnt) + " 笔" + NL +
            "💎 充值总额：" + ("%.4f" % total) + " USDT",
            custom_markup=admin_menu())
        return True

    if data == "adm_users":
        active = get_active_users(24)
        today = get_today_new_users()
        s = get_stats()
        send_message(cid,
            "👥 使用统计" + NL + "━━━━━━━━━━━━" + NL +
            "📌 总用户：" + str(s["total_users"]) + NL +
            "🆕 今日新增：" + str(today) + NL +
            "🟢 24小时活跃：" + str(active),
            custom_markup=admin_menu())
        return True

    if data == "adm_orders":
        recs = get_all_recharges(10)
        if not recs:
            send_message(cid, "暂无充值记录", custom_markup=admin_menu()); return True
        lines = ["💰 最近10条充值", "━━━━━━━━━━━━"]
        for r in recs:
            icon = "✅" if r[3] == "done" else "⏳"
            lines.append(icon + " " + str(r[2]) + " USDT · " + str(r[1]) + " · " + str(r[4]))
        send_message(cid, NL.join(lines), custom_markup=admin_menu()); return True

    if data == "adm_usage":
        us = get_usage_stats()
        if not us:
            send_message(cid, "暂无使用数据", custom_markup=admin_menu()); return True
        lines = ["📈 功能使用排行", "━━━━━━━━━━━━"]
        for i, row in enumerate(us, 1):
            lines.append(str(i) + ". " + str(row[0]) + " · " + str(row[1]) + " 次")
        send_message(cid, NL.join(lines), custom_markup=admin_menu()); return True

    if data == "adm_list":
        users = get_all_users(20)
        if not users:
            send_message(cid, "暂无用户", custom_markup=admin_menu()); return True
        lines = ["🏆 用户余额排行", "━━━━━━━━━━━━"]
        for i, row in enumerate(users, 1):
            lines.append(str(i) + ". " + str(row[1]) + " · " + ("%.4f" % row[2]) + " USDT")
        send_message(cid, NL.join(lines), custom_markup=admin_menu()); return True

    if data == "adm_user":
        send_message(cid, "👤 格式：/admin user <ID>", custom_markup=admin_menu()); return True
    if data == "adm_add":
        send_message(cid, "➕ 格式：/admin add <ID> <金额>", custom_markup=admin_menu()); return True
    if data == "adm_sub":
        send_message(cid, "➖ 格式：/admin sub <ID> <金额>", custom_markup=admin_menu()); return True
    if data == "adm_admin":
        send_message(cid, "👑 添加：/admin addadmin <ID>\n移除：/admin deladmin <ID>", custom_markup=admin_menu()); return True

    return False
