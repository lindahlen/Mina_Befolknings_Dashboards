import os
import sys
import pandas as pd
import numpy as np
import json

# =========================================================
# 1. GENERELL SETUP & SÖKVÄGSHANTERING
# =========================================================
try:
    # __file__ pekar på Specialportal/data_pipeline/bygg_vm_data.py
    current_folder = os.path.dirname(os.path.abspath(__file__))
    # Eftersom skriptet ligger i 'data_pipeline', går vi ett steg upp till modermappen 'Specialportal'
    root_folder = os.path.dirname(current_folder)
    os.chdir(root_folder)
except NameError:
    pass

print(f"📁 Arbetskatalog satt till: {os.getcwd()}")

EXCEL_DIR = "excel_filer"
JSON_DIR = "json_data"
EXCEL_FILE = os.path.join(EXCEL_DIR, "VM_matcher_samlade.xlsx")
JSON_FILE = os.path.join(JSON_DIR, "vm_data.json")

os.makedirs(JSON_DIR, exist_ok=True)

# =========================================================
# 2. HJÄLPFUNKTIONER FÖR DATATVÄTT
# =========================================================
def clean_dataframe(df):
    """Ersätter NaN med tomma strängar för att undvika JSON-krascher"""
    return df.replace({np.nan: None}).fillna("")

def safe_int(val):
    """Konverterar till int om möjligt, annars returnerar None"""
    try:
        if pd.isna(val) or val == "": return None
        return int(float(val))
    except (ValueError, TypeError):
        return None

