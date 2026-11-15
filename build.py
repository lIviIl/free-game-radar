#!/usr/bin/env python3
"""Free Game Radar v2: builds a searchable static site (English + Arabic) of free game giveaways and
discounted games, and posts new giveaways to Telegram. Standard library only, no API keys.
Data: GamerPower.com (giveaways) and CheapShark.com (deals). Attribution is shown in every footer."""
import html, json, os, re, shutil, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE, STATE = ROOT / "site", ROOT / "state"
GP = "https://www.gamerpower.com/api/giveaways?type=game&sort-by=popularity"
CS = "https://www.cheapshark.com/api/1.0"
UA = {"User-Agent": "FreeGameRadar/2.0 (static site generator)"}
esc = html.escape

# Fallback names; the live list from CheapShark /stores overrides these.
STORES = {"1": "Steam", "2": "GamersGate", "3": "Green Man Gaming", "7": "GOG", "11": "Humble Store",
          "13": "Ubisoft Store", "15": "Fanatical", "25": "Epic Games Store", "27": "Gamesplanet",
          "30": "IndieGala", "31": "Blizzard Shop"}
PLAT = (("epic", "Epic Games Store"), ("steam", "Steam"), ("gog", "GOG"), ("itch", "itch.io"),
        ("playstation", "PlayStation"), ("ps5", "PlayStation"), ("ps4", "PlayStation"), ("xbox", "Xbox"),
        ("switch", "Switch"), ("android", "Mobile"), ("ios", "Mobile"), ("ubisoft", "Ubisoft"),
        ("origin", "EA"), ("battle", "Battle.net"))

T = {
    "en": dict(dir="ltr", tag="Free games and the best deals", sub="Updated every 6 hours. Claim the free ones before they expire.",
               desc="Free games you can claim right now and the best game discounts, updated every 6 hours.",
               free="Free", sale="On sale", all="All", search="Search games", stores="All stores", sortby="Sort by",
               s_top="Top picks", s_pct="Biggest discount", s_low="Lowest price", s_rated="Best rated",
               s_end="Ending soon", s_new="Newest", none="No games match your search.", showing="Showing",
               ends="Ends", noend="No end date listed", claim="Claim for free", back="All games",
               join="Join on Telegram", other="العربية", how="How to claim", compare="Find it on sale",
               data="Data from", pos="positive", nfree="free now", nsale="on sale", updated="Updated",
               disc="Some links are affiliate links: we may earn a commission at no extra cost to you.",
               gone="This page is gone. The free giveaway may have ended."),
    "ar": dict(dir="rtl", tag="ألعاب مجانية وأفضل العروض", sub="تُحدَّث كل 6 ساعات. احصل على الألعاب المجانية قبل أن تنتهي.",
               desc="ألعاب مجانية يمكنك الحصول عليها الآن وأفضل خصومات الألعاب، تُحدَّث كل 6 ساعات.",
               free="مجانًا", sale="عروض", all="الكل", search="ابحث عن لعبة", stores="كل المتاجر", sortby="ترتيب حسب",
               s_top="الأفضل", s_pct="أكبر خصم", s_low="الأرخص", s_rated="الأعلى تقييمًا",
               s_end="ينتهي قريبًا", s_new="الأحدث", none="لا توجد ألعاب مطابقة لبحثك.", showing="المعروض",
               ends="ينتهي", noend="لا يوجد تاريخ انتهاء", claim="احصل عليها مجانًا", back="كل الألعاب",
               join="انضم على تيليجرام", other="English", how="طريقة الحصول عليها", compare="ابحث عنها بسعر مخفّض",
               data="البيانات من", pos="إيجابي", nfree="مجانية الآن", nsale="عرض", updated="آخر تحديث",
               disc="بعض الروابط تابعة: قد نحصل على عمولة دون أي تكلفة إضافية عليك.",
               gone="هذه الصفحة غير موجودة. ربما انتهى العرض المجاني."),
}

