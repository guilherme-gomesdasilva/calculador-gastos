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

import bisect
import calendar
import itertools
import json
import os
import sys
import tkinter as tk
import unicodedata
import uuid
from datetime import date
from functools import lru_cache
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter as ctk
import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.colors import to_rgb
from matplotlib.container import BarContainer
from matplotlib.image import BboxImage
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.legend_handler import (HandlerBase, HandlerPatch,
                                       update_from_first_child)
from matplotlib.patches import Rectangle
from matplotlib.transforms import Bbox, TransformedBbox
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # executável (PyInstaller): a pasta do programa pode ser temporária ou sem
    # permissão de escrita, então dados e logos ficam na pasta do usuário
    # Windows: %APPDATA%; Linux: ~/.local/share (padrão XDG)
    PASTA_DADOS = os.path.join(
        os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
        or os.path.join(os.path.expanduser("~"), ".local", "share"), "CalculadorGastos")
    LOGOS_DIR = os.path.join(PASTA_DADOS, "logos")  # nubank.png, itau.png...
    os.makedirs(LOGOS_DIR, exist_ok=True)
else:
    # rodando pelo código: tudo na pasta do projeto
    PASTA_DADOS = BASE_DIR
    LOGOS_DIR = os.path.join(BASE_DIR, "assets", "logos")
DATA_FILE = os.path.join(PASTA_DADOS, "gastos.json")
ICONE = os.path.join(BASE_DIR, "assets", "icone.png")  # vai junto no executável

def outros_por_ultimo(opcoes):
    """Deixa "Outro"/"Outros"/"Outra" no fim de uma lista (ou dict) de opções,
    mesmo que novas opções sejam escritas depois dele; o resto mantém a ordem."""
    def e_outro(nome):
        return nome.split()[0].lower() in {"outro", "outros", "outra"}
    if isinstance(opcoes, dict):
        return dict(sorted(opcoes.items(), key=lambda item: e_outro(item[0])))
    return sorted(opcoes, key=e_outro)


CATEGORIAS = outros_por_ultimo([
    "Alimentação",
    "Aluguel",
    "Luz",
    "Água",
    "Gás",
    "Internet/Telefone",
    "Fatura de Cartão",
    "Parcelamento de Compras",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Outros",
    "Financiamento/Empréstimo",
    "Reserva de Emergência",
    "Investimentos",
])

# Cor de cada categoria (usada nos gráficos) - vivas, funcionam nos dois temas
CATEGORIA_CORES = {
    "Alimentação": "#6366F1",
    "Aluguel": "#8B5CF6",
    "Luz": "#F59E0B",
    "Água": "#06B6D4",
    "Gás": "#EF4444",
    "Internet/Telefone": "#0EA5E9",
    "Fatura de Cartão": "#4338CA",
    "Parcelamento de Compras": "#F9A8D4",
    "Transporte": "#14B8A6",
    "Saúde": "#EC4899",
    "Educação": "#F97316",
    "Lazer": "#22C55E",
    "Outros": "#94A3B8",
    "Financiamento/Empréstimo": "#92400E",
    "Reserva de Emergência": "#0E7490",
    "Investimentos": "#059669",
}

# Aba "Reserva e Investimentos": guardar = gasto na categoria; tirar = renda na fonte
# poupança -> (categoria do aporte, fonte de renda do resgate)
POUPANCAS = {
    "reserva": ("Reserva de Emergência", "Resgate da Reserva"),
    "investimentos": ("Investimentos", "Resgate de Investimentos"),
}

# Compras parceladas: cada parcela é um gasto no seu mês (ver distribuir_parcelas)
CATEGORIA_PARCELAMENTO = "Parcelamento de Compras"
OUTRA_QUANTIDADE = "Outra…"
# categoria parcelada -> (quantidades rápidas no menu, máximo aceito em "Outra…")
CATEGORIAS_PARCELADAS = {
    CATEGORIA_PARCELAMENTO: ([f"{n}x" for n in (2, 3, 4, 5, 6, 10, 12)], 48),
    "Financiamento/Empréstimo": ([f"{n}x" for n in (12, 24, 36, 48)], 420),
}


def quantidade_parcelas(texto, maximo):
    """'12x' ou '12' -> 12, se estiver entre 2 e `maximo`; senão None."""
    texto = (texto or "").strip().lower().removesuffix("x").strip()
    if not texto.isdigit():
        return None
    n = int(texto)
    return n if 2 <= n <= maximo else None

# Categorias consideradas "contas fixas" (recorrentes todo mês)
CONTAS_FIXAS = [
    "Aluguel",
    "Luz",
    "Água",
    "Gás",
    "Internet/Telefone",
    "Educação",
    "Financiamento/Empréstimo",
]

# Formas de pagamento / cartões
CARTOES = outros_por_ultimo([
    "Dinheiro",
    "Pix",
    "Débito",
    "Cartão de Crédito",
    "Outro",
])
CARTAO_PADRAO = "Outro"

# Instituições das faturas de cartão, com a cor característica de cada uma
CATEGORIA_FATURA = "Fatura de Cartão"
INSTITUICOES = outros_por_ultimo({
    "Nubank": "#820AD1",
    "Itaú": "#EC7000",
    "Bradesco": "#CC092F",
    "Santander": "#EC0000",
    "Banco do Brasil": "#F9DD16",
    "Caixa": "#005CA9",
    "Inter": "#FF7A00",
    "Mercado Pago": "#00B1EA",
    "PicPay": "#21C25E",
    "Outra": "#94A3B8",
})

#Formas de transporte (usadas em gastos de transporte, para gráficos e filtros)
CATEGORIA_TRANSPORTE = "Transporte"
INSTITUICOES_TRANSPORTE = outros_por_ultimo({
    "Ônibus": "#84CC16",
    "Metrô": "#D946EF",
    "Trem": "#C2855A",
    "Táxi": "#818CF8",
    "Uber / 99": "#78716C",
    "Carro Moto/ Combustível": "#FB7185",
    "Outro": "#E879F9",
})

# Categorias que abrem um 2º seletor no formulário:
# categoria -> (prefixo no rótulo/gráficos, título do seletor, opções com cor)
SUBCATEGORIAS = {
    CATEGORIA_FATURA: ("Fatura ", "INSTITUIÇÃO", INSTITUICOES),
    CATEGORIA_TRANSPORTE: ("Transporte - ", "TIPO DE TRANSPORTE",
                           INSTITUICOES_TRANSPORTE),
}

# Formas de renda extra (entradas além do orçamento do mês)
FONTES_RENDA = outros_por_ultimo([
    "Freelance",
    "Vendas",
    "Investimentos",
    "Reembolso",
    "Presente",
    "13º / Férias",
    "Delivery / Apps",
    "Outros",
    "Resgate da Reserva",
    "Resgate de Investimentos",
])
FONTE_PADRAO = "Outros"

# Apps da fonte "Delivery / Apps", com a cor da marca (logos em assets/logos)
FONTE_DELIVERY = "Delivery / Apps"
APPS_DELIVERY = {
    "iFood": "#EA1D2C",
    "99": "#FFD200",
    "Uber": "#000000",
    "Mercado Livre": "#FFE600",
    "Shopee": "#EE4D2D",
    "Keeta": "#FFD100",
    "Rappi": "#FF441F",
    "Lalamove": "#F16622",
    "Loggi": "#00B4FC",
    "Amazon Flex": "#FF9900",
    "Borzo": "#94A3B8",
    "inDrive": "#9CE424",
    "Zé Delivery": "#FFE000",
    "aiqfome": "#7B1FA2",
    "Magalu": "#0C84FC",
}
COLUNAS_ENTRADAS = 6  # cards por linha no topo (salário, rendas e apps com valor)

# Emoji de cada forma de pagamento (gráfico de formas de pagamento)
CARTAO_EMOJI = {
    "Dinheiro": "💵",
    "Pix": "💠",
    "Débito": "🏧",
    "Cartão de Crédito": "💳",
    "Outro": "🧾",
}
# O matplotlib não desenha emoji colorido: ele vira imagem com a 1ª fonte que existir
FONTES_EMOJI = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/google-noto-color-emoji/NotoColorEmoji.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
]

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
COR_RENDA = "#10B981"     # verde-esmeralda (renda extra)
COR_RENDA_HOVER = "#0E9F6E"
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
COR_RESTANTE = "#166534"  # verde mais escuro que os demais verdes dos gráficos


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
    """Lê os orçamentos (por mês), os gastos e as rendas extras do JSON.

    Aceita vários formatos, garantindo compatibilidade:
    - novo: {"orcamentos": {...}, "gastos": [...], "rendas": [...]}
    - anterior: {"orcamento": valor_único, "gastos": [...]}
    - antigo: apenas uma lista de gastos.
    Retorna (orcamentos: dict, gastos: list, rendas: list).
    """
    if not os.path.exists(DATA_FILE):
        return {}, [], []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, [], []

    if isinstance(dados, list):  # formato antigo (lista pura)
        return {}, dados, []

    gastos = dados.get("gastos", [])
    rendas = dados.get("rendas", [])
    if "orcamentos" in dados:  # formato novo (por mês)
        orcamentos = {k: float(v) for k, v in dados["orcamentos"].items()}
        return orcamentos, gastos, rendas

    # formato anterior (orçamento único) -> aplica o valor a cada mês existente
    orcamentos = {}
    valor = float(dados.get("orcamento", 0.0))
    if valor > 0:
        for gasto in gastos:
            chave = mes_do_gasto(gasto) or mes_atual_chave()
            orcamentos[chave] = valor
    return orcamentos, gastos, rendas


