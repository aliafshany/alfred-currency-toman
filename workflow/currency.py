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
    # Country names. "us" is left out on purpose: it is an ordinary English word.
    "turkey": "TRY", "turkiye": "TRY", "türkiye": "TRY", "iran": "IRT", "america": "USD",
    "usa": "USD", "uae": "AED", "emirates": "AED", "dubai": "AED", "oman": "OMR",
    "europe": "EUR", "uk": "GBP", "britain": "GBP", "england": "GBP", "japan": "JPY",
    "china": "CNY", "russia": "RUB", "iraq": "IQD", "afghanistan": "AFN", "armenia": "AMD",
    "georgia": "GEL", "azerbaijan": "AZN", "saudi": "SAR", "qatar": "QAR", "kuwait": "KWD",
    "bahrain": "BHD", "india": "INR", "pakistan": "PKR", "canada": "CAD", "australia": "AUD",
    "switzerland": "CHF", "sweden": "SEK", "norway": "NOK", "denmark": "DKK", "korea": "KRW",
    "thailand": "THB", "malaysia": "MYR", "indonesia": "IDR", "egypt": "EGP", "brazil": "BRL",
    "mexico": "MXN",
    "ruble": "RUB", "rubles": "RUB", "rouble": "RUB", "roubles": "RUB",
    "kronor": "SEK", "krone": "NOK", "kr": "SEK",
}
SYMBOLS = {"₺": "TRY", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₽": "RUB", "﷼": "IRR",
           "₹": "INR", "₩": "KRW", "₪": "ILS", "฿": "THB", "₼": "AZN", "Rs": "INR",
           "سکه": "EMAMI", "طلا": "GRAM", "روپیه": "INR",
           "تومان": "IRT", "تومن": "IRT", "ریال": "IRR", "دلار": "USD", "یورو": "EUR",
           "لیر": "TRY", "لیره": "TRY", "درهم": "AED", "پوند": "GBP",
           "ترکیه": "TRY", "امارات": "AED", "دبی": "AED", "عمان": "OMR", "روبل": "RUB",
           "یوان": "CNY", "دینار": "IQD", "عراق": "IQD"}
MULTIPLIERS = {"k": 1e3, "m": 1e6, "thousand": 1e3, "million": 1e6, "millions": 1e6,
               "billion": 1e9, "billions": 1e9, "هزار": 1e3, "میلیون": 1e6, "میلیارد": 1e9}
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
             "peso": "MXN", "krona": "SEK", "rouble": "RUB", "ruble": "RUB", "dinar": "IQD",
             "riyal": "SAR", "krone": "NOK"}
POPULAR = ["USD", "EUR", "GBP", "TRY", "JPY", "CHF", "CAD", "AUD", "CNY", "AED", "INR", "IRT"]
CONNECTORS = ("to", "in", "as", "=", "به")
MAX_CANDIDATES = 15
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")


def codes_of(raw):
    """'usd, TL,usd' -> ['USD', 'TRY'] (aliases resolved, duplicates dropped)."""
    return list(dict.fromkeys(ALIASES.get(c.strip().lower(), c.strip().upper())
                              for c in raw.split(",") if c.strip()))


def setting(var, default):
    """Comma-separated currency list from Configure Workflow…"""
    return codes_of(os.environ.get(var) or default)


BUILTIN_TARGETS = {"default_targets": "USD,IRT", "toman_targets": "USD,TRY",
                   "gold_targets": "IRT,USD", "usd_targets": "IRT,TRY,EUR"}
TARGETS = {var: setting(var, default) for var, default in BUILTIN_TARGETS.items()}
SHOW_CHANGE = os.environ.get("show_change", "1") != "0"


def default_targets(src, known):
    """The configured target list for this source; the built-in one if nothing is left."""
    var = ("usd_targets" if src == "USD" else "toman_targets" if src in TOMAN
           else "gold_targets" if src in COINS else "default_targets")
    for choice in (TARGETS[var], codes_of(BUILTIN_TARGETS[var])):
        found = [t for t in choice if t != src and t in known]
        if found:
            return found
    return []


