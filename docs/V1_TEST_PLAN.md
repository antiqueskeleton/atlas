# Atlas AI v1.0 — Pre-Ship Test Plan

Work top to bottom; each scenario lists steps and what "pass" looks like.
Check the box when it passes; note anything odd next to the item even if it
technically passes. Scenarios marked **[needs key]** are blocked on external
credentials and can be deferred without blocking the ship decision.

Test against your normal working data (run from source). A final smoke pass
of the installed build happens after compile (Section 14).

---

## 1. Startup & Navigation

- [ ] **1.1 Launch speed** — Start Atlas. Splash appears promptly; main window is interactive in a few seconds. The window shows Home. (Startup no longer builds every page — this should feel clearly faster than your last test.)
- [ ] **1.2 First visit to each page** — Click every nav item top to bottom (Home, Visibility, Targeted Review, Trends, Intelligence, Investigate, Knowledge, Price Comparison, Settings). Pass: each page appears after a brief wait cursor on FIRST visit (~1s max), instantly on second visit. No blank pages, no errors.
- [ ] **1.3 Nav order** — Confirm the sidebar order matches the workflow: Home, Visibility, Targeted Review, Trends, Intelligence, Investigate, Knowledge, Price Comparison, Settings.
- [ ] **1.4 Nav collapse** — Click the «/» collapse toggle. Sidebar shrinks to icons; toggle back restores labels. Page content unaffected.
- [ ] **1.5 Font** — Text app-wide renders in Inter (slightly rounder/taller than Segoe UI). No clipped labels, no overlapping text anywhere you visit. Specifically check the Visibility provider dots (green/red) sit cleanly beside provider names.
- [ ] **1.6 Tools → Manage Knowledge** — Jumps to the Knowledge page (correct page after the nav reorder).

## 2. Home

- [ ] **2.1 Data Health card** — Shows one row per source (Visibility, Intelligence, Targeted Review platforms, Backups) with dates. Rows go amber when stale (7+ days), green when fresh. Numbers match reality.
- [ ] **2.2 Getting Started card** — With your data present (brand set, keys added, collections run), this card should be HIDDEN. (Fresh-install behavior is tested in 14.3.)
- [ ] **2.3 KPIs refresh** — Navigate away and back to Home; KPI numbers and Recent Activity update without restart.

## 3. Settings

- [ ] **3.1 Provider keys + Test** — For each configured AI provider, click Test. Pass: configured keys return success; the status dot on the Visibility page matches (green = keyed).
- [ ] **3.2 Provider list alphabetical** — The Active Provider dropdown lists providers alphabetically.
- [ ] **3.3 Platform Research card** — YouTube key, Reddit client ID/secret, Google Custom Search key + cx, SerpApi key, Best Buy key fields all present, saved values persist after Save All + restart.
- [ ] **3.4 Health Check** — Run it. All checks pass (DB integrity, backups fresh, etc.).
- [ ] **3.5 Target brand case-insensitivity** — Temporarily set target brand to "FIRMAN" (all caps), visit Visibility/Home — KPIs still resolve to Firman (not zeros). Restore normal casing after.

## 4. Knowledge

- [ ] **4.1 Brands alphabetical** — Brands tab lists all brands A→Z (no tier grouping visible).
- [ ] **4.2 Brand websites** — Spot-check recently backfilled brands (Buffalo Tools, Energizer, PowerSmart, Tomahawk, SENCI, Homelite, Ridgid, WhisperWatt, VTOMAN, OUPES) — each shows a website when you Edit.
- [ ] **4.3 Add/Edit/Delete brand** — Add a test brand with a website; edit it; delete it. CSV stays in sync (no errors), tables refresh.
- [ ] **4.4 Discover Brands** — Run it (uses your AI keys). Pass: dialog lists genuinely new brands with checkboxes; adding one puts it in the Brands table AND it appears in Targeted Review's brand checklist on next visit to that page — without restarting.
- [ ] **4.5 Prompt families** — Add a prompt to a family, delete it. Category assignment combo works, list shows category inline.
- [ ] **4.6 Web Intelligence scrape** — Run Scrape on an entry (e.g. Champion). Title/meta/keywords/HTTPS columns populate.

## 5. Visibility

