# Challenge Symbol Mapping & Disambiguation Table

## 1. Overview

The Tunis Bourse Challenge uses customized short symbol mnemonics that occasionally diverge from standard BVMT ticker symbols or company names.

This document records the exact, verified mapping between:
1. `Challenge Symbol`: The exact mnemonic displayed in the virtual challenge interface (`https://www.tunisbourse-challenge.com`).
2. `BVMT Ticker / Instrument ID`: The internal identifier used in BVMT exchange feeds and this platform (`instrument_master.csv`).
3. `ISIN`: The international securities identification number.
4. `BVMT Official Name`: The legal company name as registered with Bourse de Tunis.
5. `Trading Mode`: Continuous (`Continu`) or Auction (`Fixing`).

---

## 2. Disambiguated Key Mnemonics

| Challenge Symbol | Resolved BVMT Ticker | ISIN | Company Legal Name | Disambiguation Notes |
|---|---|---|---|---|
| `MGR` | `SOTUMAG` | TN0006580013 | Société Tunisienne des Marchés de Gros | Challenge uses `MGR` (Marché de Gros) rather than `SOTUMAG` |
| `AMV` | `ASSU MAGHREBIA VIE` | TNDKJ8O68X14 | Assurances Maghrebia Vie | Challenge uses `AMV` rather than full company name |
| `SAM` | `ATELIER MEUBLE INT` | TN0007740012 | Société Atelier du Meuble Intérieurs (SAM) | Challenge uses `SAM` rather than `ATELIER MEUBLE INT` |
| `STA` | `STA` | TNNGTFLC2986 | Société Tunisienne d'Automobiles (Chery) | Ticker and symbol match |
| `BH` | `BH BANK` | TN0001900604 | Banque de l'Habitat (BH Bank) | Challenge uses `BH` rather than `BH BANK` |
| `TJARI` | `ATTIJARI BANK` | TN0001200401 | Attijari Bank Tunisie | Challenge uses `TJARI` rather than `ATTIJARI BANK` |
| `TJL` / `TLS` | `TUNISIE LEASING & FAC` | TN0002100907 | Tunisie Leasing et Factoring | Both symbols map to same security |
| `TRE` | `TUNIS RE` | TN0007390016 | Société Tunisienne de Réassurance | Group 12 Fixing security |
| `WIFAK` | `WIFAK INT BANK` | TN0007280019 | Wifak International Bank | Group 12 Fixing security |
| `DH` | `DELICE HOLDING` | TN0007670011 | Délice Holding | Challenge uses `DH` rather than `DELICE HOLDING` |

---

## 3. Excluded Securities Disambiguation

The following prominent listed securities were previously proposed by broader BVMT research algorithms, but are **STRICTLY EXCLUDED** from the Tunis Bourse Challenge universe:

| Symbol / Ticker | Company Name | ISIN | Quotation Status | Challenge Universe Status |
|---|---|---|---|---|
| `MNP` | MONOPRIX | TN0001000124 | Continu (Group 11) | **NOT IN CHALLENGE** — Order entry blocked |
| `SCN` | ESSOUKNA | TN0007220015 | Continu (Group 11) | **NOT IN CHALLENGE** — Order entry blocked |
| `AL` | AIR LIQUIDE | TN0002200509 | Continu (Group 11) | **NOT IN CHALLENGE** — Order entry blocked |
| `AETEC` | AETECH | TN0007540016 | Sous Surveillance | **NOT IN CHALLENGE** — Restricted & Excluded |
| `CELL` | CELLCOM | TN0007590011 | Continu (Group 11) | **NOT IN CHALLENGE** — Order entry blocked |
| `MIP` | MIP | TN0007620016 | Sous Surveillance | **NOT IN CHALLENGE** — Restricted & Excluded |
| `GIF` | GIF FILTER | TN0007140015 | Sous Surveillance | **NOT IN CHALLENGE** — Restricted & Excluded |

### Resolution Implementation in Code
The resolution logic is programmatically guaranteed in `src/bvmt/challenge_universe.py`:
- `resolve_challenge_record(query: str) -> ChallengeSecurityRecord | None`
- Resolves by challenge symbol, ticker, ISIN, or normalized company name.
- Non-members return `None`, causing `is_challenge_member = False` and strict order suppression.

