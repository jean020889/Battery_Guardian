#!/bin/bash
# =========================================================
#  Battery Guardian - Instalador v1.3.0
# =========================================================
#  Instala el programa en un entorno virtual (venv) en:
#      /home/asus/Apps/Battery_Guardian/
#  Y crea:
#      - Icono en el escritorio (usando battery_guardian_icon.png)
#      - Entrada en el menú de aplicaciones
#      - Servicio systemd --user (arranque automático + auto-reinicio)
#      - Enlace CLI en ~/.local/bin
# =========================================================
set -e

# --- Rutas ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"

# Carpeta de instalación: /home/asus/Apps/Battery_Guardian
INSTALL_BASE="$HOME/Apps"
INSTALL_DIR="$INSTALL_BASE/Battery_Guardian"
VENV_DIR="$INSTALL_DIR/venv"
APP_FILE="$INSTALL_DIR/battery_guardian.py"
ICON_SRC="$PROJECT_DIR/battery_guardian_icon.png"
ICON_DST="$INSTALL_DIR/battery_guardian_icon.png"
LAUNCHER="$INSTALL_DIR/run.sh"

# Accesos directos
DESKTOP_FILE="$HOME/Desktop/${APP_SLUG}.desktop"
MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SYSTEMD_FILE="$SYSTEMD_USER_DIR/${APP_SLUG}.service"

echo "═══════════════════════════════════════════════════════"
echo "  🔋 Instalando $APP_NAME v1.3.0"
echo "═══════════════════════════════════════════════════════"
echo "  Origen:  $PROJECT_DIR"
echo "  Destino: $INSTALL_DIR"
echo ""

# =========================================================
#  1) Comprobar dependencias del sistema
# =========================================================
echo "▶ [1/11] Comprobando dependencias del sistema..."

MISSING_APT=()
command -v python3 &>/dev/null        || MISSING_APT+=("python3")
command -v upower  &>/dev/null        || MISSING_APT+=("upower")
python3 -c "import tkinter" 2>/dev/null || MISSING_APT+=("python3-tk")
python3 -c "import venv"    2>/dev/null || MISSING_APT+=("python3-venv")

