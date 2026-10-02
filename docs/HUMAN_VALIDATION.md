# Human validation — instructions and record sheets

Software tests show that the program does what it was written to do. They **cannot** show that a printed pattern is
the right size, that a garment fits a person, that the fabric estimate matches what a tailor really uses, or that
people find the system easy. Those need people. This page gives the procedure and an empty record sheet for each
check.

**Status of checks 1-4: Pending human validation.** None of them has been carried out (check 5 was done by one reviewer). Do not fill a sheet
with estimated, remembered or invented values: write only what was measured, and leave the rest blank. A sheet
without a name, a date and a signature is not evidence.

| # | Check | Who | Status |
|---|---|---|---|
| 1 | Printed scale (the 5 cm square and one pattern edge) | anyone with a printer and a ruler | Pending human validation |
| 2 | Muslin fit trial | a person who sews + the wearer | Pending human validation |
| 3 | Fabric consumption against a tailor's estimate and the cloth really used | a tailor | Pending human validation |
| 4 | Usability | 5 or more participants who have not used the system | Pending human validation |
| 5 | AI label review (collared neck, regular sleeve) | the project owner or a tailor | Done by one reviewer (725 photos); second-reviewer check pending |

Before any of them: participants agree in writing to take part; record no names in the system or in the thesis
(use P1, P2 ... and T1, T2 ...); body measurements are personal data and stay on this computer.

---

## 1. Printed scale

Purpose: the PDF file is at true scale (checked digitally by `backend\tools\verify_pdf.py`); this checks the
**printer**.

1. Create a pattern in the app and download the PDF.
2. Print pages 2 and one pattern tile on A4. In the print dialog choose **Actual size / 100 %**. Do not choose
   "Fit to page".
3. With a steel ruler measure the calibration square on both pages, across and down.
4. On the tile, measure one straight edge whose length the PDF states (for example the hem or the fold line).

Accept if every measurement of the square is 5.0 cm ± 0.1 cm (2 %). Otherwise the printer is scaling: correct the
setting and print again before cutting anything.

| Field | Record |
|---|---|
| Date | |
| Checked by (name, signature) | |
| Printer model / paper | |
| Print setting chosen | |
| PDF file name and pattern id | |
| `verify_pdf.py` result for this file (PASS / FAIL) | |
| Square on page 2: across (cm) / down (cm) | |
| Square on the tile: across (cm) / down (cm) | |
| Stated edge length (cm) / measured (cm) | |
| Accepted? (yes / no) | |
| Notes | |

---

## 2. Muslin fit trial

Purpose: whether a garment sewn from the pattern fits the person it was drafted for. The draft follows a published
course text with some project extensions ([pattern-drafting-method.md](pattern-drafting-method.md)); none of it has
been fit-tested, so this is the most important check.

1. Measure the wearer with a tape, following the guide in the app. Record the measurements below **as taken**.
2. Enter them, choose a supported design and a woven or knit fabric, generate the pattern and print it at 100 %
   (pass check 1 first).
3. Cut a test garment from inexpensive fabric of a similar weight (muslin / calico), with the grain as marked.
   Sew with the seam allowances printed on the pieces.
4. The wearer puts it on. Assess each point standing, with arms down and raised.

| Field | Record |
|---|---|
| Date / place | |
| Wearer code (P1 ...) and written consent (yes / no) | |
| Sewn by (name, experience in years) | |
| Design (garment, neckline, sleeve length, sleeve style) | |
| Fabric used for the test / fabric chosen in the app | |
| Fit preference chosen (close / regular / relaxed) | |
| Pattern id and PDF file | |
| Measurements entered (list each, with unit) | |

