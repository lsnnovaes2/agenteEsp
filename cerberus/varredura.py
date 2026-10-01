"""
Varredura de rede: a partir de um ponto (servidor da TI/Seguranca), verifica
as faixas de IP da propria empresa procurando servicos de agentes de IA e
tuneis expostos, sem precisar de agente instalado em cada maquina.

Para cada host, testa as portas caracteristicas e confirma por uma requisicao
HTTP no endpoint de identificacao do servico. Resolve o nome da maquina por DNS
reverso. A saida sao eventos no mesmo formato do sentinel, de modo que o modulo
de relatorio consolida tudo por equipamento.

USO AUTORIZADO: execute somente em faixas de IP que a sua organizacao
administra e tem o direito de auditar.
"""

import ipaddress
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

log = logging.getLogger("cerberus.varredura")


@dataclass(frozen=True)
class Sonda:
    servico: str                 # rotulo de agente/modelo (ex.: "ollama")
    caminho: str                 # endpoint HTTP de identificacao
    palavras: Tuple[str, ...]    # ao menos uma deve aparecer na resposta
    critico: bool = True         # False = porta generica (so confirma com assinatura)


# Mapa porta -> sonda(s). Alinhado ao catalogo de assinaturas do Cerberus.
SONDAS: Dict[int, Sonda] = {
    11434: Sonda("ollama", "/api/tags", ("models", "ollama")),
    1234:  Sonda("lmstudio", "/v1/models", ("data", "object")),
    4040:  Sonda("ngrok", "/api/tunnels", ("tunnels", "public_url")),
    3000:  Sonda("open-webui", "/api/config", ("name", "version"), critico=False),
    8000:  Sonda("api-agente", "/openapi.json", ("openapi", "paths"), critico=False),
    8080:  Sonda("localai", "/v1/models", ("models", "object", "data"), critico=False),
}

TIMEOUT_TCP = 1.0
TIMEOUT_HTTP = 2.0


@dataclass
class DeteccaoRede:
    ip: str
    host: str
    porta: int
    agente: str
    confirmado: bool        # True = assinatura HTTP bateu; False = so a porta abriu
    amostra: str = ""
    segmento: str = ""      # nome da VLAN/segmento de onde veio a deteccao

    def como_evento(self) -> dict:
        """Converte para o formato de evento consumido por cerberus.relatorio."""
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "host": self.host,
            "ip": self.ip,
            "segmento": self.segmento,
            "acao": "detectado-rede" if self.confirmado else "porta-aberta",
            "pid": None,
            "nome": self.agente,
            "usuario": "",
            "regra": "porta" if self.porta in (11434, 1234, 4040) else "porta_suspeita",
            "agente": self.agente,
            "motivo": f"Porta {self.porta} exposta na rede"
                      + (" (assinatura confirmada)" if self.confirmado else " (sem confirmacao)"),
            "porta": self.porta,
        }


def _porta_aberta(ip: str, porta: int, timeout: float = TIMEOUT_TCP) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex((ip, porta)) == 0
        except OSError:
            return False


