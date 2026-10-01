# Manual de Instalação e Uso — Cerberus

Guia completo para instalar e operar o **Cerberus** em **Linux** e **Windows**.

> ⚠️ **Uso autorizado apenas.** Utilize somente em equipamentos e redes que a
> sua organização administra e tem o direito de auditar. A operação deve ser
> aprovada pela área de Segurança/TI e comunicada aos usuários conforme a
> política interna. O Cerberus inicia sempre em **modo auditoria** (apenas
> registra); o encerramento de processos é **opt-in**.

## Índice

1. [Visão geral](#1-visão-geral)
2. [Pré-requisitos](#2-pré-requisitos)
3. [Instalação no Linux](#3-instalação-no-linux)
4. [Instalação no Windows](#4-instalação-no-windows)
5. [Uso dos componentes](#5-uso-dos-componentes)
6. [Painel desktop](#6-painel-desktop)
7. [Redes segmentadas (VLANs)](#7-redes-segmentadas-vlans)
8. [Rodando em container (Linux)](#8-rodando-em-container-linux)
9. [Configuração por política](#9-configuração-por-política)
10. [Desinstalação](#10-desinstalação)
11. [Solução de problemas](#11-solução-de-problemas)

---

## 1. Visão geral

| Componente | Comando | Função |
|------------|---------|--------|
| Sentinel | `cerberus sentinel` | Monitora os processos **da máquina local** e audita/encerra agentes. |
| Varredura de rede | `cerberus rede` | Procura agentes expostos em **faixas de IP**, de um ponto só. |
| Painel desktop | `cerberus painel` | Interface gráfica da varredura de rede. |
| Sinkhole DNS | `cerberus sinkhole` | Gera listas de bloqueio de domínios. |
| Firewall | `cerberus firewall` | Gera regras de bloqueio de portas. |
| Relatório | `cerberus relatorio` | Consolida os eventos por equipamento. |

As duas abordagens de detecção são complementares: o **sentinel** (um por
máquina) independe de rede e vê tudo; a **varredura** cobre a rede inteira sem
instalar nada nas estações, mas só vê agentes que expõem porta.

## 2. Pré-requisitos

- **Python 3.9 ou superior** (Linux e Windows).
- **Privilégios de administrador/root** para o sentinel ver e encerrar
  processos de outros usuários.
- **Tkinter** apenas para o painel desktop (no Windows já vem com o Python; no
  Linux pode exigir um pacote do sistema — ver abaixo).

Verifique o Python:

```bash
python3 --version      # Linux
python --version       # Windows
```

---

## 3. Instalação no Linux

### 3.1. Instalação automática (recomendada)

Usa `systemd` e inicia o serviço em **modo auditoria**.

```bash
# 1. Obtenha o projeto
git clone https://github.com/lsnnovaes2/agenteEsp.git
cd agenteEsp

# 2. Rode o instalador como root
sudo ./deploy/instalar-linux.sh

# 3. Acompanhe o serviço e os eventos
systemctl status cerberus-sentinel
tail -f /var/log/cerberus/eventos.jsonl
```

Para **ativar o bloqueio** (encerrar os processos) após validar os eventos:

```bash
sudo ./deploy/instalar-linux.sh --bloquear
```

Opções: `--intervalo=N` (segundos entre varreduras) e `--desinstalar`.

O instalador cria:
- Serviço `cerberus-sentinel` (inicia no boot);
- `/etc/cerberus/assinaturas.json` (configuração);
- `/var/log/cerberus/eventos.jsonl` e `sentinel.log`.

### 3.2. Instalação manual (sem serviço)

```bash
cd agenteEsp
python3 -m pip install .
# auditoria pontual:
sudo cerberus sentinel --eventos /var/log/cerberus/eventos.jsonl
```

### 3.3. Distribuição em massa

Chame o `deploy/instalar-linux.sh` via **Ansible/Puppet/SSH** em todas as
estações, apontando o `eventos.jsonl` para um compartilhamento central.

---

## 4. Instalação no Windows

### 4.1. Instalação automática (recomendada)

Registra o Sentinel no **Agendador de Tarefas** nativo (inicia no boot como
`SYSTEM`, sem dependências externas).

```powershell
# Abra o PowerShell COMO ADMINISTRADOR
cd caminho\para\agenteEsp
.\deploy\instalar-windows.ps1
```

Para **ativar o bloqueio** após validar:

```powershell
.\deploy\instalar-windows.ps1 -Bloquear
```

Opções: `-Intervalo N` e `-Desinstalar`.

O instalador cria:
- Tarefa agendada `Cerberus-Sentinel`;
- `C:\ProgramData\cerberus\assinaturas.json`;
- `C:\ProgramData\cerberus\eventos.jsonl` e `sentinel.log`.

Acompanhe:

```powershell
schtasks /Query /TN Cerberus-Sentinel
Get-Content C:\ProgramData\cerberus\eventos.jsonl -Wait
```

### 4.2. Instalação manual (sem serviço)

```powershell
cd agenteEsp
python -m pip install .
# auditoria pontual (PowerShell como Administrador):
cerberus sentinel --eventos C:\ProgramData\cerberus\eventos.jsonl
```

### 4.3. Distribuição em massa

Distribua o `deploy\instalar-windows.ps1` via **GPO** ou **Intune**.

---

## 5. Uso dos componentes

Os comandos abaixo valem igualmente para Linux e Windows (troque os caminhos).

### 5.1. Sentinel (processos locais)

```bash
# Auditoria (não encerra nada):
sudo cerberus sentinel --eventos eventos.jsonl

# Bloqueio (encerra os processos detectados):
sudo cerberus sentinel --bloquear --eventos eventos.jsonl

# Com configuração própria:
sudo cerberus --config /etc/cerberus/assinaturas.json sentinel --bloquear
```

### 5.2. Varredura de rede

```bash
# Uma ou mais faixas:
cerberus rede 10.0.0.0/24 192.168.1.0/24 --formato html --saida rede.html

# Gerar eventos para juntar ao relatório:
cerberus rede 10.0.0.0/24 --saida eventos-rede.jsonl
```

> A varredura **não exige abrir porta** na máquina que a executa — ela só faz
> conexões de saída para os alvos.

### 5.3. Bloqueio de perímetro

```bash
# DNS sinkhole (Pi-hole, hosts, dnsmasq, rpz):
cerberus sinkhole --formato pihole --saida cerberus.list

# Firewall (iptables ou windows):
cerberus firewall --plataforma iptables --saida bloquear-portas.sh
cerberus firewall --plataforma windows  --saida bloquear-portas.bat
```

### 5.4. Relatório consolidado

```bash
# Tabela no terminal:
cerberus relatorio eventos.jsonl

# Vários hosts/segmentos, em HTML ou CSV:
cerberus relatorio coletas/*.jsonl --formato html --saida relatorio.html
cerberus relatorio coletas/*.jsonl --formato csv  --saida relatorio.csv
```

Colunas: segmento (VLAN), host, IP, agente/modelo, tipo, ação, ocorrências,
usuários, quantidade de agentes na máquina. Múltiplos agentes de uma mesma
máquina ficam agrupados.

---

## 6. Painel desktop

Interface gráfica para a varredura de rede.

### 6.1. Via Python (Linux e Windows)

```bash
cerberus painel
```

No **Linux**, se o Tkinter faltar:
- Debian/Ubuntu: `sudo apt install python3-tk`
- Fedora/RHEL: `sudo dnf install python3-tkinter`

### 6.2. Executável standalone (sem Python instalado)

Gere um binário único para distribuir às estações:

**Linux:**
```bash
./packaging/build-linux.sh
# resultado: dist/cerberus-painel
./dist/cerberus-painel
```

**Windows:**
```powershell
.\packaging\build-windows.ps1
# resultado: dist\cerberus-painel.exe
```

> O executável é gerado para o sistema em que você roda o build (um binário
> Linux não roda no Windows e vice-versa).

No painel: informe as faixas, escolha os serviços, clique em **Varrer rede** e
os resultados (máquina, IP, agente, porta) aparecem na tabela, com exportação
para HTML/CSV.

---

## 7. Redes segmentadas (VLANs)

Em redes com muitas VLANs, um scanner num ponto só não alcança os demais
segmentos. Estratégias (combine-as):

**A) `sentinel` em cada máquina — independe de VLAN** (cobertura mais completa).
Distribua por GPO/Intune (Windows) ou Ansible/SSH (Linux).

**B) Varredura por segmento.** Liste as VLANs num arquivo (ver
`config/redes.exemplo.json`) e varra todas de uma vez:

```bash
cerberus rede --arquivo config/redes.exemplo.json --formato html --saida rede.html
```

Se o host central não tiver rota até todas as VLANs, rode uma instância por
segmento, cada uma gravando seu `eventos.jsonl` numa pasta comum, e consolide:

```bash
cerberus relatorio coletas/*.jsonl --formato html --saida consolidado.html
```

O relatório exibe a coluna **VLAN/segmento** por equipamento.

---

## 8. Rodando em container (Linux)

> Por padrão, um container só enxerga **os próprios processos**. Para o sentinel
> vigiar a máquina hospedeira, use `pid: host` e `network_mode: host` (já
> configurados no compose).

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

A varredura (`cerberus rede`) funciona em qualquer container, desde que haja
rota até os alvos.

---

## 9. Configuração por política

Estenda as assinaturas sem alterar o código, via JSON (ver
`config/assinaturas.exemplo.json`):

```json
{
  "adicionar_binarios": ["meuagente-interno"],
  "adicionar_portas_proibidas": { "9100": "Agente proprietario" },
  "adicionar_usuarios_autorizados": ["pesquisa"]
}
```

Chaves `adicionar_*` somam às listas padrão; `substituir_*` trocam a lista
inteira. Aplique com `--config`:

```bash
sudo cerberus --config /etc/cerberus/assinaturas.json sentinel --bloquear
```

O **painel web** (HTML) ajuda a montar esse arquivo marcando os agentes
desejados.

---

## 10. Desinstalação

**Linux:**
```bash
sudo ./deploy/instalar-linux.sh --desinstalar
# opcional: remover dados
sudo rm -rf /etc/cerberus /var/log/cerberus
python3 -m pip uninstall cerberus
```

**Windows (PowerShell como Administrador):**
```powershell
.\deploy\instalar-windows.ps1 -Desinstalar
# opcional: remover dados
Remove-Item -Recurse -Force C:\ProgramData\cerberus
python -m pip uninstall cerberus
```

---

## 11. Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Acesso negado` ao encerrar processo | Sentinel sem privilégios | Rode como root (Linux) / tarefa como SYSTEM (Windows). |
| Painel não abre no Linux | Tkinter ausente | `sudo apt install python3-tk` (ou `dnf install python3-tkinter`). |
| Varredura não acha nada em outra VLAN | Firewall entre segmentos | Libere a saída do host ou rode uma instância por VLAN. |
| Container só vê os próprios processos | Namespace de PID isolado | Suba com `pid: host` / `network_mode: host` (ver §8). |
| `cerberus` não encontrado após instalar | Scripts do pip fora do PATH | Garanta que o diretório de scripts do Python está no PATH. |
| Nenhum evento no relatório | `eventos.jsonl` vazio | Confirme que o sentinel está rodando e gravando no caminho certo. |

Para dúvidas sobre comandos: `cerberus --help` e `cerberus <comando> --help`.
