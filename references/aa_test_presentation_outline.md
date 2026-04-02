# A/A Test Results: Presentation Outline

## Audience
DE and NL analytical teams, campaign managers, stakeholders deciding which evaluation technique to use per segment/market.

## Key message
V3 Customer Lookalike is reliable for engaged/early customers but fundamentally broken for sparse segments. City Lookalike (BSTS) shows near-zero bias across all preliminary runs — a strong candidate for segments V3 can't handle.

---

## Slide 1: Title
**A/A Test Results: How Accurate Are Our Synthetic Controls?**
Phase 1 Accuracy Benchmarking — V3 Customer Lookalike & City Lookalike (BSTS)

---

## Slide 2: Why A/A Testing?
- We use synthetic controls to estimate campaign incrementality when A/B tests aren't feasible
- But how much error does the methodology itself introduce?
- An A/A test runs the exact same matching/modelling on a period with **no campaign** — expected result is zero uplift
- Any non-zero result = inherent measurement bias we can't distinguish from a real campaign effect

---

## Slide 3: What We Tested
- **V3 Customer Lookalike**: 1:1 customer matching (exact match + KNN fallback)
- **City Lookalike (BSTS)**: MAVERICK city selection + CausalImpact time-series model
- Same pre-campaign windows, same markets (DE + NL), derived from actual campaign calendar
- V3: 80 runs (16 windows x 5 random seeds)
- City: 48 runs (16 windows x 3 cities per market), preliminary

---

## Slide 4: Pass/Fail Criteria

| Verdict | Condition |
|---------|-----------|
| PASS | |mean uplift| ≤ 2% AND 95% CI contains zero |
| WARNING | |mean uplift| > 2% OR 95% CI excludes zero |
| HARD FAIL | |mean uplift| > 5% |

---

## Slide 5: V3 Customer Lookalike — Total Level
- **+1.1% mean uplift** across 159 runs → PASS
- But this total number is misleading...
- *Visual: histogram of total-level uplift distribution centered near zero*

---

## Slide 6: V3 Customer Lookalike — The Segment Story
- The total-level result hides segment biases that cancel each other out
- *Visual: horizontal bar chart showing mean uplift per segment, colored by verdict*

| Segment | Mean Uplift | Verdict |
|---------|-------------|---------|
| engaged | +0.4% | PASS |
| early | +0.5% | PASS |
| dormant | -4.0% | WARNING |
| reactivated | -5.1% | HARD FAIL |
| lapsing | +10.6% | HARD FAIL |
| new | +11.8% | HARD FAIL |
| churned | +51.2% | HARD FAIL |
| prospect | +92.4% | HARD FAIL |

---

## Slide 7: Why Does V3 Fail for Sparse Segments?
- Churned/new/prospect customers have 0-2 orders in the lookback
- All their features (L14D, L30D, L90D orders) are near-zero
- Exact matching groups everyone with zero orders together — match is trivially perfect but uninformative
- Small absolute differences → extreme percentage uplifts (3 orders vs 2 = +50%)
- The bias is **systematically positive** because the ratio of two small random numbers is right-skewed
- *Visual: scatter plot of segment bias vs exact match coverage — high match % + high bias = red flag*

---

## Slide 8: V3 — Stability Across Time
- Bias is consistent across windows — not driven by seasonality or specific periods
- *Visual: box plot of uplift by time window (total level)*
- Levene test: variance consistent across windows (PASS)
- Kruskal-Wallis: medians consistent across windows (PASS)
- Conclusion: the bias is structural, not temporal

---

## Slide 9: V3 — DE vs NL
- Both markets show similar patterns
- *Visual: side-by-side box plots DE vs NL*
- No significant difference between markets (Mann-Whitney U test)
- Conclusion: the methodology bias is market-independent

---

## Slide 10: City Lookalike (BSTS) — Preliminary Results
- [N] runs completed across DE [+ NL]
- Total-level mean uplift: [X]% → [VERDICT]
- *Visual: bar chart of uplift per city/window*
- All results within ±2% so far
- No systematic directional bias — fluctuations are symmetric around zero