def salvar_dados(orcamentos, gastos, rendas):
    """Grava orçamentos por mês, gastos e rendas extras no arquivo JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"orcamentos": orcamentos, "gastos": gastos, "rendas": rendas},
            f,
            ensure_ascii=False,
            indent=2,
        )


MAX_CENTAVOS = 99_999_999_999  # R$ 999.999.999,99: limite dos campos de dinheiro


def formatar_numero(valor):
    """Número no formato brasileiro, sem o 'R$': 1234.5 -> '1.234,50'."""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def centavos_do_texto(texto):
    """Só os dígitos 0-9 viram centavos: '1.234,56' -> 123456, 'abc' -> 0."""
    digitos = "".join(ch for ch in texto if ch in "0123456789")
    return min(int(digitos or 0), MAX_CENTAVOS)


def formatar_moeda(valor):
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    texto = formatar_numero(valor)
    return f"R$ {texto}"


def rotulo_categoria(gasto):
    """Categoria para exibição: 'Fatura Nubank', 'Transporte - Ônibus'..."""
    sub = SUBCATEGORIAS.get(gasto["categoria"])
    inst = gasto.get("instituicao")
    if sub and inst:
        return sub[0] + inst
    return gasto["categoria"]


def instituicao_do_rotulo(rotulo):
    """'Fatura Nubank' -> 'Nubank'; qualquer outro rótulo -> None."""
    inst = rotulo.removeprefix("Fatura ")
    return inst if inst != rotulo and inst in INSTITUICOES else None


def cor_categoria(rotulo):
    """Cor de um rótulo: subcategorias (banco, transporte) usam a própria cor."""
    for prefixo, _titulo, opcoes in SUBCATEGORIAS.values():
        nome = rotulo.removeprefix(prefixo)
        if nome != rotulo and nome in opcoes:
            return opcoes[nome]
    return CATEGORIA_CORES.get(rotulo, "#94A3B8")


def arquivo_logo(instituicao, extensao=".png"):
    """'Banco do Brasil' -> '<LOGOS_DIR>/banco-do-brasil.png'."""
    nome = unicodedata.normalize("NFKD", instituicao).encode("ascii", "ignore")
    return os.path.join(LOGOS_DIR, nome.decode().lower().replace(" ", "-") + extensao)


@lru_cache(maxsize=None)
def imagem_logo(nome):
    """Logo (banco, app) como imagem PIL RGBA, ou None se não houver arquivo válido."""
    for extensao in (".png", ".jpg", ".jpeg", ".webp"):
        try:
            with Image.open(arquivo_logo(nome, extensao)) as img:
                return img.convert("RGBA")
        except (OSError, ValueError, SyntaxError):  # PIL usa SyntaxError p/ inválido
            continue
    return None


def logo_ctk(nome, altura):
    """Logo para a interface, sem fundo: uma versão legível para cada tema, ou None."""
    img = imagem_logo(nome)
    if img is None:
        return None
    arr = np.asarray(img)
    claro, escuro = (Image.fromarray(logo_sobre_cor(arr, cor)) for cor in CARD)
    return ctk.CTkImage(light_image=claro, dark_image=escuro,
                        size=(round(img.width * altura / img.height), altura))


def mesma_renda(renda, mes, fonte, app=None):
    """A renda é do mês e da fonte (e do app, no delivery) indicados?"""
    return (mes_do_gasto(renda) == mes and renda.get("app") == app
            and renda.get("fonte", FONTE_PADRAO) == fonte)


def totais_renda(rendas):
    """({app: total} de cada app de delivery, total das demais rendas extras)."""
    por_app = dict.fromkeys(APPS_DELIVERY, 0.0)
    outras = 0.0
    for renda in rendas:
        if renda.get("fonte") == FONTE_DELIVERY and renda.get("app") in por_app:
            por_app[renda["app"]] += renda["valor"]
        else:
            outras += renda["valor"]
    return por_app, outras


class _HandlerLogo(HandlerBase):
    """Desenha o logo (mantendo a proporção) no lugar do quadradinho da legenda."""

    def __init__(self, logo):
        super().__init__()
        self.logo = logo

    def create_artists(self, legend, orig_handle, xdescent, ydescent,
                       width, height, fontsize, trans):
        alt, larg = self.logo.shape[:2]
        escala = min(width / larg, height / alt)
        w, h = larg * escala, alt * escala
        x, y = -xdescent + (width - w) / 2, -ydescent + (height - h) / 2
        imagem = BboxImage(TransformedBbox(Bbox.from_bounds(x, y, w, h), trans))
        imagem.set_data(self.logo)
        return [imagem]


def _quadrado_legenda(legend, orig_handle, xdescent, ydescent, width, height,
                      fontsize):
    """Quadradinho de cor do tamanho da fonte, centrado no espaço (largo) do logo."""
    return Rectangle((-xdescent + (width - fontsize) / 2,
                      -ydescent + (height - fontsize) / 2), fontsize, fontsize)


@lru_cache(maxsize=None)
def imagem_emoji(emoji):
    """Emoji colorido como array RGBA, ou None se não houver fonte de emoji."""
    for caminho in FONTES_EMOJI:
        for tamanho in (109, 160):  # fontes de emoji em bitmap só aceitam certos tamanhos
            try:
                fonte = ImageFont.truetype(caminho, tamanho)
                img = Image.new("RGBA", (tamanho * 2, tamanho * 2), (0, 0, 0, 0))
                ImageDraw.Draw(img).text((0, 0), emoji, font=fonte, embedded_color=True)
            except OSError:
                continue
            caixa = img.getbbox()
            if caixa:
                return np.asarray(img.crop(caixa))
    return None


def logo_do_rotulo(rotulo):
    """Logo do banco de um rótulo 'Fatura <banco>', ou None."""
    img = imagem_logo(inst) if (inst := instituicao_do_rotulo(rotulo)) else None
    return None if img is None else np.asarray(img)


def _lab(rgb):
    """Cores RGB (N×3, 0-1) no espaço Lab, onde distância ≈ diferença percebida."""
    rgb = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = rgb @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722],
                          [0.0193, 0.1192, 0.9505]]).T / [0.95047, 1.0, 1.08883]
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], axis=1)


def _luminancia(rgb):
    """Luminância relativa (WCAG) de cores RGB N×3 em 0-1."""
    lin = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    return lin @ [0.2126, 0.7152, 0.0722]


def logo_sobre_cor(logo, cor):
    """Logo legível sobre `cor` (sem mexer nele se já estiver legível).

    1. Fundo escuro e logo sem fundo próprio: as partes escuras viram brancas e
       as coloridas ficam (ex.: texto do inDrive/Amazon no tema escuro).
    2. Se a maior parte do logo ainda tem a mesma cor do fundo (ex.: Inter
       laranja na fatia laranja), ele todo vira silhueta branca ou preta.
    """
    visivel = logo[..., 3] > 127
    if not visivel.any():
        return logo
    fundo = np.array([to_rgb(cor)])
    luminancia = float(_luminancia(fundo)[0])
    resultado = logo
    # ícone com fundo próprio (quase todo opaco, ex.: 99, Keeta) já tem contraste
    if luminancia < 0.2 and visivel.mean() < 0.75:
        lum = _luminancia(logo[..., :3].reshape(-1, 3) / 255).reshape(visivel.shape)
        contraste = (np.maximum(lum, luminancia) + 0.05) / (np.minimum(lum, luminancia) + 0.05)
        apagadas = visivel & (contraste < 1.5)
        if apagadas.any():
            resultado = np.array(logo, dtype=np.uint8)
            resultado[apagadas, :3] = 255
    opacos = resultado[visivel][:, :3] / 255
    if (np.linalg.norm(_lab(opacos) - _lab(fundo), axis=1) < 25).mean() < 0.5:
        return resultado
    # branco ou preto: o que tiver mais contraste com o fundo
    branco = 1.05 / (luminancia + 0.05) >= (luminancia + 0.05) / 0.05
    silhueta = np.array(resultado, dtype=np.uint8)
    silhueta[..., :3] = 255 if branco else 0
    return silhueta


@lru_cache(maxsize=None)
def logo_da_fatia(rotulo):
    """Logo do banco já ajustado para ficar sobre a cor da sua fatia, ou None."""
    logo = logo_do_rotulo(rotulo)
    return None if logo is None else logo_sobre_cor(logo, cor_categoria(rotulo))


def imagens_nas_fatias(ax, wedges, imagens, largura=0.42, altura_pts=14, minimo_pts=6):
    """Põe cada imagem (logo, emoji) dentro da sua fatia, encolhendo para caber.

    Chame depois do título e da legenda: o espaço de cada fatia é medido no
    tamanho final da rosca na tela. Fatia fina demais (imagem com menos de
    `minimo_pts` de altura) fica sem imagem. Retorna os índices com imagem.
    """
    fig = ax.figure
    fig.draw_without_rendering()  # aplica o layout para medir a rosca de verdade
    x0 = ax.transData.transform((0, 0))[0]
    pts_por_unidade = (ax.transData.transform((1, 0))[0] - x0) * 72 / fig.dpi
    folga = 1  # respiro entre a imagem e a borda da fatia
    raio = 1 - largura / 2
    com_imagem = []
    for i, (wedge, img) in enumerate(zip(wedges, imagens)):
        if img is None:
            continue
        abertura = np.deg2rad(wedge.theta2 - wedge.theta1)
        angulo = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
        # espaço da fatia no anel: ao longo do arco (corda) e na espessura do anel
        corda = 2 * raio * np.sin(min(abertura, np.pi) / 2)
        no_arco = max(corda * pts_por_unidade * 0.95 - folga, 0)
        no_anel = max(largura * pts_por_unidade * 0.9 - folga, 0)
        # a imagem não gira: quanto dela cai em cada direção depende do ângulo
        alt, larg = img.shape[:2]
        seno, cosseno = abs(np.sin(angulo)), abs(np.cos(angulo))
        zoom = min(altura_pts / alt, 2.6 * altura_pts / larg,
                   no_arco / (larg * seno + alt * cosseno),
                   no_anel / (larg * cosseno + alt * seno))
        if zoom * alt < minimo_pts:
            continue
        caixa = AnnotationBbox(
            OffsetImage(img, zoom=zoom), (raio * np.cos(angulo), raio * np.sin(angulo)),
            frameon=False, zorder=5)
        caixa.set_in_layout(False)  # não mexer no layout já medido
        ax.add_artist(caixa)
        com_imagem.append(i)
    return com_imagem


def legenda_com_logos(ax, handles, labels, imagem_de=logo_do_rotulo, altura=1.6,
                      fundo=None, **opcoes):
    """Legenda que troca o quadradinho de cor por uma imagem (logo, emoji) se houver.

    `fundo`: cor atrás da legenda; logos da mesma cor viram silhueta para aparecer.
    """
    logos = {}
    for handle, rotulo in zip(handles, labels):
        imagem = imagem_de(rotulo)
        if imagem is not None:
            logos[handle] = logo_sobre_cor(imagem, fundo) if fundo else imagem
    if not logos:
        ax.legend(handles, labels, **opcoes)
        return

    # logos horizontais (ex.: "Santander") precisam de espaço largo para ler
    maior_proporcao = max(l.shape[1] / l.shape[0] for l in logos.values())
    opcoes.update(handleheight=altura,
                  handlelength=altura * min(max(maior_proporcao, 1.0), 2.5))
    mapa = {}
    for handle in handles:
        if handle in logos:
            mapa[handle] = _HandlerLogo(logos[handle])
        else:  # sem isso o quadradinho de cor esticaria até a largura do logo
            mapa[handle] = HandlerPatch(
                patch_func=_quadrado_legenda,
                update_func=(update_from_first_child
                             if isinstance(handle, BarContainer) else None))
    ax.legend(handles, labels, handler_map=mapa, **opcoes)


def acumulado_poupancas(gastos, rendas, ate=None):
    """Aportes (gastos) menos resgates (rendas) de cada poupança, mês a mês.

    Retorna (meses, saldo, movimento): `meses` vai do 1º mês com movimento até o
    último (ou até `ate`, se for depois), sem pular meses; `saldo[nome]` é o
    acumulado em cada mês e `movimento[nome]` o que entrou/saiu no mês.
    """
    por_mes = {nome: {} for nome in POUPANCAS}
    for nome, (categoria, fonte) in POUPANCAS.items():
        for item, sinal in [(g, 1) for g in gastos if g["categoria"] == categoria] + \
                           [(r, -1) for r in rendas if r.get("fonte") == fonte]:
            mes = mes_do_gasto(item)
            if mes:
                por_mes[nome][mes] = por_mes[nome].get(mes, 0.0) + sinal * item["valor"]
    com_movimento = sorted({m for d in por_mes.values() for m in d})
    if not com_movimento:
        return [], {n: [] for n in POUPANCAS}, {n: [] for n in POUPANCAS}
    meses, mes = [], com_movimento[0]
    while mes <= max(com_movimento[-1], ate or ""):
        meses.append(mes)
        mes = mes_de_data(somar_meses(f"01/{mes[5:]}/{mes[:4]}", 1))
    movimento = {n: [d.get(m, 0.0) for m in meses] for n, d in por_mes.items()}
    saldo = {n: list(itertools.accumulate(v)) for n, v in movimento.items()}
    return meses, saldo, movimento


def somar_meses(data_texto, meses):
    """'31/01/2026' + 1 mês -> '28/02/2026' (o dia é limitado ao fim do mês)."""
    dia, mes, ano = (int(parte) for parte in data_texto.strip().split("/"))
    ano, mes = divmod(ano * 12 + mes - 1 + meses, 12)
    mes += 1
    return f"{min(dia, calendar.monthrange(ano, mes)[1]):02d}/{mes:02d}/{ano:04d}"


def descricao_parcela(gasto):
    """'Parcelamento de Compras 3/12'."""
    return f"{rotulo_categoria(gasto)} {gasto['parcela']}/{gasto['parcelas']}"


def e_conta_fixa(gasto):
    """Copiada mês a mês? Parcelados não: suas parcelas vêm de distribuir_parcelas."""
    return gasto["categoria"] in CONTAS_FIXAS and not gasto.get("compra")


def distribuir_parcelas(gastos):
    """Cria, nos meses seguintes, as parcelas que faltam de cada compra/empréstimo.

    As parcelas de uma compra têm o mesmo "compra" (id). A de menor número serve
    de base; as que já existem não são recriadas. Retorna quantas criou.
    """
    por_compra = {}
    for gasto in gastos:
        if gasto.get("compra"):
            por_compra.setdefault(gasto["compra"], []).append(gasto)
    novas = []
    for itens in por_compra.values():
        base = min(itens, key=lambda g: g["parcela"])
        if mes_do_gasto(base) is None:  # data inválida: não dá para contar meses
            continue
        existentes = {g["parcela"] for g in itens}
        for numero in range(1, base["parcelas"] + 1):
            if numero in existentes:
                continue
            nova = {**base, "parcela": numero,
                    "data": somar_meses(base["data"], numero - base["parcela"])}
            nova["descricao"] = descricao_parcela(nova)
            novas.append(nova)
    gastos.extend(novas)
    return len(novas)


def totais_por_categoria(gastos):
    """Retorna um dict {categoria: total} apenas com categorias que têm gasto."""
    totais = {}
    for gasto in gastos:
        cat = rotulo_categoria(gasto)
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
        # Com o ibus (padrão do Ubuntu), o Tk registra cada widget no método de
        # entrada e fica ~250x mais lento para criar telas e janelas. Os campos
        # do app só recebem números e datas, então dispensa o método de entrada.
        if sys.platform.startswith("linux"):
            self.root.tk.call("tk", "useinputmethods", "0")
        self.root.title("Calculador de Gastos")
        self.root.geometry("1080x980")
        self.root.minsize(940, 800)

        self.orcamentos, self.gastos, self.rendas = carregar_dados()
        self.mes_atual = mes_atual_chave()
        self._popup_mes = None
        self._toast_lbl = None
        self._editando = None  # ("g" | "r", índice) enquanto edita um lançamento
        self._redesenho = None  # after() pendente para redesenhar os gráficos do mês

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
        # os gráficos usam muito negrito: a fonte precisa ter o peso bold (700) de
        # verdade, senão o matplotlib troca por outro peso e avisa no terminal
        # (ex.: a Roboto do sistema só tem 400 e 500). Prefere a fonte da UI.
        pesos = {}
        for fonte in mpl.font_manager.fontManager.ttflist:
            peso = fonte.weight
            if isinstance(peso, str):
                peso = mpl.font_manager.weight_dict.get(peso, 400)
            pesos.setdefault(fonte.name, set()).add(peso)
        candidatas = [self.familia, "Inter", "Segoe UI", "Roboto", "Ubuntu",
                      "Cantarell", "Noto Sans", "Helvetica", "DejaVu Sans"]
        familia_mpl = next((f for f in candidatas if max(pesos.get(f, {0})) >= 700),
                           "DejaVu Sans")
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
        """Diálogo modal de confirmação (Remover/Cancelar) no estilo do app."""
        return self._escolher(titulo, mensagem, ["Remover"]) == "Remover"

    def _escolher(self, titulo, mensagem, opcoes):
        """Diálogo modal com um botão por opção (a última é a principal).

        Retorna o texto da opção escolhida, ou None se cancelar/fechar.
        """
        largura = 380 if len(opcoes) == 1 else 540
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(titulo)
        dlg.geometry(f"{largura}x190")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.after(50, dlg.grab_set)
        resultado = [None]

        ctk.CTkLabel(dlg, text=titulo, font=self.ft_secao).pack(
            padx=24, pady=(22, 4), anchor="w")
        ctk.CTkLabel(dlg, text=mensagem, font=self.ft_normal,
                     wraplength=largura - 50, justify="left", text_color=SUB).pack(
            padx=24, anchor="w")

        botoes = ctk.CTkFrame(dlg, fg_color="transparent")
        botoes.pack(side="bottom", fill="x", padx=24, pady=20)

        def escolher(opcao):
            resultado[0] = opcao
            dlg.destroy()

        for i, opcao in enumerate(reversed(opcoes)):  # pack da direita p/ esquerda
            principal = i == 0
            ctk.CTkButton(botoes, text=opcao, font=self.ft_bold,
                          fg_color=COR_NEG if principal else "transparent",
                          hover_color="#C0392B" if principal else CARD2,
                          text_color="white" if principal else COR_NEG,
                          border_width=0 if principal else 1, border_color=COR_NEG,
                          command=lambda o=opcao: escolher(o)).pack(
                side="right", padx=(8, 0))
        ctk.CTkButton(botoes, text="Cancelar", fg_color="transparent",
                      border_width=1, border_color=BORDA,
                      text_color=TEXTO, hover_color=CARD2,
                      font=self.ft_bold, command=dlg.destroy,
                      width=110).pack(side="right")
        dlg.wait_window()
        return resultado[0]

    # ------------------------------------------------------------------ mês ---
    def gastos_do_mes(self):
        return [g for g in self.gastos if mes_do_gasto(g) == self.mes_atual]

    def rendas_do_mes(self):
        return [r for r in self.rendas if mes_do_gasto(r) == self.mes_atual]

    def orcamento_do_mes(self):
        return self.orcamentos.get(self.mes_atual, 0.0)

    def renda_do_mes(self):
        return sum(r["valor"] for r in self.rendas_do_mes())

    def disponivel_do_mes(self):
        """Orçamento do mês: salário somado às rendas extras lançadas nele."""
        return self.orcamento_do_mes() + self.renda_do_mes()

    def _meses_com_dados_asc(self):
        chaves = set(self.orcamentos.keys())
        for item in self.gastos + self.rendas:
            chave = mes_do_gasto(item)
            if chave:
                chaves.add(chave)
        return sorted(chaves)

    def meses_disponiveis(self):
        return sorted(set(self._meses_com_dados_asc()) | {self.mes_atual},
                      reverse=True)

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
        self.orc_var.set(formatar_numero(self.orcamento_do_mes()))
        self._preencher_renda()
        self._atualizar_tudo()

    # ---- calendário pop-up de mês/ano ----
    def _abrir_seletor_mes(self, ancora=None, selecionado=None, ao_escolher=None):
        """Calendário de mês/ano. Sem argumentos: troca o mês exibido no app."""
        self._fechar_popup_mes()
        self._popup_ancora = ancora or self.mes_btn
        self._popup_selecionado = selecionado or self.mes_atual
        self._popup_ao_escolher = ao_escolher or self._ir_para_chave
        pop = ctk.CTkToplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        self._popup_mes = pop
        self._ano_popup = int(self._popup_selecionado.split("-")[0])

        x = self._popup_ancora.winfo_rootx()
        y = self._popup_ancora.winfo_rooty() + self._popup_ancora.winfo_height() + 6
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
        if not clicado.startswith(str(pop)) and evento.widget is not self._popup_ancora:
            self._fechar_popup_mes()

    def _mudar_ano_popup(self, delta):
        self._ano_popup += delta
        self._render_popup_mes()

    def _escolher_mes_popup(self, chave):
        ao_escolher = self._popup_ao_escolher
        self._fechar_popup_mes()
        ao_escolher(chave)

    def _ir_para_chave(self, chave):
        self.mes_atual = chave
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
            selecionado = chave == self._popup_selecionado
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
        self.tabview.add("Reserva e Investimentos")

        self._montar_aba_lancamentos(self.tabview.tab("Lançamentos"))
        self._montar_aba_graficos(self.tabview.tab("Gráficos do mês"))
        self._montar_aba_evolucao(self.tabview.tab("Evolução"))
        self._montar_aba_poupancas(self.tabview.tab("Reserva e Investimentos"))

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
        # ---- linha 1 (compacta): de onde vem o dinheiro ----
        self.entradas = ctk.CTkFrame(parent, fg_color="transparent")
        self.entradas.pack(fill="x", pady=(14, 0))
        for i in range(COLUNAS_ENTRADAS):
            self.entradas.columnconfigure(i, weight=1, uniform="entradas")

        self.card_salario_valor = self._criar_card(
            self.entradas, 0, "💼", "SALÁRIO", COR_RENDA, compacto=True)
        self.card_renda_valor = self._criar_card(
            self.entradas, 1, "💵", "RENDAS EXTRAS", COR_RENDA, compacto=True)
        self.card_app_valor = {}  # só apps com renda no mês; ver _atualizar_cards_apps
        self._apps_nos_cards = ()
        self._logos_cards = {app: logo_ctk(app, 20) for app in APPS_DELIVERY}

        # ---- linha 2: orçamento (salário + rendas), gasto e restante ----
        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.pack(fill="x", pady=(2, 10))
        for i in range(3):
            cards.columnconfigure(i, weight=1, uniform="cards")

        self.card_orc_valor = self._criar_card(cards, 0, "🎯", "ORÇAMENTO", ACCENT)
        self.card_gasto_valor = self._criar_card(cards, 1, "💸", "TOTAL GASTO",
                                                 COR_GASTO)
        (_icone, self.card_rest_titulo,
         self.card_rest_valor) = self._criar_card(cards, 2, "💰", "RESTANTE",
                                                  COR_POS, completo=True)

    def _criar_card(self, parent, coluna, icone, titulo, cor_valor, completo=False,
                    compacto=False, logo=None, linha=0):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
        card.grid(row=linha, column=coluna, sticky="nsew", padx=6,
                  pady=(0, 8) if compacto else 0)
        margem = 12 if compacto else 18

        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.pack(fill="x", padx=margem, pady=(10 if compacto else 14, 0))
        if logo:  # o logo já identifica: dispensa ícone e título
            icone_lbl = titulo_lbl = ctk.CTkLabel(topo, text="", image=logo,
                                                  height=24,
                                                  corner_radius=6, padx=4)
            icone_lbl.pack(side="left")
        else:
            icone_lbl = ctk.CTkLabel(topo, text=icone, height=24, font=(
                self.ft_bold if compacto else self.ft_valor_pq))
            icone_lbl.pack(side="left")
            titulo_lbl = ctk.CTkLabel(topo, text=titulo, text_color=SUB,
                                      height=24, font=self.ft_rotulo)
            titulo_lbl.pack(side="left", padx=6 if compacto else 8)

        valor_lbl = ctk.CTkLabel(card, text="R$ 0,00", text_color=cor_valor,
                                 font=self.ft_valor_pq if compacto else self.ft_valor)
        valor_lbl.pack(anchor="w", padx=margem, pady=(0 if compacto else 2,
                                                     10 if compacto else 16))

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

        # ---- Cards lado a lado: salário | renda extra ----
        topo = ctk.CTkFrame(parent, fg_color="transparent")
        topo.pack(fill="x", pady=(6, 14))
        topo.columnconfigure(0, weight=1, uniform="topo")
        topo.columnconfigure(1, weight=1, uniform="topo")

        orc = ctk.CTkFrame(topo, fg_color=CARD2, corner_radius=12)
        orc.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        cabecalho = ctk.CTkFrame(orc, fg_color="transparent")
        cabecalho.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(cabecalho, text="💼  Salário", font=self.ft_secao).pack(
            side="left")
        self.btn_limpar_salario = ctk.CTkButton(
            cabecalho, text="🧹  Limpar", width=90, height=26, font=self.ft_pequena,
            fg_color="transparent", text_color=COR_NEG, hover_color=CARD,
            border_width=1, border_color=COR_NEG, command=self.limpar_salario)
        self.btn_limpar_salario.pack(side="right")

        linha_orc = ctk.CTkFrame(orc, fg_color="transparent")
        linha_orc.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(linha_orc, text="R$", text_color=SUB,
                     font=self.ft_rotulo).pack(side="left", padx=(0, 6))
        self.orc_var = tk.StringVar(
            value=formatar_numero(self.orcamento_do_mes()))
        orc_entry = ctk.CTkEntry(linha_orc, textvariable=self.orc_var, width=140,
                                 font=self.ft_normal)
        orc_entry.pack(side="left")
        orc_entry.bind("<Return>", lambda e: self.definir_orcamento())
        self._campo_dinheiro(orc_entry, self.orc_var)
        ctk.CTkButton(linha_orc, text="Salvar", width=100, font=self.ft_bold,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.definir_orcamento).pack(side="left", padx=10)


        self._montar_painel_renda(topo)

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

        self.valor_rotulo = ctk.CTkLabel(form, text="VALOR (R$)", text_color=SUB,
                                         font=self.ft_rotulo)
        self.valor_rotulo.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        self.valor_var = tk.StringVar()
        valor_entry = ctk.CTkEntry(form, textvariable=self.valor_var,
                                   font=self.ft_normal)
        valor_entry.grid(row=1, column=0, sticky="we", padx=14, pady=(0, 8))
        valor_entry.bind("<Return>", lambda e: self.adicionar_gasto())
        self._campo_dinheiro(valor_entry, self.valor_var)

        self.data_rotulo = ctk.CTkLabel(form, text="DATA", text_color=SUB,
                                        font=self.ft_rotulo)
        self.data_rotulo.grid(row=0, column=1, sticky="w", padx=14, pady=(12, 2))
        self.data_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        linha_data = ctk.CTkFrame(form, fg_color="transparent")
        linha_data.grid(row=1, column=1, sticky="we", padx=14, pady=(0, 8))
        ctk.CTkEntry(linha_data, textvariable=self.data_var, font=self.ft_normal).pack(
            side="left", fill="x", expand=True)
        self.btn_data = ctk.CTkButton(linha_data, text="📅", width=36, font=self.ft_bold,
                                      fg_color=CARD, hover_color=BORDA, text_color=TEXTO,
                                      command=self._escolher_mes_da_data)
        self.btn_data.pack(side="left", padx=(6, 0))

        rotulo("CATEGORIA", 2, 0)
        self.cat_var = tk.StringVar(value=CATEGORIAS[0])
        ctk.CTkOptionMenu(form, variable=self.cat_var, values=CATEGORIAS,
                          font=self.ft_normal, fg_color=CARD,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO,
                          command=lambda _v: self._mostrar_instituicao()).grid(
            row=3, column=0, sticky="we", padx=14, pady=(0, 12))

        # só aparece quando a categoria é fatura de cartão
        self.inst_rotulo = ctk.CTkLabel(form, text="INSTITUIÇÃO", text_color=SUB,
                                        font=self.ft_rotulo)
        self.inst_rotulo.grid(row=4, column=0, sticky="w", padx=14, pady=(12, 2))
        self.inst_var = tk.StringVar(value=next(iter(INSTITUICOES)))
        self.inst_menu = ctk.CTkOptionMenu(
            form, variable=self.inst_var, values=list(INSTITUICOES),
            font=self.ft_normal, fg_color=CARD, text_color=TEXTO,
            command=lambda _v: self._mostrar_instituicao())
        self.inst_menu.grid(row=5, column=0, sticky="we", padx=14, pady=(0, 12))

        # mesmo lugar: só aparece para parcelamento de compras
        self.parc_rotulo = ctk.CTkLabel(form, text="PARCELAS", text_color=SUB,
                                        font=self.ft_rotulo)
        self.parc_rotulo.grid(row=4, column=0, sticky="w", padx=14, pady=(12, 2))
        primeira = next(iter(CATEGORIAS_PARCELADAS.values()))[0][0]
        self.parcelas_var = tk.StringVar(value=primeira)
        self._ultima_parcela = primeira  # volta para ela se "Outra…" for cancelada
        self._categoria_parcelas = None  # trocar de categoria reinicia a quantidade
        self.parc_menu = ctk.CTkOptionMenu(
            form, variable=self.parcelas_var, values=[primeira],
            font=self.ft_normal, fg_color=CARD, text_color=TEXTO,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            command=self._escolheu_parcelas)
        self.parc_menu.grid(row=5, column=0, sticky="we", padx=14, pady=(0, 12))
        self._mostrar_instituicao()

        rotulo("CARTÃO / PAGAMENTO", 2, 1)
        self.cartao_var = tk.StringVar(value=CARTOES[0])
        ctk.CTkOptionMenu(form, variable=self.cartao_var, values=CARTOES,
                          font=self.ft_normal, fg_color=CARD,
                          button_color=ACCENT, button_hover_color=ACCENT_HOVER,
                          text_color=TEXTO).grid(
            row=3, column=1, sticky="we", padx=14, pady=(0, 12))

        # na linha da instituição: fica ao lado dela quando ela aparece
        self.btn_add_gasto = ctk.CTkButton(
            form, text="➕  Adicionar gasto", font=self.ft_bold,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self.adicionar_gasto)
        self.btn_add_gasto.grid(row=5, column=1, sticky="we", padx=14, pady=(0, 14))

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
                      command=self.remover_lancamento).pack(side="right", padx=4)
        self.btn_editar = ctk.CTkButton(
            barra, text="✏️  Editar selecionado", font=self.ft_bold,
            fg_color="transparent", text_color=ACCENT, hover_color=CARD2,
            border_width=1, border_color=ACCENT, command=self.editar_lancamento)
        self.btn_editar.pack(side="right", padx=4)
        ctk.CTkButton(barra, text="🧹  Limpar mês", font=self.ft_bold,
                      fg_color=COR_NEG, hover_color="#C0392B",
                      command=self.limpar_lancamentos).pack(side="right", padx=4)

        # ---- Tabela ----
        tabela_frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        tabela_frame.pack(fill="both", expand=True)

        colunas = ("data", "categoria", "cartao", "valor")
        self.tree = ttk.Treeview(tabela_frame, columns=colunas, show="headings",
                                 selectmode="browse")
        self.tree.heading("data", text="DATA")
        self.tree.heading("categoria", text="CATEGORIA")
        self.tree.heading("cartao", text="CARTÃO")
        self.tree.heading("valor", text="VALOR")
        self.tree.column("data", width=84, anchor="center")
        self.tree.column("categoria", width=220, anchor="center")
        self.tree.column("cartao", width=130, anchor="center")
        self.tree.column("valor", width=120, anchor="e")

        scroll = ctk.CTkScrollbar(tabela_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=10)
        self.tree.bind("<Double-1>", lambda e: (self._cancelar_edicao(),
                                                self.editar_lancamento()))

    def _campo_dinheiro(self, entry, var):
        """Máscara estilo app de banco: só dígitos, que entram pelos centavos."""
        novo = [True]  # 1ª tecla depois de focar começa um valor novo

        def mostrar(centavos):
            var.set(formatar_numero(centavos / 100))
            entry.select_clear()  # a seleção sobrevive ao var.set e zeraria a próxima tecla
            entry.icursor("end")
            novo[0] = False

        def focar(_evento):
            novo[0] = True
            entry.after_idle(lambda: entry.select_range(0, "end"))

        def tecla(evento):
            if evento.keysym in ("Tab", "ISO_Left_Tab"):
                return None
            ctrl = evento.state & 0x4
            if ctrl and evento.keysym.lower() == "v":
                try:
                    mostrar(centavos_do_texto(entry.clipboard_get()))
                except tk.TclError:  # área de transferência vazia
                    pass
                return "break"
            if ctrl:  # Ctrl+A, Ctrl+C...
                return None
            atual = (0 if novo[0] or entry.select_present()
                     else centavos_do_texto(var.get()))
            if evento.char and evento.char in "0123456789":
                valor = atual * 10 + int(evento.char)
                if valor <= MAX_CENTAVOS:
                    mostrar(valor)
            elif evento.keysym in ("BackSpace", "Delete"):
                mostrar(atual // 10)
            return "break"  # letras, símbolos e setas não entram

        entry.bind("<FocusIn>", focar)
        entry.bind("<KeyPress>", tecla)
        entry.bind("<Button-2>", lambda e: "break")  # colar com o botão do meio (X11)

    def _mostrar_instituicao(self):
        """Mostra o 2º seletor (banco, transporte, parcelas) conforme a categoria."""
        regra = CATEGORIAS_PARCELADAS.get(self.cat_var.get())
        parcelado = regra is not None
        self.valor_rotulo.configure(
            text="VALOR DA PARCELA (R$)" if parcelado else "VALOR (R$)")
        self.data_rotulo.configure(text="1ª PARCELA EM" if parcelado else "DATA")
        if parcelado:  # destaque: aqui se escolhe o começo do parcelamento
            cor = CATEGORIA_CORES.get(self.cat_var.get(), ACCENT)
            self.btn_data.configure(text="📅  Início", width=96, fg_color=cor,
                                    hover_color=cor,  # rosa claro pede texto escuro
                                    text_color="#1F2430" if cor == CATEGORIA_CORES[
                                        CATEGORIA_PARCELAMENTO] else "white")
        else:
            self.btn_data.configure(text="📅", width=36, fg_color=CARD, hover_color=BORDA,
                                    text_color=TEXTO)
        for widget in (self.parc_rotulo, self.parc_menu):
            widget.grid() if parcelado else widget.grid_remove()
        trocou = self.cat_var.get() != self._categoria_parcelas
        self._categoria_parcelas = self.cat_var.get()
        if parcelado:
            rapidas, maximo = regra
            atual = None if trocou else quantidade_parcelas(self.parcelas_var.get(), maximo)
            if atual is None:  # nova categoria (ou valor inválido): 1ª opção rápida
                atual = quantidade_parcelas(rapidas[0], maximo)
            self.parcelas_var.set(f"{atual}x")
            self._ultima_parcela = f"{atual}x"
            # quantidade digitada em "Outra…" entra no menu, em ordem
            numeros = sorted({int(o.rstrip("x")) for o in rapidas} | {atual})
            cor = CATEGORIA_CORES.get(self.cat_var.get(), ACCENT)
            self.parc_menu.configure(values=[f"{n}x" for n in numeros] + [OUTRA_QUANTIDADE],
                                     button_color=cor, button_hover_color=cor)
        sub = SUBCATEGORIAS.get(self.cat_var.get())
        if not sub:
            self.inst_rotulo.grid_remove()
            self.inst_menu.grid_remove()
            return
        _prefixo, titulo, opcoes = sub
        if self.inst_var.get() not in opcoes:  # trocou fatura <-> transporte
            self.inst_var.set(next(iter(opcoes)))
        cor = opcoes[self.inst_var.get()]
        self.inst_rotulo.configure(text=titulo)
        self.inst_menu.configure(values=list(opcoes), button_color=cor,
                                 button_hover_color=cor)
        self.inst_rotulo.grid()
        self.inst_menu.grid()

    def _escolheu_parcelas(self, valor):
        """No menu de parcelas, 'Outra…' pede a quantidade digitada."""
        regra = CATEGORIAS_PARCELADAS.get(self.cat_var.get())
        if valor != OUTRA_QUANTIDADE or not regra:
            self._ultima_parcela = valor
            return
        maximo = regra[1]
        texto = ctk.CTkInputDialog(
            title="Quantidade de parcelas",
            text=f"Digite a quantidade de parcelas (2 a {maximo}):").get_input()
        n = quantidade_parcelas(texto, maximo)
        if n is None:
            if texto is not None:
                self._toast(f"Informe um número de 2 a {maximo}.", "erro")
            self.parcelas_var.set(self._ultima_parcela)
        else:
            self.parcelas_var.set(f"{n}x")
        self._mostrar_instituicao()

    def _escolher_mes_da_data(self):
        """📅: escolhe mês/ano no calendário, mantendo o dia digitado."""
        def definir(chave):
            ano, mes = (int(x) for x in chave.split("-"))
            dia = min(dia_de_data(self.data_var.get()), calendar.monthrange(ano, mes)[1])
            self.data_var.set(f"{dia:02d}/{mes:02d}/{ano:04d}")

        atual = mes_de_data(self.data_var.get()) or self.mes_atual
        self._abrir_seletor_mes(self.btn_data, atual, definir)

    def _montar_painel_renda(self, parent):
        """Painel de renda extra, ao lado do salário."""
        card = ctk.CTkFrame(parent, fg_color=CARD2, corner_radius=12)
        card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        cabecalho = ctk.CTkFrame(card, fg_color="transparent")
        cabecalho.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(cabecalho, text="💵  Renda extra", font=self.ft_secao).pack(
            side="left")
        self.btn_limpar_rendas = ctk.CTkButton(
            cabecalho, text="🧹  Limpar", width=90, height=26, font=self.ft_pequena,
            fg_color="transparent", text_color=COR_NEG, hover_color=CARD,
            border_width=1, border_color=COR_NEG, command=self.limpar_rendas)
        self.btn_limpar_rendas.pack(side="right")

        linha_valor = ctk.CTkFrame(card, fg_color="transparent")
        linha_valor.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(linha_valor, text="R$", text_color=SUB,
                     font=self.ft_rotulo).pack(side="left", padx=(0, 6))
        self.renda_valor_var = tk.StringVar()
        valor_entry = ctk.CTkEntry(linha_valor, textvariable=self.renda_valor_var,
                                   width=110, font=self.ft_normal)
        valor_entry.pack(side="left")
        valor_entry.bind("<Return>", lambda e: self.definir_renda())
        self._campo_dinheiro(valor_entry, self.renda_valor_var)

        self.renda_fonte_var = tk.StringVar(value=FONTES_RENDA[0])
        ctk.CTkOptionMenu(linha_valor, variable=self.renda_fonte_var,
                          values=FONTES_RENDA, width=140, font=self.ft_normal,
                          fg_color=CARD, button_color=COR_RENDA,
                          button_hover_color=COR_RENDA_HOVER, text_color=TEXTO,
                          command=lambda _v: self._mostrar_app_delivery()).pack(
            side="left", padx=8)

        ctk.CTkButton(linha_valor, text="Salvar", width=100, font=self.ft_bold,
                      fg_color=COR_RENDA, hover_color=COR_RENDA_HOVER,
                      command=self.definir_renda).pack(side="left")

        # só aparece quando a fonte é delivery
        self.linha_app = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(self.linha_app, text="APP", text_color=SUB,
                     font=self.ft_rotulo).pack(side="left", padx=(0, 6))
        self.renda_app_var = tk.StringVar(value=next(iter(APPS_DELIVERY)))
        self.renda_app_menu = ctk.CTkOptionMenu(
            self.linha_app, variable=self.renda_app_var, values=list(APPS_DELIVERY),
            width=140, font=self.ft_normal, fg_color=CARD, text_color=TEXTO,
            command=lambda _v: self._mostrar_app_delivery())
        self.renda_app_menu.pack(side="left")
        self.renda_app_logo = ctk.CTkLabel(self.linha_app, text="", height=30,
                                           corner_radius=6, padx=4)
        self.renda_app_logo.pack(side="left", padx=12)
        self._logos_apps = {app: logo_ctk(app, 26) for app in APPS_DELIVERY}
        self._mostrar_app_delivery()

    def _mostrar_app_delivery(self):
        """Mostra o seletor de app (com cor e logo) só para a fonte delivery."""
        self._preencher_renda()
        if self.renda_fonte_var.get() != FONTE_DELIVERY:
            self.linha_app.pack_forget()
            return
        app = self.renda_app_var.get()
        cor = APPS_DELIVERY[app]
        self.renda_app_menu.configure(button_color=cor, button_hover_color=cor)
        logo = self._logos_apps[app]
        self.renda_app_logo.configure(image=logo, text="" if logo else app,
                                      fg_color="transparent")
        self.linha_app.pack(fill="x", padx=16, pady=(0, 14))

    def _montar_aba_graficos(self, parent):
        parent.configure(fg_color="transparent")
        # rosca de categorias grande à esquerda; barras e pagamentos menores à direita
        parent.columnconfigure(0, weight=3, uniform="graficos")
        parent.columnconfigure(1, weight=2, uniform="graficos")
        parent.rowconfigure(0, weight=1, uniform="linhas_graficos")
        parent.rowconfigure(1, weight=1, uniform="linhas_graficos")

        self.canvas_pizza = self._criar_canvas_grafico(parent, 0, 0, rowspan=2)
        self.fig_pizza = self.canvas_pizza.figure
        self.ax_pizza = self.fig_pizza.add_subplot(111)

        self.canvas_barras = self._criar_canvas_grafico(parent, 0, 1)
        self.fig_barras = self.canvas_barras.figure
        self.ax_barras = self.fig_barras.add_subplot(111)

        self.canvas_cartao = self._criar_canvas_grafico(parent, 1, 1)
        self.fig_cartao = self.canvas_cartao.figure
        self.ax_cartao = self.fig_cartao.add_subplot(111)

        # o tamanho dos logos/emojis nas fatias depende do tamanho da rosca na tela
        for canvas in (self.canvas_pizza, self.canvas_cartao):
            canvas.get_tk_widget().bind("<Configure>", self._agendar_redesenho, add="+")

    def _agendar_redesenho(self, _evento=None):
        """Redesenha os gráficos do mês logo após a janela/aba mudar de tamanho."""
        if self._redesenho:
            self.root.after_cancel(self._redesenho)
        self._redesenho = self.root.after(150, self._atualizar_graficos)

    def _criar_canvas_grafico(self, parent, linha, coluna, columnspan=1, rowspan=1):
        moldura = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        moldura.grid(row=linha, column=coluna, columnspan=columnspan,
                     rowspan=rowspan, sticky="nsew", padx=6, pady=6)
        # tamanho inicial pequeno: quem manda no tamanho final são os pesos do grid
        fig = Figure(figsize=(3.0, 2.0), dpi=100, layout="constrained")
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

    def _montar_aba_poupancas(self, parent):
        parent.configure(fg_color="transparent")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=3, uniform="graficos_poupanca")  # acumulado maior
        parent.rowconfigure(2, weight=2, uniform="graficos_poupanca")

        self.poupanca_tiles = self._montar_tiles(parent, [
            ("🛟", "RESERVA DE EMERGÊNCIA", CATEGORIA_CORES["Reserva de Emergência"]),
            ("📈", "INVESTIMENTOS", CATEGORIA_CORES["Investimentos"]),
            ("🏦", "TOTAL GUARDADO", ACCENT),
            ("💵", "GUARDADO NO MÊS", COR_GASTO),
        ])
        self.canvas_acum = self._criar_canvas_grafico(parent, 1, 0)
        self.fig_acum = self.canvas_acum.figure
        self.ax_acum = self.fig_acum.add_subplot(111)
        self.canvas_aportes = self._criar_canvas_grafico(parent, 2, 0)
        self.fig_aportes = self.canvas_aportes.figure
        self.ax_aportes = self.fig_aportes.add_subplot(111)

    def _montar_resumo_evolucao(self, parent):
        self.resumo_tiles = self._montar_tiles(parent, [
            ("📊", "GASTO MÉDIO/MÊS", ACCENT),
            ("🔺", "MAIOR MÊS", COR_NEG),
            ("🔻", "MENOR MÊS", COR_POS),
            ("💰", "TOTAL ACUMULADO", COR_GASTO),
        ])

    def _montar_tiles(self, parent, tiles):
        """Faixa de resumo (ícone, título, valor e subtítulo) no topo de uma aba."""
        wrap = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        wrap.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 6))
        for i in range(len(tiles)):
            wrap.columnconfigure(i, weight=1, uniform="resumo")
        celulas = []
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
            celulas.append((valor, sub))
        return celulas

    # --------------------------------------------------------------- ações ---
    def _parse_valor(self, texto):
        try:
            return float(texto.strip().replace(".", "").replace(",", "."))
        except ValueError:
            return None

    def definir_orcamento(self):
        valor = self._parse_valor(self.orc_var.get())
        if valor is None or valor < 0:
            self._toast("Informe um salário numérico válido.", "erro")
            return
        self.orcamentos[self.mes_atual] = valor
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._atualizar_tudo()
        self._toast(f"Salário de {nome_mes(self.mes_atual)} salvo.", "sucesso")

    def _data_no_mes(self):
        """Hoje, se o mês exibido for o atual; senão, dia 1º do mês exibido."""
        if self.mes_atual == mes_atual_chave():
            return date.today().strftime("%d/%m/%Y")
        ano, mes = self.mes_atual.split("-")
        return f"01/{mes}/{ano}"

    def _renda_escolhida(self):
        """(fonte, app) escolhidos no painel; app só existe no delivery."""
        fonte = self.renda_fonte_var.get()
        return fonte, (self.renda_app_var.get() if fonte == FONTE_DELIVERY else None)

    def _preencher_renda(self):
        """Mostra no campo o valor já salvo no mês para a fonte/app escolhidos."""
        fonte, app = self._renda_escolhida()
        total = sum(r["valor"] for r in self.rendas
                    if mesma_renda(r, self.mes_atual, fonte, app))
        self.renda_valor_var.set(formatar_numero(total))

    def definir_renda(self):
        """Como o salário: grava o valor do mês para a fonte/app (0 remove)."""
        valor = self._parse_valor(self.renda_valor_var.get())
        if valor is None or valor < 0:
            self._toast("Informe um valor de renda numérico válido.", "erro")
            return

        fonte, app = self._renda_escolhida()
        self.rendas = [r for r in self.rendas
                       if not mesma_renda(r, self.mes_atual, fonte, app)]
        if valor > 0:
            nova = {"data": self._data_no_mes(), "fonte": fonte, "valor": valor}
            if app:
                nova["app"] = app
            self.rendas.append(nova)
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._preencher_renda()
        self._atualizar_tudo()
        nome, mes = app or fonte, nome_mes(self.mes_atual)
        if valor:
            self._toast(f"{nome} de {mes} salvo ({formatar_moeda(valor)}).", "sucesso")
        else:
            self._toast(f"{nome} de {mes} removido.", "sucesso")

    def adicionar_gasto(self):
        valor = self._parse_valor(self.valor_var.get())
        categoria = self.cat_var.get()
        cartao = self.cartao_var.get()
        data_texto = self.data_var.get().strip()

        if valor is None or valor <= 0:
            self._toast("Informe um valor maior que zero.", "erro")
            return
        regra = CATEGORIAS_PARCELADAS.get(categoria)
        n_parcelas = quantidade_parcelas(self.parcelas_var.get(), regra[1]) if regra else None
        if regra and n_parcelas is None:
            self._toast(f"Escolha a quantidade de parcelas (2 a {regra[1]}).", "erro")
            return

        novo = {
            "data": data_texto or date.today().strftime("%d/%m/%Y"),
            "categoria": categoria,
            "cartao": cartao,
            "valor": valor,
        }
        if categoria in SUBCATEGORIAS:
            novo["instituicao"] = self.inst_var.get()
        novo["descricao"] = rotulo_categoria(novo)  # ex.: "Luz", "Fatura Nubank"
        editando = self._editando is not None
        if categoria in CATEGORIAS_PARCELADAS:
            anterior = self.gastos[self._editando] if editando else {}
            novo["parcelas"] = n_parcelas
            novo["parcela"] = anterior.get("parcela", 1)
            novo["compra"] = anterior.get("compra") or uuid.uuid4().hex[:12]
            novo["descricao"] = descricao_parcela(novo)
        if editando:
            self.gastos[self._editando] = novo
        else:
            self.gastos.append(novo)
        salvar_dados(self.orcamentos, self.gastos, self.rendas)

        if editando:
            self._cancelar_edicao()
        else:
            self.valor_var.set("")

        mes_novo = mes_do_gasto(novo) or self.mes_atual
        self.mes_atual = mes_novo
        self._sincronizar_mes()
        acao = "alterado" if editando else "adicionado"
        if categoria in CATEGORIAS_PARCELADAS and not editando:
            self._toast(f"{categoria}: {novo['parcelas']}x de {formatar_moeda(valor)} "
                        "adicionado. Use 'Copiar contas fixas' para lançar as "
                        "próximas parcelas.", "sucesso")
        else:
            self._toast(f"Gasto {acao} ({formatar_moeda(valor)}).", "sucesso")

    def _selecionado(self):
        """Índice (em self.gastos) da linha selecionada na tabela, ou None."""
        selecao = self.tree.selection()
        if not selecao:
            return None
        return int(self.tree.item(selecao[0], "tags")[-1].removeprefix("g_"))

    def editar_lancamento(self):
        """Carrega o gasto selecionado no formulário (ou cancela a edição)."""
        if self._editando is not None:
            self._cancelar_edicao()
            return
        indice = self._selecionado()
        if indice is None:
            self._toast("Selecione um gasto para editar.", "info")
            return
        item = self.gastos[indice]
        self.valor_var.set(formatar_numero(item["valor"]))
        self.data_var.set(item["data"])
        self.cat_var.set(item["categoria"])
        self.cartao_var.set(item.get("cartao", CARTAO_PADRAO))
        if item.get("instituicao"):
            self.inst_var.set(item["instituicao"])
        if item.get("parcelas"):
            self.parcelas_var.set(f"{item['parcelas']}x")
            self._categoria_parcelas = item["categoria"]  # mantém a quantidade da parcela
        self._mostrar_instituicao()
        self.btn_add_gasto.configure(text="💾  Salvar alteração")
        self._editando = indice
        self.btn_editar.configure(text="✖  Cancelar edição")
        self._toast("Altere os campos e clique em Salvar.", "info")

    def _cancelar_edicao(self):
        if self._editando is None:
            return
        self._editando = None
        self.valor_var.set("")
        self.data_var.set(date.today().strftime("%d/%m/%Y"))
        self.btn_add_gasto.configure(text="➕  Adicionar gasto")
        self.btn_editar.configure(text="✏️  Editar selecionado")

    def limpar_lancamentos(self):
        """Apaga todos os gastos do mês exibido (salário, rendas e outros meses ficam)."""
        n_gastos = len(self.gastos_do_mes())
        mes = nome_mes(self.mes_atual)
        if not n_gastos:
            self._toast(f"Não há gastos em {mes}.", "info")
            return
        if not self._confirmar(
            "Limpar gastos do mês",
            f"Apagar todos os {n_gastos} gasto(s) de {mes}? Não dá para desfazer.",
        ):
            return
        self._cancelar_edicao()  # os índices mudam
        self.gastos = [g for g in self.gastos if mes_do_gasto(g) != self.mes_atual]
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._atualizar_tudo()
        self._toast(f"Gastos de {mes} apagados.", "sucesso")

    def limpar_salario(self):
        """Apaga o salário do mês exibido (rendas extras e gastos ficam)."""
        salario = self.orcamento_do_mes()
        mes = nome_mes(self.mes_atual)
        if not salario:
            self._toast(f"Não há salário salvo em {mes}.", "info")
            return
        if not self._confirmar(
            "Limpar salário",
            f"Apagar o salário de {mes} ({formatar_moeda(salario)})? Rendas extras "
            f"e gastos continuam. Não dá para desfazer.",
        ):
            return
        del self.orcamentos[self.mes_atual]
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._sincronizar_mes()
        self._toast(f"Salário de {mes} apagado.", "sucesso")

    def limpar_rendas(self):
        """Apaga todas as rendas extras do mês exibido (salário e gastos ficam)."""
        n_rendas = len(self.rendas_do_mes())
        mes = nome_mes(self.mes_atual)
        if not n_rendas:
            self._toast(f"Não há rendas extras em {mes}.", "info")
            return
        if not self._confirmar(
            "Limpar rendas extras",
            f"Apagar as {n_rendas} renda(s) extra(s) de {mes}? Salário e gastos "
            f"continuam. Não dá para desfazer.",
        ):
            return
        self.rendas = [r for r in self.rendas if mes_do_gasto(r) != self.mes_atual]
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._preencher_renda()
        self._atualizar_tudo()
        self._toast(f"Rendas extras de {mes} apagadas.", "sucesso")

    def remover_lancamento(self):
        indice = self._selecionado()
        if indice is None:
            self._toast("Selecione um gasto para remover.", "info")
            return
        item = self.gastos[indice]
        compra = item.get("compra")
        parcelas = [g for g in self.gastos if compra and g.get("compra") == compra]
        if len(parcelas) > 1:
            self._remover_parcelas(indice, item, parcelas)
            return
        if self._confirmar(
            "Remover gasto",
            f"Remover '{item['descricao']}' ({formatar_moeda(item['valor'])})?",
        ):
            self._cancelar_edicao()  # os índices mudam depois do del
            del self.gastos[indice]
            salvar_dados(self.orcamentos, self.gastos, self.rendas)
            self._atualizar_tudo()
            self._toast("Gasto removido.", "sucesso")

    def _remover_parcelas(self, indice, item, parcelas):
        """Parcela (compra ou empréstimo): remove só ela ou todas as parcelas."""
        so_esta = "Só esta parcela"
        todas = f"Todas as {len(parcelas)} parcelas"
        total = sum(g["valor"] for g in parcelas)
        escolha = self._escolher(
            "Remover parcelas",
            f"'{item['descricao']}' faz parte de um parcelamento "
            f"({len(parcelas)} parcelas, {formatar_moeda(total)} no total). "
            f"Uma parcela removida sozinha volta se você usar 'Copiar contas fixas'.",
            [so_esta, todas])
        if escolha is None:
            return
        self._cancelar_edicao()  # os índices mudam
        if escolha == todas:
            self.gastos = [g for g in self.gastos if g.get("compra") != item["compra"]]
            mensagem = f"{item['categoria']} removido ({len(parcelas)} parcelas)."
        else:
            del self.gastos[indice]
            mensagem = "Parcela removida."
        salvar_dados(self.orcamentos, self.gastos, self.rendas)
        self._atualizar_tudo()
        self._toast(mensagem, "sucesso")

    def _copiar_contas_fixas(self):
        parcelas = distribuir_parcelas(self.gastos)
        if parcelas:
            salvar_dados(self.orcamentos, self.gastos, self.rendas)
            self._atualizar_tudo()
            self._toast(f"{parcelas} parcela(s) de compras/empréstimos lançada(s) "
                        "nos meses seguintes.", "sucesso")

        def fixas(mes):
            return [g for g in self.gastos if mes_do_gasto(g) == mes and e_conta_fixa(g)]

        def chave(gasto):  # mesma regra de "já existe" de _executar_copia_contas
            return gasto["descricao"].strip().lower(), rotulo_categoria(gasto)

        meses_com_fixas = sorted({mes_do_gasto(g) for g in self.gastos
                                  if e_conta_fixa(g)} - {None})
        if not meses_com_fixas:
            if not parcelas:
                self._toast("Não há contas fixas lançadas para copiar.", "info")
            return

        # sugestão: copiar do mês anterior mais recente com contas para o mês atual
        anteriores = [m for m in meses_com_fixas if m < self.mes_atual]
        outros = [m for m in meses_com_fixas if m != self.mes_atual]
        origem = (anteriores or outros or [self.mes_atual])[-1]
        destino = self.mes_atual
        if origem == destino:  # só o mês atual tem contas: sugere o próximo
            destino = mes_de_data(somar_meses(f"01/{destino[5:]}/{destino[:4]}", 1))
        estado = {"origem": origem, "destino": destino, "modo": "origem",
                  "ano": int(origem[:4])}

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Copiar contas fixas")
        dlg.geometry("520x660")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.after(50, dlg.grab_set)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        ctk.CTkLabel(dlg, text="📋  Copiar contas fixas",
                     font=self.ft_secao).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(dlg, text="Escolha no calendário o mês de origem e o de destino. "
                               "Contas que já existem no destino não são duplicadas.",
                     font=self.ft_pequena, text_color=SUB, justify="left",
                     wraplength=480).pack(anchor="w", padx=20, pady=(0, 10))

        modo = ctk.CTkSegmentedButton(
            dlg, values=["Copiar de", "Copiar para"], font=self.ft_bold,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            command=lambda v: trocar_modo("origem" if v == "Copiar de" else "destino"))
        modo.pack(fill="x", padx=20)

        cabecalho = ctk.CTkFrame(dlg, fg_color="transparent")
        cabecalho.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkButton(cabecalho, text="◀", width=36, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT, hover_color=CARD2,
                      command=lambda: mudar_ano(-1)).pack(side="left")
        ano_lbl = ctk.CTkLabel(cabecalho, text="", font=self.ft_secao)
        ano_lbl.pack(side="left", expand=True)
        ctk.CTkButton(cabecalho, text="▶", width=36, font=self.ft_bold,
                      fg_color="transparent", text_color=ACCENT, hover_color=CARD2,
                      command=lambda: mudar_ano(1)).pack(side="right")

        grade = ctk.CTkFrame(dlg, fg_color="transparent")
        grade.pack(padx=20)
        legenda = ctk.CTkFrame(dlg, fg_color="transparent")
        legenda.pack(fill="x", padx=20, pady=(4, 8))
        for cor, texto in ((ACCENT, "origem"), (COR_RENDA, "destino")):
            ctk.CTkLabel(legenda, text="●", text_color=cor, font=self.ft_bold).pack(
                side="left", padx=(0, 3))
            ctk.CTkLabel(legenda, text=texto, text_color=SUB,
                         font=self.ft_pequena).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(legenda, text="▢ mês atual   • tem contas fixas", text_color=SUB,
                     font=self.ft_pequena).pack(side="left")

        previa_titulo = ctk.CTkLabel(dlg, text="", font=self.ft_bold, anchor="w")
        previa_titulo.pack(fill="x", padx=20)
        previa = ctk.CTkScrollableFrame(dlg, height=120, fg_color=CARD2)
        previa.pack(fill="x", padx=20, pady=(4, 6))
        resumo = ctk.CTkLabel(dlg, text="", font=self.ft_normal, text_color=SUB,
                              anchor="w", justify="left", wraplength=480)
        resumo.pack(fill="x", padx=20)

        botoes = ctk.CTkFrame(dlg, fg_color="transparent")
        botoes.pack(side="bottom", fill="x", padx=20, pady=16)
        btn_copiar = ctk.CTkButton(botoes, text="Copiar", fg_color=ACCENT,
                                   hover_color=ACCENT_HOVER, font=self.ft_bold,
                                   width=110, command=lambda: confirmar())
        btn_copiar.pack(side="right", padx=(8, 0))
        ctk.CTkButton(botoes, text="Cancelar", fg_color="transparent",
                      border_width=1, border_color=BORDA, text_color=TEXTO,
                      hover_color=CARD2, font=self.ft_bold, width=110,
                      command=dlg.destroy).pack(side="right")

        def trocar_modo(novo):
            estado["modo"] = novo
            modo.set("Copiar de" if novo == "origem" else "Copiar para")
            desenhar()

        def mudar_ano(delta):
            estado["ano"] += delta
            desenhar()

        def escolher(mes):
            estado[estado["modo"]] = mes
            if estado["modo"] == "origem":  # próximo passo natural: o destino
                trocar_modo("destino")
            else:
                desenhar()

        def desenhar():
            ano_lbl.configure(text=str(estado["ano"]))
            for w in grade.winfo_children():
                w.destroy()
            hoje = mes_atual_chave()
            for i, abrev in enumerate(MESES_ABREV):
                mes = f"{estado['ano']:04d}-{i + 1:02d}"
                n = len(fixas(mes))
                if mes == estado["origem"]:
                    fg, hover, txt = ACCENT, ACCENT_HOVER, "white"
                elif mes == estado["destino"]:
                    fg, hover, txt = COR_RENDA, COR_RENDA_HOVER, "white"
                elif n:
                    fg, hover, txt = CARD2, BORDA, ACCENT
                else:
                    fg, hover, txt = "transparent", CARD2, TEXTO
                contas = f"{n} conta{'s' if n != 1 else ''} •" if n else "—"
                linha, coluna = divmod(i, 4)
                ctk.CTkButton(grade, text=f"{abrev.capitalize()}\n{contas}", width=108,
                              height=48, font=self.ft_normal, fg_color=fg,
                              hover_color=hover, text_color=txt,
                              border_width=2 if mes == hoje else 0, border_color=SUB,
                              command=lambda m=mes: escolher(m)).grid(
                    row=linha, column=coluna, padx=4, pady=4)

            origem, destino = estado["origem"], estado["destino"]
            existentes = {chave(g) for g in fixas(destino)}
            contas = fixas(origem)
            novas = [g for g in contas if chave(g) not in existentes]
            previa_titulo.configure(text=f"Contas fixas de {nome_mes(origem)}")
            for w in previa.winfo_children():
                w.destroy()
            if not contas:
                ctk.CTkLabel(previa, text="Nenhuma conta fixa neste mês.",
                             text_color=SUB, font=self.ft_pequena).pack(anchor="w")
            for g in contas:
                repetida = chave(g) not in {chave(x) for x in novas}
                ctk.CTkLabel(
                    previa, anchor="w", font=self.ft_pequena,
                    text_color=SUB if repetida else TEXTO,
                    text=(f"{rotulo_categoria(g)}  ·  dia {dia_de_data(g['data']):02d}  ·  "
                          f"{formatar_moeda(g['valor'])}"
                          + ("   (já existe no destino)" if repetida else ""))).pack(
                    fill="x", anchor="w")
            if origem == destino:
                resumo.configure(text="Escolha meses diferentes para origem e destino.")
            elif not novas:
                resumo.configure(text=f"Nada novo para copiar para {nome_mes(destino)}.")
            else:
                total = sum(g["valor"] for g in novas)
                resumo.configure(
                    text=f"Copiar {len(novas)} conta(s) ({formatar_moeda(total)}) de "
                         f"{nome_mes(origem)} → {nome_mes(destino)}.")
            btn_copiar.configure(state="normal" if novas and origem != destino
                                 else "disabled")

        def confirmar():
            origem, destino = estado["origem"], estado["destino"]
            copiadas = self._executar_copia_contas(origem, destino)
            dlg.destroy()
            self.mes_atual = destino  # mostra o resultado
            self._sincronizar_mes()
            if copiadas:
                self._toast(f"{copiadas} conta(s) copiada(s) de {nome_mes(origem)} "
                            f"para {nome_mes(destino)}.", "sucesso")
            else:
                self._toast("Nenhuma conta nova para copiar.", "info")

        trocar_modo("origem")

    def _executar_copia_contas(self, origem, destino):
        existentes = {
            (g["descricao"].strip().lower(), rotulo_categoria(g))
            for g in self.gastos if mes_do_gasto(g) == destino
        }
        ano, mes = (int(x) for x in destino.split("-"))
        ultimo_dia = calendar.monthrange(ano, mes)[1]

        copiadas = 0
        for gasto in list(self.gastos):
            if mes_do_gasto(gasto) != origem:
                continue
            if not e_conta_fixa(gasto):
                continue
            chave = (gasto["descricao"].strip().lower(), rotulo_categoria(gasto))
            if chave in existentes:
                continue
            dia = min(dia_de_data(gasto.get("data", "")), ultimo_dia)
            copia = {
                "data": f"{dia:02d}/{mes:02d}/{ano:04d}",
                "descricao": gasto["descricao"],
                "categoria": gasto["categoria"],
                "cartao": gasto.get("cartao", CARTAO_PADRAO),
                "valor": gasto["valor"],
            }
            if "instituicao" in gasto:
                copia["instituicao"] = gasto["instituicao"]
            self.gastos.append(copia)
            existentes.add(chave)
            copiadas += 1

        if copiadas:
            salvar_dados(self.orcamentos, self.gastos, self.rendas)
            self._sincronizar_mes()
        return copiadas

    # ---------------------------------------------------------- atualização ---
    def _atualizar_tudo(self):
        self._atualizar_lista()
        self._atualizar_progresso()
        self._atualizar_graficos()
        self._atualizar_evolucao()
        self._atualizar_poupancas()

    def _estilizar_eixo(self, fig, ax, titulo, tamanho=12, rotulos=9, pad=10):
        """Limpa o eixo e aplica o estilo dos gráficos de barras/linhas do app."""
        self._preparar_ax(fig, ax)
        ax.clear()
        ax.set_title(titulo, fontsize=tamanho, fontweight="bold", color=_cor(TEXTO),
                     pad=pad)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(_cor(BORDA))
        ax.tick_params(left=False, labelleft=False, bottom=False)
        ax.tick_params(axis="x", labelsize=rotulos, colors=_cor(TEXTO))
        ax.yaxis.grid(True, color=_cor(GRID), zorder=0)

    def _atualizar_poupancas(self):
        meses, saldo, movimento = acumulado_poupancas(self.gastos, self.rendas,
                                                      ate=self.mes_atual)
        texto, sub = _cor(TEXTO), _cor(SUB)
        nomes = {"reserva": "Reserva de Emergência", "investimentos": "Investimentos"}

        # ---- resumo no mês exibido ----
        k = bisect.bisect_right(meses, self.mes_atual) - 1  # último mês até o exibido
        reserva, invest = (saldo[n][k] if k >= 0 else 0.0 for n in POUPANCAS)
        no_mes = k >= 0 and meses[k] == self.mes_atual
        mov_mes = {n: movimento[n][k] if no_mes else 0.0 for n in POUPANCAS}
        guardado = sum(mov_mes.values())
        # quantos meses de gastos a reserva cobre (sem contar o que foi guardado)
        categorias_poupanca = {cat for cat, _ in POUPANCAS.values()}
        gasto_por_mes = {}
        for g in self.gastos:
            m = mes_do_gasto(g)
            if m and g["categoria"] not in categorias_poupanca:
                gasto_por_mes[m] = gasto_por_mes.get(m, 0.0) + g["valor"]
        media = sum(gasto_por_mes.values()) / len(gasto_por_mes) if gasto_por_mes else 0
        cobertura = (f"cobre {reserva / media:.1f} meses de gastos".replace(".", ",")
                     if media and reserva > 0 else "guarde para cobrir imprevistos")
        dados = [
            (formatar_moeda(reserva), cobertura),
            (formatar_moeda(invest), f"no mês: {formatar_moeda(mov_mes['investimentos'])}"),
            (formatar_moeda(reserva + invest), f"até {nome_mes(self.mes_atual)}"),
            (formatar_moeda(guardado), "aportes menos resgates"),
        ]
        for (valor, legenda), (texto_valor, texto_legenda) in zip(self.poupanca_tiles, dados):
            valor.configure(text=texto_valor)
            legenda.configure(text=texto_legenda)

        def estilizar(fig, ax, titulo):
            self._estilizar_eixo(fig, ax, titulo)
            if not meses:
                ax.text(0.5, 0.5, "Lance gastos nas categorias Reserva de Emergência ou "
                        "Investimentos para acompanhar aqui", ha="center", va="center",
                        color=sub, fontsize=10, transform=ax.transAxes)
                ax.axis("off")
                return False
            x = list(range(len(meses)))
            passo = max(1, len(meses) // 12)  # muitos meses: não amontoa os rótulos
            ax.set_xticks(x[::passo])
            ax.set_xticklabels([label_mes_curto(m) for m in meses][::passo])
            return True

        # ---- gráfico 1: acumulado ----
        if estilizar(self.fig_acum, self.ax_acum, "Acumulado mês a mês"):
            x = list(range(len(meses)))
            for nome, serie in saldo.items():
                cor = CATEGORIA_CORES[nomes[nome]]
                # o valor atual vai na legenda: rótulos no fim das linhas se sobrepõem
                self.ax_acum.plot(x, serie, color=cor, linewidth=2.4, marker="o",
                                  markersize=4, zorder=4,
                                  label=f"{nomes[nome]}\n{formatar_moeda(serie[-1])}")
                self.ax_acum.fill_between(x, serie, color=cor, alpha=0.15, zorder=3)
            valores = saldo["reserva"] + saldo["investimentos"]
            self.ax_acum.set_ylim(min(min(valores), 0) * 1.15, max(max(valores), 1) * 1.15)
            self.ax_acum.axhline(0, color=_cor(BORDA), linewidth=1, zorder=2)
            self.ax_acum.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                                frameon=False, fontsize=9, labelspacing=1.2,
                                labelcolor=texto)
        self.canvas_acum.draw()

        # ---- gráfico 2: aportes e resgates ----
        if estilizar(self.fig_aportes, self.ax_aportes, "Aportes e resgates por mês"):
            x = list(range(len(meses)))
            largura = 0.38
            for k, (nome, serie) in enumerate(movimento.items()):
                deslocamento = (k - 0.5) * largura
                self.ax_aportes.bar([xi + deslocamento for xi in x], serie, width=largura,
                                    color=CATEGORIA_CORES[nomes[nome]], zorder=3,
                                    label=nomes[nome])
            valores = movimento["reserva"] + movimento["investimentos"]
            self.ax_aportes.set_ylim(min(min(valores), 0) * 1.2, max(max(valores), 1) * 1.2)
            self.ax_aportes.axhline(0, color=_cor(BORDA), linewidth=1, zorder=2)
            self.ax_aportes.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
                                   frameon=False, fontsize=9, labelcolor=texto)
        self.canvas_aportes.draw()

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
                    descricao_parcela(gasto) if gasto.get("compra")
                    else rotulo_categoria(gasto),
                    cartao,
                    formatar_moeda(gasto["valor"]),
                ),
                tags=(zebra, f"g_{indice}"),
            )
            posicao += 1

        salario = self.orcamento_do_mes()
        por_app, outras_rendas = totais_renda(self.rendas_do_mes())
        orcamento = salario + outras_rendas + sum(por_app.values())
        total_geral = sum(g["valor"] for g in self.gastos_do_mes())
        restante = orcamento - total_geral

        self.card_salario_valor.configure(text=formatar_moeda(salario))
        self.card_renda_valor.configure(text=formatar_moeda(outras_rendas))
        self._atualizar_cards_apps(por_app)
        self.card_orc_valor.configure(text=formatar_moeda(orcamento))
        self.card_gasto_valor.configure(text=formatar_moeda(total_geral))
        self.card_rest_valor.configure(text=formatar_moeda(restante))
        if restante >= 0:
            self.card_rest_valor.configure(text_color=COR_POS)
            self.card_rest_titulo.configure(text="RESTANTE")
        else:
            self.card_rest_valor.configure(text_color=COR_NEG)
            self.card_rest_titulo.configure(text="ESTOUROU")

    def _atualizar_cards_apps(self, por_app):
        """Um card por app com renda no mês, quebrando linha a cada COLUNAS_ENTRADAS."""
        apps = tuple(app for app, valor in por_app.items() if valor > 0)
        if apps != self._apps_nos_cards:
            for rotulo in self.card_app_valor.values():
                rotulo.master.destroy()
            self.card_app_valor = {}
            for n, app in enumerate(apps, start=2):  # 0 e 1: salário e rendas
                linha, coluna = divmod(n, COLUNAS_ENTRADAS)
                self.card_app_valor[app] = self._criar_card(
                    self.entradas, coluna, "🛵", app.upper(), COR_RENDA,
                    compacto=True, logo=self._logos_cards[app], linha=linha)
            self._apps_nos_cards = apps
        for app, rotulo in self.card_app_valor.items():
            rotulo.configure(text=formatar_moeda(por_app[app]))

    def _atualizar_progresso(self):
        disponivel = self.disponivel_do_mes()
        total_gasto = sum(g["valor"] for g in self.gastos_do_mes())
        pct = (total_gasto / disponivel * 100) if disponivel > 0 else 0
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
        card = _cor(CARD)

        # ---- rosca (donut): gastos por categoria ----
        self._preparar_ax(self.fig_pizza, self.ax_pizza)
        self.ax_pizza.clear()
        self.ax_pizza.set_title("Gastos por categoria", fontsize=13,
                                fontweight="bold", color=texto, pad=10)
        if totais:
            labels = list(totais.keys())
            valores = list(totais.values())
            cores = [cor_categoria(l) for l in labels]
            total = sum(valores)
            restante = self.disponivel_do_mes() - total
            if restante > 0:
                labels.append("Restante")
                valores.append(restante)
                cores.append(COR_RESTANTE)
            wedges, _t, pcts = self.ax_pizza.pie(
                valores, colors=cores, startangle=90, counterclock=False,
                autopct=lambda p: f"{p:.0f}%" if p >= 7 else "",
                pctdistance=0.79,
                wedgeprops={"width": 0.42, "edgecolor": card, "linewidth": 2},
                textprops={"fontsize": 9, "color": "white", "fontweight": "bold"},
            )
            self.ax_pizza.text(0, 0, f"Gasto\n{formatar_moeda(total)}",
                               ha="center", va="center", fontsize=11,
                               fontweight="bold", color=texto)
            legenda_com_logos(self.ax_pizza, wedges, labels, altura=2.2, fundo=card,
                              loc="center left", bbox_to_anchor=(1.02, 0.5),
                              ncol=-(-len(labels) // 9), frameon=False,
                              fontsize=8.5, handlelength=1, columnspacing=1,
                              labelcolor=texto)
            logos = [logo_da_fatia(l) for l in labels]
            for i in imagens_nas_fatias(self.ax_pizza, wedges, logos):
                # o logo ocupa o meio da fatia: a porcentagem vai para fora do anel
                angulo = np.deg2rad((wedges[i].theta1 + wedges[i].theta2) / 2)
                x, y = np.cos(angulo), np.sin(angulo)
                pcts[i].set_position((1.16 * x, 1.16 * y))
                pcts[i].set_color(texto)
                pcts[i].set_ha("left" if x > 0.2 else "right" if x < -0.2 else "center")
        else:
            self.ax_pizza.text(0.5, 0.5, "Sem gastos ainda", ha="center",
                               va="center", color=sub, fontsize=10)
            self.ax_pizza.axis("off")
        self.canvas_pizza.draw()

        # ---- barras: orçamento x gasto x restante ----
        renda = self.renda_do_mes()
        total_gasto = sum(g["valor"] for g in gastos_mes)
        restante = orcamento + renda - total_gasto
        self._estilizar_eixo(self.fig_barras, self.ax_barras,
                             "Salário, rendas, gasto e restante",
                             tamanho=10.5, rotulos=8.5, pad=8)
        itens = ["Salário", "Rendas", "Gasto", "Restante"]
        valores = [orcamento, renda, total_gasto, restante]
        cores = [COR_ORC, COR_RENDA, COR_GASTO,
                 COR_RESTANTE if restante >= 0 else COR_NEG]
        barras = self.ax_barras.bar(itens, valores, color=cores, width=0.62,
                                    zorder=3)
        maximo = max(valores + [1])
        minimo = min(valores + [0])
        self.ax_barras.set_ylim(min(minimo * 1.2, 0), maximo + maximo * 0.20)
        for barra, valor in zip(barras, valores):
            self.ax_barras.annotate(
                formatar_moeda(valor),
                xy=(barra.get_x() + barra.get_width() / 2, valor),
                xytext=(0, 4 if valor >= 0 else -4), textcoords="offset points",
                ha="center", va="bottom" if valor >= 0 else "top",
                fontsize=7.5, fontweight="bold", color=texto)
        self.canvas_barras.draw()

        # ---- rosca pequena: formas de pagamento, com emojis ----
        self._preparar_ax(self.fig_cartao, self.ax_cartao)
        self.ax_cartao.clear()
        cartoes = totais_por_cartao(gastos_mes)
        self.ax_cartao.set_title("Formas de pagamento", fontsize=10.5,
                                 fontweight="bold", color=texto, pad=8)
        if cartoes:
            nomes = sorted(cartoes, key=cartoes.get, reverse=True)
            vals = [cartoes[n] for n in nomes]
            wedges, _t = self.ax_cartao.pie(
                vals, colors=[CARTAO_CORES.get(n, "#94A3B8") for n in nomes],
                startangle=90, counterclock=False,
                wedgeprops={"width": 0.5, "edgecolor": card, "linewidth": 2})
            emojis = [imagem_emoji(CARTAO_EMOJI.get(n, "🧾")) for n in nomes]
            rotulos = [f"{n}  {formatar_moeda(v)}" for n, v in zip(nomes, vals)]
            legenda_com_logos(self.ax_cartao, wedges, rotulos,
                              imagem_de=dict(zip(rotulos, emojis)).get, altura=1.9,

                              loc="center left", bbox_to_anchor=(1.0, 0.5),
                              frameon=False, fontsize=8, handlelength=1,
                              labelcolor=texto)
            imagens_nas_fatias(self.ax_cartao, wedges, emojis, largura=0.5,
                               altura_pts=17)
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

        # ---- gráfico 1: gasto x orçamento por mês ----
        self._estilizar_eixo(self.fig_evol, self.ax_evol,
                             "Evolução: gasto x orçamento por mês")
        if meses:
            gasto_mes = [sum(por_mes[m].values()) for m in meses]
            orc_mes = [self.orcamentos.get(m, 0.0) + sum(
                r["valor"] for r in self.rendas if mes_do_gasto(r) == m)
                for m in meses]
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
        self._estilizar_eixo(self.fig_comp, self.ax_comp,
                             "Gastos por categoria ao longo dos meses")
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
                                 color=cor_categoria(cat),
                                 label=cat, zorder=3)
                base = [b + v for b, v in zip(base, vals)]
            restantes = [
                max(self.orcamentos.get(m, 0.0) + sum(
                    r["valor"] for r in self.rendas if mes_do_gasto(r) == m) - b, 0.0)
                for m, b in zip(meses, base)
            ]
            if any(restantes):
                self.ax_comp.bar(x, restantes, bottom=base, width=0.6,
                                 color=COR_RESTANTE, label="Restante",
                                 zorder=3)
                base = [b + v for b, v in zip(base, restantes)]
            self.ax_comp.set_xticks(x)
            self.ax_comp.set_xticklabels(labels)
            self.ax_comp.set_ylim(0, max(base + [1]) * 1.10)
            handles, nomes = self.ax_comp.get_legend_handles_labels()
            legenda_com_logos(self.ax_comp, handles, nomes, fundo=_cor(CARD),
                              loc="center left", bbox_to_anchor=(1.01, 0.5),
                              ncol=-(-len(nomes) // 7), frameon=False,
                              fontsize=7.5,
                              handlelength=1, columnspacing=1, labelcolor=texto)
        else:
            self.ax_comp.text(0.5, 0.5, "Sem dados para comparar", ha="center",
                              va="center", color=sub, fontsize=10)
            self.ax_comp.axis("off")
        self.canvas_comp.draw()


def main():
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    # className vira o WM_CLASS da janela: liga a janela ao atalho do menu (Linux)
    root = ctk.CTk(className="calculador-gastos")
    root.iconphoto(True, tk.PhotoImage(file=ICONE))
    CalculadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
