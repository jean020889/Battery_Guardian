
#!/bin/bash
# =========================================================
#  Battery Guardian - Instalador v2.2.0
# =========================================================
#  Instala el programa en un entorno virtual (venv) en:
#      /home/asus/Apps/Battery_Guardian/
#  Y crea:
#      - Icono en el escritorio (battery_guardian_icon.png)
#      - Entrada en el menú de aplicaciones
#      - Servicio systemd --user (arranque automático + auto-reinicio)
#      - Enlace CLI en ~/.local/bin
#
#  DETECTA dependencias faltantes y pide permiso para instalarlas:
#      - python3, python3-venv, python3-tk, upower  (OBLIGATORIAS)
#      - xprintidle                                (RECOMENDADA)
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
echo -e "${BOLD}  🔋 Instalando $APP_NAME v2.2.0${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "  Origen:  $PROJECT_DIR"
echo -e "  Destino: $INSTALL_DIR"
echo ""


# =========================================================
#  1) DETECTAR DEPENDENCIAS
# =========================================================
echo -e "${BLUE}${BOLD}▶ [1/13] Comprobando dependencias del sistema...${NC}"
echo ""

# --- Dependencias OBLIGATORIAS ---
MISSING_REQUIRED=()

# python3
if command -v python3 &>/dev/null; then
    print_ok "python3 → $(python3 --version 2>&1)"
else
    print_fail "python3 → NO INSTALADO"
    MISSING_REQUIRED+=("python3")
fi

# python3-venv (módulo venv)
if python3 -c "import venv" 2>/dev/null; then
    print_ok "python3-venv (módulo venv)"
else
    print_fail "python3-venv → NO INSTALADO"
    MISSING_REQUIRED+=("python3-venv")
fi

# python3-tk (Tkinter)
if python3 -c "import tkinter" 2>/dev/null; then
    print_ok "python3-tk (Tkinter)"
else
    print_fail "python3-tk → NO INSTALADO"
    MISSING_REQUIRED+=("python3-tk")
fi

# upower
if command -v upower &>/dev/null; then
    print_ok "upower"
else
    print_fail "upower → NO INSTALADO"
    MISSING_REQUIRED+=("upower")
fi

# --- Dependencia RECOMENDADA ---
MISSING_RECOMMENDED=()

# xprintidle
if command -v xprintidle &>/dev/null; then
    print_ok "xprintidle (detección de inactividad)"
else
    print_warn "xprintidle → NO INSTALADO (necesario para auto-apagado)"
    MISSING_RECOMMENDED+=("xprintidle")
fi

# --- Otras útiles (opcionales, informativas) ---
echo ""
print_info "Otras dependencias opcionales:"

if command -v pactl &>/dev/null; then
    print_ok "pactl (detección de multimedia)"
else
    print_warn "pactl → no instalado (viene con PulseAudio/PipeWire)"
fi

if command -v paplay &>/dev/null; then
    print_ok "paplay (reproducción del pitido)"
else
    print_warn "paplay → no instalado (instala pulseaudio-utils)"
