# Enipower Brindisi (CTE3: U8, U9, U10): ore a zero, episodi di fermata, guasto o mercato

**File:** `analisi_zeri_CTE3.xlsx` (risultati) e `analisi_zeri_cte3.py` (script che li riproduce).
Gli orari sono **UTC**. La granularità è **oraria**: dal 2025 i dati arrivano a 15 minuti e sono stati mediati per ora.

## Fonti (tutte prese dal Google Drive del progetto)

| Dato | File | Periodo |
|---|---|---|
| Produzione per unità (ENTSO-E 16.1.A) | `CTE3_orario_2017_2026_FINALE.csv` | 27/06/2017 → 18/07/2026 21:00 (è l'ultimo dato pubblicato da ENTSO-E) |
| Verifica sul dato grezzo ENTSO-E | `enipower_brindisi_generazione.csv(.zip)`, `enipower_brindisi_generazione.zip` (2023-24), `ENIPOWER_LUGLIO_2026_FMS.zip` | 2017-2024 e luglio 2026 |
| Prezzo zonale SUD, PUN, PSV, EUA, costo marginale (CM) | `CTE3_orario_prezzi_costi.csv` | 01/01/2021 → 30/06/2026 |
| Prezzo zonale SUD a 15 minuti | `20260601_20260712_MGP_PrezziZonali_SUD.xlsx` | fino al 12/07/2026 |
| Candidati outage | `report_candidati_outage.xlsx` | 1-18/07/2026 |

**Verifiche fatte:**
- La serie oraria coincide con il dato grezzo ENTSO-E su 47.544 ore (2017-2022) con scarto 0 MW, e su 58.440 ore (2018-2024) con scarto 0.
- Su luglio 2026 lo scarto massimo è ≤ 2,8 MW.
- I prezzi SUD del file xlsx coincidono con quelli del dataset di mercato sulle 720 ore di giugno 2026 (scarto < 0,001 €/MWh).

## Risultati: copertura e ore con tutte e tre le unità a zero

"Zero" significa produzione ≤ 1 MW. Nelle stesse ore il valore è anche esattamente 0 MW.

| Anno | Finestra dati | Copertura sulla finestra | Ore 3 unità a zero | % ore 3 unità a zero | % ore U8 a zero | % ore U9 a zero | % ore U10 a zero |
|---|---|---|---|---|---|---|---|
| 2017 | dal 27/06 | 99,47% | 0 | 0,000% | 15,8 | 6,3 | 7,5 |
| 2018 | anno intero | 100% | 0 | 0,000% | 14,7 | 13,3 | 12,8 |
| 2019 | anno intero | 100% | 21 | 0,240% | 19,6 | 4,1 | 9,1 |
| 2020 | anno intero | 100% | 0 | 0,000% | 21,8 | 4,7 | 4,7 |
| 2021 | anno intero | 100% | 0 | 0,000% | 21,9 | 6,7 | 3,2 |
| 2022 | anno intero | 99,73% | 0 | 0,000% | 29,7 | 1,4 | 16,5 |
| 2023 | anno intero | 100% | 1 | 0,011% | 30,7 | 15,3 | 6,5 |
| 2024 | anno intero | 100% | 0 | 0,000% | 31,1 | 5,2 | 9,7 |
| 2025 | anno intero | 99,11% | 0 | 0,000% | 32,7 | 5,4 | 37,4 |
| 2026 | fino al 18/07 | 98,45% | 0 | 0,000% | 46,7 | 6,8 | 34,4 |

Le ore mancanti sono elencate nel foglio `ore_mancanti`: in tutto 200 ore, quasi tutte giorni interi isolati.

### Episodi con tutte e tre le unità a zero

| Inizio (UTC) | Fine (UTC) | Durata | Classificazione |
|---|---|---|---|
| 22/11/2019 03:00 | 23/11/2019 00:00 | 21 h | Non classificabile: mancano i prezzi del 2019. Lo spegnimento è stato graduale (23 MW nell'ora prima). Il report interno lo indica come fermo non dichiarato. |
| 13/09/2023 04:00 | 13/09/2023 05:00 | 1 h | Guasto probabile: da 807 MW a 0 in un'ora, con spread +17 €/MWh. È coerente con il trip di sito dichiarato a ENTSO-E, citato nel report interno. |

L'impianto non si ferma quasi mai del tutto. Le fermate significative sono quelle **di singola unità**: 1.026 episodi di durata ≥ 2 h, elencati nei fogli `episodi_per_unita` e `riepilogo_unita`.

## Come è stato distinto il guasto dalla fermata di mercato (è un'inferenza, non una prova)

Per ogni episodio lo script calcola:
- lo **spread** medio (PZ SUD − CM);
- i **MW nell'ora prima** dello spegnimento;
- la quota di ore cadute nel weekend o in festivi.

| Etichetta | Regola |
|---|---|
| Guasto / arresto forzato probabile | Da ≥ 300 MW (unità) o ≥ 600 MW (impianto) a 0 in un'ora, con spread ≥ 0 |
| Guasto / indisponibilità probabile | Spread medio ≥ +20 €/MWh, cioè sopra la soglia di riaccensione osservata (+19/+24 €/MWh) |
| Fermata lunga non di mercato probabile | Durata ≥ 7 giorni con spread ≥ +20 |
| Fermata lunga, causa incerta | Durata ≥ 7 giorni con spread tra 0 e +20: può essere una revisione o un fermo economico |
| Fermata di mercato probabile | Spegnimento graduale con spread < 0 (il PZ sta sotto il costo marginale) |
| Fermata di mercato possibile | Spegnimento graduale con spread tra 0 e +20 |
| Indeterminato | Arresto brusco in ore con spread negativo |
| Non classificabile | Prezzi assenti (2017-2020 e dal 13/07/2026) |

## Incrocio con `report_candidati_outage.xlsx` (luglio 2026)

Sette candidati riguardano le unità Enipower. Sei righe riguardano invece **UP_SRGNPGLCNT_1**, che non è Enipower (probabilmente Sorgenia): sono escluse e riportate nel foglio `candidati_esclusi_SRGN`. Tutti e sette i candidati trovano riscontro nella serie oraria, e tutti cadono di **sabato o domenica**.

| Unità | Inizio candidato (UTC) | Durata | PZ SUD medio | Spread (CM ipotizzato) | Classificazione |
|---|---|---|---|---|---|
| U10 | 04/07 03:15 | 11,75 h | 58,8 | −64,8 | Mercato probabile |
| U8 | 04/07 04:15 | 35,75 h | 85,1 | −38,4 | Mercato probabile |
| U10 | 05/07 05:15 | 8,75 h | 18,3 | −105,2 | Mercato probabile |
| U8 | 11/07 02:15 | 38,75 h | 131,0 | +7,4 | Mercato possibile |
| U10 | 11/07 03:15 | 10,75 h | 129,7 | +6,2 | Mercato possibile |
| U10 | 12/07 04:15 | 10,75 h | 100,0 | −23,5 | Mercato probabile |
| U10 | 18/07 06:15 | 7 h | — | — | Non classificabile: prezzi disponibili solo fino al 12/07 |

Nessuno dei candidati di luglio mostra la firma di un guasto. Il report interno CTE3 v3.1 dice inoltre che a luglio 2026 non risultano indisponibilità dichiarate.

## Ipotesi e limiti

1. **Costo marginale.** CM = PSV/0,51 + 0,39·EUA + 4. Rendimento, fattore di emissione e VOM sono assunzioni del report interno, non dati Enipower.
2. **Luglio 2026.** PSV ed EUA non sono disponibili, quindi il CM è tenuto fermo al valore del 30/06/2026 (**ipotesi**).
3. **Soglie.** La soglia di +20 €/MWh viene dalle soglie di accensione osservate (report interno §5.4). Le soglie di 300 e 600 MW per l'"arresto brusco" sono una scelta di questa analisi.
4. **Indisponibilità dichiarate (ENTSO-E 15.1).** Non sono state usate:
   - la rete di questo ambiente blocca gli host ENTSO-E;
   - il file `CTE3_outages_15_1_eventi_2017_2026.csv` citato nel report interno non è sul Drive.

   Sono il riscontro definitivo per confermare o smentire le etichette.
5. **Prezzi 2017-2020.** Non sono sul Drive: gli episodi di quegli anni sono classificati solo in base a come si spegne l'unità.
6. **File 2025 non scaricabile.** Il file grezzo `enipower_brindisi_generazione2025.csv` (37 MB) supera il limite di download di 10 MB. Per il 2025 e il primo semestre 2026 la serie usata è quindi verificata solo contro il dataset di mercato (scarto ≤ 0,05 MW) e contro luglio 2026.
