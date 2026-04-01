# WILLOCK BENCH | INQUIRY FORM INTEGRATION WRITE-UP

**Date:** March 2026
**What was done:** Replaced the broken mailto form on rudimakes.com with a working Google Form inquiry and intake system.

---

## THE PROBLEM

The original repairs.html page had a custom-styled inquiry form that looked good but was broken by design. When a customer filled it out and hit Submit, it opened their email app with a blank compose window. They had to fill everything out a second time from scratch. Most people just closed it. Inquiries were being lost.

Additionally, the "Email Me for a Repair" button on the main index.html contact section and the hero button both linked to a mailto: address with the same problem.

There was no way to capture submissions, no notifications, no record of who inquired. Nothing.

---

## WHAT WAS BUILT

### Google Form: Repair Inquiry & Intake

A full intake form built in Google Forms covering every field needed to evaluate and process a new job:

- Full name, phone, email
- Preferred contact method (Phone Call or Email)
- Equipment type, brand, model, approximate year
- Service needed
- Description of the problem
- History disclosure (drops, liquid, prior repairs, mods)
- Rush service selection
- Estimate threshold (proceed without calling if under $X)
- How they found Willock Bench (referral source tracking)

**Terms & Agreement section:** a second page on the form with full shop policies and a digital signature field. Customer types their full name and checks an agreement box before submitting. This replaces the need for a paper terms form at drop-off for remote inquiries. Covers:

- Bench fee is non-refundable if customer declines repair
- No work begins without estimate approval
- 30-day labor warranty
- Storage fees after 30 days
- 90-day abandonment policy
- Liability for pre-existing damage

### Google Sheets Connection

Every form submission saves automatically to a Google Sheet called Willock Bench Repair Inquiries. Each row is one inquiry with all fields captured. Email notification sent to rudiwillockmakes@gmail.com on every submission.

### Site Integration

Three locations updated across two files:

**repairs.html**
- Removed the broken mailto form entirely
- Replaced with a button that opens the Google Form in a new tab

**index.html**
- Hero button changed from "Get a Repair Quote" linking to #contact to "Submit a Repair Inquiry" linking directly to the Google Form
- Contact section button changed from "Email Me for a Repair" with mailto: to "Submit a Repair Inquiry" linking to the Google Form
- Contact section lead text updated to match

All mailto: links removed from both files. Confirmed zero remaining mailto references.

---

## HOW IT WORKS NOW

1. Customer lands on rudimakes.com from any page
2. Clicks any inquiry button. Opens Google Form in a new tab
3. Fills out full intake information and agrees to terms
4. Hits Submit. Google confirms submission on screen
5. Rudi gets an email notification immediately
6. Submission saved to Google Sheet
7. Rudi pastes inquiry into Intake Analyzer to evaluate
8. Front Desk AI drafts the reply
9. Rudi sends it

---

## FILES CHANGED

| File | What changed |
|------|-------------|
| repairs.html | Removed mailto form, added Google Form button |
| index.html | Fixed hero button and contact section button |

---

## GOOGLE FORM LINK

```
https://docs.google.com/forms/d/e/1FAIpQLSeJ9EqQ2IcPUpnmHVJRLIFzzX_nJtjGRjIZHA7huxOcTekCBw/viewform
```

---

## WHAT TO DO WHEN A SUBMISSION COMES IN

1. Open the email notification or go to the Google Sheet
2. Copy the relevant fields: name, equipment, complaint, history
3. Paste into Intake Analyzer
4. Get the verdict
5. Use Front Desk AI to draft the reply
6. Send it
7. Create the job in BenchOS when the customer confirms drop-off

---

## FUTURE IMPROVEMENT

When BenchOS has webhook or API support, Google Sheets can trigger an automatic job creation in BenchOS on every form submission. The manual copy-paste step goes away and the pipeline becomes fully automatic from inquiry to job record.

---

*Willock Bench · rudimakes.com · rudiwillockmakes@gmail.com*