CSS = """
:root{--bg:#eef1f7;--sf:#fff;--ink:#0f1a3a;--mut:#4d5a78;--bd:#0f1a3a;--sh:#0f1a3a;--free:#ffd23f;--sale:#ff4d2e;--acc:#2447e6}
@media (prefers-color-scheme:dark){:root{--bg:#0c1226;--sf:#151d38;--ink:#eef2ff;--mut:#9aa6c8;--bd:#46538a;--sh:#04070f;--acc:#8fa6ff}}
*{box-sizing:border-box}
html{color-scheme:light dark}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Segoe UI",system-ui,-apple-system,"Noto Sans Arabic",Tahoma,sans-serif}
[lang=ar] *{letter-spacing:0!important}
a{color:inherit}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
.wrap{max-width:1040px;margin:0 auto;padding:16px 16px 56px}
header{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;justify-content:space-between}
.brand{display:flex;gap:10px;align-items:center;font-weight:800;font-size:1.2rem;text-decoration:none;letter-spacing:-.01em}
.brand svg{width:30px;height:30px}
nav{display:flex;gap:10px}
nav a{padding:6px 14px;border:2px solid var(--bd);border-radius:999px;background:var(--sf);text-decoration:none;font-weight:600;font-size:.9rem}
h1{font-size:clamp(1.9rem,5vw,3rem);line-height:1.12;margin:30px 0 8px;font-weight:800;letter-spacing:-.02em;max-width:20ch}
.sub{margin:0;color:var(--mut);font-size:1.05rem}
.stats{display:flex;flex-wrap:wrap;gap:8px 22px;margin:14px 0 0;font-weight:700}
.stats span{color:var(--mut);font-weight:600}
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:24px 0 8px;padding:14px;background:var(--sf);border:2px solid var(--bd);border-radius:12px;box-shadow:4px 4px 0 var(--sh)}
.tools input{flex:1 1 220px}
input,select{font:inherit;color:inherit;background:var(--bg);border:2px solid var(--bd);border-radius:8px;padding:9px 12px;min-width:0}
.chips{display:flex;gap:6px}
.chips button{font:inherit;font-weight:700;padding:8px 14px;border:2px solid var(--bd);border-radius:999px;background:var(--sf);color:var(--ink);cursor:pointer}
.chips button[aria-pressed=true]{background:var(--ink);color:var(--bg)}
.count{margin:0 0 14px;color:var(--mut);font-size:.9rem}
.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{display:flex;flex-direction:column;background:var(--sf);border:2px solid var(--bd);border-radius:12px;overflow:hidden;text-decoration:none;box-shadow:4px 4px 0 var(--sh);transition:transform .12s,box-shadow .12s}
.card:hover{transform:translate(-2px,-2px);box-shadow:6px 6px 0 var(--sh)}
@media (prefers-reduced-motion:reduce){.card{transition:none}.card:hover{transform:none}}
.pic{position:relative;aspect-ratio:460/215;background:var(--bd)}
.pic img{display:block;width:100%;height:100%;object-fit:cover}
.tag{position:absolute;top:10px;inset-inline-start:10px;padding:2px 10px;font-weight:800;border:2px solid var(--bd);border-radius:6px;transform:rotate(-3deg)}
.tag.free{background:var(--free);color:#0f1a3a}
.tag.sale{background:var(--sale);color:#fff}
.cb{display:flex;flex-direction:column;gap:6px;flex:1;padding:12px 14px 14px}
.ct{font-weight:700;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cm{display:flex;flex-wrap:wrap;gap:2px 12px;font-size:.85rem;color:var(--mut)}
.cp{display:flex;align-items:baseline;gap:10px;margin-top:auto;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.cp s{color:var(--mut)}
.cp b{font-size:1.35rem}
.hero{display:block;width:100%;margin:18px 0;border:2px solid var(--bd);border-radius:12px;box-shadow:4px 4px 0 var(--sh)}
.btn{display:inline-block;margin:10px 0 18px;padding:13px 26px;background:var(--free);color:#0f1a3a;border:2px solid var(--bd);border-radius:10px;font-weight:800;text-decoration:none;box-shadow:4px 4px 0 var(--sh)}
ol{padding-inline-start:1.3em}
.cmp{color:var(--mut)}
footer{margin-top:44px;padding-top:16px;border-top:2px solid var(--bd);color:var(--mut);font-size:.85rem}
"""

