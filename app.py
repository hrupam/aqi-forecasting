"""
Air Quality Early Warning dashboard.     Run:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# On Streamlit Community Cloud the OpenAQ key lives in the app's Secrets, not in .env.
# Copy it into the environment before config reads it, so this app and every pipeline
# run it starts (Refresh, building a new city) can use it.
try:
    if "OPENAQ_API_KEY" in st.secrets:
        os.environ.setdefault("OPENAQ_API_KEY", str(st.secrets["OPENAQ_API_KEY"]).strip())
except Exception:                       # no secrets file (normal when running locally)
    pass

import config
from aq import insights as I, live, ui
from aq.model import exceed_prob

st.set_page_config(page_title="Air Quality Early Warning", page_icon="🌫️", layout="wide")
ui.inject()



# ------------------------------------------------------------------ cached loaders
def _mtime(p):
    return p.stat().st_mtime if p.exists() else 0


@st.cache_data
def load_all(city, _stamp):
    hourly = pd.read_csv(config.PROC_DIR / "hourly.csv", parse_dates=["time"]).set_index("time")
    hourly.index = pd.to_datetime(hourly.index, utc=True)
    meta = json.loads((config.PROC_DIR / "meta.json").read_text())
    fc = I.localize(pd.read_csv(config.REPORT_DIR / "forecast.csv"))
    drivers = pd.read_csv(config.REPORT_DIR / "drivers.csv")
    bt_file = config.REPORT_DIR / "backtest.json"
    backtest = json.loads(bt_file.read_text()) if bt_file.exists() else None
    btp_file = config.REPORT_DIR / "backtest_predictions.csv"
    btp = pd.read_csv(btp_file, parse_dates=["issue_time", "target_time"]) if btp_file.exists() else None
    return hourly, meta, fc, drivers, backtest, btp


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def geocode_cached(q):
    return live.geocode(q)


@st.cache_data(ttl=1800, show_spinner="Getting the CAMS air-quality outlook ...")
def cams_cached(lat, lon):
    return live.cams_outlook(lat, lon)


@st.cache_data(ttl=1800, show_spinner="Reading the nearest monitoring stations (OpenAQ) ...")
def stations_cached(lat, lon):
    return live.nearby_latest(lat, lon)


@st.cache_data(ttl=1800, show_spinner="Getting the outlook for all cities ...")
def cams_many_cached(city_tuple):
    return live.cams_many({n: {"lat": la, "lon": lo} for n, la, lo in city_tuple})


now = pd.Timestamp.now(tz="UTC")
SEARCH = "Search for another place…"

# ------------------------------------------------------------------ sidebar: city + settings
with st.sidebar:
    st.markdown(ui.brand(), unsafe_allow_html=True)
    st.header("City")
    view = st.radio("View", ["City dashboard", "Compare cities"], horizontal=True, label_visibility="collapsed")
    all_c = config.all_cities()
    ready = config.cities_with_forecast()
    ordered = ready + sorted(c for c in all_c if c not in ready)
    if "pending_city" in st.session_state:           # set by "Add this place" before the rerun
        st.session_state["city_select"] = st.session_state.pop("pending_city")
    if st.session_state.get("city_select") not in ordered + [SEARCH]:
        default = os.environ.get("AQ_CITY", "Kolkata")
        st.session_state["city_select"] = ready[0] if ready else (default if default in ordered else ordered[0])
    choice = st.selectbox("Choose a city", ordered + [SEARCH], key="city_select",
                          format_func=lambda c: c if c == SEARCH else (f"✅ {c}" if c in ready else c))
    st.caption("✅ = full ML forecast & early warning. Other cities show live station readings "
               "and the CAMS model outlook until you build their forecast.")
    if choice == SEARCH:
        q = st.text_input("City, town or locality", placeholder="e.g. Shillong, Dhanbad, Kathmandu")
        res = []
        if q:
            try:
                res = geocode_cached(q)
            except Exception as e:
                st.error(f"Search failed: {e}")
            if not res:
                st.caption("No matches - try another spelling.")
        if res:
            pick = st.radio("Matches", range(len(res)), format_func=lambda i: res[i]["label"])
            if st.button("Add this place"):
                g = res[pick]
                name = g["name"]
                if name in all_c and abs(all_c[name]["lat"] - g["lat"]) + abs(all_c[name]["lon"] - g["lon"]) > 0.1:
                    name = g["label"]                     # same name, different place
                if name not in all_c:
                    config.register_city(name, g["lat"], g["lon"], g["tz"])
                st.session_state["pending_city"] = name
                st.rerun()
    st.divider()
    st.header("Your alert")
    profile = st.selectbox("Who are you planning for?", list(config.PROFILES), index=1)
    threshold = st.slider("Warn me when PM2.5 exceeds (µg/m³)", 15, 250, config.PROFILES[profile], step=5)
    win_len = st.slider("Outdoor activity length (h)", 1, 4, 2)


def band_chart(fig, ymax):
    lo = 0
    for name, hi, color in config.CATEGORIES:
        if lo >= ymax:
            break
        fig.add_hrect(y0=lo, y1=min(hi, ymax), fillcolor=color, opacity=0.08, line_width=0,
                      annotation_text=name, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color="#666")
        lo = hi


def aqi_badge(a, label):
    name, color = I.aqi_category(a)
    txt = "#111" if name in ("Satisfactory", "Moderate") else "#fff"
    return (f"""<div style="background:{color};color:{txt};border-radius:10px;padding:14px 18px;text-align:center">
            <div style="font-size:0.85rem;opacity:.9">{label}</div>
            <div style="font-size:2.6rem;font-weight:800;line-height:1.1">{a:.0f}</div>
            <div style="font-size:1.05rem;font-weight:600">{name}</div></div>""")


# ------------------------------------------------------------------ view: compare cities
def render_compare():
    st.title("Compare cities")
    st.caption("CPCB AQI from 24-hour mean PM2.5 / PM10. Cities with ✅ use our station-trained ML forecast; "
               "others use the CAMS global model (coarser, often biased).")
    cities = config.all_cities()
    try:
        data = cams_many_cached(tuple(sorted((n, c["lat"], c["lon"]) for n, c in cities.items())))
    except Exception as e:
        st.error(f"Could not reach the Open-Meteo air-quality service: {e}")
        return
    rows = []
    for name, d in data.items():
        tz = cities[name].get("tz", "Asia/Kolkata")
        past = d[(d.index <= now) & (d.index > now - pd.Timedelta(hours=24))]
        fut = d[(d.index > now) & (d.index <= now + pd.Timedelta(hours=48))]
        loc = d.index.tz_convert(tz)
        tmr = d[loc.date == (now.tz_convert(tz) + pd.Timedelta(days=1)).date()]
        row = {"City": name, "AQI now": I.aqi(past.pm25.mean(), past.pm10.mean()),
               "PM2.5 now": d.pm25[d.index <= now].iloc[-1] if (d.index <= now).any() else np.nan,
               "Peak PM2.5 next 48 h": fut.pm25.max(),
               "AQI tomorrow": I.aqi(tmr.pm25.mean(), tmr.pm10.mean()), "Source": "CAMS model",
               "lat": cities[name]["lat"], "lon": cities[name]["lon"]}
        if config.city_has_forecast(name):
            f = pd.read_csv(config.REPORT_ROOT / config.slug(name) / "forecast.csv",
                            parse_dates=["target_time"])
            f["target_time"] = pd.to_datetime(f["target_time"], utc=True)
            ff = f[(f.target_time > now) & (f.target_time <= now + pd.Timedelta(hours=48))]
            ft = f[f.target_time.dt.tz_convert(tz).dt.date == (now.tz_convert(tz) + pd.Timedelta(days=1)).date()]
            if not ff.empty:
                row["Peak PM2.5 next 48 h"] = ff.q50.max()
                row["Source"] = "✅ ML forecast"
            if len(ft) >= 12:
                row["AQI tomorrow"] = I.aqi(ft.q50.mean(), tmr.pm10.mean())
        rows.append(row)
    t = pd.DataFrame(rows).sort_values("AQI now", ascending=False)
    t["Category"] = t["AQI now"].apply(lambda a: I.aqi_category(a)[0])
    t["Tomorrow"] = t["AQI tomorrow"].apply(lambda a: I.aqi_category(a)[0])
    t["color"] = t["AQI now"].apply(lambda a: I.aqi_category(a)[1])

    k1, k2, k3 = st.columns(3)
    k1.metric("Most polluted now", t.iloc[0].City, f"AQI {t.iloc[0]['AQI now']:.0f}", delta_color="off")
    k2.metric("Cleanest now", t.iloc[-1].City, f"AQI {t.iloc[-1]['AQI now']:.0f}", delta_color="off")
    k3.metric("Cities Poor or worse tomorrow", int((t["AQI tomorrow"] > 200).sum()), f"of {len(t)}",
              delta_color="off")

    figm = go.Figure(go.Scattergeo(lat=t.lat, lon=t.lon, text=t.City + "<br>AQI " + t["AQI now"].round(0).astype(int).astype(str),
                                   hoverinfo="text", mode="markers",
                                   marker=dict(size=np.clip(t["AQI now"] / 12, 7, 30), color=t.color,
                                               line=dict(width=0.5, color="#333"))))
    figm.update_geos(fitbounds="locations", showcountries=True, countrycolor="#999", showland=True,
                     landcolor="#f5f5f0", showocean=True, oceancolor="#e8f1f8")
    figm.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
    c1, c2 = st.columns([1.1, 1])
    c1.plotly_chart(figm, width="stretch")
    top = t.head(20)[::-1]
    figb = go.Figure(go.Bar(x=top["AQI now"], y=top.City, orientation="h", marker_color=top.color,
                            hovertemplate="%{y}: AQI %{x:.0f}<extra></extra>"))
    figb.update_layout(height=520, title="AQI now (24-h mean)", margin=dict(t=40, l=10))
    c2.plotly_chart(figb, width="stretch")
    show = t[["City", "AQI now", "Category", "PM2.5 now", "Peak PM2.5 next 48 h", "AQI tomorrow", "Tomorrow", "Source"]]
    st.dataframe(show.round(0), hide_index=True, width="stretch")


# ------------------------------------------------------------------ view: quick city (no model yet)
def start_build(city, extra=()):
    log = config.REPORT_DIR / "build.log"
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-u", "pipeline.py", "all", "--city", city, *extra],
                            cwd=config.ROOT, stdout=fh, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    st.session_state.setdefault("builds", {})[city] = proc


def build_running(city) -> bool:
    proc = st.session_state.get("builds", {}).get(city)
    return proc is not None and proc.poll() is None


def build_status(city, running_text):
    """Shows progress of a background build; returns True while one is running."""
    proc = st.session_state.get("builds", {}).get(city)
    log = config.REPORT_DIR / "build.log"
    tail = lambda n: "\n".join(log.read_text(encoding="utf-8", errors="ignore").splitlines()[-n:]) if log.exists() else ""
    if proc is None:
        return False
    if proc.poll() is None:
        st.info(running_text)
        st.code(tail(12) or "starting ...")
        st.button("Check progress", key=f"progress_{city}")
        return True
    st.session_state["builds"].pop(city, None)
    if proc.returncode == 0:
        st.cache_data.clear()
        st.rerun()
    st.error("The build failed. Last lines of the log:")
    st.code(tail(25))
    return False


@st.cache_data(ttl=6 * 3600, show_spinner="Listing nearby monitoring stations ...")
def stations_list(city, lat, lon, _stamp):
    """One row per station (OpenAQ location), best first. Uses the saved list when the city
    has been built, otherwise asks OpenAQ."""
    f = config.DATA_ROOT / config.slug(city) / "raw" / "sensors.csv"
    if f.exists():
        s = pd.read_csv(f)
    elif config.OPENAQ_API_KEY:
        from aq import openaq
        s = openaq.find_pm25_sensors(lat, lon, config.SEARCH_RADIUS_M)
    else:
        return pd.DataFrame()
    if s.empty:
        return s
    s["last"] = pd.to_datetime(s["last"], utc=True, format="mixed", errors="coerce")
    g = (s.groupby("location_id", sort=False)
           .agg(location=("location", "first"), provider=("provider", "first"),
                is_monitor=("is_monitor", "first"), distance_m=("distance_m", "first"),
                last=("last", "max"), sensor_id=("sensor_id", "max"), sensors=("sensor_id", list))
           .reset_index())
    return g


def station_picker(city, current_loc=None, forced=False):
    """Sidebar selector. Returns (chosen sensor id or None for automatic, changed?)."""
    c = config.all_cities()[city]
    f = config.DATA_ROOT / config.slug(city) / "raw" / "sensors.csv"
    try:
        g = stations_list(city, c["lat"], c["lon"], _mtime(f))
    except Exception as e:
        st.caption(f"Station list unavailable: {e}")
        return None, False
    if g.empty:
        st.caption("No PM2.5 monitors found within 25 km.")
        return None, False
    AUTO = "auto"

    def label(v):
        if v == AUTO:
            return "Automatic (best available)"
        r = g[g.location_id == v].iloc[0]
        age = (now - r["last"]).total_seconds() / 86400 if pd.notna(r["last"]) else np.inf
        status = "reporting" if age < 1 else (f"silent {age:.0f} days" if np.isfinite(age) else "no data")
        kind = "" if r.is_monitor else ", low-cost sensor"
        return f"{r.location} ({(r.distance_m or 0)/1000:.1f} km, {status}{kind})"

    options = [AUTO] + g.location_id.tolist()
    default = current_loc if (forced and current_loc in options) else AUTO
    pick = st.selectbox("Station", options, index=options.index(default), format_func=label,
                        key=f"station_{city}",
                        help="Automatic picks the best active reference monitor with long history. "
                             "Choosing a station trains the model on that station's readings.")
    chosen = None if pick == AUTO else int(g[g.location_id == pick].sensor_id.iloc[0])
    return chosen, pick != default


def render_quick(city):
    c = config.all_cities()[city]
    try:
        cams = cams_cached(c["lat"], c["lon"])
    except Exception as e:
        st.title(city)
        st.error(f"Could not reach the Open-Meteo air-quality service: {e}")
        return
    stations = pd.DataFrame()
    if config.OPENAQ_API_KEY:
        try:
            stations = stations_cached(c["lat"], c["lon"])
        except Exception as e:
            st.warning(f"Live station readings are unavailable right now: {e}")
    fresh = stations[stations.time > now - pd.Timedelta(hours=6)] if not stations.empty else stations

    past24 = cams[(cams.index <= now) & (cams.index > now - pd.Timedelta(hours=24))]
    fut = cams[(cams.index > now) & (cams.index <= now + pd.Timedelta(hours=48))]
    loc = cams.index.tz_convert(config.LOCAL_TZ)
    tmr_date = (now.tz_convert(config.LOCAL_TZ) + pd.Timedelta(days=1)).date()
    tmr = cams[loc.date == tmr_date]
    aqi_now = I.aqi(past24.pm25.mean(), past24.pm10.mean())
    aqi_tmr = I.aqi(tmr.pm25.mean(), tmr.pm10.mean())
    above = fut[fut.pm25 > threshold]
    if not above.empty:
        t0 = above.index[0].tz_convert(config.LOCAL_TZ)
        level, msg = "WATCH", (f"The CAMS model shows PM2.5 above {threshold} µg/m³ from {t0:%a %d %b %H:%M}, "
                               f"for about {len(above)} hours. Build this city's forecast for a calibrated warning.")
    else:
        level, msg = "CLEAR", f"The CAMS model keeps PM2.5 below {threshold} µg/m³ for the next 48 hours."
    name, col = I.aqi_category(aqi_now)
    hrs = pd.DataFrame({"local_time": fut.index.tz_convert(config.LOCAL_TZ), "value": fut.pm25.to_numpy()})
    st.markdown(ui.hero(place=city, subline=f"Quick view from the CAMS global model and nearby monitors "
                        f"({c['lat']:.2f}°, {c['lon']:.2f}°)", aqi_value=aqi_now, aqi_cat=name, aqi_color=col,
                        aqi_label="AQI, last 24 hours (CAMS)", level=level, message=msg, hours=hrs,
                        threshold=threshold), unsafe_allow_html=True)

    items = []
    if not fresh.empty:
        med = float(fresh.pm25.median())
        items.append(("Monitors right now", f"{med:.0f} <small>µg/m³</small>",
                      f"median of {len(fresh)} stations, {I.category(med)[0]}", I.category(med)[1]))
    else:
        items.append(("Monitors right now", "–", "no recent readings" if config.OPENAQ_API_KEY
                      else "add an OpenAQ key to see them", None))
    n2, c2 = I.aqi_category(aqi_tmr)
    items.append((f"AQI tomorrow, {tmr_date:%a %d %b}", f"{aqi_tmr:.0f}", n2, c2))
    if not fut.empty:
        pk = fut.pm25.idxmax()
        items.append(("Peak in the next 48 h", f"{fut.pm25.max():.0f} <small>µg/m³</small>",
                      f"{I.category(fut.pm25.max())[0]}, {pk.tz_convert(config.LOCAL_TZ):%a %H:%M}",
                      I.category(fut.pm25.max())[1]))
    st.markdown(ui.tiles(items), unsafe_allow_html=True)

    ymax = float(np.nanmax([cams.pm25.max(), threshold, fresh.pm25.max() if not fresh.empty else 0]) * 1.15)
    fig = go.Figure()
    band_chart(fig, ymax)
    fig.add_trace(go.Scatter(x=loc, y=cams.pm25, name="CAMS PM2.5", line=dict(color="#2F6FDE", width=2.5)))
    fig.add_trace(go.Scatter(x=loc, y=cams.pm10, name="CAMS PM10", line=dict(color="#8d6e63", dash="dot"),
                             visible="legendonly"))
    if not stations.empty:
        fig.add_trace(go.Scatter(x=stations.time.dt.tz_convert(config.LOCAL_TZ), y=stations.pm25, mode="markers",
                                 name="Station readings (latest)", text=stations.station,
                                 marker=dict(color="#1B2A41", size=9, symbol="diamond")))
    fig.add_hline(y=threshold, line=dict(color="#c62828", dash="dash"),
                  annotation_text=f"your threshold {threshold}", annotation_position="bottom right")
    fig.add_vline(x=now.tz_convert(config.LOCAL_TZ), line=dict(color="#555", dash="dot"))
    fig.update_layout(height=430, yaxis_title="µg/m³", yaxis_range=[0, ymax], hovermode="x unified",
                      margin=dict(t=30, b=10), legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, width="stretch")

    d = cams.assign(day=loc.date).groupby("day").agg(pm25=("pm25", "mean"), pm10=("pm10", "mean"),
                                                      peak=("pm25", "max"), n=("pm25", "size"))
    d = d[d.n >= 12]
    d["AQI"] = [I.aqi(a, b) for a, b in zip(d.pm25, d.pm10)]
    d["Category"] = d["AQI"].apply(lambda a: I.aqi_category(a)[0])
    d["Advice"] = d["Category"].map(I.HEALTH_ADVICE)
    st.subheader("Daily outlook (CAMS)")
    st.dataframe(d.reset_index().rename(columns={"day": "Day", "pm25": "PM2.5 mean", "pm10": "PM10 mean",
                                                 "peak": "PM2.5 peak"}).drop(columns="n").round(0),
                 hide_index=True, width="stretch")

    if not stations.empty:
        st.subheader("Nearest monitoring stations")
        s2 = stations.assign(Category=stations.pm25.apply(lambda v: I.category(v)[0]),
                             color=stations.pm25.apply(lambda v: I.category(v)[1]),
                             updated=stations.time.dt.tz_convert(config.LOCAL_TZ).dt.strftime("%d %b %H:%M"))
        m1, m2 = st.columns([1, 1.2])
        m1.map(s2, latitude="lat", longitude="lon", color="color", size=400)
        m2.dataframe(s2[["station", "pm25", "Category", "updated", "distance_km", "provider"]].round(1),
                     hide_index=True, width="stretch")

    st.subheader(f"Get the full forecast for {city}")
    st.markdown("Downloads this city's station history and weather, trains the model and turns on the "
                "calibrated 60-hour forecast, probabilities, drivers and track record. Takes about 3–10 minutes.")
    if not config.OPENAQ_API_KEY:
        st.info("Add your free OpenAQ key to `.env` (OPENAQ_API_KEY=...) first.")
        return
    with st.sidebar:
        st.divider()
        st.header("Station")
        chosen, _ = station_picker(city)
    if build_status(city, "Building the forecast. You can look at other cities meanwhile."):
        return
    extra = ["--sensor", str(chosen)] if chosen else ["--auto-station"]
    where = "the station chosen in the sidebar" if chosen else "the best available station"
    if st.button(f"Build forecast for {city}", type="primary"):
        start_build(city, extra)
        st.rerun()
    st.caption(f"Uses {where}. From a terminal: python pipeline.py all --city \"{city}\" "
               + (f"--sensor {chosen}" if chosen else ""))


# ------------------------------------------------------------------ routing
if view == "Compare cities":
    render_compare()
    st.stop()
if choice == SEARCH:
    st.title("Find a city")
    st.write("Type a city, town or locality in the sidebar, pick the right match and click **Add this place**. "
             "It will then appear in the city list.")
    st.stop()

config.set_city(choice)
if not config.city_has_forecast(choice):
    render_quick(choice)
    st.stop()

files = [config.PROC_DIR / "hourly.csv", config.REPORT_DIR / "forecast.csv"]
hourly, meta, fc, drivers, backtest, btp = load_all(choice, sum(_mtime(f) for f in files))

with st.sidebar:
    st.divider()
    st.header("Station")
    if meta.get("mode") == "demo":
        st.caption("Demo data: synthetic station.")
    else:
        chosen, changed = station_picker(choice, meta.get("location_id"),
                                         forced=bool(config.all_cities()[choice].get("sensor_id")))
        if changed and not build_running(choice):
            st.caption("Switching retrains this city's model on the selected station (about 3–10 minutes). "
                       "The current forecast stays visible meanwhile.")
            if st.button("Use this station", type="primary"):
                start_build(choice, ["--sensor", str(chosen)] if chosen else ["--auto-station"])
                st.rerun()
        st.caption(f"In use: {meta.get('station')} ({meta.get('provider')})")
    if st.button("Refresh data and forecast"):
        args = [sys.executable, "pipeline.py", "update", "--city", choice] + \
               (["--demo"] if meta.get("mode") == "demo" else [])
        with st.spinner("Downloading latest observations & weather forecast ..."):
            r = subprocess.run(args, cwd=config.ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            st.cache_data.clear()
            st.rerun()
        else:
            st.error((r.stderr or r.stdout)[-1500:])

# ------------------------------------------------------------------ header
build_status(choice, "Switching station and retraining. The forecast below is the previous one until this finishes.")
if meta.get("mode") == "demo":
    st.info("Demo mode: these are synthetic data. Run `python pipeline.py all` with an OpenAQ key for real data.")

last_obs_t = hourly["pm25"].last_valid_index()
last_obs = float(hourly.loc[last_obs_t, "pm25"])
issue = fc["issue_time"].iloc[0]
lag_h = (now - last_obs_t).total_seconds() / 3600

fresh = meta.get("freshness", {})
fc_end = fc["target_time"].max()
alert = I.alert_summary(fc, threshold, now)
peak_cat = I.category(alert.get("peak_value", np.nan))[0]
up = I.upcoming(fc, now)
daily = I.daily_outlook(fc, now)
pm_all = hourly["pm25"].combine_first(hourly["pm25_bridge"]) if "pm25_bridge" in hourly else hourly["pm25"]
aqi_now = I.aqi(pm_all[pm_all.index <= now].dropna().tail(24).mean())      # last 24 available hours
aqi_name, aqi_col = I.aqi_category(aqi_now)

ago = f"{lag_h:.0f} hours ago" if lag_h >= 1.5 else "within the last hour"
st.markdown(ui.hero(
    place=meta.get("city"),
    subline=f"{meta.get('station')}, last measured {ago}",
    aqi_value=aqi_now, aqi_cat=aqi_name, aqi_color=aqi_col, aqi_label="AQI, last 24 hours",
    level=alert["level"], message=alert["message"],
    hours=up.head(48).rename(columns={"q50": "value"})[["local_time", "value"]],
    threshold=threshold,
    advice=f"At the peak ({peak_cat}): {I.HEALTH_ADVICE.get(peak_cat, '')}" if peak_cat != "No data" else ""),
    unsafe_allow_html=True)

if fresh.get("bridged") and lag_h > 6:
    st.warning(f"The station has not reported for {lag_h:.0f} h. The missing hours are estimated from the "
               f"CAMS model × {fresh['bridge_ratio']:.2f} (its recent local bias), so the forecast still starts from now. "
               "Treat it as lower-confidence until the station is back, or choose another station in the sidebar.")
elif lag_h > 12:
    st.warning(f"The station's latest reading is {lag_h:.0f} h old, so forecasts further ahead are less reliable. "
               "Use Refresh in the sidebar, or choose a station that is still reporting.")
if fc_end <= now:
    st.error(f"This forecast ended at {fc_end.tz_convert(config.LOCAL_TZ):%a %d %b %H:%M} because the station stopped "
             "reporting. Click Refresh in the sidebar: outages under 14 days are bridged with CAMS.")

items = [("Last reading", f"{last_obs:.0f} <small>µg/m³</small>",
          f"{I.category(last_obs)[0]}, {last_obs_t.tz_convert(config.LOCAL_TZ):%a %H:%M}", I.category(last_obs)[1])]
nxt = up[up["target_time"] <= now + pd.Timedelta(hours=24)]
lat = up[up["target_time"] > now + pd.Timedelta(hours=24)]
for label, part in (("Peak in the next 24 h", nxt), ("Peak in 24–48 h", lat)):
    if not part.empty:
        r = part.loc[part.q50.idxmax()]
        items.append((label, f"{r.q50:.0f} <small>µg/m³</small>",
                      f"{I.category(r.q50)[0]}, {r.local_time:%a %H:%M}", I.category(r.q50)[1]))
if len(daily) > 1:
    d = daily.iloc[1]
    items.append((f"Tomorrow's 24-h mean", f"{d.q50:.0f} <small>µg/m³</small>",
                  f"{d.p_naaqs:.0%} chance above the national limit of {config.NAAQS_24H}", I.category(d.q50)[1]))
st.markdown(ui.tiles(items), unsafe_allow_html=True)

tabs = st.tabs(["Forecast", "Plan your day", "Why", "Track record", "Patterns", "Compared with weather apps"])


def add_category_bands(fig, ymax):
    lo = 0
    for name, hi, color in config.CATEGORIES:
        if lo >= ymax:
            break
        fig.add_hrect(y0=lo, y1=min(hi, ymax), fillcolor=color, opacity=0.08, line_width=0,
                      annotation_text=name, annotation_position="top left",
                      annotation_font_size=10, annotation_font_color="#666")
        lo = hi


# ------------------------------------------------------------------ tab 1: forecast
with tabs[0]:
    hist = hourly.loc[last_obs_t - pd.Timedelta(hours=96): last_obs_t, "pm25"]
    hist_local = hist.index.tz_convert(config.LOCAL_TZ)
    ymax = float(np.nanmax([fc.q90.max(), hist.max(), threshold]) * 1.15)
    fig = go.Figure()
    add_category_bands(fig, ymax)
    fig.add_trace(go.Scatter(x=fc.local_time, y=fc.q90, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc.local_time, y=fc.q10, fill="tonexty", fillcolor="rgba(47,111,222,0.16)",
                             line=dict(width=0), name="80% range"))
    fig.add_trace(go.Scatter(x=fc.local_time, y=fc.q50, name="Our forecast (median)",
                             line=dict(color="#2F6FDE", width=3)))
    fig.add_trace(go.Scatter(x=hist_local, y=hist.values, name="Measured", line=dict(color="#1B2A41", width=2)))
    if "pm25_bridge" in hourly and hourly["pm25_bridge"].notna().any():
        b = hourly["pm25_bridge"].dropna()
        fig.add_trace(go.Scatter(x=b.index.tz_convert(config.LOCAL_TZ), y=b.values, name="Estimated (station offline)",
                                 line=dict(color="#1B2A41", width=2, dash="dot")))
    if fc["cams"].notna().any():
        fig.add_trace(go.Scatter(x=fc.local_time, y=fc.cams, name="CAMS global model (what weather apps show)",
                                 line=dict(color="#888", dash="dot")))
    fig.add_hline(y=threshold, line=dict(color="#c62828", dash="dash"),
                  annotation_text=f"your alert threshold {threshold}", annotation_position="bottom right")
    fig.add_vline(x=now.tz_convert(config.LOCAL_TZ), line=dict(color="#555", dash="dot"))
    fig.update_layout(height=470, yaxis_title="PM2.5 (µg/m³)", yaxis_range=[0, ymax], hovermode="x unified",
                      margin=dict(t=30, b=10), legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, width="stretch")

    up["p"] = exceed_prob(up.q10, up.q50, up.q90, threshold)
    figp = go.Figure(go.Bar(x=up.local_time, y=up.p * 100,
                            marker_color=np.where(up.p >= 0.6, "#c62828", np.where(up.p >= 0.3, "#f9a825", "#90a4ae")),
                            hovertemplate="%{x|%a %H:%M}: %{y:.0f}%<extra></extra>"))
    figp.update_layout(height=230, title=f"Chance PM2.5 exceeds {threshold} µg/m³, hour by hour",
                       yaxis_title="%", yaxis_range=[0, 100], margin=dict(t=40, b=10))
    st.plotly_chart(figp, width="stretch")

# ------------------------------------------------------------------ tab 2: plan
with tabs[1]:
    st.subheader("Daily outlook")
    if daily.empty:
        st.info("No forecast hours left for the coming days - refresh the data first.")
    cols = st.columns(max(len(daily), 1))
    for col, (_, d) in zip(cols, daily.iterrows()):
        name, color = I.category(d.q50)
        col.markdown(
            f"""<div class="day" style="--c:{color}"><h4>{pd.Timestamp(d.day):%A %d %b}</h4>
            <div class="big">{d.q50:.0f} <small>µg/m³ 24-h mean</small></div>
            <p><b>{name}</b>, likely between {d.q10:.0f} and {d.q90:.0f}</p>
            <p>{d.x_who:.1f} times the WHO guideline, like smoking {d.cigarettes:.1f} cigarettes</p>
            <p>{d.p_naaqs:.0%} chance of breaching India's 24-hour limit ({config.NAAQS_24H})</p></div>""",
            unsafe_allow_html=True)
    st.caption("Cigarette equivalence: Berkeley Earth rule of thumb (22 µg/m³ over 24 h ≈ 1 cigarette). "
               "Partial days show only the remaining forecast hours.")

    st.subheader(f"Best {win_len}-hour window for outdoor activity (06:00–21:00)")
    bw = I.best_windows(fc, duration=win_len, now=now)
    if bw.empty:
        st.write("Not enough forecast hours left.")
    else:
        for _, r in bw.iterrows():
            gain = r.worst_same_day - r.roll
            st.markdown(f"- **{r.start:%a %d %b %H:%M}–{r.end:%H:%M}** · expected ≈ {r.roll:.0f} µg/m³ "
                        f"({I.category(r.roll)[0]}) – about {gain:.0f} µg/m³ cleaner than the worst slot that day")

    st.subheader("Hour by hour (next 48 h)")
    tbl = up.assign(Time=up.local_time.dt.strftime("%a %d %b %H:%M"),
                    Forecast=up.q50.round(0), Low=up.q10.round(0), High=up.q90.round(0),
                    Category=up.q50.apply(lambda v: I.category(v)[0]),
                    **{"Chance > threshold": (up.p * 100).round(0).astype(int).astype(str) + "%"})
    st.dataframe(tbl[["Time", "Forecast", "Low", "High", "Category", "Chance > threshold"]],
                 hide_index=True, width="stretch", height=360)
    st.download_button("⬇️ Download forecast (CSV)", fc.to_csv(index=False), "pm25_forecast.csv")

