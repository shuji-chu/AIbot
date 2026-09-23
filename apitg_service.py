import requests
APITG_KEY = "sk_M5RMaXgQ95qdnJiUQwoomF8wS02dfiUm"
BASE = "http://www.apitg.net/api/"
SEP = "━━━━━━━━━━━━━━"
NL = chr(10)

def _call(params):
    p = {"key": APITG_KEY}; p.update(params)
    try: return requests.post(BASE, data=p, timeout=60).json()
    except Exception as e: return {"code": 500, "msg": "请求异常:" + str(e)[:60]}

def _kv(d, keys):
    lines = []
    for k, label in keys:
        v = d.get(k)
        if v not in (None, "", []):
            lines.append(label + "：" + str(v))
    return NL.join(lines)

def ip_area(ip):
    d = _call({"id": 10, "ip": ip})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "🌐 IP归属地" + NL + SEP + NL + _kv(r, [
        ("ip","📍 IP"),("location","🗺 地区"),("Digitaladdress","🔢 数字地址")])


def site_tdk(url):
    if not url.startswith("http"): url = "http://" + url
    d = _call({"id": 17, "url": url}); r = d.get("data", {})
    return "📌 网站TDK" + NL + SEP + NL + _kv(r, [
        ("title","标题"),("description","描述"),("keywords","关键词"),
        ("url","URL"),("icp","ICP")])


def icp_query(domain):
    d = _call({"id": 1, "domain": domain})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "📋 ICP备案" + NL + SEP + NL + _kv(r, [
        ("name","单位"),("icp","备案号"),("domain","域名"),
        ("type","性质"),("date","审核时间")])


def whois_query(domain):
    d = _call({"id": 16, "domain": domain}); r = d.get("data", {})
    return "🌐 WHOIS" + NL + SEP + NL + _kv(r, [
        ("domain","域名"),("registrars","注册商"),("Registration_Time","注册时间"),
        ("Expiration_Time","到期时间"),
        ("dns","DNS"),("domain_Status","状态")])


def icp_unit(name):
    d = _call({"id": 36, "name": name}); r = d.get("data", {})
    return "🏢 主办单位" + NL + SEP + NL + _kv(r, [
        ("name","名称"),("count","备案数"),("list","详情")])

def baidu_index(domain):
    d = _call({"id": 49, "domain": domain}); r = d.get("data", {})
    return "📊 百度收录" + NL + SEP + NL + _kv(r, [
        ("domain","域名"),("count","收录量"),("today","今日")])

def baidu_weight(domain):
    d = _call({"id": 50, "domain": domain}); r = d.get("data", {})
    return "📊 百度权重" + NL + SEP + NL + _kv(r, [
        ("domain","域名"),("Br","BR"),("Kw_count","关键词数"),
        ("Uv_count","预估流量"),("Up_date","更新时间")])


def qq_block(url):
    d = _call({"id": 12, "url": url}); r = d.get("data", {})
    return "🛡 QQ域名拦截" + NL + SEP + NL + _kv(r, [
        ("url","URL"),("status","状态"),("msg","说明")])

def wx_block(url):
    d = _call({"id": 13, "url": url}); r = d.get("data", {})
    return "🛡 微信域名拦截" + NL + SEP + NL + _kv(r, [
        ("url","URL"),("status","状态"),("msg","说明")])

def phone_area(phone):
    d = _call({"id": 15, "phone": phone}); r = d.get("data", {})
    return "📱 手机归属地" + NL + SEP + NL + _kv(r, [
        ("phone","号码"),("province","省份"),("city","城市"),
        ("sp","运营商"),("code","区号"),("postcode","邮编")])

def phone_two(name, phone):
    d = _call({"id": 8, "name": name, "phone": phone})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    s = {"1": "✅ 一致", "2": "❌ 不一致", "3": "⚠️ 异常"}.get(str(r.get("state", "")), "未知")
    return "📱 手机二要素" + NL + SEP + NL + "👤 " + name + NL + "📞 " + phone + NL + \
        "📊 结果：" + s + NL + _kv(r, [
        ("new_yys","当前运营商"),("old_yys","原运营商"),("is_xhzw","携号转网")])

