"""Enipower Brindisi (CTE3: U8, U9, U10) - copertura dati, ore a zero, episodi di fermata
e classificazione guasto / fermata di mercato con dati di mercato (PZ SUD, PSV, EUA).

Uso:
    python -I analisi_zeri_cte3.py --orario CTE3_orario_2017_2026_FINALE.csv \
        --mercato CTE3_orario_prezzi_costi.csv --sud-lug sud_orario_202606_20260712_utc.csv \
        --candidati report_candidati_outage.xlsx --raw2017 enipower_brindisi_generazione.csv \
        --out analisi_zeri_CTE3.xlsx

Tutti gli orari sono UTC. Granularita' oraria (dal 2025 ENTSO-E pubblica a 15 minuti: media oraria).
"""
import argparse

import numpy as np
import pandas as pd

UNITS = ["U8", "U9", "U10"]
UNIT_NAME = {"UP_NPWRBRNDSI_8": "U8", "UP_NPWRBRNDSI_9": "U9", "UP_NPWRBRNDSI_10": "U10"}
ZERO_MW = 1.0            # soglia "zero": <= 1 MW (stessa soglia del report candidati)
MIN_UNIT_EP_H = 2        # durata minima episodi per unita' (come report candidati)
FULL_LOAD_UNIT = 300.0   # MW: unita' "a carico" nell'ora precedente (min tecnico ~220, max ~380)
FULL_LOAD_PLANT = 600.0  # MW: impianto "a carico" nell'ora precedente
SPREAD_RESTART = 20.0    # EUR/MWh: soglia di riaccensione osservata (report interno CTE3 v3.1: +19/+24)
LONG_STOP_H = 168        # >= 7 giorni: fermata lunga (revisione o conservazione)

# Festivita' nazionali italiane fisse + Pasquetta (lun. dell'Angelo) 2017-2026
FIXED = ["01-01", "01-06", "04-25", "05-01", "06-02", "08-15", "11-01", "12-08", "12-25", "12-26"]
EASTER_MON = ["2017-04-17", "2018-04-02", "2019-04-22", "2020-04-13", "2021-04-05",
              "2022-04-18", "2023-04-10", "2024-04-01", "2025-04-21", "2026-04-06"]


def holidays():
    s = {pd.Timestamp(f"{y}-{d}") for y in range(2017, 2027) for d in FIXED}
    s |= {pd.Timestamp(d) for d in EASTER_MON}
    return s


def load_orario(path):
    f = pd.read_csv(path, parse_dates=["hour"])
    f["t"] = f["hour"].dt.tz_convert("UTC").dt.tz_localize(None)
    f = f.drop_duplicates("t").set_index("t").sort_index()
    return f[UNITS + ["src"]]


def load_mercato(path, sud_lug):
    c = pd.read_csv(path, parse_dates=["hour_utc"])
    c["t"] = c["hour_utc"].dt.tz_convert("UTC").dt.tz_localize(None)
    c = c.set_index("t")[["sud", "pun", "psv", "eua", "cm", "spread"]]
    c["fonte_mercato"] = "CTE3_orario_prezzi_costi (GME MGP, MGP-GAS, EUA)"
    j = pd.read_csv(sud_lug, parse_dates=["utc"]).set_index("utc")
    j = j[j.index > c.index.max()]
    if len(j):
        add = pd.DataFrame(index=j.index, data={"sud": j["sud"]})
        # IPOTESI: PSV ed EUA di luglio 2026 non disponibili -> CM fermo all'ultimo valore (30/06/2026)
        last = c.dropna(subset=["cm"]).iloc[-1]
        add["psv"], add["eua"], add["cm"] = last["psv"], last["eua"], last["cm"]
        add["spread"] = add["sud"] - add["cm"]
        add["fonte_mercato"] = "GME MGP SUD 15' (xlsx); CM = ultimo valore 30/06/2026 (IPOTESI)"
        c = pd.concat([c, add])
    return c


