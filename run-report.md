# Run report

## R1
- status: `draft`
- reason: Draft successfully created and verified for request R1: vendor V1 (Cedar Office) address updated to 42 Fiction Lane, Demo City, 00123, Exampleland. Save succeeded on first attempt; read_drafts confirms the draft matches the requested address exactly.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name 'Northstar Supplies' is ambiguous, matching both 'Northstar Supplies East' (V2) and 'Northstar Supplies West' (V3). Please provide the exact vendor_id to proceed. No changes have been made to either record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Vendor V4 (Maple Parts) resolved successfully, but the requested address update has an empty postal_code, which is a required field. Cannot save draft until a valid postal code is provided. No changes were made to the existing vendor record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID 'V999' does not match any vendor in the portal. No matching vendor found, so the address update cannot be processed. Please verify the vendor ID and resubmit.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Vendor V6 (Birch Goods) resolved unambiguously. First save attempt failed due to simulated failure; retried once successfully. Verified via read_drafts that request R5 draft now exists with the new address (42 Fiction Lane, Demo City, 00123, Exampleland) while leaving original address and vendor identity untouched.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
