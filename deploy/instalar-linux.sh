#!/usr/bin/env bash
#
# Instalador automatico do agenteEsp para Linux (systemd).
# Instala o pacote, cria o servico e o inicia em modo AUDITORIA.
#
# Uso:
#   sudo ./instalar-linux.sh                  # instala em modo auditoria
#   sudo ./instalar-linux.sh --bloquear       # ja inicia encerrando processos
#   sudo ./instalar-linux.sh --desinstalar    # remove servico e arquivos
#
set -euo pipefail

SERVICO="agenteesp-sentinel"
DIR_CONF="/etc/agenteesp"
DIR_LOG="/var/log/agenteesp"
UNIT="/etc/systemd/system/${SERVICO}.service"
MODO_BLOQUEIO=0
DESINSTALAR=0
INTERVALO=3

for arg in "$@"; do
  case "$arg" in
    --bloquear)    MODO_BLOQUEIO=1 ;;
    --desinstalar) DESINSTALAR=1 ;;
    --intervalo=*) INTERVALO="${arg#*=}" ;;
    *) echo "Argumento desconhecido: $arg"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "ERRO: execute como root (sudo)." >&2
  exit 1
fi

# Diretorio raiz do projeto (pasta acima de deploy/)
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

desinstalar() {
  echo "[*] Removendo ${SERVICO}..."
  systemctl stop "${SERVICO}" 2>/dev/null || true
  systemctl disable "${SERVICO}" 2>/dev/null || true
  rm -f "${UNIT}"
  systemctl daemon-reload
  echo "[*] Servico removido. Configuracao em ${DIR_CONF} e logs em ${DIR_LOG} foram mantidos."
  echo "    Remova manualmente se desejar: rm -rf ${DIR_CONF} ${DIR_LOG}"
}

if [[ $DESINSTALAR -eq 1 ]]; then
  desinstalar
  exit 0
fi

echo "[*] Instalando dependencias e pacote agenteEsp..."
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "ERRO: python3 nao encontrado." >&2; exit 1
fi
$PY -m pip install --upgrade pip >/dev/null 2>&1 || true
$PY -m pip install "${RAIZ}" >/dev/null

BIN="$(command -v agenteesp || echo /usr/local/bin/agenteesp)"
echo "[*] Binario: ${BIN}"

echo "[*] Criando diretorios..."
mkdir -p "${DIR_CONF}" "${DIR_LOG}"

# Copia um config inicial se ainda nao existir (nao sobrescreve ajustes locais)
if [[ ! -f "${DIR_CONF}/assinaturas.json" && -f "${RAIZ}/config/assinaturas.exemplo.json" ]]; then
  cp "${RAIZ}/config/assinaturas.exemplo.json" "${DIR_CONF}/assinaturas.json"
  echo "[*] Config inicial copiada para ${DIR_CONF}/assinaturas.json (ajuste conforme a politica)."
fi
CONF_ARG=""
[[ -f "${DIR_CONF}/assinaturas.json" ]] && CONF_ARG="--config ${DIR_CONF}/assinaturas.json"

FLAG_BLOQUEIO=""
if [[ $MODO_BLOQUEIO -eq 1 ]]; then
  FLAG_BLOQUEIO=" --bloquear"
  echo "[!] MODO BLOQUEIO: o servico ira ENCERRAR os processos detectados."
else
  echo "[*] MODO AUDITORIA: o servico apenas registra (recomendado para iniciar)."
fi

echo "[*] Gerando unidade systemd em ${UNIT}..."
cat > "${UNIT}" <<EOF
[Unit]
Description=agenteEsp - Sentinel de bloqueio de agentes nao autorizados
After=network.target

[Service]
Type=simple
ExecStart=${BIN} ${CONF_ARG} sentinel${FLAG_BLOQUEIO} --intervalo ${INTERVALO} \\
    --eventos ${DIR_LOG}/eventos.jsonl --log-arquivo ${DIR_LOG}/sentinel.log
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Habilitando e iniciando o servico..."
systemctl daemon-reload
systemctl enable "${SERVICO}" >/dev/null
systemctl restart "${SERVICO}"

sleep 1
echo
systemctl --no-pager --full status "${SERVICO}" | head -n 8 || true
echo
echo "[OK] agenteEsp instalado."
echo "     Eventos : ${DIR_LOG}/eventos.jsonl"
echo "     Logs    : ${DIR_LOG}/sentinel.log"
echo "     Status  : systemctl status ${SERVICO}"
echo "     Relatorio: agenteesp relatorio ${DIR_LOG}/eventos.jsonl --formato html --saida /tmp/relatorio.html"
