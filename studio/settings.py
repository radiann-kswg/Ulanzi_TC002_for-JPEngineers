"""Translate editable Studio fields to the same document the bridge watches."""
from dataclasses import dataclass
from ipaddress import IPv4Address
import re

from bridge import config, github, store, weather


@dataclass(frozen=True)
class Fields:
    device: str
    name: str
    lat: str
    lon: str
    owner: str
    repos: str
    adb: str
    weekday_coloring: str

    @classmethod
    def from_document(cls, document):
        place = document.get("place", weather.AKO)
        if not isinstance(place, dict) or not {"name", "lat", "lon"} <= place.keys():
            raise ValueError("place に地点名、緯度、経度を指定してください。")
        repos = document.get("repos", [])
        if not isinstance(repos, list) or not all(isinstance(repo, str) for repo in repos):
            raise ValueError("repos にはリポジトリ名の配列を指定してください。")
        def optional(key):
            value = document.get(key)
            if value is None:
                return ""
            if not isinstance(value, str):
                raise ValueError(f"{key} には文字列を指定してください。")
            return value
        coloring = document.get("weekdayColoring", config.DEFAULT_WEEKDAY_COLORING)
        if coloring not in config.WEEKDAY_COLORINGS:
            raise ValueError("曜日配色の設定を確認してください。")
        return cls(optional("device"), str(place["name"]), str(place["lat"]), str(place["lon"]),
                   optional("owner"), ", ".join(repos), optional("adb"), coloring)

    def apply(self, document):
        updated = document.copy()
        address = self.device.strip()
        if address:
            try:
                ip = IPv4Address(address)
                if int(ip) == 0 or ip.is_multicast or int(ip) == 0xFFFFFFFF:
                    raise ValueError()
            except ValueError:
                raise ValueError("時計の IP アドレスにはユニキャスト IPv4 を入力してください。") from None
        try:
            lat, lon, name = store.position({"name": self.name, "lat": self.lat, "lon": self.lon})
        except (TypeError, ValueError):
            raise ValueError("地点名、緯度（−90～90）、経度（−180～180）を確認してください。") from None
        updated["place"] = {**document.get("place", {}), "name": name, "lat": lat, "lon": lon}
        try:
            updated["repos"] = list(dict.fromkeys(github.repository(repo) for repo in re.split(
                r"[,\s]+", self.repos.strip()) if repo))
        except ValueError:
            raise ValueError("リポジトリは owner/name 形式で入力し、複数ある場合はコンマで区切ってください。") from None
        owner = self.owner.strip()
        if owner:
            try:
                github.repository(owner + "/check")
            except ValueError:
                raise ValueError("GitHub 所有者にはアカウント名または組織名を入力してください。") from None
        for key, value in (("device", address), ("owner", owner), ("adb", self.adb.strip())):
            if value:
                updated[key] = value
            else:
                updated.pop(key, None)
        if self.weekday_coloring not in config.WEEKDAY_COLORINGS:
            raise ValueError("曜日配色の設定を確認してください。")
        updated["weekdayColoring"] = self.weekday_coloring
        return updated


def save(path, baseline, fields):
    def edit(current):
        if Fields.from_document(current) != baseline:
            raise ValueError("別の操作で設定が変わりました。再読み込みしてから編集してください。")
        return fields.apply(current)
    return Fields.from_document(config.update(path, edit))
