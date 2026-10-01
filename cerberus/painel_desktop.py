"""
Painel desktop (GUI) do Cerberus para buscar, na rede interna, maquinas que
rodam agentes de IA / tuneis expostos.

Usa Tkinter (biblioteca padrao do Python) — nao precisa instalar nada alem do
proprio Cerberus. A varredura roda em uma thread separada para a janela nao
travar, e os resultados aparecem na tabela conforme sao encontrados.

USO AUTORIZADO: varra somente faixas de IP que a sua organizacao administra.
"""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List

from .relatorio import consolidar, para_csv, para_html
from .varredura import SONDAS, DeteccaoRede, expandir_alvos, varrer_host


def _salvar_dialogo(conteudo: str, titulo: str, padrao: str, filtros):
    from tkinter import filedialog, messagebox
    caminho = filedialog.asksaveasfilename(title=titulo, defaultextension=padrao,
                                           filetypes=filtros)
    if not caminho:
        return
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        messagebox.showinfo("Cerberus", f"Salvo em:\n{caminho}")
    except OSError as e:
        messagebox.showerror("Cerberus", f"Falha ao salvar: {e}")


class PainelDesktop:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self._fila = queue.Queue()
        self._parar = threading.Event()
        self._varrendo = False
        self._achados: List[DeteccaoRede] = []
        self._vars_servico = {}

        self.root = tk.Tk()
        self.root.title("Cerberus — Busca de IA na rede")
        self.root.geometry("860x560")
        self.root.minsize(720, 460)

        self._montar_topo()
        self._montar_servicos()
        self._montar_tabela()
        self._montar_rodape()

        self.root.after(120, self._processar_fila)

    # ----------------------------------------------------------------- layout
    def _montar_topo(self):
        tk, ttk = self.tk, self.ttk
        topo = ttk.Frame(self.root, padding=12)
        topo.pack(fill="x")

        ttk.Label(topo, text="Faixas / IPs da rede (separe por espaco):").grid(
            row=0, column=0, columnspan=4, sticky="w")
        self.ent_alvos = ttk.Entry(topo)
        self.ent_alvos.insert(0, "192.168.0.0/24")
        self.ent_alvos.grid(row=1, column=0, columnspan=3, sticky="we", pady=(2, 0))

        ttk.Label(topo, text="Threads:").grid(row=1, column=3, sticky="e", padx=(10, 4))
        self.spin_threads = ttk.Spinbox(topo, from_=10, to=500, width=6)
        self.spin_threads.set(100)
        self.spin_threads.grid(row=1, column=4, sticky="w")

        topo.columnconfigure(0, weight=1)
        topo.columnconfigure(1, weight=1)
        topo.columnconfigure(2, weight=1)

        self.btn_varrer = ttk.Button(topo, text="▶  Varrer rede", command=self._iniciar)
        self.btn_varrer.grid(row=1, column=5, padx=(10, 0))
        self.btn_parar = ttk.Button(topo, text="■  Parar", command=self._parar_varredura,
                                    state="disabled")
        self.btn_parar.grid(row=1, column=6, padx=(6, 0))

    def _montar_servicos(self):
        tk, ttk = self.tk, self.ttk
        frm = ttk.LabelFrame(self.root, text="Agentes/serviços a procurar", padding=8)
        frm.pack(fill="x", padx=12)
        col = 0
        for porta, sonda in SONDAS.items():
            var = tk.BooleanVar(value=True)
            self._vars_servico[porta] = var
            ttk.Checkbutton(frm, text=f"{sonda.servico} ({porta})", variable=var).grid(
                row=0, column=col, sticky="w", padx=6, pady=2)
            col += 1

    def _montar_tabela(self):
        ttk = self.ttk
        frm = ttk.Frame(self.root, padding=(12, 8))
        frm.pack(fill="both", expand=True)

        cols = ("maquina", "ip", "agente", "porta", "confirmado")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        titulos = {"maquina": "Máquina", "ip": "IP", "agente": "Agente / Modelo",
                   "porta": "Porta", "confirmado": "Confirmado"}
        larg = {"maquina": 240, "ip": 130, "agente": 160, "porta": 70, "confirmado": 110}
        for c in cols:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=larg[c], anchor="w")
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _montar_rodape(self):
        ttk = self.ttk
        rod = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        rod.pack(fill="x")
        self.prog = ttk.Progressbar(rod, mode="determinate")
        self.prog.pack(fill="x", pady=(0, 6))
        linha = ttk.Frame(rod)
        linha.pack(fill="x")
        self.lbl_status = ttk.Label(linha, text="Pronto. Informe as faixas e clique em Varrer.")
        self.lbl_status.pack(side="left")
        self.btn_html = ttk.Button(linha, text="Exportar HTML", command=self._exportar_html,
                                   state="disabled")
        self.btn_html.pack(side="right", padx=(6, 0))
        self.btn_csv = ttk.Button(linha, text="Exportar CSV", command=self._exportar_csv,
                                  state="disabled")
        self.btn_csv.pack(side="right")

    # --------------------------------------------------------------- varredura
    def _iniciar(self):
        if self._varrendo:
            return
        from tkinter import messagebox
        alvos = self.ent_alvos.get().split()
        if not alvos:
            messagebox.showwarning("Cerberus", "Informe ao menos uma faixa ou IP.")
            return
        portas = [p for p, v in self._vars_servico.items() if v.get()]
        if not portas:
            messagebox.showwarning("Cerberus", "Selecione ao menos um serviço.")
            return
        try:
            ips = expandir_alvos(alvos)
        except Exception as e:
            messagebox.showerror("Cerberus", f"Faixa inválida: {e}")
            return
        if not ips:
            messagebox.showwarning("Cerberus", "Nenhum IP resultou das faixas informadas.")
            return

        self.tree.delete(*self.tree.get_children())
        self._achados.clear()
        self._parar.clear()
        self._varrendo = True
        self.btn_varrer.config(state="disabled")
        self.btn_parar.config(state="normal")
        self.btn_html.config(state="disabled")
        self.btn_csv.config(state="disabled")
        self.prog.config(maximum=len(ips), value=0)

        threads = int(float(self.spin_threads.get()))
        t = threading.Thread(target=self._worker, args=(ips, portas, threads), daemon=True)
        t.start()

    def _worker(self, ips, portas, threads):
        from concurrent.futures import as_completed
        feitos = 0
        total = len(ips)
        with ThreadPoolExecutor(max_workers=min(threads, max(total, 1))) as ex:
            futuros = {ex.submit(varrer_host, ip, portas): ip for ip in ips}
            for fut in as_completed(futuros):
                if self._parar.is_set():
                    break
                feitos += 1
                try:
                    for d in fut.result():
                        self._fila.put(("achado", d))
                except Exception:
                    pass
                self._fila.put(("progresso", (feitos, total)))
        self._fila.put(("fim", None))

    def _parar_varredura(self):
        self._parar.set()
        self.lbl_status.config(text="Interrompendo…")

    # ----------------------------------------------------------------- eventos
    def _processar_fila(self):
        try:
            while True:
                tipo, dado = self._fila.get_nowait()
                if tipo == "achado":
                    self._add_linha(dado)
                elif tipo == "progresso":
                    feitos, total = dado
                    self.prog.config(value=feitos)
                    self.lbl_status.config(
                        text=f"Varrendo… {feitos}/{total} hosts — "
                             f"{len(self._achados)} detecção(ões)")
                elif tipo == "fim":
                    self._finalizar()
        except queue.Empty:
            pass
        self.root.after(120, self._processar_fila)

    def _add_linha(self, d: DeteccaoRede):
        self._achados.append(d)
        self.tree.insert("", "end", values=(
            d.host, d.ip, d.agente, d.porta, "sim" if d.confirmado else "porta aberta"))

    def _finalizar(self):
        self._varrendo = False
        self.btn_varrer.config(state="normal")
        self.btn_parar.config(state="disabled")
        maquinas = len({d.ip for d in self._achados})
        self.lbl_status.config(
            text=f"Concluído. {len(self._achados)} detecção(ões) em {maquinas} máquina(s).")
        if self._achados:
            self.btn_html.config(state="normal")
            self.btn_csv.config(state="normal")

    # ----------------------------------------------------------------- export
    def _eventos(self):
        return [d.como_evento() for d in self._achados]

    def _exportar_html(self):
        html = para_html(consolidar(self._eventos()), titulo="Relatório Cerberus")
        _salvar_dialogo(html, "Salvar relatório HTML", ".html",
                        [("HTML", "*.html"), ("Todos", "*.*")])

    def _exportar_csv(self):
        csv_txt = para_csv(consolidar(self._eventos()))
        _salvar_dialogo(csv_txt, "Salvar CSV", ".csv",
                        [("CSV", "*.csv"), ("Todos", "*.*")])

    def executar(self):
        self.root.mainloop()


def main():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        import sys
        print("ERRO: Tkinter nao esta disponivel neste Python.\n"
              "  Linux : instale o pacote do sistema (ex.: sudo apt install python3-tk)\n"
              "  Windows/macOS: Tkinter ja vem com o instalador oficial do Python.",
              file=sys.stderr)
        return 1
    PainelDesktop().executar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
