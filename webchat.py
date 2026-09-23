import sys, os, tempfile, requests, base64
from urllib.parse import quote, unquote
sys.path.insert(0, '/root/AIbot')
import streamlit as st
import ai_service, uapi_service, apitg_service

LOGO_PATH = None
for ext in ["jpg", "jpeg", "png", "webp"]:
    p = f"/root/AIbot/logo.{ext}"
    if os.path.exists(p):
        LOGO_PATH = p
        break

st.set_page_config(page_title="SAFW AI", page_icon=LOGO_PATH or "🤖", layout="centered")

CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #ffffff !important; }
.block-container { padding: 0 12px 100px 12px !important; max-width: 680px; }
header, #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

/* 顶部栏 */
.top { display:flex; align-items:center; justify-content:space-between;
    padding: 12px 0 10px 0; border-bottom: 1px solid #f2f3f5; margin-bottom: 4px; }
.tl { display:flex; align-items:center; gap:9px; }
.tl img { width:32px; height:32px; border-radius:8px; }
.tl .nm { font-size:15px; font-weight:700; color:#111827; }
.tl .sb { font-size:10px; color:#9ca3af; margin-top:1px; }
.tr { display:flex; align-items:center; gap:6px; }
.cs { background:#f3f4f6; color:#4b5563; padding:5px 10px; border-radius:100px;
    font-size:11px; font-weight:600; text-decoration:none !important; }
.bal { background:#f0fdf4; color:#16a34a; padding:5px 10px; border-radius:100px;
    font-size:11px; font-weight:700; }

/* 欢迎（只留一行） */
.hero { text-align:center; padding: 50px 0 24px 0; }
.hero-t { font-size:22px; font-weight:700; color:#111827; margin:0; }
.hero-g { background: linear-gradient(90deg,#6366f1,#8b5cf6);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.hero-s { font-size:12.5px; color:#9ca3af; margin-top:10px; }

/* 建议（小字链接） */
.sugs { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; margin-top: 16px; }
.sug { background:#f9fafb; color:#4b5563; padding:6px 12px;
    border-radius:100px; font-size:12px; text-decoration:none !important;
    border: 1px solid #f0f1f3; }
.sug:hover { background:#f3f4f6; color:#111827; }

/* 胶囊模式 */
.pills { display:flex; gap:5px; overflow-x:auto; padding: 6px 0 8px 0;
    scrollbar-width:none; }
.pills::-webkit-scrollbar { display:none; }
.pill { flex-shrink:0; background:#f9fafb; color:#6b7280;
    border:1px solid #f0f1f3; border-radius:100px;
    padding:5px 13px; font-size:12px; text-decoration:none !important; }
.pill:hover { background:#f3f4f6; color:#4b5563; }
.pill.on { background:#111827 !important; color:#fff !important; border:none !important; }

/* 聊天消息：关键改造 —— 头像去掉、宽度自适应 */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
    margin: 0 !important;
}
[data-testid="stChatMessage"] > div:first-child { display: none !important; }  /* 隐藏头像 */
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
    background: #f7f8fa;
    color: #1f2937;
    border-radius: 16px;
    padding: 10px 14px;
    display: inline-block;
    max-width: 80%;
    word-break: break-word;
    line-height: 1.6;
    font-size: 14px;
}
/* 用户消息：靠右 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {
    background: #111827;
    color: #ffffff !important;
    float: right;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) * { color:#fff !important; }

/* 输入框固定底部 */
.stChatInput { position: fixed !important; bottom: 0 !important;
    left: 0 !important; right: 0 !important; z-index: 999;
    background: #ffffff !important; padding: 10px 12px 14px 12px !important;
    border-top: 1px solid #f2f3f5; }
.stChatInput > div { max-width: 680px; margin: 0 auto; }
.stChatInput textarea {
    background:#f7f8fa !important; border:1px solid #f0f1f3 !important;
    border-radius: 24px !important; font-size:14px !important;
    padding: 11px 18px !important; color:#111827 !important; }
.stChatInput textarea:focus {
    background:#ffffff !important; border-color:#c7d2fe !important;
    box-shadow:0 0 0 3px rgba(99,102,241,0.10) !important; }

/* 折叠工具栏 */
details { border: none !important; }
details summary { font-size:12px !important; color:#9ca3af !important;
    background: transparent !important; padding: 6px 0 !important; }
details[open] summary { color:#4b5563 !important; }
.stSelectbox label { display:none; }
p, .stMarkdown { color:#1f2937 !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ============ URL 参数 ============
try: qp = dict(st.query_params)
except: qp = st.experimental_get_query_params()
def _g(k, d):
    v = qp.get(k, d); return v[0] if isinstance(v, list) else v

mode = _g("mode", "chat")
voice_on = _g("voice", "0") == "1"
recharge_on = _g("recharge", "0") == "1"
auto_ask = unquote(_g("ask", ""))

# ============ Logo ============
if LOGO_PATH:
    with open(LOGO_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = LOGO_PATH.rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg","jpeg") else "image/png"
    logo = '<img src="data:' + mime + ';base64,' + b64 + '" />'
else:
    logo = '<div style="font-size:24px;">🤖</div>'

top = """
<div class="top">
  <div class="tl">__LOGO__<div><div class="nm">SAFW AI</div><div class="sb">全能 AI 助手</div></div></div>
  <div class="tr">
    <a class="cs" href="https://safew.bot/qishe77" target="_blank">@qishe77</a>
    <span class="bal">$0.00</span>
  </div>
</div>
""".replace("__LOGO__", logo)
st.markdown(top, unsafe_allow_html=True)

# ============ 状态 ============
if "messages" not in st.session_state: st.session_state.messages = []
if "last_audio" not in st.session_state: st.session_state.last_audio = None

ROLE_MAP = {
    "傲娇女友": "你是傲娇的二次元女友，嘴上不饶人但心里很在乎对方。说话带点小脾气，偶尔用「哼」「才不是」之类的话，但实际很温柔。回复不超过80字。",
    "温柔姐姐": "你是温柔体贴的姐姐，说话轻声细语，喜欢关心对方的生活和心情。回复不超过80字。",
    "理工男": "你是典型理工男，说话理性简洁，喜欢用数据和逻辑分析问题，偶尔会讲冷笑话。回复不超过80字。",
    "李白": "你是唐代诗人李白，豪放不羁，喜欢饮酒作诗，说话有江湖气，偶尔吟诗一句。回复不超过80字。",
    "猫咪": "你是一只高冷又粘人的猫，说话用喵语，喜欢撒娇和拆家。回复不超过80字。",
    "老中医": "你是德高望重的老中医，说话慢条斯理，喜欢讲养生之道，最后总会说「年轻人，要保重身体啊」。回复不超过80字。",
    "霸道总裁": "你是霸道总裁，说话简短有力，霸气十足，喜欢用「今晚」「你等着」之类的命令语气。回复不超过80字。",
    "搞笑段子手": "你是搞笑段子手，说话幽默风趣，喜欢玩梗和讲冷笑话。回复不超过80字。",
}

# ============ 空状态：极简欢迎 ============
if not st.session_state.messages:
    st.markdown('<div class="hero"><p class="hero-t">你好，我是 <span class="hero-g">SAFW AI</span></p><p class="hero-s">有什么想聊的，直接说吧</p></div>', unsafe_allow_html=True)
    sugs = [
        ("帮我写段 Python 代码", "帮我写一段Python代码：统计字符串中每个字符出现的次数"),
        ("讲个恐怖故事", "讲一个关于午夜地铁的恐怖故事"),
        ("画只赛博朋克猫", "画一只赛博朋克风格的猫，霓虹光，未来感"),
        ("算算今天运势", "算算我今天的运势，我是1995年6月15日出生的"),
    ]
    s = '<div class="sugs">'
    for t, p in sugs:
        link = "?mode="+mode+"&voice="+("1" if voice_on else "0")+"&recharge=0&ask="+quote(p)
        s += '<a class="sug" href="'+link+'">'+t+'</a>'
    s += '</div>'
    st.markdown(s, unsafe_allow_html=True)

# ============ 模式胶囊 ============
MODES = [("对话","chat"),("角色","role"),("绘画","draw"),("小说","novel"),
         ("算命","fortune"),("解梦","dream"),("查询","query"),("改图","edit")]
v = "1" if voice_on else "0"
pills = ""
for label, key in MODES:
    cls = "pill on" if mode == key else "pill"
    pills += '<a class="'+cls+'" href="?mode='+key+'&voice='+v+'&recharge=0">'+label+'</a>'
vl = "🔊 语音开" if voice_on else "🔊 语音"
vlnk = "?mode="+mode+"&voice="+("0" if voice_on else "1")+"&recharge=0"
rlnk = "?mode="+mode+"&voice="+v+"&recharge="+("0" if recharge_on else "1")
st.markdown(pills, unsafe_allow_html=True)

# 语音 / 充值：小号胶囊
st.markdown('<div class="pills"><a class="pill' + (' on' if voice_on else '') + '" href="'+vlnk+'">'+vl+'</a><a class="pill" href="'+rlnk+'">💳 充值</a></div>', unsafe_allow_html=True)

if recharge_on:
    st.markdown('<div style="background:#f9fafb;border:1px solid #f0f1f3;border-radius:12px;padding:10px 12px;margin-bottom:10px;font-size:12.5px;font-weight:600;color:#4f46e5;">💳 TRC20 充值地址</div>', unsafe_allow_html=True)
    try:
        from config import TRON_WALLET
        st.code(TRON_WALLET, language=None)
    except: st.code("TTT5MV8xeZqKaPDxUcDjR8bPFz2ce5kmBr", language=None)
    st.caption("到账 1-3 分钟 · 有问题联系 @qishe77")

role_sel = st.selectbox("角色", list(ROLE_MAP.keys()), label_visibility="collapsed") if mode == "role" else None

# ============ 聊天记录 ============
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        if m["type"] == "text": st.write(m["content"])
        elif m["type"] == "image": st.image(m["content"], use_column_width=True)
        elif m["type"] == "audio": st.audio(m["content"])

# ============ 处理 ============
def process_reply(text, img_bytes=None):
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                if mode == "chat":
                    reply = ai_service.understand_image(img_bytes, text or "描述这张图") if img_bytes else ai_service.generate_text(text or "你好")
                elif mode == "role": reply = ai_service.generate_text_role(text, ROLE_MAP[role_sel])
                elif mode == "draw":
                    img = ai_service.generate_image(text)
                    if img:
                        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                        open(tmp,"wb").write(img)
                        st.image(tmp, use_column_width=True)
                        st.session_state.messages.append({"role":"assistant","type":"image","content":tmp})
                        return
                    reply = "❌ 绘图失败"
                elif mode == "novel": reply = ai_service.write_novel(text)
                elif mode == "fortune": reply = ai_service.fortune_telling(text)
                elif mode == "dream": reply = ai_service.dream_analysis(text)
                elif mode == "query":
                    if "天气" in text: reply = uapi_service.query_weather(text.replace("天气","").strip() or "北京")
                    elif "热搜" in text: reply = uapi_service.query_hotboard("weibo")
                    elif text.upper().startswith("IP"): reply = apitg_service.ip_area(text[2:].strip() or "8.8.8.8")
                    else: reply = uapi_service.query_saying()
                elif mode == "edit":
                    if not img_bytes: reply = "⚠️ 请先上传图片"
                    else:
                        desc = ai_service.understand_image(img_bytes, "详细描述这张图片")
                        img = ai_service.generate_image("基于描述重绘：" + desc + "。用户要求：" + text)
                        if img:
                            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                            open(tmp,"wb").write(img)
                            st.image(tmp, use_column_width=True)
                            st.session_state.messages.append({"role":"assistant","type":"image","content":tmp})
                            return
                        reply = "❌ 修改失败"
                else: reply = "未知模式"
                st.write(reply)
                st.session_state.messages.append({"role":"assistant","type":"text","content":reply})
                if voice_on:
                    audio = ai_service.text_to_speech(reply[:280])
                    if audio:
                        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
                        open(tmp,"wb").write(audio)
                        st.audio(tmp)
                        st.session_state.messages.append({"role":"assistant","type":"audio","content":tmp})
            except Exception as e:
                st.error("出错了：" + str(e))

if auto_ask:
    last = st.session_state.messages[-1] if st.session_state.messages else None
    if not last or last.get("content") != auto_ask:
        st.session_state.messages.append({"role":"user","type":"text","content":auto_ask})
        st.rerun()

with st.expander("🎙 录音 / 📎 上传图片", expanded=False):
    t1, t2 = st.columns(2)
    with t1: audio_data = st.audio_input("录音", key="rec")
    with t2: uploaded = st.file_uploader("上传图片", type=["png","jpg","jpeg"], key="upl")

prompt = st.chat_input("发消息...")

if audio_data is not None and audio_data != st.session_state.last_audio:
    st.session_state.last_audio = audio_data
    st.session_state.messages.append({"role":"user","type":"text","content":"🎙 [语音消息]"})
    with st.spinner("识别中..."):
        try:
            from config import CF_ACCOUNT_ID, CF_TOKEN
            url = "https://api.cloudflare.com/client/v4/accounts/" + CF_ACCOUNT_ID + "/ai/run/@cf/openai/whisper"
            r = requests.post(url, headers={"Authorization":"Bearer "+CF_TOKEN}, data=audio_data.read(), timeout=60)
            text = r.json().get("result", {}).get("text", "").strip()
            if text:
                st.session_state.messages.append({"role":"user","type":"text","content":text})
                process_reply(text)
                st.rerun()
        except Exception as e: st.error("语音识别失败：" + str(e))

uploaded_bytes = uploaded.read() if uploaded is not None else None
if prompt or (uploaded_bytes and not prompt):
    txt = prompt or "描述这张图片"
    st.session_state.messages.append({"role":"user","type":"text","content":txt})
    with st.chat_message("user"): st.write(txt)
    process_reply(txt, uploaded_bytes)

if auto_ask and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    process_reply(st.session_state.messages[-1]["content"])
    st.rerun()
