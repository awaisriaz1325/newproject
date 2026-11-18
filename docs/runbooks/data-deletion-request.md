# Runbook: customer data deletion request

1. Verify the requester is an **owner** of the organization (or the account holder for user data).
2. Documents: owner can delete in-app (`DELETE /orgs/{org}/documents/{id}`), which removes the
   encrypted original, encrypted page images and encrypted derived text, and leaves a content-free
   tombstone (no filename, no hash) plus an audit entry.
3. Whole organization: run the org purge (Phase 10 admin command) — deletes all documents via the same
   path, then cases/findings, then memberships; audit log entries are retained (they contain no
   document content) unless counsel advises otherwise.
4. Backups: deleted data persists in database/object-store backups until the backup window expires
   (documented in the backup policy, Phase 10). State this window in the confirmation to the customer.
5. Confirm in writing with the date and the backup expiry date. Record the request in the audit log.
