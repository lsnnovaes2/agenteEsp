"""Interface de linha de comando do Cerberus."""

import argparse
import logging
import sys

from . import __version__
from .assinaturas import carregar
from .bloqueios import firewall, sinkhole
from .relatorio import gerar as gerar_relatorio, ler_eventos
from .sentinel import SentinelMonitor
from .varredura import eventos_de, varrer_rede


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


def _cmd_relatorio(args) -> int:
    eventos = ler_eventos(args.eventos)
    saida = gerar_relatorio(
        eventos, formato=args.formato,
        incluir_porta_suspeita=not args.sem_portas_suspeitas,
    )
    (open(args.saida, "w", encoding="utf-8").write(saida) if args.saida
     else sys.stdout.write(saida if saida.endswith("\n") else saida + "\n"))
    if args.saida:
        print(f"Relatorio ({args.formato}) salvo em {args.saida}", file=sys.stderr)
    return 0


def _cmd_rede(args) -> int:
    def progresso(feitos, total):
        if feitos == total or feitos % 50 == 0:
            print(f"[*] {feitos}/{total} hosts verificados...", file=sys.stderr)

    print(f"[*] Varrendo {', '.join(args.alvos)} (uso autorizado apenas)...", file=sys.stderr)
    achados = varrer_rede(args.alvos, threads=args.threads, progresso=progresso)
    eventos = eventos_de(achados)
    print(f"[*] {len(eventos)} deteccao(oes) em {len({e['ip'] for e in eventos})} host(s).",
          file=sys.stderr)

    if args.formato == "jsonl":
        saida = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in eventos)
    else:
        saida = gerar_relatorio(eventos, formato=args.formato)
        if not saida.endswith("\n"):
            saida += "\n"
    (open(args.saida, "w", encoding="utf-8").write(saida) if args.saida
     else sys.stdout.write(saida))
    if args.saida:
        print(f"Saida ({args.formato}) salva em {args.saida}", file=sys.stderr)
    return 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cerberus",
        description="Deteccao e bloqueio de agentes de IA e tuneis nao autorizados.",
    )
    p.add_argument("--version", action="version", version=f"Cerberus {__version__}")
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

    r = sub.add_parser("relatorio",
                       help="Consolida os eventos por equipamento (agente, IP, maquina).")
    r.add_argument("eventos", nargs="+",
                   help="Um ou mais arquivos JSONL de eventos gerados pelo sentinel.")
    r.add_argument("--formato", default="texto", choices=["texto", "json", "csv", "html"])
    r.add_argument("--saida", help="Arquivo de saida (padrao: stdout).")
    r.add_argument("--sem-portas-suspeitas", action="store_true",
                   help="Ignora deteccoes de portas genericas (apenas alertas).")
    r.set_defaults(func=_cmd_relatorio)

    v = sub.add_parser("rede",
                       help="Varre faixas de IP da rede interna procurando agentes expostos.")
    v.add_argument("alvos", nargs="+",
                   help="Faixas CIDR ou IPs da SUA rede (ex.: 10.0.0.0/24 192.168.1.5).")
    v.add_argument("--formato", default="jsonl",
                   choices=["jsonl", "texto", "json", "csv", "html"],
                   help="jsonl (padrao) gera eventos para juntar ao relatorio; "
                        "os demais ja montam o relatorio consolidado.")
    v.add_argument("--threads", type=int, default=100, help="Varreduras simultaneas.")
    v.add_argument("--saida", help="Arquivo de saida (padrao: stdout).")
    v.set_defaults(func=_cmd_rede)

    return p


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
