
---

## 5. `config.py`: settings and the multi-city switch

`config.py` is imported by every other module. It plays two roles:
1. It holds the **constants**: thresholds, model settings, the city list.
2. It holds the **mutable "active city" state**: coordinates and folders.

Other modules always read `config.LAT`, `config.RAW_DIR` and so on **at call time**. Switching city with `set_city()` therefore redirects the whole program, with no parameters passed around.

### 5.1 Module-level constants
| Name | Value | Meaning |
|---|---|---|
| `ROOT` | folder of `config.py` | Project root; all paths are built from it |
| `DATA_ROOT`, `MODEL_ROOT`, `REPORT_ROOT` | `data/`, `models/`, `reports/` | Parent folders; each city gets a subfolder |
| `CITIES_FILE` | `data/cities.json` | Registry of searched/custom cities and pinned stations |
| `OPENAQ_API_KEY` | from `.env` | Needed for station data |
| `SEARCH_RADIUS_M` | 25 000 | OpenAQ's maximum search radius |
| `PRESET_CITIES` | 35 Indian cities → (lat, lon) | The dropdown list |
| `CITIES` | dict name → `{lat, lon, tz}` | Built from the presets, time zone Asia/Kolkata |
| `TRAIN_START` | `2023-01-01` (or `AQ_TRAIN_START`) | First day of history downloaded. Open-Meteo's archived forecasts and CAMS history start in 2022, so 2023 is safe |
| `MAX_HORIZON` | 60 | Forecast length in hours: 48 h of useful forecast plus 12 h of slack, because Indian stations often report hours late. If the last reading is 10 h old, a 60-h forecast still covers the next 48 h from *now* |
| `QUANTILES` | (0.1, 0.5, 0.9) | The 10th, 50th (median) and 90th percentiles forecast |
| `ISSUE_STRIDE` | 3 | Only every 3rd hour is used as a training "issue time". Neighbouring hours are nearly identical, so this cuts the data and training time by 3× with almost no loss of information |
| `TEST_FRACTION` | 0.25 | The last 25 % of time is held out for the backtest |
| `CATEGORIES` | CPCB PM2.5 bands with colours | Good ≤30, Satisfactory ≤60, Moderate ≤90, Poor ≤120, Very Poor ≤250, Severe above that |
| `NAAQS_24H`, `WHO_24H` | 60, 15 | 24-h standards |
| `PROFILES` | 5 profiles → threshold | General 90; Sensitive, Children & elderly, Outdoor workers 60; Strict (WHO-based) 35 |

### 5.2 Functions
**`_load_dotenv()`** is a tiny `.env` reader that avoids a dependency on `python-dotenv`.
* It reads `KEY=value` lines, skipping blank lines and `#` comments, and strips quotes.
* It uses `os.environ.setdefault`, so a real environment variable always wins over the file.

**`slug(name)`** turns a city name into a safe folder name.
* It applies Unicode NFKD normalisation and drops non-ASCII marks, so "Bārāsat" becomes "Barasat".
* It lower-cases, replaces any run of non-alphanumeric characters with `_`, and trims underscores.
* It falls back to `"place"` if the result would be empty.
* Examples: `"Kolkata"` → `kolkata`; `"Bārāsat, South 24 Parganas"` → `barasat_south_24_parganas`.
* Why: Windows paths and accented characters don't mix reliably.

**`_custom_cities()`** reads `data/cities.json` and returns `{}` if it is missing or broken. It never crashes.

**`all_cities()`** returns `{**CITIES, **_custom_cities()}`. Custom entries **override** presets with the same name. This is how a pinned `sensor_id` gets attached to a preset city such as Kolkata.

**`register_city(name, lat, lon, tz, **extra)`** adds or overwrites a city in `cities.json`. `extra` carries optional fields such as `sensor_id`.

**`set_city_sensor(name, sensor_id | None)`** pins a city to a station (stores `sensor_id`) or unpins it (`None` removes the key). The dashboard's station picker and the CLI flags `--sensor` and `--auto-station` use it.

**`city_has_forecast(name)`** is true when both the model file and `forecast.csv` exist for the city. This decides between the **full dashboard** and **quick view**, and adds the ✅ mark.

**`cities_with_forecast()`** lists the ✅ cities. `--all-cities` and the dropdown ordering use it.

**`_migrate_single_city_layout(default_city)`** is a one-time upgrade for projects created before multi-city support.
* If `data/processed/meta.json` exists, the old flat layout is moved into `data/<city>/…`, `models/<city>/…` and `reports/<city>/…`.
* The city name is read from the old `meta.json`.
* It moves only when the destination doesn't already exist, so it is safe to run repeatedly.

**`set_city(name, lat=None, lon=None, tz=None)`** is the most important function in the file. It uses `global` to rebind the module variables `CITY, LAT, LON, LOCAL_TZ, SENSOR_ID, RAW_DIR, PROC_DIR, MODEL_DIR, REPORT_DIR`.
* If coordinates are given and the city is unknown (or moved), it registers the city.
* An unknown city without coordinates is an error that lists the valid names.
* **`SENSOR_ID` precedence:** a pinned `sensor_id` in the registry wins. Otherwise `AQ_SENSOR_ID` from `.env` is used, but only for the default city (`AQ_CITY`), so it doesn't leak into other cities.
* It creates the four per-city folders.

