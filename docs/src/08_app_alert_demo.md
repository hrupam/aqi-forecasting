
---

## 15. `app.py`: the Streamlit dashboard

### 15.1 How Streamlit runs this file
Streamlit re-executes `app.py` from top to bottom **every time the user interacts**: picking a city, moving a slider, clicking a button. Three mechanisms make this work:
* **`st.session_state`** is a dictionary that survives reruns. It holds the selected city, pending selections and background build processes.
* **`@st.cache_data`** caches function results by their arguments, so expensive work (reading CSVs, API calls) is not repeated. Parameters whose names start with `_` are *not* part of the cache key.
* **`st.rerun()`** restarts the script immediately, for example after adding a place.

### 15.2 Page set-up and cached loaders
* `st.set_page_config(layout="wide")`, then `ui.inject()` (CSS and chart template).
* **`_mtime(path)`** returns a file's modification time, or 0 if it is missing.
* **`load_all(city, _stamp)`** reads `hourly.csv`, `meta.json`, `forecast.csv`, `drivers.csv`, `backtest.json` and `backtest_predictions.csv`. The cache key is the city name; the sum of the files' modification times is passed as `_stamp`, and the cache is cleared after every refresh or build.
* **`geocode_cached`** (24 h), **`cams_cached`**, **`stations_cached`** and **`cams_many_cached`** (30 min each) wrap the live API calls. The time-to-live values balance freshness against API load.

### 15.3 Sidebar: city and alert settings
* **View radio:** *City dashboard* or *Compare cities*.
* **City list:** ✅ cities first, then the others alphabetically, then "Search for another place…".
* **Pending-city pattern:**
  * Streamlit forbids changing a widget's value after that widget has been drawn in the same run. This caused the `StreamlitWidgetAlreadyInstantiatedError` you saw.
  * So "Add this place" stores `pending_city` and reruns.
  * At the top of the next run, *before* the selectbox is drawn, `pending_city` is moved into the selectbox's key `city_select`.
* **Search flow:**
  1. Text input → `geocode_cached` → radio list of matches → **Add this place**.
  2. If the name already exists for a different place (more than 0.1° away), the full label is used as the name.
  3. `config.register_city` saves the place.
* **"Your alert":** a profile selectbox (default: Sensitive), a threshold slider (15–250, default from the profile), and the outdoor-window length.

### 15.4 Helper functions
* **`band_chart` / `add_category_bands`** draw light horizontal bands for the CPCB categories behind a chart, with labels.
* **`aqi_badge`** is an older coloured AQI badge, kept as a utility.
* **`start_build(city, extra)`** runs `python -u pipeline.py all --city X …` with `subprocess.Popen`:
  * `-u` means unbuffered output, so the log updates live
  * stdout and stderr go to `reports/<city>/build.log`
  * `PYTHONIOENCODING=utf-8` stops Windows encoding errors on "µ" and "≈"
  * the process handle is stored in `session_state["builds"][city]`
* **`build_running(city)`** checks whether that process is still alive (`poll() is None`).
* **`build_status(city, text)`**:
  * running → info box, last 12 log lines, and a "Check progress" button (which triggers a rerun)
  * finished successfully → clear all caches and rerun, so the city switches to the full dashboard
  * failed → show the last 25 log lines
* **`stations_list(city, lat, lon, _stamp)`** returns one row per station: name, provider, monitor flag, distance, last report, representative sensor and all sensor IDs. It uses the saved `sensors.csv` if present, otherwise it asks OpenAQ. Dates are parsed with `format="mixed"` for robustness. Cached for 6 h.
* **`station_picker(city, current_loc, forced)`** is the sidebar **Station** selectbox.
  * Options: "Automatic (best available)" plus every station.
  * Labels show distance and status: "reporting", "silent N days" or "no data", and "low-cost sensor" for non-reference monitors.
  * The default is the pinned station if one is pinned, otherwise Automatic.
  * Returns the chosen sensor ID (or None for automatic) and whether the choice differs from the current one.

