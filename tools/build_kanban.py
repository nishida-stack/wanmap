"""看板犬のいるお店（kanban/*.json）から、アプリが読む ../data.js を作る。
- 国土地理院の住所検索で位置を求める
- YouTube・X は公式の埋め込み情報（oEmbed）で今も見られるか確認し、見られないものは外す
- Instagram は埋め込み用ページが開けるか確認する
- 同じお店が重複していたら1つにまとめる
"""
import glob, json, re, time, unicodedata
import truststore
truststore.inject_into_ssl()
import httpx

cli = httpx.Client(timeout=30, follow_redirects=True,
                   headers={"User-Agent": "Mozilla/5.0 (dogmap-personal)"})

def geocode(addr):
    q = re.sub(r"[（(].*?[）)]", "", addr).strip()
    for _ in range(4):
        try:
            r = cli.get("https://msearch.gsi.go.jp/address-search/AddressSearch", params={"q": q}).json()
        except Exception:
            r = []
        if r:
            lng, lat = r[0]["geometry"]["coordinates"]
            return lat, lng
        # 末尾（建物名・番地）を削って再検索
        nq = re.sub(r"[\s　][^\s　]*$", "", q)
        if nq == q:
            nq = re.sub(r"[0-9０-９\-－ー番地号丁目の]+[^0-9０-９]*$", "", q)
        if nq == q or len(nq) < 5:
            break
        q = nq
    return None

def ok_youtube(vid):
    r = cli.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
    return r.json()["title"] if r.status_code == 200 else None

def ok_x(url):
    r = cli.get("https://publish.twitter.com/oembed", params={"url": url, "omit_script": "1"})
    return r.status_code == 200

def ok_instagram(url):
    m = re.search(r"instagram\.com/(?:[^/]+/)?(p|reel|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        return None
    clean = f"https://www.instagram.com/{m.group(1)}/{m.group(2)}/"
    r = cli.get(clean + "embed/captioned/")
    # 存在しない・削除された投稿でも200が返るため、実際の写真・動画の部品があるかで判定する
    return clean if r.status_code == 200 and "EmbeddedMedia" in r.text else None

def key(name):
    n = unicodedata.normalize("NFKC", name).lower()
    return re.sub(r"[（(].*?[）)]|\s|[&＆・]", "", n)

spots, seen, report = [], {}, []
for path in sorted(glob.glob("kanban/*.json")):
    for f in json.load(open(path, encoding="utf-8")):
        k = key(f["name"])
        if k in seen:
            report.append(f"重複のため統合: {f['name']}")
            continue
        g = geocode(f.get("geo") or f["address"])  # geo: 京都の通り名入り住所など、位置検索用の住所
        time.sleep(0.2)
        if not g:
            report.append(f"位置不明のため除外: {f['name']} / {f['address']}")
            continue
        media = []
        for m in f.get("media", []):
            try:
                if m["kind"] == "youtube":
                    t = ok_youtube(m["id"])
                    if t: media.append({"kind": "youtube", "id": m["id"], "title": t})
                    else: report.append(f"動画が見られず除外: {f['name']} {m['id']}")
                elif m["kind"] == "x":
                    if ok_x(m["url"]): media.append({"kind": "x", "url": m["url"]})
                    else: report.append(f"X投稿が見られず除外: {f['name']} {m['url']}")
                elif m["kind"] == "instagram":
                    u = ok_instagram(m["url"])
                    if u: media.append({"kind": "instagram", "url": u})
                    else: report.append(f"Instagram投稿が見られず除外: {f['name']} {m['url']}")
            except Exception as e:
                report.append(f"確認失敗: {f['name']} {m} {e}")
            time.sleep(0.2)
        s = {
            "n": f["name"], "t": f["type"], "lat": round(g[0], 6), "lng": round(g[1], 6),
            "a": f["address"], "note": f.get("note"), "web": f.get("website"),
            "ig": f.get("instagram_account"), "x": f.get("x_account"),
            "dogs": f.get("dogs", []), "src": f.get("dog_source"), "media": media,
        }
        seen[k] = s
        spots.append(s)

with open("../data.js", "w", encoding="utf-8") as fp:
    fp.write("// 自動生成（tools/build_kanban.py）。看板犬のいるドッグカフェ・ドッグラン（独自調査）。地図: 国土地理院\n")
    fp.write("window.SPOTS = " + json.dumps(spots, ensure_ascii=False, separators=(",", ":")) + ";\n")

print("\n".join(report))
from collections import Counter
print("件数:", len(spots), Counter(s["a"][:3] for s in spots), Counter(s["t"] for s in spots))
print("写真・動画なし:", [s["n"] for s in spots if not s["media"]])
