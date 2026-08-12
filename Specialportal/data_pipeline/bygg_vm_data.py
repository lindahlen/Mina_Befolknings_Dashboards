import os
import sys
import pandas as pd
import numpy as np
import json
import re
import unicodedata

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
        df_namn = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Namn'))
        df_trupper = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Trupper'))
        
        # Nya flikar för Domare och Förbundskaptener
        try:
            df_domare = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Domare'))
        except Exception:
            df_domare = pd.DataFrame()
            
        try:
            df_coaches = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Förbundskaptener'))
        except Exception:
            df_coaches = pd.DataFrame()
        
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
        "matches": {},
        "team_mappings": {},  
        "players": {},
        "placements": {},
        "staff": { "referees": {}, "coaches": {} } # NYTT: Åldersdata för personal
    }

    missing_players_dict = {}
    def add_missing(name, reason, extra_info=""):
        if name not in missing_players_dict:
            missing_players_dict[name] = {"Namn": name, "Källa": set(), "Info": set()}
        missing_players_dict[name]["Källa"].add(reason)
        if extra_info:
            missing_players_dict[name]["Info"].add(extra_info)

    # -- 3A. FÖRBERED UPPSLAGSVERK OCH MAPPNING --
    try:
        df_landerna = clean_dataframe(pd.read_excel(EXCEL_FILE, sheet_name='Länderna'))
        for _, row in df_landerna.iterrows():
            land = str(row.get('Land', '')).strip()
            landsnamn = str(row.get('Landsnamn', '')).strip()
            if land and landsnamn and land != landsnamn:
                db["team_mappings"][land] = landsnamn
    except Exception:
        print("Observera: Fliken 'Länderna' saknades. Ingen nationsmappning genomförs.")

    def get_mapped(team_name):
        return db["team_mappings"].get(team_name, team_name)

    valid_names = set(df_namn['Namn'].astype(str).str.strip())
    valid_names.discard("")
    valid_names.discard("None")

    # Kolla efter snarlika namn i 'Namn'-fliken
    normalized_names = {}
    for name in valid_names:
        norm = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
        norm = re.sub(r'[^a-zA-Z]', '', norm).lower()
        if norm not in normalized_names:
            normalized_names[norm] = []
        normalized_names[norm].append(name)
        
    for norm, originals in normalized_names.items():
        if len(originals) > 1:
            db["admin_warnings"].append(f"Snarlika namn (Dublettrisk): {', '.join(originals)} är väldigt lika i 'Namn'-fliken.")

    # -- Hämta åldersdata för Domare och Förbundskaptener --
    if not df_domare.empty:
        for _, row in df_domare.iterrows():
            namn = str(row.get('Domare', '')).strip()
            if not namn: continue
            fodd_val = row.get('Födelsedatum', row.get('Födelseår', ''))
            fodd_str = ""
            if pd.notnull(fodd_val) and str(fodd_val) != "" and str(fodd_val) != "None":
                if hasattr(fodd_val, 'strftime'): fodd_str = fodd_val.strftime('%Y-%m-%d')
                else: fodd_str = str(fodd_val).strip().replace(" 00:00:00", "")
            if fodd_str:
                db["staff"]["referees"][namn] = {"birth_date": fodd_str}

    if not df_coaches.empty:
        for _, row in df_coaches.iterrows():
            namn = str(row.get('FK_Namn', '')).strip()
            if not namn: continue
            fodd_val = row.get('Födelsedatum', row.get('Födelseår', ''))
            fodd_str = ""
            if pd.notnull(fodd_val) and str(fodd_val) != "" and str(fodd_val) != "None":
                if hasattr(fodd_val, 'strftime'): fodd_str = fodd_val.strftime('%Y-%m-%d')
                else: fodd_str = str(fodd_val).strip().replace(" 00:00:00", "")
            if fodd_str:
                db["staff"]["coaches"][namn] = {"birth_date": fodd_str}

    # Extrahera födelsedatum
    player_birth_info = {}
    for _, row in df_namn.iterrows():
        namn = str(row.get('Namn', '')).strip()
        fodd_val = row.get('Född', row.get('Födelsedatum', ''))
        
        fodd_str = ""
        if pd.notnull(fodd_val) and str(fodd_val) != "" and str(fodd_val) != "None":
            if hasattr(fodd_val, 'strftime'): fodd_str = fodd_val.strftime('%Y-%m-%d')
            else: fodd_str = str(fodd_val).strip().replace(" 00:00:00", "")
                
        if namn and fodd_str:
            player_birth_info[namn] = fodd_str

    # Extrahera trupper
    trupper_lookup = {}
    player_squad_info = {}
    for _, row in df_trupper.iterrows():
        t_year = str(row.get('Turn_År', '')).strip()
        t_land = str(row.get('Land', '')).strip()
        t_namn = str(row.get('Namn', row.get('efternamn', ''))).strip()
        t_anm = str(row.get('Anm', '')).lower()
        
        if t_year and t_land and t_namn:
            key = f"{t_year}_{t_land}"
            if key not in trupper_lookup: trupper_lookup[key] = set()
            trupper_lookup[key].add(t_namn)
            if t_namn not in player_squad_info:
                player_squad_info[t_namn] = {"years": set(), "nations": set(), "is_gk": False}
            player_squad_info[t_namn]["years"].add(t_year)
            player_squad_info[t_namn]["nations"].add(get_mapped(t_land))
            if 'mv' in t_anm: player_squad_info[t_namn]["is_gk"] = True

    for p_name, s_info in player_squad_info.items():
        if p_name not in valid_names: 
            nat_str = ", ".join(s_info["nations"])
            yr_str = ", ".join(sorted(list(s_info["years"])))
            db["admin_warnings"].append(f"Saknas i 'Namn': Nya trupp-spelaren '{p_name}' ({nat_str}, {yr_str})")
            add_missing(p_name, "Trupper", f"{nat_str} ({yr_str})")
            continue
            
        # Kolla tidsgap för samma namn
        years_ints = sorted([safe_int(y) for y in s_info["years"] if safe_int(y) is not None])
        if len(years_ints) >= 2:
            total_gap = years_ints[-1] - years_ints[0]
            if total_gap > 16:  
                max_consecutive_gap = 0
                for i in range(1, len(years_ints)):
                    diff = years_ints[i] - years_ints[i-1]
                    if years_ints[i-1] == 1938 and years_ints[i] == 1950:
                        diff = 4
                    if diff > max_consecutive_gap:
                        max_consecutive_gap = diff
                        
                if total_gap <= 20 and max_consecutive_gap <= 4:
                    pass 
                else:
                    db["admin_warnings"].append(f"Tidsgap-varning: Namnet '{p_name}' sträcker sig över {total_gap} år (från {years_ints[0]} till {years_ints[-1]}). Kontrollera om det är två olika personer.")

        fodd = player_birth_info.get(p_name, "")
        db["players"][p_name] = {
            "name": p_name,
            "nations": sorted(list(s_info["nations"])),
            "tournaments": [], 
            "squad_tournaments": sorted(list(s_info["years"])),
            "is_gk": s_info["is_gk"],
            "birth_date": fodd,
            "birth_year": fodd[:4] if fodd else "",
            "matches_played": 0,
            "minutes_played": 0,
            "goals": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "match_list": [],
            "admin_issues": []  # NY: Här sparar vi allt städ-jobb!
        }

    # Hämta in placeringar och tränare
    coaches_lookup = {}
    for _, row in df_nationer.iterrows():
        # Tar bort .0 ifall Excel tolkar året som en decimal
        year = str(row['Turn_ÅR']).replace('.0', '').strip()
        nation = str(row['Nation']).strip()
        placering = str(row.get('Placering', '')).strip()
        
        # 1. BEFINTLIGT: Spara huvudtränaren
        coaches_lookup[f"{year}_{nation}"] = str(row.get('Förbundskapten', '')).strip()
        
        # 2. NYTT: Kolla efter ersättare och spara på match-nivå
        sub_ids = row.get('Ersättare_Match_ID')
        sub_name = row.get('Ersättare_Namn')
        
        if pd.notna(sub_ids) and pd.notna(sub_name) and str(sub_ids).strip() != '':
            # Dela upp vid kommatecken ifall tränaren ersatte i flera matcher
            exception_matches = [m.strip() for m in str(sub_ids).split(',')]
            for m_id in exception_matches:
                # Sparar ersättaren med en unik nyckel: "ÅR_NATION_MATCHID"
                coaches_lookup[f"{year}_{nation}_{m_id}"] = str(sub_name).strip()
                print(f"SKVALLER: Registrerade {sub_name} som ersättare för {nation} ({year}), match {m_id}.")

        # 3. BEFINTLIGT: Din placerings-logik är intakt
        if year and nation and placering and placering != "None" and placering != "nan":
            mapped_nation = get_mapped(nation)
            if mapped_nation not in db["placements"]:
                db["placements"][mapped_nation] = {}
            db["placements"][mapped_nation][year] = placering

    avancerade_lookup = {}
    for _, row in df_avancerade.iterrows():
        kod = safe_int(row['Avancerade_Kod'])
        if kod is not None:
            avancerade_lookup[kod] = str(row['Innebörd'])

    # -- 3B. BYGG TURNERINGAR OCH MATCHER --
    for _, row in df_turnering.iterrows():
        ar = str(row['Turn_År'])
        current_year = safe_int(row['Turn_År'])
        
        # 1. Hämta bästa spelare först, så vi kan använda namnet för att söka
        best_player_name = str(row.get('Bästa_Spelare')).strip() if pd.notna(row.get('Bästa_Spelare')) else ""
        best_player_country = ""
        
        # 2. Om det finns ett namn, leta upp spelarens land i trupp-fliken
        if best_player_name and best_player_name.lower() not in ['nan', 'none']:
            match_trupp = df_trupper[
                (df_trupper['Turn_År'] == row['Turn_År']) & 
                (df_trupper['Namn'] == best_player_name)
            ]
            if not match_trupp.empty:
                best_player_country = str(match_trupp.iloc[0]['Land']).strip()
        # =================================================================
        # NYTT: BERÄKNA GENOMSNITTSÅLDER (ALLA SPELARE VS STARTELVAN)
        # =================================================================
        # Listor för att samla in åldern i totalt antal dagar för denna turnering
        all_players_days = []
        starting_players_days = []
        
        # Ordböcker för att kunna bryta ner per lag (Land) i den aktuella turneringen
        team_all_days = {}      # Ex: {"Brasilien": [10200, 9800, ...]}
        team_start_days = {}
        
        # 1. Hämta alla match-IDn som tillhör detta turneringsår från df_matcher
        # Vi tittar på 'Matchdatum' och plockar ut året för att matcha med turneringen
        df_matcher['Temp_År'] = pd.to_datetime(df_matcher['Matchdatum'], errors='coerce').dt.year
        df_matches_this_year = df_matcher[df_matcher['Temp_År'] == current_year]
        match_ids_this_year = df_matches_this_year['Match_ID'].unique()         
        
        # 2. Gå igenom alla matchdeltaganden för dessa matcher i df_spelare
        df_players_this_year = df_spelare[df_spelare['Match_ID'].isin(match_ids_this_year)]
        
        for _, p_row in df_players_this_year.iterrows():
            m_id = p_row['Match_ID']
            player_name = str(p_row['Namn']).strip()
            player_team = str(p_row['Land']).strip()
            position = safe_int(p_row['Position']) # Antar att safe_int finns i din kod
            
            # Hämta matchdatumet från df_matcher för denna specifika match
            match_info = df_matches_this_year[df_matches_this_year['Match_ID'] == m_id]
            if match_info.empty or pd.isna(match_info.iloc[0]['Matchdatum']):
                continue
            
            # Gör om matchdatum till ett datetime-objekt (Justera formatet '%Y-%m-%d' om det behövs)
            try:
                m_date = pd.to_datetime(match_info.iloc[0]['Matchdatum'])
            except:
                continue
                
            # Hämta information från df_namn för denna spelare
            p_info = df_namn[df_namn['Namn'] == player_name]
            
            if p_info.empty:
                felet = f"Hittades inte i fliken Namn"
                print(f"SKVALLER: {felet} - '{player_name}' (Lag: {player_team}, År: {current_year}).")
                
                # Spara ner i vår admin-lista!
                if "admin_issues" not in db:
                    db["admin_issues"] = []
                db["admin_issues"].append({
                    "year": current_year,
                    "team": player_team,
                    "player": player_name,
                    "issue": felet
                })
                continue
                
            # Plocka ut värdena
            b_date_val = p_info.iloc[0].get('Födelsedatum')
            b_year_val = p_info.iloc[0].get('Födelseår')
            b_date = pd.NaT
            
            # FÖRSÖK 1: Riktigt födelsedatum
            if pd.notna(b_date_val) and str(b_date_val).strip() != '':
                try:
                    b_date = pd.to_datetime(b_date_val)
                except Exception as e:
                    pass # Vi struntar i felmeddelandet här och går direkt på Försök 2
            
            # FÖRSÖK 2: Schablondatum från Födelseår (om Försök 1 misslyckades)
            if pd.isna(b_date) and pd.notna(b_year_val) and str(b_year_val).strip() != '':
                try:
                    # Rensar året (ifall Excel skickat med decimaler typ "1895.0")
                    clean_year = int(float(str(b_year_val).strip()))
                    # Skapar schablondatum: 1 juli
                    b_date = pd.to_datetime(f"{clean_year}-07-01")
                except Exception as e:
                    felet = f"Kunde inte skapa schablondatum från Födelseår '{b_year_val}'"
                    print(f"SKVALLER: {felet} - '{player_name}'.")
                    if "admin_issues" not in db:
                        db["admin_issues"] = []
                    db["admin_issues"].append({
                        "year": current_year,
                        "team": player_team,
                        "player": player_name,
                        "issue": felet
                    })
            
            # Om vi fortfarande inte har ett datum
            if pd.isna(b_date):
                felet = "Saknar både giltigt Födelsedatum och Födelseår"
                print(f"SKVALLER: {felet} - '{player_name}' (Lag: {player_team}).")
                if "admin_issues" not in db:
                    db["admin_issues"] = []
                db["admin_issues"].append({
                    "year": current_year,
                    "team": player_team,
                    "player": player_name,
                    "issue": felet
                })
                continue
            
            # Räkna ut exakt ålder i antal dagar på matchdagen
            age_in_days = (m_date - b_date).days
            if age_in_days <= 0:
                felet = f"Negativ eller noll ålder (Match: {m_date.date()}, Född: {b_date.date()})"
                print(f"SKVALLER: {felet} - '{player_name}'.")
                if "admin_issues" not in db:
                    db["admin_issues"] = []
                db["admin_issues"].append({
                    "year": current_year,
                    "team": player_team,
                    "player": player_name,
                    "issue": felet
                })
                continue
                
            # Initiera listor för laget om de inte redan finns
            if player_team not in team_all_days:
                team_all_days[player_team] = []
            if player_team not in team_start_days:
                team_start_days[player_team] = []
                
            # Sortera in i "Alla som spelat"
            all_players_days.append(age_in_days)
            team_all_days[player_team].append(age_in_days)
            
            # Sortera in i "Startelvan" (Position 1 till och med 11)
            if 1 <= position <= 11:
                starting_players_days.append(age_in_days)
                team_start_days[player_team].append(age_in_days)
                
        # 3. Räkna ut genomsnitten för hela turneringen (totalt)
        avg_all_tournament = sum(all_players_days) / len(all_players_days) if all_players_days else 0
        avg_start_tournament = sum(starting_players_days) / len(starting_players_days) if starting_players_days else 0
        
        # 4. Räkna ut genomsnitten per lag för denna turnering
        teams_age_stats = {}
        # Vi samlar alla unika lag som spelade detta år
        all_teams_this_year = set(list(team_all_days.keys()) + list(team_start_days.keys()))
        
        for team in all_teams_this_year:
            t_all = team_all_days.get(team, [])
            t_start = team_start_days.get(team, [])
            
            teams_age_stats[team] = {
                "avg_all_days": sum(t_all) / len(t_all) if t_all else 0,
                "avg_start_days": sum(t_start) / len(t_start) if t_start else 0
            }
        # 3. Bygg turneringsobjektet (nu med best_player_country tillagd)
        db["tournaments"][ar] = {
            "year": current_year,
            "host": str(row['Värdland']),
            "winner": str(row['Mästare']),
            "number_win": str(row['Titel_NR']),
            "best_player": best_player_name,  # Använder variabeln från steg 1
            "best_player_country": best_player_country,  # Den nya nationen vi hittade i steg 2
            "opening_match": str(row.get('Premiärmatch')).strip() if pd.notna(row.get('Premiärmatch')) else "",
            "comment": str(row.get('Kommentar')).strip() if pd.notna(row.get('Kommentar')) else "",
            # NYTT: Lägg till åldersstatistiken i turneringsobjektet!
            "age_stats": {
                "total_avg_all_days": avg_all_tournament,
                "total_avg_start_days": avg_start_tournament,
                "teams": teams_age_stats  # Innehåller lagvis uppdelning för detta år
            },

            "matches": [],
            "stats": {} 
        }

    for _, row in df_matcher.iterrows():
        match_id = str(row['Match_ID'])
        raw_time = str(row.get('Klockslag', ''))
        safe_time = raw_time.strip() if raw_time not in ['nan', 'NaT', 'None', ''] else ""
        home_team = str(row['Hemmalag'])
        away_team = str(row['Bortalag'])
        
        if row['Matchdatum'] == "":
            db["admin_warnings"].append(f"Kritisk: Match {match_id} ({home_team} - {away_team}) saknar datum.")
        
        datum_str = str(row['Matchdatum'])[:10] 
        ar = datum_str[:4] if len(datum_str) >= 4 else "Okänt"
        
        if ar in db["tournaments"]:
            db["tournaments"][ar]["matches"].append(match_id)

        adv_code = safe_int(row.get('Avancerade'))
        adv_text = avancerade_lookup.get(adv_code, "Okänd kod") if adv_code else "Ej angivet"
        
        advancing_team = None
        if adv_code in [1, 5, 13, 15]: advancing_team = home_team
        elif adv_code in [2, 4, 6, 16]: advancing_team = away_team
            
        is_group_stage = adv_code in [9, 10, 11, 12, 14]
        points_for_win = 3 if adv_code == 10 else (2 if is_group_stage else None)

        hm1, hm2 = safe_int(row.get('HM1')), safe_int(row.get('HM2'))
        bm1, bm2 = safe_int(row.get('BM1')), safe_int(row.get('BM2'))
        hfm, bfm = safe_int(row.get('HFM')), safe_int(row.get('BFM'))
        hm, bm = safe_int(row.get('HM')), safe_int(row.get('BM'))

        home_ft = hm1 + hm2 if (hm1 is not None and hm2 is not None) else (hm - hfm if (hm is not None and hfm is not None) else None)
        away_ft = bm1 + bm2 if (bm1 is not None and bm2 is not None) else (bm - bfm if (bm is not None and bfm is not None) else None)

        db["matches"][match_id] = {
            "id": match_id,
            "date": datum_str,
            "city": row['Ort'],
            "arena": row['Arena'],
            "phase": row['Fas'],
            "attendance": safe_int(row['Publik']),
            "referee": str(row.get('Domare', '')),
            "referee_country": str(row.get('Domarland', '')),
            "time": safe_time,
            "home_team": home_team,
            "away_team": away_team,
            "coaches": {
                "home": coaches_lookup.get(f"{ar}_{home_team}_{m_id}", coaches_lookup.get(f"{ar}_{home_team}", "Okänd")),
                "away": coaches_lookup.get(f"{ar}_{away_team}_{m_id}", coaches_lookup.get(f"{ar}_{away_team}", "Okänd"))
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
                "home_total": hm,
                "away_total": bm,
                "home_ht": hm1,
                "away_ht": bm1,
                "home_ft": home_ft,  
                "away_ft": away_ft,
                "home_et": hfm,      
                "away_et": bfm,  
                "home_pen": safe_int(row.get('HSM')),
                "away_pen": safe_int(row.get('BSM'))
            },
            "events": {"goals": [], "cards": [], "lineups": {"home": [], "away": []}, "penalties": []}
        }

    # -- 3C. HÄNDELSER OCH ADMIN-KONTROLLER --
    for _, row in df_mal.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Målskytt']).strip()
        if name and name.lower() not in ["självmål", "okänd"] and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Målskytt '{name}' (Match {match_id})")
            add_missing(name, "Målskytt", f"Match {match_id}")
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["goals"].append({
                "player": name, "team": str(row['Land']), "minute": str(row['Minut']),
                "type": str(row['Innebörd']), "note": str(row.get('Not', ''))
            })

    for _, row in df_utvisningar.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Namn']).strip()
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Utvisad spelare '{name}' (Match {match_id})")
            add_missing(name, "Utvisning", f"Match {match_id}")
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["cards"].append({"player": name, "minute": str(row['Minut']), "type": "Red"})
            
    for _, row in df_straffar.iterrows():
        match_id = str(row['Match_ID'])
        name = str(row['Namn']).strip()
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Straffskytt '{name}' (Match {match_id})")
            add_missing(name, "Straffskytt", f"Match {match_id}")
        if match_id in db["matches"]:
            db["matches"][match_id]["events"]["penalties"].append({
                "penalty_nr": safe_int(row['Straff_NR']), "player": name, "team": str(row['Land']),
                "outcome": str(row['Innebörd_straff']), "note": str(row['Notering'])
            })

    # -- 3E. SMART BYTES-MATEMATIK & LAGUPPSTÄLLNINGAR --
    missing_squad_warned = set()
    temp_lineups = {}
    
    for _, row in df_spelare.iterrows():
        m_id = str(row['Match_ID'])
        if m_id not in db["matches"]: continue
        
        if m_id not in temp_lineups:
            temp_lineups[m_id] = {"home": [], "away": []}
            
        hb = str(row['HB']).strip().upper()
        t_key = "home" if hb == "1" or hb.startswith("H") else "away"
        
        name = str(row['Namn']).strip()
        shirt = str(row.get('Tröjnr', ''))
        played_mins = safe_int(row['Minut']) 
        byte_str = str(row.get('Byte', '')).lower()
        
        if name and name not in valid_names:
            db["admin_warnings"].append(f"Saknas i 'Namn': Laguppst. '{name}' (Match {m_id})")
            add_missing(name, "Laguppställning", f"Match {m_id}")
            
        actual_team = db["matches"][m_id]["home_team"] if t_key == "home" else db["matches"][m_id]["away_team"]
        year = db["matches"][m_id]["date"][:4]
        
        t_key_squad = f"{year}_{actual_team}"
        if t_key_squad in trupper_lookup:
            if name not in trupper_lookup[t_key_squad]:
                db["admin_warnings"].append(f"Saknas i 'Trupper': Tröjnr {shirt} - {name} ({actual_team} {year}, Match {m_id})")
        else:
            if t_key_squad not in missing_squad_warned:
                db["admin_warnings"].append(f"Allvarlig: Har inga spelare registrerade för {actual_team} {year} i fliken 'Trupper'.")
                missing_squad_warned.add(t_key_squad)

        temp_lineups[m_id][t_key].append({
            "shirt_nr": safe_int(shirt),
            "name": name,
            "position": str(row.get('Position', '')),
            "status": str(row.get('Händelse', '')),
            "captain": str(row.get('Kapten', '')),
            "card": str(row.get('Händelse', '')),
            "played_mins": played_mins,
            "is_in": 'in' in byte_str,
            "is_out": 'ut' in byte_str
        })
        
    for m_id, teams in temp_lineups.items():
        red_cards = {}
        for rc in db["matches"][m_id]["events"]["cards"]:
            if rc["type"] == "Red": red_cards[rc["player"].strip()] = safe_int(rc["minute"])
            
        match_goals = {}
        for g in db["matches"][m_id]["events"]["goals"]:
            p_name = g["player"].strip()
            if p_name and p_name.lower() != "självmål":
                match_goals[p_name] = match_goals.get(p_name, 0) + 1
                
        for t_key, players in teams.items():
            max_mins = max([p["played_mins"] for p in players if p["played_mins"] is not None] + [90])
            for p in players:
                p["sub_in_min"] = None; p["sub_out_min"] = None
                pm = p["played_mins"]
                if pm is None: continue 
                rc_min = red_cards.get(p["name"].strip())
                if not p["is_in"]: 
                    if p["is_out"]: p["sub_out_min"] = pm
                else: 
                    if rc_min: p["sub_in_min"] = rc_min - pm
                    elif not p["is_out"]: p["sub_in_min"] = max_mins - pm
                        
            in_uts = [p for p in players if p["is_in"] and p["is_out"] and p["played_mins"] is not None]
            if in_uts:
                known_out = [p["sub_out_min"] for p in players if not p["is_in"] and p["sub_out_min"]]
                known_in = [p["sub_in_min"] for p in players if p["is_in"] and not p["is_out"] and p["sub_in_min"]]
                for p in in_uts:
                    pm = p["played_mins"]
                    matched = False
                    for ot in known_out:
                        for it in known_in:
                            if abs((ot + pm) - it) <= 1: 
                                p["sub_in_min"] = ot; p["sub_out_min"] = it; matched = True
                                break
                        if matched: break
                    if not matched:
                        unmatched = [ot for ot in known_out if not any(abs(ot - kit) <= 2 for kit in known_in)]
                        if unmatched: p["sub_in_min"] = unmatched[0]; p["sub_out_min"] = unmatched[0] + pm
                            
            for p in players:
                sub_parts = []
                if p["is_in"] and p["sub_in_min"] is not None: sub_parts.append(f"in {p['sub_in_min']}'")
                if p["is_out"] and p["sub_out_min"] is not None: sub_parts.append(f"ut {p['sub_out_min']}'")
                if not sub_parts:
                    if p["is_in"] and p["is_out"]: sub_parts = ["in", "ut"]
                    elif p["is_in"]: sub_parts = ["in"]
                    elif p["is_out"]: sub_parts = ["ut"]
                
                p_name_clean = p["name"].strip()
                db["matches"][m_id]["events"]["lineups"][t_key].append({
                    "shirt_nr": p["shirt_nr"],
                    "name": p_name_clean,
                    "position": p["position"],
                    "status": p["status"],
                    "sub": ", ".join(sub_parts), 
                    "captain": p["captain"],
                    "card": p["card"],
                    "red_card_minute": red_cards.get(p_name_clean),  
                    "goals": match_goals.get(p_name_clean, 0),       
                    "minute": p["played_mins"]
                })

    # -- 3F. AGGRERERA SPELARSTATISTIK --
    print("👤 Aggregerar detaljerad spelarstatistik...")
    for m_id, m in db["matches"].items():
        year = m["date"][:4]
        h_team = get_mapped(m["home_team"])
        a_team = get_mapped(m["away_team"])
        
        match_goals = {}
        for g in m["events"]["goals"]:
            p_name = g["player"].strip()
            if p_name and p_name.lower() != "självmål":
                match_goals[p_name] = match_goals.get(p_name, 0) + 1
                
        match_reds = set([c["player"].strip() for c in m["events"]["cards"] if c["type"] == "Red"])
        
        for t_key, t_name in [("home", h_team), ("away", a_team)]:
            for p in m["events"]["lineups"][t_key]:
                p_name = p["name"].strip()
                if not p_name: continue
                
                if p_name not in db["players"]:
                    fodd = player_birth_info.get(p_name, "")
                    db["players"][p_name] = {
                        "name": p_name,
                        "nations": [],
                        "tournaments": [],
                        "squad_tournaments": [],
                        "is_gk": player_squad_info.get(p_name, {}).get("is_gk", False),
                        "birth_date": fodd,
                        "birth_year": fodd[:4] if fodd else "",
                        "matches_played": 0,
                        "minutes_played": 0,
                        "goals": 0,
                        "yellow_cards": 0,
                        "red_cards": 0,
                        "match_list": [] 
                    }
                    
                p_obj = db["players"][p_name]
                
                if t_name not in p_obj["nations"]: p_obj["nations"].append(t_name)
                if year not in p_obj["squad_tournaments"]: p_obj["squad_tournaments"].append(year)
                
                mins = p["minute"]
                played = False
                if mins is not None: played = True
                elif "in" in str(p["sub"]).lower() or "start" in str(p["status"]).lower(): played = True
                    
                if played:
                    if year not in p_obj["tournaments"]: p_obj["tournaments"].append(year)
                    p_obj["matches_played"] += 1
                    if mins is not None: p_obj["minutes_played"] += safe_int(mins) or 0
                    p_obj["match_list"].append(m_id)
                    
                    if p_name in match_goals: p_obj["goals"] += match_goals[p_name]
                        
                    card_str = str(p.get("card", "")).lower()
                    if "v" in card_str and "utv" not in card_str: p_obj["yellow_cards"] += 1
                    if "utv" in card_str or p_name in match_reds: p_obj["red_cards"] += 1
                    if "v utv" in card_str: p_obj["yellow_cards"] += 1

    for p_obj in db["players"].values():
        p_obj["tournaments"].sort()
        p_obj["squad_tournaments"].sort()

    # -- 3G. AVANCERAD LOGISK KONTROLL --
    for m_id, m in db["matches"].items():
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
        if adv_team and actual_winner and adv_team != actual_winner:
            db["admin_warnings"].append(f"Logikfel: Match {m_id} slutade med seger för {actual_winner}, men Avancerade-koden säger att {adv_team} gick vidare/vann.")

    for t_year, t_data in db["tournaments"].items():
        t_matches = [db["matches"][m_id] for m_id in t_data["matches"]]
        t_matches.sort(key=lambda x: x["date"] if x["date"] else "9999-99-99")
        eliminated_teams = {} 
        knockout_advanced_teams = {} 
        for m in t_matches:
            home = m["home_team"]
            away = m["away_team"]
            is_bronze = m["advancement"]["is_bronze"]
            if home in eliminated_teams and not is_bronze: db["admin_warnings"].append(f"Logikfel (Slutspel): {home} spelar i match {m['id']} trots utslagning i match {eliminated_teams[home]}.")
            if away in eliminated_teams and not is_bronze: db["admin_warnings"].append(f"Logikfel (Slutspel): {away} spelar i match {m['id']} trots utslagning i match {eliminated_teams[away]}.")
            if home in knockout_advanced_teams: del knockout_advanced_teams[home]
            if away in knockout_advanced_teams: del knockout_advanced_teams[away]
            if not m["advancement"]["is_group_match"]:
                adv_team = m["advancement"]["advancing_team"]
                if adv_team:
                    loser = away if adv_team == home else home
                    eliminated_teams[loser] = m["id"]
                    if not m["advancement"]["is_final"] and not is_bronze:
                        knockout_advanced_teams[adv_team] = m["id"]
        for team, m_id in knockout_advanced_teams.items():
            db["admin_warnings"].append(f"Logikfel (Slutspel): {team} avancerade från match {m_id} men saknar efterföljande match år {t_year}.")

    # -- 3H. TURNERINGSSTATISTIK (ÖVERSIKT OCH REKORD) --
    print("📈 Aggregerar övergripande turneringsstatistik...")
    for year, t in db["tournaments"].items():
        t_goals, t_att, m_count = 0, 0, 0
        goals_h1, goals_h2, goals_et, goals_pen = 0, 0, 0, 0
        matches_et, matches_pen = 0, 0
        t_players = set()
        t_goalscorers = {}
        champion = t["winner"]
        champ_coach = ""
        champ_captain = ""
        
        for m_id in t["matches"]:
            m = db["matches"].get(m_id)
            if not m or m["score"]["home_total"] is None: continue
            
            m_count += 1
            t_goals += m["score"]["home_total"] + m["score"]["away_total"]
            if m["attendance"]: t_att += m["attendance"]
            
            s = m["score"]
            if s["home_ht"] is not None and s["away_ht"] is not None:
                goals_h1 += s["home_ht"] + s["away_ht"]
            if s["home_ft"] is not None and s["home_ht"] is not None:
                goals_h2 += (s["home_ft"] - s["home_ht"]) + (s["away_ft"] - s["away_ht"])
            if s["home_et"] is not None:
                goals_et += s["home_et"] + s["away_et"]
                matches_et += 1
            if s["home_pen"] is not None:
                goals_pen += s["home_pen"] + s["away_pen"]
                matches_pen += 1
                
            for g in m["events"]["goals"]:
                p_name = g["player"].strip()
                if p_name and p_name.lower() != "självmål":
                    t_goalscorers[p_name] = t_goalscorers.get(p_name, 0) + 1
                    
            for t_key in ["home", "away"]:
                for p in m["events"]["lineups"][t_key]:
                    if p["minute"] is not None or "in" in str(p["sub"]).lower() or "start" in str(p["status"]).lower():
                        t_players.add(p["name"].strip())
                        
            if m["advancement"]["is_final"] and champion and champion != "Okänd":
                if get_mapped(m["home_team"]) == get_mapped(champion) or m["home_team"] == champion:
                    champ_coach = m["coaches"]["home"]
                    for p in m["events"]["lineups"]["home"]:
                        if "c" in str(p["captain"]).lower(): champ_captain = p["name"]
                elif get_mapped(m["away_team"]) == get_mapped(champion) or m["away_team"] == champion:
                    champ_coach = m["coaches"]["away"]
                    for p in m["events"]["lineups"]["away"]:
                        if "c" in str(p["captain"]).lower(): champ_captain = p["name"]
                        
        debutants = 0
        for p_name in t_players:
            p_obj = db["players"].get(p_name)
            if p_obj and p_obj["tournaments"] and p_obj["tournaments"][0] == year:
                debutants += 1
                
        top_scorer_list = []
        if t_goalscorers:
            max_g = max(t_goalscorers.values())
            top_scorer_list = [{"name": p, "goals": g} for p, g in t_goalscorers.items() if g == max_g]
            
        t["stats"] = {
            "total_goals": t_goals,
            "total_attendance": t_att,
            "matches_played": m_count,
            "goals_h1": goals_h1,
            "goals_h2": goals_h2,
            "goals_et": goals_et,
            "goals_pen": goals_pen,
            "matches_et": matches_et,
            "matches_pen": matches_pen,
            "players_used": len(t_players),
            "debutants": debutants,
            "goalscorers": len(t_goalscorers),
            "top_scorers": top_scorer_list,
            "champion_coach": champ_coach,
            "champion_captain": champ_captain
        }

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
        
    print(f"✅ JSON-databas uppdaterad med Turneringsöversikt, Laguppställnings-mål & Placeringsmatris!")

    # -- 3I. EXPORTERA SAKNADE SPELARE TILL CSV --
    if missing_players_dict:
        export_list = []
        for name, data in missing_players_dict.items():
            export_list.append({
                "Namn": name,
                "Saknas i (Källa)": ", ".join(sorted(list(data["Källa"]))),
                "Extra info": ", ".join(sorted(list(data["Info"])))
            })
        df_missing = pd.DataFrame(export_list)
        missing_file = os.path.join(EXCEL_DIR, "Saknade_Spelare_Export.csv")
        df_missing.to_csv(missing_file, index=False, encoding='utf-8-sig', sep=';')
        print(f"⚠️ Hittade {len(export_list)} saknade spelare. Listan har sparats till: {missing_file}")

if __name__ == "__main__":
    build_database()