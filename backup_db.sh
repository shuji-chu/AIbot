#!/bin/bash
BACKUP_DIR="/root/AIbot/backups"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
cp /root/AIbot/aibot.db $BACKUP_DIR/aibot_$DATE.db
find $BACKUP_DIR -name "aibot_*.db" -mtime +7 -delete
echo "$(date) 备份：aibot_$DATE.db" >> $BACKUP_DIR/backup.log
