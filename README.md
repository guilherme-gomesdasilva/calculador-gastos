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
- 💼 **Salário por mês** — cada mês tem o seu salário; o **orçamento** do mês é
  o salário somado a todas as rendas extras.
- 💵 **Renda extra** — funciona como o salário: escolha a fonte (freelance,
  vendas, investimentos, reembolso, presente, 13º/férias, delivery), informe o
  valor do mês e salve; ele vai direto para os cards do topo, sem misturar com
  os gastos (salvar 0 remove). Em **Delivery / Apps** você escolhe o app
  (iFood, 99, Uber, Mercado Livre, Shopee, Keeta, Rappi, Lalamove, Loggi,
  Amazon Flex, Borzo, inDrive, Zé Delivery, aiqfome, Magalu) e cada app com
  renda no mês ganha um card com logo no topo.
- 💸 **Lançamento de gastos** com descrição, valor, **categoria** e
  **cartão / forma de pagamento**.
- 🧾 **Categorias de contas** (aluguel, luz, água, gás, internet, fatura de
  cartão, além de alimentação, transporte, saúde, educação, lazer e outros).
  Na **fatura de cartão** você escolhe a instituição (Nubank, Itaú, Bradesco…)
  e ela aparece nos gráficos com a cor característica do banco.
- 📊 **Gráficos ao vivo**: rosca de gastos por categoria, barras de
  orçamento × renda × gasto × restante e barras por cartão.
- 📈 **Aba de Evolução** — compara os meses (gasto × orçamento, categorias
  empilhadas) e mostra um resumo (gasto médio, maior/menor mês, total).
- 🛟 **Aba Reserva e Investimentos** — acumulado mês a mês da reserva de
  emergência e dos investimentos: guardar é um gasto nas categorias *Reserva de
  Emergência* ou *Investimentos*; tirar é uma renda em *Resgate da Reserva* ou
  *Resgate de Investimentos*. Mostra quantos meses de gastos a reserva cobre.
- 📏 **Barra de progresso do orçamento** que muda de cor conforme o uso.
- 📋 **Copiar contas fixas** de um mês para outro, sem duplicar.
- 🛍️ **Parcelamento de compras e financiamentos/empréstimos** — escolha a
  quantidade de parcelas (compras: 2x a 48x; empréstimos: até 420x) e o valor da parcela;
  ao clicar em *Copiar contas fixas*, as parcelas que faltam são lançadas nos
  meses seguintes (1/12, 2/12…), sem duplicar.
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

> **Logos dos bancos (opcional):** coloque arquivos PNG em `assets/logos/`
> com o nome da instituição em minúsculas, sem acento e com hífen no lugar
> do espaço — `nubank.png`, `itau.png`, `bradesco.png`, `santander.png`,
> `banco-do-brasil.png`, `caixa.png`, `inter.png`, `mercado-pago.png`,
> `picpay.png` — e dos apps de delivery, pelo mesmo padrão: `ifood.png`,
> `99.png`, `mercado-livre.png`, `amazon-flex.png`, `ze-delivery.png`, `keeta.png`… Eles aparecem na legenda dos gráficos no lugar da cor. Prefira
> o ícone quadrado (de app) com fundo transparente. Os logos são marcas
> registradas, por isso a pasta fica fora do Git.

> Os seus gastos ficam salvos em `gastos.json`, que **não** é versionado
> (está no `.gitignore`). O arquivo `gastos.exemplo.json` serve como ponto
> de partida — se você não copiá-lo, o app começa vazio.

---

## 💻 Aplicativos para Windows e Ubuntu

Não precisa instalar Python: o GitHub gera os aplicativos automaticamente
(workflow `.github/workflows/aplicativos.yml`) a cada push na `main`.
No GitHub, abra **Actions → Aplicativos**, clique na execução mais recente e,
em **Artifacts**, baixe o arquivo do seu sistema.

Para publicar uma versão com download direto na página **Releases**, crie uma
tag: `git tag v1.0 && git push origin v1.0`.

### Windows

1. Baixe **CalculadorDeGastos-windows.zip** e extraia.
2. Abra `CalculadorDeGastos\CalculadorDeGastos.exe`.

Os dados ficam em `%APPDATA%\CalculadorGastos\gastos.json` e os logos em
`%APPDATA%\CalculadorGastos\logos\` (cole essa pasta na barra de endereço do
Explorador de Arquivos para abrir). Na primeira vez, o Windows SmartScreen pode
avisar que o app não é reconhecido: clique em
**Mais informações → Executar assim mesmo**.

### Ubuntu

```bash
tar -xzf CalculadorDeGastos-ubuntu.tar.gz
./instalar-ubuntu.sh            # instala para o seu usuário, sem sudo
./instalar-ubuntu.sh --remover  # remove (seus dados continuam)
```

Depois procure por **Calculador de Gastos** nos aplicativos. Os dados ficam em
`~/.local/share/CalculadorGastos/gastos.json` e os logos em
`~/.local/share/CalculadorGastos/logos/`.

> Rodando pelo código (`python calculador.py`), os dados continuam na pasta do
> projeto — são arquivos separados dos do aplicativo instalado.

---

## 🗂️ Estrutura do projeto

```
calculador-gastos/
├── calculador.py          # Aplicação (interface + lógica + gráficos)
├── test_calculador.py     # Checagens da camada de dados (JSON)
├── empacotamento/         # instalar-ubuntu.sh (atalho no menu do Ubuntu)
├── .github/workflows/     # gera os aplicativos Windows e Ubuntu
├── requirements.txt       # Dependências do projeto
├── gastos.exemplo.json    # Dados fictícios de exemplo
├── gastos.json            # Seus dados reais (gerado no 1º uso, fora do Git)
├── assets/                # Ícone do app, logos (fora do Git) e imagens do README
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
