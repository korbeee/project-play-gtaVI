# Radar de Consoles — design

Data: 2026-11-24

## Intenção

O usuário quer comprar um console (Xbox Series S, Xbox Series X, PS5 ou PS5 Pro)
e o jogo GTA 6 pelo menor preço possível, sem ficar olhando lojas. Um robô
verifica os preços a cada 10 minutos e avisa num grupo do Telegram **só quando
encontrar uma oferta realmente boa**. Se não houver nada bom, fica em silêncio.

## Objetivos

- Monitorar 5 itens: PS5 (digital e com disco), PS5 Pro, Xbox Series X,
  Xbox Series S, GTA 6 (versões PS5 e Xbox).
- Lojas confiáveis apenas: Kabum, Amazon.com.br, Magalu, Pichau, Terabyte,
  Mercado Livre (lojas oficiais). Shopee e AliExpress ficam de fora.
- Rodar na nuvem (GitHub Actions), com o PC do usuário desligado.
- Mandar alerta no grupo do Telegram com produto, loja, preço, desconto e link.

## Fora do escopo

- WhatsApp (risco de banimento do número; trocado por Telegram com o aval do usuário).
- Resumo diário quando não há promoção.
- Comprar automaticamente.
- Acessórios, controles, bundles de outros jogos isolados.

## Anti-objetivos (seria um fracasso mesmo funcionando)

- Spam: o mesmo alerta a cada 10 minutos, ou alertas de controle/capa/suporte.
- Alertar oferta de vendedor desconhecido de marketplace (golpe do "barato demais").
- Contornar proteções anti-robô das lojas (Cloudflare, Akamai, captcha). Loja que
  bloqueia fica de fora ou entra por uma fonte que permite o acesso.

## Restrições

- **GitHub Actions grátis:** repositório **público** (minutos ilimitados). Num
  repositório privado, 10 em 10 min estoura a cota grátis de 2.000 min/mês.
- O agendamento do GitHub é aproximado: na prática o intervalo varia entre ~10 e
  ~60 min em horários de pico.
- O GitHub desativa agendamentos de repositórios públicos após 60 dias sem
  atividade. Salvar o histórico de preços com um commit mantém o repositório ativo.
- O token do bot do Telegram e o ID do grupo ficam em **GitHub Secrets**, nunca no código.
- IPs de servidores podem ser bloqueados por lojas que aceitaram o acesso do PC
  do usuário (testado em 2026-11-24 a partir do PC). Cada fonte falha sozinha
  sem derrubar as outras, e o robô registra quais falharam.

## Abordagens consideradas

| Abordagem | Prós | Contras |
|---|---|---|
| A. Script no PC (Agendador do Windows) | Acesso às lojas mais confiável; intervalo exato | Só funciona com o PC ligado |
| **B. GitHub Actions (escolhida pelo usuário)** | Funciona com o PC desligado; grátis | Intervalo irregular; lojas podem bloquear IPs de servidor; repositório público |
| C. Sites de promoção (Pelando) como fonte principal | Pega cupons e ofertas relâmpago de qualquer loja | Depende de alguém postar; mais difícil de filtrar |

O usuário escolheu **B**.

## Como funciona

### Fontes (cada uma é um módulo independente)

| Fonte | Como lê | Cobre |
|---|---|---|
| Kabum | JSON `__NEXT_DATA__` da página de busca | Kabum (+ parceiros como Magalu vendendo lá) |
| Amazon | HTML da busca (`a-price-whole`, título, link) | Amazon |
| Zoom (comparador) | JSON `__NEXT_DATA__` da busca | Magalu, Pichau, Terabyte e outras quando listadas |
| Mercado Livre | API oficial com token do usuário | **Opcional, desligado** até o usuário criar o token |

Buscas por item, por exemplo: `playstation 5`, `playstation 5 pro`,
`xbox series x`, `xbox series s`, `gta 6 ps5`, `gta 6 xbox`.

### Classificação

Cada resultado vira um `Offer(item, titulo, loja, vendedor, preco, preco_antigo, url)`.
Um classificador por regras de texto decide o item:

- Precisa conter as palavras do console (ex.: "playstation 5" ou "ps5", e "pro" para o Pro).
- Descarta títulos com: controle, capa, case, suporte, base, carregador, headset,
  skin, película, cabo, "para ps5", "compatível".
- GTA 6: "gta 6", "gta vi" ou "grand theft auto vi" + plataforma.
- Vendedor precisa estar na lista de lojas confiáveis (KaBuM!, Amazon,
  Magazine Luiza, Pichau, Terabyte, lojas oficiais do Mercado Livre).

### Regra de "barato" (decisão minha, ajustável num arquivo de configuração)

Um alerta sai quando **qualquer uma** vale:

1. O menor preço do item na rodada fica **≥ 10% abaixo da mediana dos menores
   preços dos últimos 7 dias**; ou
2. É o **menor preço já visto** para o item (só depois de 24 h de histórico,
   para não disparar tudo no primeiro dia); ou
3. Fica abaixo de um **teto fixo** opcional por item (vazio por padrão).

### Sem repetição

Cada oferta (loja + URL) é avisada uma vez. Só volta a avisar se o preço cair mais.

### Estado

`data/history.json` (menor preço por item por rodada, últimos 30 dias) e
`data/alerted.json` (ofertas já avisadas). O workflow faz commit desses
arquivos ao final de cada rodada.

### Mensagem no Telegram

```
🔥 PS5 Pro — R$ 6.899 (era ~R$ 7.799, -12%)
Loja: KaBuM!
Console PlayStation 5 Pro Sony, SSD 2TB...
https://www.kabum.com.br/produto/...
```

### Estrutura

```
radar-consoles/
  radar/            # código Python
    sources/        # kabum.py, amazon.py, zoom.py, mercadolivre.py
    classify.py     # título -> item ou descarta
    rules.py        # decide se é barato
    state.py        # history/alerted
    telegram.py     # envio
    main.py         # orquestra uma rodada
  config.toml       # itens, buscas, lojas confiáveis, limites
  data/             # estado commitado pelo workflow
  tests/            # testes com páginas salvas
  .github/workflows/radar.yml   # cron */10
```

Python 3.12, bibliotecas: `httpx`, `selectolax` (HTML), `pytest`.

## O que o usuário precisa fazer

1. Ter uma conta no GitHub e criar o repositório público.
2. Criar o bot no Telegram com o @BotFather, criar o grupo e adicionar o bot.
3. Colocar o token e o ID do grupo nos Secrets do repositório.
(Eu guio cada passo.)

## Deixado para quem constrói

- Seletores exatos de cada página e as palavras de exclusão finais.
- Detalhes do formato da mensagem.
- Atraso aleatório e número de tentativas por fonte.
