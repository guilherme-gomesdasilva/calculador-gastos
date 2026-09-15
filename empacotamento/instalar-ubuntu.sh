#!/usr/bin/env bash
# Instala o Calculador de Gastos para o usuário atual (sem sudo), com atalho no
# menu de aplicativos. Rode na pasta que contém CalculadorDeGastos/:
#   ./instalar-ubuntu.sh            instala (ou atualiza)
#   ./instalar-ubuntu.sh --remover  remove o programa (seus dados ficam)
set -euo pipefail

ORIGEM="$(cd "$(dirname "$0")" && pwd)/CalculadorDeGastos"
DESTINO="$HOME/.local/share/calculador-gastos"
ATALHO="$HOME/.local/share/applications/calculador-gastos.desktop"

if [[ "${1:-}" == "--remover" ]]; then
    rm -rf "$DESTINO" "$ATALHO"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "Calculador de Gastos removido. Seus dados continuam em ~/.local/share/CalculadorGastos"
    exit 0
fi

if [[ ! -x "$ORIGEM/CalculadorDeGastos" ]]; then
    echo "Não encontrei $ORIGEM/CalculadorDeGastos — rode este script na pasta extraída do .tar.gz." >&2
    exit 1
fi

rm -rf "$DESTINO"
mkdir -p "$DESTINO" "$(dirname "$ATALHO")"
cp -r "$ORIGEM" "$DESTINO/"

cat > "$ATALHO" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Calculador de Gastos
Comment=Controle de gastos, rendas e parcelamentos
Exec="$DESTINO/CalculadorDeGastos/CalculadorDeGastos"
Icon=$DESTINO/CalculadorDeGastos/_internal/assets/icone.png
Terminal=false
Categories=Office;Finance;
StartupWMClass=calculador-gastos
DESKTOP
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "Instalado! Procure por \"Calculador de Gastos\" nos aplicativos."
echo "Dados e logos: ~/.local/share/CalculadorGastos (logos em .../logos)"
