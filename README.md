# Currency (Toman)

Alfred 6 workflow for currency, gold and coin conversion, with Iranian Toman at the free-market rate.

> **Version 2 needs Alfred 6.** It opens a native Alfred UI panel, which Alfred 5 doesn't have. On Alfred 5, use [v1.2.0](https://github.com/aliafshany/alfred-currency-toman/releases/tag/v1.2.0).

Type `$` and an amount. A panel opens with each result as a card, and it updates as you keep typing in its box.

| You type | You get |
|---|---|
| `$100 try` | 100 Turkish lira in USD and Toman |
| `$100 try eur` | in EUR only. Name as many targets as you want; "to", "in" and "as" are optional |
| `$100` | 100 USD in Toman, TRY and EUR |
| `$5m irt` | 5,000,000 Toman in USD and TRY |
| `$1200+350 try`, `$99x3 eur`, `$2^10 usd` | math works in the amount: `+ - * / x ^ ( )` |
| `$2 emami`, `$1 gram`, `$1 ounce irt`, `$0.01 btc` | gold coins and gold, from bonbast |
| `$1.5k aed`, `$2m tmn` | `k` and `m` suffixes |
| `$100 yen`, `$100 dirham`, `$100 usd as eur` | currency names work as well as codes |
| `$100 tr`, `$100 try to e` | half-typed currency: converts with the best match at once, other matches below as cards |
| `$100 turkiye`, `$50 oman`, `$100 dubai` | country names |

- ↩ copies the selected card's number. ⌘↩ pastes it with the currency into the front app. ↑↓ move between cards.
- On a suggestion card, ↩ puts that currency into the box.
- `irt`, `toman`, `tmn` mean Toman; `irr`, `rial` mean Rial. `tl`, `lira`, `dollar`, `euro`, `pound`, `dirham` work as names.
- Gold and coins: `emami`, `azadi`, `half`, `quarter`, `gerami`, `gram` (18k), `mithqal`, `ounce`, `btc`. For these a lone `.` is a decimal point: `$1.250 gram` is 1.25 grams.
- Symbols: `₺ $ € £ ¥ ₽ ﷼ ₹ ₩ ₪ ฿ ₼`, plus `Rs` (INR) and `kr` (SEK). Words: `ruble`/`rouble` (RUB), `kronor` (SEK), `krone` (NOK), `riyal` (SAR). `$5 million toman`, `$1e10 try` (scientific notation) and `$05 try` work; amounts above 10^15 and expressions longer than 200 characters get a clear message instead of a result.
- With the world rates unreachable, Toman, gold and coin queries (and `try`/`usd` against them) still work from bonbast.

## Currency names and guided picking

Any currency can be typed by name instead of code: `$100 yen` (JPY), `$100 baht`, `$100 krona`, `$100 pounds`. A name matches a whole word of the currency's name, or the start of a word from 3 letters (`$100 japan`, `$100 swiss`). Plurals work (`yens`, `pesos`). The subtitle shows the full name, for example "100 TRY (Turkish Lira) = 2.03 USD".

Words shared by several currencies go to the usual one: `dirham` is AED, `dollar` USD, `pound` GBP, `franc` CHF, `rupee` INR, `peso` MXN, `krona` SEK.

Country names work too, in English and Persian: `turkey`, `turkiye`, `türkiye`, `iran`, `uae`, `dubai`, `oman`, `iraq`, `uk`, `japan`, `ترکیه`, `امارات`, `عمان` and about 40 more. `us` is left out because it is an ordinary English word.

When the last word is unfinished or shared, the conversion uses the best match straight away (codes first, then popular currencies), and the other matches follow as `CODE — Name` suggestion cards (up to 15). ↩ on one completes the code in the case you typed:

- `$100 tr` converts TRY. TTD is listed below it as a suggestion card.
- `$100 try to e` converts to EUR. EGP, EMAMI, ERN and more are listed below.
- `$100 dinar` converts IQD (the usual dinar). Other dinars are listed if you type part of a name: `$100 dina`.

## Typed query or selected text

The workflow tells the two apart by the text itself.

- **Typed query** (one line, only amounts, operators, currency words, connectors and multipliers): every currency is kept in the order you typed it. The first is the source and the rest are targets, whatever the case: `$100 lira eur`, `$100 TL eur`, `$100 TRY eur` and `$100 try EUR` all convert TRY to EUR, and `₺50 to eur` does too. Math is on.
- **Selected text** (anything with other words or several lines): the first currency symbol, capitalised code, alias or Persian currency word is the source, and the amount is the number right next to it, with its multiplier. Math is off, so `Order 12345 total $99` is 99 USD, `20% off 100 TL` is 100 TRY, `3 for $10` is 10 USD, `$50 - $70` is 50 USD, and `Price 100 TL, size M` is 100 TRY. Bare lower-case codes and currency names are used only when the text has no symbol, alias or capitalised code; names must be whole words or start with 4+ letters. A currency after `to`, `in` or `as` becomes the target. If no currency is found the amount is read as USD and the subtitle says "no currency found — assuming USD".

