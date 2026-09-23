# ==================== 身份加载（必须放最前）====================
def _load_identity():
    try:
        with open("/root/AIbot/identity.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "你是SAFW AI智能助手。"

IDENTITY = _load_identity()


import requests, base64, time, random
from config import (MODELSCOPE_KEY, MODELSCOPE_BASE, MODELSCOPE_DRAW_MODEL,
                    AGNES_TOKEN, ZHIPU_KEY, ZHIPU_BASE, ZHIPU_DRAW_MODEL, ZHIPU_VIDEO_MODEL)

NL = chr(10)
CF_ACCOUNT_ID = "39fba5c84e10f7f4c1cceab74dd9ec95"
CF_TOKEN = "cfut_JXFZCK4WwaOZE2U7lwOPCDrl8fBwcpaUTHcc56wb69765f01"

def generate_image(prompt, size="1024x1024"):
    try:
        url = MODELSCOPE_BASE + "/images/generations"
        headers = {"Authorization": "Bearer " + MODELSCOPE_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json={"model": MODELSCOPE_DRAW_MODEL, "prompt": prompt, "n": 1, "size": size}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            if "data" in d and d["data"]:
                f = d["data"][0]
                if f.get("url"): return requests.get(f["url"], timeout=60).content
                if f.get("b64_json"): return base64.b64decode(f["b64_json"])
            tid = d.get("task_id")
            if tid:
                for _ in range(30):
                    time.sleep(2)
                    cr = requests.get(MODELSCOPE_BASE + "/tasks/" + str(tid), headers=headers, timeout=15)
                    if cr.status_code != 200: continue
                    cd = cr.json()
                    if cd.get("task_status") == "SUCCEED":
                        outs = cd.get("outputs") or []
                        if outs:
                            o = outs[0]
                            u = o.get("url") if isinstance(o, dict) else o
                            if u: return requests.get(u, timeout=60).content
                    elif cd.get("task_status") == "FAILED": break
    except Exception as e: print("⚠️ MS:" + str(e)[:80])

    try:
        url = ZHIPU_BASE + "/images/generations"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json={"model": ZHIPU_DRAW_MODEL, "prompt": prompt, "size": size}, timeout=60)
        if r.status_code == 200:
            print("✅ 智谱")
            return requests.get(r.json()["data"][0]["url"], timeout=60).content
    except Exception as e: print("⚠️ 智谱:" + str(e)[:80])

    try:
        url = "https://api.cloudflare.com/client/v4/accounts/" + CF_ACCOUNT_ID + "/ai/run/@cf/black-forest-labs/flux-1-schnell"
        r = requests.post(url, headers={"Authorization": "Bearer " + CF_TOKEN}, json={"prompt": prompt}, timeout=60)
        if r.status_code == 200:
            ct = r.headers.get("Content-Type", "")
            if "application/json" in ct:
                b64 = r.json().get("result", {}).get("image")
                if b64: return base64.b64decode(b64)
            else:
                print("✅ CF")
                return r.content
    except Exception as e: print("⚠️ CF:" + str(e)[:80])

    try:
        url = "https://apihub.agnes-ai.com/v1/images/generations"
        r = requests.post(url, headers={"Authorization": "Bearer " + AGNES_TOKEN, "Content-Type": "application/json"},
            json={"model": "agnes-image-2.1-flash", "prompt": prompt, "n": 1, "size": "1024x1024"}, timeout=120)
        return requests.get(r.json()["data"][0]["url"], timeout=60).content
    except Exception as e:
        print("❌ 全部失败:" + str(e)[:80]); return None

def generate_image_4(prompt):
    out = []
    for _ in range(4):
        img = generate_image(prompt)
        if img: out.append(img)
    return out

def generate_image_edit(prompt, img_bytes):
    try:
        b64 = base64.b64encode(img_bytes).decode()
        url = "https://apihub.agnes-ai.com/v1/images/generations"
        r = requests.post(url, headers={"Authorization": "Bearer " + AGNES_TOKEN, "Content-Type": "application/json"},
            json={"model": "agnes-image-2.5-flash", "prompt": prompt, "image": ["data:image/jpeg;base64," + b64], "size": "1K", "ratio": "1:1"}, timeout=180)
        return requests.get(r.json()["data"][0]["url"], timeout=60).content
    except Exception as e:
        print("❌ 图生图:" + str(e)[:80]); return None

def generate_video(prompt):
    try:
        url = ZHIPU_BASE + "/videos/generations"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json={"model": ZHIPU_VIDEO_MODEL, "prompt": prompt}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            tid = d.get("id") or d.get("task_id") or d.get("request_id")
            if tid:
                for _ in range(60):
                    time.sleep(3)
                    cr = requests.get(ZHIPU_BASE + "/async-result/" + str(tid), headers=headers, timeout=15)
                    if cr.status_code != 200: continue
                    cd = cr.json()
                    st = cd.get("task_status", "")
                    if st in ("SUCCESS", "SUCCEED"):
                        vs = cd.get("video_result") or cd.get("data") or []
                        if vs:
                            v = vs[0]
                            return v.get("url") if isinstance(v, dict) else v
                    elif st == "FAIL": break
    except Exception as e: print("⚠️ 视频:" + str(e)[:80])
    return None

def convert_video_to_gif(video_bytes):
    import subprocess, tempfile, os
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f: f.write(video_bytes); ip = f.name
        op = ip.replace(".mp4", ".gif")
        subprocess.run(["ffmpeg", "-y", "-i", ip, "-t", "3", "-vf", "fps=12,scale=480:-1", op], capture_output=True, timeout=120)
        if os.path.exists(op):
            with open(op, "rb") as f: b = f.read()
            os.unlink(ip); os.unlink(op); return b
        os.unlink(ip); return None
    except Exception as e: print("❌ GIF:" + str(e)[:80]); return None

def smart_draw(prompt, size="1024x1024"):
    return generate_image(prompt, size=size)


# ============================================================
#                    对话（智谱优先）
# ============================================================
def generate_text(msg, history=None):
    SYS = "你是全能AI助手，面向国内用户，说话自然简短，只用简体中文，严禁繁体字。"
    messages = [{"role": "system", "content": SYS}]
    if history:
        for u, a in history:
            messages.append({"role": "user", "content": u})
            messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": msg})

    try:
        url = ZHIPU_BASE + "/chat/completions"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers,
                          json={"model": "glm-4-flash", "messages": messages}, timeout=60)
        if r.status_code == 200:
            print("✅ [对话] 智谱")
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("⚠️ 智谱对话：" + str(e)[:80])

    try:
        url = MODELSCOPE_BASE + "/chat/completions"
        headers = {"Authorization": "Bearer " + MODELSCOPE_KEY, "Content-Type": "application/json"}
        r = requests.post(url, headers=headers,
                          json={"model": "Qwen/Qwen2.5-7B-Instruct", "messages": messages}, timeout=60)
        if r.status_code == 200:
            print("✅ [对话] ModelScope")
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("⚠️ MS对话：" + str(e)[:80])

    try:
        url = ("https://api.cloudflare.com/client/v4/accounts/" + CF_ACCOUNT_ID +
               "/ai/run/@cf/meta/llama-3.1-8b-instruct")
        r = requests.post(url, headers={"Authorization": "Bearer " + CF_TOKEN},
                          json={"messages": messages}, timeout=60)
        if r.status_code == 200:
            return r.json()["result"]["response"]
    except:
        pass

    return "抱歉，AI暂时不可用。"


