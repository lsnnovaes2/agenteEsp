<#
    Gera o executavel standalone do painel desktop do Cerberus para Windows.
    Resultado: dist\cerberus-painel.exe (roda sem instalar Python).

    Execute em um PowerShell:
        .\packaging\build-windows.ps1
#>

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

Write-Host "[*] Instalando dependencias de build..."
python -m pip install --upgrade pip | Out-Null
python -m pip install . pyinstaller | Out-Null

Write-Host "[*] Limpando builds anteriores..."
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "[*] Empacotando com PyInstaller..."
pyinstaller packaging\cerberus-painel.spec --clean --noconfirm

Write-Host ""
if (Test-Path dist\cerberus-painel.exe) {
    Write-Host "[OK] Executavel gerado: dist\cerberus-painel.exe"
    Write-Host "     Distribua o .exe para as estacoes Windows (sem Python)."
} else {
    Write-Error "O executavel nao foi gerado. Verifique a saida acima."
    exit 1
}
