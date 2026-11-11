# Run report

**Totals:** 34 input / 2755 output tokens, 26298 cache-read, 12444 cache-write, 31.223s wall-clock, **$0.0640 actual cost** (hard cap: $0.2).

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously resolved to Juniper Tools (V5). Address draft saved successfully on first attempt with all required fields (line1, city, postal_code, country) populated, and verified via read_drafts.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: Request X2 for vendor V5 is missing the required 'country' field (empty string). Cannot save address update until country is provided.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X2.json

## X3a
- status: `draft`
- reason: Draft successfully created and verified for request_id DUP-1, vendor V1 (Cedar Office), with new address 20 New Street, Newtown, 44444, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X3a.json

## X3b
- status: `duplicate`
- reason: A draft already exists for request_id DUP-1 (vendor V1, address: 20 New Street, Newtown, 44444, Exampleland). Per policy, no new draft is created for a repeated request_id; the existing draft remains unchanged.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Vendor V2 (Northstar Supplies East) resolved unambiguously. No existing draft for request X4. First save attempt failed due to simulated failure switch; retried once per policy and the second attempt succeeded. Verified via read_drafts that the X4 draft now contains the correct new address (12 New Street, Newtown, 33333, Exampleland) without altering vendor ID/name or the original address.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
