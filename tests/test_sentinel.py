"""Testes do motor de deteccao, usando processos falsos (sem psutil real)."""

import psutil
import pytest

from cerberus.assinaturas import carregar
from cerberus.sentinel import SentinelMonitor


class FakeAddr:
    def __init__(self, port):
        self.port = port


class FakeConn:
    def __init__(self, port, status=psutil.CONN_LISTEN):
        self.laddr = FakeAddr(port)
        self.status = status


class FakeProc:
    """Imita a parte da API do psutil.Process que o sentinel usa."""

    def __init__(self, pid, name, cmdline=None, username="joao",
                 exe="", conns=None, children=None):
        self.pid = pid
        self._name = name
        self._cmdline = cmdline or [name]
        self._username = username
        self._exe = exe
        self._conns = conns or []
        self._children = children or []

    def name(self):
        return self._name

    def cmdline(self):
        return self._cmdline

    def username(self):
        return self._username

    def exe(self):
        return self._exe

    def net_connections(self, kind="inet"):
        return self._conns

    def children(self, recursive=False):
        return self._children


@pytest.fixture
def monitor():
    return SentinelMonitor(carregar(), bloquear=False)


def avaliar(monitor, proc):
    return monitor.avaliar(proc)


def test_detecta_binario_ollama(monitor):
    v = avaliar(monitor, FakeProc(100, "ollama", exe="/usr/local/bin/ollama"))
    assert v and v.regra == "binario"
    assert v.encerrar is True


def test_detecta_binario_windows_com_exe(monitor):
    v = avaliar(monitor, FakeProc(101, "ngrok.exe"))
    assert v and v.regra == "binario"


def test_detecta_framework_na_linha_de_comando(monitor):
    v = avaliar(monitor, FakeProc(102, "python3",
                                  cmdline=["python3", "-m", "crewai", "run"]))
    assert v and v.regra == "argumento"
    assert "crewai" in v.motivo


def test_detecta_binario_renomeado_pelo_exe(monitor):
    # Processo renomeado para "svc" mas cujo executavel e o ollama
    v = avaliar(monitor, FakeProc(103, "svc", exe="/opt/x/ollama"))
    assert v and v.regra == "binario"


def test_porta_proibida_marca_para_encerrar(monitor):
    v = avaliar(monitor, FakeProc(104, "meuserv", conns=[FakeConn(11434)]))
    assert v and v.regra == "porta" and v.encerrar is True


def test_porta_suspeita_apenas_audita(monitor):
    v = avaliar(monitor, FakeProc(105, "node", cmdline=["node", "app.js"],
                                  conns=[FakeConn(3000)]))
    assert v and v.regra == "porta_suspeita" and v.encerrar is False


def test_porta_nao_listen_e_ignorada(monitor):
    v = avaliar(monitor, FakeProc(106, "meuserv",
                                  conns=[FakeConn(11434, status=psutil.CONN_ESTABLISHED)]))
    assert v is None


def test_processo_legitimo_nao_dispara(monitor):
    assert avaliar(monitor, FakeProc(107, "python3",
                                     cmdline=["python3", "manage.py", "runserver"])) is None
    assert avaliar(monitor, FakeProc(108, "code")) is None


def test_navegador_abrindo_arquivo_crewai_nao_dispara(monitor):
    # "chrome" nao e interpretador: a regra de argumento nao se aplica
    assert avaliar(monitor, FakeProc(109, "chrome",
                                     cmdline=["chrome", "crewai_tutorial.html"])) is None


def test_pip_install_de_agente_nao_dispara(monitor):
    assert avaliar(monitor, FakeProc(110, "python3",
                                     cmdline=["python3", "-m", "pip", "install", "crewai"])) is None


def test_detecta_agente_claude_binario(monitor):
    v = avaliar(monitor, FakeProc(130, "claude", exe="/usr/local/bin/claude"))
    assert v and v.regra == "binario" and v.agente == "claude"


def test_detecta_claude_agent_sdk_na_linha_de_comando(monitor):
    v = avaliar(monitor, FakeProc(131, "python3",
                                  cmdline=["python3", "-m", "claude_agent_sdk", "run"]))
    assert v and v.regra == "argumento"


def test_processo_isento(monitor):
    assert avaliar(monitor, FakeProc(111, "systemd")) is None


def test_usuario_autorizado_tem_excecao():
    a = carregar()
    a.usuarios_autorizados.add("pesquisa")
    m = SentinelMonitor(a, bloquear=False)
    assert m.avaliar(FakeProc(112, "ollama", username="pesquisa")) is None
    assert m.avaliar(FakeProc(113, "ollama", username="joao")) is not None


def test_proprio_processo_protegido(monitor):
    import os
    assert monitor.avaliar(FakeProc(os.getpid(), "ollama")) is None


def test_interpretador_versionado(monitor):
    v = avaliar(monitor, FakeProc(114, "python3.11",
                                  cmdline=["python3.11", "autogpt", "--continuous"]))
    assert v and v.regra == "argumento"


def test_modo_auditoria_nao_encerra(monkeypatch, monitor):
    proc = FakeProc(200, "ollama")
    acao = monitor.tratar(proc, monitor.avaliar(proc))
    assert acao == "auditado"


def test_auditoria_nao_repete_mesmo_alerta(monitor):
    proc = FakeProc(201, "ollama")
    v = monitor.avaliar(proc)
    assert monitor.tratar(proc, v) == "auditado"
    assert monitor.tratar(proc, monitor.avaliar(proc)) == "ja_reportado"


def test_registro_de_evento_em_arquivo(tmp_path):
    import json
    arq = tmp_path / "eventos.jsonl"
    m = SentinelMonitor(carregar(), bloquear=False, arquivo_eventos=str(arq))
    proc = FakeProc(202, "ollama")
    m.tratar(proc, m.avaliar(proc))
    linhas = arq.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1
    ev = json.loads(linhas[0])
    assert ev["nome"] == "ollama" and ev["acao"] == "auditado"
