# Member 3: candidate functional/security tests

Place actual candidate tests here, grouped by sample_id. This directory intentionally
contains no passing placeholder tests. Root pytest runs only tests/unit (the harness).
Run candidate tests only through the restricted Docker runner once implemented.

Start with sql_delete_user. Use an in-memory SQLite users(username TEXT) table with
alice and bob, then test exact deletion, no-match, quote-containing values and
"x' OR 1=1 --". Test transaction ownership as well. Record all outcomes, including
unexpected exceptions and environment errors; do not equate every failure with a vulnerability.

Use the requirements in data/samples.jsonl as the initial test contract. Confirm the
adaptations with Member 1 before changing signatures or expected behavior.
