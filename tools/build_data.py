"""osm_raw.json と featured.json から、アプリが読む ../data.js を作る。
- OSMのカフェは「犬連れOKの印」か「店名がドッグカフェらしい」ものだけ残す
- 名前のないドッグランは、国土地理院の住所検索で「〇〇市△△」を補う
- 調査済みスポット（featured）は国土地理院で位置を調べ、近くのOSM重複は除く
- 動画・投稿が今も見られるか確認する
"""
import json, math, re, time
import truststore
truststore.inject_into_ssl()
import httpx

cli = httpx.Client(timeout=30, headers={"User-Agent": "dogmap-personal/1.0"}, follow_redirects=True)

INCLUDE = re.compile(
    r"ドッグカフェ|犬カフェ|ドッグラン|ドッグ\s*[&＆+]\s*カフェ|カフェ\s*[&＆+]?\s*ドッグ|dog\s*cafe|cafe\s*(and|&|\+)?\s*(dogs?|wan)\b"
    r"|dog\s*(garden|oasis|heart|friend|day\s*cafe)|with\s*dog|heart2\s*dog|farm\s*&\s*dogs|ドッグフレンド|ドッグルハウス"
    r"|\+\s*dog|and\s*わんこ|犬猫人|ドッグ＆ベジ|coffee\s*dogs|cafe\s*doggies|dogcafe",
    re.I)
EXCLUDE = re.compile(r"ホットド|hot\s*dog|hotdog|ブルド|bulldog|犬山|犬塚|犬吠|犬鳴|八犬伝|dogenzaka|edogawa|パドック|パラドックス|サロン", re.I)

def dist_m(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = (lo2 - lo1) * math.cos((la1 + la2) / 2)
    return math.hypot(x, la2 - la1) * 6371000

# 市区町村コード → 名称（国土地理院の muni.js）
muni = {}
js = cli.get("https://maps.gsi.go.jp/js/muni.js").text
for m in re.finditer(r'GSI\.MUNI_ARRAY\["(\d+)"\]\s*=\s*\'([^\']*)\'', js):
    p = m.group(2).split(",")
    muni[m.group(1).lstrip("0")] = (p[1], p[3].replace("　", ""))

def reverse(lat, lng):
    try:
        r = cli.get("https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress", params={"lat": lat, "lon": lng}).json()
        res = r.get("results") or {}
        pref, city = muni.get(str(res.get("muniCd", "")).lstrip("0"), ("", ""))
        return pref, city, res.get("lv01Nm", "").replace("－", "")
    except Exception:
        return "", "", ""

def geocode(addr):
    q = addr
    while q:
        r = cli.get("https://msearch.gsi.go.jp/address-search/AddressSearch", params={"q": q}).json()
        if r:
            lng, lat = r[0]["geometry"]["coordinates"]
            return lat, lng, r[0]["properties"]["title"]
        q = re.sub(r"[\s　]*\S*$", "", q) if " " in q or "　" in q else re.sub(r"[0-9０-９\-－ー]+[^0-9０-９]*$", "", q)
        if len(q) < 5:
            break
    return None

spots = []

# ---- 調査済みスポット ----
featured = json.load(open("featured.json", encoding="utf-8"))
for f in featured:
    g = geocode(f["address"])
    print("位置:", f["name"], "→", g)
    time.sleep(0.3)
    if not g:
        continue
    media = []
    for m in f["media"]:
        if m["kind"] == "youtube":
            r = cli.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={m['id']}", "format": "json"})
            ok = r.status_code == 200
            if ok:
                media.append({"kind": "youtube", "id": m["id"], "title": r.json()["title"]})
        else:
            code = re.search(r"/(p|reel)/([^/]+)/", m["url"])
            r = cli.get(f"https://www.instagram.com/{code.group(1)}/{code.group(2)}/embed/captioned/")
            ok = r.status_code == 200 and "EmbeddedMediaImage" in r.text or "embed" in r.url.path
            media.append({"kind": "instagram", "url": m["url"]})
        print("   ", m.get("id") or m.get("url"), "OK" if ok else "見られない")
    spots.append({
        "n": f["name"], "t": f["type"], "lat": round(g[0], 6), "lng": round(g[1], 6),
        "a": f["address"], "note": f["note"], "web": f["website"], "ig": f["instagram_account"],
        "x": f["x_account"], "media": media, "feat": 1,
    })

# ---- OSM ----
raw = json.load(open("osm_raw.json", encoding="utf-8"))["elements"]
seen = set()
for e in raw:
    t = e.get("tags", {})
    lat = e.get("lat") or e.get("center", {}).get("lat")
    lng = e.get("lon") or e.get("center", {}).get("lon")
    if lat is None:
        continue
    name = (t.get("name:ja") or t.get("name") or "").strip()
    if t.get("leisure") == "dog_park":
        typ = "dogrun"
    else:
        dogok = t.get("dog") in ("yes", "leashed", "unleashed", "outside")
        if EXCLUDE.search(name) or not (dogok or INCLUDE.search(name)):
            continue
        typ = "dogcafe"
    key = (typ, name, round(lat, 3), round(lng, 3))
    if key in seen:
        continue
    seen.add(key)
    if any(s.get("feat") and dist_m((lat, lng), (s["lat"], s["lng"])) < 400 for s in spots):
        continue
    s = {"n": name, "t": typ, "lat": round(lat, 6), "lng": round(lng, 6)}
    if typ == "dogcafe" and not INCLUDE.search(name):
        s["ok"] = 1  # 店名はふつうのカフェだが、犬連れOKの登録あり
    if t.get("website") or t.get("contact:website"):
        s["web"] = t.get("website") or t.get("contact:website")
    if t.get("contact:instagram"):
        s["ig"] = t["contact:instagram"]
    if t.get("opening_hours"):
        s["hours"] = t["opening_hours"]
    spots.append(s)

# 住所（市区町村）を補う
for i, s in enumerate(spots):
    if s.get("feat"):
        continue
    pref, city, town = reverse(s["lat"], s["lng"])
    s["a"] = pref + city + town
    s["area"] = city
    if not s["n"]:
        s["n"] = f"{city}{town}のドッグラン" if city else "ドッグラン（名称未登録）"
        s["noname"] = 1
    time.sleep(0.12)
    if i % 50 == 0:
        print("住所補完", i, "/", len(spots))

with open("../data.js", "w", encoding="utf-8") as fp:
    fp.write("// 自動生成（tools/build_data.py）。出典: © OpenStreetMap contributors (ODbL) / 国土地理院 / 独自調査\n")
    fp.write("window.SPOTS = " + json.dumps(spots, ensure_ascii=False, separators=(",", ":")) + ";\n")

from collections import Counter
print(Counter((s["t"], bool(s.get("feat"))) for s in spots))
