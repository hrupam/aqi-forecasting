# Air Quality Forecasting & Early Warning System (PM2.5)

This project forecasts PM2.5 hour by hour, 1 to 60 hours ahead, for the monitoring station nearest your city. It also tells you when pollution is about to cross a safe threshold. It combines:

* **OpenAQ**: ground-truth hourly PM2.5 from real monitors (CPCB / AirNow / others)
* **Open-Meteo**: archived and forecast weather (temperature, humidity, wind, rain, cloud, radiation, pressure, **boundary-layer / mixing height**)
* **CAMS** (via the Open-Meteo Air-Quality API): the global chemistry-transport model that most weather apps display. It's used both as a model input and as the benchmark to beat.

```
OpenAQ ─┐                               ┌─> forecast.csv (q10 / q50 / q90, 1-60 h)
Open-Meteo weather ─┼─> QC + hourly merge ─> features ─> quantile GBM ┼─> drivers.csv (why)
CAMS PM2.5 ─────────┘                               │                 └─> alert.py (Telegram / e-mail)
                                                    └─> backtest.json (track record)
                                         Streamlit dashboard (app.py) reads all of it
```

## Quick start

```bash
pip install -r requirements.txt

# 1) Try it offline right away (synthetic data, about 5 minutes including training)
python pipeline.py all --demo
streamlit run app.py

# 2) Real data
cp .env.example .env          # put your free OpenAQ key in OPENAQ_API_KEY
python pipeline.py all        # download history (first run takes several minutes), train, forecast
streamlit run app.py
```

Day-to-day use:

| Command | What it does |
|---|---|
| `python pipeline.py update` | Fetches the latest readings and weather/CAMS forecasts, then issues a new forecast (fast). Add `--city X` or `--all-cities` |
| `python pipeline.py train` | Retrains the model and backtest (do this weekly or monthly) |
| `python alert.py` | Runs `update` and sends Telegram or e-mail when the alert level rises. Schedule it every 3 h |
| 🔄 button in the dashboard | Same as `update` |

### Multiple cities
* **In the dashboard**: pick any city from the **📍 City** dropdown. The list has 35 Indian cities, and **🔎 Search any city…** finds any town in the world through Open-Meteo geocoding.
  * Cities marked ✅ have the full ML forecast.
  * Any other city opens instantly in **quick view**. This shows:
    * the CPCB AQI (from 24-h PM2.5/PM10)
    * the latest readings from the nearest OpenAQ monitors, with a map
    * the CAMS 4-day outlook
    * a daily AQI table
    * a simple threshold warning
  * Click **🚀 Build forecast** in quick view to train that city's model in the background.
* **Compare cities** view: a map, ranking and table of AQI now and tomorrow for every city.
* **From the terminal**:
  ```bash
  python pipeline.py all --city Delhi
  python pipeline.py all --city "Shillong" --lat 25.578 --lon 91.893   # any place
  python pipeline.py all --city Kolkata --sensor 12235680               # choose the station
  python pipeline.py update --all-cities                              # refresh every ✅ city
  python alert.py --city Delhi
  ```
* Each city keeps its own files in `data/<city>/`, `models/<city>/` and `reports/<city>/`. Searched cities are remembered in `data/cities.json`. Projects from before this change are moved into `data/kolkata/` automatically.

The default city for commands without `--city` is `AQ_CITY` in `.env` (Kolkata if unset). The pipeline automatically ranks nearby PM2.5 sensors (active, reference-grade, longest history) and saves the list to `data/raw/sensors.csv`. You can force a particular sensor with `AQ_SENSOR_ID`.

## Objectives → implementation

### 1. Collect and combine data (`aq/openaq.py`, `aq/openmeteo.py`, `aq/dataset.py`)
* OpenAQ v3: `/locations?coordinates=…&radius=…&parameters_id=2` finds the stations, and `/sensors/{id}/hours` gives the hourly averages. Downloads are chunked and paginated, and they back off when the API rate-limits.
* Open-Meteo **historical-forecast API**: training uses archived *forecasts*, not reanalysis. This means the model learns from the same kind of input it will see live (ERA5 is the fallback). If an endpoint doesn't offer a variable, the code drops it and retries.
* Quality control removes:
  * out-of-range values
  * hours with low coverage
  * stuck sensors (the same value for 6 h or more)
  * isolated spikes

  Gaps of 3 h or less are interpolated. The QC report appears in the dashboard.
* Everything is aligned on one hourly UTC grid in `data/processed/hourly.csv`.

### 2. Predict future air quality (`aq/features.py`, `aq/model.py`)
* **Direct multi-horizon design**: each sample is (issue time *T*, lead time *h*). One model therefore produces the whole 1–60 h curve, with no recursive error build-up.
* **Features** (54 in total):
  * PM2.5 lags (1–48 h), rolling statistics and trends
  * weather at the target hour, with wind as u/v components
  * **ventilation index** = wind × mixing height
  * rain over 6 h and 24 h
  * mean ventilation and rain *between now and the target hour*
  * changes in weather between now and then
  * CAMS PM2.5, plus CAMS corrected by the current local bias
  * hour of day, weekday and season in IST
  * same clock hour on the last observed day
