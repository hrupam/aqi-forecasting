# Air Quality Forecasting & Early Warning System

PM2.5 forecasts for Indian cities, hour by hour, up to 60 hours ahead, with early warnings before the air turns unhealthy.

The system downloads real monitoring-station readings from **OpenAQ** and combines them with weather data and the CAMS air-quality model from **Open-Meteo**. It trains a machine-learning model for each city and shows the results in an interactive **Streamlit** dashboard. The dashboard tells you:

* when pollution will cross your safety threshold
* how likely that is
* why it is happening
* the best time to go outside

---

## Contents

1. [What it does](#1-what-it-does)
2. [What it adds beyond Google Weather and IQAir](#2-what-it-adds-beyond-google-weather-and-iqair)
3. [Requirements](#3-requirements)
4. [Getting started (step by step)](#4-getting-started-step-by-step)
5. [Everyday use](#5-everyday-use)
6. [Using the dashboard](#6-using-the-dashboard)
7. [Working with multiple cities](#7-working-with-multiple-cities)
8. [Automatic alerts (Telegram / e-mail)](#8-automatic-alerts-telegram--e-mail)
9. [Deploying online (free)](#9-deploying-online-free)
10. [How it works](#10-how-it-works)
11. [Results](#11-results)
12. [Project structure](#12-project-structure)
13. [Configuration reference](#13-configuration-reference)
14. [Troubleshooting](#14-troubleshooting)
15. [Limitations and ideas for extension](#15-limitations-and-ideas-for-extension)
16. [Data sources and licences](#16-data-sources-and-licences)

---

## 1. What it does

| Objective | How the project meets it |
|---|---|
| **1. Collect and combine data** | Automatically downloads historical hourly PM2.5 from the nearest reliable OpenAQ station. It adds weather (temperature, humidity, wind, rain, cloud, radiation, pressure, mixing height) and the CAMS model forecast from Open-Meteo. The data is cleaned and everything is merged onto one hourly timeline. |
| **2. Predict future air quality** | A gradient-boosting model learns how weather and recent pollution interact. It forecasts PM2.5 for every hour from 1 to 60 hours ahead, with an 80% uncertainty range and the probability of crossing any threshold. |
| **3. Early-warning dashboard** | A Streamlit dashboard shows a colour strip of the next 48 hours, alert levels (Clear / Watch / Warning / Emergency), daily AQI outlook, best outdoor time, the reasons behind the forecast, and the model's track record. A separate script can send alerts to Telegram or e-mail. |

---

## 2. What it adds beyond Google Weather and IQAir

Google Weather and IQAir already show an hourly air-quality forecast for almost any place. What they show is **one number per hour**. This project adds the layer you need to act on it:

| | Google Weather | IQAir | This project |
|---|---|---|---|
| Source and scale | Models + sensors on a ~500 m grid | Government monitors (in Indian cities, the same CPCB / state-board network), low-cost sensors, satellite; **US AQI** scale | The **nearest official monitor**, with ML correcting the model's local bias; **India's CPCB AQI**, the 24-h limit (60 µg/m³) and the WHO guideline (15 µg/m³) |
| Forecast | Hourly, up to 4 days | Hourly and daily, up to 7 days | Hourly PM2.5, 1–60 h, anchored to the latest reading |
| Uncertainty | One number per hour | One number per hour | **80 % range** for every hour, calibrated on past data |
| Probability | – | – | **Chance (%) of crossing your threshold**, every hour and per day |
| Early warning | Colour category | Alert when the air is bad | **Watch / Warning / Emergency ahead of time**, with start time, duration and peak |
| Personal thresholds | – | – | Asthma / heart / lung, children & elderly, outdoor work, WHO-strict, or your own value |
| Why will it be bad? | – | – | **Driver attribution**: wind, mixing height, rain, humidity, regional pollution, in µg/m³ |
| Track record | Not published | Accuracy claimed, no figures | **Published backtest** for every city: error by lead time, warnings caught and false alarms, reliability |
| Local analysis | – | City rankings, history | Hour × month heatmap, **pollution rose**, weekday effect, days above the limit |
| Open | Closed | Closed | Open data, open code, retrainable for any city |

Where they are stronger: every place on Earth, more stations and pollutants, a longer range and polished mobile apps.

---

## 3. Requirements

* **Python 3.10 or newer.** This was developed and tested on Python 3.12 on Windows.
* **Internet access.** OpenAQ and Open-Meteo are online services.
* **A free OpenAQ API key** for real station data. Open-Meteo needs no key.
* About 200 MB of disk space for the virtual environment, plus 5–10 MB per city for data.

You can try everything **without a key or internet** using demo mode (synthetic data).

---

## 4. Getting started (step by step)

All commands below are run in a terminal **inside the project folder**, for example `C:\Users\<you>\Documents\aqews\aqews`.

### Step 1: Create a Python virtual environment

A virtual environment keeps this project's packages separate from the rest of your computer.

**Windows (Command Prompt or PowerShell)**

1. Create the environment (only once):
   ```bat
   python -m venv .venv
   ```
2. Activate it (every time you open a new terminal):
   ```bat
   .venv\Scripts\activate
   ```
   Your prompt now starts with `(.venv)`.

   If PowerShell says *"running scripts is disabled on this system"*, run this once and try again:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install the requirements

With the environment activated:
```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```
This installs pandas, numpy, scikit-learn, requests, joblib, Streamlit and Plotly.

### Step 3: Add your OpenAQ API key

1. Sign up for free at <https://explore.openaq.org>. Your API key is under **Account → Settings**.
2. Create a file named `.env` in the project folder by copying the template:
   ```bat
   copy .env.example .env
   ```
   (On macOS/Linux: `cp .env.example .env`.)
3. Open `.env` and fill in the key:
   ```
   OPENAQ_API_KEY=your-key-here
   ```

`.env` is listed in `.gitignore`, so your key is never committed to Git.

### Step 4: Build the first forecast

**Real data for Kolkata (default city).** The first run downloads about 3 years of history and takes 5–10 minutes:
```bat
python pipeline.py all
```

**Another city:**
```bat
python pipeline.py all --city Delhi
```

**No key or no internet?** Run the offline demo instead:
```bat
python pipeline.py all --demo
```

`all` runs the three stages one after another:
1. **fetch**: downloads and cleans the data
2. **train**: trains the model and runs the backtest
3. **forecast**: issues a 60-hour forecast

### Step 5: Start the dashboard

```bat
streamlit run app.py
```

Your browser opens <http://localhost:8501>. Stop the app with `Ctrl + C` in the terminal.

### Next time

You only need to:
```bat
.venv\Scripts\activate
python pipeline.py update        # latest readings + fresh forecast (about 1 minute)
streamlit run app.py
```

---

## 5. Everyday use

| Command | What it does | When |
|---|---|---|
| `python pipeline.py update` | Downloads the latest readings and weather forecasts, then issues a new forecast | Before you look at the dashboard (or click **Refresh** in it) |
| `python pipeline.py update --all-cities` | The same for every city that has a model | Daily, or from a scheduled task |
| `python pipeline.py train` | Retrains the model on all data so far and refreshes the track record | Weekly or monthly |
| `python pipeline.py all --city X` | Full setup for a new city: download, train, forecast | Once per city |
| `python alert.py --city X` | Updates the forecast and sends a Telegram/e-mail alert if the level rises | Every 3 hours, from a scheduled task |
| `streamlit run app.py` | Starts the dashboard | Whenever you want to look |

Add `--demo` to any `pipeline.py` command to use synthetic data.

---

## 6. Using the dashboard

### Sidebar
* **View**: *City dashboard* or *Compare cities*.
* **Choose a city**: ✅ marks cities that have a trained model. Other cities open in *quick view*. Choose **Search for another place…** to find any town or locality worldwide.
* **Your alert**:
  * **Who are you planning for?** chooses a profile (general public, sensitive groups, children and elderly, outdoor workers and athletes, WHO-strict). Each profile sets a default threshold.
  * **Warn me when PM2.5 exceeds** fine-tunes that threshold.
  * **Outdoor activity length** sets how long a window to search for.
* **Station** chooses which monitoring station the city's forecast is trained on (see section 7).
* **Refresh data and forecast** has the same effect as `python pipeline.py update`.

### Header (cities with a model)
* The city, the station, and how long ago it last reported.
* The **AQI of the last 24 hours** as a large number in its CPCB colour.
* The **alert level** with a plain-language message, for example: *"PM2.5 likely above 60 µg/m³ from Sat 21:30 (in 30 h) for about 11 h. Peak ≈ 77 µg/m³ (80% range 53–97)… Chance of exceedance up to 80%."*
* A **48-hour colour strip**: each block is one hour, coloured by its forecast category. A white tick marks hours above your threshold.
* Four tiles: last reading, peak in the next 24 h, peak in 24–48 h, and tomorrow's 24-hour mean with the chance of breaching the national limit.

### Tabs
| Tab | Contents |
|---|---|
| **Forecast** | Measured PM2.5 for the last 4 days and the forecast with its 80% band, against CPCB colour bands. The CAMS line shows what weather apps would show. Below it, the hourly probability of exceeding your threshold. |
| **Plan your day** | Daily cards (24-h mean, category, × WHO guideline, cigarette equivalent, chance above the national limit), the cleanest daytime window for outdoor activity, an hour-by-hour table and a CSV download. |
| **Why** | How much each factor (wind, mixing height, rain, temperature/humidity, regional pollution) pushes the forecast above or below a typical day. Also a ventilation and rain chart, and the model's most important inputs. |
| **Track record** | Out-of-sample error by lead time compared with simple baselines and CAMS, warning hit rate and false alarms, a reliability diagram, and the last 30 days of test forecasts against measurements. |
| **Patterns** | Hour × month heatmap, pollution rose, days per month above the national limit, weekday effect, data-quality report. |
| **Compared with weather apps** | The comparison table from section 2. |

### Quick view (cities without a model)
* AQI now and tomorrow (from CAMS)
* The latest readings from up to 8 nearby monitors, on a map and in a table
* The CAMS 4-day outlook chart
* A daily AQI table with health advice
* A simple threshold warning
* **Build forecast for <city>**, which trains that city's model in the background in about 3–10 minutes, then switches the city to the full dashboard.

### Compare cities
A map, a ranking and a table with AQI now, AQI tomorrow and the 48-hour peak for every city. Cities with a model use the ML forecast; the others use CAMS.

---

## 7. Working with multiple cities

* **35 Indian cities are built in.** These include Kolkata, Delhi, Mumbai, Bengaluru, Chennai, Hyderabad, Pune, Lucknow, Kanpur, Patna, Howrah, Kharagpur and more (see `PRESET_CITIES` in `config.py`).
* **Any other place** can be added from the dashboard search, or from the terminal:
  ```bat
  python pipeline.py all --city "Shillong" --lat 25.578 --lon 91.893
  ```
  Added places are remembered in `data/cities.json`.
* **Choose the station from the dashboard.** The sidebar's **Station** list shows every PM2.5 monitor within 25 km, with its distance and whether it is still reporting. Low-cost sensors are marked.
  * For a city with a forecast, pick a station and click **Use this station**. The model is retrained on that station's readings in the background (about 3–10 minutes), and the current forecast stays visible until it finishes.
  * Choose **Automatic (best available)** to go back to the automatic choice.
  * In quick view, the station you pick is the one **Build forecast** will use.
* **Or choose it from the terminal.** Station IDs are listed in `data/<city>/raw/sensors.csv`:
  ```bat
  python pipeline.py all --city Kolkata --sensor 12235680     # pin this station
  python pipeline.py all --city Kolkata --auto-station        # back to automatic
  ```
  A pinned station is remembered in `data/cities.json`.
* **Each city has its own folders**: `data/<city>/`, `models/<city>/` and `reports/<city>/`.
* **Default city:** commands without `--city` use `AQ_CITY` from `.env`, or Kolkata if it isn't set.

### How the station is chosen
1. All PM2.5 monitors within 25 km of the city centre are listed. Active, reference-grade stations with long histories rank first.
2. OpenAQ often keeps an old sensor ID (long history) and a new one (current data) for the same CPCB station. **All sensors of a station are downloaded and joined** into one series; where both report the same hour, the newer sensor wins.
3. A station is accepted only if it has at least 30 days of readings and one within the last 14 days. Otherwise the next station is tried.
4. A city keeps the same station on later updates, so its history stays consistent.

---

## 8. Automatic alerts (Telegram / e-mail)

`alert.py` refreshes the forecast and sends a message when the alert level **rises**, for example from Clear to Warning. The same warning is not repeated within 12 hours.

```bat
python alert.py --city Kolkata                 # sensitive-group threshold (60 µg/m³)
python alert.py --city Delhi --threshold 90
```

**Telegram**
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Send your bot a message, then open `https://api.telegram.org/bot<token>/getUpdates` to find your `chat_id`.
3. Add both to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```

**E-mail (Gmail example)**: create an App Password in your Google account, then add:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_TO=you@gmail.com
```

**Run it every 3 hours on Windows**
1. Open **Task Scheduler → Create Task**.
2. On the **Triggers** tab, set Daily, repeat every 3 hours.
3. On the **Actions** tab:
   * Program: `C:\Users\<you>\Documents\aqews\aqews\.venv\Scripts\python.exe`
   * Arguments: `alert.py --city Kolkata`
   * Start in: `C:\Users\<you>\Documents\aqews\aqews`

On macOS/Linux, use cron: `0 */3 * * * cd /path/to/aqews && .venv/bin/python alert.py --city Kolkata`.

**Or let GitHub run it.** Once the project is on GitHub, the scheduled job in section 9 checks for alerts every 3 hours without your computer being on.

---

## 9. Deploying online (free)

The dashboard runs on **Streamlit Community Cloud**, and a **GitHub Actions** job keeps every city up to date. Both are free.

```
GitHub repo (code + data + models) ──► Streamlit Community Cloud ──► users
        ▲                                 (redeploys on every commit)
        └── GitHub Actions, every 3 h: update all cities, re-forecast, alert check, commit
```

### 9.1 Put the project on GitHub
`data/`, `models/` and `reports/` are committed on purpose (about 70 MB): the deployed app reads them, and nothing is trained on the server.
```bat
git add .
git commit -m "Final version"
git push
```
`requirements.txt` pins the exact package versions the models were trained with. If you retrain with newer packages, update the pins to match (`pip freeze`).

### 9.2 Deploy the dashboard
1. Go to <https://share.streamlit.io>, sign in with GitHub and choose **Create app**.
2. Pick the repository, branch `main`, main file `app.py`.
3. **Advanced settings**:
   * Python version: **3.12**
   * Secrets:
     ```toml
     OPENAQ_API_KEY = "your-key"
     ```
4. **Deploy**. `app.py` copies the secret into the environment, so the Refresh button and new-city builds work on the server too.

Things to know about the free tier:
* the app sleeps after 12 hours without visitors; opening the link wakes it
* files written on the server (a Refresh, a city built from the dashboard) are lost when the app restarts; the scheduled job below is what keeps the published data fresh
* building a new city on the server takes several minutes; for a city you want to keep, build it locally and push

### 9.3 Keep it fresh: the scheduled job
`.github/workflows/update.yml` runs every 3 hours. It:
1. runs `python pipeline.py update --all-cities`
2. runs `python alert.py --city Kolkata --no-refresh` (sends a Telegram message if the warning level rose)
3. commits the new files, which makes Streamlit redeploy

Add the secrets in GitHub under **Settings → Secrets and variables → Actions**:
* `OPENAQ_API_KEY` (required)
* `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional, for alerts; see section 8)

Start it once by hand from the **Actions** tab → **Update forecasts** → **Run workflow**.

Retrain from your own computer now and then (`python pipeline.py train --all-cities`) and push the result.

---

## 10. How it works

```
 OpenAQ station PM2.5 ──┐
 Open-Meteo weather ────┼─► quality control ─► hourly merge ─► features ─► quantile models ─┬─► forecast.csv
 CAMS model PM2.5 ──────┘   (dataset.py)         (dataset.py)   (features.py)  (model.py)     ├─► drivers.csv
                                                                                             ├─► backtest.json
                                                                                             └─► alert.py
                                       Streamlit dashboard (app.py) reads everything in reports/<city>/
```

### 10.1 Data collection (`aq/openaq.py`, `aq/openmeteo.py`)
* **OpenAQ v3**:
  * `/locations?coordinates=…&radius=…&parameters_id=2` finds the stations.
  * `/sensors/{id}/hours` gives hourly averages, downloaded in 120-day chunks with pagination and back-off on rate limits.
* **Open-Meteo historical-forecast API**: weather for training comes from *archived forecasts* rather than reanalysis, so the model learns from the same kind of input it will receive live. ERA5 is the fallback. If an endpoint doesn't offer a variable, it is dropped automatically.
* **Open-Meteo Air-Quality API**: CAMS PM2.5 history (from August 2022) and its 4-day forecast.
* Downloads are **incremental**: later runs only fetch what is new.

### 10.2 Quality control (`aq/dataset.py`)
* **Removed readings**:
  * values ≤ 0 or above 1000 µg/m³
  * hours with less than 50% coverage
  * stuck sensors (the same value for 6 or more hours)
  * isolated spikes (more than 4 times the 24-h median and above 250)
* **Gap filling**: gaps of up to 3 hours are interpolated; longer gaps stay empty.
* **Station outages**: if a station has stopped reporting for 6 hours to 14 days, the missing recent hours are **estimated from CAMS**, scaled by the station/CAMS ratio of the previous week. This lets forecasts still start from now. These estimates are never used for training, and the dashboard flags them.

### 10.3 Features (`aq/features.py`)
Each training example is a pair *(issue time T, lead time h)*. One model therefore covers the whole 1–60 h range without feeding its own errors back in.

* **Known at T**:
  * PM2.5 lags (1–48 h) and rolling means over 3, 6, 24 and 72 h
  * variability, 24-h max and min, recent trends
  * same clock hour on the last observed day
* **Expected at T+h**:
  * forecast weather: temperature, humidity, dew point, wind (as u/v components), gusts, pressure, rain, cloud, radiation, mixing height
  * **ventilation index** (wind × mixing height)
  * rain over the previous 6 and 24 h
  * 12-h mean wind and ventilation
  * 24-h pressure and temperature changes
* **Between T and T+h**: mean ventilation and total rain along the way, and how temperature, wind and ventilation change.
* **CAMS**: how much the regional model expects PM2.5 to change.
* **Calendar**: hour of day and weekday in local time.

### 10.4 Model (`aq/model.py`)
* **Algorithm**: scikit-learn `HistGradientBoostingRegressor` with **quantile loss**, three models for the 10th, 50th and 90th percentiles.
* **Target: the change from now**, log(1 + PM2.5 at T+h) − log(1 + PM2.5 at T), not the absolute level. Past-PM features are expressed relative to the current level too.
  * This keeps the forecast anchored to what the station measures today.
  * It matters because levels can shift between years. Kolkata in summer 2026 was about 35% cleaner than in summer 2025, and a model that predicted absolute levels kept forecasting 2025 values and lost to simple persistence.
* **Blending with persistence**: for each lead time, a weight between 0 and 1 is learned on held-out data. It decides how much of the predicted change to trust; at 1 hour the forecast stays close to the latest reading.
* **Calibrated uncertainty**: split-conformal scaling widens or narrows the 10–90% band for each lead time, so it really contains the measured value about 80% of the time.
* **Exceedance probability**: P(PM2.5 > threshold) comes from the calibrated quantiles, using a split-normal distribution in log space.

### 10.5 Evaluation
* The **last 25% of the timeline** is held out. No training target falls inside it.
* Alternate weeks of that period tune the blending and the band width. The other weeks are used for every reported score.
* **Baselines**:
  * *persistence* (the next hours equal the latest reading)
  * *same hour yesterday*
  * *raw CAMS* (what weather apps show)
* **Metrics**:
  * MAE by lead time, and band coverage
  * for warnings 24–48 h ahead at 60, 90 and 120 µg/m³: probability of detection (POD), false-alarm ratio (FAR), critical success index (CSI) and Brier score
  * a reliability diagram

### 10.6 Explanations
* **Global**: permutation importance of the inputs.
* **For each forecast**: each weather group's inputs are replaced with their typical value for that month and hour, and the model is re-run. The change in the forecast (µg/m³) shows how much that factor is pushing pollution up or down today.

### 10.7 AQI and categories (`aq/insights.py`)
* **India CPCB AQI** from 24-hour mean PM2.5 and PM10. The AQI is the higher of the two sub-indices.

| Category | AQI | PM2.5 (µg/m³) |
|---|---|---|
| Good | 0–50 | 0–30 |
| Satisfactory | 51–100 | 31–60 |
| Moderate | 101–200 | 61–90 |
| Poor | 201–300 | 91–120 |
| Very Poor | 301–400 | 121–250 |
| Severe | 401–500 | > 250 |

* **Alert levels**:
  * **Watch**: the chance of exceeding your threshold reaches 30% or more within 48 h
  * **Warning**: 60% or more
  * **Emergency**: the forecast peak is above 250 µg/m³
* **Cigarette equivalent**: 22 µg/m³ over 24 hours ≈ 1 cigarette (Berkeley Earth rule of thumb).

---

## 11. Results

Out-of-sample results for every city with a model, after retraining on 9 November 2026. Each city is tested on the last 25 % of its own timeline (forecasts the model never saw while training), which now includes this autumn's polluted weeks. MAE is the mean absolute error in µg/m³; lower is better. "vs" columns show how much smaller our error is than the baseline.

| City (station) | Test period | MAE 0–24 h | MAE 24–48 h | vs persistence (day 1 / 2) | vs CAMS (day 1 / 2) | 80 % range holds |
|---|---|---|---|---|---|---|
| **Ahmedabad** (IIMA Ventures) | 2026-08-19 → 2026-11-09 | 9.3 | 11.1 | 19% / 20% | 36% / 26% | 78% / 83% |
| **Amritsar** (Golden Temple, Amritsar - PPCB) | 2026-06-09 → 2026-11-09 | 5.5 | 6.9 | 3% / 8% | 80% / 77% | 85% / 88% |
| **Delhi** (Anand Vihar, New Delhi - DPCC) | 2026-06-02 → 2026-11-09 | 23.5 | 25.9 | 24% / 27% | 31% / 26% | 81% / 80% |
| **Gurugram** (R K Puram, Delhi - DPCC) | 2026-06-03 → 2026-11-09 | 21.0 | 23.3 | 26% / 25% | 60% / 55% | 76% / 78% |
| **Jaipur** (Police Commissionerate, Jaipur - RSPCB) | 2026-06-06 → 2026-11-09 | 8.7 | 10.9 | 14% / 15% | 52% / 38% | 82% / 82% |
| **Kanpur** (Nehru Nagar, Kanpur - UPPCB) | 2026-06-04 → 2026-11-09 | 12.0 | 13.6 | 26% / 25% | 46% / 35% | 80% / 81% |
| **Kolkata** (Padmapukur, Howrah - WBPCB) | 2026-05-26 → 2026-11-09 | 5.4 | 7.0 | 15% / 16% | 62% / 53% | 83% / 83% |
| **Siliguri** (Ward-32 Bapupara, Siliguri - WBPCB) | 2026-05-30 → 2026-11-09 | 3.2 | 4.0 | 35% / 34% | 76% / 69% | 85% / 86% |

* **Persistence** ("same as the latest reading") is the standard baseline for short-range forecasts. The model beats it in every city; the gain is smallest where pollution changed little during the test months (Amritsar).
* **CAMS** is the global model behind many weather apps. The model is 31–80 % more accurate on day 1, because it is anchored to the local station.
* The **80 % range** contains the measured value 77–88 % of the time, so the uncertainty and the probabilities can be trusted.
* **Warnings** at 60 µg/m³, 24–48 h ahead: where polluted hours were common (Delhi, Gurugram, Amritsar, Jaipur, Kanpur, Kolkata) the system warned about 34–70 % of them, with 25–38 % false alarms. Ahmedabad and Siliguri had few, short polluted spells and score poorly; they need more winter data.

Refresh this table after retraining: `python tools/summarize_results.py --markdown`. Each city's details are in the dashboard's **Track record** tab.

> Scores from `--demo` runs come from synthetic data and must not be reported as results.

---

## 12. Project structure

```
aqews/
├── app.py                  Streamlit dashboard (city picker, quick view, compare, full dashboard)
├── pipeline.py             Command line: fetch | train | forecast | update | all  (--city, --demo, ...)
├── alert.py                Scheduled Telegram / e-mail notifier
├── tools/summarize_results.py  Collects every city's backtest into reports/summary_all_cities.json
├── .github/workflows/update.yml  Scheduled job: update all cities + alert check every 3 h
├── config.py               Cities, folders, thresholds, model settings
├── requirements.txt        Python packages
├── .env.example            Template for your API key and alert settings (copy to .env)
├── .streamlit/config.toml  Dashboard colour theme
├── aq/
│   ├── openaq.py           OpenAQ v3 client (stations, hourly PM2.5)
│   ├── openmeteo.py        Weather + CAMS client
│   ├── dataset.py          Quality control, hourly merge, outage bridging
│   ├── features.py         (issue time, lead time) feature builder
│   ├── model.py            Training, blending, calibration, backtest, forecast, driver attribution
│   ├── insights.py         AQI, alert levels, daily outlook, best windows, explanations
│   ├── live.py             City search, nearby stations, CAMS for quick view and compare
│   ├── ui.py               Dashboard styling: fonts, colours, chart template, header strip
│   └── demo.py             Synthetic offline data
├── data/<city>/raw/        Downloaded station, weather and CAMS data
├── data/<city>/processed/  Merged hourly table (hourly.csv) and metadata (meta.json)
├── data/cities.json        Places you added through search or --lat/--lon
├── models/<city>/          Trained model (pm25_quantile_gbm.joblib)
└── reports/<city>/         forecast.csv, drivers.csv, backtest.json, backtest_predictions.csv
```

`.venv/` and `.env` are excluded from Git. `data/`, `models/` and `reports/` are committed so the deployed app can read them.

---

## 13. Configuration reference

### `.env` (create it from `.env.example`)
| Variable | Purpose |
|---|---|
| `OPENAQ_API_KEY` | **Required** for real data |
| `AQ_CITY` | Default city for commands without `--city` (default: Kolkata) |
| `AQ_SENSOR_ID` | Force a sensor for the default city (or use `--sensor`) |
| `AQ_TRAIN_START` | First date of history to download (default: 2023-01-01) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram alerts |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` | E-mail alerts |

### `config.py`
| Setting | Default | Meaning |
|---|---|---|
| `PRESET_CITIES` | 35 Indian cities | Cities in the dropdown |
| `SEARCH_RADIUS_M` | 25 000 | Station search radius (the OpenAQ maximum) |
| `MAX_HORIZON` | 60 | Forecast length in hours (48 h plus slack for reporting delays) |
| `QUANTILES` | 0.1, 0.5, 0.9 | Forecast percentiles |
| `ISSUE_STRIDE` | 3 | Use every 3rd hour as a training issue time |
| `TEST_FRACTION` | 0.25 | Share of the timeline held out for the backtest |
| `CATEGORIES` | CPCB bands | Category limits and colours |
| `NAAQS_24H`, `WHO_24H` | 60, 15 | 24-hour standards (µg/m³) |
| `PROFILES` | 5 profiles | Default alert threshold for each user profile |

---

## 14. Troubleshooting

| Problem | Fix |
|---|---|
| `OPENAQ_API_KEY is not set` | Create `.env` with your key (step 3). |
| PowerShell: *running scripts is disabled* | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again. |
| `'streamlit' is not recognized` | The virtual environment is not active. Run `.venv\Scripts\activate` first. |
| Warning *"The station has not reported for N h"* | The OpenAQ feed for that station is delayed or down; CPCB feeds sometimes stop for days. Outages under 14 days are bridged with CAMS automatically. Click **Refresh** later, or pick a station marked "reporting" in the sidebar's **Station** list. |
| *"None of the nearby OpenAQ stations returned PM2.5 data"* | The feed is down for the whole area, or the place has no monitors. Try again later; quick view still works with CAMS. |
| *"Model file is from an older version"* | Run `python pipeline.py train --city <city>` once. |
| **Build forecast** fails in quick view | The last lines of the log are shown on the page (full log in `reports/<city>/build.log`). Run `python pipeline.py all --city "<city>"` in the terminal to see the whole output. |
| Console: *Please replace `use_container_width` with `width`* | Upgrade Streamlit: `pip install -U streamlit`. |
| HTTP 429 from OpenAQ | Rate limit reached. The client waits and retries; if it keeps failing, wait a minute and run again. |
| Fonts look plain | The custom fonts load from Google Fonts. Without internet the app uses system fonts, which works the same. |

---

## 15. Limitations and ideas for extension

**Limitations**
* Weather inputs at forecast time are themselves forecasts, so errors grow beyond about 48 h.
* Sudden local events (firecrackers, nearby fires, dust storms) can't be predicted from weather alone. The probabilities reflect this uncertainty, and the trend features pick up a build-up once it has started.
* A city's forecast represents **one station**, not the whole city.
* The daily outlook averages hourly quantiles, which gives a slightly wide, conservative daily range.
* Warning scores need a polluted season (winter) in the test period to be meaningful.

**Ideas**
* Use several stations, or a spatial model, for a city-wide pollution map.
* Add fire hotspots (NASA FIRMS) for the stubble-burning season, and festival-calendar features.
* Compare with LightGBM/XGBoost, LSTM or Temporal Fusion Transformer models.
* Add SHAP explanations for each individual forecast.
* Forecast more pollutants (PM10, NO₂, O₃) to give a complete CPCB AQI.

---

## 16. Data sources and licences

* **OpenAQ**: <https://openaq.org>, CC BY 4.0 (individual providers' licences apply; Indian data comes from CPCB and state pollution control boards)
* **Open-Meteo** weather, air-quality and geocoding APIs: <https://open-meteo.com>, CC BY 4.0
* **CAMS**, the Copernicus Atmosphere Monitoring Service, delivered through Open-Meteo
* **Place names**: GeoNames, through the Open-Meteo geocoding API
* **AQI method**: Central Pollution Control Board (CPCB), National Air Quality Index
