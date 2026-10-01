"""
Assinaturas de agentes proibidos.

Os valores padrao abaixo podem ser sobrescritos/estendidos por um arquivo JSON
(ver config/assinaturas.exemplo.json), sem necessidade de alterar o codigo.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# Executaveis proibidos (comparacao pelo nome do processo, sem extensao .exe)
BINARIOS_PROIBIDOS: Set[str] = {
    # IA local / servidores de LLM
    "ollama", "ollama app", "lmstudio", "lm studio", "lms", "localai",
    "open-webui", "llamafile", "llama-server", "koboldcpp", "gpt4all",
    # Agentes de codigo / assistentes de linha de comando
    "claude", "claude-code", "aider", "goose", "gemini", "cursor-agent",
    # Tuneis reversos e VPNs mesh nao homologadas
    "ngrok", "cloudflared", "frpc", "bore", "localtunnel", "lt",
    "tailscale", "tailscaled", "zerotier-one", "chisel", "rathole",
}

# Frameworks de agentes autonomos procurados na linha de comando de interpretadores
ARGUMENTOS_PROIBIDOS: List[str] = [
    "crewai", "autogpt", "babyagi", "superagi", "smolagents", "metagpt",
    "langgraph", "agent_executor", "open-interpreter", "interpreter --",
    "ollama serve", "open-webui serve", "openhands", "agentgpt",
    # Agentes Claude / Anthropic (SDK e MCP)
    "claude-agent-sdk", "claude_agent_sdk", "claude mcp", "@anthropic-ai",
]

# A regra de linha de comando so vale para estes interpretadores, para nao
# derrubar IDEs, navegadores ou editores que apenas abrem arquivos com esses nomes.
INTERPRETADORES: Set[str] = {
    "python", "python3", "pythonw", "py", "node", "bun", "deno", "uv", "uvx",
    "pipx", "npx", "java",
}

# Gerenciadores de pacotes: instalar/remover nao e executar um agente.
COMANDOS_IGNORADOS: List[str] = [" pip install", " pip uninstall", " -m pip ", "npm install", "npm uninstall"]

# Portas cuja escuta, por si so, caracteriza agente proibido (acao: encerrar)
PORTAS_PROIBIDAS: Dict[int, str] = {
    11434: "Ollama",
    1234: "LM Studio",
    4040: "Ngrok (painel local)",
}

# Portas genericas: apenas registradas como suspeitas, nunca motivo de kill,
# pois sao usadas por inumeras aplicacoes legitimas.
PORTAS_SUSPEITAS: Dict[int, str] = {
    3000: "Open-WebUI / servidores Node",
    8000: "APIs de agentes (FastAPI/LangServe)",
    8080: "LocalAI / servidores genericos",
}

# Processos que nunca devem ser encerrados
PROCESSOS_ISENTOS: Set[str] = {
    "system", "system idle process", "init", "systemd", "svchost", "explorer",
    "sshd", "lsass", "csrss", "wininit", "winlogon", "services", "smss",
}

# Dominios para bloqueio via DNS (sinkhole)
DOMINIOS_IA: List[str] = [
    "api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com",
    "api.cohere.ai", "api.cohere.com", "api.mistral.ai", "api.groq.com",
    "api.together.xyz", "api.deepseek.com", "openrouter.ai", "api.perplexity.ai",
    "huggingface.co", "ollama.com", "registry.ollama.ai",
]
DOMINIOS_TUNEL: List[str] = [
    "ngrok.io", "ngrok-free.app", "ngrok.app", "ngrok.com", "trycloudflare.com",
    "loca.lt", "localtunnel.me", "bore.pub", "serveo.net", "localhost.run",
    "pinggy.io", "tailscale.com", "login.tailscale.com", "controlplane.tailscale.com",
    "zerotier.com", "my.zerotier.com",
]


@dataclass
class Assinaturas:
    binarios: Set[str] = field(default_factory=lambda: set(BINARIOS_PROIBIDOS))
    argumentos: List[str] = field(default_factory=lambda: list(ARGUMENTOS_PROIBIDOS))
    interpretadores: Set[str] = field(default_factory=lambda: set(INTERPRETADORES))
    comandos_ignorados: List[str] = field(default_factory=lambda: list(COMANDOS_IGNORADOS))
    portas_proibidas: Dict[int, str] = field(default_factory=lambda: dict(PORTAS_PROIBIDAS))
    portas_suspeitas: Dict[int, str] = field(default_factory=lambda: dict(PORTAS_SUSPEITAS))
    isentos: Set[str] = field(default_factory=lambda: set(PROCESSOS_ISENTOS))
    dominios_ia: List[str] = field(default_factory=lambda: list(DOMINIOS_IA))
    dominios_tunel: List[str] = field(default_factory=lambda: list(DOMINIOS_TUNEL))
    # Usuarios/hosts com excecao aprovada (ex.: equipe de P&D homologada)
    usuarios_autorizados: Set[str] = field(default_factory=set)


def _normalizar_nome(nome: str) -> str:
    nome = nome.strip().lower()
    return nome[:-4] if nome.endswith(".exe") else nome


def carregar(caminho: Optional[str] = None) -> Assinaturas:
    """
    Carrega as assinaturas padrao e aplica o arquivo JSON opcional.

    Chaves "adicionar_*" estendem as listas padrao; chaves "substituir_*"
    trocam a lista inteira. Ex.: {"adicionar_binarios": ["meuagente"]}.
    """
    a = Assinaturas()
    if not caminho:
        return a

    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    for chave in ("binarios", "argumentos", "interpretadores", "comandos_ignorados",
                  "isentos", "dominios_ia", "dominios_tunel", "usuarios_autorizados"):
        atual = getattr(a, chave)
        if f"substituir_{chave}" in dados:
            novo = dados[f"substituir_{chave}"]
            setattr(a, chave, type(atual)(novo))
            atual = getattr(a, chave)
        for item in dados.get(f"adicionar_{chave}", []):
            if isinstance(atual, set):
                atual.add(item)
            elif item not in atual:
                atual.append(item)

    for chave in ("portas_proibidas", "portas_suspeitas"):
        atual = getattr(a, chave)
        if f"substituir_{chave}" in dados:
            atual.clear()
            atual.update({int(p): d for p, d in dados[f"substituir_{chave}"].items()})
        atual.update({int(p): d for p, d in dados.get(f"adicionar_{chave}", {}).items()})

    a.binarios = {_normalizar_nome(b) for b in a.binarios}
    a.isentos = {_normalizar_nome(b) for b in a.isentos}
    a.interpretadores = {_normalizar_nome(b) for b in a.interpretadores}
    a.argumentos = [t.lower() for t in a.argumentos]
    a.usuarios_autorizados = {u.lower() for u in a.usuarios_autorizados}
    return a
