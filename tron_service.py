import requests
from config import TRONGRID_API, USDT_CONTRACT

TRON_API = "https://api.trongrid.io"
H = {"TRON-PRO-API-KEY": TRONGRID_API}
USDT_DECIMAL = 10 ** 6


def _get(url, params=None):
    try:
        r = requests.get(url, headers=H, params=params, timeout=15)
        return r.json()
    except Exception as e:
        return {"_err": str(e)[:100]}


def _fmt_time(ms):
    if not ms: return "未知"
    import datetime
    try:
        return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y/%m/%d %H:%M:%S")
    except:
        return "未知"


def _short(addr):
    if not addr or len(addr) < 12: return addr or ""
    return addr[:8] + "..." + addr[-6:]


def get_wallet_info(address):
    """查询钱包信息"""
    d = _get(TRON_API + "/v1/accounts/" + address)
    if "_err" in d:
        return "❌ 网络错误：" + d["_err"]
    if not d.get("data"):
        return "❌ 账户不存在或从未激活"

    a = d["data"][0]
    balance = a.get("balance", 0) / 1e6
    create_time = _fmt_time(a.get("create_time"))
    last_op = _fmt_time(a.get("latest_opration_time"))

    # 质押 TRX
    frozen_total = 0
    for f in a.get("frozenV2", []) or []:
        if isinstance(f, dict) and "amount" in f:
            frozen_total += f.get("amount", 0) / 1e6

    # USDT 余额
    usdt = 0
    for token in a.get("trc20", []) or []:
        if USDT_CONTRACT in token:
            try:
                usdt = int(token[USDT_CONTRACT]) / USDT_DECIMAL
            except: pass

    # 能量
    energy_used = 0
    energy_total = 0
    ar = a.get("account_resource", {}) or {}
    energy_used = ar.get("energy_usage", 0)
    if "frozenV2" in a:
        for f in a.get("frozenV2", []) or []:
            if f.get("type") == "ENERGY":
                energy_total += f.get("amount", 0) / 1e6
    # 净带宽
    net_used = a.get("net_usage", 0)
    net_total = a.get("net_window_size", 0)
    # 免费带宽
    free_used = a.get("free_net_usage", 0)
    free_total = 600

    # 权限
    owner_perm = a.get("owner_permission", {}) or {}
    active_perm = a.get("active_permission", []) or []
    owner_addr = owner_perm.get("keys", [{}])[0].get("address", "") if owner_perm else ""
    owner_weight = owner_perm.get("threshold", 1)
    active_addr = active_perm[0].get("keys", [{}])[0].get("address", "") if active_perm else ""
    active_weight = active_perm[0].get("threshold", 1) if active_perm else 1

    # 最近 USDT 交易笔数
    tx_d = _get(TRON_API + "/v1/accounts/" + address + "/transactions/trc20",
                {"limit": 50, "contract_address": USDT_CONTRACT})
    usdt_in = 0
    usdt_out = 0
    for tx in tx_d.get("data", []):
        try:
            if tx.get("to") == address: usdt_in += 1
            if tx.get("from") == address: usdt_out += 1
        except: pass

    lines = []
    lines.append("💼 全能AI助手 · 钱包查询")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("👤 账户类型：普通账户")
    lines.append("🔍 查询地址：" + address)
    lines.append("🕰 创建时间：" + create_time)
    lines.append("⏱ 最后活跃：" + last_op)
    lines.append("━━━ 资源 ━━━")
    lines.append("💰 TRX 余额：" + ("%.6f" % balance) + " TRX")
    lines.append("💰 TRX 质押：" + ("%.2f" % frozen_total) + " TRX")
    lines.append("💵 USDT 余额：" + ("%.6f" % usdt) + " USDT")
    lines.append("⚡ 能量：" + str(energy_used) + " / " + str(int(energy_total)))
    lines.append("🔋 质押带宽：" + str(net_used) + " / " + str(net_total))
    lines.append("🆓 免费带宽：" + str(free_used) + " / " + str(free_total))
    lines.append("━━━ 权限 ━━━")
    lines.append("👤 拥有者 (Owner) 权限")
    lines.append("  " + _short(owner_addr) + " (权重：" + str(owner_weight) + ")")
    lines.append("")
    lines.append("👤 活跃 (Active) 权限")
    lines.append("  " + _short(active_addr) + " (权重：" + str(active_weight) + ")")
    lines.append("━━━ 最近交易 ━━━")
    lines.append("📤 USDT 支出笔数：" + str(usdt_out))
    lines.append("📥 USDT 收入笔数：" + str(usdt_in))
    return "\n".join(lines)


