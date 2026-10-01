# agenteEsp

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
| **Perímetro** | `sinkhole` / `firewall` | Gera listas de bloqueio de DNS (Pi-hole, BIND RPZ, dnsmasq, hosts) e regras de firewall (iptables, Windows) para barrar a comunicação dos agentes com provedores de IA e serviços de túnel. |

## Instalação

```bash
pip install .          # instala o pacote e o comando `agenteesp`
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
sudo agenteesp sentinel --eventos /var/log/agenteesp/eventos.jsonl

# Bloqueio efetivo (encerra os processos em violação):
sudo agenteesp sentinel --bloquear --eventos /var/log/agenteesp/eventos.jsonl
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
agenteesp sinkhole --formato pihole --saida /etc/pihole/agenteesp.list

# Zona RPZ para BIND, ou formato dnsmasq/hosts:
agenteesp sinkhole --formato rpz --saida db.agenteesp.rpz

# Regras de firewall:
agenteesp firewall --plataforma iptables --saida bloquear-portas.sh
agenteesp firewall --plataforma windows  --saida bloquear-portas.bat
```

Os arquivos gerados são **configuração para revisão** — nada é aplicado
automaticamente. A equipe de rede valida e aplica nos equipamentos
homologados.

### 3. Personalização por política

Estenda as assinaturas sem alterar o código, via JSON (veja
`config/assinaturas.exemplo.json`):

```bash
agenteesp --config /etc/agenteesp/assinaturas.json sentinel --bloquear
```

Chaves `adicionar_*` somam às listas padrão; `substituir_*` trocam a lista
inteira. É possível adicionar binários, domínios, portas e liberar usuários
autorizados.

## Implantação em larga escala

- **Linux**: copie `deploy/agenteesp-sentinel.service` para
  `/etc/systemd/system/`, ajuste o `ExecStart` e habilite com
  `systemctl enable --now agenteesp-sentinel`. Distribua via Ansible/Puppet.
- **Windows**: `deploy/instalar-windows.ps1` registra o serviço via NSSM;
  distribua por GPO/Intune.

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
