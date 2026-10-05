#!/usr/bin/python3
"""Alfred Script Filter: currency, gold and coin conversion with Iranian Toman, keyword "$".
  $100 try          -> 100 TRY in USD and Toman
  $100 try eur      -> in EUR only (several targets allowed, "to"/"in"/"as" optional)
  $100              -> 100 USD in Toman, TRY, EUR
  $5m irt           -> 5,000,000 Toman in USD, TRY
  $1200+350 try     -> math works in the amount: + - * / x ^ ( )
  $2 emami          -> gold coins and gold: emami, azadi, half, quarter, gerami, gram, mithqal, ounce, btc
  $100 yen          -> currency names work too (yen, rupee, franc …); a half-typed or ambiguous
                       last word lists candidates, Tab completes: $100 tu, $100 try to e
Selected text works too (hotkey): "₺1.299,90", "$12.99", "۱۲۰ هزار تومان".
World rates: open.er-api.com (daily, no key), jsDelivr currency-api as fallback.
Toman, Rial, gold and coins: bonbast free-market buy price, via the bonbast CLI.
Old cached data is shown at once and refreshed in the background."""
import ast
import datetime
import json
import math
import operator
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("alfred_workflow_cache", "/tmp/alfred-currency")
ICONS = os.path.join(CACHE, "icons")
MAX_AGE = {"world": 6 * 3600, "bonbast": 15 * 60, "history": 6 * 3600}
TOMAN = {"IRT": 1.0, "IRR": 0.1}      # Toman per 1 unit
COINS = {                             # code: (bonbast key, label)
    "EMAMI": ("emami1", "Emami coin"), "AZADI": ("azadi1", "Azadi coin"),
    "HALF": ("azadi1_2", "½ Azadi coin"), "QUARTER": ("azadi1_4", "¼ Azadi coin"),
    "GERAMI": ("azadi1g", "Gerami coin"), "MITHQAL": ("mithqal", "Gold mithqal"),
    "GRAM": ("gol18", "18k gold gram"), "OUNCE": ("ounce", "Gold ounce"), "BTC": ("bitcoin", "Bitcoin"),
}
USD_PRICED = {"ounce", "bitcoin"}     # bonbast quotes these in dollars
LOCAL = set(TOMAN) | set(COINS)       # anything that needs bonbast
ALIASES = {
    "tl": "TRY", "lira": "TRY", "dollar": "USD", "dollars": "USD", "usdt": "USD", "euro": "EUR",
    "euros": "EUR", "pound": "GBP", "dirham": "AED", "yuan": "CNY",
    "toman": "IRT", "tomans": "IRT", "tmn": "IRT", "rial": "IRR", "rials": "IRR",
    "coin": "EMAMI", "sekke": "EMAMI", "nim": "HALF", "rob": "QUARTER", "gold": "GRAM",
    "tala": "GRAM", "grams": "GRAM", "18k": "GRAM", "mesghal": "MITHQAL", "mesqal": "MITHQAL",
    "oz": "OUNCE", "xau": "OUNCE", "bitcoin": "BTC",
}
SYMBOLS = {"₺": "TRY", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₽": "RUB", "﷼": "IRR",
           "تومان": "IRT", "تومن": "IRT", "ریال": "IRR", "دلار": "USD", "یورو": "EUR",
           "لیر": "TRY", "لیره": "TRY", "درهم": "AED", "پوند": "GBP"}