# ------------------------------------------------------------------ tab 3: why
with tabs[2]:
    st.subheader("What is driving the forecast?")
    st.caption("Each weather factor is swapped for its typical value for this month and hour, "
               "and the model is re-run. Bars show how much that factor raises (+) or lowers (−) PM2.5.")
    if not drivers.empty:
        dd = drivers.melt(id_vars="driver", var_name="period", value_name="effect")
        dd["period"] = dd["period"].map({"effect_next24h": "Next 24 h", "effect_24_48h": "24–48 h"})
        figd = go.Figure()
        for per, color in (("Next 24 h", "#90caf9"), ("24–48 h", "#2F6FDE")):
            s = dd[dd.period == per]
            figd.add_trace(go.Bar(y=s.driver, x=s.effect, name=per, orientation="h", marker_color=color))
        figd.update_layout(height=340, barmode="group", xaxis_title="µg/m³ vs a typical day", margin=dict(t=10))
        st.plotly_chart(figd, width="stretch")
        for s in I.driver_sentences(drivers) or ["No single weather factor stands out - conditions are near typical."]:
            st.markdown(f"- {s}")

    st.subheader("Weather behind it: ventilation & rain")
    w = hourly.loc[last_obs_t - pd.Timedelta(hours=24): last_obs_t + pd.Timedelta(hours=config.MAX_HORIZON)]
    wl = w.index.tz_convert(config.LOCAL_TZ)
    figw = go.Figure()
    if "blh" in w and w["blh"].notna().any():
        figw.add_trace(go.Scatter(x=wl, y=w.wind_speed * w.blh, name="Ventilation index (wind × mixing height, m²/s)",
                                  line=dict(color="#00897b")))
    figw.add_trace(go.Bar(x=wl, y=w.precip, name="Rain (mm/h)", yaxis="y2", marker_color="#5c6bc0"))
    figw.add_hrect(y0=0, y1=2000, fillcolor="#e53935", opacity=0.07, line_width=0,
                   annotation_text="stagnant (< 2000)", annotation_position="top left")
    figw.update_layout(height=320, yaxis=dict(title="m²/s"), margin=dict(t=10),
                       yaxis2=dict(title="mm/h", overlaying="y", side="right", showgrid=False),
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(figw, width="stretch")

    if backtest and backtest.get("importance"):
        imp = pd.Series(backtest["importance"]).head(12)[::-1]
        figi = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color="#546e7a"))
        figi.update_layout(height=380, title="Most important model inputs overall (permutation importance)",
                           margin=dict(t=40))
        st.plotly_chart(figi, width="stretch")
        st.caption("The model predicts how PM2.5 will CHANGE from the latest reading. "
                   "Prefixes: p_ = recent measured PM2.5 (relative to now), w_ = weather at the target hour, "
                   "c_cams_change = how much CAMS expects regional PM2.5 to change, "
                   "k_ = calendar, d_ = change from now, path_ = conditions between now and the target hour, h = lead time.")

