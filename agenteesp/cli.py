"""Interface de linha de comando do agenteEsp."""

import argparse
import logging
import sys

from . import __version__
from .assinaturas import carregar
from .bloqueios import firewall, sinkhole
from .sentinel import SentinelMonitor


def _configurar_log(nivel: str, arquivo: str = None) -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    if arquivo:
        handlers.append(logging.FileHandler(arquivo, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _cmd_sentinel(args) -> int:
    _configurar_log(args.log_nivel, args.log_arquivo)
    a = carregar(args.config)
    monitor = SentinelMonitor(
        assinaturas=a,
        intervalo=args.intervalo,
        bloquear=args.bloquear,
        arquivo_eventos=args.eventos,
    )
    monitor.iniciar()
    return 0


def _cmd_sinkhole(args) -> int:
    a = carregar(args.config)
    saida = sinkhole(a, formato=args.formato, ip_sinkhole=args.ip)
    (open(args.saida, "w", encoding="utf-8").write(saida) if args.saida
     else sys.stdout.write(saida))
    return 0


def _cmd_firewall(args) -> int:
    a = carregar(args.config)
    saida = firewall(a, plataforma=args.plataforma)
    (open(args.saida, "w", encoding="utf-8").write(saida) if args.saida
     else sys.stdout.write(saida))
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agenteesp",
        description="Deteccao e bloqueio de agentes de IA e tuneis nao autorizados.",
    )
    p.add_argument("--version", action="version", version=f"agenteEsp {__version__}")
    p.add_argument("--config", help="Arquivo JSON com assinaturas adicionais/substitutas.")
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("sentinel", help="Monitora e (opcionalmente) encerra processos locais.")
    s.add_argument("--intervalo", type=float, default=3.0, help="Segundos entre varreduras.")
    s.add_argument("--bloquear", action="store_true",
                   help="Encerra os processos. Sem esta flag, apenas audita (padrao).")
    s.add_argument("--eventos", help="Arquivo JSONL para registrar as violacoes.")
    s.add_argument("--log-nivel", default="INFO")
    s.add_argument("--log-arquivo")
    s.set_defaults(func=_cmd_sentinel)

    k = sub.add_parser("sinkhole", help="Gera lista de bloqueio de DNS.")
    k.add_argument("--formato", default="pihole", choices=["pihole", "hosts", "dnsmasq", "rpz"])
    k.add_argument("--ip", default="0.0.0.0", help="IP de redirecionamento do sinkhole.")
    k.add_argument("--saida", help="Arquivo de saida (padrao: stdout).")
    k.set_defaults(func=_cmd_sinkhole)

    f = sub.add_parser("firewall", help="Gera regras de firewall para portas de agentes.")
    f.add_argument("--plataforma", default="iptables", choices=["iptables", "windows"])
    f.add_argument("--saida", help="Arquivo de saida (padrao: stdout).")
    f.set_defaults(func=_cmd_firewall)

    return p


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
