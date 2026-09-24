# -*- coding: utf-8 -*-
"""全语言多角色配音（自动拉取 Edge TTS 所有音色）"""
import os, re, json, asyncio, tempfile, subprocess
from edge_tts import Communicate

CACHE_FILE = "/root/AIbot/voice_cache.json"


def load_all_voices():
    """拉取所有音色，缓存到本地"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and len(data) > 100:
                    print(f"[配音] 加载缓存 {len(data)} 个音色")
                    return data
        except: pass
    
    print("[配音] 首次拉取所有音色...")
    voices = asyncio.run(_fetch_voices())
    result = {}
    for v in voices:
        locale = v.get("Locale", "")
        name = v.get("ShortName", "")
        gender = v.get("Gender", "")
        result[name] = {
            "locale": locale,
            "lang": locale.split("-")[0] if locale else "",
            "gender": gender.lower(),
            "name": name,
        }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[配音] 已缓存 {len(result)} 个音色")
    return result


async def _fetch_voices():
    return await __import__("edge_tts").list_voices()


# 全局音色表
ALL_VOICES = load_all_voices()


def detect_lang(text):
    """检测文本主要语言"""
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text): return "ja"
    if re.search(r'[\uac00-\ud7af]', text): return "ko"
    if re.search(r'[\u4e00-\u9fff]', text): return "zh"
    if re.search(r'[\u0600-\u06ff]', text): return "ar"
    if re.search(r'[\u0400-\u04ff]', text): return "ru"
    if re.search(r'[\u0900-\u097f]', text): return "hi"
    if re.search(r'[\u0e00-\u0e7f]', text): return "th"
    if re.search(r'[a-zA-Z]', text): return "en"
    return "zh"


def pick_voice(lang, gender, exclude=None):
    """从所有音色里挑一个最匹配的"""
    exclude = exclude or set()
    gender = (gender or "male").lower()
    
    candidates = []
    for name, info in ALL_VOICES.items():
        if info.get("lang") != lang: continue
        if info.get("gender") != gender: continue
        if name in exclude: continue
        candidates.append(name)
    
    # 如果找不到对应性别，尝试另一个性别
    if not candidates:
        for name, info in ALL_VOICES.items():
            if info.get("lang") == lang and name not in exclude:
                candidates.append(name)
    
    # 如果连该语言都没有，降级到中文
    if not candidates and lang != "zh":
        for name, info in ALL_VOICES.items():
            if info.get("lang") == "zh" and info.get("gender") == gender and name not in exclude:
                candidates.append(name)
    
    # 最后兜底
    if not candidates:
        candidates = ["zh-CN-YunxiNeural"]
    
    return candidates[0]


def parse_script(text):
    """解析剧本：角色：台词"""
    lines = text.strip().split("\n")
    dialogues = []
    for line in lines:
        line = line.strip().replace('　', '')
        if not line: continue
        m = re.match(r'^([^：:]{1,10})[：:]\s*(.+)$', line)
        if m:
            role = m.group(1).strip()
            content = m.group(2).strip()
            if content:
                dialogues.append((role, content))
        else:
            dialogues.append(("旁白", line))
    return dialogues


def assign_voices(dialogues):
    """为每个角色分配音色"""
    import ai_service as _a
    roles = list(set([r for r, _ in dialogues if r != "旁白" and r.strip()]))
    
    gender_map = {}
    if roles:
        try:
            samples = {}
            for role in roles:
                for r, c in dialogues:
                    if r == role:
                        samples[role] = c[:100]
                        break
            prompt = "为以下角色判断性别（男/女）。输出格式：\\n角色名=男\\n角色名=女\\n\\n"
            for role, sample in samples.items():
                prompt += f"{role}：{sample}\\n"
            r = _a.stable_ai("你是角色分析助手。", prompt, 0.1)
            for line in r.split("\\n"):
                if "=" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        role = parts[0].strip()
                        g = parts[1].strip()
                        if "男" in g: gender_map[role] = "male"
                        elif "女" in g: gender_map[role] = "female"
        except: pass
    
    voice_map = {}
    used = set()
    
    # 每个角色：检测语言 + 分配音色
    for role in roles:
        lang = "zh"
        for r, c in dialogues:
            if r == role:
                lang = detect_lang(c)
                break
        gender = gender_map.get(role, "male")
        voice = pick_voice(lang, gender, exclude=used)
        used.add(voice)
        voice_map[role] = voice
        print(f"[配音] {role} → {voice} ({lang}/{gender})")
    
    # 旁白
    narration = " ".join([c for r, c in dialogues if r == "旁白"])
    nar_lang = detect_lang(narration) if narration else "zh"
    nar_voice = pick_voice(nar_lang, "male", exclude=used)
    if nar_voice in used:
        nar_voice = pick_voice(nar_lang, "female", exclude=used)
    voice_map["旁白"] = nar_voice
    print(f"[配音] 旁白 → {nar_voice} ({nar_lang})")
    
    return voice_map


async def _tts_one(text, voice, out_path):
    comm = Communicate(text=text, voice=voice, rate="+0%")
    await comm.save(out_path)


def make_voice_drama(script_text, uid):
    """主函数"""
    dialogues = parse_script(script_text)
    if not dialogues:
        return None, "❌ 剧本为空，格式：角色：台词"
    if len(dialogues) > 50:
        dialogues = dialogues[:50]
    
    voice_map = assign_voices(dialogues)
    print("[配音] 映射：" + str(voice_map))
    
    tmp_dir = tempfile.mkdtemp()
    audio_files = []
    try:
        for i, (role, content) in enumerate(dialogues):
            voice = voice_map.get(role, "zh-CN-YunxiNeural")
            out = os.path.join(tmp_dir, f"seg_{i:03d}.mp3")
            try:
                asyncio.run(_tts_one(content[:300], voice, out))
                if os.path.exists(out) and os.path.getsize(out) > 0:
                    audio_files.append(out)
            except Exception as e:
                print(f"[配音] 第{i}段失败: {str(e)[:60]}")
        
        if not audio_files:
            return None, "❌ 所有段落生成失败"
        
        if len(audio_files) == 1:
            with open(audio_files[0], "rb") as f:
                return f.read(), None
        
        list_file = os.path.join(tmp_dir, "list.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            for af in audio_files:
                f.write("file '" + af.replace("'", "'\\''") + "'\n")
        
        out_mp3 = os.path.join(tmp_dir, "final.mp3")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", list_file, "-c", "copy", out_mp3],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
            with open(out_mp3, "rb") as f:
                return f.read(), None
        with open(audio_files[0], "rb") as f:
            return f.read(), None
    except Exception as e:
        return None, "❌ 生成失败：" + str(e)[:100]
    finally:
        import shutil
        try: shutil.rmtree(tmp_dir)
        except: pass


def list_supported_langs():
    """列出支持的语言"""
    from collections import Counter
    langs = Counter(v["lang"] for v in ALL_VOICES.values())
    return dict(sorted(langs.items(), key=lambda x: -x[1]))
