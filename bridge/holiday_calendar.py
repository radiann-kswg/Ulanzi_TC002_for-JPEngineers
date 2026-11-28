"""Fetch national holidays for Japan and representative UTC-offset regions."""
import csv
from datetime import datetime, timezone
import io
from urllib.request import Request, urlopen

import holidays


# The world clock stores an offset rather than a named zone. Each real-world offset
# therefore has one representative country whose national public holidays are shown.
REPRESENTATIVE_ZONES = {
    -660: ("AS", "AS"), -600: ("US", "US"), -570: ("PF", "PF"),
    -540: ("US", "US"), -480: ("US", "US"), -420: ("US", "US"),
    -360: ("US", "US"), -300: ("US", "US"), -240: ("US", "US"),
    -210: ("CA", "CA"), -180: ("BR", "BR"), -120: ("BR", "BR"),
    -60: ("CV", "CV"), 0: ("GB", "GB"), 60: ("FR", "FR"),
    120: ("ZA", "ZA"), 180: ("SA", "SA"), 210: ("IR", "IR"),
    240: ("AE", "AE"), 270: ("AF", "AF"), 300: ("PK", "PK"),
    330: ("IN", "IN"), 345: ("NP", "NP"), 360: ("BD", "BD"),
    390: ("MM", "MM"), 420: ("TH", "TH"), 480: ("SG", "SG"),
    525: ("AU", "AU"), 540: ("JP", "日本"), 570: ("AU", "AU"),
    600: ("AU", "AU"), 630: ("AU", "AU"), 660: ("NC", "NC"),
    720: ("NZ", "NZ"), 765: ("NZ", "NZ"), 780: ("WS", "WS"),
    840: ("KI", "KI"),
}


def _read(url):
    request = Request(url, headers={"User-Agent": "Ulanzi-TC002-for-JPEngineers/holiday-calendar"})
    with urlopen(request, timeout=12) as response:
        return response.read()


def japan_holidays():
    raw = _read("https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp932")
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        try:
            day = datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
        except ValueError:
            continue
        rows.append((day, row[1].strip()))
    if not rows:
        raise ValueError("Cabinet Office holiday data was empty")
    return rows


def world_holidays(country, year):
    language = None if country in {"ZA", "NZ", "WS", "KI"} else "en_US"
    calendar = holidays.country_holidays(country, years=year, language=language)
    return sorted(calendar.items())


def collect(now, japan_loader=japan_holidays, world_loader=world_holidays):
    """Return complete holiday years; the device selects its current local date."""
    years = sorted({datetime.fromtimestamp(now + offset * 60, timezone.utc).year
                    for offset in REPRESENTATIVE_ZONES})
    japanese = [(day, name) for day, name in japan_loader() if day.year in years]
    countries = sorted({country for country, _ in REPRESENTATIVE_ZONES.values() if country != "JP"})
    requests = [(country, year) for country in countries for year in years]
    calendars = {}
    errors = []
    for key in requests:
        try:
            calendars[key] = world_loader(*key)
        except Exception as error:
            calendars[key] = []
            errors.append(f"{key[0]}:{key[1]}:{type(error).__name__}")
    records = []
    for offset, (country, region) in REPRESENTATIVE_ZONES.items():
        if country == "JP":
            records.extend({"date":day.isoformat(),"offset":offset,"region":region,"name":name}
                           for day, name in japanese)
            continue
        for year in years:
            for day, name in calendars[country, year]:
                if isinstance(name, str) and name:
                    records.append({"date":day.isoformat(),"offset":offset,"region":region,"name":name})
    return {"observedAt": now, "holidays": records, "worldErrors": errors}
