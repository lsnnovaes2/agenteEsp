# agenteEsp - instalacao do Sentinel como servico do Windows
# Execute em um PowerShell como Administrador.
# Requer o utilitario NSSM (https://nssm.cc) no PATH para registrar o servico.

$ErrorActionPreference = "Stop"

Write-Host "Instalando agenteEsp..."
python -m pip install --upgrade .

$exe = (Get-Command agenteesp).Source
$logDir = "C:\ProgramData\agenteesp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Registra o servico em modo AUDITORIA. Para encerrar processos, acrescente
# o argumento --bloquear apos validar os eventos coletados.
nssm install agenteEsp $exe "sentinel --intervalo 3 --eventos $logDir\eventos.jsonl --log-arquivo $logDir\sentinel.log"
nssm set agenteEsp Start SERVICE_AUTO_START
nssm start agenteEsp

Write-Host "Servico 'agenteEsp' instalado e iniciado em modo auditoria."
Write-Host "Eventos: $logDir\eventos.jsonl"
