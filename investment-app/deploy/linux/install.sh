#!/usr/bin/env bash
# Instala el Asistente de inversión en un mini PC (Ubuntu Server / Debian) o una Raspberry Pi
# (Raspberry Pi OS de 64 bits). Guía paso a paso: deploy/linux/GUIA-MINIPC.md
# Uso:  bash deploy/linux/install.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
USER_NAME="$(id -un)"
CONF_DIR="$HOME/.config/asistente-inversion"
ENV_FILE="$CONF_DIR/env"

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "x86_64" ]; then
  echo "Aviso: hace falta un sistema de 64 bits (detectado: $(uname -m))."
fi
if ! command -v apt-get > /dev/null; then
  echo "Este instalador es para Ubuntu, Debian o Raspberry Pi OS (usa apt)." >&2
  exit 1
fi

echo "==> Instalando dependencias del sistema"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git curl

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Hace falta Python 3.10 o superior (tienes $(python3 --version)). Usa Ubuntu 24.04 LTS o Debian 12 o posterior." >&2
  exit 1
fi

echo "==> Creando el entorno de Python en $APP_DIR/.venv"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Preparando el archivo de claves en $ENV_FILE"
mkdir -p "$CONF_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP_DIR/deploy/linux/env.example" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
if ! grep -q '^APP_PASSWORD=.\+' "$ENV_FILE"; then
  PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
  sed -i "s|^APP_PASSWORD=.*|APP_PASSWORD=$PASS|" "$ENV_FILE"
  echo "    Contraseña de la web generada: $PASS  (guárdala; está en $ENV_FILE)"
fi

echo "==> Claude Code (para usar tu suscripción de Claude en lugar de la API)"
if command -v claude > /dev/null || [ -x "$HOME/.local/bin/claude" ]; then
  echo "    Ya está instalado."
else
  read -r -p "    ¿Instalar Claude Code? Solo hace falta si vas a usar tu suscripción [s/N] " ANS
  if [ "${ANS,,}" = "s" ]; then
    curl -fsSL https://claude.ai/install.sh | bash
  fi
fi

echo "==> Instalando los servicios"
for unit in asistente-web.service asistente-bot.service asistente-bot.timer asistente-review.service asistente-review.timer; do
  sed -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@USER@|$USER_NAME|g" -e "s|@ENV_FILE@|$ENV_FILE|g" -e "s|@HOME@|$HOME|g" \
    "$APP_DIR/deploy/linux/$unit" | sudo tee "/etc/systemd/system/$unit" > /dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable asistente-web.service asistente-bot.timer asistente-review.timer
sudo systemctl restart asistente-web.service asistente-bot.timer asistente-review.timer  # aplica también las actualizaciones

IP="$(hostname -I | awk '{print $1}')"
cat <<MSG

Listo.
  - Web:            http://$IP:8501   (desde tu red de casa)
  - Claves:         nano $ENV_FILE    y después: sudo systemctl restart asistente-web
  - Suscripción:    ~/.local/bin/claude setup-token   (copia el token en CLAUDE_CODE_OAUTH_TOKEN del archivo de claves)
  - Próximos ciclos: systemctl list-timers asistente-bot.timer
  - Ciclo manual:   sudo systemctl start asistente-bot.service
  - Revisión manual de la estrategia: sudo systemctl start asistente-review.service
  - Registro:       journalctl -u asistente-bot.service -n 50

El bot empieza en modo SIMULACIÓN. Revisa la configuración en la sección "Bot de inversión".
MSG
