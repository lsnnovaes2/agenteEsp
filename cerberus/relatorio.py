"""
Consolida os eventos gerados pelo sentinel (um ou mais arquivos JSONL, de
varias maquinas) em um relatorio de inventario, agrupado por equipamento.

Cada equipamento (identificado por hostname + IP) lista todos os agentes/modelos
distintos encontrados nele. Multiplos agentes na mesma maquina ficam juntos, na
mesma entrada. Saidas: tabela de texto, JSON, CSV e HTML.
"""

import csv
import html
import io
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class AgenteDetectado:
    agente: str
    tipo: str            # IA local | Framework | Tunel/Porta | ...
    acao: str            # auditado | encerrado | ...
    ocorrencias: int = 1
    usuarios: set = field(default_factory=set)
    primeiro: str = ""
    ultimo: str = ""


@dataclass
class Equipamento:
    host: str
    ip: str
    agentes: "OrderedDict[str, AgenteDetectado]" = field(default_factory=OrderedDict)

    @property
    def total_agentes(self) -> int:
        return len(self.agentes)

    @property
    def total_ocorrencias(self) -> int:
        return sum(a.ocorrencias for a in self.agentes.values())


_TIPO_POR_REGRA = {
    "binario": "IA local / Tunel",
    "argumento": "Framework de agente",
    "porta": "Servico em porta caracteristica",
    "porta_suspeita": "Porta generica (verificar)",
}


def _tipo(evento: dict) -> str:
    return _TIPO_POR_REGRA.get(evento.get("regra", ""), "Outro")


def _nome_agente(evento: dict) -> str:
    return (evento.get("agente") or evento.get("nome") or "desconhecido").strip()


def ler_eventos(caminhos: Iterable[str]) -> List[dict]:
    """Le um ou mais arquivos JSONL de eventos, ignorando linhas invalidas."""
    eventos = []
    for caminho in caminhos:
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except json.JSONDecodeError:
                    continue
    return eventos


def consolidar(eventos: Iterable[dict],
               incluir_auditoria_porta_suspeita: bool = True) -> List[Equipamento]:
    """
    Agrupa os eventos por equipamento (host|ip) e, dentro de cada um, por agente.
    Retorna a lista ordenada por quantidade de agentes (maior primeiro).
    """
    por_equip: "OrderedDict[str, Equipamento]" = OrderedDict()

    for ev in eventos:
        if not incluir_auditoria_porta_suspeita and ev.get("regra") == "porta_suspeita":
            continue
        host = ev.get("host") or "desconhecido"
        ip = ev.get("ip") or "0.0.0.0"
        chave = f"{host}|{ip}"
        equip = por_equip.get(chave)
        if equip is None:
            equip = por_equip[chave] = Equipamento(host=host, ip=ip)

        agente = _nome_agente(ev)
        det = equip.agentes.get(agente)
        ts = ev.get("timestamp", "")
        if det is None:
            det = equip.agentes[agente] = AgenteDetectado(
                agente=agente, tipo=_tipo(ev), acao=ev.get("acao", ""),
                primeiro=ts, ultimo=ts)
        else:
            det.ocorrencias += 1
            det.ultimo = ts or det.ultimo
        if ev.get("usuario"):
            det.usuarios.add(ev["usuario"])

    equipamentos = list(por_equip.values())
    for e in equipamentos:
        e.agentes = OrderedDict(sorted(e.agentes.items(), key=lambda kv: kv[0]))
    equipamentos.sort(key=lambda e: (-e.total_agentes, e.host))
    return equipamentos


# --------------------------------------------------------------------- saidas
def para_dict(equipamentos: List[Equipamento]) -> dict:
    return {
        "resumo": {
            "equipamentos": len(equipamentos),
            "equipamentos_com_multiplos_agentes": sum(1 for e in equipamentos if e.total_agentes > 1),
            "total_agentes_distintos": sum(e.total_agentes for e in equipamentos),
        },
        "equipamentos": [
            {
                "host": e.host, "ip": e.ip, "qtd_agentes": e.total_agentes,
                "agentes": [
                    {"agente": a.agente, "tipo": a.tipo, "acao": a.acao,
                     "ocorrencias": a.ocorrencias, "usuarios": sorted(a.usuarios),
                     "primeiro": a.primeiro, "ultimo": a.ultimo}
                    for a in e.agentes.values()
                ],
            }
            for e in equipamentos
        ],
    }


def para_json(equipamentos: List[Equipamento]) -> str:
    return json.dumps(para_dict(equipamentos), ensure_ascii=False, indent=2)


def para_csv(equipamentos: List[Equipamento]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["host", "ip", "agente_modelo", "tipo", "acao", "ocorrencias", "usuarios", "qtd_agentes_na_maquina"])
    for e in equipamentos:
        for a in e.agentes.values():
            w.writerow([e.host, e.ip, a.agente, a.tipo, a.acao, a.ocorrencias,
                        ";".join(sorted(a.usuarios)), e.total_agentes])
    return buf.getvalue()


