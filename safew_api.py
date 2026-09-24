import datetime as _dt
import json
import requests, time
from io import BytesIO
from PIL import Image
from config import SAFEW_TOKEN
BASE = "https://api.safew.bot/bot" + SAFEW_TOKEN

def send_message(chat_id, text, custom_markup=None, reply_to_msg_id=None):
    p = {"chat_id": chat_id, "text": text}
    if reply_to_msg_id: p["reply_to_message_id"] = reply_to_msg_id
    if custom_markup: p["reply_markup"] = custom_markup
    try:
        r = requests.post(BASE + "/sendMessage", json=p, timeout=15)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendMessage失败：" + str(e)[:80]); return None

def send_long_message(chat_id, text, limit=3000, reply_to_msg_id=None):
    if not text: return
    if len(text) <= limit:
        send_message(chat_id, text, reply_to_msg_id=reply_to_msg_id); return
    paras = text.split("\n"); buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 > limit:
            if buf:
                send_message(chat_id, buf.strip(), reply_to_msg_id=reply_to_msg_id)
                reply_to_msg_id = None; time.sleep(0.5)
            buf = p
        else:
            buf = buf + "\n" + p if buf else p
    if buf: send_message(chat_id, buf.strip(), reply_to_msg_id=reply_to_msg_id)

def send_photo(chat_id, img_bytes, caption=None, reply_to_msg_id=None, custom_markup=None):
    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        buf = BytesIO(); img.save(buf, format="JPEG", quality=90)
        img_bytes = buf.getvalue()
    except Exception as e:
        print("图片转换失败：" + str(e)[:80]); return None
    d = {"chat_id": chat_id}
    if caption: d["caption"] = caption
    if reply_to_msg_id: d["reply_to_message_id"] = reply_to_msg_id
    if custom_markup:
        d["reply_markup"] = json.dumps(custom_markup, ensure_ascii=False)
    try:
        r = requests.post(BASE + "/sendPhoto", data=d, files={"photo": ("image.jpg", img_bytes, "image/jpeg")}, timeout=120)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendPhoto失败：" + str(e)[:80]); return None

def send_video(chat_id, video_bytes, caption=None, reply_to_msg_id=None):
    d = {"chat_id": chat_id}
    if caption: d["caption"] = caption
    if reply_to_msg_id: d["reply_to_message_id"] = reply_to_msg_id
    try:
        r = requests.post(BASE + "/sendVideo", data=d, files={"video": ("video.mp4", video_bytes, "video/mp4")}, timeout=180)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendVideo失败：" + str(e)[:80]); return None

def send_animation(chat_id, gif_bytes, caption=None, reply_to_msg_id=None):
    d = {"chat_id": chat_id}
    if caption: d["caption"] = caption
    if reply_to_msg_id: d["reply_to_message_id"] = reply_to_msg_id
    try:
        r = requests.post(BASE + "/sendDocument", data=d, files={"document": ("animation.gif", gif_bytes, "image/gif")}, timeout=120)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendAnimation失败：" + str(e)[:80]); return None

def download_url(url):
    try:
        r = requests.get(url, timeout=300)
        if r.status_code == 200: return r.content
    except Exception as e:
        print("下载失败：" + str(e)[:80])
    return None

def delete_message(chat_id, msg_id):
    if not msg_id: return
    try:
        requests.post(BASE + "/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id}, timeout=10)
    except: pass

def get_file_bytes(file_id):
    try:
        r = requests.get(BASE + "/getFile", params={"file_id": file_id}, timeout=15)
        fp = r.json()["result"]["file_path"]
        return requests.get("https://api.safew.bot/file/bot" + SAFEW_TOKEN + "/" + fp, timeout=60).content
    except Exception as e:
        print("下载文件失败：" + str(e)[:80]); return None

def answer_callback(cq_id):
    try:
        requests.post(BASE + "/answerCallbackQuery", json={"callback_query_id": cq_id}, timeout=5)
    except: pass

def set_commands():
    cmds = [
        {"command": "start", "description": "开始使用"},
        {"command": "draw", "description": "AI绘画"},
        {"command": "balance", "description": "查询余额"},
        {"command": "recharge", "description": "充值"},
        {"command": "help", "description": "使用帮助"},
    ]
    try:
        requests.post(BASE + "/setMyCommands", json={"commands": cmds}, timeout=15)
        print("[" + _dt.datetime.now().strftime("%H:%M:%S") + "] ✅ 菜单命令已设置")
    except: pass


def send_audio(chat_id, audio_bytes, caption=None, reply_to_msg_id=None):
    url = BASE + "/sendAudio"
    files = {"audio": ("voice.mp3", audio_bytes, "audio/mpeg")}
    data = {"chat_id": chat_id}
    if caption: data["caption"] = caption
    if reply_to_msg_id: data["reply_to_message_id"] = reply_to_msg_id
    try:
        r = requests.post(url, data=data, files=files, timeout=60)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendAudio失败：" + str(e)[:80]); return None


def send_voice(chat_id, audio_bytes, reply_to_msg_id=None):
    """发送语音条（自动 mp3 → ogg/opus 转码）"""
    import subprocess, tempfile, os
    d = {"chat_id": chat_id}
    if reply_to_msg_id: d["reply_to_message_id"] = reply_to_msg_id
    tmp_in = tmp_out = None
    try:
        # 写入 mp3
        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_in.write(audio_bytes)
        tmp_in.close()
        # 转码为 ogg/opus
        tmp_out = tmp_in.name.replace(".mp3", ".ogg")
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in.name,
             "-c:a", "libopus", "-b:a", "48k",
             "-vbr", "on", "-compression_level", "10",
             "-frame_duration", "60", "-application", "voip",
             tmp_out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60
        )
        with open(tmp_out, "rb") as f:
            ogg_bytes = f.read()
        r = requests.post(BASE + "/sendVoice",
                          data=d,
                          files={"voice": ("voice.ogg", ogg_bytes, "audio/ogg")},
                          timeout=60)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendVoice失败：" + str(e)[:120]); return None
    finally:
        for p in (tmp_in, tmp_out):
            if p and os.path.exists(getattr(p, "name", p)):
                try: os.unlink(getattr(p, "name", p))
                except: pass


def send_document(chat_id, file_bytes, filename="file.txt", caption=None, reply_to_msg_id=None):
    d = {"chat_id": chat_id}
    if caption: d["caption"] = caption
    if reply_to_msg_id: d["reply_to_message_id"] = reply_to_msg_id
    try:
        r = requests.post(BASE + "/sendDocument",
                          data=d,
                          files={"document": (filename, file_bytes, "text/plain")},
                          timeout=120)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("sendDocument失败：" + str(e)[:80]); return None
