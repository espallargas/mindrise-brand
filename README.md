# mindrise-brand

Fonte única da identidade visual da **mindrise.** e de suas newsletters. Tokens, scripts e assets.

> Showcase: preenchido na Parte 2 (gerador de logo e conjunto núcleo).

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `tokens/` | `tokens.json` no padrão W3C DTCG 2025.10: cores e geometria |
| `scripts/` | `contrast.py` (checagem WCAG) e, na Parte 2, o gerador de logo |
| `assets/01-nucleo/` | logo, ícone, cor, tipografia da marca-mãe |
| `assets/02-newsletters/` | `ia/` e `tech/` (tech provisória) |
| `assets/03-aplicacoes/` | e-mail, web, redes sociais |
| `assets/04-templates/` | modelos de banner, capa e carrossel |
| `fonts/` | licenças e fontes (Gelasio, OFL) |
| `docs/` | notas de uso |

## Regra de ouro
O **SVG mestre** é a fonte. PNG, PDF e favicon são derivados por script e nunca editados à mão.

## Nome dos arquivos
`{marca}-{newsletter}-{tipo}-{variante}-{fundo}-{tamanho}.{ext}`

Exemplo: `mindrise-ia-logo-horizontal-claro-2400.png`. Para a marca-mãe, a newsletter é `mae`.

## Verificar contraste
```
python3 scripts/contrast.py
```
Sai com código 1 se algum par de texto ou logo ficar abaixo do mínimo WCAG.

## Geometria (resumo)
`u` = 1/9 do tamanho da fonte do wordmark. Barra 9u × 1,5u; arcos de raio 3u, 2u e 1u; altura do ícone 4,5u; zona de proteção 3u. Valores completos em `tokens/tokens.json`.

## Wordmark
Gelasio Bold (OFL), minúsculas, convertido em curvas nos arquivos finais.

Painel de progresso e decisões: página "Brand mindrise: memória e progresso" no Notion.
