# FC27 player reference

The built-in verifier rebuilt the FC27 research distribution from 19,789 PostgreSQL player rows and reproduced content hash `224e4474dc0e0b54e7a422774d536d3962e4ebc6a224ebe7143872a759ec305e`. The frozen artifact was identical and remains `fc27-players-2026-09-r1` in the player universe.

```sh
python scripts/build_reference_distribution_v3.py --game-version FC27 --verify
python scripts/build_field_provenance_v3.py --game-version FC27 --report /tmp/fc27-provenance.json
```

A distinct UT card reference is required for card-scope scoring. The acceptance fixture creates one using synthetic engineering inputs and exercises the same V3.2 scoring pipeline. There is currently no approved real-card reference.