fi

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
    if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
        echo -e "  ${RED}${BOLD}OBLIGATORIAS (sin ellas el programa no funciona):${NC}"
        for pkg in "${MISSING_REQUIRED[@]}"; do
            echo "    - $pkg"
        done
        echo ""
    fi
    if [ ${#MISSING_RECOMMENDED[@]} -gt 0 ]; then
        echo -e "  ${YELLOW}${BOLD}RECOMENDADAS (mejoran funciones):${NC}"
        for pkg in "${MISSING_RECOMMENDED[@]}"; do
            echo "    - $pkg"
        done
        echo ""
    fi

    # --- Si faltan obligatorias, preguntar ---
    if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
        echo -e "  Se pueden instalar automáticamente con:"
        echo -e "      ${BOLD}sudo apt update && sudo apt install ${ALL_MISSING[*]}${NC}"
        echo ""
        read -r -p "  ¿Quieres que las instale ahora? [s/N]: " RESP

        if [[ "$RESP" =~ ^[sS]$ ]]; then
            echo ""
            echo -e "${BLUE}${BOLD}▶ [2/13] Actualizando repositorios (apt update)...${NC}"
            if sudo apt update; then
                print_ok "Repositorios actualizados"
            else
                print_fail "No se pudo actualizar los repositorios"
                echo ""
                read -r -p "  ¿Continuar de todas formas? [s/N]: " CONT
                [[ "$CONT" =~ ^[sS]$ ]] || { echo "  Cancelado."; exit 1; }
            fi
            echo ""

            echo -e "${BLUE}${BOLD}▶ [3/13] Instalando dependencias (apt install)...${NC}"
            if sudo apt install -y "${ALL_MISSING[@]}"; then
                print_ok "Dependencias instaladas"
            else
                print_fail "Falló la instalación de dependencias"
                echo ""
                echo "  Instálalas manualmente:"
                echo "      sudo apt install ${ALL_MISSING[*]}"
                exit 1
            fi
            echo ""

            # Re-verificar
            echo "   Verificando instalación..."
            for pkg in "${ALL_MISSING[@]}"; do
                case "$pkg" in
                    python3)        command -v python3 &>/dev/null && print_ok "python3" || { print_fail "python3"; exit 1; } ;;
                    python3-venv)   python3 -c "import venv" 2>/dev/null && print_ok "python3-venv" || { print_fail "python3-venv"; exit 1; } ;;
                    python3-tk)     python3 -c "import tkinter" 2>/dev/null && print_ok "python3-tk" || { print_fail "python3-tk"; exit 1; } ;;
                    upower)         command -v upower &>/dev/null && print_ok "upower" || { print_fail "upower"; exit 1; } ;;
                    xprintidle)     command -v xprintidle &>/dev/null && print_ok "xprintidle" || print_warn "xprintidle (no crítico)" ;;
                esac
            done
            echo ""

        else
            # El usuario dijo que no
            echo ""
            echo -e "  ${RED}No se pueden instalar las dependencias obligatorias.${NC}"
            echo ""
            echo "  Instálalas manualmente y vuelve a ejecutar ./install.sh:"
            echo "      sudo apt update"
            echo "      sudo apt install ${ALL_MISSING[*]}"
            echo ""
            exit 1
        fi

    else
        # Solo faltan las recomendadas
        echo -e "  Se pueden instalar automáticamente con:"
        echo -e "      ${BOLD}sudo apt install ${MISSING_RECOMMENDED[*]}${NC}"
        echo ""
        read -r -p "  ¿Quieres que las instale ahora? [s/N]: " RESP

        if [[ "$RESP" =~ ^[sS]$ ]]; then
            echo ""
            echo -e "${BLUE}${BOLD}▶ [2/13] Instalando dependencias recomendadas...${NC}"
            sudo apt update 2>/dev/null || true
            if sudo apt install -y "${MISSING_RECOMMENDED[@]}"; then
                print_ok "Dependencias recomendadas instaladas"
            else
                print_warn "No se pudieron instalar (el programa seguirá funcionando)"
            fi
            echo ""
        else
            echo ""
            print_warn "Continuando sin las dependencias recomendadas"
            print_info "El auto-apagado por inactividad no funcionará sin xprintidle"
            echo ""
        fi
    fi

else
    echo -e "${GREEN}${BOLD}  ✓ Todas las dependencias están instaladas${NC}"
    echo ""
fi

# =========================================================
#  4) Comprobar archivos requeridos
# =========================================================
echo -e "${BLUE}${BOLD}▶ [4/13] Comprobando archivos del proyecto...${NC}"

if [ ! -f "$ICON_SRC" ]; then
    echo ""
    print_fail "No se encontró el icono:"
    echo "       $ICON_SRC"
    echo "   Asegúrate de que 'battery_guardian_icon.png' está en la raíz del proyecto."
    exit 1
fi
print_ok "Icono: battery_guardian_icon.png"

if [ ! -f "$PROJECT_DIR/battery_guardian.py" ]; then
    print_fail "Falta battery_guardian.py"
    exit 1
fi
print_ok "Programa: battery_guardian.py"

LICENSE_SRC=""
if [ -f "$PROJECT_DIR/LICENSE.md" ]; then
    LICENSE_SRC="$PROJECT_DIR/LICENSE.md"
    print_ok "Licencia: LICENSE.md"
elif [ -f "$PROJECT_DIR/LICENSE" ]; then
    LICENSE_SRC="$PROJECT_DIR/LICENSE"
    print_ok "Licencia: LICENSE"
else
    print_warn "Sin licencia (no se copiará)"
fi
echo ""

# =========================================================
#  5) Detener instancia antigua
# =========================================================
echo -e "${BLUE}${BOLD}▶ [5/13] Deteniendo instancias antiguas...${NC}"
if systemctl --user list-unit-files 2>/dev/null | grep -q "${APP_SLUG}.service"; then
    systemctl --user stop "${APP_SLUG}.service" 2>/dev/null || true
    systemctl --user disable "${APP_SLUG}.service" 2>/dev/null || true
fi
pkill -9 -f "battery_guardian.py" 2>/dev/null || true
sleep 1
print_ok "Sin instancias activas"
echo ""

# =========================================================
#  6) Crear carpeta de instalación
# =========================================================
echo -e "${BLUE}${BOLD}▶ [6/13] Creando carpeta de instalación...${NC}"
mkdir -p "$INSTALL_DIR"
print_ok "$INSTALL_DIR"
echo ""

