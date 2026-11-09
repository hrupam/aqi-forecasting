# Final checkpoint: presentation script and viva Q&A

**Air Quality Forecasting & Early Warning System**
Pramiti Ghosh (26CS60R22) · Rupam Hari (26CS60R04) · Tamanash Kamilya (26CS60R05)

The deck has 14 slides. At about 1–1.5 minutes per slide plus a 4-minute live demo, the talk takes 20–22 minutes. Every number below comes from `reports/summary_all_cities.json` (run `python tools/summarize_results.py` after retraining).

## Suggested split

| Speaker | Slides | Topic |
|---|---|---|
| Pramiti | 1–4 | Problem, objectives, comparison with Google Weather and IQAir |
| Rupam | 5–9 | Data pipeline, model, results, warnings |
| Tamanash | 10–14 + demo | Product features, dashboard, deployment, limitations |

Change it as you like. Whoever presents a slide should also take its questions.

---

## Slide by slide

### 1. Title
**Land:** what the system does, in one sentence.
> "Our project forecasts PM2.5, the most harmful air pollutant in Indian cities, for every hour up to 60 hours ahead, and warns people before the air becomes unhealthy. The strip is a real 48-hour forecast for Kolkata from our model: one block per hour, coloured by India's CPCB categories. Since the last checkpoint it has grown into a complete product: 8 cities, station choice, Telegram and e-mail alerts, and an online deployment that updates itself."

### 2. Kolkata's air turns unhealthy every winter
**Land:** the problem is serious and seasonal, so it can be predicted.
> "PM2.5 are particles small enough to reach the lungs and the blood. At our Kolkata station, July averages 20 µg/m³ and November 108. In December 2025, 31 of 31 days were above India's 24-hour limit of 60. On an average winter day we breathe about 7 times the WHO guideline. Emissions don't change much between July and November; the weather does. Weather can be forecast, so pollution can be forecast too."

*Q: Why is winter worse?* Cold, calm air and a low mixing layer trap smoke near the ground. There's no rain to wash it out, and north-westerly winds bring polluted air down the Indo-Gangetic Plain.

### 3. Three objectives: all delivered, and more
> "We promised three things: collect and combine data, predict 24–48 hours ahead, and give early warnings. All three work for every city. On top of that we added what the last checkpoint listed as next steps: more cities, a comparison view, station choice, alerts outside the app, an online deployment, and automatic updates every three hours."

### 4. Google Weather and IQAir give a number; we add the warning
**Land:** be precise and fair. This was the checkpoint-1 question.
> "Google Weather and IQAir both show an hourly forecast. Google's goes up to 4 days; IQAir's up to 7. But each gives one number per hour. We add what you need to act:
> * how sure the forecast is (the 80 % range)
> * the chance of crossing your own limit
> * when a bad spell starts, how long it lasts and how bad the peak is
> * why it will happen
> * a published record of how accurate we have been
>
> We also use India's CPCB scale. IQAir shows the US AQI, so the same air gets a different label. Where they are stronger: they cover the world and many pollutants. We add the decision layer."

*Q: Is your forecast more accurate than IQAir's?* "We can't claim that. IQAir doesn't publish its past forecasts, so there's nothing to score. We do beat CAMS, the global model, and the 'no change' baseline in every city. Comparing with IQAir by recording its forecast every day is in our future work."

### 5. From raw feeds to a calibrated forecast
> "The same six steps run for every city. We collect station PM2.5 from OpenAQ, weather and the CAMS model from Open-Meteo. Real data are messy: at Kolkata, out of 13,585 hourly readings we removed 257 bad ones (impossible values, hours with too few measurements, a stuck sensor, spikes), and 92.1 % of hours are usable. When a station goes silent, we fill the gap with CAMS scaled to that station's recent readings, so the forecast still starts from now. Those estimates are flagged in the dashboard and never used for training."

