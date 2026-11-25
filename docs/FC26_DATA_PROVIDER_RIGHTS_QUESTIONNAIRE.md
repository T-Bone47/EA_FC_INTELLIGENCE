# FC26 DATA PROVIDER RIGHTS QUESTIONNAIRE

Purpose: determine, precisely, whether this product can legally ingest, store, derive from, and serve a provider's FC26 Ultimate Team data. Every question maps to one of the eight evaluation dimensions in `provider_license_evaluator.py`, so a provider's answers can be mechanically recorded (EXPLICITLY_ALLOWED / EXPLICITLY_PROHIBITED / CONDITIONAL / SILENT / AMBIGUOUS) rather than interpreted.

## A. Access & Automation
1. May we programmatically access FC26 Ultimate Team data through your API?
2. Are automated, unattended requests (e.g. a scheduled daily sync) permitted?
3. What rate limits apply, and are there volume tiers relevant to a full-catalogue sync versus incremental updates?
4. What authentication is required, and are API keys transferable/revocable at your discretion?

## B. Storage
5. May our application permanently store the API responses in our own database?
6. May we store normalized card records (restructured from your response format) rather than raw responses only?
7. Is there a maximum caching or storage duration, after which we must re-fetch or delete?

## C. Derived data
8. May we calculate derived statistics from your data (e.g. a weighted attribute score)?
9. May we calculate rankings or comparisons between players/cards using your data as an input?
10. May we calculate contextual recommendations (e.g. "best card for this tactical system") from your data?
11. May we calculate analytical scores that are not direct copies of your source fields?

## D. User-facing display
12. May we display FC26 card information to our application's users?
13. May we display card attributes (pace, shooting, passing, etc.)?
14. May we display PlayStyles and PlayStyle+?
15. May we display Roles?
16. May we display card type and card version (base, TOTW, promo, Icon, Hero, Evolution)?
17. May we display prices or market observations, and if so, with what freshness/attribution requirements?

## E. Commercial use
18. Is commercial use of your data permitted in a paid or ad-supported product?
19. Are there additional commercial licensing terms or fees beyond the API pricing tier?
20. Is attribution to your service required in our product, and if so, in what form?

## F. Redistribution
21. May derived data (not your raw dataset) be served publicly to our users?
22. May our users query or search the derived data we've built from your API?
23. May any raw source data (unmodified fields, images, or text) be exposed directly to our users?
24. If raw data redistribution is not permitted, is serving derived recommendation results (rankings, contextual scores) explicitly permitted?

## G. Identity & provenance
25. May we retain your internal card IDs / player IDs in our database?
26. May we retain your source timestamps (e.g. when a card was added or last updated)?
27. May we store metadata about our observation of your data (retrieval time, our internal record of what we fetched)?
28. Are there restrictions on combining your data with data from other sources in the same product?

## H. Termination
29. If our subscription or access is cancelled, what happens to data we have already stored?
30. Must we delete historical raw data upon termination?
31. Must we delete or disable derived statistics/recommendations built from your data upon termination?

## How responses are recorded

Every answer is logged in `artifacts/phase21/provider_responses/<provider_id>.json` and classified into one of five states. **A response that does not clearly say yes is not a yes**: silence, "we haven't thought about that," or vague reassurance are all recorded as `SILENT` or `AMBIGUOUS`, never `EXPLICITLY_ALLOWED`.
