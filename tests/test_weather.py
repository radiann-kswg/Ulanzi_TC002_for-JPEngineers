import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import weather, store

class WeatherTest(unittest.TestCase):
    def test_roles_arrive_on_wire_without_changing_the_display_label(self):
        data={"current":{"weather_code":95,"temperature_2m":21,"relative_humidity_2m":60,
                          "surface_pressure":1008},
              "daily":{"temperature_2m_max":[23],"temperature_2m_min":[13]}}
        with patch("bridge.weather.request",return_value=data):
            result=weather.observe(weather.AKO)
        with tempfile.TemporaryDirectory() as temp:
            db=store.open_db(Path(temp)/"test.db")
            try:
                store.save(db,"weather",result,1000,900)
                wire=store.snapshot(db,weather.AKO,1000).decode()
                self.assertIn("雷雨\tstorm\n",wire)
                self.assertIn("赤穂市\tplace\n",wire)
            finally: db.close()
