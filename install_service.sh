#!/bin/bash

# =============================================
# Установка systemd сервиса для автоперезапуска
# =============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Определяем директорию бота
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="xbt-tracker"

echo -e "${YELLOW}📦 Установка systemd сервиса...${NC}"

# Создаём сервис
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Twitter Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${BOT_DIR}
ExecStart=${BOT_DIR}/venv/bin/python bot.py
Restart=always
RestartSec=10

# Переменные окружения
Environment=PYTHONUNBUFFERED=1

# Лимиты
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
systemctl daemon-reload

# Включаем автозапуск
systemctl enable ${SERVICE_NAME}

echo ""
echo -e "${GREEN}✅ Сервис установлен!${NC}"
echo ""
echo "Команды управления:"
echo -e "  ${YELLOW}systemctl start ${SERVICE_NAME}${NC}    - Запустить"
echo -e "  ${YELLOW}systemctl stop ${SERVICE_NAME}${NC}     - Остановить"
echo -e "  ${YELLOW}systemctl restart ${SERVICE_NAME}${NC}  - Перезапустить"
echo -e "  ${YELLOW}systemctl status ${SERVICE_NAME}${NC}   - Статус"
echo -e "  ${YELLOW}journalctl -u ${SERVICE_NAME} -f${NC}   - Логи в реальном времени"
echo ""
