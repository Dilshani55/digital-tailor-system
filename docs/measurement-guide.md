# Measurement guide

What the measurement page asks for, how each value is taken, and which design needs it. The single definition is
`backend/config/measurement_requirements.json` (schema version 3); the backend, the web page and the tests read
that file, so the lists cannot drift apart.

## Units

* Choose **cm** or **inches** once, at the top of the page. Every field then shows that unit.
* A value is stored in centimetres (1 in = 2.54 cm exactly) together with the value and unit exactly as typed, so
  switching the unit never changes or rounds what was entered.
* Decimals with a point or a comma are accepted (88.5 or 88,5).

## Body measurements

The figure on the page shows a front view and a back view; the measurement being typed is highlighted on the view
where it is taken.

| Field | How to measure | Common mistake shown in the app | Needed for |
|---|---|---|---|
| Bust around | around the fullest part of the bust and across the shoulder blades, tape level, not tight | the tape slipping down at the back makes the number too small | every design |
| Waist around | around the natural waist, the narrowest part, usually just above the navel | measuring where trousers sit (that is lower) | every design |
| Shoulder to shoulder | across the back, from one shoulder tip to the other | following the curve of the neck instead of going straight across | every design |
| Back neck to waist | from the bone at the base of the neck straight down the centre back to the waist | not marking the waist (tie a string around it first) | every design |
| Garment length | from the shoulder beside the neck straight down the front to the wanted hem | treating it as a body measurement: it is the finished length wanted | every design |
| Hip around | around the fullest part of the hips and seat, feet together | measuring too high, at the hip bones | blouse, T-shirt |
| Waist to hip | at the side, from the waist down to the level where the hip was measured | using other levels than for the waist and hip measurements | blouse, T-shirt |
| Shoulder to bust point | from the shoulder beside the neck straight down to the fullest point of the bust | starting at the shoulder tip | blouse (it has bust darts) |
| Upper arm around | around the fullest part of the upper arm, arm hanging relaxed | flexing the arm | any sleeve |
| Sleeve length | from the shoulder tip down the outside of the arm to where the sleeve ends | starting at the neck | any sleeve |
| Sleeve end around | around the arm where the sleeve will end (upper arm for a short sleeve, wrist for a long one) | measuring at another place than the chosen sleeve end | plain and puff sleeves |

The exact wording shown in the app is in the configuration file (`guide` and `mistake` of each field).

## Design values (optional)

These are style choices, not body measurements. Leave them empty to use the value the drafting method calculates;
the page shows that value as "Calculated value". A typed value replaces it, and can be emptied again later.

| Field | Calculated when empty |
|---|---|
| Neckline width | bust ÷ 6 (twice the method's neck width of bust ÷ 12) |
| Front neck depth | bust ÷ 12 + ¼ in |
| Back neck depth | 1 in |
| Armhole depth | bust ÷ 4 − 1 in |
| Between bust points | bust ÷ 5 (the method's "about one tenth bust" each side) |

## What a design asks for

| Design | Required |
|---|---|
| any | bust, waist, shoulder to shoulder, back neck to waist, garment length |
| blouse or T-shirt | + hip, waist to hip |
| blouse | + shoulder to bust point |
| short or long sleeve | + upper arm, sleeve length |
| plain or puff sleeve | + sleeve end around |

In the pattern wizard, before a design is confirmed, the measurement step shows every field (as the Measurements
page does), so a new customer can be measured completely; fields only some designs need are marked "needed for
some designs". Choosing a saved customer in that step fills in their saved measurements; they can be changed there
and saving updates that customer's profile. A new customer's measurements are typed in the same step and saved as a
new profile, so the wizard never has to be left. Once the design is confirmed, only the fields that design uses
stay on screen.

A sleeveless design asks for no sleeve measurement. Nothing else is required and nothing is filled in with a
"standard" value: a missing required measurement is reported next to its field.

## Checks

* **Errors** (the value is refused): not a number, zero or negative, or a required value is missing.
* **Warnings** (the value is saved; "Please check"): a value outside the usual adult range – often inches typed
  as centimetres – or two values that contradict each other: shoulder to shoulder at least half of the bust,
  sleeve end larger than the upper arm, shoulder to bust point not shorter than back neck to waist, garment
  length shorter than back neck to waist. The usual ranges are only used for these hints; they never reject a
  body.
* There is no judgement about body shape or weight and no BMI.
* Some combinations cannot be drafted (for example a sleeve much wider than the armhole can take). The pattern
  step then explains which measurement to check; it never changes a value silently.

## Profiles saved by an earlier version

Earlier versions asked for neck around, height, one-shoulder length, across back and wrist. Those values are kept
in old profiles and still shown as stored, but the drafting method does not use them and they are never required.
An old profile does not contain the new fields (shoulder to shoulder, waist to hip, shoulder to bust point,
sleeve end): the page asks for them before a pattern is drafted. **No missing value is estimated.** One alias
exists: for a long sleeve, an old wrist measurement is used as "sleeve end around", because it is the same place
on the arm.

## Measurements that are not collected, and why

| Measurement | Reason |
|---|---|
| Neck around | the method derives the neck width from the bust; the neckline is a design value |
| Height | no formula of the method uses it |
| One-shoulder length (neck to tip) | replaced by shoulder to shoulder, which the method uses |
| Across front / across back | the method takes the back width from shoulder to shoulder and the front from it |
| Elbow around | sleeves are drafted without an elbow dart; the sleeve narrows straight from the upper arm to its end |

These limits are part of the method chosen, not measured facts about fit.