# ==================== 多平台 AI 能力 (自动添加) ====================
def generate_text_zhipu(msg, history=None):
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE, ZHIPU_TEXT_MODEL
    url = ZHIPU_BASE + "/chat/completions"
    headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
    messages = [{"role": "system", "content": IDENTITY}]
    if history: messages.extend(history)
    messages.append({"role": "user", "content": msg})
    payload = {"model": ZHIPU_TEXT_MODEL, "messages": messages, "temperature": 0.7}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "智谱API异常: " + str(e)

def generate_text_cf(msg, history=None):
    import requests
    from config import CF_BASE, CF_TOKEN, CF_TEXT_MODEL
    url = CF_BASE + "/" + CF_TEXT_MODEL
    headers = {"Authorization": "Bearer " + CF_TOKEN}
    messages = [{"role": "system", "content": IDENTITY}]
    if history: messages.extend(history)
    messages.append({"role": "user", "content": msg})
    payload = {"messages": messages}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        return r.json()["result"]["response"]
    except Exception as e:
        return "Cloudflare API异常: " + str(e)

def generate_image_agnes(prompt):
    import requests
    from config import AGNES_BASE, AGNES_TOKEN, AGNES_IMAGE_MODEL
    url = AGNES_BASE + "/images/generations"
    headers = {"Authorization": "Bearer " + AGNES_TOKEN, "Content-Type": "application/json"}
    payload = {"model": AGNES_IMAGE_MODEL, "prompt": prompt, "n": 1, "size": "1024x1024"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        data = r.json()
        if "data" in data and len(data["data"]) > 0:
            img_url = data["data"][0].get("url", "")
            if img_url:
                return requests.get(img_url, timeout=60).content
    except Exception as e:
        print("Agnes绘图异常: " + str(e))
    return None

def generate_video_agnes(prompt, seconds="5"):
    import requests, time
    from config import AGNES_BASE, AGNES_TOKEN, AGNES_VIDEO_MODEL
    url = AGNES_BASE + "/videos"
    headers = {"Authorization": "Bearer " + AGNES_TOKEN, "Content-Type": "application/json"}
    payload = {"model": AGNES_VIDEO_MODEL, "prompt": prompt, "seconds": seconds, "mode": "text", "size": "720P", "aspect_ratio": "16:9"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        j = r.json()
        video_id = j.get("id") or j.get("video_id")
        if not video_id:
            return None, "任务创建失败: " + str(j)[:200]
        for _ in range(90):
            time.sleep(2)
            try:
                res = requests.get("https://apihub.agnes-ai.com/agnesapi",
                                   params={"video_id": video_id, "model_name": AGNES_VIDEO_MODEL},
                                   headers=headers, timeout=10).json()
                status = res.get("status")
                if status == "completed":
                    return res.get("metadata", {}).get("url"), None
                elif status == "failed":
                    return None, "生成失败: " + str(res)[:200]
            except Exception:
                continue
        return None, "生成超时"
    except Exception as e:
        return None, "Agnes视频异常: " + str(e)


# ==================== Edge TTS ====================
def text_to_speech(text, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
    """使用 Edge TTS 将文本转为语音（mp3 bytes）"""
    import asyncio, os, tempfile
    try:
        import edge_tts
    except ImportError:
        print("edge-tts 未安装")
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        async def _run():
            comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
            await comm.save(tmp.name)
        asyncio.run(_run())
        with open(tmp.name, "rb") as f:
            data = f.read()
        os.unlink(tmp.name)
        return data
    except Exception as e:
        print("EdgeTTS异常: " + str(e)[:100])
        return None


def generate_text_role(msg, system_prompt):
    """按指定角色系统提示词回复（智谱 glm-4-flash）"""
    import requests
    try:
        from config import ZHIPU_KEY, ZHIPU_BASE
        model = "glm-4-flash"
    except ImportError:
        model = "glm-4-flash"
        ZHIPU_KEY = globals().get("ZHIPU_KEY", "")
        ZHIPU_BASE = globals().get("ZHIPU_BASE", "https://open.bigmodel.cn/api/paas/v4")
    url = ZHIPU_BASE + "/chat/completions"
    headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": msg},
        ],
        "temperature": 0.9,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "角色回复失败：" + str(e)[:100]


# ==================== 趣味玩法 ====================
def fortune_telling(birthday, question=""):
    """AI 算命"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = "你是一位精通八字、星座、塔罗的命理大师。用轻松幽默但有点玄学味道的语气解读，不超过200字。"
    user_p = f"生日：{birthday}。想问：{question or '整体运势'}。请给出一段命运解读。"
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
            headers={"Authorization": "Bearer " + ZHIPU_KEY},
            json={"model": "glm-4-flash", "messages": [
                {"role":"system","content":sys_p},
                {"role":"user","content":user_p}], "temperature": 0.9},
            timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "算命失败：" + str(e)[:100]

def dream_analysis(dream):
    """AI 解梦"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = "你是弗洛伊德风格的梦境解析师，结合心理学和象征意义解读梦境，语气神秘但不吓人，不超过200字。"
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
            headers={"Authorization": "Bearer " + ZHIPU_KEY},
            json={"model": "glm-4-flash", "messages": [
                {"role":"system","content":sys_p},
                {"role":"user","content":"我梦见：" + dream}], "temperature": 0.9},
            timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "解梦失败：" + str(e)[:100]

def tell_story(topic, style="温馨"):
    """AI 讲一个短故事（用于 TTS 朗读，控制在 300 字内）"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = f"你是擅长讲{style}短故事的作家。写一个约250字的小故事，有反转、有画面感，适合朗读。"
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
            headers={"Authorization": "Bearer " + ZHIPU_KEY},
            json={"model": "glm-4-flash", "messages": [
                {"role":"system","content":sys_p},
                {"role":"user","content":"主题：" + topic}], "temperature": 0.95},
            timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "故事生成失败：" + str(e)[:100]


def understand_image(image_bytes, question="描述这张图片"):
    """智谱 GLM-4V 图片理解"""
    import requests, base64
    from config import ZHIPU_KEY, ZHIPU_BASE
    b64 = base64.b64encode(image_bytes).decode()
    url = ZHIPU_BASE + "/chat/completions"
    headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
    payload = {
        "model": "glm-4v-flash",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": b64}}
            ]
        }]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "图片理解失败：" + str(e)[:100]


def write_novel(topic):
    """写小说（分段生成，2000字左右）"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = "你是经验丰富的小说家。写一个约2000字的短篇小说，起承转合完整，情节引人入胜，人物鲜明，结尾有反转或余韵。"
    url = ZHIPU_BASE + "/chat/completions"
    headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": "主题：" + topic}
        ],
        "temperature": 0.95,
        "max_tokens": 4096
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "小说生成失败：" + str(e)[:100]


# ==================== 持久记忆 / 联网 / 链接抓取 ====================
import json as _json2
import os as _os2

HIST_DIR = "/root/AIbot/histories"
_os2.makedirs(HIST_DIR, exist_ok=True)

def load_history(uid):
    f = _os2.path.join(HIST_DIR, str(uid) + ".json")
    if not _os2.path.exists(f): return []
    try:
        with open(f, "r", encoding="utf-8") as fp:
            return _json2.load(fp)
    except: return []

def save_history(uid, history):
    f = _os2.path.join(HIST_DIR, str(uid) + ".json")
    try:
        with open(f, "w", encoding="utf-8") as fp:
            _json2.dump(history[-30:], fp, ensure_ascii=False)
    except Exception as e:
        print("save_history失败: " + str(e)[:80])

def clear_history(uid):
    f = _os2.path.join(HIST_DIR, str(uid) + ".json")
    if _os2.path.exists(f):
        try: _os2.remove(f)
        except: pass
    return True

def generate_text_with_memory(uid, user_msg, system_prompt=IDENTITY):
    """带长期记忆的对话"""
    import requests
    try:
        from config import ZHIPU_KEY, ZHIPU_BASE
        url = ZHIPU_BASE + "/chat/completions"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        hist = load_history(uid)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(hist[-20:])
        messages.append({"role": "user", "content": user_msg})
        payload = {"model": "glm-4-flash", "messages": messages, "temperature": 0.7}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        reply = r.json()["choices"][0]["message"]["content"]
        hist.append({"role": "user", "content": user_msg})
        hist.append({"role": "assistant", "content": reply})
        save_history(uid, hist)
        return reply
    except Exception as e:
        return "对话失败：" + str(e)[:100]

def generate_text_with_search(query, system_prompt=IDENTITY + "\\n\\n需要联网时先搜索再回答。"):
    """联网搜索对话"""
    import requests
    try:
        from config import ZHIPU_KEY, ZHIPU_BASE
        url = ZHIPU_BASE + "/chat/completions"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        payload = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "tools": [{"type": "web_search", "web_search": {"enable": True}}],
            "temperature": 0.7
        }
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        data = r.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        return "搜索失败：" + str(data)[:120]
    except Exception as e:
        return "搜索失败：" + str(e)[:100]

