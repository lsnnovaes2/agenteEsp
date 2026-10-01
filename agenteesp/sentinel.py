"""
Sentinel de endpoint: varre os processos locais, identifica agentes de IA e
tuneis nao autorizados e (em modo bloqueio) os encerra, registrando evidencias.

Requer a biblioteca psutil e privilegios de administrador/root para enxergar
e encerrar processos de outros usuarios.
"""

import json
import logging
import os
import re
import signal
import socket
import time
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Set, Tuple

import psutil

from .assinaturas import Assinaturas

log = logging.getLogger("agenteesp.sentinel")

_SUFIXO_VERSAO = re.compile(r"[\d.]+$")


@dataclass
class Violacao:
    pid: int
    nome: str
    usuario: str
    regra: str          # binario | argumento | porta | porta_suspeita
    motivo: str
    agente: str = ""    # rotulo limpo do agente/modelo (ex.: "ollama", "crewai")
    comando: str = ""
    exe: str = ""
    encerrar: bool = True


def _nome_base(nome: str) -> str:
    nome = nome.lower()
    if nome.endswith(".exe"):
        nome = nome[:-4]
    return nome


def _eh_interpretador(nome: str, interpretadores: Set[str]) -> bool:
    # python3.11 -> python, node18 -> node
    return nome in interpretadores or _SUFIXO_VERSAO.sub("", nome) in interpretadores


