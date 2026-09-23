import requests, time, threading
from config import TRONGRID_API, TRON_WALLET, USDT_CONTRACT
from database import get_pending_recharges, finish_recharge, get_balance

def check_recharges():
    try:
        url = "https://api.trongrid.io/v1/accounts/" + TRON_WALLET + "/transactions/trc20"
        headers = {"TRON-PRO-API-KEY": TRONGRID_API}
        params = {"limit": 20, "contract_address": USDT_CONTRACT, "only_to": "true"}
        r = requests.get(url, headers=headers, params=params, timeout=15)
        txs = r.json().get("data", [])
        pending = get_pending_recharges()
        if not pending: return
        for tx in txs:
            try:
                amt = int(tx["value"]) / (10 ** 6)
                h = tx["transaction_id"]
                for o in pending:
                    if abs(amt - o[2]) < 0.0001:
                        if finish_recharge(o[0], h):
                            print("✅ 充值:" + str(o[1]) + " +" + str(amt))
                            try:
                                from safew_api import send_message
                                send_message(o[1], "✅ 充值成功\n到账：" + str(amt) + " USDT\n余额：" + ("%.4f" % get_balance(o[1])))
                            except: pass
                        break
            except: continue
    except Exception as e:
        print("扫链错:" + str(e)[:100])

def start_monitor():
    def loop():
        while True:
            try: check_recharges()
            except: pass
            time.sleep(30)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("✅ 链上监控已启动")