*Q: Why train on archived forecasts instead of real weather?* When we run live we only have forecast weather, which has errors. Training on what was actually forecast at the time teaches the model to cope with those errors.

### 6. One model forecasts every hour from 1 to 60
> "Each training example says: from this hour, predict h hours ahead, with h as an input. So one model gives the whole 60-hour curve, and errors don't pile up as they would if we fed predictions back in. We train three versions, for the 10th, 50th and 90th percentile. The middle one is the forecast; the outer two give the 80 % range, and from them the probability of crossing any threshold."

*Q: Why gradient boosting and not LSTM?* With about 20 months of hourly data per city, gradient-boosted trees are the strongest choice for tabular data. They learn combinations such as 'low wind and a low mixing layer at night', handle missing sensor values, forecast percentiles directly, train in minutes on a laptop and can be explained. An LSTM needs more data and a GPU, and it's harder to explain.

### 7. Beats "no change" at every lead time, and CAMS by far
> "This is Kolkata, on months the model never saw: 2026-05-26 to 2026-11-09. Persistence means 'the air later will be the same as now'. It sounds trivial, but it's the standard baseline and hard to beat in the first hours. Our error is below it at every lead time: 5.4 µg/m³ on day 1 and 7.0 on day 2, which is 15 % and 16 % less than persistence. CAMS is far worse at this station because of a steady local bias. And 83 % of real values fall inside our 80 % range, so the uncertainty is honest.
>
> The key lesson is in the box. Our first model predicted the level directly and lost to persistence, because one year was much cleaner than the one before. Predicting the change from the current reading fixed it."

### 8. Tested in 8 cities
> "The same pipeline, unchanged, was built and tested in 8 cities, each on its own nearest official station. It beats 'no change' everywhere, by 3–35 % on day 1, and CAMS by 31–80 %. The 80 % range holds in every city (77–88 %). The smallest gains are in Amritsar and Jaipur, where pollution barely changed in the test months, so 'no change' was already a good guess."

*Q: Gurugram's station is in Delhi?* Yes: R K Puram is the best official monitor within 25 km of Gurugram that had enough history. The station choice in the dashboard lets a user pick another one.

### 9. Warnings: tested on real episodes, delivered to your phone
> "The probabilities become levels: Watch at a 30 % chance of crossing your threshold, Warning at 60 %, Emergency when the expected peak is above 250. We retrained every city after this autumn's pollution began, so the test period contains real episodes, and scored the warnings the way weather services do: 24–48 hours ahead, at India's limit of 60 µg/m³. Where polluted hours were common, the system warned about 34–70 % of them, and 25–38 % of its warnings were false alarms. In Kolkata it caught 58 % with 38 % false alarms. The weak cases are Ahmedabad and Siliguri: polluted spells there were few and short, which are much harder to catch a day ahead. Outside the app, alert.py sends a Telegram message or an e-mail when the level rises, at most once per 12 hours for the same warning."

*Q: What are POD, FAR and CSI?* POD (probability of detection): the share of polluted hours we warned about. FAR (false alarm ratio): the share of our warnings that didn't happen. CSI (critical success index): hits ÷ (hits + misses + false alarms); 1 is perfect.

*Q: Why not catch 100 %?* A warning threshold trades misses against false alarms. Ours fires at a 50 % chance for this score. Sudden local events, such as fires or firecrackers, can't be predicted from weather.

### 10. A complete product, not a one-city prototype
> "Eight cities have full forecasts. Any other town can be searched: you immediately see live readings from nearby monitors and the CAMS outlook, and one click builds a full model for it in the background. You can choose the monitoring station, and compare all cities side by side."

### 11–12. The dashboard
Use these slides only if the live demo fails; otherwise go straight to the demo.

### 13. Online and always up to date
> "Code, data and models are on GitHub. Every three hours a GitHub Actions job updates every city, re-forecasts, checks for alerts and commits the new files. Streamlit Cloud redeploys on every commit. It all runs on free tiers, and the API keys are stored as encrypted secrets."

