"""
Calculador de Gastos
--------------------
Controle de despesas pessoais com interface moderna em CustomTkinter:
- Modo escuro por padrão, com alternância claro/escuro.
- Paleta consistente com cor de destaque, tipografia com hierarquia e
  layout em cards com cantos arredondados.
- Gastos organizados por mês (seletor de Mês/Ano em calendário pop-up),
  orçamento por mês, cópia de contas fixas entre meses.
- Gráficos matplotlib integrados à paleta (rosca por categoria, barras de
  orçamento x gasto x restante, barras por cartão) e aba de Evolução.
- Feedback via "toasts" discretos (sem messagebox do sistema).

A lógica de cálculo e a geração dos gráficos foram mantidas; apenas a
camada visual foi modernizada.

Requer: customtkinter, matplotlib. Rode com o interpretador do .venv:
    .venv/bin/python calculador.py
"""

import calendar
import json
import os
import tkinter as tk
from datetime import date
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter as ctk
import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Arquivo de dados fica na mesma pasta do script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "gastos.json")

CATEGORIAS = [
    "Alimentação",
    "Aluguel",
    "Luz",
    "Água",
    "Gás",
    "Internet/Telefone",
    "Fatura de Cartão",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Outros",
]

# Cor de cada categoria (usada nos gráficos) - vivas, funcionam nos dois temas
CATEGORIA_CORES = {
    "Alimentação": "#6366F1",
    "Aluguel": "#8B5CF6",
    "Luz": "#F59E0B",
    "Água": "#06B6D4",
    "Gás": "#EF4444",
    "Internet/Telefone": "#0EA5E9",
    "Fatura de Cartão": "#4338CA",
    "Transporte": "#14B8A6",
    "Saúde": "#EC4899",
    "Educação": "#F97316",
    "Lazer": "#22C55E",
    "Outros": "#94A3B8",
}

# Categorias consideradas "contas fixas" (recorrentes todo mês)
CONTAS_FIXAS = [
    "Aluguel",
    "Luz",
    "Água",
    "Gás",
    "Internet/Telefone",
    "Fatura de Cartão",
]

# Formas de pagamento / cartões
CARTOES = [
    "Dinheiro",
    "Pix",
    "Débito",
    "Cartão de Crédito",
    "Outro",
]
CARTAO_PADRAO = "Outro"

# Cor de cada forma de pagamento (usada no gráfico)
CARTAO_CORES = {
    "Dinheiro": "#22C55E",
    "Pix": "#06B6D4",
    "Débito": "#6366F1",
    "Cartão de Crédito": "#EC4899",
    "Outro": "#94A3B8",
}

# --------------------------------------------------------------- paleta ---
# Cores em tupla (claro, escuro): resolvidas conforme o tema atual.
ACCENT = "#3B82F6"        # cor de destaque (azul)
ACCENT_HOVER = "#2563EB"
COR_GASTO = "#F59E0B"     # âmbar
COR_POS = "#22C55E"       # verde
COR_NEG = "#EF4444"       # vermelho
COR_ORC = ACCENT

BG = ("#EEF1F8", "#15171C")       # fundo geral
CARD = ("#FFFFFF", "#20242C")     # cards
CARD2 = ("#F1F3FB", "#282D37")    # campos / superfícies secundárias
TEXTO = ("#1F2430", "#E7E9EE")    # texto principal
SUB = ("#75809A", "#9AA3B2")      # texto secundário / rótulos
BORDA = ("#E2E6F0", "#333844")    # bordas
GRID = ("#EEF0F6", "#333844")     # gridlines dos gráficos
ZEBRA = ("#F7F8FC", "#262B34")    # linha alternada da tabela


def _cor(tupla):
    """Resolve uma tupla (claro, escuro) para a cor do tema atual."""
    return tupla[1] if ctk.get_appearance_mode() == "Dark" else tupla[0]


# =========================================================== dados / util ===
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

MESES_ABREV = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


def label_mes_curto(chave):
    """Converte 'AAAA-MM' em 'set/26'."""
    try:
        ano, mes = chave.split("-")
        return f"{MESES_ABREV[int(mes) - 1]}/{ano[2:]}"
    except (ValueError, IndexError):
        return chave


def mes_de_data(texto):
    """Extrai a chave de mês 'AAAA-MM' de uma data 'dd/mm/aaaa'."""
    partes = (texto or "").strip().split("/")
    if len(partes) == 3:
        try:
            _dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
            if 1 <= mes <= 12:
                return f"{ano:04d}-{mes:02d}"
        except ValueError:
            pass
    return None


def mes_do_gasto(gasto):
    """Chave de mês de um gasto (a partir da sua data)."""
    return mes_de_data(gasto.get("data", ""))


def dia_de_data(texto):
    """Extrai o dia (int) de uma data 'dd/mm/aaaa'. Retorna 1 se não der."""
    partes = (texto or "").strip().split("/")
    try:
        return int(partes[0])
    except (ValueError, IndexError):
        return 1


def nome_mes(chave):
    """Converte 'AAAA-MM' em algo como 'Setembro 2026'."""
    try:
        ano, mes = chave.split("-")
        return f"{MESES_PT[int(mes) - 1]} {ano}"
    except (ValueError, IndexError):
        return chave


def mes_atual_chave():
    hoje = date.today()
    return f"{hoje.year:04d}-{hoje.month:02d}"


def carregar_dados():
    """Lê os orçamentos (por mês) e os gastos do arquivo JSON.

    Aceita vários formatos, garantindo compatibilidade:
    - novo: {"orcamentos": {"AAAA-MM": valor, ...}, "gastos": [...]}
    - anterior: {"orcamento": valor_único, "gastos": [...]}
    - antigo: apenas uma lista de gastos.
    Retorna (orcamentos: dict, gastos: list).
    """
    if not os.path.exists(DATA_FILE):
        return {}, []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, []

    if isinstance(dados, list):  # formato antigo (lista pura)
        return {}, dados

    gastos = dados.get("gastos", [])
    if "orcamentos" in dados:  # formato novo (por mês)
        orcamentos = {k: float(v) for k, v in dados["orcamentos"].items()}
        return orcamentos, gastos

    # formato anterior (orçamento único) -> aplica o valor a cada mês existente
    orcamentos = {}
    valor = float(dados.get("orcamento", 0.0))
    if valor > 0:
        for gasto in gastos:
            chave = mes_do_gasto(gasto) or mes_atual_chave()
            orcamentos[chave] = valor
    return orcamentos, gastos