def get_usdt_history(address, limit=10):
    """查 USDT 交易历史"""
    d = _get(TRON_API + "/v1/accounts/" + address + "/transactions/trc20",
             {"limit": limit, "contract_address": USDT_CONTRACT})
    if "_err" in d:
        return "❌ 网络错误：" + d["_err"]
    txs = d.get("data", [])
    if not txs:
        return "📭 暂无 USDT 交易记录"
    lines = ["📜 USDT 交易历史（最近 " + str(len(txs)) + " 笔）", "━━━━━━━━━━━━━━"]
    for i, tx in enumerate(txs, 1):
        try:
            amt = int(tx["value"]) / USDT_DECIMAL
            ts = _fmt_time(tx.get("block_timestamp"))
            frm = tx.get("from", "")
            to = tx.get("to", "")
            direction = "⬇️ 收入" if to == address else "⬆️ 支出"
            other = frm if to == address else to
            lines.append(str(i) + ". " + direction + " " + ("%.2f" % amt) + " USDT")
            lines.append("   " + ("from" if to == address else "to") + ": " + _short(other))
            lines.append("   🕐 " + ts)
            lines.append("")
        except: continue
    return "\n".join(lines)


def get_trx_history(address, limit=10):
    """查 TRX 交易历史"""
    d = _get(TRON_API + "/v1/accounts/" + address + "/transactions", {"limit": limit})
    if "_err" in d:
        return "❌ 网络错误：" + d["_err"]
    txs = d.get("data", [])
    if not txs:
        return "📭 暂无 TRX 交易记录"
    lines = ["💎 TRX 交易历史（最近 " + str(len(txs)) + " 笔）", "━━━━━━━━━━━━━━"]
    for i, tx in enumerate(txs, 1):
        try:
            txid = tx.get("txID", "")
            ts = _fmt_time(tx.get("block_timestamp"))
            status = tx.get("ret", [{}])[0].get("contractRet", "")
            contract = tx.get("raw_data", {}).get("contract", [{}])[0]
            ctype = contract.get("type", "")
            if ctype != "TransferContract":
                lines.append(str(i) + ". ⚙️ " + ctype + " · " + ("✅" if status == "SUCCESS" else "❌"))
                lines.append("   🕐 " + ts)
                lines.append("   🔗 " + txid[:16] + "...")
                lines.append("")
                continue
            params = contract.get("parameter", {}).get("value", {})
            amt = params.get("amount", 0) / 1e6
            frm = params.get("owner_address", "")
            to = params.get("to_address", "")
            direction = "⬇️ 收入" if to == address else "⬆️ 支出"
            other = frm if to == address else to
            lines.append(str(i) + ". " + direction + " " + ("%.6f" % amt) + " TRX")
            lines.append("   " + ("from" if to == address else "to") + ": " + _short(other))
            lines.append("   🕐 " + ts)
            lines.append("")
        except: continue
    return "\n".join(lines)


def get_tx_detail(txhash):
    """查单笔交易详情"""
    d = _get(TRON_API + "/v1/transactions/" + txhash)
    if "_err" in d:
        return "❌ 网络错误：" + d["_err"]
    if not d.get("data"):
        return "❌ 交易不存在"
    tx = d["data"][0]
    ts = _fmt_time(tx.get("blockTime") or (tx.get("raw_data", {}).get("timestamp")))
    status = tx.get("ret", [{}])[0].get("contractRet", "")
    contract = tx.get("raw_data", {}).get("contract", [{}])[0]
    ctype = contract.get("type", "")
    lines = ["🧾 交易详情", "━━━━━━━━━━━━━━"]
    lines.append("🔗 Hash：" + txhash[:20] + "...")
    lines.append("✅ 状态：" + ("成功" if status == "SUCCESS" else status))
    lines.append("🕐 时间：" + ts)
    lines.append("📋 类型：" + ctype)
    if ctype == "TransferContract":
        params = contract.get("parameter", {}).get("value", {})
        amt = params.get("amount", 0) / 1e6
        lines.append("💰 金额：" + ("%.6f" % amt) + " TRX")
        lines.append("📤 发送：" + _short(params.get("owner_address", "")))
        lines.append("📥 接收：" + _short(params.get("to_address", "")))
    return "\n".join(lines)