- [ ] **5.1 Provider row** — Checkboxes + status dots correct per key state; All / None / Configured buttons work.
- [ ] **5.2 Prompt selection** — Show/Hide Prompts collapses only the prompt list (providers stay visible). All / None / Top 20 work. Category checkboxes cascade to member families. Search filter works.
- [ ] **5.3 Saved Panel** — Select a specific set of prompts + providers → Saved Panel ▾ → Save Current Selection. Change selections, then Load Saved Panel — exact selection restored. Status line confirms both actions.
- [ ] **5.4 Run a small collection** — Pick 1-2 prompt families + 1-2 providers, click Run. Pass: progress bar + counts advance, Pause pauses (button becomes Resume), Resume continues, Stop ends the run keeping collected responses. New responses appear in Raw Data.
- [ ] **5.5 KPI provenance** — Every KPI tile shows n= and as-of date. Small samples (<30) show the amber "directional" note.
- [ ] **5.6 Raw Data tab** — Provider filter (alphabetical), review-status filter, and search all narrow the list; clicking a response shows full text beside it.
- [ ] **5.7 Review workflow** — Flag a response, mark one Reviewed. Spot-Check Accuracy tile updates; 🎲 Audit Random walks unreviewed samples.
- [ ] **5.8 Brands tab** — Mention counts look sane post word-boundary fix (CAT ~ hundreds not thousands). Sentiment and Position tables render.
- [ ] **5.9 Exports** — Click the green XLS icon → Excel saves and opens, sheets populated. Click the red PDF icon → PDF report generates. Both icons show tooltips; buttons disable while generating.
- [ ] **5.10 Cadence nudge** — If your last collection is 7+ days old, the amber "run the Saved Panel" nudge shows in the toolbar (and on Home).

## 6. Targeted Review

- [ ] **6.1 Brand checklist** — Alphabetical; target brand pre-checked and bold; Top AI-Mentioned selects target + 5; None clears to target only.
- [ ] **6.2 Find Socials** — Check ~5 brands with websites, click Find Socials. Pass: progress counts up in the brand panel's own status line, then a green "Done — social links saved for X of Y brand(s)…" message that is visible regardless of which platform tab is open.
- [ ] **6.3 YouTube collection** — Collect with target + a few competitors. Pass: Relevant/Fresh/Top-10 Views populate; Ch. Subs fills for brands where Find Socials found a channel; double-click a brand → drill-down shows Top videos AND Owner voice comments, each row with a working "Watch ↗" link; comment Signal column tags mention/negative/recommend.
- [ ] **6.4 AI Overviews collection** — Collect. 5 shared queries run (5 SerpApi searches total, not per brand). Drill-down shows per-query Overview shown / Brand named.
- [ ] **6.5 Gap analysis cards** — After collections, cards show GAP/STRENGTH badges with Why/Tactics text citing the measured numbers.
- [ ] **6.6 Retail listings** — Your saved Amazon/Walmart URLs collect; Last Fetch column shows per-URL result; Lowe's/Home Depot URLs show their blocked error rather than silently failing.
- [ ] **6.7 Influencers tab** — Add a real YouTube creator (channel URL + display name). Click Collect Creator Data. Pass: Posts (period) / Avg Views / Avg Comments populate; double-click → recent-videos drill-down with working links. Remove Selected removes. Duplicate add shows "Already Tracked."
- [ ] **6.8 Reddit collection** **[needs key]** — When your Reddit key arrives: brand collection populates Posts/Upvotes/Comments/Top Subreddits; a Reddit username creator collects post cadence + scores.
- [ ] **6.9 Best Buy collection** **[needs key]** — When approved: listings/reviews/ratings populate; drill-down lists products.
- [ ] **6.10 Editorial collection** **[needs key]** — After the Google-side fix (fresh GCP project): per-site coverage populates without the 403.

## 7. Trends

- [ ] **7.1 Charts render** — All tabs draw with your history; target brand consistently blue; competitor lines muted gray.
- [ ] **7.2 Event markers** — Dotted vertical markers appear where brands/prompts were edited or a provider's model changed; hover/legend explains them.
- [ ] **7.3 Refresh** — After running 5.4's collection, Refresh adds the new run's point.

## 8. Intelligence

- [ ] **8.1 Mode badge** — Shows just "DB Mode" (green) with your data; the ⓘ tooltip explains modes with counts.
- [ ] **8.2 Run Analysis** — Runs to completion; transient status shows during the run then disappears; Last Run KPI tile updates with date + provider/duration.
- [ ] **8.3 Briefing quality** — VISIBILITY SNAPSHOT counts match the full database (e.g. "X of 606"); Scope line present; verification badge shows (e.g. "9/9 verified" or flags unverified claims on hover); MEASURED PLATFORM PRESENCE facts appear when Targeted Review data exists; portfolio gaps labeled as portfolio, not visibility.
- [ ] **8.4 Opportunities** — Ranked with evidence-count findings first; status toggle (New/In Progress/Done) persists across a re-run; "From run:" date shown.
- [ ] **8.5 Exports (all four)** — DOC icon → Word; PDF icon → PDF; Export Tab (Full) from each tab incl. Opportunities (this crashed before — verify it saves now); briefing-card PDF icon → briefing-only export. All open cleanly.