At import time the module runs `_migrate_single_city_layout()` and `set_city(AQ_CITY or "Kolkata")`, so there is always an active city.

> **Design note:** module-level globals are a deliberate simplification here. Each process (CLI run or Streamlit run) works on one city at a time. A larger system would pass a `City` object around instead.

---

## 6. Data clients

### 6.1 `aq/openaq.py`: OpenAQ v3 client
Constants: `BASE = "https://api.openaq.org/v3"`, `PM25_PARAMETER_ID = 2`.

**`_get(path, params, retries=6)`** handles every call to OpenAQ.
1. Refuses to run without an API key, with a helpful message that says where to get one.
2. Sends the request with header `X-API-Key` and a 60 s timeout.
3. On **429 (rate-limited) or 5xx**, waits and retries, up to 6 attempts:
   * the wait is the `x-ratelimit-reset` header if present, otherwise exponential back-off (5 s, 10 s, 20 s…)
   * the wait is capped at 60 s
4. On other errors, raises (`raise_for_status`).
5. After every success it sleeps **1.1 s**, which keeps the client under about 55 requests per minute.

**`find_pm25_sensors(lat, lon, radius_m)`** builds the list of candidate sensors.
* Calls `/locations` with `coordinates`, `radius`, `parameters_id=2` and `limit=100`.
* Makes one row per PM2.5 sensor with these fields:
  * `sensor_id`, `location_id`, `location` (name), `provider` (for example CPCB, AirNow)
  * `is_monitor` (reference-grade vs low-cost), `lat`/`lon`, `distance_m`
  * `first` / `last` (the location's first and last data times)
* Adds two derived columns:
  * `active`: last data less than 3 days ago
  * `years`: `(last - first)` in years
* **Ranking:** active first, then reference monitors, then the longest history, then the closest.
* *Nitty-gritty:* `first` and `last` are **location-level** dates. That is why two sensors of the same station get the same rank, and why the pipeline joins all sensors of a station instead of trusting one sensor ID (see section 8.2).

**`fetch_sensor_hours(sensor_id, start, end=None, chunk_days=120)`** downloads a long history safely.
* Normalises `start` and `end` to UTC. `end` defaults to now.
* Splits the period into **120-day chunks**, because asking for years at once can hit the API's timeout (HTTP 408).
* Concatenates the chunks, drops duplicate timestamps and sorts.
* Returns an empty frame with the right columns if there is no data.

**`_fetch_hours_range(sensor_id, start, end)`** handles one chunk, with pagination.
* Requests `limit=1000` per page and keeps paging until a page returns fewer rows than the limit.
* If the server rejects `limit=1000` with **422**, it restarts the chunk with `limit=100`. Some API deployments cap the page size.
* For each item it keeps `time = period.datetimeFrom.utc`, `pm25 = value` and `coverage = coverage.percentComplete`. Coverage is the share of sub-hourly readings present in that hour, and quality control uses it.
* Prints progress on one line (`end="\r"`).

### 6.2 `aq/openmeteo.py`: weather and CAMS client
Constants: four endpoint URLs, `WEATHER_VARS` (the 11 hourly variables in section 4.2), and `RENAME`, which maps API names to short column names.

**`_request(url, params, variables)`** is the self-healing core of this module.
* Always asks for `timezone=GMT` (UTC timestamps) and `wind_speed_unit=ms` (metres per second).
* **Unsupported-variable recovery:** if the API answers 400 and its `reason` mentions one of the requested variables, that variable is removed and the request retried. The historical endpoints don't all offer `boundary_layer_height` for every period, and this keeps the pipeline running instead of crashing.
* On 429 it waits 30 s, 60 s, and so on.
* Converts the JSON `hourly` block to a DataFrame and localises the times to UTC.
* **Forces every value column to numeric** (`pd.to_numeric(errors="coerce")`). JSON `null`s for a missing variable otherwise produce *object* columns, which crashed `interpolate` in an early version.
* Renames the columns with `RENAME`.

**`_yearly_chunks(start, end)`** is a generator of (start, end) date strings, one calendar year at a time. Long requests are slower and more fragile.

**`fetch_weather_history(lat, lon, start, end)`** fetches yearly chunks from the **historical-forecast** API. If a chunk fails, that chunk is fetched from the **ERA5 archive** instead.

**`fetch_weather_forecast(lat, lon, past_days=5, days=4)`** fetches recent and future weather. The 5 past days cover the archive lag (it ends 2 days ago) plus some overlap.

**`fetch_cams_history(lat, lon, start, end)`** fetches CAMS PM2.5 history.
* The start is clipped to `2022-08-01`, where CAMS history begins.
* A failed year is skipped with a message rather than stopping the run.
* Returns an empty frame with the right columns if nothing came back.

**`fetch_cams_forecast(...)`** fetches recent and future CAMS PM2.5.
