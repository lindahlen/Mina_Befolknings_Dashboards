import os
import pandas as pd
import json
import numpy as np

# ==========================================
# SÖKVÄGAR OCH INSTÄLLNINGAR
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    main_folder = os.path.abspath(os.path.join(current_folder, '..'))
    excel_folder = os.path.join(main_folder, 'excel_filer')
    json_folder = os.path.join(main_folder, 'json_data')
except NameError:
    excel_folder = '../excel_filer'
    json_folder = '../json_data'

if not os.path.exists(json_folder):
    os.makedirs(json_folder)

FILNAMN_EXCEL = os.path.join(excel_folder, 'Cupmästare_Målskyttar.xlsx')
FILNAMN_JSON = os.path.join(json_folder, 'cup_djupdykning.json')

def clean_data(val):
    if pd.isna(val): return ""
    if isinstance(val, (np.int64, np.float64, int, float)):
        if val == int(val): return str(int(val))
        return str(val).replace('.0', '')
    return str(val).strip()

def bygg_json():
    print("=" * 50)
    print("STARTAR BYGGE AV DJUPDYKNINGS-JSON")
    print("=" * 50)
    
    try:
        xls = pd.read_excel(FILNAMN_EXCEL, sheet_name=None)
        print(f"✅ Excel-fil öppnad. Hittade flikarna: {list(xls.keys())}")
    except Exception as e:
        print(f"❌ FEL: Kunde inte öppna Excel-filen. \nFelmeddelande: {e}")
        return

    db = {"spelare": {}, "sasonger": {}, "matcher": {}, "admin_varningar": []}

    # 1. SPELARNAMN
    if 'Spelarnamn' in xls:
        seen_names = {}
        for _, row in xls['Spelarnamn'].iterrows():
            namn = clean_data(row.get('Namn', ''))
            if namn:
                fodd = clean_data(row.get('Födelsedatum', ''))
                ar = clean_data(row.get('Födelseår', ''))
                
                # Kontrollera om exakt samma namn finns med ett helt annat födelseår!
                if namn in seen_names:
                    old_ar = seen_names[namn]
                    if ar and old_ar and ar != old_ar:
                        msg = f"Spelarnamn: '{namn}' finns inlagd flera gånger men med olika födelseår ({old_ar} vs {ar}). Saknas en siffra i namnet?"
                        if msg not in db["admin_varningar"]:
                            db["admin_varningar"].append(msg)
                else:
                    if ar: seen_names[namn] = ar

                db["spelare"][namn] = {
                    "id": clean_data(row.get('NAMN_ID', '')),
                    "klubbar": clean_data(row.get('Klubbar', '')),
                    "fodd": fodd,
                    "ar": ar
                }
        print(f"✅ Laddade in {len(db['spelare'])} spelare från 'Spelarnamn'.")

    # 2. LAGKAPTEN OCH TRÄNARE
    if 'Lagkapten_Tränare' in xls:
        df_ledare = xls['Lagkapten_Tränare']
        sas_col = 'Cupsäs' if 'Cupsäs' in df_ledare.columns else ('Säsong' if 'Säsong' in df_ledare.columns else None)
        if sas_col:
            for _, row in df_ledare.iterrows():
                sasong = clean_data(row.get(sas_col, ''))
                if sasong:
                    db["sasonger"][sasong] = {
                        "kapten": clean_data(row.get('Lagkapten_Mästare', '')),
                        "tranare_vinnare": clean_data(row.get('Tränare_Mästare', '')),
                        "tranare_tvaa": clean_data(row.get('Tränare_Tvåa', '')),
                        "pokal": clean_data(row.get('Pokal', '')),
                        "finalar": clean_data(row.get('Finalår', '')),
                        "sm_vinnare": clean_data(row.get('SM-vinnare', '')),
                        "cup_vinnare": clean_data(row.get('Cupvinnare', ''))
                    }
            print(f"✅ Laddade in ledare/pokaler/SM-vinnare för {len(db['sasonger'])} säsonger.")

    def get_match(m_id):
        m_id = str(m_id)
        if m_id not in db["matcher"]:
            db["matcher"][m_id] = {"uppstallning": [], "mal": [], "utvisningar": []}
        return db["matcher"][m_id]

    # 3. FINALLAG
    if 'Finallag' in xls:
        for idx, row in xls['Finallag'].iterrows():
            m_id = clean_data(row.get('Match_ID', ''))
            namn = clean_data(row.get('Namn', ''))
            if m_id == "": continue
            match = get_match(m_id)
            match["uppstallning"].append({
                "namn": namn,
                "pos": clean_data(row.get('Position', '')),
                "lag": clean_data(row.get('Plats', '')), 
                "minuter": clean_data(row.get('Minuter', '')),
                "byte": clean_data(row.get('Byte', ''))
            })

    # 4. MÅLSKYTTAR
    def lagg_till_mal(df, fliknamn):
        count_mal = 0
        for idx, row in df.iterrows():
            m_id = clean_data(row.get('Match_ID', ''))
            skytt = clean_data(row.get('Målskytt', ''))
            minut = clean_data(row.get('Minut', ''))
            innebord = clean_data(row.get('Innebörd', ''))
            info = clean_data(row.get('Målinfo', ''))
            
            lag = ""
            if fliknamn == 'Slutomgångar': lag = clean_data(row.get('Klubben', ''))
            else:
                lag = clean_data(row.get('Cupmästare', ''))
                if not lag: lag = clean_data(row.get('Cupmastare', ''))
            
            if m_id == "" or skytt == "": continue
            
            match = get_match(m_id)
            is_duplicate = False
            
            if fliknamn == 'Mästarna':
                for befintligt_mal in match["mal"]:
                    if befintligt_mal["skytt"] == skytt and str(befintligt_mal["minut"]) == str(minut) and befintligt_mal["innebord"] == innebord:
                        is_duplicate = True
                        befintligt_mal["merged"] = True
                        slut_lag = befintligt_mal.get("lag", "")
                        if lag and slut_lag and lag != slut_lag:
                            befintligt_mal["klubb_mismatch"] = f"Slutomg: {slut_lag} | Mästarna: {lag}"
                        elif lag and not slut_lag:
                            befintligt_mal["lag"] = lag
                        break
            
            if not is_duplicate:
                match["mal"].append({
                    "skytt": skytt,
                    "minut": minut,
                    "innebord": innebord,
                    "info": info,
                    "avgorande": clean_data(row.get('Avgörande', '')),
                    "lag": lag,
                    "kalla_flik": fliknamn
                })
                count_mal += 1
        print(f"✅ Laddade in {count_mal} mål från '{fliknamn}'.")

    if 'Målskyttar_Slutomg' in xls: lagg_till_mal(xls['Målskyttar_Slutomg'], 'Slutomgångar')
    if 'Målskyttar_Mästare' in xls: lagg_till_mal(xls['Målskyttar_Mästare'], 'Mästarna')

    # 5. UTVISNINGAR
    if 'Utvisningar' in xls:
        finalnr_till_matchid = {}
        if 'Finallag' in xls:
            for _, row in xls['Finallag'].iterrows():
                fnr = clean_data(row.get('Final_nr', ''))
                mid = clean_data(row.get('Match_ID', ''))
                if fnr and mid: finalnr_till_matchid[fnr] = mid

        for _, row in xls['Utvisningar'].iterrows():
            fnr = clean_data(row.get('Final_nr', ''))
            direkt_mid = clean_data(row.get('Match_ID', ''))
            m_id = direkt_mid if direkt_mid else finalnr_till_matchid.get(fnr, f"OKAND_{fnr}")
            
            if m_id and m_id != "":
                match = get_match(m_id)
                match["utvisningar"].append({
                    "namn": clean_data(row.get('Namn', '')),
                    "minut": clean_data(row.get('Matchminut', '')),
                    "lag": clean_data(row.get('Plats', ''))
                })

    try:
        with open(FILNAMN_JSON, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"🚀 SUCCÉ! JSON-fil sparad perfekt till: {FILNAMN_JSON}")
    except Exception as e:
        print(f"❌ FEL VID SPARANDE: {e}")

if __name__ == "__main__":
    bygg_json()