MULTIPLIERS = {"k": 1e3, "m": 1e6, "هزار": 1e3, "میلیون": 1e6, "میلیارد": 1e9}
LABEL = {"IRT": "Toman", "IRR": "Rial", **{c: v[1] for c, v in COINS.items()}}
# Currency names: taken from Alfred's official Currency Converter workflow
# (Alfred team, BSD-3-Clause), plus the local items this workflow adds.
CURRENCY_NAMES = {
    "AED": "United Arab Emirates Dirham", "AFN": "Afghan Afghani", "ALL": "Albanian Lek",
    "AMD": "Armenian Dram", "ANG": "Netherlands Antillian Guilder", "AOA": "Angolan Kwanza",
    "ARS": "Argentine Peso", "AUD": "Australian Dollar", "AWG": "Aruban Florin",
    "AZN": "Azerbaijani Manat", "BAM": "Bosnia and Herzegovina Mark", "BBD": "Barbados Dollar",
    "BDT": "Bangladeshi Taka", "BGN": "Bulgarian Lev", "BHD": "Bahraini Dinar",
    "BIF": "Burundian Franc", "BMD": "Bermudian Dollar", "BND": "Brunei Dollar",
    "BOB": "Bolivian Boliviano", "BRL": "Brazilian Real", "BSD": "Bahamian Dollar",
    "BTN": "Bhutanese Ngultrum", "BWP": "Botswana Pula", "BYN": "Belarusian Rouble",
    "BZD": "Belize Dollar", "CAD": "Canadian Dollar", "CDF": "Congolese Franc",
    "CHF": "Swiss Franc", "CLF": "Chilean Unidad de Fomento", "CLP": "Chilean Peso",
    "CNH": "Chinese Renminbi", "CNY": "Chinese Renminbi", "COP": "Colombian Peso",
    "CRC": "Costa Rican Colon", "CUP": "Cuban Peso", "CVE": "Cape Verdean Escudo",
    "CZK": "Czech Koruna", "DJF": "Djiboutian Franc", "DKK": "Danish Krone",
    "DOP": "Dominican Peso", "DZD": "Algerian Dinar", "EGP": "Egyptian Pound",
    "ERN": "Eritrean Nakfa", "ETB": "Ethiopian Birr", "EUR": "Euro",
    "FJD": "Fiji Dollar", "FKP": "Falkland Islands Pound", "FOK": "Faroese Króna",
    "GBP": "United Kingdom Pound", "GEL": "Georgian Lari", "GGP": "Guernsey Pound",
    "GHS": "Ghanaian Cedi", "GIP": "Gibraltar Pound", "GMD": "Gambian Dalasi",
    "GNF": "Guinean Franc", "GTQ": "Guatemalan Quetzal", "GYD": "Guyanese Dollar",
    "HKD": "Hong Kong Dollar", "HNL": "Honduran Lempira", "HRK": "Croatian Kuna",
    "HTG": "Haitian Gourde", "HUF": "Hungarian Forint", "IDR": "Indonesian Rupiah",
    "ILS": "Israeli New Shekel", "IMP": "Manx Pound", "INR": "Indian Rupee",
    "IQD": "Iraqi Dinar", "IRR": "Iranian Rial", "ISK": "Icelandic Króna",
    "JEP": "Jersey Pound", "JMD": "Jamaican Dollar", "JOD": "Jordanian Dinar",
    "JPY": "Japanese Yen", "KES": "Kenyan Shilling", "KGS": "Kyrgyzstani Som",
    "KHR": "Cambodian Riel", "KID": "Kiribati Dollar", "KMF": "Comorian Franc",
    "KRW": "South Korean Won", "KWD": "Kuwaiti Dinar", "KYD": "Cayman Islands Dollar",
    "KZT": "Kazakhstani Tenge", "LAK": "Lao Kip", "LBP": "Lebanese Pound",
    "LKR": "Sri Lanka Rupee", "LRD": "Liberian Dollar", "LSL": "Lesotho Loti",
    "LYD": "Libyan Dinar", "MAD": "Moroccan Dirham", "MDL": "Moldovan Leu",
    "MGA": "Malagasy Ariary", "MKD": "Macedonian Denar", "MMK": "Burmese Kyat",
    "MNT": "Mongolian Tögrög", "MOP": "Macanese Pataca", "MRU": "Mauritanian Ouguiya",
    "MUR": "Mauritian Rupee", "MVR": "Maldivian Rufiyaa", "MWK": "Malawian Kwacha",
    "MXN": "Mexican Peso", "MYR": "Malaysian Ringgit", "MZN": "Mozambican Metical",
    "NAD": "Namibian Dollar", "NGN": "Nigerian Naira", "NIO": "Nicaraguan Córdoba",
    "NOK": "Norwegian Krone", "NPR": "Nepalese Rupee", "NZD": "New Zealand Dollar",
    "OMR": "Omani Rial", "PAB": "Panamanian Balboa", "PEN": "Peruvian Sol",
    "PGK": "Papua New Guinean Kina", "PHP": "Philippine Peso", "PKR": "Pakistani Rupee",
    "PLN": "Polish Złoty", "PYG": "Paraguayan Guaraní", "QAR": "Qatari Riyal",
    "RON": "Romanian Leu", "RSD": "Serbian Dinar", "RUB": "Russian Rouble",
    "RWF": "Rwandan Franc", "SAR": "Saudi Riyal", "SBD": "Solomon Islands Dollar",
    "SCR": "Seychellois Rupee", "SDG": "Sudanese Pound", "SEK": "Swedish Krona",
    "SGD": "Singapore Dollar", "SHP": "Saint Helena Pound", "SLE": "Sierra Leonean Leone",
    "SLL": "Sierra Leonean Leone", "SOS": "Somali Shilling", "SRD": "Surinamese Dollar",
    "SSP": "South Sudanese Pound", "STN": "São Tomé and Príncipe Dobra", "SYP": "Syrian Pound",
    "SZL": "Eswatini Lilangeni", "THB": "Thai Baht", "TJS": "Tajikistani Somoni",
    "TMT": "Turkmenistan Manat", "TND": "Tunisian Dinar", "TOP": "Tongan Paʻanga",
    "TRY": "Turkish Lira", "TTD": "Trinidad and Tobago Dollar", "TVD": "Tuvaluan Dollar",
    "TWD": "New Taiwan Dollar", "TZS": "Tanzanian Shilling", "UAH": "Ukrainian Hryvnia",
    "UGX": "Ugandan Shilling", "USD": "United States Dollar", "UYU": "Uruguayan Peso",
    "UZS": "Uzbekistani So'm", "VES": "Venezuelan Bolívar Soberano", "VND": "Vietnamese Đồng",
    "VUV": "Vanuatu Vatu", "WST": "Samoan Tālā", "XAF": "Central African Franc",
    "XCD": "East Caribbean Dollar", "XCG": "Caribbean Guilder", "XDR": "Special Drawing Rights",
    "XOF": "West African Franc", "XPF": "CFP Franc", "YER": "Yemeni Rial",
    "ZAR": "South African Rand", "ZMW": "Zambian Kwacha", "ZWG": "Zimbabwean ZiG",
    "ZWL": "Zimbabwean Dollar",
    "IRT": "Iranian Toman", **{c: v[1] for c, v in COINS.items()},
}
NAME_STOP = {"and", "of", "the"}         # words of a name that never identify it
# A bare word that several names share goes to the usual currency (dirham -> AED, not MAD).
PREFERRED = {"dirham": "AED", "dollar": "USD", "pound": "GBP", "franc": "CHF", "rupee": "INR",
             "peso": "MXN", "krona": "SEK"}
