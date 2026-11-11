# Run report

**Totals:** 30 input / 2540 output tokens, 20559 cache-read, 11597 cache-write, 28.454s wall-clock, **$0.0586 actual cost** (hard cap: $0.2).

## R1
- status: `draft`
- reason: Draft successfully saved and verified for request R1, vendor V1 (Cedar Office): address updated to 42 Fiction Lane, Demo City, 00123, Exampleland.
- save attempts: 1 (failure seen: False)
- new drafts created: 1
- transcript: logs/R1.json

## R2
- status: `needs-information`
- reason: Vendor name "Northstar Supplies" is ambiguous, matching both "Northstar Supplies East" (V2) and "Northstar Supplies West" (V3). Please provide the exact vendor ID (or full unambiguous name) to proceed with the address update for request R2. No changes have been made to either vendor record.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R2.json

## R3
- status: `needs-information`
- reason: Vendor V4 (Maple Parts) resolved successfully, and no duplicate draft exists for request R3. However, the request's postal_code field is empty, and postal code is a required nonempty field for address updates. Please provide a valid postal code before this change can be saved.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R3.json

## R4
- status: `unresolved`
- reason: Vendor ID "V999" does not match any vendor in the portal. Cannot proceed with the address update without a valid vendor identifier. Please verify the vendor ID and resubmit.
- save attempts: 0 (failure seen: False)
- new drafts created: 0
- transcript: logs/R4.json

## R5
- status: `draft`
- reason: Vendor V6 (Birch Goods) resolved unambiguously. First save attempt failed due to simulated failure switch; retried once and succeeded. Verified via read_drafts that draft R5 for V6 contains the correct new address (42 Fiction Lane, Demo City, 00123, Exampleland) without altering vendor identity or original address.
- save attempts: 2 (failure seen: True)
- new drafts created: 1
- transcript: logs/R5.json
