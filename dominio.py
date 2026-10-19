"""Cálculos e formatação independentes da interface e do armazenamento."""

import calendar
import itertools
import math
import re
import unicodedata
from datetime import date, datetime

from configuracao import (
    APPS_DELIVERY,
    CARTAO_PADRAO,
    CATEGORIA_CAIXINHA,
    CATEGORIA_CORES,
    CONTAS_FIXAS,
    FONTE_CAIXINHA,
    FONTE_DELIVERY,
    FONTE_PADRAO,
    INSTITUICOES,
    MAX_CENTAVOS,
    MESES_ABREV,
    MESES_PT,
    POUPANCAS,
    SUBCATEGORIAS
)

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
            _, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
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


def saldos_caixinhas(caixinhas, gastos, rendas):
    """{nome: guardado - retirado} de cada caixinha, na ordem em que foram criadas."""
    saldos = {cx["nome"]: 0.0 for cx in caixinhas}
    for item, sinal in [(g, 1) for g in gastos] + [(r, -1) for r in rendas]:
        if item.get("caixinha") in saldos:
            saldos[item["caixinha"]] += sinal * item["valor"]
    return saldos


def nome_de_caixinha(nome, caixinhas, atual=None):
    """(nome limpo, None) se puder usar, ou (None, erro). Não repete nome, sem
    ligar para maiúsculas/acentos; `atual` é o nome da caixinha sendo renomeada."""
    nome = " ".join(str(nome or "").split())[:40]
    if not nome:
        return None, "Erro: dê um nome para a caixinha."
    if any(_chave(cx["nome"]) == _chave(nome) and cx["nome"] != atual for cx in caixinhas):
        return None, f"Erro: já existe uma caixinha chamada {nome}."
    return nome, None


def movimento_caixinha(nome, valor, guardar, data_texto):
    """Guardar: gasto na categoria Caixinhas; retirar: renda de resgate."""
    item = {"data": data_texto, "valor": valor, "caixinha": nome,
            "descricao": f"Caixinha {nome}"}
    if guardar:
        item.update(categoria=CATEGORIA_CAIXINHA, cartao=CARTAO_PADRAO)
    else:
        item["fonte"] = FONTE_CAIXINHA
    return item


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


def subopcoes(gasto, escolha):
    """Opções do 2º seletor (banco/transporte do gasto, app do ganho), ou None."""
    if gasto:
        return SUBCATEGORIAS[escolha][2] if escolha in SUBCATEGORIAS else None
    return APPS_DELIVERY if escolha == FONTE_DELIVERY else None


def novo_lancamento(gasto, valor, data_texto, escolha, sub=None, cartao=None):
    """Monta o gasto (categoria, pagamento) ou a renda (fonte, app) de um dia."""
    item = {"data": data_texto, "valor": valor}
    if gasto:
        item.update(categoria=escolha, cartao=cartao or CARTAO_PADRAO)
        if sub:
            item["instituicao"] = sub
        item["descricao"] = rotulo_categoria(item)
    else:
        item.update(descricao=sub or escolha, fonte=escolha)
        if sub:
            item["app"] = sub
    return item


def _chave(texto):
    """Texto para comparar: sem acentos, minúsculas, sem espaços nas pontas."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().casefold().strip()


def valor_digitado(texto):
    """Valor escrito à mão (sem a máscara dos campos): "3.500,50", "3500,5",
    "3500.50" e "3.500" -> float; None se não for número."""
    texto = texto.strip().removeprefix("R$").strip()
    if "," not in texto and re.fullmatch(r"\d+\.\d{1,2}", texto):
        valor = float(texto)  # ponto seguido de 1-2 casas: decimal
        return valor if math.isfinite(valor) else None
    try:
        valor = float(texto.replace(".", "").replace(",", "."))
        return valor if math.isfinite(valor) else None
    except ValueError:
        return None


def totais_por_dia(itens):
    """{date: soma dos valores} dos gastos ou rendas (datas inválidas ficam de fora)."""
    totais = {}
    for item in itens:
        try:
            dia = datetime.strptime(item["data"].strip(), "%d/%m/%Y").date()
        except (KeyError, ValueError):
            continue
        totais[dia] = totais.get(dia, 0.0) + item["valor"]
    return totais


