
#!/bin/bash
# =========================================================
#  Battery Guardian - Instalador v2.1.0
# =========================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"
INSTALL_DIR="$HOME/Apps/Battery_Guardian"
VENV_DIR="$INSTALL_DIR/venv"
APP_FILE="$INSTALL_DIR/battery_guardian.py"
ICON_SRC="$PROJECT_DIR/battery_guardian_icon.png"
ICON_DST="$INSTALL_DIR/battery_guardian_icon.png"
LAUNCHER="$INSTALL_DIR/run.sh"

DESKTOP_FILE="$HOME/Desktop/${APP_SLUG}.desktop"
MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SYSTEMD_FILE="$SYSTEMD_USER_DIR/${APP_SLUG}.service"

echo "═══════════════════════════════════════════════════════"
echo "  🔋 Instalando $APP_NAME v2.1.0"
echo "═══════════════════════════════════════════════════════"
echo ""

# =========================================================
#  1) Dependencias
# =========================================================
echo "▶ [1/12] Comprobando dependencias del sistema..."
MISSING_APT=()
command -v python3 &>/dev/null        || MISSING_APT+=("python3")
command -v upower  &>/dev/null        || MISSING_APT+=("upower")
python3 -c "import tkinter" 2>/dev/null || MISSING_APT+=("python3-tk")
python3 -c "import venv"    2>/dev/null || MISSING_APT+=("python3-venv")