# =========================================================
#  7) Copiar archivos
# =========================================================
echo -e "${BLUE}${BOLD}▶ [7/13] Copiando archivos...${NC}"
cp -f "$PROJECT_DIR/battery_guardian.py" "$APP_FILE"
chmod +x "$APP_FILE"
cp -f "$ICON_SRC" "$ICON_DST"

[ -f "$PROJECT_DIR/requirements.txt" ] && cp -f "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
[ -f "$PROJECT_DIR/README.md" ]        && cp -f "$PROJECT_DIR/README.md"        "$INSTALL_DIR/"
[ -n "$LICENSE_SRC" ]                  && cp -f "$LICENSE_SRC"                  "$INSTALL_DIR/"
[ -f "$PROJECT_DIR/Installation_instructions.md" ] && \
    cp -f "$PROJECT_DIR/Installation_instructions.md" "$INSTALL_DIR/"
[ -f "$PROJECT_DIR/.gitignore" ]       && cp -f "$PROJECT_DIR/.gitignore"       "$INSTALL_DIR/"

print_ok "Archivos copiados"
echo ""

# =========================================================
#  8) Crear entorno virtual
# =========================================================
echo -e "${BLUE}${BOLD}▶ [8/13] Creando entorno virtual...${NC}"
[ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/python" ] && rm -rf "$VENV_DIR"
[ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
[ -x "$VENV_DIR/bin/python" ] || { print_fail "venv roto (bin/python)"; exit 1; }
[ -x "$VENV_DIR/bin/pip" ]    || { print_fail "venv roto (bin/pip)"; exit 1; }
print_ok "venv: $("$VENV_DIR/bin/python" --version 2>&1)"
echo ""

# =========================================================
#  9) Instalar dependencias Python en el venv
# =========================================================
echo -e "${BLUE}${BOLD}▶ [9/13] Instalando dependencias Python en el venv...${NC}"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
[ -f "$INSTALL_DIR/requirements.txt" ] && \
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

"$VENV_DIR/bin/python" -c "import pystray" 2>/dev/null && print_ok "pystray" || print_warn "pystray"
"$VENV_DIR/bin/python" -c "import PIL"     2>/dev/null && print_ok "Pillow"  || print_warn "Pillow"
echo ""

# =========================================================
#  10) Crear lanzador
# =========================================================
echo -e "${BLUE}${BOLD}▶ [10/13] Creando lanzador...${NC}"
cat > "$LAUNCHER" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/battery_guardian.py" "$@"
LAUNCHER
chmod +x "$LAUNCHER"
print_ok "$LAUNCHER"

# Enlace CLI
mkdir -p "$HOME/.local/bin"
ln -sf "$LAUNCHER" "$BIN_LINK"
print_ok "Enlace CLI: $BIN_LINK"
echo ""

# =========================================================
#  11) Accesos directos
# =========================================================
echo -e "${BLUE}${BOLD}▶ [11/13] Creando accesos directos...${NC}"
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
print_ok "Escritorio: $DESKTOP_FILE"

mkdir -p "$HOME/.local/share/applications"
cp -f "$DESKTOP_FILE" "$MENU_FILE"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
print_ok "Menú: $MENU_FILE"
echo ""

# =========================================================
#  12) Servicio systemd con retardo
# =========================================================
echo -e "${BLUE}${BOLD}▶ [12/13] Instalando servicio systemd --user...${NC}"
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
# Retardo de 20 s para no competir con el escritorio al arrancar
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
#  13) Verificación final
# =========================================================
echo -e "${BLUE}${BOLD}▶ [13/13] Verificando instalación...${NC}"
echo ""
echo "   📂 Contenido de $INSTALL_DIR:"
ls -lh "$INSTALL_DIR" | grep -v "^total" | awk '{printf "      %-40s %s\n", $9, $5}'
echo ""

if systemctl --user is-active --quiet "${APP_SLUG}.service"; then
    print_ok "Servicio systemd ACTIVO"
else
    print_warn "Servicio NO activo (revisa: systemctl --user status ${APP_SLUG}.service)"
fi
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
echo "  📂 Instalado en:  $INSTALL_DIR"
echo "  📦 venv en:       $VENV_DIR"
echo "  ⏱️  Arranque:      retrasado 20 s tras iniciar sesión"
echo ""
if ! command -v xprintidle &>/dev/null; then
    echo -e "  ${YELLOW}⚠  xprintidle NO instalado${NC}"
    echo "     El auto-apagado por inactividad NO funcionará."
    echo "     Instálalo después con:"
    echo "         sudo apt install xprintidle"
    echo ""
fi
echo "  🖱️  Abrir el programa:"
echo "      - Icono del escritorio"
echo "      - Menú → '$APP_NAME'"
echo "      - Terminal:  $APP_SLUG"
echo ""
echo "  🗑️  Desinstalar:  $PROJECT_DIR/uninstall.sh"
echo ""

