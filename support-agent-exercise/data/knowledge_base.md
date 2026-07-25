# Nimbus Cloud Storage — Support Knowledge Base

## Password reset
Go to nimbus.example.com/reset, enter your account email, and follow the
link sent to your inbox. Links expire after 30 minutes. If no email
arrives within 5 minutes, check spam, then try again.

## Sync issues
1. Confirm the desktop app shows "Connected" (not "Paused" or "Offline").
2. Restart the Nimbus sync app.
3. Clear the local sync cache: Settings -> Advanced -> Clear Cache.
4. Reinstall the desktop client if the above doesn't resolve it.
If a customer says they've already tried these steps and sync is still
broken, do not repeat the same steps -- this needs a human engineer.

## Storage limit reached
Free plan: 5 GB. Pro plan: 100 GB. Team plan: 1 TB (1000 GB) shared across
seats. When a customer is at or near their limit, they can delete files,
empty Trash (see below), or upgrade their plan. Do not offer a refund or
credit for hitting a storage limit -- that is expected behavior, not a bug.

## Accidental deletion / data recovery
Deleted files go to Trash and are recoverable for 30 days, after which
they are permanently purged and cannot be recovered by anyone, including
support. Instruct the customer to check Trash first.

## Billing and failed payments
If a payment fails, we retry automatically 3 times over 7 days. Customers
can update their card at nimbus.example.com/billing. After 2 failed
attempts, the account is flagged past_due but not yet suspended -- it
suspends after the 3rd failure. Refunds for accidental charges under $50
can be processed directly; refunds of $50 or more require billing-team
approval (create a ticket, do not promise a refund yourself).

## Account security / suspicious activity
Any report of a suspicious login, unrecognized device, or possible
account compromise must be escalated to the security team immediately.
Do not attempt to troubleshoot this via the knowledge base -- use the
escalate_to_human tool right away, even before checking the account.
