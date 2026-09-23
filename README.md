# 🤖 SAFW AI — 全能智能助手

基于 SafeW Bot 的多功能 AI 机器人，集成对话、绘画、视频、语音、查询等功能。

## ✨ 核心功能

### 🎨 AI 创作
- `/draw` 绘画（通义万相）
- `/video` AI 视频（智谱 CogVideoX）
- `/tts` 文字转语音（Edge TTS）
- `/poster` `/logo` 海报/LOGO 生成

### 💬 智能对话
- 支持持久记忆
- 智谱 + OpenRouter 智能路由
- 自动联网搜索
- 8 种角色扮演

### 📷 拍照识别
- 发图自动识别文字/名片/菜单
- `/style` 风格转换（动漫/油画/赛博朋克）

### 🔍 60+ 工具命令
- 天气、IP、热搜、壁纸、汇率
- 域名、ICP、WHOIS、百度权重
- 手机、身份证、车辆、企业查询
- 链上钱包、USDT 交易查询

## 🚀 部署

    git clone <repo>
    cd AIbot
    pip install -r requirements.txt
    cp config.example.py config.py
    # 填入你的 API Key
    python3 main.py

## ⚙️ 配置

编辑 `config.py`，填入以下 Key：
- `SAFEW_TOKEN` — SafeW Bot Token
- `ZHIPU_KEY` — 智谱 AI
- `OPENROUTER_KEY` — OpenRouter
- `MODELSCOPE_KEY` — ModelScope
- `TRONGRID_API` — TronGrid

## 📞 联系

客服：@qishe77
