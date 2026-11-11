# Run report

## X1
- status: `draft`
- reason: Vendor 'Juniper' unambiguously resolved to V5 (Juniper Tools). Address draft saved and verified: 10 New Street, Newtown, 11111, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs_extended/X1.json

## X2
- status: `needs-information`
- reason: Request X2 for vendor V5 (Juniper Tools) is missing the required 'country' field (empty string). All postal-address fields (line1, city, postal_code, country) must be nonempty to save a draft. Please supply a valid country value before this update can be processed.
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
- reason: A draft for request_id DUP-1 already exists (vendor V1, address: 20 New Street, Newtown, 44444, Exampleland). Per policy, the same request_id must not produce a duplicate draft. No new draft was created; the original draft remains unchanged.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs_extended/X3b.json

## X4
- status: `draft`
- reason: Vendor V2 (Northstar Supplies East) resolved unambiguously. First save attempt failed due to simulated failure switch; retried once successfully. Verified via read_drafts that request X4 now has a draft with the new address (12 New Street, Newtown, 33333, Exampleland) while vendor ID and name remain unchanged and the original address was not overwritten in place (new draft record created).
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs_extended/X4.json
