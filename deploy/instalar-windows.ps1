<#
    Instalador automatico do Cerberus para Windows.
    Instala o pacote e registra o Sentinel para iniciar com o sistema.

    Usa o Agendador de Tarefas (nativo, sem dependencias externas) para rodar
    o servico em modo auditoria ou bloqueio.

    Execute em um PowerShell COMO ADMINISTRADOR:
        .\instalar-windows.ps1                # modo auditoria (padrao)
        .\instalar-windows.ps1 -Bloquear      # encerra os processos detectados
        .\instalar-windows.ps1 -Desinstalar   # remove a tarefa
#>

[CmdletBinding()]
param(
    [switch]$Bloquear,
    [switch]$Desinstalar,
    [int]$Intervalo = 3
)

$ErrorActionPreference = "Stop"
$NomeTarefa = "Cerberus-Sentinel"
$DirDados   = "C:\ProgramData\cerberus"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Error "Execute este script em um PowerShell como Administrador."
    exit 1
}

if ($Desinstalar) {
    Write-Host "[*] Removendo tarefa $NomeTarefa..."
    schtasks /End /TN $NomeTarefa 2>$null | Out-Null
    schtasks /Delete /TN $NomeTarefa /F 2>$null | Out-Null
    Write-Host "[*] Tarefa removida. Dados mantidos em $DirDados."
    exit 0
}

# Raiz do projeto (pasta acima de deploy\)
$Raiz = Split-Path -Parent $PSScriptRoot

# Localiza o Python
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $py) { Write-Error "Python nao encontrado no PATH. Instale o Python 3.9+ e tente novamente."; exit 1 }

Write-Host "[*] Instalando o pacote Cerberus..."
& $py.Source -m pip install --upgrade pip | Out-Null
& $py.Source -m pip install "$Raiz" | Out-Null

$exe = (Get-Command cerberus -ErrorAction SilentlyContinue)
if (-not $exe) { Write-Error "Comando 'cerberus' nao encontrado apos a instalacao."; exit 1 }
Write-Host "[*] Binario: $($exe.Source)"

New-Item -ItemType Directory -Force -Path $DirDados | Out-Null

# Config inicial (nao sobrescreve ajustes locais)
$confDestino = Join-Path $DirDados "assinaturas.json"
$confExemplo = Join-Path $Raiz "config\assinaturas.exemplo.json"
if ((-not (Test-Path $confDestino)) -and (Test-Path $confExemplo)) {
    Copy-Item $confExemplo $confDestino
    Write-Host "[*] Config inicial copiada para $confDestino (ajuste conforme a politica)."
}
$confArg = ""
if (Test-Path $confDestino) { $confArg = "--config `"$confDestino`"" }

$flagBloqueio = ""
if ($Bloquear) {
    $flagBloqueio = " --bloquear"
    Write-Host "[!] MODO BLOQUEIO: a tarefa ira ENCERRAR os processos detectados."
} else {
    Write-Host "[*] MODO AUDITORIA: a tarefa apenas registra (recomendado para iniciar)."
}

$eventos = Join-Path $DirDados "eventos.jsonl"
$logArq  = Join-Path $DirDados "sentinel.log"
$args = "$confArg sentinel$flagBloqueio --intervalo $Intervalo --eventos `"$eventos`" --log-arquivo `"$logArq`""

Write-Host "[*] Registrando tarefa agendada (inicia no boot, como SYSTEM)..."
# /RL HIGHEST garante privilegios para encerrar processos de outros usuarios
schtasks /Create /TN $NomeTarefa /TR "`"$($exe.Source)`" $args" `
    /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F | Out-Null

Write-Host "[*] Iniciando a tarefa agora..."
schtasks /Run /TN $NomeTarefa | Out-Null

Write-Host ""
Write-Host "[OK] Cerberus instalado."
Write-Host "     Eventos  : $eventos"
Write-Host "     Logs     : $logArq"
Write-Host "     Status   : schtasks /Query /TN $NomeTarefa"
Write-Host "     Relatorio: cerberus relatorio `"$eventos`" --formato html --saida `"$DirDados\relatorio.html`""
