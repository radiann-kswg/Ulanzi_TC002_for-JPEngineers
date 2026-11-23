import json
from urllib.parse import urlencode
from urllib.request import urlopen

AKO = {"name":"赤穂市","lat":34.754974,"lon":134.390354}

def request(url, params):
    with urlopen(url+"?"+urlencode(params), timeout=12) as response:
        return json.load(response)

def search(name):
    hits = request("https://msearch.gsi.go.jp/address-search/AddressSearch", {"q":name})
    return [{"name":h["properties"]["title"], "lat":h["geometry"]["coordinates"][1],
             "lon":h["geometry"]["coordinates"][0]} for h in hits if h["geometry"]["type"]=="Point"]

def description(code):
    if code == 0: return "快晴"
    if code in (1,2): return "晴れ" if code==1 else "薄曇り"
    if code == 3: return "曇り"
    if code in (45,48): return "霧"
    if code in (51,53,55,56,57): return "霧雨"
    if code in (61,63,65,66,67): return "雨"
    if code in (71,73,75,77,85,86): return "雪"
    if code in (80,81,82): return "にわか雨"
    if code in (95,96,99): return "雷雨"
    return "天気不明"

def observe(place):
    result = request("https://api.open-meteo.com/v1/forecast", {
        "latitude":place["lat"],"longitude":place["lon"],
        "current":"temperature_2m,relative_humidity_2m,weather_code,surface_pressure",
        "daily":"temperature_2m_max,temperature_2m_min","forecast_days":1,
        "timezone":"Asia/Tokyo"})
    current, daily = result["current"], result["daily"]
    items = [place["name"], description(current["weather_code"]),
             f'{current["temperature_2m"]:.1f}°C', f'湿度 {current["relative_humidity_2m"]}%',
             f'{current["surface_pressure"]:.0f}hPa',
             f'最高 {daily["temperature_2m_max"][0]:g}°C',f'最低 {daily["temperature_2m_min"][0]:g}°C']
    symbol={"快晴":"sun","晴れ":"sun","曇り":"cloud","薄曇り":"partly","霧":"fog",
            "霧雨":"rain","雨":"rain","にわか雨":"rain","雪":"snow","雷雨":"storm"}
    return {"rows":[[3,3,item] for item in items],
            "weatherKinds":["place",symbol.get(items[1],"cloud"),"temp","humidity","pressure","high","low"]}

def air(place):
    data=request("https://air-quality-api.open-meteo.com/v1/air-quality",{
        "latitude":place["lat"],"longitude":place["lon"],"current":"us_aqi"})
    return {"rows":[[3,3,f'US AQI {data["current"]["us_aqi"]:.0f}']],"weatherKinds":["air"]}
