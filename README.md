# Radar de Consoles

Robô que procura, a cada 10 minutos, preços de **PlayStation 5, PlayStation 5 Pro,
Xbox Series X, Xbox Series S e GTA 6** em lojas confiáveis e avisa num grupo do
Telegram **só quando o preço está realmente baixo**. Se não houver promoção, não
manda nada.

Roda de graça no GitHub Actions, com o seu PC desligado.

## De onde vêm os preços

| Fonte | Cobre |
|---|---|
| Kabum | Kabum e parceiros que vendem lá (ex.: Magalu) |
| Amazon.com.br | Amazon |
| Zoom (comparador) | Magalu, Pichau, Terabyte e outras, quando listadas |

Só valem vendedores da lista `trusted_sellers` em `config.toml`. Pichau, Terabyte,
Magalu e Shopee bloqueiam robôs no acesso direto; o radar **não** contorna esses
bloqueios.

## Quando ele avisa

Para cada item, pega o menor preço da rodada e avisa se:

1. ficou **10% ou mais abaixo da média dos últimos 7 dias**; ou
2. é o **menor preço já visto** (pelo menos 1% abaixo do anterior); ou
3. ficou abaixo do **teto** que você definir (`cap`, opcional).

As regras 1 e 2 só começam depois de 24 h de histórico, para o grupo não receber
uma enxurrada no primeiro dia. Cada oferta é avisada uma vez; só volta a avisar
se o preço cair mais.

Exemplo de aviso:

```
🔥 PlayStation 5 Pro — R$ 6.899,00
-12% vs. média dos últimos 7 dias (R$ 7.799,00)
Loja: KaBuM!
Console PlayStation 5 Pro Sony, SSD 2TB
https://www.kabum.com.br/produto/...
```

## Como colocar para funcionar

### 1. Criar o bot do Telegram

1. No Telegram, abra uma conversa com **@BotFather**.
2. Envie `/newbot`, escolha um nome e um usuário terminado em `bot`.
3. Ele responde com um **token** (algo como `123456:ABC-...`). Guarde, é a senha do bot.

### 2. Criar o grupo e descobrir o ID dele

1. Crie um grupo no Telegram e adicione o seu bot.
2. Mande qualquer mensagem no grupo (ex.: `oi`).
3. No navegador, abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   (troque `<SEU_TOKEN>` pelo token).
4. Procure `"chat":{"id":-100...`. Esse número negativo é o **ID do grupo**.

### 3. Subir o projeto para o GitHub

1. Crie uma conta em https://github.com, se ainda não tiver.
2. Crie um repositório **público** (ex.: `radar-consoles`), sem README.
   Precisa ser público: num privado, rodar a cada 10 minutos estoura a cota grátis.
3. Nesta pasta, rode (troque `SEU_USUARIO`):

```powershell
git remote add origin https://github.com/SEU_USUARIO/radar-consoles.git
git push -u origin main
```

### 4. Guardar o token como segredo

No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie dois:

| Nome | Valor |
|---|---|
| `TELEGRAM_TOKEN` | o token do @BotFather |
| `TELEGRAM_CHAT_ID` | o ID do grupo (com o sinal de menos) |

Os segredos não aparecem no código nem nos logs, mesmo com o repositório público.

### 5. Ligar

Na aba **Actions**, ative os workflows se o GitHub pedir, abra **radar** e clique em
**Run workflow** para a primeira rodada. Depois ele roda sozinho a cada ~10 minutos
(o GitHub às vezes atrasa em horários de pico).

## Ajustes

Tudo fica em `config.toml`:

- **Teto por item:** acrescente `cap = 6500` embaixo de `[items.ps5_pro]`, por exemplo.
- **Sensibilidade:** `drop_pct = 0.10` (10%). Use `0.05` para avisos mais frequentes.
- **Preço mínimo plausível:** `min_price`. Anúncios abaixo disso são ignorados porque
  quase sempre são jogos, acessórios ou golpe com título de console.

Para **pausar**, vá em **Actions → radar → ⋯ → Disable workflow**.

## Rodar no seu PC (teste)

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m radar --dry-run
.venv\Scripts\python -m pytest
```

`--dry-run` mostra os avisos na tela em vez de enviar e não altera o histórico.