def _ip_local() -> str:
    """Descobre o IP principal da maquina (o usado para sair pela rede)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # nao envia pacote; so resolve a interface de saida
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def _conexoes(proc: psutil.Process):
    # psutil >= 6 renomeou connections() para net_connections()
    metodo = getattr(proc, "net_connections", None) or proc.connections
    return metodo(kind="inet")


class SentinelMonitor:
    def __init__(self, assinaturas: Assinaturas, intervalo: float = 3.0,
                 bloquear: bool = False, arquivo_eventos: Optional[str] = None):
        self.a = assinaturas
        self.intervalo = intervalo
        self.bloquear = bloquear
        self.arquivo_eventos = arquivo_eventos
        self.executando = True
        self.hostname = socket.gethostname()
        self.ip = _ip_local()
        # Nunca encerrar o proprio sentinel nem quem o iniciou
        self._protegidos = {os.getpid(), os.getppid()}
        # Evita repetir o mesmo alerta a cada ciclo em modo auditoria
        self._ja_reportados: Set[Tuple[int, str]] = set()

    # ------------------------------------------------------------------ deteccao
    def avaliar(self, proc: psutil.Process) -> Optional[Violacao]:
        """Retorna a violacao encontrada no processo, ou None se estiver conforme."""
        try:
            if proc.pid in self._protegidos or proc.pid == 0:
                return None
            nome = _nome_base(proc.name())
            if nome in self.a.isentos:
                return None
            try:
                usuario = proc.username() or ""
            except (psutil.AccessDenied, KeyError):
                usuario = ""
            if usuario and usuario.lower().split("\\")[-1] in self.a.usuarios_autorizados:
                return None

            try:
                cmd = " ".join(proc.cmdline())
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmd = ""
            try:
                exe = proc.exe() or ""
            except (psutil.AccessDenied, psutil.ZombieProcess, OSError):
                exe = ""

            base = dict(pid=proc.pid, nome=nome, usuario=usuario, comando=cmd, exe=exe)

            # Regra 1: nome do executavel (ou do arquivo em exe, caso renomeado no name)
            exe_nome = _nome_base(os.path.basename(exe)) if exe else ""
            for candidato in (nome, exe_nome):
                if candidato and candidato in self.a.binarios:
                    return Violacao(regra="binario", agente=candidato,
                                    motivo=f"Executavel proibido: {candidato}", **base)

            # Regra 2: frameworks de agentes executados por interpretadores
            if cmd and _eh_interpretador(nome, self.a.interpretadores):
                cmd_l = f" {cmd.lower()} "
                if not any(ign in cmd_l for ign in self.a.comandos_ignorados):
                    for termo in self.a.argumentos:
                        if termo in cmd_l:
                            return Violacao(regra="argumento", agente=termo.strip(),
                                            motivo=f"Framework de agente na linha de comando: '{termo}'",
                                            **base)

            # Regra 3: escuta em portas caracteristicas
            try:
                for c in _conexoes(proc):
                    if c.status != psutil.CONN_LISTEN or not c.laddr:
                        continue
                    porta = c.laddr.port
                    if porta in self.a.portas_proibidas:
                        return Violacao(regra="porta", agente=self.a.portas_proibidas[porta],
                                        motivo=f"Escutando na porta {porta} ({self.a.portas_proibidas[porta]})",
                                        **base)
                    if porta in self.a.portas_suspeitas:
                        return Violacao(regra="porta_suspeita", encerrar=False,
                                        agente=self.a.portas_suspeitas[porta],
                                        motivo=f"Escutando na porta generica {porta} "
                                               f"({self.a.portas_suspeitas[porta]}) - verificar manualmente",
                                        **base)
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        return None

    # -------------------------------------------------------------------- acao
    def _registrar_evento(self, v: Violacao, acao: str) -> None:
        if not self.arquivo_eventos:
            return
        evento = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                  "host": self.hostname, "ip": self.ip, "acao": acao, **asdict(v)}
        try:
            with open(self.arquivo_eventos, "a", encoding="utf-8") as f:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        except OSError as e:
            log.error("Falha ao gravar evento em %s: %s", self.arquivo_eventos, e)

    def tratar(self, proc: psutil.Process, v: Violacao) -> str:
        """Aplica a acao cabivel e retorna o que foi feito."""
        chave = (v.pid, v.motivo)
        if not (self.bloquear and v.encerrar):
            if chave in self._ja_reportados:
                return "ja_reportado"
            self._ja_reportados.add(chave)
            acao = "auditado"
            log.warning("VIOLACAO [%s] PID %d %s (usuario=%s): %s | cmd=%s",
                        v.regra, v.pid, v.nome, v.usuario or "?", v.motivo, v.comando[:200])
            self._registrar_evento(v, acao)
            return acao

        log.warning("VIOLACAO [%s] PID %d %s (usuario=%s): %s - encerrando",
                    v.regra, v.pid, v.nome, v.usuario or "?", v.motivo)
        try:
            # Encerra tambem os filhos (ex.: runners do Ollama, workers do agente)
            filhos = proc.children(recursive=True)
            for p in [proc] + filhos:
                try:
                    p.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, vivos = psutil.wait_procs([proc] + filhos, timeout=3)
            for p in vivos:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
            acao = "encerrado" if not vivos else "encerrado_forcado"
        except psutil.NoSuchProcess:
            acao = "ja_finalizado"
        except psutil.AccessDenied:
            acao = "acesso_negado"
            log.error("Acesso negado ao encerrar PID %d. Execute como Administrador/root.", v.pid)
        self._registrar_evento(v, acao)
        log.info("PID %d (%s): %s", v.pid, v.nome, acao)
        return acao

    # -------------------------------------------------------------------- loop
    def ciclo(self, processos: Optional[Iterable[psutil.Process]] = None) -> List[Tuple[Violacao, str]]:
        resultados = []
        vivos = set()
        for proc in processos if processos is not None else psutil.process_iter():
            vivos.add(proc.pid)
            v = self.avaliar(proc)
            if v:
                resultados.append((v, self.tratar(proc, v)))
        # PIDs sao reutilizados: esquece alertas de processos que ja morreram
        self._ja_reportados = {k for k in self._ja_reportados if k[0] in vivos}
        return resultados

    def _parar(self, signum, _frame):
        log.info("Sinal %s recebido, finalizando.", signum)
        self.executando = False

    def iniciar(self) -> None:
        signal.signal(signal.SIGINT, self._parar)
        signal.signal(signal.SIGTERM, self._parar)
        log.info("Sentinel iniciado em %s | modo=%s | intervalo=%ss",
                 self.hostname, "BLOQUEIO" if self.bloquear else "AUDITORIA", self.intervalo)
        while self.executando:
            try:
                self.ciclo()
            except Exception:  # o servico nunca deve morrer por um erro pontual
                log.exception("Erro inesperado no ciclo de varredura")
            time.sleep(self.intervalo)
        log.info("Sentinel finalizado.")
