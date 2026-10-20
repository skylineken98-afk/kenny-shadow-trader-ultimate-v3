# V3 Robinhood risk policy update — October 20, 2026

Requested **maximum $60 per order**. The research-only `AllocationPolicy` defaults are now:

- Total intended allocation: $100
- Maximum single order notional: $60
- Maximum combined open/pending exposure: $60 (raised from $50 to accommodate a $60 order)
- Daily realized loss stop: $5 (unchanged)

These caps are **not broker-enforced**. Live Robinhood execution is still blocked; this build does not authorize trades. Order cap includes quantity multiplied by order price, not just the quoted share/option premium.
