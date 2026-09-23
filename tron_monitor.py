import requests, time, threading
import datetime as _dt
from config import TRONGRID_API, TRON_WALLET, USDT_CONTRACT
from database import (get_pending_recharges, finish_recharge, get_balance,
                      get_pending_vip_orders, finish_vip_order, add_vip,
                      get_vip_info)


def _log(*args):
    print("[" + _dt.datetime.now().strftime("%H:%M:%S") + "]", *args)


def check_recharges():
    try:
        url = "https://api.trongrid.io/v1/accounts/" + TRON_WALLET + "/transactions/trc20"
        headers = {"TRON-PRO-API-KEY": TRONGRID_API}
        params = {"limit": 20, "contract_address": USDT_CONTRACT, "only_to": "true"}
        r = requests.get(url, headers=headers, params=params, timeout=15)
        txs = r.json().get("data", [])

        pending = get_pending_recharges()
        vip_orders = get_pending_vip_orders()
        if not pending and not vip_orders:
            return

        for tx in txs:
            try:
                amt = int(tx["value"]) / (10 ** 6)
                h = tx["transaction_id"]

                # ===== 充值订单匹配 =====
                for o in pending:
                    if abs(amt - o[2]) < 0.0001:
                        if finish_recharge(o[0], h):
                            _log("✅ 充值:" + str(o[1]) + " +" + str(amt))
                            try:
                                from safew_api import send_message
                                send_message(o[1], "✅ 充值成功\n到账：" + str(amt) +
                                             " USDT\n余额：" + ("%.4f" % get_balance(o[1])))
                            except: pass
                        break

                # ===== VIP 订单匹配 =====
                for vo in vip_orders:
                    order_no, v_uid, v_amt, v_days = vo
                    if abs(amt - v_amt) < 0.0001:
                        if finish_vip_order(order_no, h):
                            add_vip(v_uid, v_days, "monthly")
                            _log("👑 VIP:" + str(v_uid) + " +" + str(v_days) + "天")
                            try:
                                from safew_api import send_message
                                info = get_vip_info(v_uid)
                                exp = info[0] if info else "?"
                                send_message(v_uid,
                                    "👑 会员开通成功！\n"
                                    "━━━━━━━━━━━━\n"
                                    "类型：月卡会员\n"
                                    "有效期至：" + str(exp) + "\n\n"
                                    "💎 会员特权：\n"
                                    "• 每天 10 次免费绘画\n"
                                    "• 每天 3 次免费视频\n"
                                    "• 趣味功能无限\n"
                                    "• 每天 3 次免费换脸\n"
                                    "• 语音克隆半价\n\n"
                                    "发 /vip 查看详情")
                            except: pass
                        break
            except:
                continue
    except Exception as e:
        _log("扫链错:" + str(e)[:100])


def start_monitor():
    def loop():
        while True:
            try:
                check_recharges()
            except:
                pass
            time.sleep(30)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _log("✅ 链上监控已启动")
