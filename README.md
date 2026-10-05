# Currency (Toman)

Alfred 5 workflow for currency, gold and coin conversion, with Iranian Toman at the free-market rate.

Type `$` and an amount. Results show as you type, with the country's flag on each row.

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
| `$100 tu`, `$100 try to e` | half-typed currency: pick from a list, ⇥ completes it |

- ↩ copies the number. ⌘↩ pastes it into the front app.
- `irt`, `toman`, `tmn` mean Toman; `irr`, `rial` mean Rial. `tl`, `lira`, `dollar`, `euro`, `pound`, `dirham` work as names.
- Gold and coins: `emami`, `azadi`, `half`, `quarter`, `gerami`, `gram` (18k), `mithqal`, `ounce`, `btc`.

## Currency names and guided picking

Any currency can be typed by name instead of code: `$100 yen` (JPY), `$100 baht`, `$100 krona`, `$100 pounds`. A name matches a whole word of the currency's name, or the start of a word from 3 letters (`$100 japan`, `$100 swiss`). Plurals work (`yens`, `pesos`). The subtitle shows the full name, for example "100 TRY (Turkish Lira) = 2.03 USD".

Words shared by several currencies go to the usual one: `dirham` is AED, `dollar` USD, `pound` GBP, `franc` CHF, `rupee` INR, `peso` MXN, `krona` SEK. Other shared words, such as `dinar`, and half-typed ones list the candidates instead of guessing.

When the last word is unfinished or ambiguous, rows show `CODE — Name` (up to 15). Press ⇥ on a row to put its code into the query and keep typing:

- `$100 tu` lists TRY, TMT, TND, TVD. ⇥ on TRY gives `$100 TRY `.
- `$100 try to e` lists EUR, EGP, EMAMI, ERN, ETB and more. ⇥ on EUR gives `$100 try to EUR `.
- A complete code, alias or single name (`try`, `tl`, `yen`) shows the conversion straight away.

Like lowercase codes, names are ignored when the text already has a currency symbol or a capitalised code, so selected prose such as "Only $5, real deal" is not read as currency names. After the `$` keyword, `$100 try yen` works; `$100 TRY yen` ignores `yen`, so write codes and names in lowercase when you mix them.

## Convert selected text

Give the Hotkey trigger a shortcut (Alfred removes hotkeys on import, so the trigger ships empty). Then select a price anywhere and press it:

- `₺1.299,90` → 26.45 USD and 7,097,454 Toman
- `$12.99`, `€50`, `£20`
- Persian text and digits: `۱۲۰ هزار تومان`

The same works from Alfred's Universal Actions: select text anywhere, or take a calculator or clipboard result, press → (the actions key), and choose **Convert Currency**. The workflow ships this trigger already connected to the converter.

The first currency symbol or code in the selection is the source. Turkish and European number formats (`1.299,90`) and thousands separators are read correctly. Stray words such as "All" or "Top" are not taken as currency codes unless written in capitals.

## Daily change

Toman, gold and coin rows show ▲ or ▼ with the change in price. When the workflow has a snapshot from about 24 hours earlier (±90 minutes), it compares with that; otherwise it compares with bonbast's rate for the previous day. The subtitle says which.

## Install

1. Download `Currency Toman.alfredworkflow` from Releases and double-click it.
2. For Toman, Rial, gold and coins, install the [bonbast](https://github.com/SamadiPour/bonbast) command-line tool:
   ```bash
   pipx install bonbast
   ```
   The workflow looks for it in `~/.local/bin`, `/opt/homebrew/bin` and `/usr/local/bin`, or at the path you set in the workflow settings. Without it, every other currency still works.
3. Optional: flags are drawn with the system emoji font through `swift`, which comes with the Xcode Command Line Tools (`xcode-select --install`). Without it, rows use the workflow icon.

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

Alfred 5 with the Powerpack, macOS with `/usr/bin/python3` (Xcode Command Line Tools).

## Development

`tools/package.sh` builds `dist/Currency Toman.alfredworkflow` from `workflow/`.

## License

MIT
