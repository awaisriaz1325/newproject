# Runbook: a wrong finding reached a customer

1. Mark the finding `rejected` with a note (reviewer endpoint); this removes it from new packages.
2. If a package containing it was approved or submitted, contact the customer the same day with a
   corrected package (new version) and a plain explanation. Never contact the carrier ourselves.
3. If a contingency fee was invoiced on an amount that included it, void/credit the difference in
   Stripe and record it.
4. Root cause: rule (citation wrong? → demote to `candidate`, bump `REGISTRY_VERSION`), extraction
   (add an evaluation case), or reviewer process. Add a golden test reproducing it.
