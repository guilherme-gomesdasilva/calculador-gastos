# 💰 Calculador de Gastos

> Controle simples e visual das suas despesas mensais — orçamento, gráficos e histórico por mês, com interface moderna em modo claro/escuro.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1f6aa5)
![Matplotlib](https://img.shields.io/badge/Gr%C3%A1ficos-Matplotlib-11557c)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Um aplicativo de desktop em Python para acompanhar seus gastos mês a mês:
defina um orçamento, registre despesas por categoria e forma de pagamento e
veja tudo em gráficos que se atualizam ao vivo.

![screenshot](assets/screenshot.png)

---

## ✨ Funcionalidades

- 📅 **Organização por mês** — seletor de Mês/Ano em calendário pop-up, com
  navegação por ano e destaque para os meses que já têm dados.
- 🎯 **Orçamento por mês** — cada mês tem o seu próprio orçamento.
- 💸 **Lançamento de gastos** com descrição, valor, **categoria** e
  **cartão / forma de pagamento**.
- 🧾 **Categorias de contas** (aluguel, luz, água, gás, internet, fatura de
  cartão, além de alimentação, transporte, saúde, educação, lazer e outros).
- 📊 **Gráficos ao vivo**: rosca de gastos por categoria, barras de
  orçamento × gasto × restante e barras por cartão.
- 📈 **Aba de Evolução** — compara os meses (gasto × orçamento, categorias
  empilhadas) e mostra um resumo (gasto médio, maior/menor mês, total).
- 📏 **Barra de progresso do orçamento** que muda de cor conforme o uso.
- 📋 **Copiar contas fixas** de um mês para outro, sem duplicar.
- 🌗 **Modo claro/escuro** com um clique.
- 💾 **Salvamento automático** em JSON (nada de configuração).

---

## 🚀 Como instalar e rodar

Pré-requisito: **Python 3.10+**.

```bash
# 1. Clonar o repositório
git clone https://github.com/guilherme-gomesdasilva/calculador-gastos.git
cd calculador-gastos

# 2. Criar e ativar um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows (PowerShell)

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. (Opcional) Começar a partir dos dados de exemplo
cp gastos.exemplo.json gastos.json   # Linux/macOS
# copy gastos.exemplo.json gastos.json   # Windows

# 5. Rodar o app
python calculador.py
```

> Os seus gastos ficam salvos em `gastos.json`, que **não** é versionado
> (está no `.gitignore`). O arquivo `gastos.exemplo.json` serve como ponto
> de partida — se você não copiá-lo, o app começa vazio.

---

## 🗂️ Estrutura do projeto

```
calculador-gastos/
├── calculador.py          # Aplicação (interface + lógica + gráficos)
├── requirements.txt       # Dependências do projeto
├── gastos.exemplo.json    # Dados fictícios de exemplo
├── gastos.json            # Seus dados reais (gerado no 1º uso, fora do Git)
├── assets/                # Imagens do README (screenshots)
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🛠️ Tecnologias utilizadas

- **[Python](https://www.python.org/)** — linguagem principal.
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)** — widgets
  modernos sobre o Tkinter (cards, botões arredondados, modo claro/escuro).
- **[Matplotlib](https://matplotlib.org/)** — gráficos integrados à interface.
- **JSON** (biblioteca padrão) — persistência local dos dados.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais
detalhes.