# =========================================================
# 3. LÄSA IN OCH BYGGA DATABASEN
# =========================================================
def build_database():
    print(f"📊 Läser in flikar från {EXCEL_FILE}...")
    
    try:
        # Läs in flikarna
        df_turnering = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Turnering'))
        df_matcher = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Matcher'))
        df_mal = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Mål'))
        df_spelare = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Spelare'))
        df_utvisningar = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Utvisningar'))
        df_nationer = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Nationer'))
        
        # Byt namn om det står HSM på två ställen av misstag
        if list(df_matcher.columns).count('HSM') > 1:
            cols = list(df_matcher.columns)
            cols[cols.index('HSM', cols.index('HSM') + 1)] = 'BSM'
            df_matcher.columns = cols
            
    except Exception as e:
        print(f"❌ Fel vid inläsning: {e}")
        sys.exit(1)

    print("⚙️ Bygger hierarkisk JSON-struktur...")
    
    # Grundstrukturen för vår Dashboard
    db = {
        "metadata": {"title": "Fotbolls-VM Historik 1930-", "last_updated": str(pd.Timestamp.now().date())},
        "admin_warnings": [], # Här samlar vi alla ologiska dataskevheter
        "tournaments": {}, # Nyckel: Turn_År
        "matches": {}      # Nyckel: Match_ID
    }

    # 1. Bygg Turneringar
    for _, row in df_turnering.iterrows():
        ar = str(row['Turn_År'])
        db["tournaments"][ar] = {
            "year": safe_int(row['Turn_År']),
            "host": str(row['Värdland']),
            "winner": str(row['Mästare']),
            "matches": [] 
        }

    # 1.5 Bygg uppslagverk för Förbundskaptener
    coaches_lookup = {}
    for _, row in df_nationer.iterrows():
        year = str(row['Turn_ÅR'])
        nation = str(row['Nation'])
        coach = str(row['Förbundskapten'])
        coaches_lookup[f"{year}_{nation}"] = coach

    # 2. Bygg Matcher
    for _, row in df_matcher.iterrows():
        match_id = str(row['Match_ID'])
        home_team = str(row['Hemmalag'])
        away_team = str(row['Bortalag'])
        
        # --- ADMIN VALIDERING: MATCHER ---
        if row['Matchdatum'] == "":
            db["admin_warnings"].append(f"Kritisk: Match {match_id} ({home_team} - {away_team}) saknar giltigt datum.")
        if row['Fas'] == "":
            db["admin_warnings"].append(f"Varning: Match {match_id} saknar turneringsfas (t.ex. Final, Gruppspel).")
        if safe_int(row['HM']) is None or safe_int(row['BM']) is None:
            db["admin_warnings"].append(f"Allvarlig: Match {match_id} ({home_team} - {away_team}) saknar slutresultat.")
        
        datum_str = str(row['Matchdatum'])[:10] 
        ar = datum_str[:4] if len(datum_str) >= 4 else "Okänt"
        
        # Varna om året inte finns i Turneringsfliken
        if ar not in db["tournaments"] and ar != "Okän":
            db["admin_warnings"].append(f"System: Match {match_id} spelas {ar}, men året finns inte inlagt i 'Turnering'-fliken.")
        
        if ar in db["tournaments"]:
            db["tournaments"][ar]["matches"].append(match_id)

        db["matches"][match_id] = {
            "id": match_id,
            "date": datum_str,
            "city": row['Ort'],
            "arena": row['Arena'],
            "phase": row['Fas'],
            "attendance": safe_int(row['Publik']),
            "referee": str(row.get('Domare', '')),
            "referee_country": str(row.get('Domarland', '')),
            "home_team": home_team,
            "away_team": away_team,
            "coaches": {
                "home": coaches_lookup.get(f"{ar}_{home_team}", "Okänd"),
                "away": coaches_lookup.get(f"{ar}_{away_team}", "Okänd")
            },
            "score": {
                "home_total": safe_int(row['HM']),
                "away_total": safe_int(row['BM']),
                "home_ht": safe_int(row['HM1']),
                "away_ht": safe_int(row['BM1']),
                "home_et": safe_int(row['HFM']),
                "away_et": safe_int(row['BFM']),
                "home_pen": safe_int(row.get('HSM')),
                "away_pen": safe_int(row.get('BSM'))
            },
            "events": {"goals": [], "cards": [], "lineups": {"home": [], "away": []}}
        }

    # 3. Mappa Mål till Matcher
    for _, row in df_mal.iterrows():
        match_id = str(row['Match_ID'])
        
        # --- ADMIN VALIDERING: MÅL ---
        if match_id not in db["matches"]:
            db["admin_warnings"].append(f"Datafel: Mål registrerat för Match_ID {match_id}, men matchen finns inte i Match-fliken.")
            continue
            
        if row['Minut'] == "":
            db["admin_warnings"].append(f"Varning: Målskytt {row['Målskytt']} i match {match_id} saknar matchminut.")

        db["matches"][match_id]["events"]["goals"].append({
            "player": str(row['Målskytt']),
            "team": str(row['Land']),
            "minute": str(row['Minut']),
            "type": str(row['Innebörd']) 
        })

    # 4. Mappa Spelare (Laguppställningar) till Matcher
    for _, row in df_spelare.iterrows():
        match_id = str(row['Match_ID'])
        
        # --- ADMIN VALIDERING: SPELARE ---
        if safe_int(row['Tröjnr']) is None:
            db["admin_warnings"].append(f"Datafel: Spelare {row['Namn']} i match {match_id} saknar tröjnummer.")
            
        if match_id in db["matches"]:
            hb = str(row['HB']).upper()
            team_key = "home" if hb == "H" else "away"
            
            db["matches"][match_id]["events"]["lineups"][team_key].append({
                "shirt_nr": safe_int(row['Tröjnr']),
                "name": str(row['Namn']),
                "position": str(row['Position']),
                "status": str(row['Händelse']), 
                "minute": str(row['Minut'])
            })

    # 5. Mappa Utvisningar till Matcher
    for _, row in df_utvisningar.iterrows():
        match_id = str(row['Match_ID'])
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["cards"].append({
                "player": str(row['Namn']),
                "minute": str(row['Minut']),
                "type": "Red"
            })

    # Spara filen
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
        
    print(f"✅ JSON-databas framgångsrikt byggd och sparad: {JSON_FILE}")
    print(f"Antal turneringar laddade: {len(db['tournaments'])}")
    print(f"Antal matcher laddade: {len(db['matches'])}")
    print(f"⚠️ Hittade {len(db['admin_warnings'])} admin-varningar. Dessa kan granskas i Dashboarden.")

# =========================================================
# KÖR SKRIPTET
# =========================================================
if __name__ == "__main__":
    build_database()