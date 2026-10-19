"""Regressões de persistência. Execute: python -m unittest -v test_armazenamento."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from armazenamento import carregar_dados, salvar_dados


class ArmazenamentoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name) / "gastos.json"
        self.gasto = {"data": "05/09/2026", "categoria": "Luz", "valor": 90.0}

    def gravar(self, dados):
        self.caminho.write_text(json.dumps(dados), encoding="utf-8")

    def test_arquivo_ausente(self):
        self.assertEqual(carregar_dados(self.caminho), ({}, [], [], []))
        self.assertEqual(list(self.caminho.parent.iterdir()), [])

    def test_formatos_anteriores(self):
        for dados, esperado in [
            ([self.gasto], ({}, [self.gasto], [], [])),
            ({"orcamento": "2500", "gastos": [self.gasto]},
             ({"2026-09": 2500.0}, [self.gasto], [], [])),
            ({}, ({}, [], [], [])),
        ]:
            with self.subTest(dados=dados):
                self.gravar(dados)
                original = self.caminho.read_bytes()
                self.assertEqual(carregar_dados(self.caminho), esperado)
                self.assertEqual(self.caminho.read_bytes(), original)

    def test_ida_volta_com_parcelas_caixinhas_e_campos_extras(self):
        gasto = {**self.gasto, "compra": "abc", "parcela": 1, "parcelas": 12,
                 "campo_futuro": {"teste": True}}
        renda = {"data": "10/09/2026", "fonte": "Freelance", "valor": 100.0}
        dados = ({"2026-09": 3000.0}, [gasto], [renda], [{"nome": "Casa", "meta": 5000.0}])
        salvar_dados(self.caminho, *dados)
        self.assertEqual(carregar_dados(self.caminho), dados)
        self.assertFalse(Path(str(self.caminho) + ".tmp").exists())

    def test_estrutura_invalida_preserva_todos_os_bytes(self):
        ruins = [None, True, 42, "texto", {"gastos": {}}, {"gastos": [None]},
                 {"gastos": [self.gasto, {"valor": 1}]}, {"rendas": "texto"},
                 {"orcamentos": []}, {"orcamentos": {"2026-13": 1}},
                 {"orcamentos": {"0000-01": 1}}, {"orcamentos": {"2026-09": "abc"}},
                 {"orcamentos": {"2026-09": True}}, {"caixinhas": {}},
                 {"caixinhas": [{"nome": ""}]}, {"caixinhas": [{"nome": "Casa", "meta": None}]},
                 {"caixinhas": [{"nome": "Casa"}, {"nome": "Casa"}]}]
        ruins += [{"gastos": [{**self.gasto, "valor": valor}]} for valor in
                  (None, "90", True, -1, float("nan"), float("inf"), 10**400)]
        ruins += [{"gastos": [{**self.gasto, **campos}]} for campos in
                  ({"data": "31/02/2026"}, {"data": 1}, {"categoria": []},
                   {"descricao": []}, {"compra": "abc"},
                   {"compra": "abc", "parcela": 2, "parcelas": 1},
                   {"compra": "abc", "parcela": True, "parcelas": 12})]
        for dados in ruins:
            with self.subTest(dados=dados):
                self.gravar(dados)
                original = self.caminho.read_bytes()
                antes = set(self.caminho.parent.glob("*.corrompido-*"))
                self.assertEqual(carregar_dados(self.caminho), ({}, [], [], []))
                novas = set(self.caminho.parent.glob("*.corrompido-*")) - antes
                self.assertEqual(len(novas), 1)
                self.assertEqual(novas.pop().read_bytes(), original)
                self.assertFalse(self.caminho.exists())

    def test_json_truncado_e_encoding_invalido(self):
        for conteudo in (b'{"gastos": [', b'\xff\xfe'):
            self.caminho.write_bytes(conteudo)
            self.assertEqual(carregar_dados(self.caminho), ({}, [], [], []))
            self.assertTrue(any(p.read_bytes() == conteudo for p in self.caminho.parent.iterdir()))

    def test_nao_sobrescreve_se_validacao_falhar(self):
        self.gravar({"gastos": [self.gasto]})
        original = self.caminho.read_bytes()
        with self.assertRaises(ValueError):
            salvar_dados(self.caminho, {}, [{**self.gasto, "valor": float("inf")}], [], [])
        self.assertEqual(self.caminho.read_bytes(), original)

    def test_falha_na_troca_mantem_original_e_remove_temporario(self):
        self.gravar({"gastos": [self.gasto]})
        original = self.caminho.read_bytes()
        with patch("armazenamento.os.replace", side_effect=PermissionError("sem permissão")):
            with self.assertRaises(PermissionError):
                salvar_dados(self.caminho, {}, [], [], [])
        self.assertEqual(self.caminho.read_bytes(), original)
        self.assertFalse(Path(str(self.caminho) + ".tmp").exists())

    def test_falha_no_backup_nao_retorna_dados_vazios(self):
        self.gravar({"gastos": "inválido"})
        original = self.caminho.read_bytes()
        with patch("armazenamento.os.replace", side_effect=PermissionError("sem permissão")):
            with self.assertRaises(PermissionError):
                carregar_dados(self.caminho)
        self.assertEqual(self.caminho.read_bytes(), original)

    def test_falha_de_acesso_nao_move_arquivo(self):
        self.gravar({"gastos": [self.gasto]})
        with patch("builtins.open", side_effect=PermissionError("sem permissão")):
            with self.assertRaises(PermissionError):
                carregar_dados(self.caminho)
        self.assertTrue(self.caminho.exists())
        self.assertEqual(list(self.caminho.parent.glob("*.corrompido-*")), [])

    def test_dados_de_exemplo_sao_validos(self):
        self.caminho.write_bytes(Path(__file__).with_name("gastos.exemplo.json").read_bytes())
        orcamentos, gastos, rendas, caixinhas = carregar_dados(self.caminho)
        self.assertEqual(orcamentos["2026-09"], 3200.0)
        self.assertEqual(len(gastos), 9)
        self.assertEqual(len(rendas), 2)
        self.assertEqual(caixinhas, [])


if __name__ == "__main__":
    unittest.main()