def summarize_url(url):
    """抓取链接正文并让 AI 总结"""
    import requests
    from bs4 import BeautifulSoup
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        # 去掉脚本样式
        for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
            s.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = soup.get_text(separator="\n", strip=True)
        text = "\n".join([l for l in text.split("\n") if len(l) > 5])[:3500]
        if not text:
            return "❌ 无法抓取页面内容"
        # 让 AI 总结
        import requests as _rq
        from config import ZHIPU_KEY, ZHIPU_BASE
        prompt = "请用中文简要总结以下网页内容，200字以内：\n\n标题：" + title + "\n\n正文：\n" + text
        payload = {
            "model": "glm-4-flash",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5
        }
        url_api = ZHIPU_BASE + "/chat/completions"
        headers2 = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        resp = _rq.post(url_api, headers=headers2, json=payload, timeout=60)
        summary = resp.json()["choices"][0]["message"]["content"]
        return "📄 " + (title[:40] if title else url[:40]) + "\n" + "━━━━━━━━━━━━" + "\n" + summary
    except Exception as e:
        return "❌ 链接处理失败：" + str(e)[:100]




# ==================== 趣味功能（免费）====================
def _zhipu_simple(system, user, temp=0.9):
    import requests
    try:
        from config import ZHIPU_KEY, ZHIPU_BASE
        url = ZHIPU_BASE + "/chat/completions"
        headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
        payload = {"model": "glm-4-flash", "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], "temperature": temp}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ " + str(e)[:100]

def tarot_reading(question=""):
    s = "你是塔罗牌占卜师。用户提问后，随机抽取3张牌（大阿卡纳），每张牌给出正/逆位，简洁解读，最后给一句总建议。不超过200字。"
    u = "我的问题：" + (question or "今天的运势")
    return _zhipu_simple(s, u)

def horoscope(sign):
    s = "你是星座运势专家，用轻松有趣的语气写今日运势，包含爱情/事业/财运，最后给一句幸运提示。不超过150字。"
    return _zhipu_simple(s, "写" + sign + "今天的运势")

def love_words():
    return _zhipu_simple("你是浪漫情话大师，写一句简短走心的情话，不要超过30字。", "来一句情话", 1.1)

def acrostic_poem(word):
    s = "你是诗人。用户给一个词，你写一首藏头诗，每句首字连起来就是那个词。要求押韵、有意境。"
    return _zhipu_simple(s, "藏头：" + word)

def ai_name(kind):
    s = "你是起名大师，给出5个有寓意、好听的名字，每个名字带简短寓意。"
    return _zhipu_simple(s, "帮我给" + kind + "起名")

def translate_text(lang, text):
    s = "你是专业翻译。用户指定目标语言，你只输出翻译结果，不要解释。"
    return _zhipu_simple(s, "翻译成" + lang + "：" + text)

def roast_words(target):
    s = "你是搞笑毒舌段子手，吐槽要幽默但不伤人，不超过80字。"
    return _zhipu_simple(s, "吐槽一下：" + target)

def brain_riddle():
    s = "你出一个中文脑筋急转弯，然后给出答案。"
    return _zhipu_simple(s, "来一个脑筋急转弯", 1.0)

def couple_match(a, b):
    s = "你是搞笑配对大师，根据两人名字编一个有趣的配对指数和点评。"
    return _zhipu_simple(s, "配对：" + a + " 和 " + b, 1.0)


# ==================== 拍照识别 / 风格 / 帮写 ====================
def recognize_image(img_bytes, hint=""):
    """拍照智能识别：自动判断是文字/名片/菜单/物体"""
    import requests, base64
    from config import ZHIPU_KEY, ZHIPU_BASE
    b64 = base64.b64encode(img_bytes).decode()
    sys_p = """你是图像识别专家。用户发图片时，自动判断类型并输出对应结果：
- 如果图中有文字 → 完整提取文字（OCR）
- 如果是名片 → 提取姓名、电话、公司、职位、邮箱
- 如果是菜单/商品 → 列出菜名/商品及价格
- 如果是发票 → 提取金额、号码、日期
- 如果是外文 → 翻译成中文
- 如果是普通图片 → 详细描述内容和场景
输出简洁整齐，中文回复，不加废话。"""
    user_text = hint if hint else "识别这张图片"
    payload = {
        "model": "glm-4v-flash",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": b64}}
            ]
        }]
    }
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"},
                          json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ 识别失败：" + str(e)[:100]


