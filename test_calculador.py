"""Checagens da camada de dados. Rode com: .venv/bin/python test_calculador.py"""

import json
import os
import tempfile

import matplotlib.image as mpimg

import calculador as c


def _usar_arquivo_temporario():
    caminho = os.path.join(tempfile.mkdtemp(), "gastos.json")
    c.DATA_FILE = caminho
    return caminho


def test_ida_e_volta():
    _usar_arquivo_temporario()
    rendas = [{"data": "10/09/2026", "descricao": "Site",
               "fonte": "Freelance", "valor": 800.0}]
    c.salvar_dados({"2026-09": 3000.0}, [], rendas)
    orcamentos, gastos, lidas = c.carregar_dados()
    assert orcamentos == {"2026-09": 3000.0}
    assert gastos == []
    assert lidas == rendas


def test_formatos_antigos_sem_rendas():
    caminho = _usar_arquivo_temporario()
    gasto = {"data": "05/08/2026", "descricao": "Aluguel",
             "categoria": "Aluguel", "cartao": "Pix", "valor": 1400.0}

    # formato antigo: lista pura de gastos
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump([gasto], f)
    assert c.carregar_dados() == ({}, [gasto], [])

    # formato anterior: orçamento único, aplicado ao mês do gasto
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"orcamento": 2500.0, "gastos": [gasto]}, f)
    orcamentos, gastos, rendas = c.carregar_dados()
    assert orcamentos == {"2026-08": 2500.0}
    assert gastos == [gasto] and rendas == []


def test_arquivo_ausente_ou_corrompido():
    caminho = _usar_arquivo_temporario()
    assert c.carregar_dados() == ({}, [], [])
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("{ isso não é json")
    assert c.carregar_dados() == ({}, [], [])


def test_fatura_por_instituicao():
    nubank = {"categoria": "Fatura de Cartão", "instituicao": "Nubank", "valor": 300.0}
    itau = {"categoria": "Fatura de Cartão", "instituicao": "Itaú", "valor": 200.0}
    antiga = {"categoria": "Fatura de Cartão", "valor": 50.0}  # sem instituição
    luz = {"categoria": "Luz", "valor": 100.0}

    assert c.totais_por_categoria([nubank, itau, antiga, luz, nubank]) == {
        "Fatura Nubank": 600.0, "Fatura Itaú": 200.0,
        "Fatura de Cartão": 50.0, "Luz": 100.0,
    }
    assert c.cor_categoria("Fatura Nubank") == c.INSTITUICOES["Nubank"]
    assert c.cor_categoria("Fatura de Cartão") == c.CATEGORIA_CORES["Fatura de Cartão"]
    assert c.cor_categoria("Luz") == c.CATEGORIA_CORES["Luz"]


def test_transporte_por_tipo():
    onibus = {"categoria": "Transporte", "instituicao": "Ônibus", "valor": 40.0}
    uber = {"categoria": "Transporte", "instituicao": "Uber / 99", "valor": 60.0}
    antigo = {"categoria": "Transporte", "valor": 10.0}  # sem tipo
    assert c.totais_por_categoria([onibus, uber, antigo, onibus]) == {
        "Transporte - Ônibus": 80.0, "Transporte - Uber / 99": 60.0,
        "Transporte": 10.0,
    }
    assert c.cor_categoria("Transporte - Uber / 99") == \
        c.INSTITUICOES_TRANSPORTE["Uber / 99"]
    assert c.cor_categoria("Transporte") == c.CATEGORIA_CORES["Transporte"]
    assert c.instituicao_do_rotulo("Transporte - Ônibus") is None  # sem logo


def test_logos():
    c.LOGOS_DIR = tempfile.mkdtemp()
    c.imagem_logo.cache_clear()
    assert c.arquivo_logo("Banco do Brasil").endswith("banco-do-brasil.png")
    assert c.arquivo_logo("Itaú").endswith("itau.png")
    assert c.arquivo_logo("Zé Delivery").endswith("ze-delivery.png")
    assert c.arquivo_logo("Amazon Flex").endswith("amazon-flex.png")
    assert c.instituicao_do_rotulo("Fatura Itaú") == "Itaú"
    assert c.instituicao_do_rotulo("Fatura de Cartão") is None
    assert c.instituicao_do_rotulo("Nubank") is None

    assert c.imagem_logo("Nubank") is None  # sem arquivo: fica só a cor
    with open(c.arquivo_logo("Inter"), "w") as f:
        f.write("não é png")
    assert c.imagem_logo("Inter") is None   # arquivo inválido não quebra

    mpimg.imsave(c.arquivo_logo("Itaú"), [[[1.0, 0.5, 0.0]] * 4] * 2)
    assert c.imagem_logo("Itaú").size == (4, 2)

    mpimg.imsave(c.arquivo_logo("Nubank", ".jpg"), [[[0.5, 0.0, 0.8]] * 3] * 3)
    assert c.imagem_logo("Nubank") is None  # ainda em cache do 1º acesso
    c.imagem_logo.cache_clear()
    assert c.imagem_logo("Nubank").size == (3, 3)