POPULAR = ["USD", "EUR", "GBP", "TRY", "JPY", "CHF", "CAD", "AUD", "CNY", "AED", "INR", "IRT"]
CONNECTORS = ("to", "in", "as", "=", "به")
MAX_CANDIDATES = 15
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")


def setting(var, default):
    """Comma-separated currency list from Configure Workflow…"""
    raw = os.environ.get(var) or default
    return [ALIASES.get(c.strip().lower(), c.strip().upper()) for c in raw.split(",") if c.strip()]


DEFAULT_TARGETS = setting("default_targets", "USD,IRT")
TOMAN_TARGETS = setting("toman_targets", "USD,TRY")
COIN_TARGETS = setting("gold_targets", "IRT,USD")
USD_TARGETS = setting("usd_targets", "IRT,TRY,EUR")
SHOW_CHANGE = os.environ.get("show_change", "1") != "0"


def locks_pending():
    """True while a refresh or icon render still holds its lock."""
    for name in ("world", "bonbast", "history"):
        if os.path.exists(path(name) + ".lock"):
            return True
    return os.path.exists(os.path.join(CACHE, "icons.lock"))


def emit(items):
    payload = {"items": items}
    if locks_pending():
        payload["rerun"] = 1  # prices/icons show up without another keystroke
    print(json.dumps(payload, ensure_ascii=False))


# ---------- data sources ----------

def find_bonbast():
    # Alfred runs scripts with a bare PATH, so check the usual pipx/Homebrew spots too.
    for c in (os.environ.get("bonbast_path", ""), "~/.local/bin/bonbast",
              "/opt/homebrew/bin/bonbast", "/usr/local/bin/bonbast"):
        c = os.path.expanduser(c)
        if c and os.access(c, os.X_OK):
            return c
    return shutil.which("bonbast")


def run_bonbast(*args):
    exe = find_bonbast()
    if not exe:
        raise FileNotFoundError("bonbast not installed (pipx install bonbast)")
    out = subprocess.run([exe, *args], capture_output=True, check=True, timeout=12).stdout
    return json.loads(out.decode("utf-8"))


