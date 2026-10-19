"""Persistência JSON com validação, migração de formatos antigos e gravação atômica."""

import json
import math
import os
import re
import uuid
from datetime import datetime

from dominio import mes_atual_chave, mes_do_gasto


def _numero(valor):
    """Aceita números JSON finitos e não negativos; bool não é dinheiro."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Valor monetário deve ser numérico.")
    try:
        finito = math.isfinite(valor)
    except OverflowError:
        finito = False
    if not finito or valor < 0:
        raise ValueError("Valor monetário deve ser finito e não negativo.")
    return valor


def _movimentos(itens, campo):
    if not isinstance(itens, list):
        raise ValueError("Lançamentos devem ser uma lista.")
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Lançamento deve ser um objeto.")
        if not isinstance(item.get(campo), str) or not item[campo].strip():
            raise ValueError(f"Lançamento sem {campo}.")
        _numero(item.get("valor"))
        # Só o tipo é exigido: versões anteriores aceitavam qualquer texto na data
        # (ex.: "31/02/2026"). Recusar aqui esconderia o arquivo inteiro; o app já
        # ignora datas inválidas nas contas e valida as datas novas na interface.
        if not isinstance(item.get("data"), str):
            raise ValueError("Data deve ser texto.")
        for chave in ("descricao", "cartao", "instituicao", "app", "caixinha", "compra"):
            if chave in item and not isinstance(item[chave], str):
                raise ValueError(f"{chave} deve ser texto.")
        if any(chave in item for chave in ("compra", "parcela", "parcelas")):
            parcela, parcelas = item.get("parcela"), item.get("parcelas")
            if (not isinstance(item.get("compra"), str) or not item["compra"]
                    or type(parcela) is not int or type(parcelas) is not int
                    or not 1 <= parcela <= parcelas <= 420):
                raise ValueError("Parcelamento inválido.")
    return itens


def _validar(dados):
    """Valida o conjunto inteiro: nenhum lançamento é descartado silenciosamente."""
    if isinstance(dados, list):
        return {}, _movimentos(dados, "categoria"), [], []
    if not isinstance(dados, dict):
        raise ValueError("A raiz do arquivo deve ser um objeto ou uma lista antiga.")
    gastos = _movimentos(dados.get("gastos", []), "categoria")
    rendas = _movimentos(dados.get("rendas", []), "fonte")
    caixinhas = dados.get("caixinhas", [])
    if not isinstance(caixinhas, list):
        raise ValueError("Caixinhas devem ser uma lista.")
    nomes = set()
    for cx in caixinhas:
        if (not isinstance(cx, dict) or not isinstance(cx.get("nome"), str)
                or not cx["nome"].strip() or cx["nome"] in nomes):
            raise ValueError("Caixinha inválida ou repetida.")
        nomes.add(cx["nome"])
        if "meta" in cx:
            _numero(cx["meta"])
    if "orcamentos" in dados:
        orcamentos = dados["orcamentos"]
        if not isinstance(orcamentos, dict):
            raise ValueError("Orçamentos devem ser um objeto.")
        for mes, valor in orcamentos.items():
            if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", mes) or mes.startswith("0000"):
                raise ValueError("Mês de orçamento inválido.")
            # Compatibilidade com valores numéricos em texto de arquivos anteriores.
            if isinstance(valor, str):
                try:
                    valor = float(valor)
                except ValueError:
                    raise ValueError("Orçamento inválido.") from None
            _numero(valor)
        return {mes: float(valor) for mes, valor in orcamentos.items()}, gastos, rendas, caixinhas
    valor = dados.get("orcamento", 0.0)
    if isinstance(valor, str):
        valor = float(valor)
    valor = _numero(valor)
    orcamentos = {mes_do_gasto(g) or mes_atual_chave(): float(valor) for g in gastos} if valor > 0 else {}
    return orcamentos, gastos, rendas, caixinhas


def carregar_dados(caminho, ao_preservar=None):
    """Lê formatos atuais/antigos. Preserva arquivo inválido antes de iniciar vazio.

    `ao_preservar(copia)` é chamado com o caminho da cópia quando o arquivo é
    guardado como corrompido, para a interface poder avisar o usuário.

    Erros de acesso e falhas ao preservar o original são propagados: retornar
    vazio nesses casos poderia permitir sobrescrever dados ainda não protegidos.
    """
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        return {}, [], [], []
    except (json.JSONDecodeError, UnicodeDecodeError):
        dados = None
    try:
        return _validar(dados)
    except (ValueError, TypeError, OverflowError):
        copia = f"{caminho}.corrompido-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
        os.replace(caminho, copia)
        if ao_preservar:
            ao_preservar(copia)
        return {}, [], [], []


def salvar_dados(caminho, orcamentos, gastos, rendas, caixinhas):
    """Valida antes de gravar e substitui o arquivo somente após flush/fsync."""
    dados = {"orcamentos": orcamentos, "gastos": gastos, "rendas": rendas, "caixinhas": caixinhas}
    _validar(dados)
    temporario = os.fspath(caminho) + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