def phone_three(name, phone, idcard):
    d = _call({"id": 20, "name": name, "phone": phone, "idcard": idcard})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    s = {"1": "✅ 一致", "2": "❌ 不一致", "3": "⚠️ 异常"}.get(str(r.get("state", "")), "未知")
    return "📱 手机三要素" + NL + SEP + NL + "👤 " + name + NL + "📞 " + phone + NL + \
        "📊 结果：" + s + NL + _kv(r, [
        ("new_yys","当前运营商"),("old_yys","原运营商"),("is_xhzw","携号转网")])

def phone_status(phone):
    d = _call({"id": 6, "phone": phone}); r = d.get("data", {})
    return "📱 在网状态" + NL + SEP + NL + _kv(r, [
        ("phone","号码"),("yys","运营商"),("guishu","归属地"),
        ("status","状态码"),("status_msg","状态")])

def phone_age(phone):
    d = _call({"id": 37, "phone": phone}); r = d.get("data", {})
    return "📱 使用时长" + NL + SEP + NL + _kv(r, [
        ("phone","号码"),("age","时长"),("start","开卡时间"),("status","状态")])

def phone_balance(phone):
    d = _call({"id": 5, "phone": phone}); r = d.get("data", {})
    return "💰 话费余额" + NL + SEP + NL + _kv(r, [
        ("phone","号码"),("yys","运营商"),("balance","余额"),("status","状态")])

def idcard_area(idcard):
    d = _call({"id": 14, "idcard": idcard}); r = d.get("data", {})
    return "🆔 身份证归属地" + NL + SEP + NL + _kv(r, [
        ("idcard","号码"),("province","省份"),("city","城市"),
        ("district","区县"),("birthday","出生日期"),("sex","性别"),("age","年龄")])

def idcard_real(name, idcard):
    d = _call({"id": 4, "name": name, "idcard": idcard})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    s = {"1": "✅ 一致", "2": "❌ 不一致", "3": "⚠️ 异常"}.get(str(r.get("status", "")), "未知")
    return "🆔 身份证实名" + NL + SEP + NL + "👤 " + name + NL + \
        "🆔 " + idcard[:6] + "****" + idcard[-4:] + NL + "📊 结果：" + s

def bank_area(cardno):
    d = _call({"id": 23, "cardno": cardno}); r = d.get("data", {})
    return "💳 银行卡归属地" + NL + SEP + NL + _kv(r, [
        ("cardno","卡号"),("bank","银行"),("area","地区"),
        ("cardType","卡类型"),("bin","BIN")])

def car_5(chepai):
    d = _call({"id": 2, "chepai": chepai})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "🚗 车牌五项" + NL + SEP + NL + "🚙 " + chepai + NL + _kv(r, [
        ("vin","VIN"),("brand","品牌"),("model","车型"),
        ("registerDate","初登日期"),("useNature","使用性质"),("engine","发动机号")])

def car_plate(chepai):
    d = _call({"id": 7, "chepai": chepai})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "🚗 车牌解析" + NL + SEP + NL + "🚙 " + chepai + NL + _kv(r, [
        ("name","品牌"),("name_info","车型"),("vin","VIN"),
        ("date","初登"),("pailiang","排量"),("max_horsepower","马力"),
        ("max_power","功率"),("fuel_type","燃油"),("drivemode","驱动"),
        ("gear_type","变速箱"),("environmentalstandards","排放"),
        ("market_price","市场价"),("seat_num","座位"),("door_num","车门")])

def vin_query(vin):
    d = _call({"id": 11, "vin": vin}); r = d.get("data", {})
    return "🚗 VIN解析" + NL + SEP + NL + _kv(r, [
        ("vin","VIN"),("brand","品牌"),("model","车型"),
        ("year","年款"),("displacement","排量"),("engine","发动机"),
        ("fuel","燃料"),("body","车身"),("country","产地")])

def car_insurance(value):
    d = _call({"id": 34, "value": value}); r = d.get("data", {})
    return "🚗 上险信息" + NL + SEP + NL + _kv(r, [
        ("value","号码"),("count","保险数"),("list","记录")])

def car_transfer(value):
    d = _call({"id": 29, "value": value}); r = d.get("data", {})
    return "🔄 车辆过户" + NL + SEP + NL + _kv(r, [
        ("value","号码"),("count","过户次数"),("list","记录")])

def company_name(page, kw):
    d = _call({"id": 51, "page": page, "keyword": kw}); r = d.get("data", {})
    return "🏢 企业名称查询" + NL + SEP + NL + "📌 " + kw + NL + _kv(r, [
        ("count","数量"),("list","列表")])