# Search, filter chips, store filter and sorting. Without JavaScript the full list is still shown.
JS = """
(function(){
var g=document.getElementById('grid'),f=document.getElementById('tools');if(!g||!f)return;
var cards=[].slice.call(g.children),q=document.getElementById('q'),st=document.getElementById('store'),
so=document.getElementById('sort'),none=document.getElementById('none'),cnt=document.getElementById('count'),
chips=[].slice.call(f.querySelectorAll('[data-chip]')),kind='all';
function norm(s){return s.toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'')}
function num(c,k,d){var v=c.dataset[k];return v===''||v===undefined?d:Number(v)}
var by={top:function(a,b){return num(a,'pop',0)-num(b,'pop',0)},
pct:function(a,b){return num(b,'pct',0)-num(a,'pct',0)},
low:function(a,b){return num(a,'price',0)-num(b,'price',0)},
rated:function(a,b){return num(b,'rating',0)-num(a,'rating',0)},
end:function(a,b){return num(a,'end',9e12)-num(b,'end',9e12)},
newest:function(a,b){return num(b,'added',0)-num(a,'added',0)}};
function run(){var t=norm(q.value.trim()),s=st.value,n=0;
cards.sort(by[so.value]||by.top);
cards.forEach(function(c){g.appendChild(c);
var ok=(kind==='all'||c.dataset.kind===kind)&&(!s||c.dataset.store===s)&&(!t||c.dataset.q.indexOf(t)>-1);
c.hidden=!ok;if(ok)n++});
none.hidden=n>0;cnt.textContent=n}
chips.forEach(function(b){b.addEventListener('click',function(){kind=b.dataset.chip;
chips.forEach(function(x){x.setAttribute('aria-pressed',x===b)});run()})});
q.addEventListener('input',run);st.addEventListener('change',run);so.addEventListener('change',run);
f.addEventListener('submit',function(e){e.preventDefault()});
f.hidden=false;
})();
"""

LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" stroke-width="2.5"/>'
        '<circle cx="16" cy="16" r="7" fill="none" stroke="currentColor" stroke-width="2.5"/>'
        '<path d="M16 16 24 10" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>'
        '<circle cx="24" cy="10" r="3.2" fill="#ffd23f" stroke="currentColor" stroke-width="2"/></svg>')


