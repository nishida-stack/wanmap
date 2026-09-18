"""OpenStreetMap（Overpass API）から全国のドッグラン・ドッグカフェを取得して osm_raw.json に保存する。"""
import json
import truststore
truststore.inject_into_ssl()
import httpx

QUERY = r"""
[out:json][timeout:300];
area["ISO3166-1"="JP"][admin_level=2]->.jp;
(
  nwr["leisure"="dog_park"](area.jp);
  nwr["amenity"="cafe"]["dog"~"^(yes|leashed|unleashed|outside)$"](area.jp);
  nwr["amenity"~"^(cafe|restaurant)$"]["name"~"ドッグ|ドック|わんこ|ワンコ|ワンちゃん|犬|[Dd]og|DOG|[Ww]an|WAN"](area.jp);
);
out center tags;
"""

ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

for url in ENDPOINTS:
    try:
        r = httpx.post(url, data={"data": QUERY}, timeout=400, headers={"User-Agent": "dogmap-personal/1.0"})
        r.raise_for_status()
        data = r.json()
        break
    except Exception as e:
        print("失敗:", url, e)
else:
    raise SystemExit(1)

with open("osm_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
print("件数:", len(data["elements"]))