* **Model**: scikit-learn `HistGradientBoostingRegressor` with quantile loss at 10/50/90 %. It predicts the *change* from the latest reading, log(1+PM2.5 at T+h) − log(1+PM2.5 now), rather than the absolute level.
  * Past-PM features are expressed relative to the current level, and CAMS enters only as its forecast change.
  * This keeps the forecast anchored to what the station measures today. It matters because a station's level can shift between years (for example, Kolkata in summer 2026 was about 35 % cleaner than in summer 2025). An absolute-level model trained on 2025 kept forecasting 2025 levels and lost to persistence.
* **Blending**: for each lead time, an out-of-sample weight decides how much of the model's predicted change to trust (0 = "same as now"). The data chooses this weight, so very short horizons lean on the latest reading and longer ones lean on the model.
* **Calibrated uncertainty**: split-conformal scaling makes the 80 % band contain the truth about 80 % of the time. Alternate weeks of the test period are used for calibration; the other weeks are used for scoring.
* **Exceedance probability**: P(PM2.5 > threshold) comes from the calibrated quantiles, using a split-normal distribution in log space.
* **Honest backtest**: the last 25 % of the timeline is held out. Training targets never enter the test period. The model is compared against:
  * persistence
  * same-hour-yesterday
  * raw CAMS

  Reported metrics: MAE per lead time; alert POD / FAR / CSI / Brier score for 60, 90 and 120 µg/m³; and a reliability diagram.
* **Explanations**: global permutation importance, plus *per-forecast driver attribution*. For each weather group (wind, mixing height, rain, temperature/humidity/pressure, regional CAMS), its inputs are replaced with typical values for that month and hour and the model is re-run. The difference, in µg/m³, is how much that factor is pushing today's forecast up or down.

### 3. Early-warning dashboard (`app.py`, `aq/insights.py`, `alert.py`)
* **Alert banner** with four levels: CLEAR / WATCH (≥30 % chance) / WARNING (≥60 %) / EMERGENCY (peak above 250). It shows the start time, lead time, duration, peak value with its range, and health advice.
* **User profiles**: general public, sensitive, children & elderly, athletes, or strict WHO-based. You can also set a custom threshold.
* **Tabs**:
  * **Forecast**: chart with bands and CPCB colour categories, with CAMS for comparison
  * **Plan your day**: daily 24-h mean compared with the NAAQS, ×WHO, cigarette equivalent, the best outdoor window, and an hourly table with CSV download
  * **Why?**: driver bars, ventilation and rain chart, feature importance
  * **Track record**: backtest results
  * **Insights**: hour × month heatmap, pollution rose, weekday effect, days per month above the standard, QC report
  * **vs weather apps**: comparison table

## What it adds beyond Google Weather

| Gap in typical weather apps | This project |
|---|---|
| The AQI comes from a coarse model grid (CAMS ~10–45 km), not your nearest monitor | ML forecast anchored to a **real station**, which learns and corrects the local CAMS bias |
| One number, no uncertainty | **80 % range** and the **probability of exceeding** your threshold |
| No advance warning | **Watch / Warning / Emergency, issued up to 48 h ahead**, with start time and duration |
| One scale for everyone | **Personal thresholds** (asthma, children/elderly, athletes, WHO-strict) |
| US-style AQI | **Indian CPCB categories, 24-h NAAQS (60 µg/m³) and the WHO guideline (15)** |
| No reason given | **Driver attribution**: stagnant wind, low mixing height, no rain, regional transport |
| No planning help | **Best outdoor time window** each day |
| Abstract index | **Cigarette-equivalent** dose and ×WHO |
| Accuracy never shown | A public **track record**: error by lead time, hit and false-alarm rates, reliability |
| No local analytics | Seasonal/diurnal heatmap, **pollution rose** (source direction), weekday effect |
| Notifications you can't control | `alert.py`: Telegram/e-mail alerts on your own schedule, with no duplicate messages |

## Project layout
```
config.py        city, paths, thresholds, model settings
pipeline.py      fetch | train | forecast | update | all   (+ --demo)
app.py           Streamlit dashboard
alert.py         scheduled notifier
aq/openaq.py     OpenAQ v3 client
aq/openmeteo.py  weather + CAMS client
aq/dataset.py    QC and hourly merge
aq/features.py   (issue time, horizon) feature builder
aq/model.py      training, calibration, backtest, forecast, driver attribution
aq/insights.py   alerts, daily outlook, best windows, explanations
aq/demo.py       synthetic offline data
```

## Notes and limitations
* **Demo scores are not real results.** The synthetic data is generated from the weather by construction, so its accuracy is optimistic. Report the scores from a run on real data.
* At forecast time the weather inputs are forecasts. Training also uses archived forecasts, which keeps the two consistent. Their errors grow after about 48 h.
* Indian station feeds on OpenAQ can lag by several hours. The model forecasts up to 60 h from the last reading, and the dashboard warns you when that reading is old.
* Sudden local events, such as firecrackers or nearby fires, can't be predicted from the weather alone. The band and probabilities reflect this uncertainty, and `p_trend` features catch a build-up once it has started.
* The daily outlook averages the hourly quantiles. This gives a slightly wide, conservative daily range.

## Ideas to extend (for the report or viva)
* Use several stations, or a spatial model for a city-wide map.
* Add fire hotspots (NASA FIRMS) for stubble-burning season, and festival calendar flags.
* Compare with LSTM / Temporal Fusion Transformer models, and with LightGBM / XGBoost.
* Add SHAP values for each individual forecast.
* Add more pollutants (PM10, NO₂, O₃) and compute a full CPCB AQI.

Data: OpenAQ (CC BY 4.0, per-provider licences), Open-Meteo (CC BY 4.0), Copernicus CAMS.
