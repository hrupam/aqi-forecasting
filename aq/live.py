"""Live look-ups for the city picker: geocoding, nearby stations' latest PM2.5,
CAMS outlook for one city and for many cities at once. No model needed."""
from __future__ import annotations

import requests
import pandas as pd

import config

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def geocode(name: str, count: int = 8) -> list[dict]:
    """Search any place name (Open-Meteo / GeoNames). Returns [{label, name, lat, lon, tz}]."""
    if len(name.strip()) < 2:
        return []
    r = requests.get(GEO_URL, params={"name": name.strip(), "count": count, "language": "en"}, timeout=20)
    r.raise_for_status()
    out, seen = [], set()
    for g in r.json().get("results", []) or []:
        # GeoNames often lists the same town several times (town, municipality, division):
        # merge entries closer than ~5 km and show the district to tell real namesakes apart
        key = (g.get("name"), round(g["latitude"] / 0.05), round(g["longitude"] / 0.05))
        if key in seen:
            continue
        seen.add(key)
        parts = [g.get("name"), g.get("admin2") if g.get("admin2") != g.get("name") else None,
                 g.get("admin1"), g.get("country")]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        if any(o["label"] == label for o in out):
            label += f" ({g['latitude']:.2f}°, {g['longitude']:.2f}°)"
        out.append({"label": label, "name": g.get("name"), "lat": g["latitude"], "lon": g["longitude"],
                    "tz": g.get("timezone") or "UTC", "population": g.get("population")})
    return out


def nearby_latest(lat: float, lon: float, max_stations: int = 8) -> pd.DataFrame:
    """Latest PM2.5 at the nearest active OpenAQ stations (needs OPENAQ_API_KEY)."""
    from aq import openaq
    sensors = openaq.find_pm25_sensors(lat, lon, config.SEARCH_RADIUS_M)
    if sensors.empty:
        return sensors
    sensors = sensors[sensors["active"]].sort_values("distance_m").drop_duplicates("location_id")
    rows = []
    for _, s in sensors.head(max_stations).iterrows():
        try:
            js = openaq._get(f"/locations/{int(s.location_id)}/latest")
        except Exception:
            continue
        ours = [m for m in js.get("results", []) if m.get("sensorsId") == s.sensor_id] or \
               [m for m in js.get("results", []) if m.get("sensorsId") in set(sensors.sensor_id)]
        if not ours:
            continue
        m = ours[0]
        rows.append({"station": s.location, "provider": s.provider, "lat": s.lat, "lon": s.lon,
                     "distance_km": (s.distance_m or 0) / 1000, "pm25": m.get("value"),
                     "time": pd.to_datetime((m.get("datetime") or {}).get("utc"), utc=True)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[(df.pm25 >= 0) & (df.pm25 < 1000)]
    return df


def cams_outlook(lat: float, lon: float, past_days: int = 3, days: int = 4) -> pd.DataFrame:
    """Hourly CAMS PM2.5 and PM10 (UTC index) for one place."""
    r = requests.get(AQ_URL, params={"latitude": lat, "longitude": lon, "hourly": "pm2_5,pm10",
                                     "past_days": past_days, "forecast_days": days, "timezone": "GMT"},
                     timeout=60)
    r.raise_for_status()
    h = pd.DataFrame(r.json()["hourly"])
    h["time"] = pd.to_datetime(h["time"]).dt.tz_localize("UTC")
    return h.set_index("time").rename(columns={"pm2_5": "pm25"}).apply(pd.to_numeric, errors="coerce")


def cams_many(cities: dict) -> dict[str, pd.DataFrame]:
    """CAMS PM2.5/PM10 for many cities in one request: {name: {"lat", "lon"}} -> {name: df}."""
    names = list(cities)
    out = {}
    for i in range(0, len(names), 50):                     # the API takes a list of coordinates
        chunk = names[i:i + 50]
        r = requests.get(AQ_URL, params={
            "latitude": ",".join(f"{cities[n]['lat']:.4f}" for n in chunk),
            "longitude": ",".join(f"{cities[n]['lon']:.4f}" for n in chunk),
            "hourly": "pm2_5,pm10", "past_days": 1, "forecast_days": 3, "timezone": "GMT"}, timeout=90)
        r.raise_for_status()
        js = r.json()
        js = js if isinstance(js, list) else [js]
        for n, item in zip(chunk, js):
            h = pd.DataFrame(item["hourly"])
            h["time"] = pd.to_datetime(h["time"]).dt.tz_localize("UTC")
            out[n] = h.set_index("time").rename(columns={"pm2_5": "pm25"}).apply(pd.to_numeric, errors="coerce")
    return out
