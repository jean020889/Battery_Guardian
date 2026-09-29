

#!/bin/bash
# =========================================================
#  Battery Guardian - Instalador v2.2.9 (adaptado)
#  Instala en: /home/asus/Apps/Battery_Guardian
# =========================================================
set -e

# ---------------------------------------------------------
#  Rutas
# ---------------------------------------------------------
APPS_DIR="/home/asus/Apps"
APP_NAME="Battery Guardian"
APP_SLUG="battery-guardian"
INSTALL_DIR="$APPS_DIR/Battery_Guardian"
VENV_DIR="$INSTALL_DIR/venv"
APP_FILE="$INSTALL_DIR/battery_guardian.py"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_SRC="$PROJECT_DIR/battery_guardian_icon.png"
ICON_DST="$INSTALL_DIR/battery_guardian_icon.png"
LAUNCHER="$INSTALL_DIR/run.sh"

# Detectar carpeta de escritorio (Español o Inglés)
if [ -d "$HOME/Escritorio" ]; then
    DESKTOP_DIR="$HOME/Escritorio"
elif [ -d "$HOME/Desktop" ]; then
    DESKTOP_DIR="$HOME/Desktop"
else
    DESKTOP_DIR="$HOME"
fi
DESKTOP_FILE="$DESKTOP_DIR/${APP_SLUG}.desktop"

MENU_FILE="$HOME/.local/share/applications/${APP_SLUG}.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/${APP_SLUG}.desktop"
BIN_LINK="$HOME/.local/bin/${APP_SLUG}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SYSTEMD_FILE="$SYSTEMD_USER_DIR/${APP_SLUG}.service"

SUDOERS_FILE="/etc/sudoers.d/battery-guardian"
POWEROFF_PATH="/usr/sbin/poweroff"

# Colores
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m"

