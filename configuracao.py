"""Categorias, opções e paleta compartilhadas, sem dependências de interface."""

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


POUPANCAS = {
    "reserva": ("Reserva de Emergência", "Resgate da Reserva"),
    "investimentos": ("Investimentos", "Resgate de Investimentos"),
}


CATEGORIA_CAIXINHA = "Caixinhas"


FONTE_CAIXINHA = "Resgate de Caixinha"


CATEGORIA_CORES[CATEGORIA_CAIXINHA] = "#FACC15"


CATEGORIA_PARCELAMENTO = "Parcelamento de Compras"


OUTRA_QUANTIDADE = "Outra…"


CATEGORIAS_PARCELADAS = {
    CATEGORIA_PARCELAMENTO: ([f"{n}x" for n in (2, 3, 4, 5, 6, 10, 12)], 48),
    "Financiamento/Empréstimo": ([f"{n}x" for n in (12, 24, 36, 48)], 420),
}


CATEGORIAS_DIA = [c for c in CATEGORIAS if c not in CATEGORIAS_PARCELADAS]


def quantidade_parcelas(texto, maximo):
    """'12x' ou '12' -> 12, se estiver entre 2 e `maximo`; senão None."""
    texto = (texto or "").strip().lower().removesuffix("x").strip()
    if not texto.isdigit():
        return None
    n = int(texto)
    return n if 2 <= n <= maximo else None


CONTAS_FIXAS = [
    "Aluguel",
    "Luz",
    "Água",
    "Gás",
    "Internet/Telefone",
    "Educação",
    "Financiamento/Empréstimo",
]


CARTOES = outros_por_ultimo([
    "Dinheiro",
    "Pix",
    "Débito",
    "Cartão de Crédito",
    "Outro",
])


CARTAO_PADRAO = "Outro"


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


SUBCATEGORIAS = {
    CATEGORIA_FATURA: ("Fatura ", "INSTITUIÇÃO", INSTITUICOES),
    CATEGORIA_TRANSPORTE: ("Transporte - ", "TIPO DE TRANSPORTE",
                           INSTITUICOES_TRANSPORTE),
}


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


CARTAO_EMOJI = {
    "Dinheiro": "💵",
    "Pix": "💠",
    "Débito": "🏧",
    "Cartão de Crédito": "💳",
    "Outro": "🧾",
}


FONTES_EMOJI = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/google-noto-color-emoji/NotoColorEmoji.ttf",
    "C:/Windows/Fonts/seguiemj.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
]


CARTAO_CORES = {
    "Dinheiro": "#22C55E",
    "Pix": "#06B6D4",
    "Débito": "#6366F1",
    "Cartão de Crédito": "#EC4899",
    "Outro": "#94A3B8",
}


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


MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


MESES_ABREV = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


MAX_CENTAVOS = 99_999_999_999  # R$ 999.999.999,99: limite dos campos de dinheiro


