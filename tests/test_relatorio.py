"""Testes da consolidacao de eventos em relatorio por equipamento."""

import csv
import io
import json

import pytest

from cerberus.relatorio import (consolidar, gerar, ler_eventos, para_csv,
                                  para_dict, para_html)


def ev(host, ip, agente, regra="binario", acao="encerrado", usuario="joao", ts="2026-10-01T10:00:00"):
    return {"host": host, "ip": ip, "agente": agente, "regra": regra,
            "acao": acao, "usuario": usuario, "timestamp": ts}


@pytest.fixture
def eventos():
    return [
        ev("PC-01", "10.0.0.11", "ollama"),
        ev("PC-01", "10.0.0.11", "ngrok", acao="encerrado"),
        ev("PC-01", "10.0.0.11", "crewai", regra="argumento"),
        ev("PC-02", "10.0.0.22", "lmstudio"),
        ev("PC-01", "10.0.0.11", "ollama"),  # repeticao -> conta ocorrencia
    ]


def test_agrupa_por_equipamento(eventos):
    equip = consolidar(eventos)
    assert len(equip) == 2
    # PC-01 tem 3 agentes distintos -> vem primeiro (ordenado por qtd)
    assert equip[0].host == "PC-01"
    assert equip[0].total_agentes == 3
    assert equip[1].host == "PC-02"


def test_multiplos_agentes_na_mesma_maquina(eventos):
    equip = consolidar(eventos)
    pc01 = equip[0]
    nomes = set(pc01.agentes.keys())
    assert nomes == {"ollama", "ngrok", "crewai"}


def test_conta_ocorrencias_repetidas(eventos):
    pc01 = consolidar(eventos)[0]
    assert pc01.agentes["ollama"].ocorrencias == 2


def test_resumo(eventos):
    d = para_dict(consolidar(eventos))
    assert d["resumo"]["equipamentos"] == 2
    assert d["resumo"]["equipamentos_com_multiplos_agentes"] == 1
    assert d["resumo"]["total_agentes_distintos"] == 4


def test_csv_tem_uma_linha_por_agente(eventos):
    texto = para_csv(consolidar(eventos))
    linhas = list(csv.DictReader(io.StringIO(texto)))
    assert len(linhas) == 4  # 3 do PC-01 + 1 do PC-02
    pc01 = [l for l in linhas if l["host"] == "PC-01"]
    assert all(l["qtd_agentes_na_maquina"] == "3" for l in pc01)
    ollama = next(l for l in pc01 if l["agente_modelo"] == "ollama")
    assert ollama["ocorrencias"] == "2"


def test_html_marca_maquina_com_multiplos(eventos):
    h = para_html(consolidar(eventos))
    assert "múltiplos" in h
    assert "PC-01" in h and "10.0.0.11" in h


def test_fallback_nome_quando_sem_agente():
    equip = consolidar([{"host": "X", "ip": "1.1.1.1", "nome": "ollama", "regra": "binario"}])
    assert "ollama" in equip[0].agentes


def test_porta_suspeita_pode_ser_excluida():
    evs = [ev("X", "1.1.1.1", "Node", regra="porta_suspeita", acao="auditado")]
    assert len(consolidar(evs, incluir_auditoria_porta_suspeita=True)) == 1
    assert len(consolidar(evs, incluir_auditoria_porta_suspeita=False)) == 0


def test_gerar_formatos(eventos):
    assert "RELATORIO" in gerar(eventos, "texto")
    assert json.loads(gerar(eventos, "json"))["resumo"]["equipamentos"] == 2
    assert "<table>" in gerar(eventos, "html")
    with pytest.raises(ValueError):
        gerar(eventos, "pdf")


def test_ler_eventos_ignora_linha_invalida(tmp_path):
    arq = tmp_path / "e.jsonl"
    arq.write_text(json.dumps(ev("X", "1.1.1.1", "ollama")) + "\nLINHA QUEBRADA\n"
                   + json.dumps(ev("Y", "2.2.2.2", "ngrok")) + "\n", encoding="utf-8")
    assert len(ler_eventos([str(arq)])) == 2


def test_ler_multiplos_arquivos(tmp_path):
    a = tmp_path / "a.jsonl"; b = tmp_path / "b.jsonl"
    a.write_text(json.dumps(ev("A", "1.1.1.1", "ollama")) + "\n", encoding="utf-8")
    b.write_text(json.dumps(ev("B", "2.2.2.2", "ngrok")) + "\n", encoding="utf-8")
    equip = consolidar(ler_eventos([str(a), str(b)]))
    assert {e.host for e in equip} == {"A", "B"}
