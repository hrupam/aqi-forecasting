# 7-minute final presentation: script

**Rules from sir:** at most 5 slides, simple layout, show the demo, hard stop at 7:00.
**Deck:** `AQ_Final_Presentation.pptx` (5 slides). The results are shown live in the app's **Track record** tab during the demo.

## Timing (aim to finish at 6:30)

| Time | Slide | Speaker |
|---|---|---|
| 0:00–0:20 | 1. Title | Pramiti |
| 0:20–0:55 | 2. The problem | Pramiti |
| 0:55–1:45 | 3. How our product is different | Pramiti |
| 1:45–2:35 | 4. How it works | Rupam |
| 2:35–6:15 | 5. Live demo | Tamanash |
| 6:15–6:30 | "Thank you, questions?" | Tamanash |

Swap the names as you like. Practise once with a timer: the demo is where time runs away.

## Before you start (not part of the 7 minutes)
* Open **https://my-aqi.streamlit.app** and click through every tab once, so the app is awake and Kolkata is loaded.
* Zoom the browser to about 80–90 %.
* Starting state: city **Kolkata**, profile **Sensitive (asthma / heart / lung)**, view **City dashboard**.
* Keep a phone hotspot ready, and `streamlit run app.py` running locally as a last resort.

---

## Slide 1: Title (20 s)
> "We built an air-quality forecasting and early-warning system. It predicts PM2.5, the most harmful air pollutant in Indian cities, for every hour up to 60 hours ahead, and warns people before the air becomes unhealthy. It runs online for eight cities. This strip is a real Kolkata forecast from our model."

## Slide 2: The problem (35 s)
> "In Kolkata, every day of December 2025 broke India's daily limit, and winter air is about seven times the WHO guideline. November averages 108 µg/m³ against 20 in July. Emissions barely change between those months; the weather does. Weather can be forecast, so pollution can be forecast too."

## Slide 3: How our product is different (50 s)
> "Google Weather and IQAir already show an hourly forecast, but one number per hour. We add five things:
> * a range, so you know how sure the forecast is
> * the chance of crossing the limit that matters to *you*
> * a warning ahead of time: when a bad spell starts, how long it lasts, how bad the peak is
> * the reason: calm wind, a low mixing layer, no rain
> * India's own scale, and our accuracy published openly
>
> They cover more places and pollutants; we add what you need to act."

*If asked "Are you more accurate than IQAir?":* "IQAir doesn't publish its past forecasts, so we can't compare directly. We beat CAMS, the global model, and the 'no change' baseline in all eight cities."

## Slide 4: How it works (50 s)
> "Four steps, the same for every city. We **collect** hourly readings from the nearest official monitor, plus weather and the CAMS model. We **clean** them: remove bad readings and fill gaps. A machine-learning model (gradient-boosted trees) **predicts** every hour from 1 to 60 ahead, with a range. And we **warn**: Watch, Warning or Emergency. It updates itself every three hours and runs online. Let's see it."

## Slide 5: Live demo (3 min 40 s), then switch to the browser
1. **The warning at a glance**, Kolkata header (30 s): "AQI on India's scale, the warning in one sentence (when, how long, how bad), and the next 48 hours as colours."
2. **Your threshold** (25 s): switch the profile from *Sensitive* to *General public*. "For someone with asthma the threshold is 60; for the general public it's 90, and the warning changes." Switch back.
3. **Forecast and its range**, Forecast tab (35 s): "Measured in black, our forecast in blue with its range, CAMS in grey, and the chance of exceedance for every hour."
4. **Why it will be bad**, Why tab (25 s): "Low wind and a shallow mixing layer push the forecast up."
5. **Track record** (40 s): "Our report card on months the model never saw. Our error is the lowest from three hours ahead, and we beat both 'no change' and CAMS in all eight cities."
6. **Compare cities · any town** (45 s): open *Compare cities*, then search a new town, e.g. Durgapur. "Any place works: nearby monitors and the CAMS outlook appear at once, and one click builds a full model."

Close: "Thank you. We're happy to take questions."

**If the app doesn't load:** stay on slide 5 and describe the six points. Never wait more than 15 seconds for a page.

## If you're running late
* Past **3:00** when the demo starts: do steps 1, 3, 5 and 6 only.
* Past **6:30**: stop and say "thank you".

## Numbers to have ready for questions
* Kolkata error on day 1: **5.4 µg/m³**, 15 % lower than "no change"
* All 8 cities, day 1: **3–35 %** better than "no change", **31–80 %** better than CAMS
* The 80 % range holds **77–88 %** of the time
* Warnings 24–48 h ahead at 60 µg/m³: **34–70 %** of polluted hours caught, **25–38 %** false alarms (six cities; Ahmedabad and Siliguri weakest)
