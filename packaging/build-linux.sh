#!/usr/bin/env bash
#
# Gera o executavel standalone do painel desktop do Cerberus para Linux.
# Resultado: dist/cerberus-painel (binario unico, roda sem instalar Python).
#
# Uso:  ./packaging/build-linux.sh
#
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${RAIZ}"

echo "[*] Instalando dependencias de build..."
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install . pyinstaller >/dev/null

# Tkinter e necessario em tempo de build e de execucao
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "[!] Tkinter nao encontrado. Instale antes de empacotar:"
  echo "      Debian/Ubuntu : sudo apt install python3-tk"
  echo "      Fedora/RHEL   : sudo dnf install python3-tkinter"
  exit 1
fi

echo "[*] Limpando builds anteriores..."
rm -rf build dist

echo "[*] Empacotando com PyInstaller..."
pyinstaller packaging/cerberus-painel.spec --clean --noconfirm

echo
if [[ -f dist/cerberus-painel ]]; then
  chmod +x dist/cerberus-painel
  echo "[OK] Executavel gerado: dist/cerberus-painel"
  echo "     Rode com: ./dist/cerberus-painel"
  echo "     (binario standalone; copie para as estacoes Linux sem Python)"
else
  echo "[ERRO] O executavel nao foi gerado. Verifique a saida acima." >&2
  exit 1
fi
