# Run report

## R1
- status: `draft`
- reason: Draft successfully created and verified for request R1: vendor V1 (Cedar Office) address updated to 42 Fiction Lane, Demo City, 00123, Exampleland. Original address record left unchanged.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name "Northstar Supplies" is ambiguous, matching both "Northstar Supplies East" (V2) and "Northstar Supplies West" (V3). Please provide the exact vendor ID to proceed. No changes have been made to either record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Request R3 for vendor V4 (Maple Parts) has an empty postal_code field, which is required for an address update. Please provide the missing postal code before this change can be saved as a draft.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID V999 does not match any known vendor in the portal. Cannot proceed with address update for request R4 without a valid vendor. Please verify the correct vendor ID.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Draft successfully saved for request R5 (vendor V6, Birch Goods) with address 42 Fiction Lane, Demo City, 00123, Exampleland. First save attempt failed due to simulated failure; retry succeeded and was verified via read_drafts.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
