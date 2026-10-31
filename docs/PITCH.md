# 3-minute pitch

Speaker notes. The times are targets. Every number is from `artifacts/evidence/` (see README).

## 0:00–0:20 · The analyst (landing page on screen)

"Meet a conjunction-assessment analyst at a satellite operator. Every close approach sends them a stream of
warnings: several messages per event. About two days before closest approach they have to decide: plan a
manoeuvre, or not.
Each light in this sky is a real close approach from the ESA test set. The red ones are Critical right now."

## 0:20–0:50 · Why it's hard

"Labelling one message is easy. Miss distance alone decides almost every tier. The hard part is the two-day
decision. If you act on what you see at two days, you miss 99 of the 551 events that end Critical. In ESA's 2019
competition on this data, 'copy the latest message' was a hard baseline to beat."

## 0:50–1:50 · Demo (click "Open the queue", then "Guided demo")

1. **Clear Critical (event 1813).** "The tier, the rule that fired in plain words, the probabilities, and the
   message history with the two-day line."
2. **Caught early (event 1387).** "Today it looks Elevated. The forecast says Critical at closest approach. Here's
   the orbit pair on the globe, and here's what would change the tier."
3. **Where we fail (event 1947).** "Placeholder covariance and only two messages: this is the pattern we miss in
   testing. So we don't give a confident answer. The tier set holds more than one tier, and it goes to the
   analyst." Then click Accept and show the audit entry.

"The brief is written by an LLM, but it only restates computed facts. Any number it invents is caught, and the
template is shown instead. The model and the rules decide; the analyst signs."

## 1:50–2:35 · Results (Results tab)

- "Per message, on the organisers' test set: same 100% Critical recall as the baseline rule, with false alarms on
  Safe messages down from 29% to 7%."
- "Forecasting at two days: we tie the best simple baseline at equal budget. We don't claim to beat it. What we add
  is a guarantee: at most 5% of Critical events missed, measured at 3.3% in held-out folds. On the real test labels
  it missed 2 of 17, so that guarantee didn't fully hold, but neither event was dismissed. Both went to the
  analyst."
- "Against ESA's released labels, scored once: of 17 events that ended Critical, we dismissed none. The baseline
  missed 8. The price is precision. We flag far more events than it does, and the Results page says so."

## 2:35–3:00 · Impact and limits

"At a cost ratio of 100 to 1, expected cost per event falls from 1.26 to 0.40 manoeuvres' worth, and missed
Critical events from 1.19 to 0.22 per hundred. The cost is about 11 more manoeuvres and 11 analyst reviews per
hundred events, and the slider shows the trade-off.
Limits: radial uncertainties only, and late miss-distance collapses we can't foresee. OrbitGuard is decision
support. The analyst decides."
