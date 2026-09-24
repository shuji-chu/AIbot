# -*- coding: utf-8 -*-
"""AI 漫画生成"""
import os, re, io
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc"


def _get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()


def split_to_panels(story):
    import ai_service as _a
    prompt = f"""把以下故事拆成 4 个连贯画面（用于画漫画）。

故事：{story}

要求：
- 每个画面一句话描述（20-40字）
- 强调视觉元素（角色、动作、环境）
- 4 个画面要连贯
- 输出严格格式：
1. XXX
2. XXX
3. XXX
4. XXX

只输出 4 行。"""
    r = _a.stable_ai("你是漫画分镜师。", prompt, 0.7)
    panels = []
    for line in r.split("\n"):
        m = re.match(r'^\d+[.、]\s*(.+)$', line.strip())
        if m:
            panels.append(m.group(1).strip())
    return panels[:4]


def generate_comic(story):
    import ai_service as _a
    panels = split_to_panels(story)
    if not panels:
        return None, "❌ 分镜生成失败"
    print("[漫画] 分镜：" + str(panels))
    images = []
    for i, desc in enumerate(panels):
        try:
            full_prompt = "漫画风格，" + desc + "，卡通，明亮色彩，日式漫画，无文字"
            img_bytes = _a.generate_image(full_prompt)
            if img_bytes:
                images.append((i+1, desc, img_bytes))
                print(f"[漫画] 第{i+1}格 OK")
        except Exception as e:
            print(f"[漫画] 第{i+1}格失败: {str(e)[:60]}")
    if not images:
        return None, "❌ 所有分镜生成失败"
    return _stitch_comic(images), None


def _stitch_comic(images):
    W, H = 512, 512
    gap = 10
    canvas_w = W * 2 + gap * 3
    canvas_h = H * 2 + gap * 3 + 70
    canvas = Image.new("RGB", (canvas_w, canvas_h), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    title_font = _get_font(30)
    draw.text((canvas_w // 2, 30), "🎨 AI 漫画", fill=(60, 60, 60), font=title_font, anchor="mm")
    for idx, (num, desc, img_bytes) in enumerate(images):
        row = idx // 2
        col = idx % 2
        x = gap + col * (W + gap)
        y = 70 + gap + row * (H + gap)
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img = img.resize((W, H), Image.LANCZOS)
            canvas.paste(img, (x, y))
            badge_font = _get_font(28)
            draw.ellipse([x + 15, y + 15, x + 60, y + 60], fill=(255, 100, 100))
            draw.text((x + 37, y + 37), str(num), fill=(255, 255, 255), font=badge_font, anchor="mm")
        except Exception as e:
            print(f"[漫画] 粘贴第{num}格失败: {str(e)[:60]}")
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