def _nome_host(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return ip  # sem DNS reverso: usa o proprio IP como identificador


def _confirmar_http(ip: str, porta: int, sonda: Sonda) -> Tuple[bool, str]:
    url = f"http://{ip}:{porta}{sonda.caminho}"
    req = urllib.request.Request(url, headers={"User-Agent": "Cerberus/compliance-scan"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as resp:
            corpo = resp.read(2048).decode("utf-8", errors="ignore").lower()
        if any(p in corpo for p in sonda.palavras):
            return True, corpo[:120].strip()
        return False, "porta aberta, resposta nao bateu com a assinatura"
    except urllib.error.HTTPError as e:
        # 401/403/404 ainda indicam servidor ativo
        return False, f"HTTP {e.code} (servico ativo)"
    except Exception:
        return False, "sem resposta HTTP (protocolo diferente?)"


def varrer_host(ip: str, portas: Optional[Iterable[int]] = None) -> List[DeteccaoRede]:
    """Audita um unico host contra as sondas selecionadas."""
    portas = list(portas) if portas is not None else list(SONDAS)
    achados: List[DeteccaoRede] = []
    host = None
    for porta in portas:
        sonda = SONDAS.get(porta)
        if not sonda or not _porta_aberta(ip, porta):
            continue
        confirmado, amostra = _confirmar_http(ip, porta, sonda)
        # Em porta generica (nao critica), so reporta se a assinatura confirmar,
        # para nao marcar qualquer servidor web legitimo na 8080/8000/3000.
        if not sonda.critico and not confirmado:
            continue
        if host is None:
            host = _nome_host(ip)
        achados.append(DeteccaoRede(ip=ip, host=host, porta=porta,
                                    agente=sonda.servico, confirmado=confirmado,
                                    amostra=amostra))
    return achados


def expandir_alvos(alvos: Iterable[str]) -> List[str]:
    """Expande CIDRs e IPs soltos em uma lista de enderecos."""
    ips: List[str] = []
    for alvo in alvos:
        alvo = alvo.strip()
        if not alvo:
            continue
        try:
            rede = ipaddress.ip_network(alvo, strict=False)
            ips.extend(str(ip) for ip in (rede.hosts() if rede.num_addresses > 2 else rede))
        except ValueError:
            ips.append(alvo)  # hostname ou IP isolado
    return ips


def varrer_rede(alvos: Iterable[str], portas: Optional[Iterable[int]] = None,
                threads: int = 100,
                progresso=None) -> List[DeteccaoRede]:
    """
    Varre varios hosts em paralelo. `alvos` aceita CIDRs e IPs.
    `progresso` (opcional) e chamado como progresso(feitos, total).
    """
    ips = expandir_alvos(alvos)
    total = len(ips)
    achados: List[DeteccaoRede] = []
    feitos = 0
    with ThreadPoolExecutor(max_workers=min(threads, max(total, 1))) as ex:
        futuros = {ex.submit(varrer_host, ip, portas): ip for ip in ips}
        for fut in as_completed(futuros):
            feitos += 1
            try:
                achados.extend(fut.result())
            except Exception as e:  # um host com erro nao derruba a varredura
                log.debug("Erro ao varrer %s: %s", futuros[fut], e)
            if progresso:
                progresso(feitos, total)
    return achados


def eventos_de(achados: Iterable[DeteccaoRede]) -> List[dict]:
    return [a.como_evento() for a in achados]


def carregar_segmentos(caminho: str) -> List[Tuple[str, str]]:
    """
    Le um arquivo JSON descrevendo os segmentos/VLANs da empresa e retorna
    uma lista de (nome_segmento, cidr).

    Formato aceito:
      {"segmentos": [
          {"nome": "VLAN10-RH",       "cidr": "10.10.0.0/24"},
          {"nome": "VLAN20-Financeiro","cidr": "10.20.0.0/24"},
          {"nome": "VLAN30-Fabrica",  "cidr": "10.30.0.0/22"}
      ]}
    Tambem aceita uma lista simples de CIDRs: ["10.10.0.0/24", "10.20.0.0/24"].
    """
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if isinstance(dados, dict):
        dados = dados.get("segmentos", [])
    segmentos: List[Tuple[str, str]] = []
    for item in dados:
        if isinstance(item, str):
            segmentos.append((item, item))
        else:
            cidr = item.get("cidr") or item.get("rede") or ""
            nome = item.get("nome") or cidr
            if cidr:
                segmentos.append((nome, cidr))
    return segmentos


def varrer_segmentos(segmentos: Iterable[Tuple[str, str]],
                     portas: Optional[Iterable[int]] = None,
                     threads: int = 100,
                     progresso=None,
                     por_segmento=None) -> List[DeteccaoRede]:
    """
    Varre varios segmentos/VLANs em sequencia, rotulando cada deteccao com o
    nome do segmento. `por_segmento(nome, achados)` (opcional) e chamado ao fim
    de cada VLAN. Uma VLAN inalcancavel (sem rota) apenas nao retorna hosts.
    """
    todos: List[DeteccaoRede] = []
    for nome, cidr in segmentos:
        achados = varrer_rede([cidr], portas=portas, threads=threads, progresso=progresso)
        for a in achados:
            a.segmento = nome
        if por_segmento:
            por_segmento(nome, achados)
        todos.extend(achados)
    return todos
