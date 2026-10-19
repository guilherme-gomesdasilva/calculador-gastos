"""Integrações verificáveis sem abrir janela ou iniciar um modelo local."""

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import assistente
from calculador import CalculadorApp
from dominio import valor_digitado


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


if __name__ == "__main__":
    unittest.main()