def test_rendas_por_app():
    ifood = {"fonte": "Delivery / Apps", "app": "iFood", "valor": 300.0}
    uber = {"fonte": "Delivery / Apps", "app": "Uber", "valor": 120.0}
    sem_app = {"fonte": "Delivery / Apps", "valor": 50.0}  # renda antiga
    freela = {"fonte": "Freelance", "valor": 800.0}
    por_app, outras = c.totais_renda([ifood, uber, sem_app, freela, ifood])
    assert por_app["iFood"] == 600.0 and por_app["Uber"] == 120.0
    assert set(por_app) == set(c.APPS_DELIVERY)
    assert sum(por_app.values()) == 720.0
    assert outras == 850.0


def test_mesma_renda():
    ifood_set = {"data": "05/09/2026", "fonte": "Delivery / Apps", "app": "iFood", "valor": 1.0}
    assert c.mesma_renda(ifood_set, "2026-09", "Delivery / Apps", "iFood")
    assert not c.mesma_renda(ifood_set, "2026-09", "Delivery / Apps", "Uber")
    assert not c.mesma_renda(ifood_set, "2026-08", "Delivery / Apps", "iFood")
    freela = {"data": "05/09/2026", "fonte": "Freelance", "valor": 1.0}
    assert c.mesma_renda(freela, "2026-09", "Freelance")
    assert not c.mesma_renda(freela, "2026-09", "Vendas")


def test_campo_dinheiro():
    assert c.centavos_do_texto("1.234,56") == 123456
    assert c.centavos_do_texto("R$ 0,05") == 5
    assert c.centavos_do_texto("abc") == 0 and c.centavos_do_texto("") == 0
    assert c.centavos_do_texto("²³٣") == 0  # só dígitos 0-9
    assert c.centavos_do_texto("9" * 20) == c.MAX_CENTAVOS
    assert c.formatar_numero(1234.5) == "1.234,50"
    assert c.formatar_numero(0.01) == "0,01"
    assert c.formatar_numero(999999999.99) == "999.999.999,99"
    assert c.formatar_moeda(1234.5) == "R$ 1.234,50"


def test_parcelamento():
    assert c.somar_meses("14/09/2026", 0) == "14/09/2026"
    assert c.somar_meses("31/01/2026", 1) == "28/02/2026"
    assert c.somar_meses("15/11/2026", 3) == "15/02/2027"
    assert c.somar_meses("10/05/2026", 47) == "10/04/2030"

    compra = {"data": "31/10/2026", "categoria": "Parcelamento de Compras",
              "cartao": "Cartão de Crédito", "valor": 150.0, "parcelas": 4,
              "parcela": 1, "compra": "abc", "descricao": "x"}
    luz = {"data": "05/10/2026", "categoria": "Luz", "valor": 90.0, "descricao": "Luz"}
    gastos = [compra, luz]
    assert c.distribuir_parcelas(gastos) == 3
    parcelas = sorted((g for g in gastos if g.get("compra") == "abc"),
                      key=lambda g: g["parcela"])
    assert [(g["parcela"], g["data"]) for g in parcelas] == [
        (1, "31/10/2026"), (2, "30/11/2026"), (3, "31/12/2026"), (4, "31/01/2027")]
    assert all(g["valor"] == 150.0 for g in parcelas)
    assert parcelas[2]["descricao"] == "Parcelamento de Compras 3/4"
    assert c.distribuir_parcelas(gastos) == 0, "clicar de novo não duplica"
    assert len(gastos) == 5

    # parcela apagada à mão volta; base pode ser uma parcela do meio
    gastos.remove(parcelas[1])
    assert c.distribuir_parcelas(gastos) == 1
    so_do_meio = [{**compra, "compra": "xyz", "parcela": 3, "data": "10/03/2027"}]
    assert c.distribuir_parcelas(so_do_meio) == 3
    assert sorted((g["parcela"], g["data"]) for g in so_do_meio) == [
        (1, "10/01/2027"), (2, "10/02/2027"), (3, "10/03/2027"), (4, "10/04/2027")]
    invalida = [{**compra, "compra": "q", "data": "sem data"}]
    assert c.distribuir_parcelas(invalida) == 0