## 9. Investigate

- [ ] **9.1 Ask a question** — e.g. "Why is Champion mentioned more than Firman?" Pass: progress steps show, answer renders with evidence prev/next working, no raw JSON visible.
- [ ] **9.2 Provider override** — Provider dropdown (alphabetical) changes which provider answers.

## 10. Price Comparison

- [ ] **10.1 Real run** — Primary: Firman + a real model (e.g. T07571). Check 3-4 competitors (Champion, Westinghouse, DuroMax…). Run Comparison. Pass: progress advances; no crash; Data Status tab shows each comp brand's Model Source as "matched by AI" (or "top search result" fallback with a note in the left status area).
- [ ] **10.2 Spec Comparison tab** — Amazon-style: products as columns; rows ordered Best Price, Customer Rating, Wattage, Fuel Type, Start Type, Generator Type (bold), then remaining specs; unconfirmed cells show "—"; AI-matched columns show * with tooltip.
- [ ] **10.3 Sanity of matches** — The AI-matched models are actually comparable (similar wattage class/fuel/start). Note any absurd match — that calibrates the prompt.
- [ ] **10.4 Key-attribute overrides** — Set Wattage 9000 + Tri Fuel, re-run: matched models shift accordingly.
- [ ] **10.5 Price table + Excel** — MSRP vs Best Price populate where found; re-running later shows Prev Best/Change%; Export Excel produces both sheets.
- [ ] **10.6 Retailer URLs** — Paste a real Amazon product URL for the primary; its price appears with the retailer named.

## 11. Help & About

- [ ] **11.1 Usage Guide** — Reflects reality: workflow order, all 9 pages incl. Targeted Review/Influencers, Price Comparison described as live (not Coming Soon).
- [ ] **11.2 Methodology** — Includes Influencer Tracking and Price Comparison Matching sections.
- [ ] **11.3 About** — Text wraps cleanly (no orphan words); dweeb.co looks like plain text but opens the site when clicked.
- [ ] **11.4 Easter egg** — Click the © in About. The game opens; playing it drains/refills sensibly; best time persists across app restarts; nothing anywhere advertises it.
- [ ] **11.5 Check for Updates** — Reports "up to date" (until the v1.0 manifest is published).

## 12. Data safety & resilience

- [ ] **12.1 Backup on launch** — After a restart, a new backup file exists in the backups folder; only the newest 5 kept.
- [ ] **12.2 Missing-key states** — Uncheck/blank a platform credential temporarily: the relevant Collect button reports what's missing instead of erroring. Restore after.
- [ ] **12.3 Sleep guard** — (If practical) start a small collection, let the PC sleep briefly; collection resumes/completes rather than dying silently.

## 13. Cross-cutting polish

- [ ] **13.1 Alphabetization** — All brand/provider dropdowns and checklists A→Z (Knowledge brands, Targeted Review brands, Price Comparison brands, provider selectors).
- [ ] **13.2 Button styling** — No stray bold-blue buttons on Visibility/Intelligence toolbars; export icons consistent (XLS green, PDF red, DOC blue).
- [ ] **13.3 Window sizes** — At default 1340×860 and at minimum 1100×700, no overlapping/clipped controls on any page.

## 14. Post-build (after compile, before release)

- [ ] **14.1 Installed build smoke** — Install v1.0 over v0.9.5. App launches, splash correct, version shows 1.0.0 in About/status bar, fonts bundled (Inter renders), all 9 pages open.
- [ ] **14.2 Data migration** — Installed build sees the existing %APPDATA% database; new tables (targeted review, creators) create automatically; nothing lost.
- [ ] **14.3 Fresh-install first-run** — On a clean profile (or after renaming %APPDATA%\Atlas): app seeds brands, Home shows the Getting Started checklist, checklist items check off as you complete them and the card disappears after the 4th.
- [ ] **14.4 Updater end-to-end** — After the release + manifest are published: a v0.9.5 install detects v1.0.0 and the download link resolves (HTTP 200).

---

**Reporting back:** for anything that fails, the most useful report is: the item number, what you saw (screenshot if visual), and the exact text of any error shown.