def style_transfer(img_bytes, style):
    """风格转换：先识别图片内容，再用指定风格重绘"""
    desc = understand_image(img_bytes, "详细描述这张图片的内容、主体、场景、构图")
    style_map = {
        "动漫": "anime style, Japanese animation, cel shading, vibrant colors",
        "油画": "oil painting style, thick brush strokes, classical art",
        "素描": "pencil sketch, black and white, hand drawn",
        "赛博朋克": "cyberpunk style, neon lights, futuristic, dark background",
        "水彩": "watercolor painting, soft colors, artistic",
        "3D": "3D render, Pixar style, cinematic lighting",
        "像素": "pixel art, 8-bit retro game style",
        "国风": "traditional Chinese painting, ink wash, ancient style",
    }
    style_en = style_map.get(style, style)
    prompt = "Redraw this image in " + style_en + " style. Content: " + desc
    return generate_image(prompt)


def write_copy(topic, style="多风格"):
    """帮写文案"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = """你是爆款文案写手。根据用户主题，写出3条不同风格的文案：
1. 小红书风格（带emoji，亲切口语化）
2. 朋友圈风格（简洁，有故事感）
3. 抖音/短视频风格（吸引眼球，带钩子）
每条不超过100字，直接输出，不要解释。"""
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": "主题：" + topic}
        ],
        "temperature": 0.9
    }
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"},
                          json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ 生成失败：" + str(e)[:100]


def generate_titles(content):
    """生成爆款标题"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = """你是爆款标题大师。根据用户提供的内容，生成 8 个吸引人的标题，涵盖：