def proxy_listening():
    """True when the local HTTP proxy is accepting connections."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        sock.connect(("127.0.0.1", 1082))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def curl(url):
    # curl, not urllib: some endpoints reject the old LibreSSL in /usr/bin/python3.
    # /usr/bin/curl ignores the macOS system proxy, so retry once via the local proxy.
    cmd = ["/usr/bin/curl", "-sf", "--max-time", "8", url]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, OSError):
        if not proxy_listening():
            raise
        out = subprocess.run(
            ["/usr/bin/curl", "-x", "http://127.0.0.1:1082", "-sf", "--max-time", "8", url],
            capture_output=True, check=True).stdout
    return json.loads(out.decode("utf-8"))


def fetch_world():
    try:
        d = curl("https://open.er-api.com/v6/latest/USD")
        if d.get("result") == "success":
            return {"rates": d["rates"], "date": d["time_last_update_utc"][5:16]}
    except Exception:
        pass
    d = curl("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json")
    return {"rates": {k.upper(): v for k, v in d["usd"].items()}, "date": d["date"]}


def split_bonbast(raw):
    """bonbast JSON -> Toman per unit for currencies and for gold/coins."""
    raw = {k.lower(): v for k, v in raw.items() if isinstance(v, dict)}
    rates, coins = {}, {}
    for key, v in raw.items():
        try:
            price = float(v.get("buy") or v.get("price"))
        except (TypeError, ValueError):
            continue
        if price > 0 and len(key) == 3 and key.isalpha():
            # "10 Japanese Yen" / "100 Iraqi Dinar": buy is the price of that many units.
            match = re.match(r"(\d+)\s", str(v.get("name") or ""))
            if match:
                count = int(match.group(1))
                if count > 0:
                    price /= count
            rates[key.upper()] = price
    for code, (key, _) in COINS.items():
        v = raw.get(key)
        if not v:
            continue
        try:
            price = float(v.get("buy") or v.get("price"))
        except (TypeError, ValueError):
            continue
        if key in USD_PRICED:
            if "USD" not in rates:
                continue
            price *= rates["USD"]
        if price > 0:
            coins[code] = price
    return rates, coins


def short_time(iso):
    """'2026-10-05T01:06:29+03:00' -> '01:06' today, '4 Oct 01:06' on another day."""
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    if t.date() == datetime.datetime.now(t.tzinfo).date():
        return t.strftime("%H:%M")
    return f"{t.day} {t.strftime('%b %H:%M')}"


def iso_now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def fetch_bonbast():
    rates, coins = split_bonbast(run_bonbast("export"))
    if "USD" not in rates:
        raise ValueError("bonbast returned no USD rate")
    return {"rates": rates, "coins": coins, "date": iso_now()}


def fetch_history():
    day = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    rates, coins = split_bonbast(run_bonbast("history", "--date", day, "--json"))
    return {"rates": rates, "coins": coins, "date": day, "ts": iso_now()}


FETCHERS = {"world": fetch_world, "bonbast": fetch_bonbast, "history": fetch_history}


def path(name):
    return os.path.join(CACHE, f"{name}.json")


def fail_path(name):
    return os.path.join(CACHE, f"{name}.fail")


def marker_fresh(marker, seconds=60):
    try:
        return time.time() - os.path.getmtime(marker) < seconds
    except OSError:
        return False


def touch(marker):
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    open(marker, "w").close()


def workflow_data():
    return os.environ.get("alfred_workflow_data") or os.path.expanduser(
        "~/Library/Application Support/Alfred/Workflow Data/"
        + os.environ.get("alfred_workflow_bundleid", "com.aliafshany.currency-toman"))


def snapshot_file():
    return os.path.join(workflow_data(), "snapshots.jsonl")


def append_snapshot(rates, coins):
    """Keep one bonbast quote per successful refresh, dropping anything older than 72 h."""
    directory = workflow_data()
    os.makedirs(directory, exist_ok=True)
    dest = snapshot_file()
    now = time.time()
    cutoff = now - 72 * 3600
    rows = []
    try:
        with open(dest, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                stamp = row.get("t") if isinstance(row, dict) else None
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
                    continue
                if float(stamp) < cutoff:
                    continue
                rows.append({
                    "t": float(stamp),
                    "rates": row.get("rates") or {},
                    "coins": row.get("coins") or {},
                })
    except OSError:
        pass
    rows.append({"t": now, "rates": rates, "coins": coins})
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, dest)


def snapshot_around(target, window):
    """The saved quote whose timestamp is closest to target, if it falls inside ±window."""
    best = None
    best_dt = None
    try:
        with open(snapshot_file(), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                stamp = row.get("t") if isinstance(row, dict) else None
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
                    continue
                if not isinstance(row.get("rates"), dict):
                    continue
                dt = abs(float(stamp) - target)
                if dt <= window and (best_dt is None or dt < best_dt):
                    best = {"t": float(stamp), "rates": row["rates"], "coins": row.get("coins") or {}}
                    best_dt = dt
    except OSError:
        return None
    return best


def refresh(name):
    data = FETCHERS[name]()
    data["fetched"] = time.time()
    if name == "bonbast":
        append_snapshot(data["rates"], data["coins"])
    os.makedirs(CACHE, exist_ok=True)
    with open(path(name) + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path(name) + ".tmp", path(name))
    return data


def background(*args, lock):
    """Run this script again detached. A failed refresh backs off for 60 s."""
    fail = fail_path(args[1]) if tuple(args[:1]) == ("--refresh",) and len(args) > 1 else None
    if marker_fresh(lock) or (fail and marker_fresh(fail)):
        return
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    open(lock, "w").close()
    subprocess.Popen([sys.executable, os.path.abspath(__file__), *args],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def load(name, wait=True):
    """Return (data, very_old). Old data is returned at once and refreshed in the background.
    With wait=False a missing cache returns (None, False) and is fetched in the background."""
    try:
        with open(path(name), encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        if marker_fresh(fail_path(name)) or marker_fresh(path(name) + ".lock"):
            if not wait:
                return None, False
            raise RuntimeError(f"{name} refresh failed")
        if not wait:
            background("--refresh", name, lock=path(name) + ".lock")
            return None, False
        try:
            return refresh(name), False
        except Exception:
            try:
                touch(fail_path(name))
            except OSError:
                pass
            raise
    age = time.time() - cached["fetched"]
    if age > MAX_AGE[name]:
        background("--refresh", name, lock=path(name) + ".lock")
    return cached, age > 3 * MAX_AGE[name]


# ---------- icons ----------

def flag(code):
    if code in TOMAN:
        return "🇮🇷"
    if code in COINS:
        return "🪙"
    if len(code) == 3 and code.isalpha() and not code.startswith("X"):
        return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code[:2])
    return "💱"


def icon(code, all_codes):
    p = os.path.join(ICONS, f"{code}.png")
    if os.path.exists(p):
        return {"path": p}
    if not os.path.exists(os.path.join(ICONS, ".done")):
        background("--icons", *sorted(all_codes), lock=os.path.join(CACHE, "icons.lock"))
    return None


def render_icons(codes):
    """Draw each currency's flag with the system emoji font (needs Xcode Command Line Tools)."""
    os.makedirs(ICONS, exist_ok=True)
    listing = os.path.join(CACHE, "icons.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("".join(f"{c}\t{flag(c)}\n" for c in codes))
    swift = shutil.which("swift") or "/usr/bin/swift"
    subprocess.run([swift, os.path.join(HERE, "render_flags.swift"), listing, ICONS],
                   check=True, capture_output=True, timeout=180)
    open(os.path.join(ICONS, ".done"), "w").close()


# ---------- parsing ----------

def norm_number(s):
    """'1.299,90' -> '1299.90', '1,200' -> '1200', '2,5' -> '2.5', '12.99' stays."""
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            return s.replace(",", "")
        return s.replace(".", "").replace(",", ".")
    if "," in s:
        return s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    if re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", s):
        return s.replace(".", "")    # 1.299 (Turkish/European thousands)
    return s


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def finite_float(result):
    if isinstance(result, complex) or not isinstance(result, float) or not math.isfinite(result):
        raise ValueError("not finite")
    return result


def safe_eval(expr):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Num):        # Python 3.7 and older
            return float(n.n)
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            right = ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return finite_float(OPS[type(n.op)](ev(n.left), right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
            return finite_float(OPS[type(n.op)](ev(n.operand)))
        raise ValueError("not arithmetic")
    return finite_float(ev(ast.parse(expr, mode="eval")))


# A number ends on a digit, so a trailing "." or "," stays out of the token.
TOKEN = re.compile(r"(?P<num>\d(?:[\d.,]*\d)?)|(?P<word>[A-Za-z]+|[؀-ۿ]+)|(?P<sym>[₺$€£¥₽﷼])|(?P<op>[-+*/×÷^()])")


def plain_text(text):
    """Lower-case ASCII form: 'Króna' -> 'krona', 'Złoty' -> 'zloty'."""
    text = text.translate(str.maketrans("łŁđĐ", "lLdD"))     # no accent form to strip
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


NAME_WORDS = {code: [w for w in re.findall(r"[a-z0-9]+", plain_text(name)) if w not in NAME_STOP]
              for code, name in CURRENCY_NAMES.items()}


def name_matches(text, known, prefix_from):
    """Codes whose name holds the typed word as a whole word, and as a word prefix
    (prefix only counts from prefix_from letters). A trailing plural s is ignored."""
    low = plain_text(text)
    forms = [low] + ([low[:-1]] if len(low) > 3 and low.endswith("s") else [])
    whole, prefix = [], []
    for code, words in NAME_WORDS.items():
        if code not in known:
            continue
        if any(w in forms for w in words):
            whole.append(code)
        elif len(low) >= prefix_from and any(w.startswith(f) for w in words for f in forms):
            prefix.append(code)
    return whole, prefix


def resolve_name(text, known):
    """The one currency a word names, else None. A whole word beats a prefix of the
    name; a prefix needs 3+ letters; PREFERRED settles shared words like "dirham"."""
    if not (text.isascii() and text.isalpha()):
        return None
    whole, prefix = name_matches(text, known, 3)
    pool = whole or prefix
    if len(pool) > 1 and whole:
        low = plain_text(text)
        preferred = PREFERRED.get(low) or PREFERRED.get(low[:-1])
        if preferred in whole:
            return preferred
    return pool[0] if len(pool) == 1 else None


def word_class(text, known):
    """How a word should be read: symbol/alias/uppercase outrank a bare code, then names."""
    low = text.lower()
    if low in MULTIPLIERS or low == "x" or low in CONNECTORS:
        return "plain"
    if text in SYMBOLS:
        return "symbol"
    if low in ALIASES:
        return "alias"
    upper = text.upper()
    if upper in known and text.isupper():
        return "upper"
    if upper in known:
        return "weak"
    if resolve_name(text, known):
        return "name"
    if len(text) == 3 and text.isascii() and text.isupper():
        return "upper-unknown"
    if len(text) == 3 and text.isascii():
        return "weak-unknown"
    return "plain"


def absorb_group(prev, text):
    """Join a thousands group that follows a number ('1' + '299,90' -> '1299.90')."""
    grouped = re.fullmatch(r"(\d{3})(?:[.,](\d+))?", text)
    if not grouped:
        return prev
    merged = prev + grouped.group(1)
    if grouped.group(2):
        merged += "." + grouped.group(2)
    return merged


def parse(q, known):
    """Return (amount, [codes], unknown, expression shown, bad expression or None)."""
    q = q.translate(DIGITS)
    matches = list(TOKEN.finditer(q))
    strong = False
    for match in matches:
        if match.lastgroup == "sym":
            strong = True
        elif match.lastgroup == "word" and word_class(match.group(), known) in ("symbol", "alias", "upper"):
            strong = True
    expr, codes, unknown = [], [], []
    typed_math = False
    last_num_end = None
    since_op = True
    for match in matches:
        kind, text = match.lastgroup, match.group()
        if kind == "num":
            # Two numbers with nothing between them: keep the first, unless the
            # next one is a 3-digit group sitting right after the previous ("1 299,90").
            if last_num_end is not None and not since_op:
                gap = q[last_num_end:match.start()]
                prev = expr[-1] if expr else ""
                if (re.fullmatch(r"\s*", gap) and re.fullmatch(r"\d{3}(?:[.,]\d+)?", text)
                        and re.fullmatch(r"\d+", prev)):
                    expr[-1] = absorb_group(prev, text)
                    last_num_end = match.end()
                continue
            expr.append(norm_number(text))
            last_num_end = match.end()
            since_op = False
            continue
        if kind == "op":
            typed_math = typed_math or text not in "()"
            expr.append({"×": "*", "÷": "/", "^": "**"}.get(text, text))
            since_op = True
            continue
        if kind == "sym":
            codes.append(SYMBOLS[text])
            continue
        low = text.lower()
        if low in MULTIPLIERS and expr and expr[-1][-1:].isdigit():
            expr[-1] = f"({expr[-1]}*{MULTIPLIERS[low]:.0f})"
            continue
        if low == "x" and expr:
            typed_math = True
            expr.append("*")
            since_op = True
            continue
        if low in CONNECTORS:
            continue
        wk = word_class(text, known)
        if wk == "symbol":
            codes.append(SYMBOLS[text])
        elif wk == "alias":
            codes.append(ALIASES[low])
        elif wk == "upper":
            codes.append(text.upper())
        elif wk == "weak" and not strong:
            codes.append(text.upper())
        elif wk == "name" and not strong:     # like a bare code: prose next to a symbol is ignored
            codes.append(resolve_name(text, known))
        elif wk == "upper-unknown":
            unknown.append(text.upper())
        elif wk == "weak-unknown" and not strong:
            unknown.append(text.upper())
    amount = 1.0
    shown = ""
    bad = None
    if expr:
        joined = "".join(expr)
        try:
            amount = safe_eval(joined)
            shown = joined.replace("**", "^") if typed_math else ""
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError, ArithmeticError):
            bad = joined.replace("**", "^")
    return amount, codes, unknown, shown, bad


def pending_word(q, known):
    """The unfinished last word as (start offset, candidate codes), or None.
    Unfinished = a word at the very end that is no exact code, alias, symbol or single name
    but is the start of a code or a currency name."""
    matches = list(TOKEN.finditer(q.translate(DIGITS)))
    if not matches:
        return None
    last = matches[-1]
    text, low = last.group(), last.group().lower()
    if last.lastgroup != "word" or q[last.end():].strip() or not text.isascii():
        return None
    if (low in MULTIPLIERS or low == "x" or low in CONNECTORS or text in SYMBOLS
            or low in ALIASES or text.upper() in known or resolve_name(text, known)):
        return None
    if len(matches) > 1 and not any(
            m.lastgroup in ("num", "sym") or word_class(m.group(), known) not in ("plain", "weak-unknown")
            for m in matches[:-1]):
        return None                       # prose with no amount or currency in front of it
    whole, prefix = name_matches(text, known, 1)
    group = {c: 2 for c in prefix}                       # name starts with the text
    group.update({c: 1 for c in whole})                  # name has it as a whole word
    group.update({c: 0 for c in known if c.lower().startswith(low)})   # code starts with it
    used = set(parse(q[:last.start()], known)[1])
    pool = [c for c in group if c not in used] or list(group)
    pool.sort(key=lambda c: (group[c], POPULAR.index(c) if c in POPULAR else len(POPULAR), c))
    return (last.start(), pool[:MAX_CANDIDATES]) if pool else None


# ---------- output ----------

def fmt_small(x):
    """Fixed decimals, about 4 significant digits, never scientific notation."""
    ax = abs(x)
    if ax == 0:
        return "0"
    places = max(0, 3 - int(math.floor(math.log10(ax))))
    text = f"{x:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-", "-0"):
        return "0"
    return text


