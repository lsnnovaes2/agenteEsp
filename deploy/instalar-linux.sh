#!/usr/bin/env bash
#
# Instalador automatico do Cerberus para Linux (systemd).
# Instala o pacote, cria o servico e o inicia em modo AUDITORIA.
#
# Uso:
#   sudo ./instalar-linux.sh                  # instala em modo auditoria
#   sudo ./instalar-linux.sh --bloquear       # ja inicia encerrando processos
#   sudo ./instalar-linux.sh --rede           # tambem agenda a varredura de rede
#   sudo ./instalar-linux.sh --desinstalar    # remove servicos e timers
#
# Opcoes da varredura periodica:
#   --rede                 ativa a varredura de rede agendada (systemd timer)
#   --rede-quando=DIARIO   frequencia (OnCalendar do systemd; padrao "daily")
#   --rede-alvos="A B"     faixas/IPs a varrer (senao usa /etc/cerberus/redes.json)
#
set -euo pipefail

SERVICO="cerberus-sentinel"
DIR_CONF="/etc/cerberus"
DIR_LOG="/var/log/cerberus"
UNIT="/etc/systemd/system/${SERVICO}.service"
REDE_SVC="cerberus-rede"
REDE_UNIT="/etc/systemd/system/${REDE_SVC}.service"
REDE_TIMER="/etc/systemd/system/${REDE_SVC}.timer"
MODO_BLOQUEIO=0
DESINSTALAR=0
INTERVALO=3
REDE=0
REDE_QUANDO="daily"
REDE_ALVOS=""

for arg in "$@"; do
  case "$arg" in
    --bloquear)      MODO_BLOQUEIO=1 ;;
    --desinstalar)   DESINSTALAR=1 ;;
    --intervalo=*)   INTERVALO="${arg#*=}" ;;
    --rede)          REDE=1 ;;
    --rede-quando=*) REDE_QUANDO="${arg#*=}" ;;
    --rede-alvos=*)  REDE_ALVOS="${arg#*=}"; REDE=1 ;;
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
  echo "[*] Removendo a varredura de rede agendada (se existir)..."
  systemctl stop "${REDE_SVC}.timer" 2>/dev/null || true
  systemctl disable "${REDE_SVC}.timer" 2>/dev/null || true
  rm -f "${REDE_UNIT}" "${REDE_TIMER}"
  systemctl daemon-reload
  echo "[*] Servicos removidos. Configuracao em ${DIR_CONF} e logs em ${DIR_LOG} foram mantidos."
  echo "    Remova manualmente se desejar: rm -rf ${DIR_CONF} ${DIR_LOG}"
}

if [[ $DESINSTALAR -eq 1 ]]; then
  desinstalar
  exit 0
fi

echo "[*] Instalando dependencias e pacote Cerberus..."
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "ERRO: python3 nao encontrado." >&2; exit 1
fi
$PY -m pip install --upgrade pip >/dev/null 2>&1 || true
$PY -m pip install "${RAIZ}" >/dev/null

BIN="$(command -v cerberus || echo /usr/local/bin/cerberus)"
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
Description=Cerberus - Sentinel de bloqueio de agentes nao autorizados
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

# -------------------------------------------------- varredura de rede agendada
if [[ $REDE -eq 1 ]]; then
  echo
  echo "[*] Configurando a varredura de rede agendada..."

  # Define os alvos: --rede-alvos tem prioridade; senao usa o redes.json
  if [[ -n "${REDE_ALVOS}" ]]; then
    REDE_CMD_ALVOS="${REDE_ALVOS}"
  else
    if [[ ! -f "${DIR_CONF}/redes.json" && -f "${RAIZ}/config/redes.exemplo.json" ]]; then
      cp "${RAIZ}/config/redes.exemplo.json" "${DIR_CONF}/redes.json"
      echo "[!] ATENCAO: edite ${DIR_CONF}/redes.json com as faixas REAIS da empresa."
    fi
    REDE_CMD_ALVOS="--arquivo ${DIR_CONF}/redes.json"
  fi

  mkdir -p "${DIR_LOG}/rede"

  echo "[*] Gerando ${REDE_UNIT}..."
  cat > "${REDE_UNIT}" <<EOF
[Unit]
Description=Cerberus - Varredura periodica de agentes na rede interna
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
# Grava um JSONL com carimbo de data/hora a cada execucao (%% escapa o % no systemd)
ExecStart=/bin/sh -c '${BIN} ${CONF_ARG} rede ${REDE_CMD_ALVOS} --saida ${DIR_LOG}/rede/rede-\$(date +%%Y%%m%%d-%%H%%M).jsonl'
EOF

  echo "[*] Gerando ${REDE_TIMER} (OnCalendar=${REDE_QUANDO})..."
  cat > "${REDE_TIMER}" <<EOF
[Unit]
Description=Cerberus - Agenda da varredura de rede

[Timer]
OnCalendar=${REDE_QUANDO}
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable "${REDE_SVC}.timer" >/dev/null
  systemctl start "${REDE_SVC}.timer"
  echo "[*] Timer ativo:"
  systemctl --no-pager list-timers "${REDE_SVC}.timer" | head -n 3 || true
fi

echo
echo "[OK] Cerberus instalado."
echo "     Eventos : ${DIR_LOG}/eventos.jsonl"
echo "     Logs    : ${DIR_LOG}/sentinel.log"
echo "     Status  : systemctl status ${SERVICO}"
if [[ $REDE -eq 1 ]]; then
  echo "     Rede    : varredura ${REDE_QUANDO} -> ${DIR_LOG}/rede/*.jsonl"
  echo "     Timer   : systemctl list-timers ${REDE_SVC}.timer"
  echo "     Executar ja: systemctl start ${REDE_SVC}.service"
  echo "     Relatorio: cerberus relatorio ${DIR_LOG}/rede/*.jsonl --formato html --saida /tmp/relatorio.html"
else
  echo "     Relatorio: cerberus relatorio ${DIR_LOG}/eventos.jsonl --formato html --saida /tmp/relatorio.html"
fi