| Fit point | Too tight / correct / too loose | By about how much (cm) | Remark |
|---|---|---|---|
| Bust | | | |
| Waist | | | |
| Hip (if the hem reaches it) | | | |
| Shoulder length / shoulder seam position | | | |
| Neckline (lies flat? gapes?) | | | |
| Armhole (cuts in? too deep?) | | | |
| Sleeve cap (eased in without puckers? pulls?) | | | |
| Bicep | | | |
| Sleeve length (as wanted?) | | | |
| Garment length | | | |
| Darts (point at the bust? length?) | | | |
| Side seams hang straight? | | | |
| Seams that are sewn together: equal length? (shoulder, side, sleeve-to-armhole) | | | |

| Overall | Record |
|---|---|
| Wearable as sewn? (yes / with alterations / no) | |
| Alterations a tailor would make | |
| Assessed by (name, signature) | |

Report the result as observed for this one wearer and design. One trial does not validate the method.

---

## 3. Fabric consumption

Purpose: compare the system's fabric requirement with a tailor's own estimate and with the cloth actually used.
The system's layout is a heuristic; it is not claimed to be the minimum.

1. Give the tailor the design, the measurements and the fabric width only. The tailor writes an estimate
   **before** seeing the system's number.
2. Note the system's values for the same width from the fabric-estimate step.
3. If the garment is cut: lay the printed pieces on the real fabric as the tailor would, cut, and measure the length
   of cloth used.

| Field | Record |
|---|---|
| Date | |
| Tailor code (T1 ...), years of experience, consent (yes / no) | |
| Design and size (bust / waist / hip, garment length) | |
| Fabric type and width (36" / 45" / 60") | |
| Folded or open layout | |
| Tailor's estimate before seeing the system (m) | |
| System: layout length (cm) | |
| System: recommended purchase (m) | |
| Cloth actually used (cm), if cut | |
| Difference: tailor − system purchase (m) | |
| Difference: actually used − system layout length (cm) | |
| Tailor's remarks (print matching, nap, shrinkage allowed for?) | |
| Recorded by (name, signature) | |

Report differences as measured, per case. Do not state a percentage saving unless it comes from these sheets, and
state how many cases it is based on.

---

## 4. Usability

Purpose: whether a person who has not seen the system can produce a pattern, and where they get stuck.

Task given to each participant (read it out, do not help unless they are stuck for two minutes):
"Create a pattern for the garment in this photo for a customer with these measurements, find out how much 45-inch
fabric is needed, and download the pattern."

| Field | Record |
|---|---|
| Date | |
| Participant code (P1 ...), consent (yes / no) | |
| Background (tailor / sewing student / other), computer use (daily / sometimes / rarely) | |
| Device (laptop / phone) | |
| Task completed without help? (yes / with help / no) | |
| Time from sign-in to PDF download (min:s) | |
| Number of times help was needed, and at which step | |
| Errors made (wrong unit, wrong field, wrong design ...) | |
| AI suggestions: how many of the four were corrected by the participant | |
| Ease rating 1 (very hard) – 5 (very easy), as chosen in the app | |
| What was confusing (participant's words) | |
| What they would change | |
| Observer (name, signature) | |

Report the number of participants, how many completed the task, the times and ratings as recorded. With fewer than
about 10 participants report counts, not percentages.

---

## 5. AI label review

Purpose: two classes (collared neck, regular sleeve) had no trusted label in any dataset, so a person had to look at
candidate photos.

**Done on 1 Oct 2026**: 725 of 725 candidate photos answered by one reviewer (the project owner) in 24 minutes with
a local review screen. Answers: neckline - collared 278, other 62, unclear 49, off-shoulder 1; sleeve - regular 288,
other 18, unclear 16, puff 9, bell 4. The answers are stored in `backend/training/data/label_queue_m42/decisions.jsonl`
and are part of the training data of the neckline and sleeve-design models.

Still pending: a second reviewer. One fast reviewer gives labels with some noise (a later look at a sample found a
few jackets and coats among the answers), so the results for these two classes should be read with that in mind.

| Field | Record |
|---|---|
| Second reviewer for a sample of 50 (name, signature, date) | |
| Number of the 50 where the two reviewers disagree | |

How the labels are used and what the models achieve: [AI_MODELS.md](AI_MODELS.md).