### 15.5 `render_compare()`: the Compare cities view
1. One `cams_many_cached` call for every city.
2. For each city:
   * **AQI now:** 24-h means of PM2.5 and PM10 over the last 24 h
   * **PM2.5 now**
   * **Peak in the next 48 h**
   * **AQI tomorrow:** the local date in the city's own time zone
3. For ✅ cities, the 48-h peak and tomorrow's PM2.5 come from **our forecast** (combined with CAMS PM10 for the AQI). The source is labelled.
4. **Output:**
   * tiles for most polluted, cleanest, and the number of cities Poor or worse tomorrow
   * a Plotly **`Scattergeo`** map (marker size and colour by AQI) and a ranked bar chart of the top 20
   * the full table

### 15.6 `render_quick(city)`: cities without a model
1. Gets CAMS (3 past days + 4 ahead) and, with a key, the nearby station readings. Readings within the last 6 h count as current.
2. **AQI now and tomorrow** from CAMS 24-h means.
3. **A simple CAMS warning:** WATCH if CAMS PM2.5 exceeds the threshold within 48 h. It is deliberately labelled as uncalibrated.
4. The **same header** (`ui.hero`) and tiles: median of the monitors now, AQI tomorrow, peak in 48 h.
5. **Chart:** CAMS PM2.5 (PM10 hidden in the legend), the latest station readings as diamonds, the threshold line, the "now" line and category bands.
6. **Daily table:** AQI, category and advice for each day.
7. **Station map and table** (`st.map` with category colours).
8. **Build the forecast:**
   * the sidebar station picker
   * then `build_status` while a build runs
   * otherwise a **Build forecast** button that passes `--sensor id` or `--auto-station`

### 15.7 Routing
```
Compare cities         → render_compare(); stop
Search…                → instructions; stop
config.set_city(choice)
no model for the city  → render_quick(choice); stop
else                   → full dashboard (below)
```
`st.stop()` ends the script run early, so only one view is drawn.

### 15.8 The full dashboard
**Sidebar, station section:**
* demo data → a note only
* real data → the station picker:
  * if the choice changed and no build is running, a **Use this station** button starts a retrain (`--sensor id` or `--auto-station`)
  * a line shows the station in use
* **Refresh data and forecast** runs `pipeline.py update --city X` synchronously with a spinner, then clears the cache and reruns. On failure it shows the error output.

**Header:**
1. `build_status` (shown if a station switch is running).
2. A demo-mode notice, if relevant.
3. **Calculations:**
   * `last_obs_t` and `last_obs` from the real readings
   * `lag_h`: how stale they are
   * `alert = alert_summary(...)`, `up = upcoming(...)`, `daily = daily_outlook(...)`
   * **AQI now** = sub-index of the mean of the **last 24 available hours** (bridge estimates included if the station is offline)
4. `ui.hero(...)` with the 48-hour strip from the forecast median.
5. **Warnings:**
   * bridged outage → "estimated from CAMS × ratio"
   * stale data (more than 12 h) → a warning
   * a forecast entirely in the past → an error with the fix
6. **Four tiles:** last reading; peak in the next 24 h; peak in 24–48 h; tomorrow's 24-h mean with the chance of breaching the national limit.

**Tabs:**

| Tab | Content and how it's built |
|---|---|
| **Forecast** | Measured PM2.5 for the last 96 h (solid), bridge estimates (dotted), the forecast median (blue) with the q10–q90 band (`fill="tonexty"` between two traces), CAMS (grey dotted), the threshold line, a "now" line and category bands. Below: an hourly **exceedance-probability bar chart** (red ≥ 60 %, amber ≥ 30 %) |
| **Plan your day** | Day cards from `daily_outlook`; the **best outdoor window** per day from `best_windows`, with how much cleaner it is than the worst slot; an hour-by-hour table; **CSV download** (`st.download_button`) |
| **Why** | Grouped horizontal bars of the driver effects (next 24 h vs 24–48 h) plus plain sentences; a **ventilation-index** line with the stagnant zone (< 2,000 m²/s) shaded and rain bars on a second axis; the top 12 **permutation importances** with a key to the prefixes |
| **Track record** | Error tiles (0–24 h, 24–48 h, skill against persistence and CAMS, band coverage); **MAE by lead time** for the model and the three baselines; warning verification table (POD, FAR, CSI, Brier); **reliability diagram** (marker size ∝ √n); last 30 days of test forecasts against measurements, for a selectable lead time |
| **Patterns** | **Heatmap** of mean PM2.5 by local hour × month; **pollution rose**: wind direction binned into 8 sectors with `((dir + 22.5) // 45) % 8`, mean PM2.5 per sector on a `Barpolar` chart, showing where dirty air comes from; days per month with a 24-h mean above 60; **weekday effect**; the data-quality JSON |
| **Compared with weather apps** | The gap table (section 2.4) |