- 悬念型
- 数字型
- 情绪型
- 干货型
每个标题不超过25字，编号输出，不加解释。"""
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": content}
        ],
        "temperature": 0.95
    }
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"},
                          json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ 生成失败：" + str(e)[:100]


# ==================== 图生视频 / 会议纪要 / 短视频脚本 ====================
def generate_video_from_image(img_bytes, prompt=""):
    """图生视频（智谱 CogVideoX）"""
    import requests, base64
    from config import ZHIPU_KEY, ZHIPU_BASE
    b64 = base64.b64encode(img_bytes).decode()
    url = ZHIPU_BASE + "/videos/generations"
    headers = {"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"}
    payload = {
        "model": "cogvideox-flash",
        "image_url": b64,
        "prompt": prompt or "让画面动起来",
        "with_audio": False
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        d = r.json()
        tid = d.get("id") or d.get("task_id") or d.get("request_id")
        if not tid:
            return None, "任务创建失败: " + str(d)[:120]
        import time
        for _ in range(80):
            time.sleep(3)
            cr = requests.get(ZHIPU_BASE + "/async-result/" + str(tid), headers=headers, timeout=15)
            if cr.status_code != 200:
                continue
            cd = cr.json()
            st = cd.get("task_status", "")
            if st in ("SUCCESS", "SUCCEED"):
                vs = cd.get("video_result") or cd.get("data") or []
                if vs:
                    v = vs[0]
                    return (v.get("url") if isinstance(v, dict) else v), None
            elif st == "FAIL":
                return None, "生成失败: " + str(cd)[:120]
        return None, "生成超时"
    except Exception as e:
        return None, "图生视频异常: " + str(e)[:100]


def summarize_meeting(transcript):
    """会议纪要提炼"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = """你是会议纪要助手。用户提供会议录音转写的文字，你输出：
