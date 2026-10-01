# TypeScript restock parity

Run `python -m pytest backend/tests/test_restock_parity.py -q` from the
repository root. This compares all 250 default-option results with
`pipeline/data/processed/restock.csv`: `restock_qty` must match exactly, and
the four numeric fields stored at two decimal places must be within 0.01.

When Node.js is installed, the same suite executes `lib/restock.ts` through the
project's `tsx` package for five fixed series and compares every returned field
with the Python implementation at full precision:

```powershell
python -m pytest backend/tests/test_restock_parity.py -k five_series -q
```

The TypeScript implementation returns `Infinity` for `days_of_cover` when
forecast demand is zero. The API substitutes the documented finite cap `1e9`
for that case so responses remain valid strict JSON; this still sorts after
finite cover values and gives the same `LOW` priority.
