import os
import sys
import pandas as pd
import numpy as np
import json

# =========================================================
# 1. GENERELL SETUP & SÖKVÄGSHANTERING
# =========================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
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
    return df.replace({np.nan: None}).fillna("")

def safe_int(val):
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
        df_turnering = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Turnering'))
        df_matcher = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Matcher'))
        df_mal = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Mål'))
        df_spelare = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Spelare'))
        df_utvisningar = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Utvisningar'))
        df_nationer = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Nationer'))
        df_avancerade = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Avancerade'))
        df_straffar = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Straffläggning'))
        
        # NYA FLIKAR FÖR KONTROLL
        df_namn = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Namn'))
        df_trupper = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Trupper'))
        
        if list(df_matcher.columns).count('HSM') > 1:
            cols = list(df_matcher.columns)
            cols[cols.index('HSM', cols.index('HSM') + 1)] = 'BSM'
            df_matcher.columns = cols
            
    except Exception as e:
        print(f"❌ Fel vid inläsning av Excel: {e}")
        sys.exit(1)

    print("⚙️ Bygger hierarkisk JSON-struktur och granskar datan...")
    
    db = {
        "metadata": {"title": "Fotbolls-VM Historik 1930-", "last_updated": str(pd.Timestamp.now().date())},
        "admin_warnings": [],
        "tournaments": {}, 
        "matches": {}      
    }

    # -- 3A. FÖRBERED UPPSLAGSVERK OCH VALIDERINGS-LISTOR --
    
    # 1. Hämta alla unika och giltiga namn
    valid_names = set(df_namn['Namn'].astype(str).str.strip())
    valid_names.discard("")
    valid_names.discard("None")

    # 2. Hämta trupper
    trupper_lookup = {}
    for _, row in df_trupper.iterrows():
        t_year = str(row.get('Turn_År', '')).strip()
        t_land = str(row.get('Land', '')).strip()
        t_namn = str(row.get('Namn', row.get('efternamn', ''))).strip()
        
        if t_year and t_land and t_namn:
            key = f"{t_year}_{t_land}"
            if key not in trupper_lookup:
                trupper_lookup[key] = set()
            trupper_lookup[key].add(t_namn)

    coaches_lookup = {}
    for _, row in df_nationer.iterrows():
        year = str(row['Turn_ÅR'])
        nation = str(row['Nation'])
        coaches_lookup[f"{year}_{nation}"] = str(row['Förbundskapten'])

    avancerade_lookup = {}
    for _, row in df_avancerade.iterrows():
        kod = safe_int(row['Avancerade_Kod'])
        if kod is not None:
            avancerade_lookup[kod] = str(row['Innebörd'])

    # -- 3B. BYGG TURNERINGAR OCH MATCHER --
    for _, row in df_turnering.iterrows():
        ar = str(row['Turn_År'])
        db["tournaments"][ar] = {
            "year": safe_int(row['Turn_År']),
            "host": str(row['Värdland']),
            "winner": str(row['Mästare']),
            "matches": [],
            "stats": {"total_goals": 0, "total_attendance": 0, "matches_played": 0} 
        }

    for _, row in df_matcher.iterrows():
        match_id = str(row['Match_ID'])
        home_team = str(row['Hemmalag'])
        away_team = str(row['Bortalag'])
        
        if row['Matchdatum'] == "":
            db["admin_warnings"].append(f"Kritisk: Match {match_id} ({home_team} - {away_team}) saknar datum.")
        
        datum_str = str(row['Matchdatum'])[:10] 
        ar = datum_str[:4] if len(datum_str) >= 4 else "Okänt"
        
        if ar in db["tournaments"]:
            db["tournaments"][ar]["matches"].append(match_id)

        # Logik för avancemang
        adv_code = safe_int(row.get('Avancerade'))
        adv_text = avancerade_lookup.get(adv_code, "Okänd kod") if adv_code else "Ej angivet"
        
        advancing_team = None
        if adv_code in [1, 5, 13, 15]: advancing_team = home_team
        elif adv_code in [2, 4, 6, 16]: advancing_team = away_team
            
        is_group_stage = adv_code in [9, 10, 11, 12, 14]
        points_for_win = 3 if adv_code == 10 else (2 if is_group_stage else None)

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
            "advancement": {
                "code": adv_code,
                "text": adv_text,
                "advancing_team": advancing_team,
                "is_group_match": is_group_stage,
                "points_for_win": points_for_win,
                "is_final": adv_code in [5, 6],
                "is_bronze": adv_code in [15, 16]
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
            "events": {"goals": [], "cards": [], "lineups": {"home": [], "away": []}, "penalties": []}
        }

    # -- 3C. HÄNDELSER OCH ADMIN-KONTROLLER --
    
    # Mål
    for _, row in df_mal.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Målskytt']).strip()
        
        if name and name.lower() not in ["självmål", "okänd"] and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Målskytt '{name}' (Match {match_id})")

        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["goals"].append({
                "player": name,
                "team": str(row['Land']),
                "minute": str(row['Minut']),
                "type": str(row['Innebörd']),
                "note": str(row.get('Not', ''))
            })

    # Utvisningar
    for _, row in df_utvisningar.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Namn']).strip()
        
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Utvisad spelare '{name}' (Match {match_id})")
            
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["cards"].append({
                "player": name,
                "minute": str(row['Minut']),
                "type": "Red"
            })
            
    # Straffläggning
    for _, row in df_straffar.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Namn']).strip()
        
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Straffskytt '{name}' (Match {match_id})")
            
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["penalties"].append({
                "penalty_nr": safe_int(row['Straff_NR']),
                "player": name,
                "team": str(row['Land']),
                "outcome": str(row['Innebörd_straff']),
                "note": str(row['Notering'])
            })

    # Spelare (Laguppställningar) och Trupp-kontroll
    missing_squad_warned = set()
    for _, row in df_spelare.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Namn']).strip()
        shirt = str(row.get('Tröjnr', ''))
        hb = str(row['HB']).strip().upper()
        
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Laguppst. '{name}' (Match {match_id})")
            
        if match_id in db["matches"]:
            m = db["matches"][match_id]
            team_key = "home" if hb == "1" or hb.startswith("H") else "away"
            actual_team = m["home_team"] if team_key == "home" else m["away_team"]
            year = m["date"][:4]
            
            # Kolla mot Trupper
            t_key = f"{year}_{actual_team}"
            if t_key in trupper_lookup:
                if name not in trupper_lookup[t_key]:
                    db["admin_warnings"].append(f"Saknas i 'Trupper': Tröjnr {shirt} - {name} ({actual_team} {year}, Match {match_id})")
            else:
                if t_key not in missing_squad_warned:
                    db["admin_warnings"].append(f"Allvarlig: Har inga spelare registrerade för {actual_team} {year} i fliken 'Trupper'.")
                    missing_squad_warned.add(t_key)

            db["matches"][match_id]["events"]["lineups"][team_key].append({
                "shirt_nr": safe_int(shirt),
                "name": name,
                "position": str(row['Position']),
                "status": str(row['Händelse']),
                "sub": str(row.get('Byte', '')),
                "captain": str(row.get('Kapten', '')),
                "card": str(row.get('Händelse', '')),
                "minute": str(row['Minut'])
            })

    # -- 3D. AVANCERAD LOGISK KONTROLL (TIDSLINJE & RESULTAT) --
    for m_id, m in db["matches"].items():
        # Kontroll 1: Stämmer mål/straff-resultatet med koden för avancemang?
        ht_g = m["score"]["home_total"]
        at_g = m["score"]["away_total"]
        ht_p = m["score"]["home_pen"]
        at_p = m["score"]["away_pen"]
        
        actual_winner = None
        if ht_g is not None and at_g is not None:
            if ht_g > at_g: actual_winner = m["home_team"]
            elif at_g > ht_g: actual_winner = m["away_team"]
            elif ht_p is not None and at_p is not None:
                if ht_p > at_p: actual_winner = m["home_team"]
                elif at_p > ht_p: actual_winner = m["away_team"]
                
        adv_team = m["advancement"]["advancing_team"]
        
        # Om matchen inte är ett oavgjort gruppspel, men vi har fel avancemang
        if adv_team and actual_winner and adv_team != actual_winner:
            db["admin_warnings"].append(f"Logikfel: Match {m_id} slutade med seger för {actual_winner}, men Avancerade-koden säger att {adv_team} gick vidare/vann.")

    # Kontroll 2: Tidslinjen för utslagna lag
    for t_year, t_data in db["tournaments"].items():
        # Hämta årets matcher och sortera i datumordning
        t_matches = [db["matches"][m_id] for m_id in t_data["matches"]]
        t_matches.sort(key=lambda x: x["date"] if x["date"] else "9999-99-99")
        
        eliminated_teams = {} # Sparar vilket lag som åkte ut i vilken match
        knockout_advanced_teams = {} # Sparar lag som gick vidare i slutspelet
        
        for m in t_matches:
            home = m["home_team"]
            away = m["away_team"]
            is_bronze = m["advancement"]["is_bronze"]
            
            # Varnar om ett utslaget lag spelar en ny match (undantag Bronsmatch)
            if home in eliminated_teams and not is_bronze:
                db["admin_warnings"].append(f"Logikfel (Slutspel): {home} spelar i match {m['id']} trots att de blev utslagna redan i match {eliminated_teams[home]}.")
            if away in eliminated_teams and not is_bronze:
                db["admin_warnings"].append(f"Logikfel (Slutspel): {away} spelar i match {m['id']} trots att de blev utslagna redan i match {eliminated_teams[away]}.")
                
            # Bocka av lag som faktiskt spelar (så de inte varnas för att ha "försvunnit")
            if home in knockout_advanced_teams: del knockout_advanced_teams[home]
            if away in knockout_advanced_teams: del knockout_advanced_teams[away]
            
            # Registrera utslagning / avancemang för utslagsmatcher
            if not m["advancement"]["is_group_match"]:
                adv_team = m["advancement"]["advancing_team"]
                if adv_team:
                    loser = away if adv_team == home else home
                    eliminated_teams[loser] = m["id"]
                    
                    if not m["advancement"]["is_final"] and not is_bronze:
                        knockout_advanced_teams[adv_team] = m["id"]
                        
        # Om något lag ligger kvar i listan över avancerade, har de gått vidare men aldrig spelat nästa match
        for team, m_id in knockout_advanced_teams.items():
            db["admin_warnings"].append(f"Logikfel (Slutspel): {team} avancerade från match {m_id} men saknar efterföljande slutspelsmatch i turneringen {t_year}.")

    # Beräkna enkel turneringsstatistik innan vi sparar
    for year, t in db["tournaments"].items():
        t_goals, t_att, m_count = 0, 0, 0
        for m_id in t["matches"]:
            m = db["matches"].get(m_id)
            if m and m["score"]["home_total"] is not None:
                m_count += 1
                t_goals += m["score"]["home_total"] + m["score"]["away_total"]
                if m["attendance"] is not None:
                    t_att += m["attendance"]
        db["tournaments"][year]["stats"] = {"total_goals": t_goals, "total_attendance": t_att, "matches_played": m_count}

    # Spara filen
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
        
    print(f"✅ JSON-databas uppdaterad med omfattande Admin-validering!")
    print(f"⚠️  {len(db['admin_warnings'])} larm genererade. Öppna dashboarden (Fliken Admin) för att granska.")

if __name__ == "__main__":
    build_database()