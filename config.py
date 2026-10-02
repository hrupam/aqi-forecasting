"""
Central configuration for the Air Quality Forecasting & Early Warning System.

Every city gets its own folders:  data/<city>/raw, data/<city>/processed,
models/<city>/, reports/<city>/.  The active city is chosen with set_city(...)
(the CLI's --city flag and the dashboard's dropdown both call it).
Your OpenAQ API key is read from OPENAQ_API_KEY (or a .env file in this folder).
"""
from pathlib import Path
import json
import os
import re
import shutil

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
MODEL_ROOT = ROOT / "models"
REPORT_ROOT = ROOT / "reports"
CITIES_FILE = DATA_ROOT / "cities.json"      # cities added through search / --lat --lon


def _load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
OPENAQ_API_KEY = os.environ.get("OPENAQ_API_KEY", "")
SEARCH_RADIUS_M = 25_000          # OpenAQ max is 25 km

# ---------------------------------------------------------------- cities
_IST = "Asia/Kolkata"
PRESET_CITIES = {
    "Kolkata": (22.5726, 88.3639), "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946), "Chennai": (13.0827, 80.2707), "Hyderabad": (17.3850, 78.4867),
    "Ahmedabad": (23.0225, 72.5714), "Pune": (18.5204, 73.8567), "Lucknow": (26.8467, 80.9462),
    "Kanpur": (26.4499, 80.3319), "Patna": (25.5941, 85.1376), "Jaipur": (26.9124, 75.7873),
    "Chandigarh": (30.7333, 76.7794), "Gurugram": (28.4595, 77.0266), "Noida": (28.5355, 77.3910),
    "Ghaziabad": (28.6692, 77.4538), "Faridabad": (28.4089, 77.3178), "Agra": (27.1767, 78.0081),
    "Varanasi": (25.3176, 82.9739), "Bhopal": (23.2599, 77.4126), "Indore": (22.7196, 75.8577),
    "Nagpur": (21.1458, 79.0882), "Visakhapatnam": (17.6868, 83.2185), "Bhubaneswar": (20.2961, 85.8245),
    "Guwahati": (26.1445, 91.7362), "Thiruvananthapuram": (8.5241, 76.9366), "Kochi": (9.9312, 76.2673),
    "Coimbatore": (11.0168, 76.9558), "Amritsar": (31.6340, 74.8723), "Ludhiana": (30.9010, 75.8573),
    "Durgapur": (23.5204, 87.3119), "Asansol": (23.6739, 86.9524), "Siliguri": (26.7271, 88.3953),
    "Kharagpur": (22.3460, 87.2320), "Howrah": (22.5958, 88.2636),
}
CITIES = {name: {"lat": la, "lon": lo, "tz": _IST} for name, (la, lo) in PRESET_CITIES.items()}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _custom_cities() -> dict:
    try:
        return json.loads(CITIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def all_cities() -> dict:
    return {**CITIES, **_custom_cities()}


def register_city(name: str, lat: float, lon: float, tz: str = _IST, **extra) -> None:
    """Remember a searched / custom city (with its coordinates) for later runs."""
    reg = _custom_cities()
    reg[name] = {"lat": float(lat), "lon": float(lon), "tz": tz or _IST, **extra}
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    CITIES_FILE.write_text(json.dumps(reg, indent=2), encoding="utf-8")


def city_has_forecast(name: str) -> bool:
    return (MODEL_ROOT / slug(name) / "pm25_quantile_gbm.joblib").exists() and \
           (REPORT_ROOT / slug(name) / "forecast.csv").exists()


def cities_with_forecast() -> list[str]:
    return [c for c in all_cities() if city_has_forecast(c)]


def _migrate_single_city_layout(default_city: str):
    """Projects created before multi-city support kept everything in data/raw, data/processed,
    models/, reports/. Move that into the per-city folders once."""
    old_meta = DATA_ROOT / "processed" / "meta.json"
    if not old_meta.exists():
        return
    try:
        city = json.loads(old_meta.read_text()).get("city") or default_city
    except Exception:
        city = default_city
    s = slug(city)
    moves = [(DATA_ROOT / "raw", DATA_ROOT / s / "raw"), (DATA_ROOT / "processed", DATA_ROOT / s / "processed")]
    moves += [(f, MODEL_ROOT / s / f.name) for f in MODEL_ROOT.glob("*.joblib")]
    moves += [(f, REPORT_ROOT / s / f.name) for f in REPORT_ROOT.glob("*.*") if f.is_file()]
    for src, dst in moves:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    print(f"[config] moved existing {city} data into the per-city folders")


def set_city(name: str, lat: float | None = None, lon: float | None = None, tz: str | None = None):
    """Make `name` the active city: sets LAT/LON/LOCAL_TZ and the per-city folders."""
    global CITY, LAT, LON, LOCAL_TZ, SENSOR_ID, RAW_DIR, PROC_DIR, MODEL_DIR, REPORT_DIR
    known = all_cities().get(name)
    if lat is not None and lon is not None:
        if not known or (abs(known["lat"] - lat) > 1e-4 or abs(known["lon"] - lon) > 1e-4):
            register_city(name, lat, lon, tz or (known or {}).get("tz", _IST))
        known = all_cities()[name]
    if not known:
        raise SystemExit(f"Unknown city '{name}'. Use one of {sorted(all_cities())} "
                         "or pass --lat and --lon.")
    CITY, LAT, LON = name, known["lat"], known["lon"]
    LOCAL_TZ = tz or known.get("tz", _IST)
    env_city = os.environ.get("AQ_CITY", "Kolkata")
    SENSOR_ID = known.get("sensor_id") or (os.environ.get("AQ_SENSOR_ID") if name == env_city else None)
    s = slug(name)
    RAW_DIR, PROC_DIR = DATA_ROOT / s / "raw", DATA_ROOT / s / "processed"
    MODEL_DIR, REPORT_DIR = MODEL_ROOT / s, REPORT_ROOT / s
    for d in (RAW_DIR, PROC_DIR, MODEL_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


_migrate_single_city_layout(os.environ.get("AQ_CITY", "Kolkata"))
set_city(os.environ.get("AQ_CITY", "Kolkata"))

# ---------------------------------------------------------------- history window
# Open-Meteo historical forecasts (with boundary-layer height) start ~2022,
# CAMS air-quality history starts Aug 2022.
TRAIN_START = os.environ.get("AQ_TRAIN_START", "2023-01-01")

# ---------------------------------------------------------------- model
MAX_HORIZON = 60          # hours; 48 h + slack for station reporting delay
QUANTILES = (0.1, 0.5, 0.9)
ISSUE_STRIDE = 3          # use every 3rd hour as a forecast issue time when training
TEST_FRACTION = 0.25      # last 25 % of time (≥ 1 winter) is held out for the backtest

# ---------------------------------------------------------------- thresholds (µg/m³)
# CPCB (India) PM2.5 AQI bands; upper bound of each band.
CATEGORIES = [
    ("Good",         30,  "#2e7d32"),
    ("Satisfactory", 60,  "#9ccc65"),
    ("Moderate",     90,  "#fdd835"),
    ("Poor",         120, "#fb8c00"),
    ("Very Poor",    250, "#e53935"),
    ("Severe",       10_000, "#7b1fa2"),
]
NAAQS_24H = 60      # India National Ambient Air Quality Standard, 24-h mean
WHO_24H = 15        # WHO 2021 guideline, 24-h mean

# Alert threshold by user profile (hourly PM2.5 that triggers a warning)
PROFILES = {
    "General public": 90,
    "Sensitive (asthma / heart / lung)": 60,
    "Children & elderly": 60,
    "Outdoor workers / athletes": 60,
    "Strict (WHO-based)": 35,
}
