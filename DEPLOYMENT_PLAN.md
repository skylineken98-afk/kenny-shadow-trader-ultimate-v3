# Deployment order

This branch prepares KST r5 and does not deploy it.

The current V3 Railway service runs workers.scan_worker in vivacious-analysis. A second service named shadow-trader-mobile in patient-stillness also uses this backend repository and runs worker.py; it is not the mobile website. Keep both existing services intact until their intended roles are reviewed.

1. Apply the explicitly approved additive Supabase migration before deploying new services.
2. Merge this source update only after review and CI. A push to main can auto-deploy existing services.
3. Add/configure separate options, chat, Pro and push services using their railway-*.json files. Additional running services can increase Railway usage.
4. The existing shared Alpaca names are APCA_API_KEY_ID and APCA_API_SECRET_KEY. Reference these securely into the ALPACA_API_KEY and ALPACA_API_SECRET names required by the new data services. Do not copy values into code. OPENAI_API_KEY is already a shared variable in patient-stillness; reference it on the new chat service.
5. Configure missing Finnhub, public Auth key, proxy token and optional push/billing settings as described in RELEASE_R5.md.
6. Deploy the companion mobile Worker and verify two-user account isolation and data freshness end to end.

Billing enforcement and real-money execution stay disabled. The execution adapter must not be started as part of the initial feature deployment.
