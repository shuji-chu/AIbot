# ============================================================
# SAFW AI 配置文件模板
# 使用方法：复制本文件为 config.py，填入你自己的 Key
# ============================================================

# ===== SafeW Bot =====
SAFEW_TOKEN = "你的SafeW Bot Token"
BOT_USERNAME = "AiDrawChat"
BOT_NAME = "全能AI助手"

# ===== 管理员 =====
ADMIN_IDS = [你的UID]

# ===== 智谱 AI =====
ZHIPU_KEY = "你的智谱API Key"
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_DRAW_MODEL = "cogview-3-flash"
ZHIPU_VIDEO_MODEL = "cogvideox-flash"

# ===== OpenRouter（备用强推理）=====
OPENROUTER_KEY = "你的OpenRouter Key"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OR_MODEL_REASONING = "nvidia/nemotron-3-super-120b-a12b:free"
OR_MODEL_VISION = "inclusionai/ling-3.0-flash-vl:free"
OR_MODEL_DEFAULT = "nvidia/nemotron-3-super-120b-a12b:free"

# ===== ModelScope（绘画）=====
MODELSCOPE_KEY = "你的ModelScope Key"
MODELSCOPE_BASE = "https://api-inference.modelscope.cn/v1"
MODELSCOPE_DRAW_MODEL = "Tongyi-MAI/Z-Image-Turbo"

# ===== Agnes AI（图像/视频）=====
AGNES_TOKEN = "你的Agnes Token"
AGNES_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
AGNES_VIDEO_MODEL = "agnes-video-2.5"

# ===== Cloudflare Workers AI =====
CF_ACCOUNT_ID = "你的CF账户ID"
CF_TOKEN = "你的CF Token"
CF_BASE = "https://api.cloudflare.com/client/v4/accounts/{账户ID}/ai/run"
CF_TEXT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

# ===== UAPI =====
UAPI_KEY = "你的UAPI Key"
UAPI_BASE = "https://uapis.cn/api/v1"

# ===== APITG =====
APITG_KEY = "你的APITG Key"
APITG_BASE = "http://www.apitg.net/api/"

# ===== TronGrid =====
TRON_WALLET = "你的TRON钱包地址"
TRONGRID_API = "你的TronGrid API Key"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# ===== 客服 =====
CUSTOMER_SERVICE = "@qishe77"

# ===== 免费额度配置 =====
QUOTA = {
    "chat":      (999999, 0),
    "fun":       (5,   0.05),
    "text_tool": (3,   0.10),
    "draw":      (1,   0.20),
    "video":     (0,   2.00),
    "tts":       (3,   0.10),
    "doc":       (0,   0.50),
    "research":  (0,   1.00),
    "data":      (0,   0.80),
    "clone":     (0,   5.00),
    "meme":      (5,   0.05),
    "img_edit":  (3,   0.10),
}
