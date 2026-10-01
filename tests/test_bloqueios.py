"""Testes dos geradores de sinkhole de DNS e regras de firewall."""

import pytest

from agenteesp.assinaturas import carregar
from agenteesp.bloqueios import firewall, sinkhole


@pytest.fixture
def a():
    return carregar()


def test_sinkhole_pihole(a):
    saida = sinkhole(a, formato="pihole")
    assert "0.0.0.0 api.openai.com" in saida
    assert "0.0.0.0 ngrok.io" in saida


def test_sinkhole_dnsmasq(a):
    saida = sinkhole(a, formato="dnsmasq")
    assert "address=/api.anthropic.com/0.0.0.0" in saida


def test_sinkhole_rpz_inclui_wildcard(a):
    saida = sinkhole(a, formato="rpz")
    assert "*.ngrok.io CNAME ." in saida
    assert "SOA" in saida


def test_sinkhole_formato_invalido(a):
    with pytest.raises(ValueError):
        sinkhole(a, formato="xyz")


def test_firewall_iptables(a):
    saida = firewall(a, plataforma="iptables")
    assert "--dport 11434 -j DROP" in saida
    assert saida.startswith("#!/bin/sh")


def test_firewall_windows(a):
    saida = firewall(a, plataforma="windows")
    assert "localport=11434" in saida
    assert "netsh advfirewall" in saida


def test_firewall_plataforma_invalida(a):
    with pytest.raises(ValueError):
        firewall(a, plataforma="xyz")


def test_config_json_estende_assinaturas(tmp_path):
    import json
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({
        "adicionar_binarios": ["meuagente"],
        "adicionar_dominios_ia": ["api.exemplo.com"],
        "adicionar_portas_proibidas": {"9999": "Agente interno"},
    }), encoding="utf-8")
    a = carregar(str(cfg))
    assert "meuagente" in a.binarios
    assert 9999 in a.portas_proibidas
    assert "0.0.0.0 api.exemplo.com" in sinkhole(a)
