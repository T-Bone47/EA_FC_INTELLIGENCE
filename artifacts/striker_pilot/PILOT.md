# FC27 striker comparison

The pilot compares the exact source cards below at striker in 4-3-3. Both appeared as primary strikers in the Phase 31 top 100 research cohort. Scores use the frozen FC27 card reference and V3.2.1. Tag the offline predictions and subsequent gameplay with protocol key `fc27-st-press-counter-r1`.

| Arm | Card | Source item ID | High press | Counterattack |
| --- | --- | --- | ---: | ---: |
| A | Ousmane Dembélé, Rare 90 | 231443 | 0.84518 | 0.86155 |
| B | Kylian Mbappé, Rare 91 | 231747 | 0.83194 | 0.87317 |

The engine led with A in high press by 0.01324 and B in counterattack by 0.01162. Both gaps exceed the engine's 0.005 tie tolerance. The scores and coverage describe modeled suitability. The tactical outcome hypotheses below require match evidence. Current matches in this pilot total zero.

| Tactic | Primary outcome | Secondary outcomes |
| --- | --- | --- |
| High press | The selected striker's tackles won per 90. Predict A leads B. | The striker's interceptions, shots on target and goals |
| Counterattack | The selected striker's shots on target per 90. Predict B leads A. | The striker's shots, goals and interceptions |

Count each selected striker's events using the available post-match player stats or reviewed footage. Use the same method for both cards. Tackles won are one observable component of pressing. Shots on target are counted across the entire match played under the counterattack setup. Enter zero only when the event was tracked and never happened. Leave missing observations blank.

## Play the eight matches

| Session | First block | Second block |
| --- | --- | --- |
| 1 | High press, Dembélé then Mbappé | Counterattack, Mbappé then Dembélé |
| 2 | Counterattack, Dembélé then Mbappé | High press, Mbappé then Dembélé |

1. Use `MATCH_SHEET.csv` and play the two sessions separately. Confirm the exact card version from the table before playing. If either version is unavailable, the frozen protocol stays pending.
2. Keep the same player/controller, opponent or AI difficulty, game mode, patch, team, striker role and playing time. Within each tactic, preserve all team instructions, chemistry conditions, and card boosts. Pick one striker role supported by both items in your build and write the actual role in the sheet. Keep it fixed across both tactics so the comparison targets the tactical setup. Use a repeatable mode where both exact items can play.
3. Before playing, record which in-game settings implement each tactic and give the setup a short anonymous key. Record the actual patch, match date, role, playing time and evidence locator. A screenshot filename or local video timestamp can identify the evidence without including anyone's account details.
4. If a disconnect, early substitution, chemistry change, or other deviation breaks a block's match conditions, mark both original rows with a deviation and copy both rows for a rerun. Keep their block, session, and order fields and give both rerun rows fresh match keys. Keep the original rows as a record of the deviation. A patch change starts a separate comparison.
5. Return the completed sheet and any evidence you choose to share. Reviewed rows can enter the Performance Evidence Lab as `CONTROLLED_EXPERIMENT`, with source `controlled`. Compare each tactic's rates separately. Record the raw counts, matched minutes, and whether the direction repeats across sessions. An eight-match pilot supports descriptive results and helps refine the measurement procedure.

## Reproduce the predictions

Run `python -m verification.prepare_fc27_striker_pilot` from the project root with backend dependencies installed. The generator reads the existing Phase 31 export and frozen card reference. The local API was offline when the prediction was frozen, so this uses the same scoring engine directly on the 15 eligible exported primary strikers. No engine or release data was changed.

## Evaluate a completed sheet

From the project root, run `python -m verification.evaluate_fc27_striker_pilot path/to/completed.csv`. Use `--predictions path/to/FROZEN_PREDICTIONS.json` to point to a separate frozen copy. The JSON report gives per-tactic paired rates, A-minus-B differences, session-level directions, and descriptive agreement with the model. Patch and setup differences appear as separate groups. A group needs both run orders in different sessions before reporting a pooled rate. These are unreviewed local results. Independently reviewed evidence can still be submitted to the lab.
