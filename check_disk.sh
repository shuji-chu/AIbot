#!/bin/bash
USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ $USAGE -gt 80 ]; then
    echo "$(date) ⚠️ 磁盘 ${USAGE}%" >> /root/AIbot/disk_alert.log
fi
