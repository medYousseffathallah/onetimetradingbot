# Tunis Bourse Challenge Quotation Universe (42 Securities)

## 1. Executive Summary & Regulatory Boundary

The Tunis Bourse Challenge (`https://www.tunisbourse-challenge.com`) does not quote all 76 listed BVMT equities for virtual order entry. Instead, it restricts participants to an active quotation universe of **exactly 42 liquid equity securities**.

```
+-------------------------------------------------------------------------+
|                  BVMT Official Market (76 Listed Equities)             |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |           Tunis Bourse Challenge Universe (42 Equities)           |  |
|  |  • 40 Continuous Trading Mode ('Continu')                         |  |
|  |  • 2 Fixing Trading Mode ('Fixing': TRE, WIFAK)                   |  |
|  |  • Manual order entry strictly permitted                          |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |           Non-Challenge Listed Equities (34 Equities)             |  |
|  |  • Includes: MNP (MONOPRIX), SCN (ESSOUKNA), AL, AETEC, etc.      |  |
|  |  • 100% Valid for Quantitative Research & Signal Benchmarking    |  |
|  |  • STRICTLY BLOCKED from Actionable Challenge Order Plans        |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

### Safety Rules Enforced in Platform:
1. **Universe Gating**: Any security outside these 42 instruments is classified as `in_challenge_universe = False` and `order_entry_eligibility = "NOT_IN_UNIVERSE"`.
2. **Order Sizing Block**: In `TUNIS_BOURSE_CHALLENGE` mode, non-members have `suggested_shares = 0`, `is_actionable = False`, and are restricted to `RESEARCH_CANDIDATE` category.
3. **Research Separation**: Non-challenge stocks (such as `MONOPRIX` or `ESSOUKNA`) remain fully analyzable in the Market Explorer and Research engine with verified prices, but cannot be sized for competition execution.
4. **Pre-Opening Status ("non coté")**: When the challenge quotation sheet reports a security as `"non coté"`, this reflects an exchange activity state (pre-market, waiting for 10:00 AM auction match), NOT a permanent disqualification. The platform marks this with a blue informational badge without zeroing reference prices or permanently disqualifying the security.

---

## 2. The 42 Official Challenge Equities

| # | Challenge Symbol | Official BVMT Name | ISIN | Quotation Group | Trading Mode | Min Price | Max Price | Tick Size | Threshold |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `AB` | AMEN BANK | TN0003400058 | 11 | Continu | 42.680 | 47.160 | 0.010 | 5.0% |
| 2 | `ATB` | ARAB TUNISIAN BANK | TN0003600350 | 11 | Continu | 3.520 | 3.880 | 0.010 | 5.0% |
| 3 | `ATL` | ATTIJARI LEASING | TN0004700100 | 11 | Continu | 4.850 | 5.350 | 0.010 | 5.0% |
| 4 | `ARTES` | ARTES | TN0007300015 | 11 | Continu | 8.840 | 9.760 | 0.010 | 5.0% |
| 5 | `TJARI` | ATTIJARI BANK | TN0001200401 | 11 | Continu | 62.230 | 68.770 | 0.010 | 5.0% |
| 6 | `TJL` | TUNISIE LEASING & FAC | TN0002100907 | 11 | Continu | 17.580 | 19.420 | 0.010 | 5.0% |
| 7 | `BT` | BANQUE DE TUNISIE | TN0004400057 | 11 | Continu | 5.420 | 5.980 | 0.010 | 5.0% |
| 8 | `BNA` | BNA BANK | TN0003100609 | 11 | Continu | 8.840 | 9.760 | 0.010 | 5.0% |
| 9 | `BH` | BH BANK | TN0001900604 | 11 | Continu | 12.350 | 13.650 | 0.010 | 5.0% |
| 10 | `BIAT` | BIAT | TN0001800457 | 11 | Continu | 110.200 | 121.800 | 0.010 | 5.0% |
| 11 | `CC` | CARTHAGE CEMENT | TN0007400013 | 11 | Continu | 2.190 | 2.410 | 0.010 | 5.0% |
| 12 | `CITY` | CITY CARS | TN0007550015 | 11 | Continu | 15.200 | 16.800 | 0.010 | 5.0% |
| 13 | `DH` | DELICE HOLDING | TN0007670011 | 11 | Continu | 18.150 | 20.050 | 0.010 | 5.0% |
| 14 | `NAKL` | ENNAKL AUTOMOBILES | TN0007410012 | 11 | Continu | 10.640 | 11.760 | 0.010 | 5.0% |
| 15 | `ECYCL` | EURO-CYCLES | TN0007570013 | 11 | Continu | 10.450 | 11.550 | 0.010 | 5.0% |
| 16 | `ICF` | ICF | TN0003200755 | 11 | Continu | 75.620 | 83.580 | 0.010 | 5.0% |
| 17 | `LNDOR` | LAND OR | TN0007510019 | 11 | Continu | 9.880 | 10.920 | 0.010 | 5.0% |
| 18 | `AMV` | ASSU MAGHREBIA VIE | TNDKJ8O68X14 | 11 | Continu | 6.080 | 6.720 | 0.010 | 5.0% |
| 19 | `SAM` | ATELIER MEUBLE INT | TN0007740012 | 11 | Continu | 6.270 | 6.930 | 0.010 | 5.0% |
| 20 | `MPBS` | MPBS | TN0007440019 | 11 | Continu | 10.740 | 11.860 | 0.010 | 5.0% |
| 21 | `NBL` | NEW BODY LINE | TN0007560014 | 11 | Continu | 4.850 | 5.350 | 0.010 | 5.0% |
| 22 | `OTH` | ONE TECH HOLDING | TN0007580012 | 11 | Continu | 9.500 | 10.500 | 0.010 | 5.0% |
| 23 | `PGH` | POULINA GP HOLDING | TN0005700018 | 11 | Continu | 10.830 | 11.970 | 0.010 | 5.0% |
| 24 | `SAH` | SAH | TN0007610017 | 11 | Continu | 10.450 | 11.550 | 0.010 | 5.0% |
| 25 | `SFBT` | SFBT | TN0001100551 | 11 | Continu | 12.070 | 13.330 | 0.010 | 5.0% |
| 26 | `SIAME` | SIAME | TN0006590012 | 11 | Continu | 3.520 | 3.880 | 0.010 | 5.0% |
| 27 | `SMART` | SMART TUNISIE | TNMSY4N64C71 | 11 | Continu | 14.250 | 15.750 | 0.010 | 5.0% |
| 28 | `SOTET` | SOTETEL | TN0006530018 | 11 | Continu | 6.560 | 7.240 | 0.010 | 5.0% |
| 29 | `STPAP` | SOTIPAPIER | TN0007630015 | 11 | Continu | 4.660 | 5.140 | 0.010 | 5.0% |
| 30 | `STPIL` | SOTRAPIL | TN0007030018 | 11 | Continu | 14.730 | 16.270 | 0.010 | 5.0% |
| 31 | `MGR` | SOTUMAG | TN0006580013 | 11 | Continu | 6.180 | 6.820 | 0.010 | 5.0% |
| 32 | `SOTUV` | SOTUVER | TN0006560015 | 11 | Continu | 12.350 | 13.650 | 0.010 | 5.0% |
| 33 | `SPDIT` | SPDIT - SICAF | TN0001400704 | 11 | Continu | 11.400 | 12.600 | 0.010 | 5.0% |
| 34 | `STA` | STA | TNNGTFLC2986 | 11 | Continu | 110.200 | 121.800 | 0.010 | 5.0% |
| 35 | `STB` | STB BANK | TN0002600955 | 11 | Continu | 3.140 | 3.460 | 0.010 | 5.0% |
| 36 | `TLNET` | TELNET HOLDING | TN0007450018 | 11 | Continu | 5.130 | 5.670 | 0.010 | 5.0% |
| 37 | `TPR` | TPR | TN0007270010 | 11 | Continu | 6.650 | 7.350 | 0.010 | 5.0% |
| 38 | `TRE` | TUNIS RE | TN0007390016 | 12 | Fixing | 7.980 | 8.820 | 0.010 | 5.0% |
| 39 | `TLS` | TUNISIE LEASING & FAC | TN0002100907 | 11 | Continu | 17.580 | 19.420 | 0.010 | 5.0% |
| 40 | `UIB` | UIB | TN0003900107 | 11 | Continu | 25.650 | 28.350 | 0.010 | 5.0% |
| 41 | `UMED` | UNIMED | TN0007720014 | 11 | Continu | 7.790 | 8.610 | 0.010 | 5.0% |
| 42 | `WIFAK` | WIFAK INT BANK | TN0007280019 | 12 | Fixing | 8.840 | 9.760 | 0.010 | 5.0% |

---

## 3. Microstructure & Trading Mode Differences

1. **Continuous Securities (40 stocks)**:
   - Quotation Group 11.
   - Pre-opening from 08:30 to 10:00 Africa/Tunis.
   - Continuous order matching from 10:00 to 14:10 Africa/Tunis.
   - Runoff matching at 14:15 Africa/Tunis.
   - Dynamic threshold ±3.0% around last traded price; static threshold ±5.0% around reference close.

2. **Fixing Securities (2 stocks: `TRE`, `WIFAK`)**:
   - Quotation Group 12.
   - Order collection from 08:30 to 13:00 Africa/Tunis.
   - Single daily match auction at 13:00 Africa/Tunis.
   - Static threshold ±5.0% around reference close.
   - Orders cannot match continuously during the day.