def fmt(x, code="", sep=True):
    if code in TOMAN or abs(x) >= 1000:
        return f"{x:,.0f}" if sep else f"{x:.0f}"
    if x == 0:
        return "0"
    if abs(x) >= 1:
        s = f"{x:,.2f}" if sep else f"{x:.2f}"
        return s[:-3] if s.endswith(".00") else s
    return fmt_small(x)


def fmt_amount(x, code):
    """The user's own amount: keep cents (1,299.90), unlike converted results."""
    if code in TOMAN or x == int(x):
        return f"{x:,.0f}"
    return f"{x:,.2f}" if abs(x) >= 1 else fmt_small(x)


def main():
    q = " ".join(sys.argv[1:]).strip()
    if not q:
        emit([{"title": "Type an amount and a currency", "valid": False,
               "subtitle": "$100 try  ·  $100 try eur  ·  $5m irt  ·  $1200+350 try  ·  $2 emami"}])
        return
    try:
        world, world_old = load("world")
    except Exception as exc:
        emit([{"title": "Couldn't get exchange rates", "valid": False,
               "subtitle": f"{type(exc).__name__} — check internet/VPN"}])
        return
    W = world["rates"]
    known = set(W) | LOCAL
    amount, codes, unknown, shown, bad = parse(q, known)
    if bad:
        emit([{"title": f"Invalid expression: {q}", "valid": False}])
        return
    pending = pending_word(q, known)
    if pending:
        start, found = pending
        rows = []
        for code in found:
            row = {"title": f"{code} — {CURRENCY_NAMES.get(code, code)}", "valid": False,
                   "subtitle": f"Tab to use {code}", "autocomplete": f"{q[:start]}{code} "}
            ic = icon(code, known)
            if ic:
                row["icon"] = ic
            rows.append(row)
        emit(rows)
        return
    if unknown and not codes:
        emit([{"title": f"Unknown currency: {', '.join(unknown)}", "valid": False,
               "subtitle": "Use 3-letter codes: USD EUR TRY GBP AED … names like yen, or toman, emami, gram"}])
        return
    src = codes[0] if codes else "USD"
    targets = [c for c in dict.fromkeys(codes[1:]) if c != src and c in known]
    if not targets:
        targets = (USD_TARGETS if src == "USD" else TOMAN_TARGETS if src in TOMAN
                   else COIN_TARGETS if src in COINS else DEFAULT_TARGETS)
        targets = [t for t in targets if t != src and t in known]

    bon = bon_err = None
    bon_old = False
    ref = None
    ref_label = "yesterday"
    if src in LOCAL or any(t in LOCAL for t in targets):
        try:
            bon, bon_old = load("bonbast")
        except Exception as exc:
            bon_err = str(exc) if isinstance(exc, FileNotFoundError) else type(exc).__name__
        if bon and SHOW_CHANGE:
            snap = snapshot_around(time.time() - 86400, 90 * 60)
            if snap:
                ref, ref_label = snap, "24h ago"
            else:
                try:
                    hist, _ = load("history", wait=False)
                except Exception:
                    hist = None
                if hist:
                    ref, ref_label = hist, "yesterday"

    def toman_per(c, data, cross=True):   # Toman for 1 unit of c, or None
        if c in TOMAN:
            return TOMAN[c]
        if c in COINS:
            return data.get("coins", {}).get(c)
        if c in data["rates"]:
            return data["rates"][c]
        return data["rates"]["USD"] / W[c] if cross and c in W else None

    sname = LABEL.get(src, src)
    full = CURRENCY_NAMES.get(src, "")
    sfull = f"{sname} ({full})" if full and sname == src else sname   # Toman, coins: label is the name
    all_codes = known
    items = []
    for tgt in targets:
        name = LABEL.get(tgt, tgt)
        change = ""
        if src in LOCAL or tgt in LOCAL:
            if bon is None:
                items.append({"title": f"{name}: bonbast unavailable", "valid": False,
                              "subtitle": f"{bon_err or 'error'} — Toman, gold and coin prices come from bonbast"})
                continue
            a, b = toman_per(src, bon), toman_per(tgt, bon)
            if not a or not b:
                missing = src if not a else tgt
                items.append({"title": f"No bonbast price for {LABEL.get(missing, missing)}", "valid": False,
                              "subtitle": "bonbast didn't return this item right now"})
                continue
            unit = a / b
            note = f"bonbast {short_time(bon.get('date', ''))}"
            if bon_old:
                try:
                    age_s = time.time() - float(bon["fetched"])
                except (TypeError, ValueError, KeyError):
                    age_s = 0
                if age_s > 3600:
                    note += f"  ·  old prices ({int(age_s // 3600)}h)"
            # Change of the non-Toman side's Toman price. When the row shows the
            # inverse (Toman → foreign), the title arrow follows the displayed number.
            foreign = tgt if src in TOMAN else src if tgt in TOMAN else None
            if ref and foreign:
                now_price, then_price = toman_per(foreign, bon), toman_per(foreign, ref, cross=False)
                if now_price and then_price:
                    pct = (now_price / then_price - 1) * 100
                    title_pct = -pct if src in TOMAN else pct

                    def arrow(value):
                        if abs(value) < 0.005:
                            return "="
                        return ("▲" if value > 0 else "▼") + f"{abs(value):.2f}%"

                    change = "  " + arrow(title_pct)
                    note += f"  ·  {LABEL.get(foreign, foreign)} vs {ref_label} {arrow(pct)}"
        else:
            unit = W[tgt] / W[src]
            note = f"rates {world['date']}" + ("  ·  old rates" if world_old else "")
        value = amount * unit
        plain = fmt(value, tgt, sep=False)
        # Quote the rate per foreign unit, never "1 Toman = 0.0000037 USD".
        rate = (f"1 {name} = {fmt(1 / unit, src)} {sname}" if src in TOMAN
                else f"1 {sname} = {fmt(unit, tgt)} {name}")
        lhs = f"{shown} = " if shown else ""
        rate_part = "" if amount == 1 else f"{rate}  ·  "
        item = {
            "title": f"{fmt(value, tgt)} {name}{change}",
            "subtitle": f"{lhs}{fmt_amount(amount, src)} {sfull} = {fmt(value, tgt)} {name}  ·  {rate_part}{note}",
            "arg": plain,
            "text": {"copy": plain, "largetype": f"{fmt_amount(amount, src)} {sname}\n= {fmt(value, tgt)} {name}"},
            "mods": {"cmd": {"arg": plain, "subtitle": "Paste the number into the front app"}},
        }
        ic = icon(tgt, all_codes)
        if ic:
            item["icon"] = ic
        items.append(item)
    emit(items)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--refresh"]:
        name = sys.argv[2]
        ok = False
        try:
            refresh(name)
            ok = True
        except Exception:
            # Keep a 60 s backoff so a dead source is not retried on every keystroke.
            try:
                touch(fail_path(name))
            except OSError:
                pass
        finally:
            if ok:
                try:
                    os.remove(fail_path(name))
                except OSError:
                    pass
            try:
                os.remove(path(name) + ".lock")
            except OSError:
                pass
    elif sys.argv[1:2] == ["--icons"]:
        try:
            render_icons(sys.argv[2:])
        finally:
            try:
                os.remove(os.path.join(CACHE, "icons.lock"))
            except OSError:
                pass
    else:
        main()
