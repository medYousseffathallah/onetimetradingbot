# Official rule verification checklist

Source supplied by user: https://www.tunisbourse-challenge.com/displayp.aspx
Access attempt during preparation: HTTP 403; no rule text retrieved.
Do not assume a public search result or a prior edition's document governs this account.

## 1. Read-only inspection of `/reglement.aspx` (T01, 2026-11-05)
- `https://www.tunisbourse-challenge.com/displayp.aspx` and `https://www.tunisbourse-challenge.com/help.aspx`: HTTP 302 redirect to `login.aspx` when unauthenticated.
- `https://www.tunisbourse-challenge.com/reglement.aspx`: HTTP 200 (15,118 bytes), retrieved at `2026-11-05T16:04:08.317065+00:00`, snapshotted at `data/raw/tunisbourse_challenge_reglement/767725a9e60aac3efd8da30c107c0e8a95f7a85c73501e1775001278bdd21891.bin`.
- **Exact wording observed on `/reglement.aspx`** (pending human verification that the participant's account is entered in this edition):
  - **1.3- Dates du Challenge**: *"La 14ème édition du Challenge débute le 1er Octobre 2026 et s’achève le 31 mai 2027."* (Note internal contradiction between section 2.1 *"inscrire avant le 31 janvier 2026"* and section 4.1 *"Les joueurs inscrits après le 31 janvier 2027 ne seront pas pris en compte lors du classement final de la 14ème édition."*)
  - **3. REGLES DU CHALLENGE — Horaires de cotation**: *"La cotation se déroule de 8h30 à 14h15, sauf durant Ramadhan, Juillet et Août de 8h30 à 12h15, pendant les jours ouvrables du lundi au vendredi de chaque semaine."*
  - **Titres éligibles**: *"Seules les actions cotées au mode Continu du Marché Principal de la Bourse, sont éligibles dans le présent challenge."*
  - **Capital initial**: *"Le participant dispose d'un capital virtuel initial de 50 000 Dinars, qu’il devra fructifier au mieux en investissant dans les titres éligibles. A tout moment, la valeur du portefeuille constitué sera la somme des valeurs des titres détenus valorisés au prix du marché et des liquidités disponibles."*
  - **Diversification**: *"Avant tout achat d’actions d’une société donnée, le système vérifie que la valeur des actions déjà détenues par le participant dans cette société ne dépasse pas 10% de la valeur totale du portefeuille. Dans ce cas, le système peut réduire la quantité spécifiée dans l’ordre d’achat afin de respecter le plafond de 10%."*
  - **Marché au comptant**: *"Il n’y a pas de vente ni d’achat à découvert. Les ordres de vente ne seront exécutés qu’à hauteur des actions détenues dans le portefeuille. Les ordres d’achat ne seront exécutés qu’à hauteur des liquidités disponibles."*
  - **Ordres**: *"Deux types d'ordres sont disponibles : • Ordre à cours limité : Prix maximal d’achat ou Prix minimal de vente. • Ordre au marché : Achat ou vente à tout prix. Il est prioritaire. Les ordres saisis et non exécutés peuvent être annulés."*
  - **Frais de courtage**: *"A l’achat comme à la vente, des frais de courtage de 0,5% du montant de la transaction sont prélevés."*
  - **Opérations sur titres**: *"Les opérations sur titres seront prises en considération. Les cours seront ajustés si nécessaire. En cas d’augmentation de capital, la valeur calculée le jour du détachement des droits d’attribution et/ou de souscription s’ajoutera aux liquidités. Les dividendes distribués s’ajouteront aux liquidités disponibles dans le portefeuille."*
  - **4.1 Classement des participants & 4.2 Prix**: *"Le tri des participants est effectué par ordre décroissant de valorisation financière du portefeuille... En cas d’ex-æquo, le premier inscrit sera retenu."*

## 2. Participant-supplied FAQ evidence (`/help.aspx`, 2026-11-05)
- **Source URL**: `https://www.tunisbourse-challenge.com/help.aspx`
- **Evidence type**: Participant-supplied evidence attributed to the official FAQ (`help.aspx`), NOT independently fetched website content (unauthenticated GET redirects to `login.aspx`).
- **Capture date**: `2026-11-05`
- **Confirmed FAQ statements**:
  - **Order types (`allowed_order_types`)**: Market orders and limit orders are supported; buying and selling are supported; a sell order cannot exceed owned shares; pending orders can be cancelled before execution.
  - **Execution (`execution_matching`)**:
    - Orders may execute between **09:00 and 14:15** (`Africa/Tunis`).
    - Orders enter a pending state before being considered.
    - Orders placed outside the execution window are considered during the next session.
    - Orders may remain pending when a security has not traded or trading activity is below an unspecified minimum threshold.
    - Limit orders remain pending when the limit condition is not satisfied.
    - Orders on suspended securities remain pending until trading resumes.
    - Partial execution is possible.
    - Unexecuted orders are cancelled after **one week** (whether 7 calendar days or a trading-week convention remains unresolved).
  - **Portfolio constraints (`position_and_sector_limits`, `short_selling_and_leverage`, `settlement_and_cash`)**:
    - Maximum exposure to a single stock is **10%** of portfolio value; the simulator may automatically reduce order quantity to respect this limit.
    - Orders can be cancelled or purged when there is insufficient cash, insufficient owned shares, or a concentration-limit violation.
    - The exact calculation timing and treatment of pending orders remain unresolved.
  - **Transaction costs (`fees_and_taxes`)**:
    - A **0.50% fee** applies to purchases and a **0.50% fee** applies to sales. No additional fees should be assumed without evidence.
  - **Leaderboard (`scoring_and_final_valuation`)**:
    - Rankings are recalculated hourly between **11:00 and 15:00**.
    - Total portfolio profit/loss includes realized gains and losses.
    - Final valuation methodology (including treatment of suspended holdings at competition end) remains unverified.
  - **Participation**: Only one competition account per participant is allowed.

## 3. Critical separation: BVMT Exchange Calendar vs. Simulator Execution Schedule
- The official BVMT exchange calendar (`src/bvmt/calendar.py`) and the Tunis Bourse Challenge simulator (`configs/competition.json`) are **separate concepts** and must be modeled independently:
  1. The `08:30` opening time mentioned in `reglement.aspx` or planning documents is not a verified official BVMT continuous-trading schedule; exchange sessions require official BVMT calendar evidence (`source_document_id`).
  2. The FAQ's `09:00–14:15` window applies specifically to **possible simulator order execution** in the Tunis Bourse Challenge.

## 4. Why `rules-check` reports blocker counts vs. distinct unresolved rules
The readiness checker (`src/bvmt/rules.py`) inspects **15 required rule categories** (`REQUIRED_FIELDS`), and for each category checks up to **6 metadata attributes** (`value`, `status == "verified"`, `source`, `evidence_locator`, `reviewed_by`, `reviewed_at`).
- When all 15 categories are completely empty (`null`), `15 fields × 6 checks = 90 blockers` are emitted.
- In `configs/competition.json`, we now populate `value`, `source`, and `evidence_locator` for the **6 categories directly evidenced by the participant-supplied FAQ** (`allowed_order_types`, `fees_and_taxes`, `short_selling_and_leverage`, `execution_matching`, `position_and_sector_limits`, `scoring_and_final_valuation`), while keeping their `status` as `"unverified"` (and `reviewed_by`/`reviewed_at` as `null`) because either sub-questions remain unresolved or formal human sign-off (`reviewed_by`, `reviewed_at`) has not occurred.
- The remaining **9 categories** (`edition`, `initial_cash_tnd`, `start_date`, `end_date`, `eligible_instruments`, `settlement_and_cash`, `corporate_actions`, `tick_and_lot_rules`, `automation_policy`) retain `value: null` until the participant confirms their entered edition (`reglement.aspx`) and resolves the remaining mechanics.
- Thus `rules-check` now reports **72 attribute-level blockers** (`6 × 3` for the 6 partially populated FAQ categories + `9 × 6` for the 9 null categories) across **15 unverified rule categories**, and exits `2` (`status: "blocked"`).

## 5. Exact remaining blockers grouped by rule category
1. **Edition & Dates (`edition`, `start_date`, `end_date`)**: Confirm that the participant's account is in the 14th edition (`2026-10-01` to `2027-05-31`) and resolve the registration-cutoff contradiction in `reglement.aspx` (`31 janvier 2026` vs `31 janvier 2027`).
2. **Initial Capital & Universe (`initial_cash_tnd`, `eligible_instruments`, `corporate_actions`)**: Human review sign-off confirming `50000` TND initial balance, *Continu du Marché Principal* eligibility list, and corporate-action cash adjustment rules from `reglement.aspx`.
3. **Execution Matching (`execution_matching`)**:
   - Exact minimum trading activity threshold required before a pending order executes.
   - Whether the 1-week order expiry means 7 calendar days or 5 trading sessions.
   - How partial fills and reference execution prices are determined from the BVMT feed (e.g., last trade vs best bid/ask, feed delay).
4. **Position & Sector Limits (`position_and_sector_limits`)**:
   - Exact formula and timing for the 10% single-stock cap (whether evaluated at order entry vs execution, how pending buy orders affect available room, and whether automatic quantity reduction rounds down to whole shares).
5. **Settlement & Cash (`settlement_and_cash`)**:
   - Whether cash from sales is immediately reusable (`T+0`) and how cash is reserved while buy orders are pending.
6. **Scoring & Final Valuation (`scoring_and_final_valuation`)**:
   - Exact final valuation price basis and treatment of suspended or non-traded holdings at competition close.
7. **Tick & Lot Rules (`tick_and_lot_rules`)**:
   - Simulator tick-size table and minimum lot size (1 share vs board lot).
8. **Automation Policy (`automation_policy`)**:
   - Official policy on read-only data collection; note that order submission remains permanently disabled (`execution_enabled: false`) in this starter.