📋 会议纪要
━━━━━━━━━━━━
📌 主要议题：
（1-3 条）

📝 讨论要点：
（按主题分组，每条不超过30字）

✅ 待办事项：
- 负责人：任务（截止时间）

🔑 决议结论：
（1-2 条）

输出简洁，中文回复。"""
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": transcript[:6000]}
        ],
        "temperature": 0.5
    }
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"},
                          json=payload, timeout=90)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ 生成失败：" + str(e)[:100]


def generate_script(topic):
    """短视频脚本"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    sys_p = """你是短视频编剧。根据用户主题，输出一个 30 秒的短视频脚本：

🎬 短视频脚本
━━━━━━━━━━━━
【开场 0-3s】钩子（抓住注意力）

【正文 3-25s】核心内容（3-4 个镜头）

【结尾 25-30s】引导行动

🎵 BGM 建议：（风格）
💬 口播文案：（完整可念）
📌 拍摄提示：（1-2 条）

简洁、有画面感，中文回复。"""
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": "主题：" + topic}
        ],
        "temperature": 0.9
    }
    try:
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY, "Content-Type": "application/json"},
                          json=payload, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ 生成失败：" + str(e)[:100]


# ==================== 智能路由（智谱 + OpenRouter 双平台）====================
def _call_openrouter(messages, model=None, temp=0.7, max_tokens=2048):
    """调用 OpenRouter"""
    import requests
    from config import OPENROUTER_KEY, OPENROUTER_BASE, OR_MODEL_DEFAULT
    try:
        payload = {
            "model": model or OR_MODEL_DEFAULT,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tokens,
        }
        r = requests.post(OPENROUTER_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + OPENROUTER_KEY,
                                   "Content-Type": "application/json",
                                   "HTTP-Referer": "https://sfw.bar",
                                   "X-Title": "SAFW AI"},
                          json=payload, timeout=90)
        d = r.json()
        if "choices" in d and d["choices"]:
            return d["choices"][0]["message"]["content"], None
        return None, str(d.get("error", d))[:200]
    except Exception as e:
        return None, "OpenRouter异常: " + str(e)[:120]


def _call_zhipu(messages, model="glm-4-flash", temp=0.7):
    """调用智谱"""
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    try:
        payload = {"model": model, "messages": messages, "temperature": temp}
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=60)
        d = r.json()
        if "choices" in d and d["choices"]:
            return d["choices"][0]["message"]["content"], None
        return None, str(d.get("error", d))[:200]
    except Exception as e:
        return None, "智谱异常: " + str(e)[:120]


def smart_chat(user_msg, uid=None, task_type="auto", history=None):
    """
    智能路由对话：
    - task_type='vision'   → OpenRouter Ling（视觉）
    - task_type='reason'   → OpenRouter Nemotron-120B（强推理）
    - task_type='auto'     → 智谱优先，失败自动切 OpenRouter
    """
    import json as _j, os as _o
    # 加载历史
    if history is None and uid:
        hist_file = "/root/AIbot/histories/" + str(uid) + ".json"
        if _o.path.exists(hist_file):
            try:
                with open(hist_file, "r", encoding="utf-8") as f:
                    history = _j.load(f)[-20:]
            except: history = []
    history = history or []

    system_prompt = """你是「SAFW AI」，全能智能助手，由 SAFW 团队开发。
