# Run report

**Totals:** 34 input / 2686 output tokens, 26223 cache-read, 12308 cache-write, 30.685s wall-clock.

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously resolved to Juniper Tools (V5). Address draft saved successfully on first attempt and verified via read_drafts: line1='10 New Street', city='Newtown', postal_code='11111', country='Exampleland'. No duplicate existed prior to save.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: Request X2 for vendor V5 is missing the required 'country' field (empty string). Cannot save an address update with an empty required field. Please provide the country value before resubmitting.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X2.json

## X3a
- status: `draft`
- reason: Draft successfully created and verified for request_id DUP-1, vendor V1 (Cedar Office), with new address 20 New Street, Newtown, 44444, Exampleland. Save succeeded on first attempt; no retry needed.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X3a.json

## X3b
- status: `duplicate`
- reason: A draft for request_id DUP-1 already exists (vendor V1, original address '20 New Street, Newtown, 44444, Exampleland'). Per rules, no new draft was created; the existing draft remains unchanged. new_drafts=0.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Vendor V2 (Northstar Supplies East) resolved unambiguously. First save attempt failed due to simulated failure switch; retried once and succeeded. Verified via read_drafts that request_id X4 now has a draft with address 12 New Street, Newtown, 33333, Exampleland, vendor_id V2, with original address untouched.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
