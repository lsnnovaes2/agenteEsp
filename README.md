# Cerberus

Ferramenta de **conformidade corporativa** para detectar e bloquear o uso de
agentes de IA e túneis de rede **não autorizados** nas estações e na rede
interna da empresa, conforme a política de segurança.

> ⚠️ **Uso autorizado apenas.** Implante estas ferramentas somente em
> equipamentos e redes que a sua organização administra e tem o direito de
> auditar. A operação deve ser aprovada pela área de Segurança/TI e
> comunicada aos usuários conforme a política interna.

O projeto ataca o problema em duas camadas, por ser mais eficaz do que
qualquer medida isolada:

| Camada | Componente | O que faz |
|--------|------------|-----------|
| **Endpoint** | `sentinel` | Varre os processos locais e audita ou encerra agentes de IA locais (Ollama, LM Studio, LocalAI…), frameworks autônomos (CrewAI, AutoGPT…) e túneis reversos (ngrok, cloudflared, frp…). |
| **Rede** | `rede` | Varre faixas de IP da rede interna, de um ponto só, procurando agentes expostos — sem precisar de instalação em cada máquina. Alimenta o mesmo relatório. |
| **Perímetro** | `sinkhole` / `firewall` | Gera listas de bloqueio de DNS (Pi-hole, BIND RPZ, dnsmasq, hosts) e regras de firewall (iptables, Windows) para barrar a comunicação dos agentes com provedores de IA e serviços de túnel. |
| **Relatório** | `relatorio` | Consolida os eventos das máquinas em um inventário por equipamento (agente/modelo, IP, nome da máquina), agrupando múltiplos agentes de um mesmo host. Saídas: texto, JSON, CSV, HTML. |

As duas abordagens são complementares: o **`sentinel`** (um agente por máquina)
vê tudo, inclusive processos que não abrem porta; a **`rede`** (varredura a
partir de um ponto) cobre a rede inteira sem instalar nada nas estações, mas só
enxerga agentes que expõem uma porta. Use as duas juntas.

## Instalação

```bash
pip install .          # instala o pacote e o comando `cerberus`
# para desenvolvimento/testes:
pip install -e ".[dev]"
```

Dependência: `psutil` (apenas o `sentinel` a usa; os geradores de bloqueio
usam só a biblioteca padrão).

## Uso

### 1. Sentinel de endpoint

Comece **sempre em modo auditoria** (padrão): ele apenas registra, sem
encerrar nada. Analise os eventos coletados e só então ative o bloqueio.

```bash
# Auditoria (não encerra nada, apenas registra):
sudo cerberus sentinel --eventos /var/log/cerberus/eventos.jsonl

# Bloqueio efetivo (encerra os processos em violação):
sudo cerberus sentinel --bloquear --eventos /var/log/cerberus/eventos.jsonl
```

Precisa de **root/Administrador** para enxergar e encerrar processos de
outros usuários. Cada violação vira uma linha JSON com host, PID, usuário,
regra acionada e comando — ideal para encaminhar a um SIEM.

**Regras de detecção** (desenhadas para evitar falsos positivos):
- **Executável proibido** — pelo nome do processo *ou* pelo caminho real do
  binário (pega agentes renomeados).
- **Framework na linha de comando** — só quando o processo é um
  interpretador (`python`, `node`, `java`…); um navegador abrindo um arquivo
  chamado `crewai.html` não dispara. Comandos de `pip install`/`npm install`
  são ignorados (instalar ≠ executar).
- **Porta característica** — escuta em `11434` (Ollama), `1234` (LM Studio),
  `4040` (ngrok) gera encerramento; portas genéricas (`3000`, `8000`,
  `8080`) apenas geram alerta para verificação manual.
- **Isenções** — processos críticos do SO nunca são tocados, e é possível
  liberar usuários homologados (ex.: laboratório de P&D).

### 2. Bloqueio no perímetro (DNS + firewall)

```bash
# Lista de DNS para o Pi-hole:
cerberus sinkhole --formato pihole --saida /etc/pihole/cerberus.list

# Zona RPZ para BIND, ou formato dnsmasq/hosts:
cerberus sinkhole --formato rpz --saida db.cerberus.rpz

# Regras de firewall:
cerberus firewall --plataforma iptables --saida bloquear-portas.sh
cerberus firewall --plataforma windows  --saida bloquear-portas.bat
```

Os arquivos gerados são **configuração para revisão** — nada é aplicado
automaticamente. A equipe de rede valida e aplica nos equipamentos
homologados.

### 3. Varredura da rede interna (de um ponto só)

Rode a partir de um servidor da TI/Segurança para verificar faixas inteiras de
IP **da sua empresa**, sem agente instalado nas estações:

```bash
# Gera eventos (jsonl) para juntar ao relatório:
cerberus rede 10.0.0.0/24 192.168.1.0/24 --saida eventos-rede.jsonl

# Ou já monta o relatório consolidado direto:
cerberus rede 10.0.0.0/24 --formato html --saida relatorio-rede.html
```

