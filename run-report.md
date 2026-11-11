# Run report

**Totals:** 30 input / 2481 output tokens, 20557 cache-read, 11566 cache-write, 28.076s wall-clock.

## R1
- status: `draft`
- reason: Draft successfully saved and verified for request R1, vendor V1 (Cedar Office). New address: 42 Fiction Lane, Demo City, 00123, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name "Northstar Supplies" is ambiguous, matching both "Northstar Supplies East" (V2) and "Northstar Supplies West" (V3). Please provide the exact vendor ID to proceed. No changes were made to either vendor record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Request R3 for vendor V4 (Maple Parts) is missing a required field: postal_code is empty. Cannot save an address update with a blank required field. Please provide a valid postal code to proceed.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID 'V999' does not match any known vendor in the portal. Cannot proceed with address update for an unresolved vendor. Please provide a valid vendor ID or name.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Vendor V6 (Birch Goods) resolved unambiguously. First save attempt failed due to simulated failure; retried once and succeeded. Verified via read_drafts that R5 draft for V6 now has address 42 Fiction Lane, Demo City, 00123, Exampleland, matching the request. Original address was not overwritten (new draft record), vendor ID/name unchanged.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
