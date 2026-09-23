# -*- coding: utf-8 -*-
"""SaaS 授权系统"""
import json, os, hashlib, datetime

LIC_FILE = "/root/AIbot/license.json"

def _sign(data):
    return hashlib.sha256((data + "SAFW_SECRET_2026").encode()).hexdigest()[:16]

def generate_license(owner, days=30, plan="basic"):
    exp = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    code = _sign(owner + exp + plan)
    lic = {
        "owner": owner,
        "expire_at": exp,
        "plan": plan,
        "sign": code,
    }
    with open(LIC_FILE, "w", encoding="utf-8") as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    return lic

def check_license():
    if not os.path.exists(LIC_FILE):
        return False, "未授权"
    try:
        with open(LIC_FILE, "r", encoding="utf-8") as f:
            lic = json.load(f)
    except:
        return False, "授权文件损坏"
    expected = _sign(lic.get("owner", "") + lic.get("expire_at", "") + lic.get("plan", ""))
    if lic.get("sign") != expected:
        return False, "授权签名无效"
    try:
        exp = datetime.datetime.strptime(lic["expire_at"], "%Y-%m-%d")
        if exp < datetime.datetime.now():
            return False, "授权已过期（" + lic["expire_at"] + "）"
    except:
        return False, "授权日期错误"
    return True, lic

def license_info():
    ok, info = check_license()
    if not ok:
        return "❌ " + info
    return "👑 授权信息\n━━━━━━━━━━━━\n客户：" + info["owner"] + "\n套餐：" + info["plan"] + "\n到期：" + info["expire_at"]
