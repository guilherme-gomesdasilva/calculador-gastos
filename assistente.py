"""Ferramentas, validação de mensagens e cliente HTTP do Ollama."""

import difflib
import json
import os
import re
import urllib.request
from datetime import date, datetime

from configuracao import (
    APPS_DELIVERY,
    CARTOES,
    CATEGORIAS_DIA,
    FONTES_RENDA,
    MAX_CENTAVOS,
    MESES_ABREV,
    MESES_PT
)

from dominio import (
    _chave,
    mes_de_data,
    mes_do_gasto,
    novo_lancamento,
    subopcoes
)

OLLAMA_URL = os.environ.get("CALCULADOR_OLLAMA_URL", "http://localhost:11434").rstrip("/")


OLLAMA_MODELO = os.environ.get("CALCULADOR_OLLAMA_MODELO", "qwen2.5-coder:14b")


MAX_RODADAS = 4  # tentativas do modelo (ex.: corrigir categoria inválida) por mensagem


FERRAMENTA_LANCAR = {"type": "function", "function": {
    "name": "lancar",
    "description": "Registra no app um gasto ou um ganho que o usuário contou. Uma "
                   "chamada por item: \"12 de uber e 6 de ônibus\" são duas. Ganho em app "
                   "(iFood, Uber, 99...) é categoria Delivery / Apps com o app em detalhe.",
    "parameters": {"type": "object", "required": ["tipo", "valor", "categoria"], "properties": {
        "tipo": {"type": "string", "enum": ["gasto", "ganho"]},
        "valor": {"type": "number", "description": "valor em reais, ex.: 25.9"},
        "data": {"type": "string", "description": "dd/mm/aaaa; omita para hoje"},
        "categoria": {"type": "string", "description":
                      "gasto: uma de " + ", ".join(CATEGORIAS_DIA)
                      + ". ganho: uma de " + ", ".join(FONTES_RENDA)},
        "detalhe": {"type": "string", "description":
                    "obrigatório em Fatura de Cartão (banco), Transporte (tipo) e "
                    "Delivery / Apps (app: " + ", ".join(APPS_DELIVERY) + ")"},
        "pagamento": {"type": "string", "enum": CARTOES},
    }}}}


FERRAMENTA_SALARIO = {"type": "function", "function": {
    "name": "salario",
    "description": "Define o salário do mês (troca o que havia). Salário não é ganho: "
                   "use esta ferramenta, nunca lancar, quando o usuário falar de salário. "
                   "Para apagar o salário use limpar com oque=salario.",
    "parameters": {"type": "object", "required": ["valor"], "properties": {
        "valor": {"type": "number", "description": "valor em reais, ex.: 2800"},
        "mes": {"type": "string", "description": "mm/aaaa; omita para o mês aberto no app"},
    }}}}


def _ferramenta(nome, descricao, propriedades=None, obrigatorios=()):
    return {"type": "function", "function": {
        "name": nome, "description": descricao,
        "parameters": {"type": "object", "required": list(obrigatorios),
                       "properties": propriedades or {}}}}


_MES = {"type": "string", "description": "mm/aaaa; omita para o mês aberto no app"}


FERRAMENTAS = [
    FERRAMENTA_LANCAR,
    FERRAMENTA_SALARIO,
    _ferramenta("limpar", "Apaga de uma vez os gastos, as rendas extras ou o salário de "
                "um mês. O app pede confirmação ao usuário.",
                {"oque": {"type": "string", "enum": ["gastos", "rendas", "salario"]},
                 "mes": _MES}, ["oque"]),
    _ferramenta("remover", "Apaga UM lançamento do mês (gasto ou ganho), achado pelo "
                "valor e/ou pelo texto (categoria, app, fonte). O app pede confirmação.",
                {"tipo": {"type": "string", "enum": ["gasto", "ganho"]},
                 "valor": {"type": "number"},
                 "texto": {"type": "string", "description": "ex.: uber, ifood, luz"},
                 "data": {"type": "string", "description": "dd/mm/aaaa, se o usuário disse"},
                 "mes": _MES}),
    _ferramenta("mudar_mes", "Mostra outro mês no app (para ver ou mexer nele).",
                {"mes": {"type": "string", "description": "mm/aaaa"}}, ["mes"]),
    _ferramenta("copiar_contas_fixas", "Abre a janela do app que copia as contas fixas "
                "(aluguel, luz...) de um mês para outro e lança parcelas futuras."),
    _ferramenta("criar_caixinha", "Cria uma caixinha (objetivo com nome, ex.: Viagem), "
                "com meta e primeiro valor guardado opcionais.",
                {"nome": {"type": "string"},
                 "meta": {"type": "number", "description": "meta em reais; omita se não houver"},
                 "guardar": {"type": "number", "description":
                             "valor para já guardar nela; omita se o usuário não disse"}},
                ["nome"]),
    _ferramenta("caixinha", "Guarda dinheiro numa caixinha ou retira dela. Não use lancar "
                "para caixinha.",
                {"acao": {"type": "string", "enum": ["guardar", "retirar"]},
                 "nome": {"type": "string", "description": "nome da caixinha"},
                 "valor": {"type": "number"}}, ["acao", "nome", "valor"]),
    _ferramenta("meta_caixinha", "Muda a meta de uma caixinha; meta 0 tira a meta.",
                {"nome": {"type": "string"}, "meta": {"type": "number"}}, ["nome", "meta"]),
    _ferramenta("renomear_caixinha", "Troca o nome de uma caixinha.",
                {"nome": {"type": "string"}, "novo_nome": {"type": "string"}},
                ["nome", "novo_nome"]),
    _ferramenta("excluir_caixinha", "Exclui uma caixinha vazia (o app pede confirmação).",
                {"nome": {"type": "string"}}, ["nome"]),
]


