#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a documentacao tecnica do Cerberus em PDF (docs/Cerberus-Documentacao-Tecnica.pdf).

Uso:
    pip install reportlab
    python3 docs/gerar_documentacao.py
"""

from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

# ----------------------------------------------------------------------- cores
VERDE = colors.HexColor("#1f6f5c")
VERDE_CLARO = colors.HexColor("#e6f0ec")
CINZA = colors.HexColor("#5b6676")
CINZA_LINHA = colors.HexColor("#d9dee6")
TINTA = colors.HexColor("#1a2230")
VERMELHO = colors.HexColor("#a4322c")
CODE_BG = colors.HexColor("#0f1722")
CODE_FG = colors.HexColor("#d6e2ef")

ARQUIVO = "docs/Cerberus-Documentacao-Tecnica.pdf"
VERSAO = "1.0.0"

# ---------------------------------------------------------------------- estilos
ss = getSampleStyleSheet()


def _estilo(nome, **kw):
    return ParagraphStyle(nome, parent=ss["Normal"], **kw)


S_TITULO = _estilo("TituloCapa", fontName="Helvetica-Bold", fontSize=30,
                   textColor=VERDE, leading=36, alignment=TA_LEFT)
S_SUBTITULO = _estilo("SubCapa", fontName="Helvetica", fontSize=14,
                      textColor=CINZA, leading=20)
S_H1 = _estilo("H1", fontName="Helvetica-Bold", fontSize=17, textColor=VERDE,
               leading=22, spaceBefore=18, spaceAfter=8)
S_H2 = _estilo("H2", fontName="Helvetica-Bold", fontSize=13, textColor=TINTA,
               leading=17, spaceBefore=12, spaceAfter=5)
S_BODY = _estilo("Body", fontSize=10.5, textColor=TINTA, leading=15.5,
                 alignment=TA_JUSTIFY, spaceAfter=7)
S_BULLET = _estilo("Bullet", fontSize=10.5, textColor=TINTA, leading=15,
                   leftIndent=14, bulletIndent=2, spaceAfter=3)
S_CODE = _estilo("Code", fontName="Courier", fontSize=8.8, textColor=CODE_FG,
                 leading=12, leftIndent=6, rightIndent=6, spaceBefore=2,
                 spaceAfter=2)
S_CELL = _estilo("Cell", fontSize=9, textColor=TINTA, leading=12.5)
S_CELLH = _estilo("CellH", fontName="Helvetica-Bold", fontSize=9,
                  textColor=colors.white, leading=12.5)
S_TOC = _estilo("Toc", fontSize=11, textColor=TINTA, leading=20)
S_NOTA = _estilo("Nota", fontSize=9.5, textColor=CINZA, leading=13,
                 alignment=TA_JUSTIFY)

story = []


# ------------------------------------------------------------------- utilitarios
def h1(txt):
    story.append(Paragraph(txt, S_H1))


def h2(txt):
    story.append(Paragraph(txt, S_H2))


def p(txt):
    story.append(Paragraph(txt, S_BODY))


def bullets(itens):
    for it in itens:
        story.append(Paragraph(it, S_BULLET, bulletText="•"))
    story.append(Spacer(1, 5))


def code(linhas):
    txt = "<br/>".join(l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                       for l in linhas)
    bloco = Table([[Paragraph(txt, S_CODE)]], colWidths=[16.4 * cm])
    bloco.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(bloco)
    story.append(Spacer(1, 8))


def tabela(cabecalho, linhas, larguras):
    dados = [[Paragraph(c, S_CELLH) for c in cabecalho]]
    for ln in linhas:
        dados.append([Paragraph(str(c), S_CELL) for c in ln])
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(estilo))
    story.append(t)
    story.append(Spacer(1, 10))


def nota(txt):
    cx = Table([[Paragraph(txt, S_NOTA)]], colWidths=[16.4 * cm])
    cx.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), VERDE_CLARO),
        ("LINEBEFORE", (0, 0), (0, -1), 3, VERDE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cx)
    story.append(Spacer(1, 10))


# ============================================================== CAPA
story.append(Spacer(1, 4.5 * cm))
story.append(Paragraph("Cerberus", S_TITULO))
story.append(Spacer(1, 4))
story.append(Paragraph("Detecção e Bloqueio de Agentes de IA Não Autorizados", S_SUBTITULO))
story.append(Spacer(1, 2))
story.append(Paragraph("na Rede Corporativa", S_SUBTITULO))
story.append(Spacer(1, 1.2 * cm))
linha = Table([[""]], colWidths=[16.4 * cm], rowHeights=[2])
linha.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), VERDE)]))
story.append(linha)
story.append(Spacer(1, 0.5 * cm))
story.append(Paragraph("Documentação Técnica", _estilo("dt", fontName="Helvetica-Bold",
             fontSize=13, textColor=TINTA)))
story.append(Spacer(1, 6 * cm))
story.append(Paragraph(f"Versão {VERSAO} &nbsp;·&nbsp; {date.today().strftime('%d/%m/%Y')}",
             _estilo("vc", fontSize=10, textColor=CINZA)))
story.append(Paragraph("Classificação: Uso interno — Segurança da Informação",
             _estilo("cc", fontSize=10, textColor=CINZA)))
story.append(PageBreak())

# ============================================================== SUMARIO
story.append(Paragraph("Sumário", S_H1))
story.append(Spacer(1, 4))
sumario = [
    "1. Visão geral e objetivo",
    "2. Arquitetura da solução",
    "3. Componentes",
    "4. Motor de detecção e assinaturas",
    "5. Varredura de rede e redes segmentadas (VLANs)",
    "6. Relatório consolidado",
    "7. Instalação e implantação",
    "8. Execução em container",
    "9. Configuração",
    "10. Operação, segurança e conformidade",
    "11. Referência de comandos (CLI)",
    "12. Testes e qualidade",
]
for item in sumario:
    story.append(Paragraph(item, S_TOC))
story.append(PageBreak())

# ============================================================== 1
h1("1. Visão geral e objetivo")
p("O <b>Cerberus</b> é uma ferramenta de conformidade corporativa cujo objetivo "
  "é <b>detectar e bloquear o uso de agentes de IA e túneis de rede não "
  "autorizados</b> nas estações de trabalho e na rede interna, em aderência à "
  "política de segurança da organização. São considerados alvos: servidores de "
  "LLM locais (Ollama, LM Studio, LocalAI), frameworks de agentes autônomos "
  "(CrewAI, AutoGPT, LangGraph), assistentes de código por linha de comando "
  "(Claude, Gemini, Aider) e serviços de tunelamento reverso (ngrok, cloudflared, "
  "frp, Tailscale).")
p("A solução adota uma abordagem em <b>camadas complementares</b>, por ser mais "
  "robusta do que qualquer medida isolada: um agente de endpoint que inspeciona "
  "processos, uma varredura ativa da rede, geradores de bloqueio de perímetro "
  "(DNS e firewall) e um relatório consolidado por equipamento.")
nota("<b>Uso autorizado apenas.</b> O Cerberus deve ser implantado somente em "
     "equipamentos e redes que a organização administra e tem o direito de "
     "auditar. A operação precisa ser aprovada pela área de Segurança/TI e "
     "comunicada aos usuários conforme a política interna. O produto inicia "
     "sempre em <b>modo auditoria</b> (apenas registra); o encerramento de "
     "processos é uma ação explícita (opt-in).")

# ============================================================== 2
h1("2. Arquitetura da solução")
p("O Cerberus é um pacote Python único (comando <font face='Courier'>cerberus</font>) "
  "que expõe seis subcomandos. Dois mecanismos de detecção coexistem e se "
  "complementam:")
bullets([
    "<b>Sentinel (endpoint):</b> um processo por máquina que inspeciona a árvore "
    "de processos local. Independe de topologia de rede e enxerga até agentes "
    "que não expõem porta.",
    "<b>Varredura (rede):</b> executada de um ponto central, conecta-se às portas "
    "características dos hosts-alvo e confirma o serviço por assinatura HTTP. "
    "Cobre a rede sem instalação nas estações, mas só vê agentes com porta aberta.",
])
p("Ambos produzem <b>eventos</b> no mesmo formato (linhas JSON), que o módulo de "
  "relatório consolida por equipamento. O bloqueio de perímetro é gerado como "
  "artefato de configuração (listas de DNS e regras de firewall) para a equipe "
  "de rede aplicar nos equipamentos homologados.")

h2("Fluxo de dados")
code([
    "  [ Estações ]                         [ Rede interna ]",
    "   sentinel  --\\                     cerberus rede --\\",
    "               \\                                      \\",
    "                >--> eventos.jsonl <-------------------/",
    "                             |",
    "                             v",
    "                   cerberus relatorio",
    "                             |",
    "            +----------------+----------------+",
    "            v                v                v",
    "         texto            CSV/JSON           HTML",
])

h2("Camadas de controle")
tabela(
    ["Camada", "Componente", "Função principal"],
    [
        ["Endpoint", "sentinel", "Audita/encerra processos de agentes na máquina local."],
        ["Rede", "rede / painel", "Localiza agentes expostos em faixas de IP."],
        ["Perímetro", "sinkhole / firewall", "Gera bloqueio de DNS e de portas."],
        ["Consolidação", "relatorio", "Inventário por equipamento (agente, IP, máquina, VLAN)."],
    ],
    [2.3 * cm, 3.2 * cm, 10.9 * cm],
)

# ============================================================== 3
h1("3. Componentes")
h2("3.1 Sentinel (cerberus sentinel)")
p("Serviço de monitoramento contínuo baseado na biblioteca <font face='Courier'>"
  "psutil</font>. A cada ciclo, percorre os processos do sistema e aplica as "
  "regras de detecção. Em modo auditoria apenas registra evidências; em modo "
  "bloqueio encerra o processo e seus filhos (SIGTERM e, se necessário, SIGKILL). "
  "Requer privilégios de root/administrador para enxergar e encerrar processos "
  "de outros usuários.")

h2("3.2 Varredura de rede (cerberus rede)")
p("Varre faixas CIDR/IP usando um pool de threads. Para cada host, testa as "
  "portas-alvo via conexão TCP e, quando abertas, confirma o serviço com uma "
  "requisição HTTP ao endpoint de identificação (por exemplo "
  "<font face='Courier'>/api/tags</font> do Ollama). Resolve o nome da máquina "
  "por DNS reverso. Usa apenas a biblioteca padrão do Python.")

h2("3.3 Painel desktop (cerberus painel)")
p("Interface gráfica (Tkinter) sobre o motor de varredura. Permite informar as "
  "faixas, escolher os serviços, acompanhar o progresso e exportar o resultado "
  "em HTML/CSV. Pode ser empacotado como executável standalone (PyInstaller) "
  "para distribuição sem Python.")

h2("3.4 Bloqueio de perímetro (cerberus sinkhole / firewall)")
p("Geradores de configuração. O <font face='Courier'>sinkhole</font> produz "
  "listas de bloqueio de DNS nos formatos Pi-hole, hosts, dnsmasq e BIND RPZ. "
  "O <font face='Courier'>firewall</font> gera regras iptables (Linux) ou netsh "
  "(Windows). Nenhum aplica mudanças automaticamente — são artefatos para revisão.")

h2("3.5 Relatório (cerberus relatorio)")
p("Consolida um ou mais arquivos de eventos, agrupando por equipamento e "
  "juntando múltiplos agentes de um mesmo host. Exporta em texto, JSON, CSV e HTML.")

# ============================================================== 4
h1("4. Motor de detecção e assinaturas")
p("As regras foram desenhadas para <b>minimizar falsos positivos</b>, que num "
  "ambiente de produção poderiam interromper trabalho legítimo:")
tabela(
    ["Regra", "Critério", "Ação"],
    [
        ["Binário proibido", "Nome do processo <b>ou</b> caminho real do executável "
         "(detecta agentes renomeados).", "Encerrar"],
        ["Framework em interpretador", "Termo na linha de comando, apenas quando o "
         "processo é python/node/java. Comandos de instalação (pip/npm) são ignorados.",
         "Encerrar"],
        ["Porta característica", "Escuta em 11434 (Ollama), 1234 (LM Studio), "
         "4040 (ngrok).", "Encerrar"],
        ["Porta genérica", "Escuta em 3000/8000/8080 (usadas por apps legítimos).",
         "Apenas alertar"],
        ["Isenção", "Processos de SO e usuários homologados.", "Ignorar"],
    ],
    [3.4 * cm, 10 * cm, 3 * cm],
)
p("As assinaturas padrão cobrem servidores de LLM, frameworks de agentes, "
  "assistentes CLI (incluindo Claude/Anthropic e Gemini) e túneis. Podem ser "
  "estendidas ou substituídas por um arquivo JSON de política, sem alterar o código.")

# ============================================================== 5
h1("5. Varredura de rede e redes segmentadas (VLANs)")
p("Em redes com muitas VLANs, um scanner único não alcança os demais segmentos, "
  "pois o roteamento/firewall entre sub-redes normalmente bloqueia. O Cerberus "
  "oferece duas estratégias, idealmente combinadas:")
bullets([
    "<b>Sentinel por máquina (independe de VLAN):</b> cada estação se reporta "
    "sozinha; é a cobertura mais completa. Distribuído por GPO/Intune (Windows) "
    "ou Ansible/SSH (Linux).",
    "<b>Varredura por segmento:</b> um arquivo lista as VLANs; cada detecção é "
    "rotulada com o segmento. Quando não há rota até todas as VLANs, roda-se uma "
    "instância por segmento, e os eventos são consolidados num único relatório.",
])
nota("A varredura faz apenas <b>conexões de saída</b> e não exige abrir porta na "
     "máquina que a executa, nem no firewall de host. Em VLANs segmentadas, o "
     "firewall entre as sub-redes precisa permitir a saída do host de varredura "
     "para as portas dos alvos — ou utiliza-se uma instância por segmento.")

# ============================================================== 6
h1("6. Relatório consolidado")
p("O relatório agrupa as detecções por equipamento (identificado por host e IP) "
  "e lista todos os agentes distintos encontrados em cada um, com a VLAN quando "
  "disponível. Máquinas com múltiplos agentes são destacadas. Colunas:")
bullets([
    "<b>segmento</b> (VLAN) · <b>host</b> · <b>IP</b> · <b>agente/modelo</b>",
    "<b>tipo</b> · <b>ação</b> (auditado/encerrado/detectado-rede) · "
    "<b>ocorrências</b> · <b>usuários</b> · <b>qtd. de agentes na máquina</b>",
])
p("Formatos de saída: <b>texto</b> (terminal), <b>JSON</b> (integração/SIEM), "
  "<b>CSV</b> (planilha) e <b>HTML</b> (apresentação). O HTML destaca "
  "visualmente os equipamentos com mais de um agente.")

# ============================================================== 7
h1("7. Instalação e implantação")
h2("7.1 Linux (systemd)")
code([
    "sudo ./deploy/instalar-linux.sh                 # auditoria (recomendado)",
    "sudo ./deploy/instalar-linux.sh --bloquear      # encerra os processos",
    "sudo ./deploy/instalar-linux.sh --rede          # agenda a varredura (timer)",
    "sudo ./deploy/instalar-linux.sh --desinstalar   # remove servicos e timers",
])
p("Cria o serviço <font face='Courier'>cerberus-sentinel</font>, os diretórios "
  "<font face='Courier'>/etc/cerberus</font> e <font face='Courier'>/var/log/"
  "cerberus</font>, e (com <font face='Courier'>--rede</font>) um "
  "<font face='Courier'>service</font> oneshot e um <font face='Courier'>timer</font> "
  "que executam a varredura periodicamente, gravando um JSONL com data/hora.")

h2("7.2 Windows (Agendador de Tarefas)")
code([
    ".\\deploy\\instalar-windows.ps1                  # auditoria (recomendado)",
    ".\\deploy\\instalar-windows.ps1 -Bloquear        # encerra os processos",
    ".\\deploy\\instalar-windows.ps1 -Desinstalar     # remove a tarefa",
])
p("Registra a tarefa <font face='Courier'>Cerberus-Sentinel</font> (inicia no "
  "boot como SYSTEM, sem dependências externas) e cria os dados em "
  "<font face='Courier'>C:\\ProgramData\\cerberus</font>.")

h2("7.3 Painel como executável standalone")
code([
    "./packaging/build-linux.sh        # Linux  -> dist/cerberus-painel",
    ".\\packaging\\build-windows.ps1     # Windows -> dist\\cerberus-painel.exe",
])

# ============================================================== 8
h1("8. Execução em container")
p("Por padrão, um container enxerga apenas os próprios processos (namespace de "
  "PID isolado). Para o sentinel vigiar a máquina hospedeira, o compose fornecido "
  "usa <font face='Courier'>pid: host</font> e <font face='Courier'>network_mode: "
  "host</font>:")
code([
    "docker compose -f deploy/docker-compose.yml up -d --build",
])
p("A varredura de rede funciona em qualquer container, desde que haja rota de "
  "rede até os alvos.")

# ============================================================== 9
h1("9. Configuração")
p("As assinaturas são estendidas por um JSON de política aplicado com "
  "<font face='Courier'>--config</font>. Chaves <font face='Courier'>adicionar_*"
  "</font> somam às listas padrão; <font face='Courier'>substituir_*</font> "
  "trocam a lista inteira.")
code([
    "{",
    '  "adicionar_binarios": ["meuagente-interno"],',
    '  "adicionar_portas_proibidas": { "9100": "Agente proprietario" },',
    '  "adicionar_usuarios_autorizados": ["pesquisa"]',
    "}",
])
p("Para as VLANs, o arquivo de segmentos (ver <font face='Courier'>config/"
  "redes.exemplo.json</font>) lista nome e CIDR de cada rede. O painel web auxilia "
  "a montar o arquivo de assinaturas marcando os agentes desejados.")

# ============================================================== 10
h1("10. Operação, segurança e conformidade")
bullets([
    "<b>Inicie em auditoria.</b> Rode por um período registrando antes de ativar "
    "o bloqueio, para medir impacto e refinar isenções.",
    "<b>Privilégios.</b> O sentinel precisa de root/SYSTEM para encerrar processos "
    "de outros usuários; sem isso, apenas audita o que consegue ler.",
    "<b>Evidências.</b> Cada evento (host, IP, usuário, regra, comando) é uma linha "
    "JSON, pronta para encaminhamento a um SIEM.",
    "<b>Exceções.</b> Usuários/equipes homologados (ex.: laboratório de P&D) podem "
    "ser isentos por configuração.",
    "<b>Limitações.</b> O sentinel detecta agentes conhecidos — mantenha as "
    "assinaturas atualizadas e combine com o bloqueio de perímetro.",
])
nota("<b>Aviso legal.</b> O encerramento automático de processos pode interromper "
     "o trabalho do usuário. Garanta respaldo na política interna e um canal de "
     "exceção para casos homologados. Toda varredura de rede deve ser previamente "
     "autorizada.")

# ============================================================== 11
h1("11. Referência de comandos (CLI)")
tabela(
    ["Comando", "Descrição"],
    [
        ["cerberus sentinel [--bloquear]", "Monitora e (opcionalmente) encerra processos locais."],
        ["cerberus rede &lt;cidr…&gt; [--arquivo]", "Varre faixas de IP; aceita arquivo de segmentos."],
        ["cerberus painel", "Abre o painel desktop de varredura."],
        ["cerberus sinkhole --formato", "Gera lista de bloqueio de DNS."],
        ["cerberus firewall --plataforma", "Gera regras de firewall."],
        ["cerberus relatorio &lt;jsonl…&gt;", "Consolida os eventos por equipamento."],
    ],
    [6.2 * cm, 10.2 * cm],
)
p("Todos aceitam <font face='Courier'>--config</font> (assinaturas) e "
  "<font face='Courier'>--help</font>. Saídas de relatório/bloqueio aceitam "
  "<font face='Courier'>--saida</font>.")

# ============================================================== 12
h1("12. Testes e qualidade")
p("O projeto acompanha uma suíte de testes automatizados (pytest) que cobre as "
  "regras de detecção, isenções, auditoria vs. bloqueio, os geradores de DNS e "
  "firewall, a consolidação do relatório, a varredura de rede (com servidor HTTP "
  "simulado) e o suporte a segmentos/VLANs. A integração contínua (GitHub Actions) "
  "executa a suíte nas versões de Python 3.9 a 3.12.")
code([
    "pip install -e \".[dev]\"",
    "pytest -q",
])
p("A documentação complementar está no repositório: "
  "<font face='Courier'>README.md</font> (guia rápido) e "
  "<font face='Courier'>docs/MANUAL.md</font> (manual de instalação e uso).")


# ------------------------------------------------------- cabecalho / rodape
def _rodape(canvas, doc):
    canvas.saveState()
    largura, _ = A4
    # rodape
    canvas.setStrokeColor(CINZA_LINHA)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.4 * cm, largura - 2 * cm, 1.4 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.0 * cm, f"Cerberus · Documentação Técnica · v{VERSAO}")
    canvas.drawRightString(largura - 2 * cm, 1.0 * cm, f"Página {doc.page}")
    canvas.drawCentredString(largura / 2, 1.0 * cm, "Uso interno")
    canvas.restoreState()


def _capa(canvas, doc):
    canvas.saveState()
    largura, altura = A4
    canvas.setFillColor(VERDE)
    canvas.rect(0, altura - 1.2 * cm, largura, 1.2 * cm, fill=1, stroke=0)
    canvas.restoreState()


frame = Frame(2 * cm, 1.8 * cm, A4[0] - 4 * cm, A4[1] - 3.6 * cm, id="corpo")
doc = BaseDocTemplate(ARQUIVO, pagesize=A4, title="Cerberus - Documentacao Tecnica",
                      author="Seguranca da Informacao", leftMargin=2 * cm,
                      rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm)
doc.addPageTemplates([
    PageTemplate(id="capa", frames=[frame], onPage=_capa),
    PageTemplate(id="miolo", frames=[frame], onPage=_rodape),
])
# a primeira pagina usa 'capa'; a partir da 2a, 'miolo'
story.insert(0, NextPageTemplate("miolo"))

doc.build(story)
print(f"PDF gerado: {ARQUIVO}")