A multiplier (`k`, `m`, `thousand`, `million`, `billion`, `هزار`, `میلیون`, `میلیارد`) counts only when it follows the number directly.

## Convert selected text

Give the Hotkey trigger a shortcut (Alfred removes hotkeys on import, so the trigger ships empty). Then select a price anywhere and press it:

- `₺1.299,90` → 26.45 USD and 7,097,454 Toman
- `$12.99`, `€50`, `£20`
- Persian text and digits: `۱۲۰ هزار تومان`

The same works from Alfred's Universal Actions: select text anywhere, or take a calculator or clipboard result, press → (the actions key), and choose **Convert Currency**. The workflow ships this trigger already connected to the converter.

The currency next to the number is the source (see "Typed query or selected text" above). Turkish and European number formats (`1.299,90`) and thousands separators are read correctly. Stray words such as "All" or "Top" are not taken as currency codes unless written in capitals.

Persian and Arabic text is cleaned first (ي ك ة ى become ی ک ه ی, ZWNJ and direction marks are dropped). Glued forms split: `هزارتومان`, `میلیونتومان`; suffixes are ignored: `تومانی`, `دلاری`, `یورویی`, `لیری`; `۲۵۰ت` means 250 Toman; and `و` joins groups: `۵ میلیون و ۵۰۰ هزار تومان` is 5,500,000 Toman. `سکه` is an Emami coin, `طلا` is gold (gram), `روپیه` is INR.

## Daily change

Toman, gold and coin rows show ▲ or ▼ with the change in price. When the workflow has a snapshot from about 24 hours earlier (±90 minutes), it compares with that; otherwise it compares with bonbast's rate for the previous day. The subtitle says which.

## Install

1. Download `Currency Toman.alfredworkflow` from Releases and double-click it.
2. For Toman, Rial, gold and coins, install the [bonbast](https://github.com/SamadiPour/bonbast) command-line tool:
   ```bash
   pipx install bonbast
   ```
   The workflow looks for it in `~/.local/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, or at the path you set in the workflow settings. Without it, every other currency still works.
3. The v1 rows showed flags drawn through `swift`. The v2 panel's cards are text only, so that step is no longer needed.

## Settings

Open the workflow in Alfred Preferences and choose **Configure Workflow…**:

| Setting | Default | Used when |
|---|---|---|
| Default targets | `USD,IRT` | you name one currency, e.g. `$100 try` |
| Targets for USD | `IRT,TRY,EUR` | `$100` or `$100 usd` |
| Targets for Toman | `USD,TRY` | `$5m irt` |
| Targets for gold and coins | `IRT,USD` | `$2 emami` |
| Daily change | on | ▲/▼ on Toman, gold and coin rows |
| bonbast path | empty | bonbast is somewhere unusual |

## Where the numbers come from

- **Toman, Rial, gold, coins:** [bonbast.com](https://www.bonbast.com) free-market *buy* prices, via the bonbast CLI. Cached for 15 minutes. Currencies bonbast quotes per 10 or 100 units (JPY, AMD, IQD) are converted to per-unit prices.
- **Everything else:** [open.er-api.com](https://www.exchangerate-api.com/docs/free) daily rates (no key), with the [fawazahmed0 currency API](https://github.com/fawazahmed0/exchange-api) on jsDelivr as fallback. Cached for 6 hours.
- Old cached prices are shown instantly and refreshed in the background. If bonbast prices are more than an hour old, the subtitle says so.

## Credits

Currency names come from Alfred's Currency Converter workflow (Alfred team, BSD-3-Clause).

## Privacy

The workflow only downloads exchange rates. It sends nothing about you or your queries anywhere: the rate requests contain no amounts or selections. Requests go through `/usr/bin/curl`; if a direct request fails and a local HTTP proxy is listening on `127.0.0.1:1082`, it retries through that proxy once.

## Requirements

Alfred 6 with the Powerpack, macOS with `/usr/bin/python3` (Xcode Command Line Tools).

## Development

`tools/package.sh` builds `dist/Currency Toman.alfredworkflow` from `workflow/`.

## License

MIT