PEDE_CRIAR = ("cri", "abre", "abrir", "abra", "nova", "novo", "faz", "faca", "fazer")


PEDE_RENOMEAR = ("renome", "nome", "chama")


def ferramentas_para(texto, caixinhas=()):
    """Só oferece ao modelo o que pode passar nas checagens: lançar, salário e
    guardar pedem um valor escrito; limpar, remover e excluir pedem "apagar". Numa
    pergunta sobram mudar_mes e copiar_contas_fixas (e criar/renomear caixinha, se
    ela for citada), e o modelo responde com texto."""
    if numeros_do_texto(texto) or pede_para_apagar(texto):
        return FERRAMENTAS
    nomes = {"mudar_mes", "copiar_contas_fixas"}
    chave = _chave(texto)
    if "caixinh" in chave and any(p in chave for p in PEDE_CRIAR):
        nomes.add("criar_caixinha")
    citou = "caixinh" in chave or any(_chave(cx["nome"]) in chave for cx in caixinhas)
    if citou and any(p in chave for p in PEDE_RENOMEAR):
        nomes.add("renomear_caixinha")
    return [f for f in FERRAMENTAS if f["function"]["name"] in nomes]


def _achar(texto, opcoes):
    """A opção igual ao texto (sem ligar para maiúsculas/acentos); se não houver,
    a única que o contém ("uber" -> "Uber / 99"), a única contida nele
    ("Transporte - Ônibus" -> "Transporte") ou a mais parecida, para erro de
    digitação ("trasporte" -> "Transporte"); senão None."""
    chave = _chave
    procurado = chave(texto)
    if not procurado:
        return None
    iguais = [o for o in opcoes if chave(o) == procurado]
    contem = [o for o in opcoes if procurado in chave(o)]
    dentro = [o for o in opcoes if chave(o) in procurado]
    for achadas in (iguais, contem, dentro):
        if len(achadas) == 1 or (achadas is iguais and achadas):
            return achadas[0]
    por_chave = {chave(o): o for o in opcoes}
    parecida = difflib.get_close_matches(procurado, list(por_chave), n=1, cutoff=0.8)
    return por_chave[parecida[0]] if parecida else None


def numeros_do_texto(texto):
    """Valores que aparecem no texto: "25", "12,50", "1.200", "12.5" (ambos os
    jeitos) e "2 mil", "2,8 mil", "3k"."""
    valores = set()
    for n, mil in re.findall(r"(\d+(?:[.,]\d+)*)\s*(mil\b|k\b)?", texto.lower()):
        for convertido in (n.replace(".", "").replace(",", "."), n.replace(",", "")):
            try:
                valores.add(round(float(convertido) * (1000 if mil else 1), 2))
            except ValueError:  # "1.2.3" no jeito americano
                pass
    return valores


def _valor_do_modelo(args, texto_usuario, minimo=0.01):
    """Valor que o modelo mandou, se for válido e estiver escrito pelo usuário
    (o modelo não inventa quanto foi); senão um texto de erro."""
    try:
        valor = round(float(args.get("valor")), 2)
    except (TypeError, ValueError):
        return "Erro: valor deve ser um número."
    if not minimo <= valor <= MAX_CENTAVOS / 100:
        return "Erro: valor fora do permitido."
    if texto_usuario is not None and valor not in numeros_do_texto(texto_usuario):
        return ("Erro: o usuário não escreveu esse valor. Não salve; pergunte quanto foi "
                "(em números).")
    return valor


def salario_do_assistente(args, mes_padrao, texto_usuario=None):
    """Valida "salario": retorna (mês "AAAA-MM", valor) ou um texto de erro."""
    if args.get("valor") in (0, "0"):
        return "Erro: para apagar o salário use a ferramenta limpar com oque=salario."
    valor = _valor_do_modelo(args, texto_usuario)
    if isinstance(valor, str):
        return valor
    mes = mes_do_modelo(args, mes_padrao)
    return (mes, valor) if mes else "Erro: mes deve ser mm/aaaa."


def pede_para_apagar(texto):
    """O usuário pediu para apagar algo? (limpar/remover só rodam se sim)"""
    return any(v in _chave(texto) for v in
               ("apag", "remov", "tir", "limp", "exclu", "delet", "zer", "desfaz"))