print_ok()   { echo -e "   [${GREEN}✓${NC}] $1"; }
print_fail() { echo -e "   [${RED}✗${NC}] $1"; }
print_warn() { echo -e "   [${YELLOW}⚠${NC}] $1"; }
print_info() { echo -e "   [i] $1"; }

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  🔋 Instalando $APP_NAME v2.2.9${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "  Origen:  $PROJECT_DIR"
echo -e "  Destino: $INSTALL_DIR"
echo ""

# =========================================================
#  1) DETECTAR DEPENDENCIAS
# =========================================================
echo -e "${BLUE}${BOLD}▶ [1/14] Comprobando dependencias del sistema...${NC}"
echo ""

MISSING_REQUIRED=()
if command -v python3 &>/dev/null; then
    print_ok "python3 → $(python3 --version 2>&1)"
else
    print_fail "python3 → NO INSTALADO"
    MISSING_REQUIRED+=("python3")
fi

if python3 -c "import venv" 2>/dev/null; then
    print_ok "python3-venv (módulo venv)"
else
    print_fail "python3-venv → NO INSTALADO"
    MISSING_REQUIRED+=("python3-venv")
fi

if python3 -c "import tkinter" 2>/dev/null; then
    print_ok "python3-tk (Tkinter)"
else
    print_fail "python3-tk → NO INSTALADO"
    MISSING_REQUIRED+=("python3-tk")
fi

if command -v upower &>/dev/null; then
    print_ok "upower"
else
    print_fail "upower → NO INSTALADO"
    MISSING_REQUIRED+=("upower")
fi

MISSING_RECOMMENDED=()
command -v xprintidle &>/dev/null && print_ok "xprintidle" || { print_warn "xprintidle → NO INSTALADO"; MISSING_RECOMMENDED+=("xprintidle"); }
command -v xdotool    &>/dev/null && print_ok "xdotool"    || { print_warn "xdotool → NO INSTALADO";    MISSING_RECOMMENDED+=("xdotool"); }
command -v xprop      &>/dev/null && print_ok "x11-utils (xprop)" || { print_warn "x11-utils → NO INSTALADO"; MISSING_RECOMMENDED+=("x11-utils"); }

echo ""
print_info "Otras dependencias opcionales:"
command -v pactl  &>/dev/null && print_ok "pactl"  || print_warn "pactl → no instalado"
command -v paplay &>/dev/null && print_ok "paplay" || print_warn "paplay → no instalado"
echo ""

# =========================================================
#  2) OFRECER INSTALAR DEPENDENCIAS FALTANTES
# =========================================================
ALL_MISSING=("${MISSING_REQUIRED[@]}" "${MISSING_RECOMMENDED[@]}")

if [ ${#ALL_MISSING[@]} -gt 0 ]; then
    echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}${BOLD}  ⚠  Faltan dependencias${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo ""
    [ ${#MISSING_REQUIRED[@]} -gt 0 ] && {
        echo -e "  ${RED}${BOLD}OBLIGATORIAS:${NC}"
        for pkg in "${MISSING_REQUIRED[@]}"; do echo "    - $pkg"; done
        echo ""
    }
    [ ${#MISSING_RECOMMENDED[@]} -gt 0 ] && {
        echo -e "  ${YELLOW}${BOLD}RECOMENDADAS:${NC}"
        for pkg in "${MISSING_RECOMMENDED[@]}"; do echo "    - $pkg"; done
        echo ""
    }

    if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
        echo -e "  Se pueden instalar automáticamente con:"
        echo -e "      ${BOLD}sudo apt update && sudo apt install ${ALL_MISSING[*]}${NC}"
        echo ""
        read -r -p "  ¿Quieres que las instale ahora? [s/N]: " RESP
        if [[ "$RESP" =~ ^[sS]$ ]]; then
            echo ""
            echo -e "${BLUE}${BOLD}▶ [2/14] Actualizando repositorios (apt update)...${NC}"
            sudo apt update || true
            print_ok "Repositorios actualizados"
            echo ""
            echo -e "${BLUE}${BOLD}▶ [3/14] Instalando dependencias (apt install)...${NC}"
            if sudo apt install -y "${ALL_MISSING[@]}"; then
                print_ok "Dependencias instaladas"
            else
                print_fail "Falló la instalación"
                exit 1
            fi
            echo ""
        else
            print_fail "No se pueden instalar las dependencias obligatorias."
            echo "  Instálalas manualmente y vuelve a ejecutar ./install.sh:"
            echo "      sudo apt update && sudo apt install ${ALL_MISSING[*]}"
            exit 1
        fi
    else
        echo -e "  Se pueden instalar con: ${BOLD}sudo apt install ${MISSING_RECOMMENDED[*]}${NC}"
        echo ""
        read -r -p "  ¿Quieres instalarlas ahora? [s/N]: " RESP
        if [[ "$RESP" =~ ^[sS]$ ]]; then
            sudo apt update 2>/dev/null || true
            sudo apt install -y "${MISSING_RECOMMENDED[@]}" \
                && print_ok "Instaladas" \
                || print_warn "No se pudieron instalar"
            echo ""
        else
            print_warn "Continuando sin ellas (detecciones limitadas)"
            echo ""
        fi
    fi
else
    echo -e "${GREEN}${BOLD}  ✓ Todas las dependencias están instaladas${NC}"
    echo ""
fi

# =========================================================
#  4) Comprobar archivos del proyecto
# =========================================================
echo -e "${BLUE}${BOLD}▶ [4/14] Comprobando archivos del proyecto...${NC}"

[ ! -f "$ICON_SRC" ] && { print_fail "No se encontró el icono: $ICON_SRC"; exit 1; }
print_ok "Icono: battery_guardian_icon.png"

[ ! -f "$PROJECT_DIR/battery_guardian.py" ] && { print_fail "Falta battery_guardian.py"; exit 1; }
print_ok "Programa: battery_guardian.py"

LICENSE_SRC=""
for candidate in LICENSE.md LICENSE LICENCE.md LICENCE license.md license; do
    if [ -f "$PROJECT_DIR/$candidate" ]; then
        LICENSE_SRC="$PROJECT_DIR/$candidate"
        break
    fi
done
[ -n "$LICENSE_SRC" ] && print_ok "Licencia: $(basename "$LICENSE_SRC")" || print_warn "Sin licencia"
echo ""

# =========================================================
#  5) Detener instancia antigua (SOLO de esta app)
# =========================================================
echo -e "${BLUE}${BOLD}▶ [5/14] Deteniendo instancias antiguas...${NC}"
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
fi
pkill -9 -f "battery_guardian.py" 2>/dev/null || true
sleep 1
print_ok "Sin instancias activas"
echo ""

# =========================================================
#  6) Eliminar SOLO la subcarpeta del programa si existe
# =========================================================
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}El directorio $INSTALL_DIR ya existe. Eliminando instalación anterior...${NC}"
    rm -rf "$INSTALL_DIR"
fi

# =========================================================
#  7) Crear carpeta y copiar TODO
# =========================================================
echo -e "${BLUE}${BOLD}▶ [6/14] Creando carpeta de instalación...${NC}"
mkdir -p "$INSTALL_DIR"
print_ok "$INSTALL_DIR"
echo ""

echo -e "${BLUE}${BOLD}▶ [7/14] Copiando TODOS los archivos del proyecto...${NC}"
tar --exclude='./venv' \
    --exclude='./.git' \
    --exclude='./__pycache__' \
    --exclude='./.idea' \
    --exclude='./.vscode' \
    --exclude='./*.pyc' \
    -cf - -C "$PROJECT_DIR" . | (cd "$INSTALL_DIR" && tar -xf -)

chmod +x "$APP_FILE" 2>/dev/null || true
[ -f "$INSTALL_DIR/install.sh" ]   && chmod +x "$INSTALL_DIR/install.sh"   && print_ok "install.sh"
[ -f "$INSTALL_DIR/uninstall.sh" ] && chmod +x "$INSTALL_DIR/uninstall.sh" && print_ok "uninstall.sh"
print_ok "Archivos copiados"
echo ""

# =========================================================
#  8) Crear entorno virtual
# =========================================================
echo -e "${BLUE}${BOLD}▶ [8/14] Creando entorno virtual...${NC}"
[ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/python" ] && rm -rf "$VENV_DIR"
[ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
[ -x "$VENV_DIR/bin/python" ] || { print_fail "venv roto (bin/python)"; exit 1; }
[ -x "$VENV_DIR/bin/pip" ]    || { print_fail "venv roto (bin/pip)"; exit 1; }
print_ok "venv: $("$VENV_DIR/bin/python" --version 2>&1)"
echo ""

# =========================================================
#  9) Instalar dependencias Python en el venv
# =========================================================
echo -e "${BLUE}${BOLD}▶ [9/14] Instalando dependencias Python en el venv...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
[ -f "$INSTALL_DIR/requirements.txt" ] && \
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

"$VENV_DIR/bin/python" -c "import pystray" 2>/dev/null && print_ok "pystray" || print_warn "pystray"
"$VENV_DIR/bin/python" -c "import PIL"     2>/dev/null && print_ok "Pillow"  || print_warn "Pillow"
echo ""

# =========================================================
#  10) Crear lanzador
# =========================================================
echo -e "${BLUE}${BOLD}▶ [10/14] Creando lanzador...${NC}"
cat > "$LAUNCHER" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/battery_guardian.py" "$@"
LAUNCHER
chmod +x "$LAUNCHER"
print_ok "$LAUNCHER"

mkdir -p "$HOME/.local/bin"
ln -sf "$LAUNCHER" "$BIN_LINK"
print_ok "Enlace CLI: $BIN_LINK"
echo ""

# =========================================================
#  11) Accesos directos
# =========================================================
echo -e "${BLUE}${BOLD}▶ [11/14] Creando accesos directos...${NC}"

# Icono a ~/.local/share/icons para que el sistema lo reconozca
mkdir -p "$HOME/.local/share/icons"
cp -f "$ICON_DST" "$HOME/.local/share/icons/${APP_SLUG}.png" 2>/dev/null || true

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
GenericName=Battery Care
Comment=Cuida la salud de la batería de tu portátil
Exec=$LAUNCHER
Path=$INSTALL_DIR
Icon=$ICON_DST
Terminal=false
Categories=Utility;System;
StartupNotify=true
DESKTOP
chmod +x "$DESKTOP_FILE"
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
print_ok "Escritorio: $DESKTOP_FILE"

mkdir -p "$HOME/.local/share/applications"
cp -f "$DESKTOP_FILE" "$MENU_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
print_ok "Menú: $MENU_FILE"
echo ""

# =========================================================
#  12) Servicio systemd
# =========================================================
echo -e "${BLUE}${BOLD}▶ [12/14] Instalando servicio systemd --user...${NC}"
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
ExecStartPre=/bin/sleep 20
ExecStart=$LAUNCHER --hidden
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=default.target
SYSTEMD

systemctl --user daemon-reload
systemctl --user enable "${APP_SLUG}.service"
systemctl --user start  "${APP_SLUG}.service" || true
print_ok "Servicio systemd configurado (retardo 20 s)"
echo ""

# =========================================================
#  13) Configurar sudoers
# =========================================================
echo -e "${BLUE}${BOLD}▶ [13/14] Configurando sudoers para auto-apagado...${NC}"
echo ""

REAL_POWEROFF="$(which poweroff 2>/dev/null || echo "/usr/sbin/poweroff")"
REAL_SYSTEMCTL="$(which systemctl 2>/dev/null || echo "/usr/bin/systemctl")"
CURRENT_USER="$(whoami)"

print_info "Usuario: $CURRENT_USER"
print_info "poweroff: $REAL_POWEROFF"
print_info "systemctl: $REAL_SYSTEMCTL"
echo ""

SUDOERS_CONTENT="$CURRENT_USER ALL=(ALL) NOPASSWD: $REAL_SYSTEMCTL poweroff, $REAL_POWEROFF, $REAL_POWEROFF --force --force"

read -r -p "  ¿Configurar sudoers para permitir auto-apagado sin contraseña? [S/n]: " RESP_SUDO
if [[ "$RESP_SUDO" =~ ^[nN]$ ]]; then
    print_warn "Omitido. El auto-apagado podría no funcionar sin esto."
    echo ""
else
    TMP_SUDOERS="$(mktemp)"
    echo "$SUDOERS_CONTENT" > "$TMP_SUDOERS"

    if ! sudo visudo -c -f "$TMP_SUDOERS" &>/dev/null; then
        print_fail "Error de sintaxis en sudoers. No se aplica."
        rm -f "$TMP_SUDOERS"
    else
        sudo cp "$TMP_SUDOERS" "$SUDOERS_FILE"
        sudo chmod 0440 "$SUDOERS_FILE"
        sudo chown root:root "$SUDOERS_FILE"
        rm -f "$TMP_SUDOERS"
        print_ok "Creado: $SUDOERS_FILE"

        if sudo -n "$REAL_SYSTEMCTL" poweroff --help &>/dev/null; then
            print_ok "Verificado: sudo -n systemctl poweroff funciona"
        elif sudo -n "$REAL_POWEROFF" --help &>/dev/null; then
            print_ok "Verificado: sudo -n poweroff funciona"
        else
            print_warn "Verificación fallida. Prueba: sudo -n systemctl poweroff --help"
        fi
    fi
fi
echo ""

# =========================================================
#  14) Verificación final
# =========================================================
echo -e "${BLUE}${BOLD}▶ [14/14] Verificando instalación...${NC}"
echo ""
echo "   📂 Contenido de $INSTALL_DIR:"
ls -lh "$INSTALL_DIR" | grep -v "^total" | awk '{printf "      %-40s %s\n", $9, $5}'
echo ""

systemctl --user is-active --quiet "${APP_SLUG}.service" \
    && print_ok "Servicio systemd ACTIVO" \
    || print_warn "Servicio NO activo"

[ -f "$SUDOERS_FILE" ] && print_ok "Sudoers configurado" || print_warn "Sudoers NO configurado"

command -v xprintidle &>/dev/null && print_ok "xprintidle OK" || print_warn "xprintidle NO instalado"
command -v xdotool    &>/dev/null && print_ok "xdotool OK"    || print_warn "xdotool NO instalado"
command -v xprop      &>/dev/null && print_ok "xprop OK"      || print_warn "xprop NO instalado"
echo ""

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo -e "${YELLOW}⚠  Añade ~/.local/bin al PATH:${NC}"
    echo '   echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
    echo '   source ~/.bashrc'
    echo ""
fi

echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ Instalación completada${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  📂 Instalado en:   $INSTALL_DIR"
echo "  📦 venv en:        $VENV_DIR"
echo "  🔧 Sudoers en:     $SUDOERS_FILE"
echo ""
echo "  🖱️  Abrir el programa:"
echo "      - Icono del escritorio"
echo "      - Menú → '$APP_NAME'"
echo "      - Terminal:  $APP_SLUG"
echo ""
echo "  🧪 Diagnóstico:"
echo "      $APP_SLUG --info"
echo "      cd $INSTALL_DIR && ./venv/bin/python battery_guardian.py --debug"
echo ""
echo "  🗑️  Desinstalar:"
echo "      $INSTALL_DIR/uninstall.sh"
echo ""