---

## Slide 11: Why Does City Lookalike Perform Better?
- Unit of analysis is **entire city**, not individual customer
- Individual-level noise (one churned customer placing a random order) is smoothed in city aggregates
- BSTS builds a time-series counterfactual — captures trends and seasonality naturally
- MAVERICK KNN + correlation filter ensures control cities track treatment city closely
- Does not depend on individual customer order history → works for all segments

---

## Slide 12: Head-to-Head Comparison

| Dimension | V3 Customer Lookalike | City Lookalike (BSTS) |
|-----------|----------------------|----------------------|
| Total-level bias | +1.1% (PASS) | ~[X]% (preliminary) |
| Engaged/Early | PASS (<1%) | N/A (total only so far) |
| Churned/New/Prospect | HARD FAIL (10-92%) | Expected PASS (city-level smoothing) |
| Requires customer history | Yes | No |
| Captures spillover | No | Yes |
| Statistical framework | None (ratio only) | BSTS with posterior intervals |

---

## Slide 13: What This Means for Production Evaluations

**Use V3 Customer Lookalike for:**
- Engaged and Early segments (bias < 1%)
- Quick retrospective evaluation of campaigns targeting existing customers

**Do NOT use V3 for:**
- Churned, prospect, new, lapsing segments (bias > 5%)
- Any campaign where total-level uplift is the only reported metric

**Use City Lookalike (BSTS) for:**
- Segments without order history (churned, prospect, new)
- City-wide campaigns (Flash Sales, OMT)
- When statistical confidence intervals are needed

---

## Slide 14: Recommended Evaluation Framework

| Campaign targets... | Technique | Confidence |
|---------------------|-----------|------------|
| Engaged customers | V3 Customer Lookalike | High |
| Early customers | V3 Customer Lookalike | High |
| Dormant customers | V3 with bias correction (accuracy TBD — prior -4% claim was circular) | Medium |
| Lapsing customers | City Lookalike | Pending A/A |
| New/Churned/Prospect | City Lookalike | Pending A/A |
| All segments (total) | Both — cross-validate | Medium |
| Flash Sales / OMT | City Lookalike | Pending A/A |

---

## Slide 15: Next Steps
1. **Complete City Lookalike A/A** — finish all 48 runs, add per-segment analysis
2. **Run comparison notebook** — formal cross-technique statistical comparison
3. **Test geographical constraint for V3** — restrict lookalike pool to similar cities (Phase 2 optimisation)
4. **Align with markets** — agree on per-segment technique recommendations across DE, NL, UK
5. **Automate bias checks** — reject any production evaluation where |pre-period uplift| exceeds threshold

---

## Slide 16: Appendix — A/A Test Configuration

| Parameter | Value |
|-----------|-------|
| Markets | DE, NL |
| V3 windows | 10 (DE), 6 (NL) |
| V3 seeds per window | 5 |
| V3 audience size | 200,000 per run |
| City windows | 10 (DE), 6 (NL) |
| City treatment cities | Dortmund, Dresden, Essen (DE); Amsterdam, Eindhoven, Nijmegen (NL) |
| City control cities | Top 25 KNN, filtered by correlation ≥ 0.8 |
| Bias threshold (WARN) | 2% |
| Bias threshold (FAIL) | 5% |

---

## Slide 17: Appendix — V3 Bias Correction Table

If V3 must be used for all segments, subtract the A/A-measured bias:

| Segment | A/A Bias | If V3 measures +5% | Adjusted |
|---------|----------|---------------------|----------|
| engaged | +0.4% | 5% - 0.4% | +4.6% |
| early | +0.5% | 5% - 0.5% | +4.5% |
| dormant | -4.0% | 5% + 4.0% | +9.0% |
| lapsing | +10.6% | 5% - 10.6% | -5.6% ← negative = no real effect |
| churned | +51.2% | — | Do not use |

Caveat: corrections are averages across 80 runs. Actual bias may vary by campaign.
