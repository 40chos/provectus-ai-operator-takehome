# Run report

**Totals:** 30 input / 2497 output tokens, 20557 cache-read, 11620 cache-write, 28.865s wall-clock.

## R1
- status: `draft`
- reason: Address update for vendor V1 (Cedar Office) saved successfully as a draft and verified via read_drafts. New address: 42 Fiction Lane, Demo City, 00123, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name "Northstar Supplies" is ambiguous - it matches both "Northstar Supplies East" (V2) and "Northstar Supplies West" (V3). Please provide the exact vendor ID to proceed. No changes have been made to either vendor record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Vendor V4 (Maple Parts) resolved successfully, and no existing draft was found for request R3. However, the request's postal_code field is empty, and postal code is a required field for address updates. Please supply a valid postal code before this change can be saved.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID 'V999' does not match any vendor in the portal. Cannot proceed with address update for an unknown vendor. Please verify the correct vendor ID.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Vendor V6 (Birch Goods) resolved unambiguously. All required address fields were present and valid. First save attempt failed due to simulated failure; retried once successfully. Verified via read_drafts that request R5 now has a saved draft with the correct vendor_id and new address, leaving the original address and vendor identity unchanged.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