def company_fuzzy(page, kw):
    d = _call({"id": 52, "page": page, "keyword": kw}); r = d.get("data", {})
    return "🏢 工商模糊" + NL + SEP + NL + "📌 " + kw + NL + _kv(r, [
        ("count","数量"),("list","列表")])

def company_std(name):
    d = _call({"id": 53, "name": name})
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "🏢 企业工商" + NL + SEP + NL + _kv(r, [
        ("name","企业名"),("legalPerson","法人"),("regCapital","注册资本"),
        ("estiblishTime","成立日期"),("regStatus","状态"),("industry","行业"),
        ("regNumber","注册号"),("creditCode","统一信用代码"),
        ("address","地址"),("businessScope","经营范围")])

def company_record(idcard, name=None):
    p = {"id": 60, "idcard": idcard}
    if name: p["name"] = name
    d = _call(p)
    if d.get("code") != 200: return "❌ " + str(d.get("msg", ""))
    r = d.get("data", {})
    return "🏢 企业任职" + NL + SEP + NL + _kv(r, [
        ("person_name","姓名"),("totalCount","关联企业数"),
        ("cancelCount","已注销"),("legalPersonCount","担任法人"),
        ("list","企业列表")])

def shixin(name, idcard=None):
    p = {"id": 45, "name": name}
    if idcard: p["idcard"] = idcard
    d = _call(p); r = d.get("data", {})
    if r.get("status") == 2: return "✅ " + name + " 未命中失信名单"
    lst = r.get("list", [])
    if not lst: return "❌ 无记录"
    f = lst[0]
    return "🚨 失信被执行人" + NL + SEP + NL + _kv(r, [("name","姓名")]) + NL + _kv(f, [
        ("sex","性别"),("age","年龄"),("province","省份"),
        ("caseno","案号"),("filingdate","立案时间"),("court","法院"),
        ("baseonno","执行依据"),("duty","义务"),("performance","履行情况"),
        ("description","失信情形"),("pubdate","发布时间")])

def xiangao(name, idcard=None):
    p = {"id": 44, "name": name}
    if idcard: p["idcard"] = idcard
    d = _call(p); r = d.get("data", {})
    if r.get("status") == 2: return "✅ " + name + " 未命中限高"
    return "🚫 限高消费" + NL + SEP + NL + _kv(r, [
        ("name","姓名"),("list","记录")])

def judicial(name, idcard):
    d = _call({"id": 62, "name": name, "idcard": idcard}); r = d.get("data", {})
    return "⚖️ 司法综合" + NL + SEP + NL + "👤 " + name + NL + _kv(r, [
        ("shixin_count","失信被执行人"),("zhixing_count","被执行人"),
        ("kaiting_count","开庭公告"),("gonggao_count","法院公告"),
        ("wenshu_count","裁判文书"),("liucheng_count","审判流程")])

def bad_record(name, idcard):
    d = _call({"id": 40, "name": name, "idcard": idcard}); r = d.get("data", {})
    return "📋 不良记录" + NL + SEP + NL + "👤 " + name + NL + _kv(r, [
        ("status","结果"),("list","明细")])

def express(number):
    d = _call({"id": 61, "number": number}); r = d.get("data", {})
    tracks = r.get("list", [])
    lines = [str(t.get("time", "")) + "  " + str(t.get("context", "")) for t in tracks[:8]]
    return "📦 快递物流" + NL + SEP + NL + _kv(r, [
        ("number","单号"),("company","快递公司"),("status","状态")]) + NL + SEP + NL + \
        (NL.join(lines) if lines else "暂无轨迹")

def exchange(money, from_code):
    d = _call({"id": 56, "money": money, "from_Code": from_code}); r = d.get("data", {})
    return "💱 汇率转换" + NL + SEP + NL + _kv(r, [
        ("from","原币"),("to","目标币"),("money","金额"),
        ("rate","汇率"),("result","结果")])

def lottery(type_):
    d = _call({"id": 58, "type": type_}); r = d.get("data", {})
    return "🎰 彩票开奖" + NL + SEP + NL + _kv(r, [
        ("type","类型"),("issue","期号"),("number","号码"),
        ("date","开奖日期"),("sales","销量")])