def locks_pending():
    """True while a refresh or icon render holds a fresh lock; a lock older than 60 s is dead."""
    pending = False
    locks = [path(name) + ".lock" for name in ("world", "bonbast", "history")]
    for lock in locks + [os.path.join(CACHE, "icons.lock")]:
        if os.path.exists(lock):
            if marker_fresh(lock, 60):
                pending = True
            else:
                try:
                    os.remove(lock)
                except OSError:
                    pass
    return pending


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
    # Keep real currencies only: crypto tickers (SOL, ONE, OKB …) would match ordinary words.
    rates = {k.upper(): v for k, v in d["usd"].items()
             if k.upper() in CURRENCY_NAMES or k.upper() in LOCAL}
    return {"rates": rates, "date": d["date"]}


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


def tehran_yesterday():
    """Yesterday's date in Tehran (UTC+3:30, no daylight saving)."""
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3, minutes=30)
    return (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def fetch_history():
    day = tehran_yesterday()
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


def touch(marker, text=""):
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write(text)


def fail_text(exc):
    """What a failed refresh leaves in its .fail file, so the next keystroke shows the same message."""
    return str(exc) if isinstance(exc, FileNotFoundError) else type(exc).__name__


def fail_message(exc):
    return str(exc) if isinstance(exc, (FileNotFoundError, RuntimeError)) else type(exc).__name__


def read_fail(name):
    try:
        with open(fail_path(name), encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


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


def valid_cache(cached):
    """A cache file must be {"rates": {...}, "fetched": <number>, ...}; anything else is refetched."""
    if not isinstance(cached, dict) or not isinstance(cached.get("rates"), dict):
        return False
    fetched = cached.get("fetched")
    return isinstance(fetched, (int, float)) and not isinstance(fetched, bool)


def load(name, wait=True):
    """Return (data, very_old). Old data is returned at once and refreshed in the background.
    With wait=False a missing cache returns (None, False) and is fetched in the background."""
    cached = None
    try:
        with open(path(name), encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        pass
    if not valid_cache(cached):
        if marker_fresh(fail_path(name)) or marker_fresh(path(name) + ".lock"):
            if not wait:
                return None, False
            raise RuntimeError(read_fail(name) or f"{name} refresh failed")
        if not wait:
            background("--refresh", name, lock=path(name) + ".lock")
            return None, False
        try:
            return refresh(name), False
        except Exception as exc:
            try:
                touch(fail_path(name), fail_text(exc))
            except OSError:
                pass
            raise
    age = time.time() - cached["fetched"]
    if age > MAX_AGE[name] or (name == "history" and cached.get("date") != tehran_yesterday()):
        background("--refresh", name, lock=path(name) + ".lock")
    return cached, age > 3 * MAX_AGE[name]


# ---------- icons ----------

def flag(code):
    if code in TOMAN:
        return "🇮🇷"
    if code in COINS:
        return "🪙"
    if code == "ANG":                     # Netherlands Antilles: no flag exists
        return "💱"
    if len(code) == 3 and code.isalpha() and not code.startswith("X"):
        return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code[:2])
    return "💱"


def icon(code, all_codes):
    p = os.path.join(ICONS, f"{code}.png")
    if os.path.exists(p):
        return {"path": p}
    if (not os.path.exists(os.path.join(ICONS, ".done"))
            and not marker_fresh(os.path.join(CACHE, "icons.fail"))):   # a failed render backs off 60 s
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

FA_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ى": "ی"})
FA_DROP = re.compile("[‌‍‎‏ً-ٰٟـ]")
SPACES = str.maketrans({" ": " ", " ": " ", " ": " "})
FA_UNITS = ("تومان", "تومن", "ریال", "دلار", "یورو", "لیر", "لیره", "درهم", "پوند", "یوان",
            "روبل", "دینار", "روپیه")
FA_MULTS = ("میلیارد", "میلیون", "هزار")
GROUP = re.compile(r"\d{3}(?:[.,]\d+)?")
HSPACE = re.compile(r"[ \t]*")


def normalize_text(q):
    """Persian/Arabic clean-up: unify look-alike letters, drop ZWNJ, direction marks, diacritics."""
    return FA_DROP.sub("", q.translate(FA_MAP)).translate(SPACES)


def norm_number(s, dot_decimal=False):
    """'1.299,90' -> '1299.90', '1,200' -> '1200', '2,5' -> '2.5', '12.99' stays.
    dot_decimal (gold, coins, BTC): a lone '.' is a decimal point, '1.250' is 1.25."""
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            return s.replace(",", "")
        return s.replace(".", "").replace(",", ".")
    if "," in s:
        return s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    if not dot_decimal and re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", s):
        return s.replace(".", "")    # 1.299 (Turkish/European thousands)
    return s


def strip_zeros(s):
    """'05' -> '5', '0912' -> '912', '0.5' stays (Python rejects leading zeros)."""
    t = s.lstrip("0")
    if not t:
        return "0"
    return "0" + t if t[0] in ".eE" else t


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
# "exp" (1e10) is only read as a number in a typed query. Persian words are letters only.
TOKEN = re.compile(
    r"(?P<exp>\d+(?:\.\d+)?[eE][+-]?\d+(?![\d.A-Za-z]))"
    r"|(?P<num>\d(?:[\d.,]*\d)?)"
    r"|(?P<word>[A-Za-zÀ-ÖØ-öø-ɏ]+|[ء-يٱ-ۓە]+)"
    r"|(?P<sym>[₺$€£¥₽﷼₹₩₪฿₼])"
    r"|(?P<op>[-+*/×÷^()])")


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


def resolve_name(text, known, prefix_from=3):
    """The one currency a word names, else None. A whole word beats a prefix of the
    name; a prefix needs prefix_from+ letters; PREFERRED settles shared words like "dirham"."""
    if not (text.isascii() and text.isalpha()):
        return None
    whole, prefix = name_matches(text, known, prefix_from)
    pool = whole or prefix
    if len(pool) > 1 and whole:
        low = plain_text(text)
        preferred = PREFERRED.get(low) or PREFERRED.get(low[:-1])
        if preferred in whole:
            return preferred
    return pool[0] if len(pool) == 1 else None


def word_class(text, known, prefix_from=3):
    """How a word should be read: symbol/alias/uppercase outrank a bare code, then names."""
    low = text.lower()
    if low in MULTIPLIERS or low == "x" or low in CONNECTORS or text == "و":
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
    if resolve_name(text, known, prefix_from):
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


class Tok:
    __slots__ = ("kind", "text", "start", "end")

    def __init__(self, kind, text, start, end):
        self.kind, self.text, self.start, self.end = kind, text, start, end


def fa_pieces(word):
    """Split glued Persian money words and strip suffixes: هزارتومان -> هزار تومان, تومانی -> تومان."""
    if word in SYMBOLS or word in MULTIPLIERS or word == "و":
        return [word]
    for mult in FA_MULTS:
        if word.startswith(mult) and len(word) > len(mult):
            rest = fa_pieces(word[len(mult):])
            if len(rest) == 1 and rest[0] in FA_UNITS:
                return [mult, rest[0]]
    for unit in FA_UNITS:
        if word in (unit + "ی", unit + "یی"):
            return [unit]
    return [word]


def tokenize(q):
    """Tokens of q (Persian digits read as ASCII; offsets stay valid for q itself)."""
    toks = []
    for m in TOKEN.finditer(q.translate(DIGITS)):
        kind, text = m.lastgroup, m.group()
        if kind == "word" and "ء" <= text[0] <= "ە":
            pieces = fa_pieces(text)
            if len(pieces) > 1 and "".join(pieces) == text:
                pos = m.start()
                for piece in pieces:
                    toks.append(Tok("word", piece, pos, pos + len(piece)))
                    pos += len(piece)
            else:
                toks.append(Tok("word", pieces[0], m.start(), m.end()))
            continue
        toks.append(Tok(kind, text, m.start(), m.end()))
    for i, t in enumerate(toks):          # "۲۵۰ت" -> 250 Toman
        if (t.kind == "word" and t.text == "ت" and i and toks[i - 1].kind in ("num", "exp")
                and toks[i - 1].end == t.start):
            t.text = "تومان"
    out = []
    for t in toks:                        # "1 299,90": a 3-digit group right after a number joins it
        prev = out[-1] if out else None
        if (t.kind == "num" and prev is not None and prev.kind == "num" and prev.text.isdigit()
                and HSPACE.fullmatch(q[prev.end:t.start]) and GROUP.fullmatch(t.text)):
            prev.text = absorb_group(prev.text, t.text)
            prev.end = t.end
        else:
            out.append(t)
    return out


def ws_gap(q, a, b):
    """Only spaces between token a and token b (no line break)."""
    return HSPACE.fullmatch(q[a.end:b.start]) is not None


def num_text(tok, dot):
    return strip_zeros(tok.text if tok.kind == "exp" else norm_number(tok.text, dot))


def good_num(tok, dot):
    try:
        float(num_text(tok, dot))
        return True
    except ValueError:
        return False


def read_atom(toks, i, q, dot):
    """A number with its multiplier ("5 million"), joined by "و" ("۵ میلیون و ۵۰۰ هزار").
    Returns ([(number text, multiplier, typed multiplier)], index of the last token used)."""
    terms = []
    j = i
    while True:
        mult, typed = 1.0, ""
        k = j + 1
        if (k < len(toks) and toks[k].kind == "word" and toks[k].text.lower() in MULTIPLIERS
                and ws_gap(q, toks[j], toks[k])):
            typed = toks[k].text.lower()
            mult = MULTIPLIERS[typed]
            k += 1
        terms.append((num_text(toks[j], dot), mult, typed))
        j = k - 1
        if (j + 2 < len(toks) and toks[j + 1].kind == "word" and toks[j + 1].text == "و"
                and toks[j + 2].kind == "num" and good_num(toks[j + 2], dot)
                and ws_gap(q, toks[j], toks[j + 1]) and ws_gap(q, toks[j + 1], toks[j + 2])):
            j += 2
            continue
        return terms, j


def query_word_ok(text, known, code_like=True):
    """True when a word is something a typed query may hold: currency, multiplier, connector.
    code_like: a 3-letter word that is no currency may be a mistyped code ("100 xyz")."""
    low = text.lower()
    if low in MULTIPLIERS or low == "x" or low in CONNECTORS or text == "و":
        return True
    if text in SYMBOLS or low in ALIASES or text.upper() in known:
        return True
    if not (text.isascii() and text.isalpha()):
        return False
    if name_matches(text, known, 99)[0]:
        return True
    return code_like and word_class(text, known) in ("upper-unknown", "weak-unknown")


def classify(q, toks, known, pending):
    """"query" when the whole text is amount/currency/operator words, else "prose"."""
    if "\n" in q or "\r" in q:
        return "prose"
    priced = 0                              # "$50 - $70": several symbol+number pairs = a price list
    for i, t in enumerate(toks[:-1]):
        nxt = toks[i + 1]
        if t.kind == "sym" and nxt.kind in ("num", "exp") and ws_gap(q, t, nxt):
            priced += 1
    if priced > 1:
        return "prose"
    # An unknown 3-letter word only reads as a mistyped code when no real currency is present.
    code_like = not any(
        t.kind == "sym" or (t.kind == "word" and query_word_ok(t.text, known, False)
                            and word_class(t.text, known) not in ("plain",))
        for t in toks)
    last = len(toks) - 1
    for i, t in enumerate(toks):
        if t.kind != "word" or query_word_ok(t.text, known, code_like):
            continue
        if i == last and (pending or resolve_name(t.text, known)):
            continue                        # an unfinished last word, or the start of one currency name
        return "prose"
    return "query"


def new_result(mode):
    return {"amount": 1.0, "codes": [], "unknown": [], "shown": "", "bad": None,
            "mode": mode, "assumed": False}


def parse_query(q, toks, known, dot):
    """Typed query: every code counts in typed order, math is on."""
    res = new_result("query")
    items = []                  # (expression text, text as typed)
    typed_math = False
    prev = "start"              # start | num | op | lp | rp
    i = 0
    while i < len(toks):
        t = toks[i]
        kind = t.kind
        if kind in ("num", "exp"):
            if prev == "num":                 # two numbers in a row: keep the first
                i += 1
                continue
            terms, last = read_atom(toks, i, q, dot)
            parts = [n if m == 1 else f"{n}*{m:.0f}" for n, m, _ in terms]
            if len(terms) == 1 and terms[0][1] == 1:
                expr = parts[0]
            else:
                expr = "(" + "+".join(parts) + ")"
            shown = "+".join(n + (w if len(w) <= 1 else f" {w} ") for n, _, w in terms)
            items.append((expr, shown.strip()))
            prev = "num"
            i = last + 1
            continue
        i += 1
        if kind == "op":
            ch = t.text
            if ch == "(":
                items.append(("(", "("))
                prev = "lp"
            elif ch == ")":
                items.append((")", ")"))
                prev = "rp"
            else:
                if ch not in "+-" or prev in ("num", "rp"):
                    typed_math = True         # a leading minus is a sign, not math
                items.append(({"×": "*", "÷": "/", "^": "**"}.get(ch, ch), {"×": "*", "÷": "/"}.get(ch, ch)))
                prev = "op"
            continue
        if kind == "sym":
            res["codes"].append(SYMBOLS[t.text])
            continue
        text, low = t.text, t.text.lower()
        if low in MULTIPLIERS or low in CONNECTORS or text == "و":
            continue
        if low == "x":
            if items:
                typed_math = True
                items.append(("*", "*"))
                prev = "op"
            continue
        wk = word_class(text, known)
        if wk == "symbol":
            res["codes"].append(SYMBOLS[text])
        elif wk == "alias":
            res["codes"].append(ALIASES[low])
        elif wk in ("upper", "weak"):
            res["codes"].append(text.upper())
        elif wk == "name":
            res["codes"].append(resolve_name(text, known))
        elif wk in ("upper-unknown", "weak-unknown"):
            res["unknown"].append(text.upper())
    if items:
        joined = "".join(e for e, _ in items)
        typed = "".join(s for _, s in items)
        try:
            if len(joined) > 200:
                raise ValueError("expression too long")
            res["amount"] = safe_eval(joined)
            res["shown"] = typed if typed_math else ""
        except Exception:                     # syntax, zero division, overflow, recursion ...
            res["bad"] = typed or "?"
    return res


def parse_prose(q, toks, known, dot):
    """Selected text: find the currency, then the number right next to it. No math."""
    res = new_result("prose")
    atoms = []                  # (first token, last token, value)
    i = 0
    while i < len(toks):
        if toks[i].kind == "num" and good_num(toks[i], dot):
            terms, last = read_atom(toks, i, q, dot)
            atoms.append((i, last, sum(float(n) * m for n, m, _ in terms)))
            i = last + 1
        else:
            i += 1
    cands = []                  # (token index, code, strong)
    for idx, t in enumerate(toks):
        if t.kind == "sym":
            cands.append((idx, SYMBOLS[t.text], True))
        elif t.kind == "word":
            wk = word_class(t.text, known, 4)
            if wk == "symbol":
                cands.append((idx, SYMBOLS[t.text], True))
            elif wk == "alias":
                cands.append((idx, ALIASES[t.text.lower()], True))
            elif wk == "upper":
                cands.append((idx, t.text.upper(), True))
            elif wk == "weak":
                cands.append((idx, t.text.upper(), False))
            elif wk == "name":
                cands.append((idx, resolve_name(t.text, known, 4), False))
            elif wk == "upper-unknown":
                res["unknown"].append(t.text.upper())
    pool = [c for c in cands if c[2]] or cands

    def next_to(idx):
        before = [a for a in atoms if a[1] == idx - 1 and ws_gap(q, toks[a[1]], toks[idx])]
        after = [a for a in atoms if a[0] == idx + 1 and ws_gap(q, toks[idx], toks[a[0]])]
        order = (after + before) if toks[idx].kind == "sym" else (before + after)
        return order[0] if order else None

    def nearest(idx):
        best, best_key = None, None
        for a in atoms:
            dist = min(abs(a[0] - idx), abs(a[1] - idx))
            span = q[min(toks[idx].start, toks[a[0]].start):max(toks[idx].start, toks[a[0]].start)]
            key = ("\n" in span, dist, a[0])
            if best_key is None or key < best_key:
                best, best_key = a, key
        return best

    chosen = atom = None
    for idx, code, _ in pool:
        atom = next_to(idx)
        if atom:
            chosen = (idx, code)
            break
    if chosen is None and pool:
        chosen = (pool[0][0], pool[0][1])
        atom = nearest(chosen[0])
    if chosen is None:
        atom = atoms[0] if atoms else None
        res["assumed"] = True
    else:
        res["codes"].append(chosen[1])
        later = [n for n in range(chosen[0] + 1, len(toks))
                 if toks[n].kind == "word" and toks[n].text.lower() in CONNECTORS]
        if later:
            for t in toks[later[0] + 1:]:
                if t.kind == "sym":
                    res["codes"].append(SYMBOLS[t.text])
                    continue
                wk = word_class(t.text, known, 4) if t.kind == "word" else "plain"
                if wk == "symbol":
                    res["codes"].append(SYMBOLS[t.text])
                elif wk == "alias":
                    res["codes"].append(ALIASES[t.text.lower()])
                elif wk in ("upper", "weak"):
                    res["codes"].append(t.text.upper())
                elif wk == "name":
                    res["codes"].append(resolve_name(t.text, known, 4))
                else:
                    break
    if atom:
        res["amount"] = atom[2]
    return res


def parse(q, known, pending=None):
    """Return a dict: amount, codes, unknown, shown (typed math), bad, mode, assumed."""
    toks = tokenize(q)
    mode = classify(q, toks, known, pending)
    run = parse_query if mode == "query" else parse_prose
    res = run(q, toks, known, False)
    if res["codes"] and res["codes"][0] in COINS:   # gold, coins, BTC: "1.250" is 1.25
        res = run(q, toks, known, True)
    return res


def pending_word(q, known):
    """The unfinished last word as (start offset, candidate codes), or None.
    Unfinished = a word at the very end that is no exact code, alias, symbol or single name
    but is the start of a code or a currency name."""
    toks = tokenize(q)
    if not toks:
        return None
    last = toks[-1]
    text, low = last.text, last.text.lower()
    if last.kind != "word" or q[last.end:].strip() or not text.isascii():
        return None
    if (low in MULTIPLIERS or low == "x" or low in CONNECTORS or text in SYMBOLS
            or low in ALIASES or text.upper() in known or resolve_name(text, known)):
        return None
    if len(toks) > 1 and not any(
            t.kind in ("num", "exp", "sym") or word_class(t.text, known) not in ("plain", "weak-unknown")
            for t in toks[:-1]):
        return None                       # prose with no amount or currency in front of it
    whole, prefix = name_matches(text, known, 1)
    group = {c: 2 for c in prefix}                       # name starts with the text
    group.update({c: 1 for c in whole})                  # name has it as a whole word
    group.update({ALIASES[a]: 1 for a in ALIASES         # country or alias starts with it
                  if len(low) >= 2 and a.startswith(low) and ALIASES[a] in known})
    group.update({c: 0 for c in known if c.lower().startswith(low)})   # code starts with it
    used = set(parse(q[:last.start], known)["codes"])
    pool = [c for c in group if c not in used] or list(group)
    pool.sort(key=lambda c: (group[c], POPULAR.index(c) if c in POPULAR else len(POPULAR), c))
    return (last.start, pool[:MAX_CANDIDATES]) if pool else None


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
    rounded = round(x, 6)
    if code in TOMAN or rounded == int(rounded):
        return f"{rounded:,.0f}"
    return f"{x:,.2f}" if abs(x) >= 1 else fmt_small(x)


def main():
    q = normalize_text(" ".join(sys.argv[1:])).strip()
    if not q:
        emit([{"title": "Type an amount and a currency", "valid": False,
               "subtitle": "$100 try  ·  $100 try eur  ·  $5m irt  ·  $1200+350 try  ·  $2 emami"}])
        return
    world, world_old, world_err = None, False, ""
    try:
        world, world_old = load("world")
    except Exception as exc:
        world_err = fail_message(exc)
    bon = bon_err = None
    bon_old = False
    if world is None:                    # no world rates: bonbast alone can still answer Toman queries
        try:
            bon, bon_old = load("bonbast")
        except Exception as exc:
            bon_err = fail_message(exc)
        if bon is None:
            emit([{"title": "Couldn't get exchange rates", "valid": False,
                   "subtitle": f"{world_err} — check internet/VPN"}])
            return
    W = world["rates"] if world else {}
    known = set(W) | LOCAL | (set(bon["rates"]) if bon else set())

    def invalid(text, more=()):
        shown = text if len(text) <= 60 else text[:57] + "…"
        emit([{"title": f"Invalid expression: {shown}", "valid": False}] + list(more))

    pending = pending_word(q, known)
    res = parse(q, known, pending)
    if res["bad"]:
        invalid(q)
        return
    # An unfinished last word converts with its best match right away ("$100 tr" -> TRY);
    # the other matches follow the results as Tab rows. Only a typed query completes words.
    complete = None
    others = []
    if pending and res["mode"] == "query":
        start, found = pending
        # Fill in the case that was typed: an upper-case code would outrank "try" in "100 try eur".
        cased = (lambda c: c.lower()) if q[start:].islower() else (lambda c: c)
        for code in found[1:]:
            row = {"title": f"{code} — {CURRENCY_NAMES.get(code, LABEL.get(code, code))}",
                   "valid": False, "subtitle": f"Tab to use {code}",
                   "autocomplete": f"{q[:start]}{cased(code)} "}
            ic = icon(code, known)
            if ic:
                row["icon"] = ic
            others.append(row)
        q = f"{q[:start]}{cased(found[0])}"
        complete = f"{q} "
        res = parse(q, known)
        if res["bad"]:
            invalid(q, others)
            return
    amount, codes, unknown = res["amount"], res["codes"], res["unknown"]
    shown, assumed = res["shown"], res["assumed"]
    if unknown and not codes:
        emit([{"title": f"Unknown currency: {', '.join(unknown)}", "valid": False,
               "subtitle": "Use 3-letter codes: USD EUR TRY GBP AED … names like yen, or toman, emami, gram"}])
        return
    if abs(amount) > 1e15:
        emit([{"title": "Amount too large", "valid": False,
               "subtitle": "Keep amounts below 1,000,000,000,000,000"}])
        return
    src = codes[0] if codes else "USD"
    targets = [c for c in dict.fromkeys(codes[1:]) if c != src and c in known]
    if not targets:
        targets = default_targets(src, known)

    ref = None
    ref_label = "yesterday"
    if bon is None and bon_err is None and (src in LOCAL or any(t in LOCAL for t in targets)):
        try:
            bon, bon_old = load("bonbast")
        except Exception as exc:
            bon_err = fail_message(exc)
    if bon and SHOW_CHANGE and (src in LOCAL or any(t in LOCAL for t in targets)):
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
        both_toman = src in TOMAN and tgt in TOMAN
        if src in LOCAL or tgt in LOCAL or world is None:
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
            foreign = None if both_toman else tgt if src in TOMAN else src if tgt in TOMAN else None
            if ref and foreign:
                now_price, then_price = toman_per(foreign, bon), toman_per(foreign, ref, cross=False)
                if now_price and then_price:
                    pct = (now_price / then_price - 1) * 100
                    title_pct = (then_price / now_price - 1) * 100 if src in TOMAN else pct

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
        rate = (f"1 {name} = {fmt(1 / unit, '' if both_toman else src)} {sname}" if src in TOMAN
                else f"1 {sname} = {fmt(unit, tgt)} {name}")
        lhs = f"{shown} = " if shown else ""
        rate_part = "" if amount == 1 else f"{rate}  ·  "
        extra = "  ·  no currency found — assuming USD" if assumed else ""
        item = {
            "title": f"{fmt(value, tgt)} {name}{change}",
            "subtitle": f"{lhs}{fmt_amount(amount, src)} {sfull} = {fmt(value, tgt)} {name}  ·  {rate_part}{note}{extra}",
            "arg": plain,
            "text": {"copy": plain, "largetype": f"{fmt_amount(amount, src)} {sname}\n= {fmt(value, tgt)} {name}"},
            "mods": {"cmd": {"arg": plain, "subtitle": "Paste the number into the front app"}},
        }
        if complete:
            item["autocomplete"] = complete
        ic = icon(tgt, all_codes)
        if ic:
            item["icon"] = ic
        items.append(item)
    emit(items + others)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--refresh"] and len(sys.argv) > 2 and sys.argv[2] in FETCHERS:
        name = sys.argv[2]
        ok = False
        try:
            refresh(name)
            ok = True
        except Exception as exc:
            # Keep a 60 s backoff so a dead source is not retried on every keystroke.
            try:
                touch(fail_path(name), fail_text(exc))
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
    elif sys.argv[1:2] == ["--icons"] and len(sys.argv) > 2:
        try:
            render_icons(sys.argv[2:])
            try:
                os.remove(os.path.join(CACHE, "icons.fail"))
            except OSError:
                pass
        except Exception:
            try:
                touch(os.path.join(CACHE, "icons.fail"))
            except OSError:
                pass
        finally:
            try:
                os.remove(os.path.join(CACHE, "icons.lock"))
            except OSError:
                pass
    else:
        main()