### 14. Limitations and future work
> "We depend on the OpenAQ feed; outages are bridged at lower confidence. One station represents its neighbourhood, not the whole city. We forecast PM2.5 only. Next: validate the warnings on this winter in every city, add PM10, NO₂ and ozone plus fire hotspots, combine several stations per city, and compare against IQAir. Thank you; we're happy to take questions."

---

## Live demo (4 minutes)

Open the deployed app before you start talking, so it's awake. Keep `streamlit run app.py` ready locally as a backup.

1. **Kolkata header** (30 s): AQI, warning message, the 48-hour strip.
2. **Change the profile** from *General public* to *Sensitive* (30 s): the threshold drops, and the warning and white ticks change.
3. **Forecast tab** (45 s): measured line, forecast band, CAMS, hourly probability bars.
4. **Why tab** (30 s): which factors push the forecast up tonight.
5. **Track record tab** (30 s): error vs lead time and the warning scores.
6. **Compare cities** (30 s): Delhi vs Kolkata vs Siliguri.
7. **Search a new town**, for example Kharagpur (45 s): live nearby readings and the CAMS outlook appear instantly; mention that one click builds a full model.
8. **Optional:** show the Telegram alert on a phone.

---

## Viva questions

**Data**
* *Why OpenAQ?* It is the largest open archive of government monitor data, including CPCB and the state boards, with one API for every city.
* *Why join two sensor IDs?* OpenAQ often splits one CPCB station into an old and a new sensor ID. Joined, they give one continuous history.
* *What if the station is offline?* For 6 hours to 14 days, the missing hours are estimated as CAMS × the station/CAMS ratio of the previous week (a median in log space). The dashboard flags it, and training never uses it.
* *Why UTC?* One unambiguous timeline for all sources; it is shown in local time.

**Model**
* *What is the target?* The change in log PM2.5 from the latest reading to the target hour, so the model is anchored to today's level.
* *How do you get the 80 % range?* Separate 10th- and 90th-percentile models, scaled with split-conformal calibration on held-out weeks.
* *How do you get a probability?* From the three percentiles we fit a split-normal distribution in log space and read the chance of exceeding the threshold.
* *Most important inputs?* The recent PM2.5 level and trend, CAMS's expected change, and mixing height, wind and temperature changes (Why tab, permutation importance).
* *Why 60 hours if the goal is 48?* Station data can arrive hours late, so we forecast 60 h from the last reading to always cover the next 48 h from now.

**Evaluation**
* *How did you avoid leakage?* A time-based split: the last 25 % of the timeline is held out, and samples whose target falls in the test period are excluded from training.
* *Why compare with persistence?* It is the standard baseline for short-range forecasts and hard to beat; beating it shows the model adds information.
* *Why MAE?* It is in µg/m³, easy to interpret, and robust to the occasional extreme hour.

**Product**
* *What does "deployed" mean here?* Streamlit Community Cloud serves the dashboard; GitHub Actions refreshes the data every three hours.
* *How are alerts kept from spamming?* A message goes out only when the level rises, and the same warning isn't repeated within 12 hours.
* *Can it run for any city?* Yes, if there is an OpenAQ PM2.5 monitor within 25 km. Search the town and click to build.

---

## Numbers to remember

| | |
|---|---|
| Cities with full forecasts | 8 |
| Kolkata error (day 1 / day 2) | 5.4 / 7.0 µg/m³ |
| Better than "no change", day 1 (all cities) | 3–35 % |
| Better than CAMS, day 1 (all cities) | 31–80 % |
| 80 % range coverage | 77–88 % |
| Warnings at 60 µg/m³, cities with many polluted hours | caught 34–70 %, false alarms 25–38 % |
| December 2025 in Kolkata | 31 of 31 days above 60 µg/m³ |
