#!/bin/bash
# 日志轮转：超过 10MB 清空
for f in /root/AIbot/bot.log /root/AIbot/api.log; do
    if [ -f "$f" ]; then
        size=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ $size -gt 10485760 ]; then
            > "$f"
            echo "$(date) 已清理 $f" >> /root/AIbot/clean.log
        fi
    fi
done