---

## 16. `alert.py`: scheduled notifications

* **`RANK`** orders the levels: CLEAR 0 < WATCH 1 < WARNING 2 < EMERGENCY 3 (Unknown is −1).
* **`send_telegram(text)`** posts to `https://api.telegram.org/bot<token>/sendMessage` with `chat_id`. It returns False if the channel isn't configured.
* **`send_email(subject, text)`** sends over SMTP with STARTTLS (port 587 by default), logging in with `SMTP_USER`/`SMTP_PASSWORD`. A Gmail App Password works. It returns False if the channel isn't configured.
* **`main()`**:
  1. Arguments: `--threshold` (default 60), `--no-refresh`, `--demo`, `--city`.
  2. Activates the city. Unless `--no-refresh`, runs `fetch(history=False)` and `run_forecast()`.
  3. `alert_summary(fc, threshold)`, then compares with the saved state in `reports/<city>/alert_state.json`:
     * **escalated** (level rank went up) → send
     * **repeat due** (level is Warning or above and the last message was more than 12 h ago) → send again
     * **de-escalated** → update the state silently
  4. The message is `[City PM2.5] LEVEL: message`, plus the health advice for the peak category.
  5. Prints which channels were used ("console only" if none).

This avoids **alert fatigue**: users get a message when things get worse, not every 3 hours.

---

## 17. `aq/demo.py`: synthetic data for offline demos

**`_ar1(n, phi, sigma, rng)`** generates an AR(1) noise process, $x_t = \phi x_{t-1} + \varepsilon_t$. This is realistic "weather-like" persistence: random, but correlated over time.

**`make_demo(start, end=None, seed=7)`** builds a physically motivated world from the start date to now + 4 days, with a fixed random seed.

**Seasonality:**
* `winter = cos(2π(doy − 15)/365.25)`, which is +1 in mid-January and −1 in mid-July
* a monsoon flag for June–September
* a daylight curve from 07:00 to 18:00 local time

**Weather:**
* temperature, humidity, dew point
* wind (stronger by day and in the monsoon)
* wind direction (north-west in winter, south-west in the monsoon)
* rain (Poisson-like events, frequent in the monsoon)
* cloud, radiation
* mixing height (deep on sunny days, shallow at night and in winter)
* pressure

**A stagnation spell is planted 16–64 h after now:** wind and mixing height are cut, rain is removed, the wind turns north-west, and local burning increases. This gives the demo something to warn about.

**PM2.5 dynamics:**

$$\text{target} = 38 \cdot \text{season} \cdot \text{traffic} \cdot \text{ventilation factor} \cdot \text{transport} \cdot \text{episode} \cdot e^{\text{noise}}$$

| Factor | Definition |
|---|---|
| Traffic | Morning and evening peaks (Gaussian bumps at 09:30 and 21:00) and a Sunday dip |
| Ventilation factor | (median ventilation ÷ ventilation)^0.35: low ventilation means more pollution |
| Transport | +25 % when winter winds come from the north-west |
| Episodes | Random 1–4-day burning episodes from October to February |

**Then:**
* **Smoothing:** `pm[t] = (0.82·pm[t−1] + 0.18·target[t]) · (1 − washout)`, so pollution builds and decays gradually, and rain removes up to 50 %.
* **CAMS-like series:** the truth smoothed, lagged 4 h, biased low and noisy, plus 6. This imitates a coarse model.
* **Station:** reports up to 2 h ago, with about 3 % random gaps.

> Demo scores are optimistic, because the data obey the model's assumptions exactly. **Never report demo results.**
