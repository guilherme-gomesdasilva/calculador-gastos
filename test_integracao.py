"""Integrações verificáveis sem abrir janela ou iniciar um modelo local."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import assistente
from calculador import CalculadorApp, ErroAoSalvar
from armazenamento import carregar_dados, salvar_dados
from dominio import mes_de_data, totais_por_dia, valor_digitado


class IntegracaoTests(unittest.TestCase):
    def test_modelo_e_url_configuraveis_na_abertura(self):
        ambiente = {**os.environ, "CALCULADOR_OLLAMA_MODELO": "modelo-teste",
                    "CALCULADOR_OLLAMA_URL": "http://localhost:12345/"}
        resultado = subprocess.check_output(
            [sys.executable, "-c", "import assistente as a; print(a.OLLAMA_MODELO, a.OLLAMA_URL)"],
            env=ambiente, text=True)
        self.assertEqual(resultado.strip(), "modelo-teste http://localhost:12345")

    def test_cliente_ollama_monta_pedido_e_retorna_mensagem(self):
        resposta = Mock()
        resposta.read.return_value = json.dumps({"message": {"content": "ok"}}).encode()
        resposta.__enter__ = Mock(return_value=resposta)
        resposta.__exit__ = Mock(return_value=False)
        with patch("assistente.urllib.request.urlopen", return_value=resposta) as abrir:
            self.assertEqual(assistente.chamar_ollama({"model": "teste"}), {"content": "ok"})
        pedido = abrir.call_args.args[0]
        self.assertEqual(pedido.full_url, assistente.OLLAMA_URL + "/api/chat")
        self.assertEqual(json.loads(pedido.data), {"model": "teste"})
        self.assertEqual(abrir.call_args.kwargs["timeout"], 300)

    def test_cliente_ollama_retorna_falha_de_conexao(self):
        erro = OSError("serviço indisponível")
        with patch("assistente.urllib.request.urlopen", side_effect=erro):
            self.assertIs(assistente.chamar_ollama({}), erro)

    def test_campos_monetarios_rejeitam_nao_finitos(self):
        for texto in ("nan", "NaN", "inf", "-inf", "1e999"):
            with self.subTest(texto=texto):
                self.assertIsNone(valor_digitado(texto))
                self.assertIsNone(CalculadorApp._parse_valor(None, texto))
        self.assertEqual(CalculadorApp._parse_valor(None, "1.234,56"), 1234.56)

    def test_data_invalida_na_interface_nao_altera_lancamentos(self):
        app = CalculadorApp.__new__(CalculadorApp)
        for nome, valor in (("valor_var", "90,00"), ("cat_var", "Luz"),
                            ("cartao_var", "Pix"), ("data_var", "31/02/2026")):
            setattr(app, nome, Mock(get=Mock(return_value=valor)))
        app.gastos = []
        app._salvar = Mock()
        app._toast = Mock()
        app.adicionar_gasto()
        app._salvar.assert_not_called()
        self.assertEqual(app.gastos, [])
        self.assertIn("data válida", app._toast.call_args.args[0])

    def test_edicao_nao_reduz_total_abaixo_da_parcela_atual(self):
        app = CalculadorApp.__new__(CalculadorApp)
        for nome, valor in (("valor_var", "90,00"), ("cat_var", "Parcelamento de Compras"),
                            ("cartao_var", "Pix"), ("data_var", "10/09/2026"),
                            ("parcelas_var", "2x")):
            setattr(app, nome, Mock(get=Mock(return_value=valor)))
        original = {"compra": "abc", "parcela": 3, "parcelas": 12}
        app.gastos = [original.copy()]
        app._editando = 0
        app._salvar = Mock()
        app._toast = Mock()
        app.adicionar_gasto()
        app._salvar.assert_not_called()
        self.assertEqual(app.gastos, [original])

    def test_falha_ao_salvar_desfaz_a_alteracao_e_avisa(self):
        app = CalculadorApp.__new__(CalculadorApp)
        gasto = {"data": "05/09/2026", "categoria": "Luz", "cartao": "Pix", "valor": 90.0}
        app.orcamentos, app.gastos, app.rendas, app.caixinhas = {}, [gasto], [], []
        app._salvo = ({}, [dict(gasto)], [], [])
        app.mes_atual = "2026-09"
        app.orc_var = Mock()
        app._preencher_renda = Mock()
        app._atualizar_tudo = Mock()
        app._toast = Mock()
        app.gastos.append({**gasto, "valor": 10.0})
        with patch("calculador.salvar_dados", side_effect=PermissionError("sem permissão")):
            with self.assertRaises(ErroAoSalvar):
                app._salvar()
        self.assertEqual(app.gastos, [gasto])
        app._atualizar_tudo.assert_called_once()
        self.assertIn("desfeita", app._toast.call_args.args[0])

    def test_datas_antigas_preservadas_sem_divergencia_nos_totais(self):
        validos = [{"data": "28/02/2026", "categoria": "Luz", "valor": 10.0}]
        invalidos = [{"data": data, "categoria": "Luz", "valor": 90.0}
                     for data in ("31/02/2026", "00/02/2026", "01/02/0000", "10/09", " ")]
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "gastos.json"
            dados = ({}, validos + invalidos, [], [])
            salvar_dados(caminho, *dados)
            app = CalculadorApp.__new__(CalculadorApp)
            app.orcamentos, app.gastos, app.rendas, app.caixinhas = carregar_dados(caminho)
            app.mes_atual = "2026-02"
            self.assertEqual(app.gastos, validos + invalidos)
            self.assertEqual(app.gastos_do_mes(), validos)
            self.assertEqual(app._meses_com_dados_asc(), ["2026-02"])
            self.assertEqual(sum(g["valor"] for g in app.gastos_do_mes()),
                             sum(totais_por_dia(app.gastos).values()))
            self.assertFalse(list(Path(pasta).glob("*.corrompido-*")))
        self.assertEqual(mes_de_data("29/02/2024"), "2024-02")
        self.assertIsNone(mes_de_data("29/02/2026"))

    def test_falha_ao_salvar_restaura_campos_de_salario_e_renda(self):
        from tkinter import StringVar, Tcl
        for acao in ("definir_orcamento", "definir_renda"):
            with self.subTest(acao=acao):
                app = CalculadorApp.__new__(CalculadorApp)
                renda = {"data": "05/09/2026", "fonte": "Freelance", "valor": 150.0}
                app.mes_atual = "2026-09"
                app.orcamentos, app.gastos, app.rendas, app.caixinhas = {"2026-09": 1000.0}, [], [renda], []
                app._salvo = ({"2026-09": 1000.0}, [], [dict(renda)], [])
                interpretador = Tcl()
                app.orc_var = StringVar(master=interpretador, value="2.000,00")
                app.renda_valor_var = StringVar(master=interpretador, value="300,00")
                app.renda_fonte_var = StringVar(master=interpretador, value="Freelance")
                app._atualizar_tudo = Mock()
                app._toast = Mock()
                with patch("calculador.salvar_dados", side_effect=PermissionError("sem permissão")):
                    with self.assertRaises(ErroAoSalvar):
                        getattr(app, acao)()
                self.assertEqual(app.orcamentos, {"2026-09": 1000.0})
                self.assertEqual(app.rendas, [renda])
                self.assertEqual(app.orc_var.get(), "1.000,00")
                self.assertEqual(app.renda_valor_var.get(), "150,00")
                self.assertIn("desfeita", app._toast.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