# ------------------------------------------------------------------ tab 4: track record
with tabs[3]:
    if not backtest:
        st.info("Run `python pipeline.py train` to produce the backtest.")
    else:
        p = backtest["period"]
        st.caption(f"Out-of-sample test: forecasts issued {p['test_start'][:10]} → {p['test_end'][:10]} "
                   "(the model never saw these hours while training).")
        a, b = backtest["summary_0-24h"], backtest["summary_24-48h"]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Error 0–24 h (MAE)", f"{a['mae_model']:.1f} µg/m³",
                  f"{a['skill_vs_persistence']:+.0%} vs persistence")
        k2.metric("Error 24–48 h (MAE)", f"{b['mae_model']:.1f} µg/m³",
                  f"{b['skill_vs_persistence']:+.0%} vs persistence")
        if "skill_vs_cams" in b:
            k3.metric("Better than CAMS (24–48 h)", f"{b['skill_vs_cams']:+.0%}", "lower error than global model")
        k4.metric("80% range really contains truth", f"{b['coverage_80']:.0%}", "target 80%", delta_color="off")

        bh = pd.DataFrame(backtest["by_horizon"])
        fig = go.Figure()
        for col, name, style in (("mae_model", "Our model", dict(color="#2F6FDE", width=3)),
                                 ("mae_persistence", "Persistence (now = later)", dict(color="#999")),
                                 ("mae_same_hour", "Same hour yesterday", dict(color="#bbb", dash="dash")),
                                 ("mae_cams", "CAMS global model", dict(color="#f57c00", dash="dot"))):
            if bh[col].notna().any():
                fig.add_trace(go.Scatter(x=bh.h, y=bh[col], name=name, line=style))
        fig.update_layout(height=360, xaxis_title="Lead time (h)", yaxis_title="Mean absolute error (µg/m³)",
                          margin=dict(t=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")

        st.subheader("How good are the warnings? (24–48 h ahead, warn when chance ≥ 50%)")
        al = pd.DataFrame(backtest["alerts"]).T.reset_index().rename(columns={"index": "Threshold µg/m³"})
        al = al.rename(columns={"events": "Event hours", "POD": "Caught (POD)", "FAR": "False alarms (FAR)",
                                "CSI": "CSI", "brier": "Brier score"})
        st.dataframe(al, hide_index=True, width="stretch")

        c1, c2 = st.columns(2)
        rel = pd.DataFrame(backtest.get("reliability", []))
        if not rel.empty:
            figr = go.Figure()
            figr.add_trace(go.Scatter(x=[0, 1], y=[0, 1], line=dict(color="#aaa", dash="dash"), name="perfect"))
            figr.add_trace(go.Scatter(x=rel.forecast_prob, y=rel.observed_freq, mode="lines+markers",
                                      name="model", marker=dict(size=np.clip(np.sqrt(rel.n) / 3, 6, 22))))
            figr.update_layout(height=340, title="Reliability: when we say X%, does it happen X% of the time? (>90)",
                               xaxis_title="Forecast probability", yaxis_title="Observed frequency",
                               margin=dict(t=40))
            c1.plotly_chart(figr, width="stretch")
        if btp is not None:
            hsel = c2.selectbox("Lead time to inspect", sorted(btp.h.unique()), index=min(4, btp.h.nunique() - 1))
            s = btp[btp.h == hsel].sort_values("target_time")
            s = s[s.target_time >= s.target_time.max() - pd.Timedelta(days=30)]
            # the scored weeks alternate with calibration weeks: break the lines across the gaps
            gap = s.target_time.diff() > pd.Timedelta(hours=12)
            if gap.any():
                fill = s[gap].assign(target_time=s[gap].target_time - pd.Timedelta(hours=1),
                                     y=np.nan, q10=np.nan, q50=np.nan, q90=np.nan)
                s = pd.concat([s, fill]).sort_values("target_time")
            figb = go.Figure()
            figb.add_trace(go.Scatter(x=s.target_time, y=s.q90, line=dict(width=0), showlegend=False))
            figb.add_trace(go.Scatter(x=s.target_time, y=s.q10, fill="tonexty", line=dict(width=0),
                                      fillcolor="rgba(47,111,222,0.16)", name="80% range"))
            figb.add_trace(go.Scatter(x=s.target_time, y=s.q50, name=f"Forecast {hsel} h ahead",
                                      line=dict(color="#2F6FDE")))
            figb.add_trace(go.Scatter(x=s.target_time, y=s.y, name="Measured", line=dict(color="#1B2A41")))
            figb.update_layout(height=340, title="Last 30 days of the test period", margin=dict(t=40),
                               legend=dict(orientation="h", y=-0.2))
            c2.plotly_chart(figb, width="stretch")

# ------------------------------------------------------------------ tab 5: insights
with tabs[4]:
    h = hourly[hourly.pm25.notna()].copy()
    loc = h.index.tz_convert(config.LOCAL_TZ)
    h["month"], h["hour"], h["dow"] = loc.month, loc.hour, loc.dayofweek
    c1, c2 = st.columns(2)
    hm = h.pivot_table(index="hour", columns="month", values="pm25", aggfunc="mean")
    figh = go.Figure(go.Heatmap(z=hm.values, x=[pd.Timestamp(2000, m, 1).strftime("%b") for m in hm.columns],
                                y=hm.index, colorscale="YlOrRd", colorbar=dict(title="µg/m³")))
    figh.update_layout(height=420, title="Typical PM2.5 by hour of day and month", yaxis_title="Hour (IST)",
                       margin=dict(t=40))
    c1.plotly_chart(figh, width="stretch")

    if "wind_dir" in h and h["wind_dir"].notna().any():
        hw = h.dropna(subset=["wind_dir"])                  # hours without weather data can't be placed
        sector = ((hw.wind_dir + 22.5) // 45 % 8).astype(int)
        names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        rose = hw.pm25.groupby(sector).mean().reindex(range(8))
        figr = go.Figure(go.Barpolar(r=rose.values, theta=names, marker_color=rose.values,
                                     marker_colorscale="YlOrRd"))
        figr.update_layout(height=420, title="Pollution rose: mean PM2.5 by wind direction (where dirty air comes from)",
                           margin=dict(t=60),
                           polar=dict(angularaxis=dict(rotation=90, direction="clockwise")))   # compass: N up, E right
        c2.plotly_chart(figr, width="stretch")

    daily_obs = h.pm25.resample("D").mean()
    ex = (daily_obs > config.NAAQS_24H).groupby(daily_obs.index.to_period("M")).sum()
    fige = go.Figure(go.Bar(x=ex.index.astype(str), y=ex.values, marker_color="#e53935"))
    fige.update_layout(height=300, title=f"Days per month with 24-h mean above NAAQS ({config.NAAQS_24H} µg/m³)",
                       margin=dict(t=40))
    st.plotly_chart(fige, width="stretch")

    wk = h.groupby("dow").pm25.mean()
    c1, c2 = st.columns(2)
    c1.plotly_chart(go.Figure(go.Bar(x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], y=wk.values,
                                     marker_color="#546e7a")).update_layout(
        height=280, title="Weekday effect (traffic & activity)", margin=dict(t=40)), width="stretch")
    c2.markdown("**Data quality report**")
    c2.json(meta.get("qc", {}))

# ------------------------------------------------------------------ tab 6: comparison
with tabs[5]:
    st.subheader("What this system adds beyond Google Weather and IQAir")
    st.markdown("""
| Need | Google Weather | IQAir | This system |
|---|---|---|---|
| Source of the number | Models + sensors on a ~500 m grid | Government monitors (WBPCB/CPCB in Indian cities), low-cost sensors, satellite | **The nearest official monitoring station, with ML correcting the model's local bias** |
| Forecast | Hourly AQI, up to 4 days | Hourly and daily, up to 7 days | **Hourly PM2.5, 1–60 h, anchored to the latest reading** |
| Uncertainty | One number per hour | One number per hour | **80 % range for every hour, calibrated on past data** |
| Probability | Not given | Not given | **Chance (%) of crossing your threshold, every hour and per day** |
| Early warning | Colour category | Alert when the air is bad | **Watch / Warning / Emergency with start time, duration and peak, ahead of time** |
| Personal thresholds | One scale for everyone | One scale for everyone | **Profiles for asthma, children/elderly, outdoor work; custom threshold** |
| Indian standards | Varies by region | US AQI scale | **CPCB categories, the 24-h NAAQS (60) and WHO (15) comparison** |
| Why will it be bad? | Not explained | Not explained | **Driver attribution: wind, mixing height, rain, humidity, regional transport** |
| When to go out | Read it off the hourly forecast | Read it off the hourly forecast | **Cleanest outdoor window each day, suggested directly** |
| Trustworthiness | Accuracy not published | Accuracy claimed, no figures | **Public track record: error by lead time, warning hit / false-alarm rates, reliability** |
| Local patterns | — | City rankings, history | **Hour × month heatmap, pollution rose (source direction), weekday effect, exceedance days** |
| Alerts outside the app | App notifications | App notifications | **Telegram / e-mail alerts when the level rises** (`alert.py`) |
| Open & reproducible | Closed | Closed | **Open data (OpenAQ, Open-Meteo), open code, retrainable for any city** |

Where they are stronger: every place on Earth, more stations and pollutants, a longer range and polished mobile apps.
This system adds the decision layer: uncertainty, probability, timed warnings, reasons and a published track record.
""")
