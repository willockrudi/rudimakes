# WILLOCK BENCH — FORMS REFERENCE

**For all agents. These are the three forms used in every repair job. Know the fields, know who fills what, know what flows where.**

---

# FORM 1 — INTAKE FORM

**Filled by:** Rudi (at intake)
**Given to:** Bench Tech AI (as starting context for diagnosis)
**Stored in:** BenchOS → job_intake table

---

## JOB

| Field | Value |
|-------|-------|
| Job # | |
| Date Received | |
| Rush Service (+$35) | ☐ Yes  ☐ No |

## CUSTOMER

| Field | Value |
|-------|-------|
| Name | |
| Phone | |
| Email | |
| Preferred Contact | ☐ Phone  ☐ Text  ☐ Email |
| Referral Source | |

## EQUIPMENT

| Field | Value |
|-------|-------|
| Type | ☐ Tube Amp  ☐ Solid State  ☐ Bass Amp  ☐ Guitar  ☐ Bass  ☐ Pedal  ☐ Synth/Keys  ☐ Mixer  ☐ Rack Gear  ☐ Speaker Cab  ☐ Other: |
| Brand | |
| Model | |
| Serial # | |
| Year (approx) | |
| High Voltage | ☐ Yes  ☐ No |

## ACCESSORIES RECEIVED

☐ Power cable  ☐ Speaker cab  ☐ Footswitch  ☐ Case/cover  ☐ Tubes (separate)
☐ Other: _____________

## CUSTOMER COMPLAINT

*(Their words — what they say is wrong)*

&nbsp;

**When did the problem start?**

&nbsp;

## HISTORY & CONDITION

| Question | Answer |
|----------|--------|
| Drop or liquid damage? | ☐ No  ☐ Yes → detail: |
| Modifications? | ☐ No  ☐ Yes → detail: |
| Prior repairs? | ☐ No  ☐ Yes → by who: ________  ☐ Unknown |
| Original tubes? | ☐ Yes  ☐ No  ☐ N/A  ☐ Unknown |
| Last retube (approx) | |

**Cosmetic condition:**

&nbsp;

## INITIAL OBSERVATIONS

*(Filled by Rudi during intake — quick bench check)*

| Check | Result |
|-------|--------|
| Powers on | ☐ Yes  ☐ No |
| Passes signal | ☐ Yes  ☐ No  ☐ Partial |
| Blows fuse | ☐ Yes  ☐ No |
| Intermittent | ☐ Yes  ☐ No |
| Burn/smoke smell | ☐ Yes  ☐ No |
| Noise / Hum / Distortion | |
| Problem occurs | ☐ Always  ☐ Cold  ☐ Warm  ☐ Intermittent  ☐ Under load |

**Quick checks performed:**

| Check | Done | Notes |
|-------|------|-------|
| Known good cable | ☐ | |
| Known good speaker/load | ☐ | |
| FX return / power amp test | ☐ | |
| Jacks cleaned | ☐ | |
| Tubes swapped | ☐ | |
| Visual inspection | ☐ | |

**Obvious issue found?** ☐ No  ☐ Yes →

## INITIAL MEASUREMENTS

*(Fill if taken at intake — otherwise Bench Tech AI will guide these during diagnosis)*

| Rail / Point | Reading |
|-------------|---------|
| B+ | |
| Plate voltage | |
| Screen voltage | |
| Bias voltage | |
| Heater voltage | |
| ±15V rails | |
| 5V rail | |
| 3.3V rail | |
| DC offset at speaker | |

## AUTHORIZATION

| Field | Value |
|-------|-------|
| Estimate threshold | $ _______ (proceed without calling if under this amount) |
| Call before any work | ☐ Yes  ☐ No |
| Terms signed | ☐ Yes  ☐ No |

## JOB CLASSIFICATION

**Job type:** ☐ Quick fix  ☐ Standard repair  ☐ Diagnosis only  ☐ Intermittent  ☐ Previous repair cleanup  ☐ Restoration  ☐ Quoted job  ☐ Rush

**Risk level:** ☐ Low  ☐ Medium  ☐ High  ☐ Parts risk  ☐ Intermittent  ☐ Previous repair

**Estimate category:**
☐ Bench fee / diagnosis — $45
☐ Retube + bias (combo) — $65 + tubes
☐ Retube + bias (head) — $85 + tubes
☐ Bias only — $45
☐ Power supply recap — $95–150 + parts
☐ Speaker replacement — $45 + parts
☐ Hum / noise troubleshooting — $65/hr
☐ General repair — $65/hr
☐ Guitar/bass electronics — $35–65
☐ Pedal repair — $55/hr
☐ Synth repair — $65/hr
☐ Quoted job
☐ Not economical — warn customer

## SHOP USE

| Event | Date | Notes |
|-------|------|-------|
| Received by | | |
| Bench fee collected | ☐ | |
| Estimate given | | |
| Estimate approved | ☐ | |
| Parts ordered | | |
| Parts received | ☐ | |
| Repair completed | | |
| Customer contacted | | |
| Picked up | | |

**Intake tech notes:**

&nbsp;

---

*$45 bench fee — applied to repair if authorized, non-refundable if declined.*
*30-day labor warranty. Parts warranties per manufacturer.*
*Equipment unclaimed after 90 days may be surrendered.*

---

---

# FORM 2 — REPAIR DONE FORM

**Filled by:** Bench Tech AI (from conversation with Rudi + BenchOS data)
**Given to:** Customer (summary section), Shop records, Site Manager AI (for website story)
**Stored in:** BenchOS → job_diagnostics + job_repairs + job_parts tables

---

## JOB INFO

| Field | Value |
|-------|-------|
| Job # | |
| Date Received | |
| Date Completed | |
| Customer | |
| Phone / Email | |

