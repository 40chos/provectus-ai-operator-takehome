# Run report

**Totals:** 34 input / 2726 output tokens, 26291 cache-read, 12336 cache-write, 30.867s wall-clock.

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously resolved to Juniper Tools (V5). Address draft for request X1 saved successfully on first attempt and verified via read_drafts: new address (10 New Street, Newtown, 11111, Exampleland) recorded without altering vendor ID/name or the original address.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: Request X2 for vendor V5 is missing the required 'country' field (empty string). Cannot save an address update with a blank required field. Please provide the country value before this request can be processed.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X2.json

## X3a
- status: `draft`
- reason: Vendor V1 (Cedar Office) resolved unambiguously. No prior draft existed for request_id DUP-1. Saved new address draft (20 New Street, Newtown, 44444, Exampleland) on first attempt and verified it is present in read_drafts output without altering the vendor's original address or identity.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X3a.json

## X3b
- status: `duplicate`
- reason: Request_id DUP-1 already has an existing draft (vendor V1, address: 20 New Street, Newtown, 44444, Exampleland). Per policy, duplicate request_ids must not produce a second draft. No save attempted; original draft left unchanged. new_drafts=0.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Vendor V2 (Northstar Supplies East) resolved unambiguously. First save attempt failed due to simulated failure switch; retried once and succeeded. Verified via read_drafts that request X4 now has a saved draft with vendor_id V2 and address {12 New Street, Newtown, 33333, Exampleland}, matching the request. No duplicate existed prior to this save, and original address was left untouched.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