if [ ${#MISSING_APT[@]} -gt 0 ]; then
    echo ""
    echo "❌ Faltan dependencias del sistema:"
    for pkg in "${MISSING_APT[@]}"; do
        echo "   - $pkg"
    done
    echo ""
    echo "   Instálalas con:"
    echo "     sudo apt update"
    echo "     sudo apt install ${MISSING_APT[*]}"
    echo ""
    exit 1
fi
echo "   ✓ Dependencias del sistema OK"
echo ""

# =========================================================
#  2) Comprobar el icono
# =========================================================
echo "▶ [2/11] Comprobando icono..."

if [ ! -f "$ICON_SRC" ]; then
    echo "❌ No se encontró el icono en:"
    echo "   $ICON_SRC"
    echo ""
    echo "   Asegúrate de que el archivo 'battery_guardian_icon.png'"
    echo "   está en la raíz del proyecto."
    exit 1
fi
echo "   ✓ Icono encontrado"
echo ""

# =========================================================
#  3) Detener instancia antigua (si existe)
# =========================================================
echo "▶ [3/11] Deteniendo instancias antiguas..."

if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
fi

pkill -9 -f "battery_guardian.py" 2>/dev/null || true
sleep 1
echo "   ✓ Sin instancias activas"
echo ""

# =========================================================
#  4) Crear carpeta y copiar archivos
# =========================================================
echo "▶ [4/11] Copiando archivos..."

mkdir -p "$INSTALL_BASE"
mkdir -p "$INSTALL_DIR"

cp -f "$PROJECT_DIR/battery_guardian.py" "$APP_FILE"
cp -f "$ICON_SRC" "$ICON_DST"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    cp -f "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
fi
if [ -f "$PROJECT_DIR/README.md" ]; then
    cp -f "$PROJECT_DIR/README.md" "$INSTALL_DIR/README.md"
fi

chmod +x "$APP_FILE"
echo "   ✓ Archivos copiados a $INSTALL_DIR"
echo ""

# =========================================================
#  5) Crear entorno virtual
# =========================================================
echo "▶ [5/11] Creando entorno virtual..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
echo "   ✓ Entorno virtual: $VENV_DIR"
echo ""

# =========================================================
#  6) Instalar dependencias en el venv
# =========================================================
echo "▶ [6/11] Instalando dependencias de Python en el venv..."

"$VENV_DIR/bin/pip" install --upgrade pip --quiet

if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
fi
echo "   ✓ Dependencias instaladas"
echo ""

# =========================================================
#  7) Crear lanzador
# =========================================================
echo "▶ [7/11] Creando lanzador..."

cat > "$LAUNCHER" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/battery_guardian.py" "$@"
LAUNCHER
chmod +x "$LAUNCHER"

echo "   ✓ Lanzador: $LAUNCHER"
echo ""

# =========================================================
#  8) Enlace CLI en ~/.local/bin
# =========================================================
echo "▶ [8/11] Creando enlace CLI..."

mkdir -p "$HOME/.local/bin"
ln -sf "$LAUNCHER" "$BIN_LINK"
echo "   ✓ Enlace: $BIN_LINK"
echo ""

# =========================================================
#  9) Icono del escritorio + entrada del menú
# =========================================================
echo "▶ [9/11] Creando accesos directos..."

# --- Icono del escritorio ---
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

# --- Entrada del menú de aplicaciones ---
mkdir -p "$HOME/.local/share/applications"
cat > "$MENU_FILE" << DESKTOP
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
chmod +x "$MENU_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "   ✓ Menú: $MENU_FILE"
echo ""

# =========================================================
#  10) Servicio systemd --user (arranque automático)
# =========================================================
echo "▶ [10/11] Instalando servicio systemd --user..."

# Eliminar autostart .desktop antiguo (evita arranque duplicado)
if [ -f "$AUTOSTART_FILE" ]; then
    rm -f "$AUTOSTART_FILE"
    echo "   (autostart .desktop antiguo eliminado)"
fi

mkdir -p "$SYSTEMD_USER_DIR"
cat > "$SYSTEMD_FILE" << SYSTEMD
[Unit]
Description=$APP_NAME - Cuida la batería del portátil
Documentation=file://$INSTALL_DIR/README.md
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$LAUNCHER --hidden
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=default.target
SYSTEMD
echo "   ✓ Servicio: $SYSTEMD_FILE"

systemctl --user daemon-reload
systemctl --user enable "${APP_SLUG}.service"
systemctl --user start  "${APP_SLUG}.service" || true
echo "   ✓ Servicio activado y arrancado"
echo ""

# =========================================================
#  11) Verificación final
# =========================================================
echo "▶ [11/11] Verificando instalación..."

"$VENV_DIR/bin/python" -c "import pystray, PIL; print('   ✓ pystray y Pillow OK')" || \
    echo "   ⚠ No se pudieron verificar pystray/Pillow"

if systemctl --user is-active --quiet "${APP_SLUG}.service"; then
    echo "   ✓ Servicio systemd ACTIVO"
else
    echo "   ⚠ El servicio no está activo. Revisa:"
    echo "       systemctl --user status ${APP_SLUG}.service"
fi
echo ""

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "⚠  NOTA: ~/.local/bin no está en tu PATH."
    echo '   echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
    echo '   source ~/.bashrc'
    echo ""
fi

echo "═══════════════════════════════════════════════════════"
echo "  ✅ Instalación completada"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  📂 Instalado en:  $INSTALL_DIR"
echo ""
echo "  📌 El programa ya está corriendo en segundo plano."
echo "     Búscalo en la bandeja del sistema (donde WiFi/Bluetooth)."
echo ""
echo "  🖱️  Abrir la ventana:"
echo "      - Clic en el icono de la bandeja"
echo "      - Doble clic en el icono del escritorio"
echo "      - Menú de aplicaciones → '$APP_NAME'"
echo "      - Terminal:  $APP_SLUG"
echo ""
echo "  🛑 Detener temporalmente:"
echo "      systemctl --user stop ${APP_SLUG}.service"
echo ""
echo "  🗑️  Desinstalar:"
echo "      $PROJECT_DIR/uninstall.sh"
echo ""
