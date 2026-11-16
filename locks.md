Lock 1: no data from 1 January 2021 onward is used before Phase 3.
Lock 2: locked market = emerging-market equities, series EEM.
Note (22-29 Oct 2026): this market was named after three earlier exposures.
- The LSEG ETF download (13 Oct) and the Yahoo download of 22 Oct
  (data/raw/yahoo-raw/2026-10-22_211506_universe) both include EEM. The files
  are not opened, and the cleaning code refuses EEM until Phase 3.
- Before the locks I had already seen daily prices from 2020-06 to 2025-05 for the
  19 instruments of Portfolio Risk Lab (github.com/niccolopa/Project-Portfolio_Risk_lab).
  EEM is not among them.

Correction (9 Nov 2026): the note added on 7 Nov says the lock is enforced in code. It is not
yet: cleaning_engine.py stops on a KeyError before reaching the check, and there is no test of
the refusal. This note becomes true when that test passes.

## Note, 16 Nov 2026: history rewritten
On 16 Nov 2026 the git history was rewritten with git filter-repo, to remove an LSEG file
(data/raw/lseg-raw/) that must not be redistributed and to replace the author email with
the GitHub noreply address. Commit dates and contents are otherwise unchanged; commit hashes
changed. The full old → new map is kept privately (commit-map_2026-11-16.txt).