# Run report

**Totals:** 34 input / 2665 output tokens, 26270 cache-read, 12320 cache-write, 33.545s wall-clock.

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously matched Juniper Tools (V5). Saved new address draft for request X1 (10 New Street, Newtown, 11111, Exampleland) on first attempt; verified via read_drafts that the draft was persisted correctly with no changes to vendor identity or original address.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: The request for vendor V5 is missing a required field: 'country' is empty. Per policy, all address fields (line1, city, postal_code, country) must be nonempty before a draft can be saved. No draft was created; please resupply the country value to proceed.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X2.json

## X3a
- status: `draft`
- reason: Draft successfully created and verified for request_id DUP-1, vendor V1 (Cedar Office), with new address 20 New Street, Newtown, 44444, Exampleland. Original address left unchanged.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X3a.json

## X3b
- status: `duplicate`
- reason: Request_id DUP-1 already has an existing draft (20 New Street, Newtown, 44444, Exampleland). Per duplicate-prevention rules, the new submission (99 Changed Street) was not saved, and the original draft remains unchanged. new_drafts=0.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Vendor V2 (Northstar Supplies East) resolved unambiguously. First save attempt failed due to simulated failure switch; retried once successfully. Verified via read_drafts that request X4 now has a saved draft with the new address (12 New Street, Newtown, 33333, Exampleland), original address untouched, vendor ID/name unchanged, and no duplicate was created.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