def runs(mask):
    """Blocchi consecutivi True su indice orario regolare (con NaN = interruzione)."""
    m = mask.fillna(False).astype(bool).values
    idx = mask.index
    out, start = [], None
    for i, v in enumerate(m):
        if v and start is None:
            start = i
        if (not v or i == len(m) - 1) and start is not None:
            end = i if v else i - 1
            out.append((idx[start], idx[end]))
            start = None
    return out


def classify(dur_h, prev_mw, full_load, spread_mean, pz_mean, has_mkt, cm_is_assumed):
    abrupt = prev_mw is not None and not np.isnan(prev_mw) and prev_mw >= full_load
    if dur_h >= LONG_STOP_H and has_mkt and spread_mean >= SPREAD_RESTART:
        lab = "FERMATA LUNGA NON DI MERCATO (revisione/guasto prolungato) - probabile"
        why = (f"durata {dur_h:.0f} h >= 7 gg con spread medio {spread_mean:+.1f} EUR/MWh sopra la soglia di "
               "riaccensione: restare fermi non conveniva")
    elif dur_h >= LONG_STOP_H and has_mkt and spread_mean >= 0:
        lab = "FERMATA LUNGA - causa incerta (revisione o fermo economico)"
        why = (f"durata {dur_h:.0f} h >= 7 gg, spread medio {spread_mean:+.1f} EUR/MWh positivo ma sotto la "
               "soglia di riaccensione: compatibile sia con revisione sia con conservazione economica")
    elif not has_mkt:
        lab = ("ARRESTO BRUSCO (firma da guasto) - prezzi assenti" if abrupt
               else "NON CLASSIFICABILE - prezzi di mercato assenti")
        why = f"MW ora precedente {prev_mw:.0f}" if prev_mw is not None and not np.isnan(prev_mw) else "n.d."
    elif abrupt and spread_mean >= 0:
        lab = "GUASTO / ARRESTO FORZATO - probabile"
        why = (f"da {prev_mw:.0f} MW a 0 in <=1 h con spread medio {spread_mean:+.1f} EUR/MWh "
               "(fermarsi faceva perdere margine)")
    elif spread_mean >= SPREAD_RESTART:
        lab = "GUASTO / INDISPONIBILITA' - probabile"
        why = (f"spread medio {spread_mean:+.1f} EUR/MWh >= soglia di riaccensione {SPREAD_RESTART:.0f}: "
               "un'unita' disponibile sarebbe stata in marcia")
    elif abrupt and spread_mean < 0:
        lab = "INDETERMINATO - arresto brusco in ore non remunerative"
        why = f"da {prev_mw:.0f} MW a 0 in <=1 h ma spread medio {spread_mean:+.1f} EUR/MWh"
    elif spread_mean < 0:
        lab = "FERMATA DI MERCATO - probabile"
        why = f"spegnimento graduale e spread medio {spread_mean:+.1f} EUR/MWh (PZ sotto il costo marginale)"
    else:
        lab = "FERMATA DI MERCATO - possibile"
        why = (f"spegnimento graduale, spread medio {spread_mean:+.1f} EUR/MWh: positivo ma sotto la "
               f"soglia di riaccensione ~{SPREAD_RESTART:.0f}")
    if cm_is_assumed:
        why += " [CM luglio 2026 ipotizzato = 30/06/2026]"
    return lab, why