## EQUIPMENT

| Field | Value |
|-------|-------|
| Brand / Model | |
| Serial # | |
| Category | |
| Year (approx) | |

## CUSTOMER COMPLAINT

*(From intake form — what they told us was wrong)*

&nbsp;

## DIAGNOSTIC FINDINGS

| Field | Value |
|-------|-------|
| Symptom Summary | |
| Observed Behavior | |
| Safety Flags | ☐ None  ☐ HV caps charged  ☐ Mains exposed  ☐ DC on chassis  ☐ Other: |
| Fault Area | |
| Root Cause | |

**Detailed Findings:**

&nbsp;

## REPAIR PERFORMED

**Repair Summary** *(one line, plain English — this goes to the customer):*

&nbsp;

**Work Performed** *(detailed — for shop records and future techs):*

&nbsp;

| Field | Value |
|-------|-------|
| Modifications Corrected | |
| Prior Bad Repair Found | ☐ No  ☐ Yes → detail: |
| Calibration / Bias Notes | |

## PARTS REPLACED

*(From BenchOS job_parts — Rudi provides this list)*

| Part | Specification | Qty | Source |
|------|--------------|-----|--------|
| | | | |
| | | | |
| | | | |

**Tubes Installed** *(if applicable):*

| Position | Type | Brand |
|----------|------|-------|
| | | |
| | | |

## TESTING

| Test | Result |
|------|--------|
| Signal test | ☐ Pass  ☐ Fail  ☐ N/A |
| Load test | ☐ Pass  ☐ Fail  ☐ N/A |
| Burn-in test | ☐ Pass  ☐ Fail  ☐ N/A  — Hours: |
| Noise test | ☐ Pass  ☐ Fail  ☐ N/A |

**Final Test Notes:**

&nbsp;

**Final Result:** ☐ REPAIRED  ☐ PARTIAL  ☐ NOT REPAIRABLE  ☐ COULD NOT REPRODUCE  ☐ CUSTOMER DECLINED

## COST

*(From BenchOS estimate/invoice)*

| Item | Amount |
|------|--------|
| Bench Fee | $ |
| Labor ( ____ hrs × $ ____ /hr) | $ |
| Parts | $ |
| Rush Fee | $ |
| **Total** | **$** |

**Payment:** ☐ Cash  ☐ Venmo  ☐ PayPal  ☐ Card

## WARRANTY

30-day labor warranty from date of completion.
Parts warranties per manufacturer.

## TECH NOTES *(internal — does not go to customer)*

&nbsp;

## CUSTOMER SUMMARY *(plain English — goes to customer)*

*(1–3 sentences. No heavy technical language. What was wrong, what was done, what to expect.)*

&nbsp;

---

**Technician:** Rudi Willock — Willock Bench
**rudiwillockmakes@gmail.com — rudimakes.com**

---

---

# FORM 3 — SERVICE RECORD CARD

**Filled by:** Bench Tech AI (from repair conversation)
**Lives:** Inside the unit (taped to chassis, tucked in cabinet, etc.)
**Purpose:** Any future tech — including Rudi — knows what was done and when

---

## STANDARD CARD *(print on cardstock)*

```
══════════════════════════════════════════
 WILLOCK BENCH — SERVICE RECORD
══════════════════════════════════════════

 Job:          _______________
 Date:         _______________
 Tech:         Rudi Willock

 Equipment:    _______________
 Serial:       _______________

 SERVICE PERFORMED:
 _________________________________________
 _________________________________________
 _________________________________________

 PARTS REPLACED:
 _________________________________________
 _________________________________________
 _________________________________________

 TUBES INSTALLED:         BIAS SET TO:
 ________________________ _______________

 NOTES:
 _________________________________________
 _________________________________________

 WARRANTY: 30 days labor

 rudimakes.com
 rudiwillockmakes@gmail.com
══════════════════════════════════════════
```

## MINI STICKER *(for pedals and small gear)*

```
┌──────────────────────────────┐
│  SERVICED BY WILLOCK BENCH   │
│  Date: ___________           │
│  Work: _____________________ │
│  Tech: RW                    │
│  rudimakes.com               │
└──────────────────────────────┘
```

## WRITING GUIDE — SERVICE PERFORMED

Keep it short. Use standard phrases:

| Situation | Write |
|-----------|-------|
| Retube | Retubed + bias set |
| Power supply | Power supply rebuilt |
| Filter caps | Filter caps replaced |
| Output section | Output transistors replaced |
| Jack repair | Input/output jack replaced |
| Pot cleaning | Pots cleaned + exercised |
| Noise fix | Noise issue repaired — [detail] |
| Intermittent fix | Intermittent connection repaired |
| Full service | Full service + test |
| Restoration | Partial/full restoration |
| Mod | [Mod name] installed/removed |
| Recap | Full/partial recap |
| No fault found | Tested OK — no fault found |

## WRITING GUIDE — NOTES

Use this section for things a future tech needs to know:

- Bias readings and settings
- Mod status ("original circuit" or "has [mod name]")
- Known quirks ("reverb pan microphonic but functional")
- Component substitutions ("used 560Ω at R33, original spec 470Ω")
- Anything unusual about the build or revision
- Prior repair observations ("previous tech re-capped with incorrect values")

## BENCH TECH AI INSTRUCTION

When Rudi says **"Create Service Record Card"** or **"Create job card"**: fill out the standard card template using all information from the current conversation. Keep SERVICE PERFORMED to 2–4 lines max. Keep PARTS REPLACED to a clean list. Keep NOTES to things a future tech actually needs. The whole card should fit on a half-sheet of cardstock or a large label.

---

*Willock Bench — rudimakes.com — rudiwillockmakes@gmail.com*