if [ ${#MISSING_APT[@]} -gt 0 ]; then
    echo "❌ Faltan dependencias:"
    for pkg in "${MISSING_APT[@]}"; do echo "   - $pkg"; done
    echo ""
    echo "   sudo apt update && sudo apt install ${MISSING_APT[*]}"
    exit 1
fi
echo "   ✓ Dependencias OK"

# Dependencias OPCIONALES para auto-apagado por inactividad
echo ""
echo "   Dependencias opcionales (auto-apagado por inactividad):"
if command -v xprintidle &>/dev/null; then
    echo "   ✓ xprintidle instalado (detección de inactividad)"
else
    echo "   ⚠ xprintidle NO instalado."
    echo "     Sin él, la detección de inactividad no funciona en X11."
    echo "     Instálalo con:  sudo apt install xprintidle"
fi
if command -v pactl &>/dev/null; then
    echo "   ✓ pactl instalado (detección de multimedia)"
else
    echo "   ⚠ pactl NO instalado (normalmente viene con PulseAudio/PipeWire)"
fi
echo ""

# =========================================================
#  2) Comprobar archivos
# =========================================================
echo "▶ [2/12] Comprobando archivos requeridos..."
[ -f "$ICON_SRC" ] || { echo "❌ Falta battery_guardian_icon.png"; exit 1; }
[ -f "$PROJECT_DIR/battery_guardian.py" ] || { echo "❌ Falta battery_guardian.py"; exit 1; }
echo "   ✓ Archivos OK"

LICENSE_SRC=""
[ -f "$PROJECT_DIR/LICENSE.md" ] && LICENSE_SRC="$PROJECT_DIR/LICENSE.md"
[ -z "$LICENSE_SRC" ] && [ -f "$PROJECT_DIR/LICENSE" ] && LICENSE_SRC="$PROJECT_DIR/LICENSE"
echo ""

# =========================================================
#  3) Detener instancia antigua
# =========================================================
echo "▶ [3/12] Deteniendo instancias antiguas..."
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
fi
pkill -9 -f "battery_guardian.py" 2>/dev/null || true
sleep 1
echo "   ✓ OK"
echo ""

# =========================================================
#  4) Crear carpeta
# =========================================================
echo "▶ [4/12] Creando carpeta de instalación..."
mkdir -p "$INSTALL_DIR"
echo "   ✓ $INSTALL_DIR"
echo ""

# =========================================================
#  5) Copiar archivos
# =========================================================
echo "▶ [5/12] Copiando archivos..."
cp -f "$PROJECT_DIR/battery_guardian.py" "$APP_FILE"
chmod +x "$APP_FILE"
cp -f "$ICON_SRC" "$ICON_DST"
[ -f "$PROJECT_DIR/requirements.txt" ] && cp -f "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
[ -f "$PROJECT_DIR/README.md" ]        && cp -f "$PROJECT_DIR/README.md"        "$INSTALL_DIR/"
[ -n "$LICENSE_SRC" ]                  && cp -f "$LICENSE_SRC"                  "$INSTALL_DIR/"
[ -f "$PROJECT_DIR/Installation_instructions.md" ] && \
    cp -f "$PROJECT_DIR/Installation_instructions.md" "$INSTALL_DIR/"
echo "   ✓ Archivos copiados"
echo ""

# =========================================================
#  6) venv
# =========================================================
echo "▶ [6/12] Creando entorno virtual..."
[ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/python" ] && rm -rf "$VENV_DIR"
[ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
[ -x "$VENV_DIR/bin/python" ] || { echo "❌ venv roto"; exit 1; }
[ -x "$VENV_DIR/bin/pip" ]    || { echo "❌ pip roto"; exit 1; }
echo "   ✓ venv OK ($("$VENV_DIR/bin/python" --version))"
echo ""

# =========================================================
#  7) Dependencias Python
# =========================================================
echo "▶ [7/12] Instalando dependencias Python..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
[ -f "$INSTALL_DIR/requirements.txt" ] && \
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
echo "   ✓ pystray y Pillow instalados"
echo ""

# =========================================================
#  8) Lanzador
# =========================================================
echo "▶ [8/12] Creando lanzador..."
cat > "$LAUNCHER" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/battery_guardian.py" "$@"
LAUNCHER
chmod +x "$LAUNCHER"
echo "   ✓ $LAUNCHER"
echo ""

# =========================================================
#  9) Enlace CLI
# =========================================================
echo "▶ [9/12] Enlace CLI..."
mkdir -p "$HOME/.local/bin"
ln -sf "$LAUNCHER" "$BIN_LINK"
echo "   ✓ $BIN_LINK"
echo ""

# =========================================================
#  10) Escritorio + menú
# =========================================================
echo "▶ [10/12] Creando accesos directos..."
mkdir -p "$HOME/Desktop"
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
GenericName=Battery Care
Comment=Cuida la salud de la batería de tu portátil
Exec=$LAUNCHER
Icon=$ICON_DST
Terminal=false
Categories=Utility;System;
StartupNotify=true
DESKTOP
chmod +x "$DESKTOP_FILE"
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
echo "   ✓ Escritorio: $DESKTOP_FILE"

mkdir -p "$HOME/.local/share/applications"
cp -f "$DESKTOP_FILE" "$MENU_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "   ✓ Menú: $MENU_FILE"
echo ""

# =========================================================
#  11) Servicio systemd CON RETARDO DE ARRANQUE
# =========================================================
echo "▶ [11/12] Instalando servicio systemd --user (con retardo)..."
[ -f "$AUTOSTART_FILE" ] && rm -f "$AUTOSTART_FILE"

mkdir -p "$SYSTEMD_USER_DIR"
cat > "$SYSTEMD_FILE" << SYSTEMD
[Unit]
Description=$APP_NAME - Cuida la batería del portátil
Documentation=file://$INSTALL_DIR/README.md
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
# Espera 20 s para que el escritorio termine de arrancar
# (mejora el tiempo de inicio del sistema y evita conflictos)
ExecStartPre=/bin/sleep 20
ExecStart=$LAUNCHER --hidden
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=default.target
SYSTEMD
echo "   ✓ Servicio con retardo de 20 s configurado"

systemctl --user daemon-reload
systemctl --user enable "${APP_SLUG}.service"
systemctl --user start  "${APP_SLUG}.service" || true
echo "   ✓ Servicio habilitado y arrancado"
echo ""

# =========================================================
#  12) Verificación
# =========================================================
echo "▶ [12/12] Verificando..."
echo ""
echo "   📂 Contenido de $INSTALL_DIR:"
ls -lh "$INSTALL_DIR" | grep -v "^total" | awk '{printf "      %-40s %s\n", $9, $5}'
echo ""
echo "   📂 venv:"
ls "$VENV_DIR/bin" | tr '\n' ' ' | sed 's/^/      /'
echo ""
echo ""
if systemctl --user is-active --quiet "${APP_SLUG}.service"; then
    echo "   ✓ Servicio systemd ACTIVO"
else
    echo "   ⚠ Servicio NO activo"
fi
echo ""

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "⚠  Añade ~/.local/bin al PATH:"
    echo '   echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
    echo '   source ~/.bashrc'
    echo ""
fi

echo "═══════════════════════════════════════════════════════"
echo "  ✅ Instalación completada"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  📂 Instalado en:  $INSTALL_DIR"
echo "  📦 venv en:       $VENV_DIR"
echo ""
echo "  ⏱️  Arranque del servicio: retrasado 20 s tras iniciar sesión"
echo "     (systemd: ExecStartPre=/bin/sleep 20)"
echo ""
echo "  🆕 Nueva función v2.1.0: AUTO-APAGADO POR INACTIVIDAD"
echo "     - Se activa/desactiva desde la GUI"
echo "     - Detecta teclado/ratón (xprintidle)"
echo "     - No apaga si hay multimedia reproduciéndose"
echo ""
if ! command -v xprintidle &>/dev/null; then
    echo "  ⚠  RECOMENDADO: instala xprintidle para que funcione"
    echo "     la detección de inactividad:"
    echo "         sudo apt install xprintidle"
    echo ""
fi
echo "  🖱️  Abrir la ventana:"
echo "      - Clic en el icono de la bandeja"
echo "      - Doble clic en el icono del escritorio"
echo "      - Terminal:  $APP_SLUG"
echo ""
echo "  🗑️  Desinstalar:  ./uninstall.sh"
echo ""