def salvar_dados(orcamentos, gastos):
    """Grava os orçamentos por mês e a lista de gastos no arquivo JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"orcamentos": orcamentos, "gastos": gastos},
            f,
            ensure_ascii=False,
            indent=2,
        )


def formatar_moeda(valor):
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def totais_por_categoria(gastos):
    """Retorna um dict {categoria: total} apenas com categorias que têm gasto."""
    totais = {}
    for gasto in gastos:
        cat = gasto["categoria"]
        totais[cat] = totais.get(cat, 0.0) + gasto["valor"]
    return totais


def totais_por_cartao(gastos):
    """Retorna um dict {cartão: total} apenas com formas de pagamento usadas."""
    totais = {}
    for gasto in gastos:
        cartao = gasto.get("cartao", CARTAO_PADRAO)
        totais[cartao] = totais.get(cartao, 0.0) + gasto["valor"]
    return totais


def _cor_progresso(pct):
    """Cor da barra conforme o quanto do orçamento já foi usado."""
    if pct >= 100:
        return COR_NEG
    if pct >= 75:
        return COR_GASTO
    return COR_POS


# ================================================================== app ===
class CalculadorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculador de Gastos")
        self.root.geometry("1080x980")
        self.root.minsize(940, 800)

        self.orcamentos, self.gastos = carregar_dados()
        self.mes_atual = mes_atual_chave()
        self._popup_mes = None
        self._toast_lbl = None

        self._preparar_fontes()
        self._configurar_matplotlib()
        self._montar_widgets()
        self._estilizar_treeview()
        self._atualizar_tudo()

    # ------------------------------------------------------------- fontes ---
    def _preparar_fontes(self):
        preferidas = ["Inter", "Segoe UI", "Roboto", "Ubuntu", "Cantarell",
                      "Noto Sans", "DejaVu Sans", "Helvetica"]
        familias = set(tkfont.families())
        self.familia = next((f for f in preferidas if f in familias), "sans-serif")
        fam = self.familia
        self.ft_titulo = ctk.CTkFont(family=fam, size=20, weight="bold")
        self.ft_subtitulo = ctk.CTkFont(family=fam, size=12)
        self.ft_secao = ctk.CTkFont(family=fam, size=14, weight="bold")
        self.ft_rotulo = ctk.CTkFont(family=fam, size=11, weight="bold")
        self.ft_valor = ctk.CTkFont(family=fam, size=24, weight="bold")
        self.ft_valor_pq = ctk.CTkFont(family=fam, size=17, weight="bold")
        self.ft_normal = ctk.CTkFont(family=fam, size=12)
        self.ft_bold = ctk.CTkFont(family=fam, size=12, weight="bold")
        self.ft_pequena = ctk.CTkFont(family=fam, size=11)

    def _configurar_matplotlib(self):
        # usa uma fonte que o matplotlib garante ter (a UI usa self.familia);
        # se a família da UI também existir no matplotlib, aproveita.
        disponiveis = {f.name for f in mpl.font_manager.fontManager.ttflist}
        familia_mpl = self.familia if self.familia in disponiveis else "DejaVu Sans"
        mpl.rcParams.update({
            "font.size": 9,
            "font.family": familia_mpl,
            "figure.autolayout": False,
        })

    def _estilizar_treeview(self):
        """Estiliza a ttk.Treeview conforme o tema atual (claro/escuro)."""
        card = _cor(CARD)
        texto = _cor(TEXTO)
        sub = _cor(SUB)
        heading_bg = _cor(CARD2)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=card, fieldbackground=card,
                        foreground=texto, rowheight=30, borderwidth=0,
                        font=(self.familia, 10))
        style.configure("Treeview.Heading", background=heading_bg,
                        foreground=sub, relief="flat", borderwidth=0,
                        font=(self.familia, 10, "bold"))
        style.map("Treeview.Heading", background=[("active", heading_bg)])
        style.map("Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        if hasattr(self, "tree"):
            self.tree.tag_configure("par", background=_cor(ZEBRA), foreground=texto)
            self.tree.tag_configure("impar", background=card, foreground=texto)

    # -------------------------------------------------------------- toasts ---
    def _toast(self, mensagem, tipo="info"):
        """Mostra uma mensagem discreta e temporária no rodapé da janela."""
        cores = {"sucesso": COR_POS, "erro": COR_NEG, "info": ACCENT}
        if self._toast_lbl is not None and self._toast_lbl.winfo_exists():
            self._toast_lbl.destroy()
        lbl = ctk.CTkLabel(self.root, text=f"  {mensagem}  ",
                           fg_color=cores.get(tipo, ACCENT), text_color="white",
                           corner_radius=10, font=self.ft_bold, height=40)
        lbl.place(relx=0.5, rely=0.965, anchor="s")
        self._toast_lbl = lbl
        self.root.after(2800, lambda: lbl.winfo_exists() and lbl.destroy())

    def _confirmar(self, titulo, mensagem):
        """Diálogo modal de confirmação (Sim/Não) no estilo do app."""
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(titulo)
        dlg.geometry("380x180")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.after(50, dlg.grab_set)
        resultado = {"ok": False}

        ctk.CTkLabel(dlg, text=titulo, font=self.ft_secao).pack(
            padx=24, pady=(22, 4), anchor="w")
        ctk.CTkLabel(dlg, text=mensagem, font=self.ft_normal, wraplength=330,
                     justify="left", text_color=SUB).pack(
            padx=24, anchor="w")

        botoes = ctk.CTkFrame(dlg, fg_color="transparent")
        botoes.pack(side="bottom", fill="x", padx=24, pady=20)

        def sim():
            resultado["ok"] = True
            dlg.destroy()

        ctk.CTkButton(botoes, text="Remover", fg_color=COR_NEG,
                      hover_color="#C0392B", font=self.ft_bold,
                      command=sim, width=110).pack(side="right", padx=(8, 0))
        ctk.CTkButton(botoes, text="Cancelar", fg_color="transparent",
                      border_width=1, border_color=BORDA,
                      text_color=TEXTO, hover_color=CARD2,
                      font=self.ft_bold, command=dlg.destroy,
                      width=110).pack(side="right")
        dlg.wait_window()
        return resultado["ok"]

    # ------------------------------------------------------------------ mês ---
    def gastos_do_mes(self):
        return [g for g in self.gastos if mes_do_gasto(g) == self.mes_atual]

    def orcamento_do_mes(self):
        return self.orcamentos.get(self.mes_atual, 0.0)

    def meses_disponiveis(self):
        chaves = set(self.orcamentos.keys())
        for gasto in self.gastos:
            chave = mes_do_gasto(gasto)
            if chave:
                chaves.add(chave)
        chaves.add(self.mes_atual)
        return sorted(chaves, reverse=True)

    def _meses_com_dados_asc(self):
        chaves = set(self.orcamentos.keys())
        for gasto in self.gastos:
            chave = mes_do_gasto(gasto)
            if chave:
                chaves.add(chave)
        return sorted(chaves)

    def _ir_para_mes(self, delta):
        ano, mes = (int(x) for x in self.mes_atual.split("-"))
        mes += delta
        while mes < 1:
            mes += 12
            ano -= 1
        while mes > 12:
            mes -= 12
            ano += 1
        self.mes_atual = f"{ano:04d}-{mes:02d}"
        self._sincronizar_mes()

    def _ir_para_mes_atual(self):
        self.mes_atual = mes_atual_chave()
        self._sincronizar_mes()

    def _sincronizar_mes(self):
        self.mes_btn.configure(text=nome_mes(self.mes_atual))
        self.orc_var.set(f"{self.orcamento_do_mes():.2f}".replace(".", ","))
        self._atualizar_tudo()

    # ---- calendário pop-up de mês/ano ----
    def _abrir_seletor_mes(self):
        self._fechar_popup_mes()
        pop = ctk.CTkToplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        self._popup_mes = pop
        self._ano_popup = int(self.mes_atual.split("-")[0])

        x = self.mes_btn.winfo_rootx()
        y = self.mes_btn.winfo_rooty() + self.mes_btn.winfo_height() + 6
        pop.geometry(f"+{x}+{y}")

        self._popup_inner = ctk.CTkFrame(pop, fg_color=CARD,
                                         border_width=1, border_color=BORDA,
                                         corner_radius=12)
        self._popup_inner.pack(padx=0, pady=0)
        self._render_popup_mes()

        pop.bind("<Escape>", lambda e: self._fechar_popup_mes())
        pop.after(20, pop.focus_force)
        self._bind_fora = self.root.bind_all(
            "<Button-1>", self._talvez_fechar_popup, add="+")

    def _fechar_popup_mes(self):
        if getattr(self, "_bind_fora", None):
            self.root.unbind_all("<Button-1>")
            self._bind_fora = None
        pop = self._popup_mes
        if pop is not None and pop.winfo_exists():
            pop.destroy()
        self._popup_mes = None

    def _talvez_fechar_popup(self, evento):
        pop = self._popup_mes
        if not pop or not pop.winfo_exists():
            return
        clicado = str(evento.widget)
        if not clicado.startswith(str(pop)) and evento.widget is not self.mes_btn:
            self._fechar_popup_mes()

    def _mudar_ano_popup(self, delta):
        self._ano_popup += delta
        self._render_popup_mes()

    def _escolher_mes_popup(self, chave):
        self.mes_atual = chave
        self._fechar_popup_mes()
        self._sincronizar_mes()

    def _render_popup_mes(self):
        parent = self._popup_inner
        for w in parent.winfo_children():
            w.destroy()

        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkButton(head, text="◀", width=32, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT,
                      hover_color=CARD2,
                      command=lambda: self._mudar_ano_popup(-1)).pack(side="left")
        ctk.CTkLabel(head, text=str(self._ano_popup), font=self.ft_secao).pack(
            side="left", expand=True)
        ctk.CTkButton(head, text="▶", width=32, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT,
                      hover_color=CARD2,
                      command=lambda: self._mudar_ano_popup(1)).pack(side="right")

        grade = ctk.CTkFrame(parent, fg_color="transparent")
        grade.pack(padx=12, pady=(0, 6))
        com_dados = set(self.meses_disponiveis())
        hoje = mes_atual_chave()
        for i, abrev in enumerate(MESES_ABREV):
            linha, coluna = divmod(i, 3)
            chave = f"{self._ano_popup:04d}-{i + 1:02d}"
            selecionado = chave == self.mes_atual
            tem_dados = chave in com_dados
            if selecionado:
                fg, hover, txt = ACCENT, ACCENT_HOVER, "white"
            elif tem_dados:
                fg, hover, txt = CARD2, BORDA, ACCENT
            else:
                fg, hover, txt = "transparent", CARD2, TEXTO
            texto = abrev.capitalize() + (" •" if tem_dados and not selecionado else "")
            borda = 2 if (chave == hoje and not selecionado) else 0
            ctk.CTkButton(grade, text=texto, width=76, height=34,
                          font=self.ft_bold if selecionado else self.ft_normal,
                          fg_color=fg, hover_color=hover, text_color=txt,
                          border_width=borda, border_color=ACCENT,
                          command=lambda k=chave: self._escolher_mes_popup(k)
                          ).grid(row=linha, column=coluna, padx=4, pady=4)

        ctk.CTkButton(parent, text="Ir para o mês atual",
                      fg_color="transparent", text_color=SUB,
                      hover_color=CARD2, font=self.ft_pequena,
                      command=lambda: self._escolher_mes_popup(mes_atual_chave())
                      ).pack(pady=(0, 10))

    # ------------------------------------------------------------------ UI ---
    def _montar_widgets(self):
        self.root.configure(fg_color=BG)
        self._montar_header()

        corpo = ctk.CTkFrame(self.root, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self._montar_seletor_mes(corpo)
        self._montar_cards(corpo)
        self._montar_progresso(corpo)

        self.tabview = ctk.CTkTabview(corpo, fg_color=CARD,
                                      segmented_button_selected_color=ACCENT,
                                      segmented_button_selected_hover_color=ACCENT_HOVER)
        self.tabview.pack(fill="both", expand=True, pady=(6, 0))
        self.tabview.add("Lançamentos")
        self.tabview.add("Gráficos do mês")
        self.tabview.add("Evolução")

        self._montar_aba_lancamentos(self.tabview.tab("Lançamentos"))
        self._montar_aba_graficos(self.tabview.tab("Gráficos do mês"))
        self._montar_aba_evolucao(self.tabview.tab("Evolução"))

    def _montar_header(self):
        header = ctk.CTkFrame(self.root, fg_color=ACCENT, corner_radius=0, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)

        esq = ctk.CTkFrame(header, fg_color="transparent")
        esq.pack(side="left", padx=22)
        ctk.CTkLabel(esq, text="💰  Calculador de Gastos", text_color="white",
                     font=self.ft_titulo).pack(anchor="w", pady=(14, 0))
        ctk.CTkLabel(esq, text="Controle simples das suas despesas",
                     text_color="#E4E9FF", font=self.ft_subtitulo).pack(anchor="w")

        self.btn_tema = ctk.CTkButton(
            header, text="☀️  Modo claro", width=140, font=self.ft_bold,
            fg_color="#FFFFFF", text_color=ACCENT, hover_color="#E7ECFF",
            command=self._alternar_tema)
        self.btn_tema.pack(side="right", padx=22)

    def _alternar_tema(self):
        novo = "Light" if ctk.get_appearance_mode() == "Dark" else "Dark"
        ctk.set_appearance_mode(novo)
        if novo == "Dark":
            self.btn_tema.configure(text="☀️  Modo claro")
        else:
            self.btn_tema.configure(text="🌙  Modo escuro")
        self.root.configure(fg_color=BG)
        self._estilizar_treeview()
        self._atualizar_tudo()

    def _montar_seletor_mes(self, parent):
        barra = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
        barra.pack(fill="x", pady=(16, 0))

        ctk.CTkLabel(barra, text="📅  Mês", text_color=SUB,
                     font=self.ft_rotulo).pack(side="left", padx=(18, 10), pady=12)

        ctk.CTkButton(barra, text="◀", width=36, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT,
                      hover_color=CARD2,
                      command=lambda: self._ir_para_mes(-1)).pack(side="left")

        self.mes_btn = ctk.CTkButton(
            barra, text=nome_mes(self.mes_atual), width=190, font=self.ft_bold,
            fg_color=CARD2, text_color=TEXTO, hover_color=BORDA,
            command=self._abrir_seletor_mes)
        self.mes_btn.pack(side="left", padx=6)

        ctk.CTkButton(barra, text="▶", width=36, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT,
                      hover_color=CARD2,
                      command=lambda: self._ir_para_mes(1)).pack(side="left")

        ctk.CTkButton(barra, text="Mês atual", width=90, font=self.ft_pequena,
                      fg_color="transparent", text_color=SUB,
                      hover_color=CARD2,
                      command=self._ir_para_mes_atual).pack(side="right", padx=(6, 16))
        ctk.CTkButton(barra, text="📋  Copiar contas fixas", font=self.ft_pequena,
                      fg_color="transparent", text_color=ACCENT,
                      hover_color=CARD2,
                      command=self._copiar_contas_fixas).pack(side="right")

    def _montar_cards(self, parent):
        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(14, 10))
        for i in range(3):
            cards.columnconfigure(i, weight=1, uniform="cards")

        self.card_orc_valor = self._criar_card(cards, 0, "🎯", "ORÇAMENTO", ACCENT)
        self.card_gasto_valor = self._criar_card(cards, 1, "💸", "TOTAL GASTO",
                                                 COR_GASTO)
        (self.card_rest_icone, self.card_rest_titulo,
         self.card_rest_valor) = self._criar_card(cards, 2, "🟢", "RESTANTE",
                                                  COR_POS, completo=True)

    def _criar_card(self, parent, coluna, icone, titulo, cor_valor, completo=False):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
        card.grid(row=0, column=coluna, sticky="nsew", padx=6)

        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(14, 0))
        icone_lbl = ctk.CTkLabel(topo, text=icone, font=self.ft_valor_pq)
        icone_lbl.pack(side="left")
        titulo_lbl = ctk.CTkLabel(topo, text=titulo, text_color=SUB,
                                  font=self.ft_rotulo)
        titulo_lbl.pack(side="left", padx=8)

        valor_lbl = ctk.CTkLabel(card, text="R$ 0,00", text_color=cor_valor,
                                 font=self.ft_valor)
        valor_lbl.pack(anchor="w", padx=18, pady=(2, 16))

        if completo:
            return icone_lbl, titulo_lbl, valor_lbl
        return valor_lbl

    def _montar_progresso(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
        wrap.pack(fill="x", pady=(0, 12))

        topo = ctk.CTkFrame(wrap, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(topo, text="Uso do orçamento", font=self.ft_bold).pack(
            side="left")
        self.prog_label = ctk.CTkLabel(topo, text="0% usado", font=self.ft_bold,
                                       text_color=SUB)
        self.prog_label.pack(side="right")

        self.prog_bar = ctk.CTkProgressBar(wrap, height=14, corner_radius=8,
                                           progress_color=COR_POS)
        self.prog_bar.pack(fill="x", padx=18, pady=(0, 18))
        self.prog_bar.set(0)

    def _montar_aba_lancamentos(self, parent):
        parent.configure(fg_color="transparent")

        # ---- Card: definir orçamento ----
        ctk.CTkLabel(parent, text="Orçamento", font=self.ft_secao).pack(
            anchor="w", padx=4, pady=(6, 4))
        orc = ctk.CTkFrame(parent, fg_color=CARD2, corner_radius=12)
        orc.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(orc, text="Orçamento do mês (R$):", font=self.ft_normal).pack(
            side="left", padx=(16, 8), pady=14)
        self.orc_var = tk.StringVar(
            value=f"{self.orcamento_do_mes():.2f}".replace(".", ","))
        orc_entry = ctk.CTkEntry(orc, textvariable=self.orc_var, width=140,
                                 font=self.ft_normal)
        orc_entry.pack(side="left")
        orc_entry.bind("<Return>", lambda e: self.definir_orcamento())
        ctk.CTkButton(orc, text="Salvar", width=110, font=self.ft_bold,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.definir_orcamento).pack(side="left", padx=12)

        # ---- Card: novo gasto ----
        ctk.CTkLabel(parent, text="Novo gasto", font=self.ft_secao).pack(
            anchor="w", padx=4, pady=(0, 4))
        form = ctk.CTkFrame(parent, fg_color=CARD2, corner_radius=12)
        form.pack(fill="x", pady=(0, 14))
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=2)

        def rotulo(texto, r, c):
            ctk.CTkLabel(form, text=texto, text_color=SUB,
                         font=self.ft_rotulo).grid(row=r, column=c, sticky="w",
                                                   padx=14, pady=(12, 2))

        rotulo("DESCRIÇÃO", 0, 0)
        self.desc_var = tk.StringVar()
        ctk.CTkEntry(form, textvariable=self.desc_var, font=self.ft_normal).grid(
            row=1, column=0, sticky="we", padx=14, pady=(0, 8))

        rotulo("VALOR (R$)", 0, 1)
        self.valor_var = tk.StringVar()
        valor_entry = ctk.CTkEntry(form, textvariable=self.valor_var,
                                   font=self.ft_normal)
        valor_entry.grid(row=1, column=1, sticky="we", padx=14, pady=(0, 8))
        valor_entry.bind("<Return>", lambda e: self.adicionar_gasto())

        rotulo("CATEGORIA", 2, 0)
        self.cat_var = tk.StringVar(value=CATEGORIAS[0])
        ctk.CTkOptionMenu(form, variable=self.cat_var, values=CATEGORIAS,
                          font=self.ft_normal, fg_color=CARD,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO).grid(
            row=3, column=0, sticky="we", padx=14, pady=(0, 12))

        rotulo("CARTÃO / PAGAMENTO", 2, 1)
        self.cartao_var = tk.StringVar(value=CARTOES[0])
        ctk.CTkOptionMenu(form, variable=self.cartao_var, values=CARTOES,
                          font=self.ft_normal, fg_color=CARD,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO).grid(
            row=3, column=1, sticky="we", padx=14, pady=(0, 12))

        rotulo("DATA", 4, 0)
        self.data_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ctk.CTkEntry(form, textvariable=self.data_var, font=self.ft_normal).grid(
            row=5, column=0, sticky="we", padx=14, pady=(0, 14))

        ctk.CTkButton(form, text="➕  Adicionar gasto", font=self.ft_bold,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.adicionar_gasto).grid(
            row=5, column=1, sticky="we", padx=14, pady=(0, 14))

        # ---- Barra de filtros ----
        barra = ctk.CTkFrame(parent, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(barra, text="Categoria:", text_color=SUB,
                     font=self.ft_bold).pack(side="left", padx=(4, 6))
        self.filtro_var = tk.StringVar(value="Todas")
        ctk.CTkOptionMenu(barra, variable=self.filtro_var,
                          values=["Todas"] + CATEGORIAS, width=150,
                          font=self.ft_normal, fg_color=CARD2,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO,
                          command=lambda _v: self._atualizar_lista()).pack(side="left")

        ctk.CTkLabel(barra, text="Cartão:", text_color=SUB,
                     font=self.ft_bold).pack(side="left", padx=(14, 6))
        self.filtro_cartao_var = tk.StringVar(value="Todos")
        ctk.CTkOptionMenu(barra, variable=self.filtro_cartao_var,
                          values=["Todos"] + CARTOES, width=150,
                          font=self.ft_normal, fg_color=CARD2,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO,
                          command=lambda _v: self._atualizar_lista()).pack(side="left")

        ctk.CTkButton(barra, text="🗑  Remover selecionado", font=self.ft_bold,
                      fg_color="transparent", text_color=COR_NEG,
                      hover_color=CARD2, border_width=1,
                      border_color=COR_NEG,
                      command=self.remover_gasto).pack(side="right", padx=4)

        # ---- Tabela ----
        tabela_frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        tabela_frame.pack(fill="both", expand=True)

        colunas = ("data", "descricao", "categoria", "cartao", "valor")
        self.tree = ttk.Treeview(tabela_frame, columns=colunas, show="headings",
                                 selectmode="browse")
        self.tree.heading("data", text="DATA")
        self.tree.heading("descricao", text="DESCRIÇÃO")
        self.tree.heading("categoria", text="CATEGORIA")
        self.tree.heading("cartao", text="CARTÃO")
        self.tree.heading("valor", text="VALOR")
        self.tree.column("data", width=84, anchor="center")
        self.tree.column("descricao", width=250)
        self.tree.column("categoria", width=120, anchor="center")
        self.tree.column("cartao", width=130, anchor="center")
        self.tree.column("valor", width=120, anchor="e")

        scroll = ctk.CTkScrollbar(tabela_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=10)

    def _montar_aba_graficos(self, parent):
        parent.configure(fg_color="transparent")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=3)
        parent.rowconfigure(1, weight=2)

        self.canvas_pizza = self._criar_canvas_grafico(parent, 0, 0)
        self.fig_pizza = self.canvas_pizza.figure
        self.ax_pizza = self.fig_pizza.add_subplot(111)

        self.canvas_barras = self._criar_canvas_grafico(parent, 0, 1)
        self.fig_barras = self.canvas_barras.figure
        self.ax_barras = self.fig_barras.add_subplot(111)

        self.canvas_cartao = self._criar_canvas_grafico(parent, 1, 0, columnspan=2)
        self.fig_cartao = self.canvas_cartao.figure
        self.ax_cartao = self.fig_cartao.add_subplot(111)

    def _criar_canvas_grafico(self, parent, linha, coluna, columnspan=1):
        moldura = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        moldura.grid(row=linha, column=coluna, columnspan=columnspan,
                     sticky="nsew", padx=6, pady=6)
        fig = Figure(figsize=(4.4, 3.4), dpi=100, layout="constrained")
        canvas = FigureCanvasTkAgg(fig, master=moldura)
        canvas.get_tk_widget().configure(highlightthickness=0)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        return canvas

    def _montar_aba_evolucao(self, parent):
        parent.configure(fg_color="transparent")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        self._montar_resumo_evolucao(parent)

        self.canvas_evol = self._criar_canvas_grafico(parent, 1, 0)
        self.fig_evol = self.canvas_evol.figure
        self.ax_evol = self.fig_evol.add_subplot(111)

        self.canvas_comp = self._criar_canvas_grafico(parent, 2, 0)
        self.fig_comp = self.canvas_comp.figure
        self.ax_comp = self.fig_comp.add_subplot(111)

    def _montar_resumo_evolucao(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        wrap.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 6))
        for i in range(4):
            wrap.columnconfigure(i, weight=1, uniform="resumo")

        self.resumo_tiles = []
        tiles = [
            ("📊", "GASTO MÉDIO/MÊS", ACCENT),
            ("🔺", "MAIOR MÊS", COR_NEG),
            ("🔻", "MENOR MÊS", COR_POS),
            ("💰", "TOTAL ACUMULADO", COR_GASTO),
        ]
        for col, (icone, titulo, cor) in enumerate(tiles):
            cel = ctk.CTkFrame(wrap, fg_color="transparent")
            cel.grid(row=0, column=col, sticky="nsew", padx=14, pady=14)
            topo = ctk.CTkFrame(cel, fg_color="transparent")
            topo.pack(anchor="w")
            ctk.CTkLabel(topo, text=icone, font=self.ft_bold).pack(side="left")
            ctk.CTkLabel(topo, text=titulo, text_color=SUB,
                         font=self.ft_rotulo).pack(side="left", padx=6)
            valor = ctk.CTkLabel(cel, text="—", text_color=cor,
                                 font=self.ft_valor_pq)
            valor.pack(anchor="w", pady=(2, 0))
            sub = ctk.CTkLabel(cel, text="", text_color=SUB,
                               font=self.ft_pequena)
            sub.pack(anchor="w")
            self.resumo_tiles.append((valor, sub))

    # --------------------------------------------------------------- ações ---
    def _parse_valor(self, texto):
        try:
            return float(texto.strip().replace(".", "").replace(",", "."))
        except ValueError:
            return None

    def definir_orcamento(self):
        valor = self._parse_valor(self.orc_var.get())
        if valor is None or valor < 0:
            self._toast("Informe um orçamento numérico válido.", "erro")
            return
        self.orcamentos[self.mes_atual] = valor
        salvar_dados(self.orcamentos, self.gastos)
        self._atualizar_tudo()
        self._toast(f"Orçamento de {nome_mes(self.mes_atual)} salvo.", "sucesso")

    def adicionar_gasto(self):
        descricao = self.desc_var.get().strip()
        valor = self._parse_valor(self.valor_var.get())
        categoria = self.cat_var.get()
        cartao = self.cartao_var.get()
        data_texto = self.data_var.get().strip()

        if not descricao:
            self._toast("Informe uma descrição.", "erro")
            return
        if valor is None or valor <= 0:
            self._toast("Informe um valor maior que zero.", "erro")
            return

        novo = {
            "data": data_texto or date.today().strftime("%d/%m/%Y"),
            "descricao": descricao,
            "categoria": categoria,
            "cartao": cartao,
            "valor": valor,
        }
        self.gastos.append(novo)
        salvar_dados(self.orcamentos, self.gastos)

        self.desc_var.set("")
        self.valor_var.set("")

        mes_novo = mes_do_gasto(novo) or self.mes_atual
        self.mes_atual = mes_novo
        self._sincronizar_mes()
        self._toast(f"Gasto adicionado ({formatar_moeda(valor)}).", "sucesso")

    def remover_gasto(self):
        selecionado = self.tree.selection()
        if not selecionado:
            self._toast("Selecione um gasto para remover.", "info")
            return
        indice = int(self.tree.item(selecionado[0], "tags")[-1].split("_")[-1])
        gasto = self.gastos[indice]
        if self._confirmar(
            "Remover gasto",
            f"Remover '{gasto['descricao']}' ({formatar_moeda(gasto['valor'])})?",
        ):
            del self.gastos[indice]
            salvar_dados(self.orcamentos, self.gastos)
            self._atualizar_tudo()
            self._toast("Gasto removido.", "sucesso")

    def _copiar_contas_fixas(self):
        origens = [m for m in self.meses_disponiveis() if m != self.mes_atual]
        if not origens:
            self._toast("Não há outro mês com dados para copiar.", "info")
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Copiar contas fixas")
        dlg.geometry("440x230")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.after(50, dlg.grab_set)

        ctk.CTkLabel(dlg, text="📋  Copiar contas fixas",
                     font=self.ft_secao).pack(anchor="w", padx=20, pady=(20, 2))
        ctk.CTkLabel(
            dlg, text=("Copia " + ", ".join(CONTAS_FIXAS).lower()
                       + f"\npara {nome_mes(self.mes_atual)} "
                       "(sem duplicar o que já existe)."),
            font=self.ft_pequena, text_color=SUB, justify="left",
            wraplength=390).pack(anchor="w", padx=20, pady=(0, 12))

        linha = ctk.CTkFrame(dlg, fg_color="transparent")
        linha.pack(fill="x", padx=20)
        ctk.CTkLabel(linha, text="Copiar do mês:", font=self.ft_bold).pack(
            side="left", padx=(0, 8))
        nomes = {nome_mes(m): m for m in origens}
        var = tk.StringVar(value=list(nomes.keys())[0])
        ctk.CTkOptionMenu(linha, variable=var, values=list(nomes.keys()),
                          font=self.ft_normal, fg_color=CARD2,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO, width=200).pack(side="left")

        botoes = ctk.CTkFrame(dlg, fg_color="transparent")
        botoes.pack(side="bottom", fill="x", padx=20, pady=18)

        def confirmar():
            origem = nomes[var.get()]
            copiadas = self._executar_copia_contas(origem, self.mes_atual)
            dlg.destroy()
            if copiadas:
                self._toast(
                    f"{copiadas} conta(s) copiada(s) de {nome_mes(origem)}.",
                    "sucesso")
            else:
                self._toast("Nenhuma conta nova para copiar.", "info")

        ctk.CTkButton(botoes, text="Copiar", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, font=self.ft_bold, width=110,
                      command=confirmar).pack(side="right", padx=(8, 0))
        ctk.CTkButton(botoes, text="Cancelar", fg_color="transparent",
                      border_width=1, border_color=BORDA,
                      text_color=TEXTO, hover_color=CARD2,
                      font=self.ft_bold, width=110,
                      command=dlg.destroy).pack(side="right")

    def _executar_copia_contas(self, origem, destino):
        existentes = {
            (g["descricao"].strip().lower(), g["categoria"])
            for g in self.gastos if mes_do_gasto(g) == destino
        }
        ano, mes = (int(x) for x in destino.split("-"))
        ultimo_dia = calendar.monthrange(ano, mes)[1]

        copiadas = 0
        for gasto in list(self.gastos):
            if mes_do_gasto(gasto) != origem:
                continue
            if gasto["categoria"] not in CONTAS_FIXAS:
                continue
            chave = (gasto["descricao"].strip().lower(), gasto["categoria"])
            if chave in existentes:
                continue
            dia = min(dia_de_data(gasto.get("data", "")), ultimo_dia)
            self.gastos.append({
                "data": f"{dia:02d}/{mes:02d}/{ano:04d}",
                "descricao": gasto["descricao"],
                "categoria": gasto["categoria"],
                "cartao": gasto.get("cartao", CARTAO_PADRAO),
                "valor": gasto["valor"],
            })
            existentes.add(chave)
            copiadas += 1

        if copiadas:
            salvar_dados(self.orcamentos, self.gastos)
            self._sincronizar_mes()
        return copiadas

    # ---------------------------------------------------------- atualização ---
    def _atualizar_tudo(self):
        self._atualizar_lista()
        self._atualizar_progresso()
        self._atualizar_graficos()
        self._atualizar_evolucao()

    def _atualizar_lista(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtro = self.filtro_var.get()
        filtro_cartao = self.filtro_cartao_var.get()
        posicao = 0
        for indice, gasto in enumerate(self.gastos):
            if mes_do_gasto(gasto) != self.mes_atual:
                continue
            cartao = gasto.get("cartao", CARTAO_PADRAO)
            if filtro != "Todas" and gasto["categoria"] != filtro:
                continue
            if filtro_cartao != "Todos" and cartao != filtro_cartao:
                continue
            zebra = "par" if posicao % 2 == 0 else "impar"
            self.tree.insert(
                "", "end",
                values=(
                    gasto["data"],
                    gasto["descricao"],
                    gasto["categoria"],
                    cartao,
                    formatar_moeda(gasto["valor"]),
                ),
                tags=(zebra, f"idx_{indice}"),
            )
            posicao += 1

        orcamento = self.orcamento_do_mes()
        total_geral = sum(g["valor"] for g in self.gastos_do_mes())
        restante = orcamento - total_geral

        self.card_orc_valor.configure(text=formatar_moeda(orcamento))
        self.card_gasto_valor.configure(text=formatar_moeda(total_geral))
        self.card_rest_valor.configure(text=formatar_moeda(restante))
        if restante >= 0:
            self.card_rest_valor.configure(text_color=COR_POS)
            self.card_rest_icone.configure(text="🟢")
            self.card_rest_titulo.configure(text="RESTANTE")
        else:
            self.card_rest_valor.configure(text_color=COR_NEG)
            self.card_rest_icone.configure(text="🔴")
            self.card_rest_titulo.configure(text="ESTOUROU")

    def _atualizar_progresso(self):
        orcamento = self.orcamento_do_mes()
        total_gasto = sum(g["valor"] for g in self.gastos_do_mes())
        pct = (total_gasto / orcamento * 100) if orcamento > 0 else 0
        self.prog_bar.set(min(pct, 100) / 100)
        self.prog_bar.configure(progress_color=_cor_progresso(pct))
        self.prog_label.configure(text=f"{pct:.0f}% usado",
                                  text_color=_cor_progresso(pct))

    def _preparar_ax(self, fig, ax):
        """Aplica cores do tema ao fundo da figura e do eixo."""
        card = _cor(CARD)
        fig.set_facecolor(card)
        ax.set_facecolor(card)

    def _atualizar_graficos(self):
        gastos_mes = self.gastos_do_mes()
        orcamento = self.orcamento_do_mes()
        totais = totais_por_categoria(gastos_mes)
        texto = _cor(TEXTO)
        sub = _cor(SUB)
        grid = _cor(GRID)
        card = _cor(CARD)

        # ---- rosca (donut): gastos por categoria ----
        self._preparar_ax(self.fig_pizza, self.ax_pizza)
        self.ax_pizza.clear()
        if totais:
            labels = list(totais.keys())
            valores = list(totais.values())
            cores = [CATEGORIA_CORES.get(l, "#94A3B8") for l in labels]
            total = sum(valores)
            wedges, _t, _a = self.ax_pizza.pie(
                valores, colors=cores, startangle=90, counterclock=False,
                autopct=lambda p: f"{p:.0f}%" if p >= 7 else "",
                pctdistance=0.78,
                wedgeprops={"width": 0.42, "edgecolor": card, "linewidth": 2},
                textprops={"fontsize": 8, "color": "white", "fontweight": "bold"},
            )
            self.ax_pizza.text(0, 0, f"Total\n{formatar_moeda(total)}",
                               ha="center", va="center", fontsize=9.5,
                               fontweight="bold", color=texto)
            self.ax_pizza.legend(wedges, labels, loc="upper center",
                                 bbox_to_anchor=(0.5, 0.02), ncol=3, frameon=False,
                                 fontsize=7.5, handlelength=1, columnspacing=1,
                                 labelcolor=texto)
        else:
            self.ax_pizza.text(0.5, 0.5, "Sem gastos ainda", ha="center",
                               va="center", color=sub, fontsize=10)
            self.ax_pizza.axis("off")
        self.ax_pizza.set_title("Gastos por categoria", fontsize=12,
                                fontweight="bold", color=texto, pad=10)
        self.canvas_pizza.draw()

        # ---- barras: orçamento x gasto x restante ----
        self._preparar_ax(self.fig_barras, self.ax_barras)
        total_gasto = sum(g["valor"] for g in gastos_mes)
        restante = orcamento - total_gasto
        self.ax_barras.clear()
        itens = ["Orçamento", "Gasto", "Restante"]
        valores = [orcamento, total_gasto, restante]
        cores = [COR_ORC, COR_GASTO, COR_POS if restante >= 0 else COR_NEG]
        barras = self.ax_barras.bar(itens, valores, color=cores, width=0.62,
                                    zorder=3)
        self.ax_barras.set_title("Orçamento x Gasto x Restante", fontsize=12,
                                 fontweight="bold", color=texto, pad=10)
        for lado in ("top", "right", "left"):
            self.ax_barras.spines[lado].set_visible(False)
        self.ax_barras.spines["bottom"].set_color(_cor(BORDA))
        self.ax_barras.tick_params(left=False, labelleft=False, bottom=False)
        self.ax_barras.tick_params(axis="x", labelsize=9.5, colors=texto)
        self.ax_barras.yaxis.grid(True, color=grid, zorder=0)
        maximo = max(valores + [1])
        minimo = min(valores + [0])
        self.ax_barras.set_ylim(min(minimo * 1.2, 0), maximo + maximo * 0.20)
        for barra, valor in zip(barras, valores):
            self.ax_barras.annotate(
                formatar_moeda(valor),
                xy=(barra.get_x() + barra.get_width() / 2, valor),
                xytext=(0, 4 if valor >= 0 else -4), textcoords="offset points",
                ha="center", va="bottom" if valor >= 0 else "top",
                fontsize=8.5, fontweight="bold", color=texto)
        self.canvas_barras.draw()

        # ---- barras horizontais: gastos por cartão ----
        self._preparar_ax(self.fig_cartao, self.ax_cartao)
        self.ax_cartao.clear()
        cartoes = totais_por_cartao(gastos_mes)
        self.ax_cartao.set_title("Gastos por cartão / forma de pagamento",
                                 fontsize=12, fontweight="bold", color=texto,
                                 pad=10)
        for lado in ("top", "right", "bottom"):
            self.ax_cartao.spines[lado].set_visible(False)
        self.ax_cartao.spines["left"].set_color(_cor(BORDA))
        self.ax_cartao.tick_params(bottom=False, labelbottom=False, left=False)
        self.ax_cartao.tick_params(axis="y", labelsize=9.5, colors=texto)
        self.ax_cartao.xaxis.grid(True, color=grid, zorder=0)
        if cartoes:
            ordenado = sorted(cartoes.items(), key=lambda x: x[1])
            nomes = [n for n, _ in ordenado]
            vals = [v for _, v in ordenado]
            cores = [CARTAO_CORES.get(n, "#94A3B8") for n in nomes]
            barrash = self.ax_cartao.barh(nomes, vals, color=cores, zorder=3,
                                          height=0.6)
            self.ax_cartao.set_xlim(0, max(vals) * 1.20)
            for barra, valor in zip(barrash, vals):
                self.ax_cartao.annotate(
                    formatar_moeda(valor),
                    xy=(valor, barra.get_y() + barra.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points", ha="left",
                    va="center", fontsize=8.5, fontweight="bold", color=texto)
        else:
            self.ax_cartao.text(0.5, 0.5, "Sem gastos ainda", ha="center",
                                va="center", color=sub, fontsize=10)
            self.ax_cartao.axis("off")
        self.canvas_cartao.draw()

    def _atualizar_resumo(self, meses, por_mes):
        com_gasto = [(m, sum(por_mes[m].values())) for m in meses
                     if sum(por_mes[m].values()) > 0]
        if not com_gasto:
            for valor, sub in self.resumo_tiles:
                valor.configure(text="—")
                sub.configure(text="")
            return
        total = sum(v for _, v in com_gasto)
        media = total / len(com_gasto)
        maior_m, maior_v = max(com_gasto, key=lambda x: x[1])
        menor_m, menor_v = min(com_gasto, key=lambda x: x[1])
        dados = [
            (formatar_moeda(media), f"em {len(com_gasto)} mês(es)"),
            (formatar_moeda(maior_v), nome_mes(maior_m)),
            (formatar_moeda(menor_v), nome_mes(menor_m)),
            (formatar_moeda(total), "somando todos os meses"),
        ]
        for (valor, sub), (texto, subtexto) in zip(self.resumo_tiles, dados):
            valor.configure(text=texto)
            sub.configure(text=subtexto)

    def _atualizar_evolucao(self):
        meses = self._meses_com_dados_asc()
        labels = [label_mes_curto(m) for m in meses]
        por_mes = {
            m: totais_por_categoria([g for g in self.gastos if mes_do_gasto(g) == m])
            for m in meses
        }
        self._atualizar_resumo(meses, por_mes)
        texto = _cor(TEXTO)
        sub = _cor(SUB)
        grid = _cor(GRID)

        # ---- gráfico 1: gasto x orçamento por mês ----
        self._preparar_ax(self.fig_evol, self.ax_evol)
        self.ax_evol.clear()
        self.ax_evol.set_title("Evolução: gasto x orçamento por mês",
                               fontsize=12, fontweight="bold", color=texto, pad=10)
        for lado in ("top", "right", "left"):
            self.ax_evol.spines[lado].set_visible(False)
        self.ax_evol.spines["bottom"].set_color(_cor(BORDA))
        self.ax_evol.tick_params(left=False, labelleft=False, bottom=False)
        self.ax_evol.tick_params(axis="x", labelsize=9, colors=texto)
        self.ax_evol.yaxis.grid(True, color=grid, zorder=0)
        if meses:
            gasto_mes = [sum(por_mes[m].values()) for m in meses]
            orc_mes = [self.orcamentos.get(m, 0.0) for m in meses]
            x = list(range(len(meses)))
            self.ax_evol.bar(x, gasto_mes, color=COR_GASTO, width=0.6, zorder=3,
                             label="Gasto")
            self.ax_evol.plot(x, orc_mes, color=ACCENT, marker="o", linewidth=2.2,
                              markersize=6, zorder=4, label="Orçamento")
            self.ax_evol.set_xticks(x)
            self.ax_evol.set_xticklabels(labels)
            topo = max(gasto_mes + orc_mes + [1])
            self.ax_evol.set_ylim(0, topo * 1.22)
            for xi, valor in zip(x, gasto_mes):
                self.ax_evol.annotate(
                    formatar_moeda(valor), xy=(xi, valor), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, fontweight="bold", color=texto)
            self.ax_evol.legend(loc="upper left", frameon=False, fontsize=9,
                                ncol=2, labelcolor=texto)
        else:
            self.ax_evol.text(0.5, 0.5, "Sem dados para comparar", ha="center",
                              va="center", color=sub, fontsize=10)
            self.ax_evol.axis("off")
        self.canvas_evol.draw()

        # ---- gráfico 2: categorias empilhadas por mês ----
        self._preparar_ax(self.fig_comp, self.ax_comp)
        self.ax_comp.clear()
        self.ax_comp.set_title("Gastos por categoria ao longo dos meses",
                               fontsize=12, fontweight="bold", color=texto, pad=10)
        for lado in ("top", "right", "left"):
            self.ax_comp.spines[lado].set_visible(False)
        self.ax_comp.spines["bottom"].set_color(_cor(BORDA))
        self.ax_comp.tick_params(left=False, labelleft=False, bottom=False)
        self.ax_comp.tick_params(axis="x", labelsize=9, colors=texto)
        self.ax_comp.yaxis.grid(True, color=grid, zorder=0)
        presentes = [c for c in CATEGORIAS
                     if any(por_mes[m].get(c, 0) > 0 for m in meses)]
        extras = sorted({c for m in meses for c in por_mes[m]
                         if c not in CATEGORIAS})
        categorias = presentes + extras
        if meses and categorias:
            x = list(range(len(meses)))
            base = [0.0] * len(meses)
            for cat in categorias:
                vals = [por_mes[m].get(cat, 0.0) for m in meses]
                self.ax_comp.bar(x, vals, bottom=base, width=0.6,
                                 color=CATEGORIA_CORES.get(cat, "#94A3B8"),
                                 label=cat, zorder=3)
                base = [b + v for b, v in zip(base, vals)]
            self.ax_comp.set_xticks(x)
            self.ax_comp.set_xticklabels(labels)
            self.ax_comp.set_ylim(0, max(base + [1]) * 1.10)
            ncol = min(len(categorias), 5)
            self.ax_comp.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16),
                                ncol=ncol, frameon=False, fontsize=7.5,
                                handlelength=1, columnspacing=1, labelcolor=texto)
        else:
            self.ax_comp.text(0.5, 0.5, "Sem dados para comparar", ha="center",
                              va="center", color=sub, fontsize=10)
            self.ax_comp.axis("off")
        self.canvas_comp.draw()


def main():
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    CalculadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
