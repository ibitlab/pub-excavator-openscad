**English** · [Українська](SAFETY.uk.md)

# Safety: the known hazards of this particular design

> ⚠️ **Everything in this repository was generated and computed by AI, none of it has been checked by a qualified engineer, and no machine has ever been built or tested from this model.** The full disclaimer is in [README.md, section Disclaimer](README.md#disclaimer). Whatever you do with this material, you do at your own risk and on your own responsibility.

This file is not general advice about being careful. It is a list of **the specific places where this design is currently unfinished or rests on assumptions**. It exists so that you do not find out about them through an injury.

## 1. Gaps that must be closed while you are still doing the hydraulics

| Hazard | What exactly is wrong | What to do |
|---|---|---|
| **The boom drops when a hose fails** | The design has **no load-holding valves** (lock valves, hose-burst valves). If a boom cylinder hose bursts or blows off under load, the boom and bucket come down at whatever speed the oil can escape. This is exactly how people are killed — standing or working under a raised boom. | Fit hose-burst / load-holding valves directly onto the boom and stick cylinders. Until they are there, **never go under a raised boom**, and prop it mechanically for any maintenance. |
| **Overpressure in a closed cylinder** | The Z50 valve has **no port relief valves**. Under an external load (a shock through the bucket, ground settling, a lever effect from the tooth) a closed boom cylinder can see **250–335 bar** instead of the 160–180 bar working pressure. The calculation accounts for this, but the safety factor at the worst section drops to 1.52. | An external block of cross-over relief + anti-cavitation valves (G3/8, 220–250 bar) on the boom cylinder lines. Set the main relief to 160–180 bar. |
| **A pinhole jet of hydraulic oil** | A pinhole in a hose produces a thin, invisible jet that **penetrates skin** and injects oil into the tissue. It looks like a small dot and hurts only moderately — and a few hours later it is an amputation if it is not operated on. | Never search for a leak with your hand or a finger — use a piece of cardboard. Release the pressure before dismantling anything. If you suspect an injection, **go to a surgeon immediately** and say it is pressurised hydraulic oil. |

## 2. The assumptions the calculations rest on

- **The mass of the machine is unknown.** The stability cap `F_STAB` in `tools/strength.py` is set to **15 kN, which is a guess**. The real forces and the tipping moment depend on the mass and wheelbase of the trailer. Without that number the vertical load cases are **meaningless**. Recompute after weighing it.
- **The cylinder lengths are nominal.** 700 / 600 / 510 mm come from the vendor description, which says "≈". The real pin-to-pin lengths must be **measured** and entered: every angle range and every clearance depends on them.
- **The boom cylinder eye size is a guess.** ШС-30 was inferred from comparable parts. If it turns out to be Ø25, then `boom_cyl_pin` and `pin_A` change, and clevis D with them.
- **The side force at the tooth is taken as 3 kN.** That is an estimate for swinging the column with the bucket in the ground. The real value depends on a swing mechanism that does not exist yet.
- **The bucket lip clearance is 7 mm** at +4° of cylinder over-travel. If the real extended length of the bucket cylinder exceeds 810 mm, the lip may reach the stick. Check with `tools/bucket.py`.

## 3. What the model does not check at all

- **The swing column is schematic** and is part of no check whatsoever — neither strength nor collision.
- **The moving pairs are checked at discrete positions** (13 bucket angles, 12 stick, 8 boom), not continuously. Between the checked points a collision is theoretically possible.
- **The fit between plates has only been checked visually** on the renders; the only thing checked numerically is that parts do not overlap.
- **Pin retention and grease nipples were deliberately deferred.** A pin that walks out of a clevis under load means that member collapses. Work out the retention (split pins, keeper plates, circlips) before you lift anything for the first time.
- **There is no operator protection**: no ROPS/FOPS, no guarding, no emergency pressure dump, no lockout against accidentally knocking a control lever.
- **Fatigue was not calculated.** Every check is static. An excavator works in cycles, and welds fail by fatigue at stresses far below the yield point.

## 4. Materials you must not economise on

- **The bucket cutting edge and teeth must be wear-resistant steel only** (Hardox 400/450, 65Г, a grader blade). Mild steel on the edge wears away in hours, and a mild-steel tooth bends and tears off.
- **The boom tube must not be rimming steel (Ст3кп).** Rimming steel is brittle in the cold and welds badly. Ask for a certificate: Ст3сп/пс or S235JRH.
- **The joint between the two boom segments** sits in the zone of the highest moment. It needs bevelled edges and **full penetration**, otherwise the weld will open under load. This is work for a certified welder, not a few tacks with a MIG gun.
- **The pins** must be king pins in induction-hardened 45Х or tempered 40Х. A pin in plain mild steel will shear.

## 5. The minimum before you lift anything with this machine

1. A qualified mechanical engineer has reviewed the calculations and the drawings.
2. A certified welder did the welding, and the critical welds have been inspected.
3. A specialist assembled the hydraulics; load-holding valves and overpressure protection are in place.
4. Every pin is retained, every joint has a grease nipple and has been greased.
5. The first load is taken on the ground, gradually, **with nobody within reach of the boom**.
6. Before every start-up, inspect the welds at the stick root, near base H and in the boom break zone: those are the places with the smallest margin.

## 6. If something turns out to be wrong

Nothing in this repository is grounds for treating the design as verified. If you find an error in a calculation or a drawing, fix it in the model and rebuild the version; do not edit the generated files by hand.