客服：@qishe77，助理：@TronBee，官网：https://sfw.bar/qishe77
回答简洁友好，中文回复。用户问到"你是谁""联系方式""你们做什么"时，如实回答。"""

    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_msg}]

    reply = None
    source = ""

    # 1) 强推理任务 → 直接走 OpenRouter Nemotron
    if task_type == "reason":
        from config import OR_MODEL_REASONING
        reply, err = _call_openrouter(messages, model=OR_MODEL_REASONING)
        source = "nemotron-120b"
        if not reply:
            reply, err = _call_zhipu(messages)
            source = "zhipu(备用)"

    # 2) 默认：智谱优先 → 失败切 OpenRouter
    else:
        reply, err = _call_zhipu(messages)
        source = "zhipu"
        if not reply:
            reply, err = _call_openrouter(messages)
            source = "openrouter(备用)"
        if not reply:
            return "❌ 所有模型都不可用：" + str(err)

    # 保存历史
    if uid and reply:
        hist_file = "/root/AIbot/histories/" + str(uid) + ".json"
        _o.makedirs("/root/AIbot/histories", exist_ok=True)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        try:
            with open(hist_file, "w", encoding="utf-8") as f:
                _j.dump(history[-30:], f, ensure_ascii=False)
        except: pass

    return reply


# ==================== AI 文本工具 ====================
def _zhipu_text(system, user, temp=0.5):
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    try:
        payload = {"model": "glm-4-flash",
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                   "temperature": temp}
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=90)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ " + str(e)[:100]

def summarize_text(text):
    return _zhipu_text("你是专业总结助手。用3-5条bullet points输出核心要点，每条不超过30字。", text[:8000], 0.3)

def polish_text(text):
    return _zhipu_text("你是资深编辑。把文字改写通顺专业，保持原意，只输出改写后文字。", text, 0.7)

def explain_code(code):
    return _zhipu_text("你是资深程序员。逐段解释代码功能与逻辑，指出潜在问题。中文简洁回复。", code[:5000], 0.5)

def generate_regex(requirement):
    return _zhipu_text("你是正则专家。输出正则表达式+一句说明。格式：\n正则：xxx\n说明：xxx", requirement, 0.3)

def generate_sql(requirement):
    return _zhipu_text("你是SQL专家。根据需求生成SQL语句+一句说明。", requirement, 0.3)

def generate_weekly(report):
    return _zhipu_text("你是职场写手。生成周报，结构：本周完成 / 下周计划 / 需协调。", report, 0.7)

def review_contract(text):
    return _zhipu_text("你是法务专家。审查合同风险点，列3-5条风险提示。", text[:8000], 0.3)

def analyze_emotion(text):
    return _zhipu_text("你是情感分析专家。判断情绪（积极/消极/中性），给强度1-10和一句理由。", text, 0.3)


# ==================== AI 文本工具 ====================
def _zhipu_text(system, user, temp=0.5):
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    try:
        payload = {"model": "glm-4-flash",
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                   "temperature": temp}
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=90)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ " + str(e)[:100]

def summarize_text(text):
    return _zhipu_text("你是专业总结助手。用3-5条bullet points输出核心要点，每条不超过30字。", text[:8000], 0.3)

def polish_text(text):
    return _zhipu_text("你是资深编辑。把文字改写通顺专业，保持原意，只输出改写后文字。", text, 0.7)

def explain_code(code):
    return _zhipu_text("你是资深程序员。逐段解释代码功能与逻辑，指出潜在问题。中文简洁回复。", code[:5000], 0.5)

def generate_regex(requirement):
    return _zhipu_text("你是正则专家。输出正则表达式+一句说明。格式：\n正则：xxx\n说明：xxx", requirement, 0.3)

def generate_sql(requirement):
    return _zhipu_text("你是SQL专家。根据需求生成SQL语句+一句说明。", requirement, 0.3)

def generate_weekly(report):
    return _zhipu_text("你是职场写手。生成周报，结构：本周完成 / 下周计划 / 需协调。", report, 0.7)

def review_contract(text):
    return _zhipu_text("你是法务专家。审查合同风险点，列3-5条风险提示。", text[:8000], 0.3)

def analyze_emotion(text):
    return _zhipu_text("你是情感分析专家。判断情绪（积极/消极/中性），给强度1-10和一句理由。", text, 0.3)


# ==================== AI 全功能扩展 ====================
def _zp(system, user, temp=0.7, model="glm-4-flash"):
    import requests
    from config import ZHIPU_KEY, ZHIPU_BASE
    try:
        payload = {"model": model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}], "temperature": temp}
        r = requests.post(ZHIPU_BASE + "/chat/completions",
                          headers={"Authorization": "Bearer " + ZHIPU_KEY,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=90)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return "❌ " + str(e)[:100]

# ===== 图像类 =====
def gen_poster(desc):
    return generate_image("商业宣传海报设计，" + desc + "，精美排版，高清，专业设计感")

def gen_logo(brand):
    return generate_image("极简现代LOGO设计，品牌：" + brand + "，纯色背景，居中构图，几何图形，专业品牌")

def gen_product(desc):
    return generate_image("电商商品图，" + desc + "，纯白背景，专业打光，高清商业摄影")

def gen_comic(story):
    return _zp("你是漫画分镜师。把故事拆成4个分镜，每个分镜描述画面+对白，简洁输出。", story)

def gen_pixel(desc):
    return generate_image("像素艺术风格，" + desc + "，8-bit复古游戏画面，16x16像素风")

# ===== 语音类 =====
def read_multilang(text, lang="zh"):
    voice_map = {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-AriaNeural",
                 "ja": "ja-JP-NanamiNeural", "ko": "ko-KR-SunHiNeural"}
    return text_to_speech(text, voice=voice_map.get(lang, "zh-CN-XiaoxiaoNeural"))

def make_audiobook(text):
    return text_to_speech(text[:500])

# ===== 职场类 =====
def gen_email(topic):
    return _zp("你是职场邮件高手。生成正式和亲切两版邮件，各不超过150字。", topic)

def gen_resume(exp):
    return _zp("你是资深HR。优化这段经历为简历要点，用动词开头，量化成果。", exp)

def gen_interview(job):
    return _zp("你是面试官。针对岗位出5道高频面试题+参考回答要点。", job)

def gen_ppt(topic):
    return _zp("你是PPT高手。输出大纲：封面/目录/5-8页内容/总结，每页标题+要点。", topic)

def gen_mindmap(topic):
    return _zp("你是思维导图师。用缩进格式输出思维导图，覆盖主要分支。", topic)

# ===== 学习类 =====
def daily_word():
    import random
    words = ["serendipity", "ephemeral", "resilience", "eloquent", "tenacious", "ambiguous", "vivid"]
    w = random.choice(words)
    return _zp("你是英语老师。给一个单词，输出：音标/词性/中文/例句/记忆技巧。", w)

def check_grammar(sentence):
    return _zp("你是语法老师。纠正英语语法错误，说明原因，给出改写。", sentence)

def gen_essay(topic):
    return _zp("你是英语写作老师。写一篇200词英语作文，分3段，附中文翻译。", topic)

def make_quiz(subject):
    return _zp("你是出题老师。出5道选择题（含答案），主题：" + subject, "开始", 0.8)

def solve_math(problem):
    return _zp("你是数学老师。详细解题步骤，每步说明，最后给答案。", problem, 0.3)

# ===== 生活类 =====
def get_recipe(ingredient):
    return _zp("你是美食家。给出菜谱：食材/步骤/小贴士，简洁。", ingredient)

def gen_travel(city_days):
    return _zp("你是旅游规划师。输出每日行程：景点/美食/交通建议，简洁。", city_days)

def gen_diet(goal):
    return _zp("你是营养师。给出饮食计划：三餐/零食/注意事项，简单实用。", goal)

def gen_workout(body):
    return _zp("你是健身教练。给出5个动作：名称/组数/要点，适合" + body, "开始")

def gen_shopping(need):
    return _zp("你是购物顾问。推荐5个选项+一句推荐理由。", need)

# ===== 娱乐类 =====
def start_story(opening):
    return _zp("你是互动小说家。根据开头写200字，结尾给3个选项让用户选。", opening)

def gen_character(setting):
    return _zp("你是角色设计师。输出角色卡：姓名/年龄/性格/背景/口头禅/弱点。", setting)

def make_trivia(topic):
    return _zp("你是冷知识达人。给5条关于该主题的有趣冷知识，每条一句话。", topic)

def make_debate(topic):
    return _zp("你是辩论教练。给出正方3个论点、反方3个论点，各配论据。", topic)

def fortune_daily(birthday):
    return _zp("你是命理师。根据生日给今日运势：爱情/事业/财运/幸运色/幸运数字，简洁。", birthday)

# ===== 创意类 =====
def gen_slogan(product):
    return _zp("你是广告大师。给5条朗朗上口的广告语，各配一句说明。", product)

def gen_brand(industry):
    return _zp("你是品牌策划师。给5个品牌名+寓意+一句slogan。", industry)

def gen_tagline(topic):
    return _zp("你是文案高手。给3条一句话签名，简洁有力，有共鸣。", topic)

def gen_hashtag(content):
    return _zp("你是运营专家。给10个爆款话题标签（小红书/抖音风格）。", content)

def gen_bio(identity):
    return _zp("你是个人品牌顾问。给3条个人简介（长短不一），专业或有趣风格。", identity)


# ==================== 火山引擎 图生图/换脸/换衣 ====================
VOLC_API_KEY = "ark-927afde8-dc19-447e-8ec4-2ad57c8607dd-c2e6b"
VOLC_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
VOLC_MODEL = "doubao-seedream-5-0-pro-260628"


def volc_image_edit(prompt, image_urls, size="2K"):
    """
    火山引擎图生图/换脸/换衣
    image_urls: 图片URL列表（第1张目标图，第2张参考图）
    """
    import requests
    headers = {"Authorization": "Bearer " + VOLC_API_KEY,
               "Content-Type": "application/json"}
    payload = {
        "model": VOLC_MODEL,
        "prompt": prompt,
        "image": image_urls,
        "response_format": "url",
        "size": size,
        "watermark": False
    }
    try:
        r = requests.post(VOLC_URL, headers=headers, json=payload, timeout=180)
        d = r.json()
        if "data" in d and d["data"]:
            return d["data"][0].get("url"), None
        return None, str(d)[:200]
    except Exception as e:
        return None, "火山异常: " + str(e)[:120]


def face_swap(target_url, source_url):
    """换脸"""
    prompt = ("将图1中人物的脸替换为图2中人物的脸。"
              "严格保持图2的脸型、五官、肤色和表情不变。"
              "保留图1的姿势、服装、光线和背景。")
    return volc_image_edit(prompt, [target_url, source_url])


def cloth_swap(target_url, source_url):
    """换衣"""
    prompt = ("将图1中人物的服装替换为图2中的服装。"
              "严格保持图1人物的脸型、五官、姿势和背景不变。"
              "图2的服装要完美贴合图1人物身材，自然融合。")
    return volc_image_edit(prompt, [target_url, source_url])
