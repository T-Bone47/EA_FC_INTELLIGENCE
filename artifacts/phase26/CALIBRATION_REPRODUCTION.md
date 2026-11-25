# FC26 calibration reproduction

Command: `python artifacts/phase26/reproduce_calibration.py` (Python 3.12+).
Input: local FC26 foundation CSV, frozen FC26 player reference, shipped default V3.2 policy. Dataset rights remain UNVERIFIED. Repeat the repository RD-3/RD-4 capability-only protocol with average-rank Spearman correlations using Python statistics. These correlations measure association with OVR, not a scoring input or a gameplay outcome.

| Position | Pool | PRESSING | POSSESSION | LOW_BLOCK | PACE_ABUSER | DIRECT_PLAY | Spread | Mean top-10 overlap¹ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CB | 6324 | 0.835725 | 0.843590 | 0.911112 | 0.817351 | 0.861953 | 0.093761 | 4.60 |
| CM | 5654 | 0.863349 | 0.924608 | 0.773221 | 0.886947 | 0.912607 | 0.151387 | 5.70 |
| ST | 5241 | 0.877095 | 0.950063 | 0.829493 | 0.893325 | 0.922889 | 0.120570 | 4.40 |

¹ Mean number of shared player names across ten pairs of top-ten lists, following the existing test.

## Outstanding policy findings

- RD-3 CB exceeds the registered [0.35, 0.85] band.
- RD-4 CB spread 0.093761 is below 0.10.
- RD-3 CM exceeds the registered [0.35, 0.85] band.
- RD-3 ST exceeds the registered [0.35, 0.85] band.

No parameter or threshold changes. The release owner retains responsibility for RD-3 and CB responsiveness.