def episode_rows(df, mk, mask, level, unit=None, min_h=1, hol=None):
    rows = []
    for s, e in runs(mask):
        dur = int((e - s) / pd.Timedelta(hours=1)) + 1
        if dur < min_h:
            continue
        prev_t = s - pd.Timedelta(hours=1)
        if level == "impianto":
            prev = df.loc[prev_t, UNITS].sum() if prev_t in df.index and df.loc[prev_t, UNITS].notna().all() else np.nan
            full = FULL_LOAD_PLANT
        else:
            prev = df.loc[prev_t, unit] if prev_t in df.index else np.nan
            full = FULL_LOAD_UNIT
        win = mk.loc[s:e]
        has_mkt = win["sud"].notna().mean() >= 0.5 if len(win) else False
        sp = win["spread"].mean() if has_mkt else np.nan
        pz = win["sud"].mean() if has_mkt else np.nan
        cm = win["cm"].mean() if has_mkt else np.nan
        neg = (win["spread"] < 0).mean() if has_mkt else np.nan
        assumed = has_mkt and win["fonte_mercato"].astype(str).str.contains("IPOTESI").any()
        hours = pd.date_range(s, e, freq="h")
        we = np.mean([(h.dayofweek >= 5) or (h.normalize() in hol) for h in hours])
        lab, why = classify(dur, prev, full, sp, pz, has_mkt, assumed)
        r = {"livello": level, "unita": unit or "U8+U9+U10", "inizio_utc": s, "fine_utc": e + pd.Timedelta(hours=1),
             "durata_h": dur, "durata_gg": round(dur / 24, 2), "anno_inizio": s.year,
             "MW_ora_prima": round(prev, 1) if prev == prev else np.nan,
             "PZ_SUD_medio": round(pz, 2), "CM_medio": round(cm, 2), "spread_medio": round(sp, 2),
             "quota_ore_spread_neg": round(neg, 3) if neg == neg else np.nan,
             "quota_ore_weekend_festivi": round(we, 3), "classificazione": lab, "motivazione": why}
        if level == "unita":
            others = [u for u in UNITS if u != unit]
            r["altre_unita_MW_medi"] = round(df.loc[s:e, others].sum(axis=1).mean(), 1)
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    for a in ["--orario", "--mercato", "--sud-lug", "--candidati", "--raw2017", "--out"]:
        ap.add_argument(a, required=True)
    a = ap.parse_args()
    hol = holidays()

    o = load_orario(a.orario)
    mk = load_mercato(a.mercato, a.sud_lug)
    t0, t1 = o.index.min(), o.index.max()
    grid = pd.date_range(t0, t1, freq="h")
    df = o.reindex(grid)
    df["present"] = df[UNITS].notna().all(axis=1)
    mk = mk.reindex(grid)

    # --- 1. Copertura e ore a zero per anno
    rows = []
    for y in range(t0.year, t1.year + 1):
        cal = pd.date_range(f"{y}-01-01", f"{y + 1}-01-01", freq="h", inclusive="left")
        win = cal[(cal >= t0) & (cal <= t1)]
        d = df.loc[win]
        pres = d[d["present"]]
        allz = (pres[UNITS] <= ZERO_MW).all(axis=1)
        allz0 = (pres[UNITS] == 0).all(axis=1)
        r = {"anno": y, "ore_calendario": len(cal), "ore_finestra_dati": len(win),
             "primo_dato_utc": win.min(), "ultimo_dato_utc": win.max(),
             "ore_con_dato": int(d["present"].sum()), "ore_mancanti": int((~d["present"]).sum()),
             "copertura_su_finestra_%": round(100 * d["present"].mean(), 2),
             "copertura_su_anno_%": round(100 * d["present"].sum() / len(cal), 2),
             "ore_3_unita_zero(<=1MW)": int(allz.sum()),
             "%_ore_3_unita_zero": round(100 * allz.mean(), 3),
             "ore_3_unita_esattamente_0MW": int(allz0.sum())}
        for u in UNITS:
            r[f"%_ore_{u}_zero"] = round(100 * (pres[u] <= ZERO_MW).mean(), 2)
        r["ore_con_prezzo_SUD"] = int(mk.loc[win, "sud"].notna().sum())
        rows.append(r)
    cov = pd.DataFrame(rows)

    # ore mancanti: blocchi
    miss = runs(~df["present"])
    gaps = pd.DataFrame([{"inizio_utc": s, "fine_utc": e + pd.Timedelta(hours=1),
                          "ore": int((e - s) / pd.Timedelta(hours=1)) + 1} for s, e in miss])

    # --- 2. Episodi impianto (tutte e tre a zero) e per unita'
    allzero = (df[UNITS] <= ZERO_MW).all(axis=1).where(df["present"])
    ep_p = episode_rows(df, mk, allzero, "impianto", hol=hol)
    ep_u = pd.concat([episode_rows(df, mk, (df[u] <= ZERO_MW).where(df["present"]), "unita", u,
                                   MIN_UNIT_EP_H, hol) for u in UNITS], ignore_index=True)
    ep_u = ep_u.sort_values(["inizio_utc", "unita"]).reset_index(drop=True)

    # verifica dati grezzi 2017-2022 (ENTSO-E 16.1.A) vs serie usata
    r = pd.read_csv(a.raw2017, sep="\t", parse_dates=["DateTime(UTC)"])
    r = r[r["GenerationUnitName"].isin(UNIT_NAME) & (r["AreaTypeCode"] == "BZN")]
    r["u"] = r["GenerationUnitName"].map(UNIT_NAME)
    rp = r.pivot_table(index="DateTime(UTC)", columns="u", values="ActualGenerationOutput[MW]", aggfunc="mean")
    jj = rp.join(o[UNITS], rsuffix="_s", how="inner")
    ver = pd.DataFrame([{"verifica": f"ENTSO-E 16.1.A grezzo 2017-2022 vs serie oraria - {u}",
                         "ore_confrontate": len(jj), "scarto_max_MW": float((jj[u] - jj[u + "_s"]).abs().max())}
                        for u in UNITS])

    # --- 3. Incrocio con report_candidati_outage.xlsx (luglio 2026)
    cand = pd.read_excel(a.candidati, "candidati_outage")
    cb = cand[cand["unit_name"].isin(UNIT_NAME)].copy()
    cb["unita"] = cb["unit_name"].map(UNIT_NAME)
    out = []
    for _, c in cb.iterrows():
        s, e = c["start_utc"], c["end_utc"]
        m = ep_u[(ep_u.unita == c.unita) & (ep_u.inizio_utc < e) & (ep_u.fine_utc > s)]
        win = mk.loc[s:e]
        others = [u for u in UNITS if u != c.unita]
        rec = {"unita": c.unita, "candidato_inizio_utc": s, "candidato_fine_utc": e,
               "candidato_durata_h": c["duration_hours"], "confidenza_report": c["confidence"],
               "tipo_episodio_report": c["episode_type"],
               "episodio_serie_oraria_inizio": m.inizio_utc.min() if len(m) else pd.NaT,
               "episodio_serie_oraria_fine": m.fine_utc.max() if len(m) else pd.NaT,
               "riscontro_serie_oraria": "si" if len(m) else "no",
               "PZ_SUD_medio": round(win["sud"].mean(), 2) if win["sud"].notna().any() else np.nan,
               "spread_medio(CM ipotizzato)": round(win["spread"].mean(), 2) if win["spread"].notna().any() else np.nan,
               "altre_unita_MW_medi": round(df.loc[s:e, others].sum(axis=1).mean(), 1),
               "quota_ore_weekend": round(np.mean([h.dayofweek >= 5 for h in pd.date_range(s, e, freq="h")]), 2),
               "classificazione": m.classificazione.iloc[0] if len(m) else "n.d.",
               "motivazione": m.motivazione.iloc[0] if len(m) else ""}
        out.append(rec)
    xc = pd.DataFrame(out).sort_values("candidato_inizio_utc")
    excl = cand[cand["unit_name"].str.contains("SRGN", na=False)][["unit_name", "start_utc", "end_utc", "duration_hours"]]

    # --- 4. Riepiloghi
    sp = ep_p.groupby(["anno_inizio", "classificazione"]).agg(episodi=("durata_h", "size"), ore=("durata_h", "sum")).reset_index()
    su = ep_u.groupby(["anno_inizio", "unita", "classificazione"]).agg(episodi=("durata_h", "size"), ore=("durata_h", "sum")).reset_index()

    meta = pd.DataFrame({"voce": [
        "Fonte produzione", "Fonte mercato", "Fonte candidati", "Periodo",
        "Soglia zero", "Episodio impianto", "Episodio unita'",
        "Arresto brusco", "Spread", "Soglia riaccensione", "Fermata lunga",
        "IPOTESI 1", "IPOTESI 2", "IPOTESI 3", "LIMITE 1", "LIMITE 2", "LIMITE 3"], "descrizione": [
        "CTE3_orario_2017_2026_FINALE.csv (Drive): ENTSO-E 16.1.A per unita', media oraria, dedup aree IT/IT-SOUTH",
        "CTE3_orario_prezzi_costi.csv (Drive): PZ SUD e PUN GME orari, PSV MGP-GAS, EUA, CM = PSV/0,51 + 0,39*EUA + 4; "
        "luglio 2026: prezzi SUD da 20260601_20260712_MGP_PrezziZonali_SUD.xlsx (15', media oraria)",
        "report_candidati_outage.xlsx (Drive, scan statistico ENTSO-E 1-18/07/2026)",
        f"{t0} -> {t1} UTC",
        f"produzione <= {ZERO_MW} MW nell'ora",
        "ore consecutive con U8, U9 e U10 tutte a zero (interrotte da ore mancanti)",
        f"ore consecutive con l'unita' a zero, durata >= {MIN_UNIT_EP_H} h",
        f"MW nell'ora precedente >= {FULL_LOAD_UNIT:.0f} (unita') o >= {FULL_LOAD_PLANT:.0f} (impianto): da carico a zero in <= 1 h",
        "PZ SUD - CM, media sulle ore dell'episodio",
        f"{SPREAD_RESTART:.0f} EUR/MWh: soglia di riaccensione osservata (+19/+24, report interno CTE3 v3.1 par. 5.4)",
        f">= {LONG_STOP_H} h con spread medio >= 0: revisione o guasto prolungato",
        "CM ricostruito con rendimento 51%, fattore emissione 0,39 t/MWh, VOM 4 EUR/MWh (assunzioni del report interno, non dati Enipower)",
        "Luglio 2026: PSV ed EUA non disponibili sul Drive -> CM fermo al valore del 30/06/2026",
        "La classificazione e' inferenziale (prezzo/forma dello spegnimento): NON e' una prova; "
        "il riscontro definitivo e' ENTSO-E 15.1 (indisponibilita' dichiarate) / REMIT",
        "ENTSO-E 15.1 (indisponibilita' dichiarate) non disponibile in questa sessione: host ENTSO-E bloccato "
        "dalla rete dell'ambiente e file CTE3_outages_15_1_eventi non presente sul Drive",
        "Prezzi di mercato assenti 2017-2020 sul Drive: episodi di quegli anni classificati solo per forma dello spegnimento",
        "ENTSO-E non pubblica Brindisi dopo il 18/07/2026 21:00 UTC (ultimo dato disponibile)"]})

    with pd.ExcelWriter(a.out, engine="openpyxl") as w:
        meta.to_excel(w, sheet_name="metodo_ipotesi", index=False)
        cov.to_excel(w, sheet_name="copertura_zeri_annui", index=False)
        ep_p.to_excel(w, sheet_name="episodi_3_unita_zero", index=False)
        sp.to_excel(w, sheet_name="riepilogo_impianto", index=False)
        ep_u.to_excel(w, sheet_name="episodi_per_unita", index=False)
        su.to_excel(w, sheet_name="riepilogo_unita", index=False)
        xc.to_excel(w, sheet_name="incrocio_candidati_lug26", index=False)
        excl.to_excel(w, sheet_name="candidati_esclusi_SRGN", index=False)
        gaps.to_excel(w, sheet_name="ore_mancanti", index=False)
        ver.to_excel(w, sheet_name="verifiche", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                L = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, L + 2), 70)
            ws.freeze_panes = "A2"
    print(cov.to_string())
    print(ep_p.to_string())
    print(sp.to_string())
    print(su.groupby(["unita", "classificazione"]).ore.sum().to_string())
    print(xc.to_string())
    print(ver.to_string())
    print(gaps.to_string())


if __name__ == "__main__":
    main()
