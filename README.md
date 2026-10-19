# 💰 Calculador de Gastos

> Controle simples e visual das suas despesas mensais — orçamento, gráficos e histórico por mês, com interface moderna em modo claro/escuro.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1f6aa5)
![Matplotlib](https://img.shields.io/badge/Gr%C3%A1ficos-Matplotlib-11557c)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Um aplicativo de desktop em Python para acompanhar seus gastos mês a mês:
defina um orçamento, registre despesas por categoria e forma de pagamento e
veja tudo em gráficos que se atualizam ao vivo.

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
- 🛟 **Aba Reserva, Investimentos e Caixinhas** — acumulado mês a mês da reserva de
  emergência e dos investimentos: guardar é um gasto nas categorias *Reserva de
  Emergência* ou *Investimentos*; tirar é uma renda em *Resgate da Reserva* ou
  *Resgate de Investimentos*. Mostra quantos meses de gastos a reserva cobre.
  Ao lado, as **caixinhas**: objetivos com nome e meta opcional, para guardar e
  retirar dinheiro (também pelo assistente).
- 📏 **Barra de progresso do orçamento** que muda de cor conforme o uso.
- 📋 **Copiar contas fixas** de um mês para outro, sem duplicar.
- 🛍️ **Parcelamento de compras e financiamentos/empréstimos** — escolha a
  quantidade de parcelas (compras: 2x a 48x; empréstimos: até 420x) e o valor da parcela;
  ao clicar em *Copiar contas fixas*, as parcelas que faltam são lançadas nos
  meses seguintes (1/12, 2/12…), sem duplicar.
- 🌗 **Modo claro/escuro** com um clique.
- 💾 **Salvamento automático** em JSON, com validação dos dados, gravação
  atômica e preservação de arquivos inválidos.
- 💬 **Assistente opcional com Ollama** — registre gastos e ganhos por texto
  usando um modelo local. Os valores e categorias passam por validação antes
  do lançamento; exclusões pedem confirmação na interface.

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

## 💬 Assistente local com Ollama (opcional)

O aplicativo funciona sem Ollama. Para usar a aba de assistente:

1. Instale o [Ollama](https://ollama.com/) e inicie o serviço local.
2. Baixe o modelo configurado por padrão:

   ```bash
   ollama pull qwen2.5-coder:14b
   ```

3. Abra o aplicativo com `python calculador.py` e use o assistente.
   Exemplo: `gastei 12 de uber e ganhei 85 no ifood`.

O padrão é `http://localhost:11434` e o modelo `qwen2.5-coder:14b`.
Para escolher outro modelo compatível com ferramentas, configure as variáveis
antes de abrir o programa (o modelo deve estar instalado no Ollama):

```bash
# Linux/macOS
export CALCULADOR_OLLAMA_MODELO="qwen2.5-coder:14b"
export CALCULADOR_OLLAMA_URL="http://localhost:11434"
python calculador.py
```

```powershell
# Windows PowerShell
$env:CALCULADOR_OLLAMA_MODELO="qwen2.5-coder:14b"
$env:CALCULADOR_OLLAMA_URL="http://localhost:11434"
python calculador.py
```

As variáveis são lidas na abertura. O assistente envia mensagens e contexto
financeiro para o endereço configurado; por padrão, o serviço é local.
As respostas do modelo podem conter erros: confira os lançamentos. Sem o serviço
ou o modelo disponível, o assistente mostra uma mensagem de erro; as demais
funções continuam disponíveis.

---

## 🧪 Como verificar o projeto

Depois de instalar as dependências:

```bash
python test_calculador.py
python -m unittest discover -v
```

A primeira suíte verifica cálculos, parcelas, caixinhas, imagens e validações do
assistente. A descoberta de testes verifica os formatos JSON atuais e antigos, estruturas
inválidas, números não finitos e falhas de acesso, backup e gravação. Os testes
usam arquivos temporários e respostas HTTP simuladas. Também verificam a
configuração do assistente e a rejeição de entradas inválidas na interface.
Não é necessário iniciar Ollama para executá-los.

O workflow **Testes** executa as duas suítes em pull requests, no Windows e no
Ubuntu, com Python 3.10 e 3.13. O workflow **Aplicativos** também executa as duas
antes de gerar os executáveis. Os testes automatizados não substituem a
conferência visual das abas, dos gráficos e dos diálogos.

### Proteção dos arquivos de dados

São aceitos o formato atual e os formatos antigos (lista de gastos ou orçamento
único). Lançamentos precisam ter data em texto, valor numérico finito e não
negativo e categoria/fonte em texto. Datas inválidas salvas por versões
anteriores (ex.: `31/02/2026`) são mantidas e ignoradas nas contas; datas
novas são validadas ao lançar. Caixinhas, orçamentos e parcelas também
são validados; campos extras dos lançamentos são mantidos.

Se o JSON estiver corrompido ou sua estrutura for inválida, o arquivo inteiro é
preservado como `gastos.json.corrompido-<data>-<identificador>` na mesma pasta,
e o aplicativo inicia com dados vazios, mostrando um aviso com o nome da cópia.
Nenhum lançamento é filtrado ou apagado individualmente. Para recuperar os
dados, guarde essa cópia, corrija o problema e restaure o conteúdo para
`gastos.json` com o aplicativo fechado.

Se não for possível ler o arquivo por falta de permissão ou preservar a cópia,
o erro é propagado, impedindo que o aplicativo inicie com dados vazios sobre um
arquivo sem proteção. Ao salvar, os dados são validados antes da gravação, e a
troca do arquivo ocorre somente depois da escrita e sincronização do temporário.
Se a gravação falhar, a alteração é desfeita na tela e um aviso é mostrado.
As cópias de recuperação e o temporário ficam fora do Git.

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
├── calculador.py          # Interface, gráficos e ponto de entrada
├── configuracao.py        # Categorias, opções e paleta compartilhadas
├── dominio.py             # Cálculos, datas, parcelas e formatação
├── armazenamento.py       # Validação, migração e persistência JSON
├── assistente.py          # Ferramentas, validação e cliente do Ollama
├── test_calculador.py     # Regressões de cálculos, assistente e gráficos
├── test_armazenamento.py  # Regressões de validação e proteção dos arquivos
├── test_integracao.py     # Cliente Ollama e validações de entrada da interface
├── empacotamento/         # instalar-ubuntu.sh (atalho no menu do Ubuntu)
├── .github/workflows/     # testes do PR e geração de aplicativos
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
