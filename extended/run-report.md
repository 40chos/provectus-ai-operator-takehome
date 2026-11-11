# Run report

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously resolved to Juniper Tools (V5). Draft saved successfully on first attempt and verified via read_drafts: address updated to 10 New Street, Newtown, 11111, Exampleland. No duplicate existed for request_id X1.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: Request X2 for vendor V5 is missing a required field: 'country' is empty. Cannot save an address update with a blank required field. Please provide the country value to proceed.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X2.json

## X3a
- status: `draft`
- reason: Draft successfully created and verified for request_id DUP-1, vendor V1 (Cedar Office), with new address: 20 New Street, Newtown, 44444, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X3a.json

## X3b
- status: `duplicate`
- reason: A draft for request_id DUP-1 already exists (vendor V1, address: 20 New Street, Newtown, 44444, Exampleland). Per policy, resubmission with a different address is not applied; the original draft remains unchanged. No new draft created.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Draft for request X4 (vendor V2) was saved successfully after a simulated single failure and a successful retry. Verified via read_drafts: address updated to 12 New Street, Newtown, 33333, Exampleland, without altering vendor ID/name or original address. No duplicate draft existed prior to this save.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