def mes_do_modelo(args, mes_padrao):
    """Mês dos argumentos -> "AAAA-MM": aceita "09/2026", "2026-09", "setembro",
    "setembro de 2026" e "set" (sem ano: o atual); sem mês, o padrão; inválido, None."""
    texto = _chave(args.get("mes") or "")
    if not texto:
        return mes_padrao
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})", texto):
        return mes_de_data(f"01/{m[2]}/{m[1]}")
    for i, (nome, abrev) in enumerate(zip(MESES_PT, MESES_ABREV)):
        if texto.startswith(abrev) or _chave(nome) in texto:
            ano = re.search(r"\d{4}", texto)
            return f"{int(ano[0]) if ano else date.today().year:04d}-{i + 1:02d}"
    return mes_de_data("01/" + texto)


def achar_lancamentos(gastos, rendas, args, mes):
    """Lançamentos do mês que batem com o pedido de "remover": [("g"|"r", índice)].

    Filtra por tipo, valor, data e texto (na categoria, descrição, app, fonte);
    pede pelo menos valor ou texto, para não achar o mês inteiro.
    """
    texto, valor = _chave(args.get("texto", "")), args.get("valor")
    if not texto and valor in (None, ""):
        return []
    tipos = {"gasto": ["g"], "ganho": ["r"]}.get(str(args.get("tipo", "")).lower(), ["g", "r"])
    achados = []
    for tipo in tipos:
        for i, item in enumerate(gastos if tipo == "g" else rendas):
            if mes_do_gasto(item) != mes or (args.get("data") and item["data"] != args["data"]):
                continue
            try:
                if valor not in (None, "") and round(float(valor), 2) != item["valor"]:
                    continue
            except (TypeError, ValueError):
                return []
            campos = " ".join(str(item.get(k, "")) for k in
                              ("categoria", "descricao", "instituicao", "app", "fonte"))
            if texto and texto not in _chave(campos):
                continue
            achados.append((tipo, i))
    return achados


def lancamento_do_assistente(args, texto_usuario=None):
    """Valida os argumentos que o modelo mandou para "lancar" (não confia nele).

    Com `texto_usuario`, o valor precisa estar escrito nele: o modelo não inventa
    quanto foi. Retorna (gasto: bool, item) pronto para salvar, ou um texto de
    erro que volta para o modelo corrigir.
    """
    tipo = str(args.get("tipo", "")).lower()
    # o modelo às vezes troca o tipo ("fiz 250 no ifood" virou gasto): categoria
    # que só existe de um lado (Delivery / Apps, Transporte...) decide
    categoria = args.get("categoria", "")
    e_gasto, e_ganho = _achar(categoria, CATEGORIAS_DIA), _achar(categoria, FONTES_RENDA)
    if bool(e_gasto) != bool(e_ganho):
        tipo = "gasto" if e_gasto else "ganho"
    if tipo not in ("gasto", "ganho"):
        return "Erro: tipo deve ser gasto ou ganho."
    valor = _valor_do_modelo(args, texto_usuario)
    if isinstance(valor, str):
        return valor
    try:
        dia = datetime.strptime(args.get("data") or date.today().strftime("%d/%m/%Y"),
                                "%d/%m/%Y")
    except (TypeError, ValueError):
        return "Erro: data deve ser dd/mm/aaaa."
    gasto = tipo == "gasto"
    opcoes = CATEGORIAS_DIA if gasto else FONTES_RENDA
    escolha = _achar(categoria, opcoes)
    if not escolha:
        return "Erro: categoria deve ser uma de: " + ", ".join(opcoes)
    subs = subopcoes(gasto, escolha)
    sub = _achar(args.get("detalhe", ""), subs) if subs else None
    if subs and not sub:
        return f"Erro: para {escolha}, detalhe deve ser um de: " + ", ".join(subs)
    cartao = _achar(args.get("pagamento", ""), CARTOES) if gasto else None
    return gasto, novo_lancamento(gasto, valor, dia.strftime("%d/%m/%Y"), escolha, sub, cartao)


def chamadas_de_ferramenta(msg):
    """tool_calls da resposta; modelos como o qwen2.5-coder às vezes escrevem a
    chamada como JSON no texto ({"name": ..., "arguments": ...}): vale também."""
    if msg.get("tool_calls"):
        return msg["tool_calls"]
    texto, decoder, chamadas, i = msg.get("content") or "", json.JSONDecoder(), [], 0
    while (i := texto.find("{", i)) != -1:  # um ou mais objetos JSON no meio do texto
        try:
            obj, fim = decoder.raw_decode(texto, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
            chamadas.append({"function": obj})
        i = fim
    if chamadas:
        msg["content"] = ""  # não mostra o JSON (nem o texto em volta) como resposta
    return chamadas


def chamar_ollama(corpo):
    """POST em /api/chat (roda fora da interface); devolve a mensagem ou a exceção."""
    pedido = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(corpo).encode(),
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=300) as resposta:
            return json.load(resposta)["message"]
    except (OSError, ValueError, KeyError) as erro:  # sem Ollama, modelo ausente, timeout
        return erro


