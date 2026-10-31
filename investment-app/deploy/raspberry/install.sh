#!/usr/bin/env bash
# Instala el Asistente de inversión en una Raspberry Pi (Raspberry Pi OS de 64 bits).
# Uso:  bash deploy/raspberry/install.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
USER_NAME="$(id -un)"
CONF_DIR="$HOME/.config/asistente-inversion"
ENV_FILE="$CONF_DIR/env"

if [ "$(uname -m)" != "aarch64" ] && [ "$(uname -m)" != "x86_64" ]; then
  echo "Aviso: se recomienda Raspberry Pi OS de 64 bits (detectado: $(uname -m))."
fi

echo "==> Instalando dependencias del sistema"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

echo "==> Creando el entorno de Python en $APP_DIR/.venv"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Preparando el archivo de claves en $ENV_FILE"
mkdir -p "$CONF_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cp "$APP_DIR/deploy/raspberry/env.example" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
if ! grep -q '^APP_PASSWORD=.\+' "$ENV_FILE"; then
  PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
  sed -i "s|^APP_PASSWORD=.*|APP_PASSWORD=$PASS|" "$ENV_FILE"
  echo "    Contraseña de la web generada: $PASS  (guárdala; está en $ENV_FILE)"
fi

echo "==> Instalando los servicios"
for unit in asistente-web.service asistente-bot.service asistente-bot.timer asistente-review.service asistente-review.timer; do
  sed -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@USER@|$USER_NAME|g" -e "s|@ENV_FILE@|$ENV_FILE|g" \
    "$APP_DIR/deploy/raspberry/$unit" | sudo tee "/etc/systemd/system/$unit" > /dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now asistente-web.service asistente-bot.timer asistente-review.timer

IP="$(hostname -I | awk '{print $1}')"
cat <<MSG

Listo.
  - Web:            http://$IP:8501   (desde tu red de casa)
  - Claves:         nano $ENV_FILE    y después: sudo systemctl restart asistente-web
  - Próximos ciclos: systemctl list-timers asistente-bot.timer
  - Ciclo manual:   sudo systemctl start asistente-bot.service
  - Revisión manual de la estrategia: sudo systemctl start asistente-review.service
  - Registro:       journalctl -u asistente-bot.service -n 50

El bot empieza en modo SIMULACIÓN. Revisa la configuración en la sección "Bot de inversión".
MSG