# ---------- data ----------
def fetch_json(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            print(f"fetch {i + 1}/{tries} failed: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    return None


def clean_title(t):
    t = re.sub(r"\s*\([^)]*\)\s*Giveaway\s*$", "", t or "", flags=re.I)
    return re.sub(r"\s*Giveaway\s*$", "", t, flags=re.I).strip() or "Free game"


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "game"


def qn(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    return "".join(c for c in s if not unicodedata.combining(c))


def money(v):
    return f"${v:,.2f}"


def parse_money(s):
    m = re.search(r"\d+(?:\.\d+)?", s or "")
    return float(m.group(0)) if m else None


def to_ts(s):
    try:
        return int(datetime.strptime((s or "")[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return 0


def platform_of(p):
    low = (p or "").lower()
    for key, label in PLAT:
        if key in low:
            return label
    return (p or "").split(",")[0].strip() or "PC"


def load_free():
    """Live giveaways. If the API is down, keep serving the last good copy."""
    cache = STATE / "free.json"
    raw = fetch_json(GP)
    if isinstance(raw, list):
        out = []
        for g in raw:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            end, worth = g.get("end_date") or "N/A", g.get("worth") or "N/A"
            out.append(dict(kind="free", id=int(g["id"]), title=clean_title(g.get("title")), worth=worth,
                            was=parse_money(worth), price=0, pct=100, rating=0,
                            image=g.get("image") or g.get("thumbnail") or "", thumb=g.get("thumbnail") or "",
                            desc=g.get("description") or "", how=g.get("instructions") or "",
                            platforms=g.get("platforms") or "", store=platform_of(g.get("platforms")),
                            endtxt=end, end=to_ts(end), added=to_ts(g.get("published_date")),
                            claim=g.get("open_giveaway_url") or g.get("gamerpower_url") or ""))
        STATE.mkdir(exist_ok=True)
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
    if isinstance(raw, dict):  # API answered "no active giveaways"
        return []
    if cache.exists():
        print("giveaways API unreachable: using cached data", file=sys.stderr)
        return json.loads(cache.read_text(encoding="utf-8"))
    return []


def big_img(thumb):
    return re.sub(r"capsule_(?:sm_120|231x87|184x69|616x353)\.jpg", "header.jpg", thumb or "")


def load_deals(cfg):
    """Discounted games from CheapShark, one entry per game (cheapest store wins)."""
    if not cfg.get("deals_enabled", True):
        return []
    cache = STATE / "deals.json"
    names = dict(STORES)
    stores = fetch_json(f"{CS}/stores", tries=2)
    if isinstance(stores, list):
        names.update({str(s.get("storeID")): s.get("storeName") for s in stores if s.get("storeName")})
    raw = []
    for query in ("onSale=1&pageSize=60", "onSale=1&pageSize=40&sortBy=Savings&desc=1&steamRating=75"):
        part = fetch_json(f"{CS}/deals?{query}", tries=2)
        if isinstance(part, list):
            raw += part
    if not raw:
        if cache.exists():
            print("deals API unreachable: using cached data", file=sys.stderr)
            return json.loads(cache.read_text(encoding="utf-8"))
        return []
    floor = float(cfg.get("min_discount", 30))
    best = {}
    for d in raw:
        try:
            price, was, pct = float(d["salePrice"]), float(d["normalPrice"]), round(float(d.get("savings") or 0))
            deal_id = d["dealID"]
        except (KeyError, TypeError, ValueError):
            continue
        if was <= 0 or price >= was or pct < floor:
            continue
        key = d.get("gameID") or deal_id
        if key in best and best[key]["price"] <= price:
            continue
        thumb = d.get("thumb") or ""
        best[key] = dict(kind="deal", id=int(key) if str(key).isdigit() else 0, title=d.get("title") or "Game",
                         price=price, was=was, pct=pct, image=big_img(thumb), thumb=thumb,
                         store=names.get(str(d.get("storeID")), f'Store {d.get("storeID")}'),
                         rating=int(d.get("steamRatingPercent") or 0), meta=int(d.get("metacriticScore") or 0),
                         added=int(d.get("lastChange") or 0), end=0,
                         rank=float(d.get("dealRating") or 0),
                         url=f"https://www.cheapshark.com/redirect?dealID={deal_id}")
    out = sorted(best.values(), key=lambda x: -x["rank"])
    STATE.mkdir(exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


# ---------- pages ----------
def fmt_end(e, L):
    m = re.match(r"\d{4}-\d{2}-\d{2}", e or "")
    return f'{L["ends"]} {m.group(0)}' if m else L["noend"]


def aff_links(title, cfg):
    out = []
    for name, a in (cfg.get("affiliates") or {}).items():
        u = a.get("url") or ""
        if a.get("enabled") and "{q}" in u:
            href = u.replace("{q}", urllib.parse.quote_plus(title))
            out.append(f'<a rel="sponsored nofollow noopener" href="{esc(href)}">{esc(name)}</a>')
    return out


def path_for(g, lang):
    return f'{"/ar" if lang == "ar" else ""}/g/{g["id"]}-{slug(g["title"])}.html'


def shell(lang, cfg, title, desc, body, here, there, img="", script=""):
    L, base = T[lang], (cfg.get("site_url") or "").rstrip("/")
    other = "en" if lang == "ar" else "ar"
    tg = (cfg.get("telegram_url") or {}).get(lang, "")
    seo = (f'<link rel="canonical" href="{base}{here}">'
           f'<link rel="alternate" hreflang="{other}" href="{base}{there}">') if base else ""
    og = f'<meta property="og:image" content="{esc(img)}">' if img else ""
    join = f'<a href="{esc(tg)}" rel="noopener">{L["join"]}</a>' if tg else ""
    disc = f'<p>{L["disc"]}</p>' if any(aff_links("x", cfg)) else ""
    home = "/ar/" if lang == "ar" else "/"
    cf = (cfg.get("cf_analytics_token") or "").strip()
    beacon = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\''
              + json.dumps({"token": cf}) + '\'></script>') if cf else ""
    js = f"<script>{script}</script>" if script else ""
    return (f'<!doctype html><html lang="{lang}" dir="{L["dir"]}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{seo}'
            f'<meta property="og:title" content="{esc(title)}">{og}<style>{CSS}</style></head>'
            f'<body><div class="wrap"><header><a class="brand" href="{home}">{LOGO}<span>{esc(cfg["name"][lang])}</span></a>'
            f'<nav>{join}<a href="{there}" hreflang="{other}">{L["other"]}</a></nav></header>'
            f'<main>{body}</main><footer>{disc}<p>{L["data"]} '
            f'<a href="https://www.gamerpower.com" rel="noopener">GamerPower.com</a>, '
            f'<a href="https://www.cheapshark.com" rel="noopener">CheapShark.com</a></p></footer></div>{js}{beacon}</body></html>')


def card(it, lang, pop):
    L = T[lang]
    free = it["kind"] == "free"
    href = path_for(it, lang) if free else it["url"]
    ext = "" if free else ' target="_blank" rel="noopener sponsored nofollow"'
    tag = f'<span class="tag free">{L["free"]}</span>' if free else f'<span class="tag sale">-{it["pct"]}%</span>'
    was = f'<s>{money(it["was"])}</s>' if it.get("was") else ""
    now = f'<b>{L["free"]}</b>' if free else f'<b>{money(it["price"])}</b>'
    if free:
        sub = f'<span>{esc(fmt_end(it["endtxt"], L))}</span>'
    elif it["rating"]:
        sub = f'<span>{it["rating"]}% {L["pos"]}</span>'
    elif it.get("meta"):
        sub = f'<span>Metacritic {it["meta"]}</span>'
    else:
        sub = ""
    fb = f' data-fb="{esc(it["thumb"])}" onerror="this.onerror=null;this.src=this.dataset.fb"' if it.get("thumb") else ""
    img = (f'<img src="{esc(it["image"])}" alt="" width="460" height="215" loading="lazy"{fb}>'
           if it["image"] else "")
    return (f'<a class="card" href="{esc(href)}"{ext} data-kind="{it["kind"]}" data-store="{esc(it["store"])}" '
            f'data-q="{esc(qn(it["title"] + " " + it["store"]))}" data-price="{it["price"]}" data-pct="{it["pct"]}" '
            f'data-end="{it["end"] or ""}" data-rating="{it["rating"]}" data-added="{it["added"]}" data-pop="{pop}">'
            f'<div class="pic">{img}{tag}</div><div class="cb"><div class="ct">{esc(it["title"])}</div>'
            f'<div class="cm"><span>{esc(it["store"])}</span>{sub}</div>'
            f'<div class="cp">{was}{now}</div></div></a>')


def index_page(items, lang, cfg):
    L = T[lang]
    nfree = sum(1 for i in items if i["kind"] == "free")
    cards = "".join(card(it, lang, n) for n, it in enumerate(items))
    stores = sorted({i["store"] for i in items})
    opts = f'<option value="">{L["stores"]}</option>' + "".join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in stores)
    sorts = "".join(f'<option value="{k}">{L[v]}</option>' for k, v in
                    (("top", "s_top"), ("pct", "s_pct"), ("low", "s_low"), ("rated", "s_rated"), ("end", "s_end"), ("newest", "s_new")))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = (f'<h1>{L["tag"]}</h1><p class="sub">{L["sub"]}</p>'
            f'<p class="stats"><strong>{nfree} <span>{L["nfree"]}</span></strong>'
            f'<strong>{len(items) - nfree} <span>{L["nsale"]}</span></strong><span>{L["updated"]} {today}</span></p>'
            f'<form class="tools" id="tools" hidden role="search"><input id="q" type="search" placeholder="{L["search"]}" '
            f'aria-label="{L["search"]}" autocomplete="off"><div class="chips">'
            f'<button type="button" data-chip="all" aria-pressed="true">{L["all"]}</button>'
            f'<button type="button" data-chip="free" aria-pressed="false">{L["free"]}</button>'
            f'<button type="button" data-chip="deal" aria-pressed="false">{L["sale"]}</button></div>'
            f'<select id="store" aria-label="{L["stores"]}">{opts}</select>'
            f'<select id="sort" aria-label="{L["sortby"]}">{sorts}</select></form>'
            f'<p class="count">{L["showing"]} <span id="count">{len(items)}</span></p>'
            f'<div class="grid" id="grid">{cards}</div><p id="none" hidden>{L["none"]}</p>')
    here, there = ("/ar/", "/") if lang == "ar" else ("/", "/ar/")
    return shell(lang, cfg, f'{cfg["name"][lang]}: {L["tag"]}', L["desc"], body, here, there, script=JS)


def detail_page(g, lang, cfg):
    L = T[lang]
    steps = [re.sub(r"^\s*\d+[.)]\s*", "", s) for s in g["how"].splitlines() if s.strip()]
    lis = "".join(f"<li>{esc(s)}</li>" for s in steps)
    how = f'<h2>{L["how"]}</h2><ol>{lis}</ol>' if steps else ""
    links = aff_links(g["title"], cfg)
    cmp_ = f'<p class="cmp">{L["compare"]}: {" ".join(links)}</p>' if links else ""
    img = f'<img class="hero" src="{esc(g["image"])}" alt="" loading="lazy">' if g["image"] else ""
    was = f'<s>{money(g["was"])}</s> ' if g.get("was") else ""
    other = "en" if lang == "ar" else "ar"
    body = (f'<p><a href="{"/ar/" if lang == "ar" else "/"}">{L["back"]}</a></p>{img}<h1>{esc(g["title"])}</h1>'
            f'<p class="cm"><span class="cp">{was}<b>{L["free"]}</b></span><span>{esc(g["platforms"])}</span>'
            f'<span>{esc(fmt_end(g["endtxt"], L))}</span></p>'
            f'<a class="btn" href="{esc(g["claim"])}" rel="noopener nofollow">{L["claim"]}</a>'
            f'<p>{esc(g["desc"])}</p>{how}{cmp_}')
    desc = f'{g["title"]}: {L["free"]}, {g["platforms"]}. {fmt_end(g["endtxt"], L)}'
    return shell(lang, cfg, f'{g["title"]} ({L["free"]}) | {cfg["name"][lang]}', desc, body,
                 path_for(g, lang), path_for(g, other), g["image"])


def extras(free, cfg):
    """sitemap, robots and an RSS feed (only once site_url is set)."""
    base = (cfg.get("site_url") or "").rstrip("/")
    if not base:
        return
    urls = [f"{base}/", f"{base}/ar/"] + [base + path_for(g, l) for g in free for l in T]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls) + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    rss = "".join(f'<item><title>{esc(g["title"])}</title><link>{esc(base + path_for(g, "en"))}</link>'
                  f'<guid>{esc(base + path_for(g, "en"))}</guid></item>' for g in free)
    (SITE / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(cfg["name"]["en"])}</title>'
        f'<link>{esc(base)}/</link><description>{esc(T["en"]["desc"])}</description>{rss}</channel></rss>',
        encoding="utf-8")


# ---------- telegram ----------
def tg_send(token, chat, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status == 200


def message(g, lang, cfg):
    L, base = T[lang], (cfg.get("site_url") or "").rstrip("/")
    link = base + path_for(g, lang) if base else g["claim"]
    was = f'<s>{money(g["was"])}</s> ' if g.get("was") else ""
    return (f'<b>{esc(g["title"])}</b>\n{was}<b>{L["free"]}</b> - {esc(g["platforms"])}\n'
            f'{esc(fmt_end(g["endtxt"], L))}\n\n{link}')


def post_new(free, cfg):
    """Post new giveaways to Telegram (max 5 per run). Without Telegram secrets, just stay in sync silently."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chats = {"en": os.environ.get("TELEGRAM_CHAT_EN", ""), "ar": os.environ.get("TELEGRAM_CHAT_AR", "")}
    sf = STATE / "posted.json"
    try:
        posted = json.loads(sf.read_text()) if sf.exists() else None
    except ValueError:
        posted = None
    ids = [g["id"] for g in free]
    STATE.mkdir(exist_ok=True)
    if posted is None or not (token and any(chats.values())):
        # first run, or Telegram not set up: remember what exists so we never flood a channel later
        sf.write_text(json.dumps(sorted(set((posted or []) + ids))[-400:]))
        return 0
    sent = []
    for g in [g for g in free if g["id"] not in posted][:5]:
        try:
            for lang, chat in chats.items():
                if chat:
                    tg_send(token, chat, message(g, lang, cfg))
                    time.sleep(1.5)
            sent.append(g["id"])
        except Exception as e:
            print(f'telegram failed for {g["id"]}: {e}', file=sys.stderr)
    sf.write_text(json.dumps(sorted(set(posted + sent))[-400:]))
    return len(sent)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    free = load_free()[: int(cfg.get("max_items", 40))]
    try:
        deals = load_deals(cfg)[: int(cfg.get("max_deals", 60))]
    except Exception as e:  # deals are a bonus: never let them break the site
        print(f"deals failed (site is still fine): {e}", file=sys.stderr)
        deals = []
    items = free + deals
    shutil.rmtree(SITE, ignore_errors=True)  # expired giveaways disappear with their pages
    for lang in T:
        out = SITE / ("ar" if lang == "ar" else "")
        write(out / "index.html", index_page(items, lang, cfg))
        for g in free:
            write(SITE / path_for(g, lang).lstrip("/"), detail_page(g, lang, cfg))
    nf = (f'<h1>{T["en"]["gone"]}</h1><p><a href="/">{T["en"]["back"]}</a></p>'
          f'<div lang="ar" dir="rtl"><h2>{T["ar"]["gone"]}</h2><p><a href="/ar/">{T["ar"]["back"]}</a></p></div>')
    write(SITE / "404.html", shell("en", cfg, "404", T["en"]["gone"], nf, "/", "/ar/"))
    # each optional piece is isolated: if one fails, the site still gets published
    for step in (extras, post_new):
        try:
            step(free, cfg)
        except Exception as e:
            print(f"{step.__name__} failed (site is still fine): {e}", file=sys.stderr)
    print(f"built {len(free)} free + {len(deals)} deals")


if __name__ == "__main__":
    main()
