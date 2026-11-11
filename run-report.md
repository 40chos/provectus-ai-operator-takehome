# Run report

## R1
- status: `draft`
- reason: Draft successfully created and verified for vendor V1 (Cedar Office) with the new address (42 Fiction Lane, Demo City, 00123, Exampleland). Save succeeded on first attempt; confirmed via read_drafts.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name 'Northstar Supplies' is ambiguous: matches both 'Northstar Supplies East' (V2) and 'Northstar Supplies West' (V3). Please provide the exact vendor ID to proceed. No changes have been made to either record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Request R3 for vendor V4 (Maple Parts) is missing a required field: postal_code is empty. Cannot save an address update with a blank required field. Please provide the postal code before resubmitting.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID 'V999' does not match any vendor known to the portal. Cannot proceed with address update for an unresolved vendor. Please verify the correct vendor ID and resubmit.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Vendor V6 (Birch Goods) resolved uniquely. First save attempt failed due to simulated failure; retried once and succeeded. Verified via read_drafts that R5 draft now exists with address: 42 Fiction Lane, Demo City, 00123, Exampleland. Original address was not overwritten (drafts are separate from vendor record).
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