A varredura **não precisa abrir nenhuma porta** na máquina que a executa, nem
no firewall, para conexões de saída dentro da rede local — ela apenas *conecta*
nas portas dos hosts-alvo (ex.: 11434 do Ollama) e confirma por uma requisição
HTTP no endpoint de identificação do serviço. Em redes segmentadas (VLANs), o
firewall entre as sub-redes precisa **permitir a saída** do host de varredura
para essas portas nos alvos — ou rode uma instância por segmento.

#### Painel desktop (interface gráfica)

Para quem prefere uma janela em vez do terminal, há um painel desktop (Tkinter,
já incluso no Python) que faz a mesma varredura e lista as máquinas com IA:

```bash
cerberus painel          # ou, após instalar: cerberus-painel
```

Informe as faixas, escolha os serviços, clique em **Varrer rede** e os
resultados (máquina, IP, agente, porta) aparecem na tabela, com exportação para
HTML/CSV. No Linux, instale o Tkinter se faltar: `sudo apt install python3-tk`.

### 4. Relatório consolidado por equipamento

Cada máquina grava suas detecções em `eventos.jsonl`. Junte esses arquivos
(via compartilhamento, SIEM ou cópia) e gere um inventário único, **agrupado
por equipamento** — múltiplos agentes de um mesmo host aparecem juntos, com
**agente/modelo, IP e nome da máquina**:

```bash
# Tabela no terminal:
cerberus relatorio /var/log/cerberus/eventos.jsonl

# Varios hosts de uma vez, em HTML (para apresentar) ou CSV (para planilha):
cerberus relatorio coletados/*.jsonl --formato html --saida relatorio.html
cerberus relatorio coletados/*.jsonl --formato csv  --saida relatorio.csv
```

Colunas: `host`, `ip`, `agente_modelo`, `tipo`, `acao`, `ocorrencias`,
`usuarios`, `qtd_agentes_na_maquina`. O HTML destaca as máquinas com mais de
um agente.

### 3. Personalização por política

Estenda as assinaturas sem alterar o código, via JSON (veja
`config/assinaturas.exemplo.json`):

```bash
cerberus --config /etc/cerberus/assinaturas.json sentinel --bloquear
```

Chaves `adicionar_*` somam às listas padrão; `substituir_*` trocam a lista
inteira. É possível adicionar binários, domínios, portas e liberar usuários
autorizados.

## Instalação automática (rodar localmente em uma máquina)

A aplicação roda localmente em cada estação. Há instaladores que fazem tudo
— instalar o pacote, criar o serviço e iniciá-lo (em **modo auditoria** por
padrão):

**Linux (systemd):**
```bash
sudo ./deploy/instalar-linux.sh                # auditoria (recomendado)
sudo ./deploy/instalar-linux.sh --bloquear     # já encerra os processos
sudo ./deploy/instalar-linux.sh --desinstalar  # remove o serviço
```

**Windows (PowerShell como Administrador):**
```powershell
.\deploy\instalar-windows.ps1                 # auditoria (recomendado)
.\deploy\instalar-windows.ps1 -Bloquear       # já encerra os processos
.\deploy\instalar-windows.ps1 -Desinstalar    # remove a tarefa
```

O instalador Windows usa o **Agendador de Tarefas** nativo (inicia no boot
como `SYSTEM`, sem dependências externas). Ambos criam
`eventos.jsonl` e `sentinel.log` em `/var/log/cerberus` (Linux) ou
`C:\ProgramData\cerberus` (Windows), e copiam um `assinaturas.json` inicial.

Para distribuir em muitas máquinas de uma vez, chame o mesmo instalador via
GPO/Intune (Windows) ou Ansible/Puppet/SSH (Linux).

### Rodando em container (Docker)

> ⚠️ Por padrão, um container só enxerga **os próprios processos**, não os da
> máquina hospedeira. Para o `sentinel` vigiar o host, suba com `pid: host` e
> `network_mode: host` (já configurados em `deploy/docker-compose.yml`):

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

O `rede` (varredura) funciona em qualquer container, pois atua pela rede — só
precisa de rota até os alvos (use `network_mode: host` ou a rede do Docker com
acesso à LAN).

## Testes

```bash
pip install -e ".[dev]"
pytest -q
```

A suíte usa processos simulados (sem depender de agentes reais rodando) e
cobre as regras de detecção, isenções, auditoria vs. bloqueio e os
geradores de DNS/firewall.

## Limitações e boas práticas

- O sentinel detecta agentes **conhecidos**; mantenha as assinaturas
  atualizadas. Combine sempre com o bloqueio de perímetro — uma camada cobre
  as lacunas da outra.
- Rode em **auditoria** por um período antes de ativar o bloqueio, para
  medir o impacto e refinar as isenções.
- O encerramento automático pode interromper trabalho do usuário; garanta
  que a política interna respalde a medida e que haja um canal de exceção
  para casos homologados.
```