def test_logo_sobre_cor():
    import numpy as np
    roxo = np.zeros((2, 3, 4), dtype=np.uint8); roxo[...] = (130, 10, 209, 255)
    branco = c.logo_sobre_cor(roxo, "#820AD1")          # 'nu' roxo na fatia roxa
    assert (branco[..., :3] == 255).all() and (branco[..., 3] == 255).all()
    amarelo = roxo.copy(); amarelo[..., :3] = (249, 221, 22)
    preto = c.logo_sobre_cor(amarelo, "#F9DD16")        # fatia clara: silhueta preta
    assert (preto[..., :3] == 0).all()
    azul = roxo.copy(); azul[..., :3] = (20, 60, 160)
    assert c.logo_sobre_cor(azul, "#EC7000") is azul    # já contrasta: fica igual
    transparente = roxo.copy(); transparente[..., 3] = 0
    assert c.logo_sobre_cor(transparente, "#820AD1") is transparente


def test_emprestimo_parcelado_nao_e_copiado_como_conta_fixa():
    antigo = {"categoria": "Financiamento/Empréstimo", "valor": 900.0}
    parcelado = {**antigo, "parcelas": 60, "parcela": 1, "compra": "x"}
    assert c.e_conta_fixa(antigo) and not c.e_conta_fixa(parcelado)
    assert c.e_conta_fixa({"categoria": "Luz", "valor": 1.0})
    assert not c.e_conta_fixa({"categoria": "Lazer", "valor": 1.0})
    rapidas, maximo = c.CATEGORIAS_PARCELADAS["Financiamento/Empréstimo"]
    assert rapidas == ["12x", "24x", "36x", "48x"] and maximo == 420
    assert c.quantidade_parcelas("60x", 420) == 60 and c.quantidade_parcelas(" 360 ", 420) == 360
    assert c.quantidade_parcelas("60", 48) is None and c.quantidade_parcelas("1", 48) is None
    assert c.quantidade_parcelas("abc", 48) is None and c.quantidade_parcelas(None, 48) is None
    assert c.quantidade_parcelas("Outra…", 420) is None


def test_outros_por_ultimo():
    assert c.outros_por_ultimo(["A", "Outros", "B", "C"]) == ["A", "B", "C", "Outros"]
    assert list(c.outros_por_ultimo({"Outra": 1, "X": 2, "Y": 3})) == ["X", "Y", "Outra"]
    assert c.outros_por_ultimo(["Outubro", "B"]) == ["Outubro", "B"]  # só a palavra exata
    for lista in (c.CATEGORIAS, c.CARTOES, c.FONTES_RENDA, list(c.INSTITUICOES),
                  list(c.INSTITUICOES_TRANSPORTE)):
        assert lista[-1].startswith("Outr"), lista


def test_acumulado_poupancas():
    g = lambda data, cat, v: {"data": data, "categoria": cat, "valor": v}
    gastos = [g("05/01/2026", "Reserva de Emergência", 500.0),
              g("05/03/2026", "Reserva de Emergência", 300.0),
              g("10/02/2026", "Investimentos", 1000.0),
              g("10/02/2026", "Luz", 99.0)]
    rendas = [{"data": "20/03/2026", "fonte": "Resgate da Reserva", "valor": 200.0},
              {"data": "20/03/2026", "fonte": "Investimentos", "valor": 50.0}]  # rendimento
    meses, saldo, mov = c.acumulado_poupancas(gastos, rendas, ate="2026-05")
    assert meses == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
    assert mov["reserva"] == [500.0, 0.0, 100.0, 0.0, 0.0]
    assert saldo["reserva"] == [500.0, 500.0, 600.0, 600.0, 600.0]
    assert saldo["investimentos"] == [0.0, 1000.0, 1000.0, 1000.0, 1000.0]
    meses, saldo, _ = c.acumulado_poupancas(gastos, rendas, ate="2025-12")
    assert meses[0] == "2026-01" and meses[-1] == "2026-03"  # "ate" antes do fim não corta
    assert c.acumulado_poupancas([g("05/01/2026", "Luz", 1.0)], []) == (
        [], {"reserva": [], "investimentos": []}, {"reserva": [], "investimentos": []})


if __name__ == "__main__":
    test_outros_por_ultimo()
    test_acumulado_poupancas()
    test_emprestimo_parcelado_nao_e_copiado_como_conta_fixa()
    test_logo_sobre_cor()
    test_parcelamento()
    test_campo_dinheiro()
    test_rendas_por_app()
    test_mesma_renda()
    test_logos()
    test_fatura_por_instituicao()
    test_transporte_por_tipo()
    test_ida_e_volta()
    test_formatos_antigos_sem_rendas()
    test_arquivo_ausente_ou_corrompido()
    print("ok — camada de dados")
