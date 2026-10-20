# SEC + FINRA regulatory connectors

## SEC (no registration or API key)
Server secret `SEC_USER_AGENT` e.g. `KennyShadowTrader research team-contact@example.com` (replace with a real monitored contact email). SEC requests must be identified, rate-limited and cached. Public endpoints: company ticker list, `data.sec.gov/submissions/CIK##########.json`, and `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`.

## FINRA (separate authorization required)
1. Create FINRA Gateway / Developer API access at https://developer.finra.org/docs.
2. Provision suitable client ID and secret. **Individual research API accounts are not licensed for commercial deployment.** Verify terms and permissions for a public paid website with FINRA.
3. Store `FINRA_CLIENT_ID` and `FINRA_CLIENT_SECRET` in server secrets (not GitHub).
4. Validate which data sets the account is entitled to and any dataset name/version changes. Present adapter is a read-only skeleton; live provider authentication has not been tested.

## Important
FINRA short interest and short-sale volume are different metrics and neither is proof of fresh net institutional inflows. Regulatory prints and SEC filings have reporting delays. These modules are not yet scheduled in Railway or storing values into Supabase. Never interpret these sources as live trade execution signals without timestamps and provenance checks.
