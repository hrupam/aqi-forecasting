# 7-minute final presentation: script

**Rules from sir:** at most 5 slides, show the demo, hard stop at 7:00.
**Deck:** `AQ_Early_Warning_Final_5slides.pptx`. Keep the 14-slide deck only as a backup for questions.

## Timing (aim to finish at 6:30)

| Time | Slide | Speaker |
|---|---|---|
| 0:00–0:20 | 1. Title | Pramiti |
| 0:20–1:10 | 2. Weather apps give a number; we give a warning | Pramiti |
| 1:10–2:10 | 3. How it works | Rupam |
| 2:10–3:00 | 4. Results | Rupam |
| 3:00–6:15 | 5. Live demo | Tamanash |
| 6:15–6:30 | "Thank you, questions?" | Tamanash |

Swap the names as you like. Practise once with a timer: the demo is where time runs away.

## Before you start (not part of the 7 minutes)
* Open **https://my-aqi.streamlit.app** in a browser tab and click around once, so the app is awake (it sleeps after 12 h without visitors) and Kolkata is loaded.
* Put the PowerPoint and the browser side by side, or learn the Alt+Tab switch.
* Keep a phone hotspot ready in case the room network blocks streamlit.app, and `streamlit run app.py` running locally as a last resort.

---

## Slide 1: Title (20 s)
> "We built an air-quality forecasting and early-warning system. It predicts PM2.5, the most harmful air pollutant in Indian cities, for every hour up to 60 hours ahead, and warns people before the air becomes unhealthy. It runs online for eight cities. This strip is a real Kolkata forecast from our model."

## Slide 2: Weather apps give a number; we give a warning (50 s)
> "The problem: in Kolkata, every day of December 2025 broke India's 24-hour limit, and winter air is about seven times the WHO guideline. Emissions barely change between July and November; the weather does, and weather can be forecast.
> Google Weather and IQAir already show an hourly forecast, but one number per hour. We add how sure the forecast is, the chance of crossing *your* limit, when the bad spell starts and how long it lasts, why it happens, India's CPCB scale, and a published track record. They're stronger on coverage; we add the decision layer."

## Slide 3: How it works (60 s)
> "Four steps, the same for every city. We collect hourly PM2.5 from the nearest official monitor through OpenAQ, plus weather and the CAMS model from Open-Meteo. We clean it and bridge station outages. Gradient-boosted trees predict every hour from 1 to 60 ahead: three of them, for the 10th, 50th and 90th percentile. The probabilities become warning levels, also sent by Telegram or e-mail.
> Three ideas made it work: predicting the *change* from the latest reading instead of the level, training on archived weather forecasts, and calibrated uncertainty. And it runs itself: a scheduled job updates every city every three hours."

## Slide 4: Results (50 s)
> "Each city was tested on its own last months, which the model never saw, including this autumn. Blue: how much smaller our error is than simply assuming 'no change'. Orange: than CAMS, the global model. We beat both in all eight cities. In Kolkata the average error on day 1 is 5.4 µg/m³. The 80 % range really holds about 80 % of outcomes. A day or two ahead, the warnings caught 34–70 % of polluted hours with 25–38 % false alarms. Short, rare spells, as in Ahmedabad and Siliguri, are still hard. Let's see it live."

## Slide 5: Live demo (3 min 15 s), then switch to the browser
1. **Kolkata header** (30 s): "AQI on India's scale, the warning in one sentence (when, how long, how bad), and the next 48 hours as colours."
2. **Profile: Sensitive → General public** (25 s): "This is set for someone with asthma, threshold 60. For the general public it's 90, and the warning changes accordingly." Switch back afterwards.
3. **Forecast tab** (35 s): "Measured in black, our forecast in blue with its range widening further ahead, CAMS in grey, and below it the chance of exceedance for every hour."
4. **Why tab** (25 s): "Which factors push tonight's forecast up: low wind, a shallow mixing layer."
5. **Compare cities** (30 s): "All cities side by side: Delhi against Kolkata and Siliguri."
6. **Search a town**, e.g. Kharagpur (40 s): "Any place works. We see nearby monitors and the CAMS outlook instantly, and one click builds a full model for it."

Close: "Thank you. We're happy to take questions."

**If the app doesn't load:** stay on slide 5 and walk through the six numbered points in words. Never spend more than 15 seconds waiting for a page.

## If you're running late
* Past **3:15** when the demo starts: do steps 1, 3 and 5 only.
* Past **6:30**: stop the demo and say "thank you".
