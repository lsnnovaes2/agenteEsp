"""
Gera artefatos de bloqueio para o perimetro da rede a partir das assinaturas:

  * sinkhole de DNS (formatos Pi-hole / BIND RPZ / dnsmasq / hosts);
  * regras de firewall (iptables / Windows netsh) para portas de agentes.

Nao executa nada no sistema: apenas emite texto de configuracao para a equipe
de rede revisar e aplicar nos equipamentos homologados.
"""

from typing import List

from .assinaturas import Assinaturas


def _dominios(a: Assinaturas) -> List[str]:
    vistos, saida = set(), []
    for d in list(a.dominios_ia) + list(a.dominios_tunel):
        d = d.strip().lower().lstrip(".")
        if d and d not in vistos:
            vistos.add(d)
            saida.append(d)
    return saida


def sinkhole(a: Assinaturas, formato: str = "pihole", ip_sinkhole: str = "0.0.0.0") -> str:
    """
    formato: pihole | hosts | dnsmasq | rpz
    """
    dominios = _dominios(a)
    cab = ["# Cerberus - sinkhole de DNS para provedores de IA e tuneis nao homologados",
           f"# formato={formato} | {len(dominios)} dominios", ""]

    if formato in ("pihole", "hosts"):
        linhas = [f"{ip_sinkhole} {d}" for d in dominios]
    elif formato == "dnsmasq":
        linhas = [f"address=/{d}/{ip_sinkhole}" for d in dominios]
    elif formato == "rpz":
        # Response Policy Zone para BIND: redireciona para NXDOMAIN
        cab = ["$TTL 300",
               "@ IN SOA localhost. admin.localhost. ( 1 3600 600 86400 300 )",
               "  IN NS localhost.", ""]
        linhas = []
        for d in dominios:
            linhas.append(f"{d} CNAME .")
            linhas.append(f"*.{d} CNAME .")
    else:
        raise ValueError(f"Formato de sinkhole desconhecido: {formato}")

    return "\n".join(cab + linhas) + "\n"


def firewall(a: Assinaturas, plataforma: str = "iptables") -> str:
    """
    Bloqueia a escuta/saida nas portas caracteristicas de agentes proibidos.
    plataforma: iptables | windows
    """
    portas = sorted(set(a.portas_proibidas) | set(a.portas_suspeitas))
    desc = {**a.portas_proibidas, **a.portas_suspeitas}

    if plataforma == "iptables":
        linhas = ["#!/bin/sh",
                  "# Cerberus - bloqueio de portas de agentes (revisar antes de aplicar)",
                  "set -e"]
        for p in portas:
            linhas.append(f"# {desc[p]}")
            linhas.append(f"iptables -A INPUT  -p tcp --dport {p} -j DROP")
            linhas.append(f"iptables -A OUTPUT -p tcp --dport {p} -j REJECT")
        return "\n".join(linhas) + "\n"

    if plataforma == "windows":
        linhas = ["@echo off",
                  "REM Cerberus - bloqueio de portas de agentes (executar como Administrador)"]
        for p in portas:
            linhas.append(f'netsh advfirewall firewall add rule name="Cerberus-bloqueio-{p}" '
                          f'dir=in action=block protocol=TCP localport={p}')
            linhas.append(f'netsh advfirewall firewall add rule name="Cerberus-bloqueio-out-{p}" '
                          f'dir=out action=block protocol=TCP remoteport={p}')
        return "\n".join(linhas) + "\n"

    raise ValueError(f"Plataforma de firewall desconhecida: {plataforma}")