def para_texto(equipamentos: List[Equipamento]) -> str:
    linhas = []
    r = {"eq": len(equipamentos),
         "multi": sum(1 for e in equipamentos if e.total_agentes > 1),
         "ag": sum(e.total_agentes for e in equipamentos)}
    linhas.append("=" * 72)
    linhas.append("RELATORIO DE AGENTES NAO AUTORIZADOS - Cerberus")
    linhas.append(f"Equipamentos afetados: {r['eq']} | com multiplos agentes: {r['multi']} "
                  f"| agentes distintos: {r['ag']}")
    linhas.append("=" * 72)
    for e in equipamentos:
        marca = "  <-- MULTIPLOS AGENTES" if e.total_agentes > 1 else ""
        linhas.append("")
        linhas.append(f"[{e.host}]  IP {e.ip}  ({e.total_agentes} agente(s)){marca}")
        linhas.append("-" * 72)
        for a in e.agentes.values():
            usr = ", ".join(sorted(a.usuarios)) or "-"
            linhas.append(f"  - {a.agente:<22} {a.tipo:<28} {a.acao:<10} "
                          f"x{a.ocorrencias}  usuario: {usr}")
    linhas.append("")
    return "\n".join(linhas)


def para_html(equipamentos: List[Equipamento], titulo: str = "Relatorio Cerberus") -> str:
    def esc(x):
        return html.escape(str(x))

    resumo = para_dict(equipamentos)["resumo"]
    linhas = []
    for e in equipamentos:
        multi = "multi" if e.total_agentes > 1 else ""
        badge = '<span class="badge">múltiplos</span>' if e.total_agentes > 1 else ""
        corpo = []
        for a in e.agentes.values():
            usr = esc(", ".join(sorted(a.usuarios)) or "—")
            corpo.append(
                f"<tr><td class='ag'>{esc(a.agente)}</td><td>{esc(a.tipo)}</td>"
                f"<td><span class='acao'>{esc(a.acao)}</span></td>"
                f"<td class='num'>{a.ocorrencias}</td><td>{usr}</td></tr>")
        linhas.append(f"""
        <section class="equip {multi}">
          <header>
            <h2>{esc(e.host)} {badge}</h2>
            <div class="meta"><span>IP {esc(e.ip)}</span><span>{e.total_agentes} agente(s)</span></div>
          </header>
          <table>
            <thead><tr><th>Agente / Modelo</th><th>Tipo</th><th>Ação</th><th>Ocorr.</th><th>Usuário(s)</th></tr></thead>
            <tbody>{''.join(corpo)}</tbody>
          </table>
        </section>""")

    return f"""<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
<style>
  :root {{ --bg:#eef1f4; --surface:#fff; --ink:#1a2230; --muted:#5b6676; --line:#d9dee6;
           --accent:#1f6f5c; --danger:#a4322c; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#11161d; --surface:#1a212b; --ink:#e7edf4;
           --muted:#9aa7b6; --line:#2b3542; --accent:#46b89a; --danger:#e08a84; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font-family:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.5; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:28px 16px 56px; }}
  h1 {{ font-size:1.5rem; margin:0 0 4px; }}
  .resumo {{ color:var(--muted); margin-bottom:22px; }}
  .resumo b {{ color:var(--ink); }}
  .equip {{ background:var(--surface); border:1px solid var(--line); border-radius:12px;
            margin-bottom:16px; overflow:hidden; }}
  .equip.multi {{ border-color:color-mix(in srgb, var(--danger) 45%, var(--line)); }}
  .equip header {{ padding:14px 16px; border-bottom:1px solid var(--line); }}
  .equip h2 {{ margin:0; font-size:1.05rem; display:flex; align-items:center; gap:10px; }}
  .equip .meta {{ color:var(--muted); font-size:.85rem; display:flex; gap:16px; margin-top:4px;
                  font-variant-numeric:tabular-nums; }}
  .badge {{ font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
            color:var(--danger); border:1px solid currentColor; border-radius:999px; padding:2px 8px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  th, td {{ text-align:left; padding:9px 16px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:.78rem; text-transform:uppercase; letter-spacing:.03em; }}
  tbody tr:last-child td {{ border-bottom:0; }}
  td.ag {{ font-weight:600; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .acao {{ font-size:.78rem; padding:2px 8px; border-radius:999px; background:var(--bg); border:1px solid var(--line); }}
</style></head><body>
<div class="wrap">
  <h1>Relatório de agentes não autorizados</h1>
  <p class="resumo"><b>{resumo['equipamentos']}</b> equipamento(s) afetado(s) ·
     <b>{resumo['equipamentos_com_multiplos_agentes']}</b> com múltiplos agentes ·
     <b>{resumo['total_agentes_distintos']}</b> agente(s) distinto(s)</p>
  {''.join(linhas) or '<p>Nenhum agente detectado nos eventos fornecidos.</p>'}
</div></body></html>"""


def gerar(eventos: Iterable[dict], formato: str = "texto",
          titulo: str = "Relatorio Cerberus",
          incluir_porta_suspeita: bool = True) -> str:
    equip = consolidar(eventos, incluir_porta_suspeita)
    saidas = {
        "texto": lambda: para_texto(equip),
        "json": lambda: para_json(equip),
        "csv": lambda: para_csv(equip),
        "html": lambda: para_html(equip, titulo),
    }
    if formato not in saidas:
        raise ValueError(f"Formato de relatorio desconhecido: {formato}. "
                         f"Use: {', '.join(saidas)}")
    return saidas[formato]()
