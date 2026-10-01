"""Testes da varredura de rede, usando um servidor HTTP falso em localhost."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from cerberus.varredura import (DeteccaoRede, carregar_segmentos, eventos_de,
                                expandir_alvos, varrer_host)


class FakeOllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            corpo = b'{"models": [{"name": "llama3"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def servidor_ollama():
    srv = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield porta
    srv.shutdown()


def test_expandir_cidr():
    ips = expandir_alvos(["192.168.0.0/30"])
    # /30 -> 2 hosts utilizaveis
    assert ips == ["192.168.0.1", "192.168.0.2"]


def test_expandir_ip_isolado():
    assert expandir_alvos(["10.0.0.5"]) == ["10.0.0.5"]


def test_detecta_servico_confirmado(servidor_ollama, monkeypatch):
    # Faz a sonda do Ollama apontar para a porta do servidor falso
    from cerberus import varredura
    monkeypatch.setitem(varredura.SONDAS, servidor_ollama,
                        varredura.Sonda("ollama", "/api/tags", ("models",)))
    achados = varrer_host("127.0.0.1", portas=[servidor_ollama])
    assert len(achados) == 1
    assert achados[0].agente == "ollama"
    assert achados[0].confirmado is True


def test_porta_fechada_nao_detecta():
    # Porta altissima, improvavel de estar aberta
    assert varrer_host("127.0.0.1", portas=[59999]) == []


def test_evento_compativel_com_relatorio():
    d = DeteccaoRede(ip="10.0.0.9", host="PC-9", porta=11434, agente="ollama",
                     confirmado=True)
    ev = d.como_evento()
    assert ev["ip"] == "10.0.0.9" and ev["host"] == "PC-9"
    assert ev["agente"] == "ollama" and ev["regra"] == "porta"
    # consolida junto com eventos do sentinel
    from cerberus.relatorio import consolidar
    equip = consolidar(eventos_de([d]))
    assert equip[0].host == "PC-9"
    assert "ollama" in equip[0].agentes


def test_carregar_segmentos_formato_completo(tmp_path):
    import json
    arq = tmp_path / "redes.json"
    arq.write_text(json.dumps({"segmentos": [
        {"nome": "VLAN10", "cidr": "10.10.0.0/24"},
        {"nome": "VLAN20", "cidr": "10.20.0.0/24"},
    ]}), encoding="utf-8")
    segs = carregar_segmentos(str(arq))
    assert segs == [("VLAN10", "10.10.0.0/24"), ("VLAN20", "10.20.0.0/24")]


def test_carregar_segmentos_lista_simples(tmp_path):
    import json
    arq = tmp_path / "redes.json"
    arq.write_text(json.dumps(["10.1.0.0/24", "10.2.0.0/24"]), encoding="utf-8")
    segs = carregar_segmentos(str(arq))
    assert [c for _, c in segs] == ["10.1.0.0/24", "10.2.0.0/24"]


def test_segmento_aparece_no_relatorio():
    from cerberus.relatorio import consolidar, para_csv
    d = DeteccaoRede(ip="10.20.0.5", host="PC-FIN", porta=11434, agente="ollama",
                     confirmado=True, segmento="VLAN20-Financeiro")
    equip = consolidar(eventos_de([d]))
    assert equip[0].segmento == "VLAN20-Financeiro"
    assert "VLAN20-Financeiro" in para_csv(equip)
