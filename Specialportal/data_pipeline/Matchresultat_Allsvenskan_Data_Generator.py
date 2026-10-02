import os
import sys
import pandas as pd
import json
import re

# ==========================================
# DATA OCH KÄLLMATERIAL
# Författare till matchinformation och grunddata: Jimmy Lindahl
# ==========================================

# ==========================================
# 1. GENERELL SETUP OCH SÖKVÄGAR
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    main_folder = os.path.abspath(os.path.join(current_folder, '..'))
    excel_folder = os.path.join(main_folder, 'excel_filer')
except NameError:
    pass 

# ==========================================
# ⚙️ INSTÄLLNINGAR: ALLSVENSKA MÄSTARBÄLTET
# ==========================================
BELT_START_MATCH_ID = 2 

# Manuella ID:n för matcher som gör upp om vakanta titlar.
# Går före automatiken (som annars letar tidigaste datum + störst seger i Omg 1)
MANUAL_VACANT_MATCHES = {
    # '1933/34': 1204,
    # '1992': 5500
    1940/41: 2091
}

# ==========================================
# 2. DATAHANTERING OCH TEXTFIX
# ==========================================
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# def flip_name_format(name):
#     """
#     Vänder 'Efternamn, Förnamn' till 'Förnamn Efternamn'.
#     Ignorerar namn som redan saknar kommatecken.
#     """
#     if not isinstance(name, str):
#         return name
#     
#     if "," in name:
#         parts = name.split(",", 1) # Delar vid första kommatecknet
#         efternamn = parts[0].strip()
#         fornamn = parts[1].strip()
#         return f"{fornamn} {efternamn}"
#     
#     return str(name).strip()

# ==========================================
# 3. MERGE / KOPPLA SAMMAN DATA
# ==========================================

# Nu när BÅDA tabellerna har formatet "Förnamn Efternamn" kommer kopplingen fungera felfritt igen.
# Exempel på hur din merge kan se ut:
# df_matches = df_matches.merge(df_info, left_on='Målvakt', right_on='Namn', how='left')    

    # Här kan du i framtiden mappa ihop Allsvenska lag som bytt namn
team_name_mapping = {
    # "Gammalt Namn": "Nytt Namn"
}

def normalize_team(team_name):
    if not isinstance(team_name, str): return team_name
    team = str(team_name).strip()
    return team_name_mapping.get(team, team)

excel_file = os.path.join(excel_folder, "Allsvenskan_matcher_samlade.xlsx")

# ==========================================
# 4. INLÄSNING OCH TVÄTT AV FÖDELSEDATA
# ==========================================

# 1. Läs in båda flikarna i ett svep
excel_data = pd.read_excel(excel_file, sheet_name=['Målvakter', 'Domare'])

# 2. Bryt ut dem till två separata DataFrames
df_malvakter = excel_data['Målvakter']
df_domare = excel_data['Domare']

# 3. Tvätta namnen (Gyllene regel B2) i båda tabellerna direkt
# (Byt ut 'Namn' mot det faktiska kolumnnamnet i respektive flik)
#  df_malvakter['Namn'] = df_malvakter['Namn'].apply(flip_name_format)
#  df_domare['Namn'] = df_domare['Namn'].apply(flip_name_format)

# ---------------------------------------------------------
# 1. LÄS IN HUVUDDATABASEN (MATCHER)
# ---------------------------------------------------------
try:
    df = pd.read_excel(excel_file)
    print(f"Laddade {len(df)} rader från Allsvenskan_matcher_samlade.xlsx.")
    df['Säs'] = df['Säs'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    
    text_columns = ['Hemmalag', 'Bortalag', 'Arena', 'NOT', 'Domare', 'Domarort', 'Hemmamålvakt', 'Bortamålvakt', 'År', 'Omgång']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(fix_text)

    # 2. Vänd på namnen från "Efternamn, Förnamn" till "Förnamn Efternamn" (Sektion 2B)
    #  person_columns = ['Domare', 'Hemmamålvakt', 'Bortamålvakt', 'Målskytt', 'Namn']
    # for col in person_columns:
    #     if col in df.columns:
    #        df[col] = df[col].apply(flip_name_format)

    # --- NY KOD: APPLICERA ALIAS DIREKT PÅ RÅDATAN ---
    # Här lägger du in alla kända namnbyten. (Gammalt namn : Nytt namn)
    name_aliases = {
        "Ericsson, Ragnar": "Elderud, Ragnar",
        "Ragnar Ericsson": "Ragnar Elderud", # Bra att ha med båda formaten ifall filen varierar
        "Ericsson, Ragnar": "Elderud, Ragnar",
        "Svensson, Stefan": "Winqvist, Stefan",
        "Östling, Joakim": "Sars, Joakim",
        "Mnonyelu Dovin, Oliver": "Dovin, Oliver",
        "Nilsson, David": "Mitov Nilsson, David"
        # "Gammalt Namn": "Nytt Namn", 
    }
    
    # Byt ut namnen i alla berörda kolumner med Pandas inbyggda .replace()
    if 'Domare' in df.columns:
        df['Domare'] = df['Domare'].replace(name_aliases)
    if 'Hemmamålvakt' in df.columns:
        df['Hemmamålvakt'] = df['Hemmamålvakt'].replace(name_aliases)
    if 'Bortamålvakt' in df.columns:
        df['Bortamålvakt'] = df['Bortamålvakt'].replace(name_aliases)
    # -------------------------------------------------

# --- NY KOD: Flagga annullerade matcher (Soft Delete) ---
    # Om ordet "Annullerad" finns i NOT-kolumnen, sätts flaggan till True, annars False.
    if 'NOT' in df.columns:
        df['Annullerad'] = df['NOT'].astype(str).str.contains('Annullerad', case=False, na=False)
    else:
        df['Annullerad'] = False

except FileNotFoundError:
    print(f"KRITISKT FEL: Filen '{excel_file}' hittades inte.")
    sys.exit(1)

# Tvinga Datum-kolumnen till ren text (ÅÅÅÅ-MM-DD)
# LÄS IN MATCHDATUM OCH DÖP OM TILL 'Datum' (SÅ ATT JS HITTAR DET)
if 'Matchdatum' in df.columns:
    df['Datum'] = pd.to_datetime(df['Matchdatum'], errors='coerce').dt.strftime('%Y-%m-%d')
elif 'Datum' in df.columns:
    df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce').dt.strftime('%Y-%m-%d')
        
df = df.fillna("")


# ---------------------------------------------------------
# 2. FUNKTIONER FÖR ATT LÄSA IN TILLÄGGSFLIKAR (MODAL-DATA)
# ---------------------------------------------------------
def prepare_person_data(filepath, sheet_name):
    try:
        df_sheet = pd.read_excel(filepath, sheet_name=sheet_name)
    except Exception:
        print(f"INFO: Fliken '{sheet_name}' hittades inte i {filepath}, hoppar över.")
        return {}
    
    df_sheet = df_sheet.where(pd.notnull(df_sheet), None)
    person_dict = {}
    
    for _, row in df_sheet.iterrows():
        namn = fix_text(row.get('Namn', ''))
        if namn:
            fodd = row.get('Född')
            fodd_str = fodd.strftime('%Y-%m-%d') if pd.notnull(fodd) and hasattr(fodd, 'strftime') else (str(fodd).strip() if pd.notnull(fodd) else None)
            
            avliden = row.get('Avliden')
            avliden_str = avliden.strftime('%Y-%m-%d') if pd.notnull(avliden) and hasattr(avliden, 'strftime') else (str(avliden).strip() if pd.notnull(avliden) else None)
            
            fodelse_ar = row.get('År')
            fodelse_ar_str = str(int(float(fodelse_ar))) if pd.notnull(fodelse_ar) and str(fodelse_ar).replace('.0', '').isdigit() else None
            
            # --- NY KOD: Läs in eventuellt nytt namn ---
            nytt_namn = row.get('Nytt namn')
            nytt_namn_str = fix_text(nytt_namn) if pd.notnull(nytt_namn) and str(nytt_namn).strip() != "" else None
            
            person_dict[namn] = {
                "Född": fodd_str,
                "År": fodelse_ar_str,
                "Avliden": avliden_str,
                "NyttNamn": nytt_namn_str
            }
    return person_dict

def prepare_scorers(filepath):
    try:
        # Läs in båda flikarna
        df_sheet = pd.read_excel(filepath, sheet_name="Skyttekungar")
        # Pythons motsvarighet till ': Läs in Födelsedatum som ren text!
        df_namn = pd.read_excel(filepath, sheet_name="Malskyttenamn", dtype={'Födelsedatum': str})
    except Exception as e:
        print(f"INFO: Fliken 'Skyttekungar' eller 'Malskyttenamn' saknas. Fel: {e}")
        return {}

    # 1. Rensa rubriker
    df_sheet.columns = df_sheet.columns.str.strip()
    df_namn.columns = df_namn.columns.str.strip()

    # 2. Tvätta text på namn
    if 'Namn' in df_sheet.columns:
        df_sheet['Namn'] = df_sheet['Namn'].apply(fix_text)
    if 'Namn' in df_namn.columns:
        df_namn['Namn'] = df_namn['Namn'].apply(fix_text)

    # ==========================================
    # REGEL B2: Datatvätt vid källan (Dubbletthantering)
    # ==========================================
    alias_dict = {
        "Andersson, Sven 2": "Andersson, Sven"
    }
    
    if 'Namn' in df_sheet.columns:
        df_sheet['Namn'] = df_sheet['Namn'].replace(alias_dict)
    if 'Namn' in df_namn.columns:
        df_namn['Namn'] = df_namn['Namn'].replace(alias_dict)
    # ==========================================

    # --- DEN MAGISKA DATUMTVÄTTEN ---
    def tvatta_excel_datum(val):
        if pd.isnull(val): return ""
        if isinstance(val, str): return val.strip()[:10] # Hanterar 1800-talets text
        try: return val.strftime('%Y-%m-%d') # Hanterar 1900-talets dolda Excel-datum
        except: return str(val)[:10]

    if 'Födelsedatum' in df_namn.columns:
        df_namn['Födelsedatum_str'] = df_namn['Födelsedatum'].apply(tvatta_excel_datum)
    else:
        df_namn['Födelsedatum_str'] = ""
    # ---------------------------------

    # 4. Ta bort dubbletter inför sammanslagning
    df_namn_unique = df_namn.drop_duplicates(subset=['Namn'])

    # 5. Para ihop Skyttekungar med deras födelsedatum
    df_merged = df_sheet.merge(
        df_namn_unique[['Namn', 'Födelsedatum_str']], 
        on='Namn', 
        how='left'
    )
    
    # 6. Förbered dictionary
    df_merged = df_merged.where(pd.notnull(df_merged), None)
    scorers = {}
    
    for _, row in df_merged.iterrows():
        sasnr = row.get('Säsnr')
        if pd.isnull(sasnr) or str(sasnr).strip() == "":
            continue
            
        sas_key = str(int(float(sasnr))) # Gör om till ren siffra (ex "1")
        
        if sas_key not in scorers:
            scorers[sas_key] = [] 

        sas_text = str(row.get('Säsong', '')).strip()
        
        # --- NY LOGIK: Beräkna säsongens slutdatum ---
        if "/" in sas_text:
            # Ex: "1924/25" -> Slutår blir "1925"
            parts = sas_text.split("/")
            if len(parts) == 2 and len(parts[1]) == 2:
                century = parts[0][:2] # "19"
                end_year = century + parts[1]
                slutdatum = f"{end_year}-06-30" # Höst/Vår slutar i juni
            else:
                slutdatum = f"{sas_text[:4]}-06-30"
        else:
            # Ex: "1959" -> Vår/Höst slutar i november
            slutdatum = f"{sas_text[:4]}-11-30"
        # ---------------------------------------------
                        
        # Nu skickas äntligen 'Född' med till JavaScriptet!
        scorers[sas_key].append({
            "SäsongText": str(row.get('Säsong', '')).strip(),
            "Namn": fix_text(row.get('Namn')),
            "Klubb": fix_text(row.get('Klubb')),
            "Mål": row.get('Mål'),
            "Född": str(row.get('Födelsedatum_str', '')) # Perfekt text skickas ut!
        })
        
    return scorers

def calculate_master_belt(df):
    """
    Spårar det inofficiella mästarbältet i tre parallella regelverk.
    Hantera manuella ID:n, datum-filtrering och målskillnad för vakanser.
    """
    results = {}
    df_sorted = df.sort_values(['År', 'Matchdatum', 'Match_ID']).copy()

    def simulate(rule):
        current_champion = None
        belt_vacant = False
        defense_count = 0
        belt_history = []
        exile_years = 0
        last_season = None
        
        target_vacant_match_id = None

        for index, row in df_sorted.iterrows():
            match_id = row['Match_ID']
            sas = row['Säs']

            try:
                hm, bm = int(row['HM']), int(row['BM'])
            except ValueError:
                continue 

            # Startpunkten 1924
            if match_id == BELT_START_MATCH_ID:
                current_champion = row['Hemmalag'] if hm > bm else row['Bortalag']
                defense_count = 0 # LOGIK-FIX 1: Erövringsmatchen räknas inte som ett försvar
                last_season = sas
                belt_history.append({"Datum": str(row['Matchdatum'])[:10], "Omgång": row['Omgång'], "Resultat": f"{hm}-{bm}", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "Första Mästaren"})
                continue

            # SÄSONGSBYTE: Degraderings-detektorn & Vakans-lösaren
            if last_season and sas != last_season:
                if current_champion:
                    champ_plays = not df_sorted[(df_sorted['Säs'] == sas) & ((df_sorted['Hemmalag'] == current_champion) | (df_sorted['Bortalag'] == current_champion))].empty
                    
                    if not champ_plays:
                        exile_years += 1
                        if rule == 'STRICT' and exile_years == 1:
                            belt_history.append({"Datum": "-", "Omgång": "-", "Resultat": "-", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "🔻 Bältet i Dvala (Degraderad)"})
                        elif rule == 'VACANT_IMMEDIATE' and not belt_vacant:
                            current_champion = None
                            belt_vacant = True
                            exile_years = 0 
                            belt_history.append({"Datum": "-", "Omgång": "-", "Resultat": "-", "Lag": "VAKANT", "Titelmatcher": 0, "Säsong": sas, "Status": "⚠️ Vakant (Direkt vid degradering)"})
                        elif rule == 'TIME_LIMIT':
                            if exile_years == 1:
                                belt_history.append({"Datum": "-", "Omgång": "-", "Resultat": "-", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "🔻 Bältet i Dvala"})
                            
                            if exile_years == 6 and not belt_vacant: # LOGIK-FIX 2: Höjt till 6 för att nå hela 5-årsspärren
                                current_champion = None
                                belt_vacant = True
                                exile_years = 0 
                                belt_history.append({"Datum": "-", "Omgång": "-", "Resultat": "-", "Lag": "VAKANT", "Titelmatcher": 0, "Säsong": sas, "Status": "⚠️ Vakant (5-årsgränsen nådd)"})
                    else:
                        if exile_years > 0:
                            belt_history.append({"Datum": "-", "Omgång": "-", "Resultat": "-", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "🔼 Återkomst till Allsvenskan"})
                        exile_years = 0

            # AUTO-VAKANS: Identifiera rätt match
            if belt_vacant:
                if sas in MANUAL_VACANT_MATCHES:
                    target_vacant_match_id = MANUAL_VACANT_MATCHES[sas]
                else:
                    r1_matches = df_sorted[(df_sorted['Säs'] == sas) & (df_sorted['Omgång'].astype(str) == '1')]
                    
                    if not r1_matches.empty:
                        earliest_date = r1_matches['Matchdatum'].min()
                        earliest_matches = r1_matches[r1_matches['Matchdatum'] == earliest_date]
                        
                        best_gd, best_gf, best_id = -99, -1, None
                        
                        for _, r1_m in earliest_matches.iterrows():
                            try:
                                h_goals, b_goals = int(r1_m['HM']), int(r1_m['BM'])
                                if h_goals == b_goals: continue 
                                
                                gd = abs(h_goals - b_goals)
                                gf = max(h_goals, b_goals)
                                
                                if gd > best_gd or (gd == best_gd and gf > best_gf):
                                    best_gd, best_gf, best_id = gd, gf, r1_m['Match_ID']
                            except ValueError:
                                pass
                        
                        if best_id:
                            target_vacant_match_id = best_id

            last_season = sas

            # LÖS VAKANSEN (När loopen når rätt match)
            if belt_vacant and match_id == target_vacant_match_id:
                current_champion = row['Hemmalag'] if hm > bm else row['Bortalag']
                belt_vacant = False
                defense_count = 0 # LOGIK-FIX 1: Erövringsmatchen räknas ej som försvar
                target_vacant_match_id = None
                belt_history.append({"Datum": str(row['Matchdatum'])[:10], "Omgång": f"1 (Vinner Vakant)", "Resultat": f"{hm}-{bm}", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "Vinner Vakant Titel"})
                continue 

            # VANLIG TITELMATCH
            if current_champion and (row['Hemmalag'] == current_champion or row['Bortalag'] == current_champion):
                is_home = (row['Hemmalag'] == current_champion)
                gf = hm if is_home else bm
                ga = bm if is_home else hm

                # LOGIK-FIX 3: Regerande mästare spelar -> Lägg till försvarsmatchen (Lyckad eller misslyckad)
                defense_count += 1
                
                # Leta baklänges och uppdatera lagets urpsrungliga erövringsrad (ignorerar ev. Dvala/Återkomst-rader)
                for event in reversed(belt_history):
                    if event['Lag'] == current_champion and event['Status'] in ["Ny Mästare", "Första Mästaren", "Vinner Vakant Titel"]:
                        event['Titelmatcher'] = defense_count
                        break

                if gf < ga:
                    # Utmanaren vinner
                    current_champion = row['Bortalag'] if is_home else row['Hemmalag']
                    defense_count = 0 # Nollställ för den nya mästaren
                    belt_history.append({"Datum": str(row['Matchdatum'])[:10], "Omgång": row['Omgång'], "Resultat": f"{hm}-{bm}", "Lag": current_champion, "Titelmatcher": defense_count, "Säsong": sas, "Status": "Ny Mästare"})

        return {"current_champion": current_champion, "current_defenses": defense_count, "history": belt_history}

    results['STRICT'] = simulate('STRICT')
    results['VACANT_IMMEDIATE'] = simulate('VACANT_IMMEDIATE')
    results['TIME_LIMIT'] = simulate('TIME_LIMIT')
    
    return results

# =========================================================
# --- NY KOD: FUNKTION FÖR PREMIÄRMÅLSKYTTAR ---
# =========================================================
def prepare_first_scorers(filepath, df_main):
    """Läser in premiärmålskyttar och slår ihop med matchdata och ålder"""
    first_scorers_dict = {}
    try:
        df_prem = pd.read_excel(filepath, sheet_name='Premiarmalskyttar')
        df_namn = pd.read_excel(filepath, sheet_name='Malskyttenamn')
        
        # 1. Rensa bort osynliga mellanslag i rubrikerna
        df_namn.columns = df_namn.columns.str.strip()
        df_prem.columns = df_prem.columns.str.strip()

        # 2. Standardisera rubriken!
        # Döper om 'Målskytt' till 'Namn' (om det inte redan är gjort i Excel)
        if 'Målskytt' in df_prem.columns:
            df_prem.rename(columns={'Målskytt': 'Namn'}, inplace=True)

        # 3. Tvätta texten (Master Config v2.0 - fix_text)
        if 'Namn' in df_prem.columns:
            df_prem['Namn'] = df_prem['Namn'].apply(fix_text)
        if 'Namn' in df_namn.columns:
            df_namn['Namn'] = df_namn['Namn'].apply(fix_text)
        if 'Lag' in df_prem.columns:
            df_prem['Lag'] = df_prem['Lag'].apply(fix_text)
            if 'normalize_team' in globals():
                df_prem['Lag'] = df_prem['Lag'].apply(normalize_team)

        # ==========================================
        # REGEL B2: Datatvätt vid källan (Dubbletthantering)
        # ==========================================
        alias_dict = {
            "Andersson, Sven 2": "Andersson, Sven"
        }
        
        if 'Namn' in df_prem.columns:
            df_prem['Namn'] = df_prem['Namn'].replace(alias_dict)
        if 'Namn' in df_namn.columns:
            df_namn['Namn'] = df_namn['Namn'].replace(alias_dict)
        # ==========================================

        # 4. Den magiska datumtvätten
        def tvatta_excel_datum(val):
            if pd.isnull(val): return ""
            if isinstance(val, str): return val.strip()[:10]
            try: return val.strftime('%Y-%m-%d')
            except: return str(val)[:10]

        if 'Födelsedatum' in df_namn.columns:
            df_namn['Födelsedatum_txt'] = df_namn['Födelsedatum'].apply(tvatta_excel_datum)
        else:
            df_namn['Födelsedatum_txt'] = ""

        # Ta bort dubbletter i namnregistret
        df_namn_unique = df_namn.drop_duplicates(subset=['Namn'])
        
        # 5. Enkel och bombsäker sammanslagning när båda nu heter "Namn"
        df_prem = df_prem.merge(
            df_namn_unique[['Namn', 'Födelsedatum_txt']], 
            on='Namn', 
            how='left'
        )
        
        # 6. Hämta matchinfo från Huvuddatabasen
        nyckel_kolumn = 'Match_ID' if 'Match_ID' in df_main.columns else 'MatchID'
        if nyckel_kolumn in df_main.columns and nyckel_kolumn in df_prem.columns:
            df_match_info = df_main[[nyckel_kolumn, 'Datum', 'Hemmalag', 'Bortalag', 'HM', 'BM']].drop_duplicates(subset=[nyckel_kolumn])
            df_prem = df_prem.merge(df_match_info, on=nyckel_kolumn, how='left')
            
            import numpy as np
            df_prem['Motståndare'] = np.where(df_prem['Lag'] == df_prem['Hemmalag'], df_prem['Bortalag'], df_prem['Hemmalag'])
        else:
            df_prem['Datum'] = pd.NaT
            df_prem['Motståndare'] = "Okänd"
            
        # 7. Åldersberäkning med de nyskapade rena textdatumen
        df_prem['Datum_dt'] = pd.to_datetime(df_prem['Datum'], errors='coerce')
        df_prem['Fodd_dt'] = pd.to_datetime(df_prem['Födelsedatum_txt'], errors='coerce')
        
        import numpy as np
        df_prem['Ålder_år'] = np.floor((df_prem['Datum_dt'] - df_prem['Fodd_dt']).dt.days / 365.25)
        
        # 8. Bygg den slutgiltiga JSON-katalogen
        for _, row in df_prem.iterrows():
            sas_val = row.get('Säsong') if 'Säsong' in row else row.get('Säs', '')
            sas = str(sas_val).replace('.0', '').strip()
            lag = row.get('Lag', '')
            
            if pd.isna(lag) or str(lag).strip() == "": 
                continue
                
            # Fånga den beräknade åldern
            alder_val = row.get('Ålder_år')
            alder = int(alder_val) if pd.notnull(alder_val) and alder_val > 0 else ""
            
            not_text = str(row.get('Not', '')).replace('nan', '').strip()
            minut_text = str(row.get('Minut', '')).replace('nan', '').replace('.0', '').strip()
            
            if sas not in first_scorers_dict:
                first_scorers_dict[sas] = {}
            if lag not in first_scorers_dict[sas]:
                first_scorers_dict[sas][lag] = []
                
            first_scorers_dict[sas][lag].append({
                "skytt": str(row.get('Namn', '')), # Båda använder nu "Namn"
                "minut": minut_text,
                "motstandare": str(row.get('Motståndare', 'Okänd')),
                "not": not_text,
                "alder": alder,
                "datum": str(row.get('Datum', ''))[:10] if pd.notnull(row.get('Datum')) else "",
                "hm": str(row.get('HM', '')),
                "bm": str(row.get('BM', '')),
                "hemmalag": str(row.get('Hemmalag', ''))
            })
        
        return first_scorers_dict
        
    except Exception as e:
        print(f"INFO/VARNING: Fliken 'Premiarmalskyttar' eller 'Malskyttenamn' saknas/felar. Fel: {e}")
        return {}
    

# =========================================================
# LÄS IN ALL EXTRA DATA OCH SPARA I MINNET
# =========================================================
gk_info = prepare_person_data(excel_file, "Målvakter")
ref_info = prepare_person_data(excel_file, "Domare")
top_scorers = prepare_scorers(excel_file)

# NYTT: Kör vår nya funktion och skickar in `df` (Huvuddatabasen) som referens!
first_scorers = prepare_first_scorers(excel_file, df)

def create_display_name(name):
    """Tar bort siffror på slutet och vänder till 'Förnamn Efternamn'."""
    if not isinstance(name, str):
        return name
    
    clean_name = re.sub(r'\s*\d+$', '', name)
    if "," in clean_name:
        parts = clean_name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}"
    return clean_name.strip()

# ---------------------------------------------------------
# SKAPA VISNINGSNAMN (Behåll de unika nycklarna)
# ---------------------------------------------------------
for raw_name, data_dict in gk_info.items():
    data_dict["Visningsnamn"] = create_display_name(raw_name)

for raw_name, data_dict in ref_info.items():
    data_dict["Visningsnamn"] = create_display_name(raw_name)

# ---------------------------------------------------------
# KONVERTERA TILL JSON
# ---------------------------------------------------------
json_gk_info = json.dumps(gk_info, ensure_ascii=False)
json_ref_info = json.dumps(ref_info, ensure_ascii=False)

# ---------------------------------------------------------
# 3. LÄS IN SÄSONGSINFORMATION OCH POÄNGSYSTEM
# ---------------------------------------------------------
season_info = {}
series_file = os.path.join(excel_folder, "Serietabellerna_samlade.xlsx")
try:
    df_series = pd.read_excel(series_file, sheet_name="Serienivå")
    for _, row in df_series.iterrows():
        sas_nr = str(row.get('Säsnr', '')).replace('.0', '').strip()
        sas_name = str(row.get('Säsong', sas_nr)).strip()
        pts = row.get('Poäng_seger', 3)
        if pd.isna(pts) or pts == "": pts = 3
        season_info[sas_nr] = {'name': sas_name, 'pts': int(pts)}
except Exception: pass

all_teams = sorted(list(set([t for t in df['Hemmalag'].tolist() + df['Bortalag'].tolist() if str(t).strip() != ""])))

def safe_season_sort(val):
    if str(val).strip() == "": return (999999, "") 
    try: return (0, float(val)) 
    except (ValueError, TypeError): return (1, str(val)) 

all_seasons_raw = sorted(list(set(df['Säs'].tolist())), key=safe_season_sort)
all_seasons = [str(s) for s in all_seasons_raw if str(s).strip() != ""]

# ==========================================
# BYGG EPOKER OCH DECENNIER
# ==========================================
decades = {}
custom_epochs = {}

for s in all_seasons:
    try:
        name = season_info.get(s, {}).get('name', s)
        year_str = "".join(filter(str.isdigit, name))[:4]
        if len(year_str) == 4:
            decade = year_str[:3] + "0-talet"
            if decade not in decades: decades[decade] = []
            decades[decade].append(s)
    except Exception: pass

try:
    df_epochs = pd.read_excel(excel_file, sheet_name="Epoker")
    df_epochs.columns = df_epochs.columns.str.strip() 
    c_period = next((c for c in df_epochs.columns if 'period' in c.lower()), df_epochs.columns[0])
    c_start = next((c for c in df_epochs.columns if 'första' in c.lower()), df_epochs.columns[1])
    c_end = next((c for c in df_epochs.columns if 'sista' in c.lower()), df_epochs.columns[2])
    
    for _, row in df_epochs.iterrows():
        period_name = str(row.get(c_period, '')).strip()
        if not period_name or period_name == "nan": continue
        try:
            start_id = float(str(row[c_start]).replace(',', '.'))
            end_id = float(str(row[c_end]).replace(',', '.'))
        except (ValueError, TypeError, KeyError): continue
            
        epoch_seasons = []
        for s in all_seasons:
            try:
                if start_id <= float(s) <= end_id: epoch_seasons.append(s)
            except ValueError: pass
        if epoch_seasons: custom_epochs[period_name] = epoch_seasons
except Exception: pass

# ==========================================
# LÄS IN MERITER OCH STARTPOÄNG
# ==========================================
team_merits = {} 
try:
    df_tabeller = pd.read_excel(series_file, sheet_name="Tabeller")
    df_tabeller.columns = df_tabeller.columns.str.strip()
    col_sasnr = next((c for c in df_tabeller.columns if 'säsnr' in c.lower()), 'Säsnr')
    col_lag = next((c for c in df_tabeller.columns if 'lag' in c.lower() and len(c) <= 4), 'Lag')
    col_merit = next((c for c in df_tabeller.columns if 'merit' in c.lower()), 'Merit')
    col_nya = next((c for c in df_tabeller.columns if 'nya' in c.lower()), 'Nya')
    col_startpts = next((c for c in df_tabeller.columns if 'startpoäng' in c.lower() or 'poängjustering' in c.lower()), None)
    col_serie = next((c for c in df_tabeller.columns if 'serie' in c.lower()), None)
    
    def sort_key(x):
        try: return float(str(x).replace(',', '.'))
        except: return 9999
        
    sas_unique = sorted(df_tabeller[col_sasnr].unique(), key=sort_key)
    last_champions = []
    
    for sas in sas_unique:
        sas_str = str(sas).replace('.0', '').strip()
        if sas_str not in team_merits: team_merits[sas_str] = {}
        current_champions = []
        
        group = df_tabeller[df_tabeller[col_sasnr] == sas]
        for _, row in group.iterrows():
            team = str(row.get(col_lag, '')).strip()
            
            # Hårdkodad justering för att fånga upp Panos Ljungskiles meriter 1997
            if team == 'Panos Ljungskile SK': 
                team = 'Ljungskile SK'
                
            merit = str(row.get(col_merit, '')).strip()
            nya = str(row.get(col_nya, '')).strip()
            if merit == 'nan': merit = ''
            if nya == 'nan': nya = ''
            
            if col_serie:
                serie_val = str(row.get(col_serie, '')).strip()
                if serie_val and 'allsvenskan' not in serie_val.lower():
                    continue
            
            start_pts = 0.0
            if col_startpts:
                try: start_pts = float(str(row.get(col_startpts, '0')).replace(',', '.'))
                except: pass
            if pd.isna(start_pts): start_pts = 0.0

            is_regerande = team in last_champions
            
            if team not in team_merits[sas_str]:
                team_merits[sas_str][team] = {'merit': merit, 'nya': nya, 'regerande': is_regerande, 'start_pts': start_pts}
            else:
                if start_pts != 0: team_merits[sas_str][team]['start_pts'] = start_pts
                if merit: team_merits[sas_str][team]['merit'] = merit
                if nya: team_merits[sas_str][team]['nya'] = nya
            
            if merit.lower() == 'mästare': current_champions.append(team)
        last_champions = current_champions
except Exception: pass

# ==========================================
# 🏆 BERÄKNA INOFFICIELLA MÄSTARBÄLTET (UFWC)
# ==========================================
try:
    belt_results = calculate_master_belt(df)
    # Observera variabelnamnet!
    json_master_belt = json.dumps(belt_results, ensure_ascii=False)
except Exception as e:
    print(f"Ett fel uppstod vid beräkning av Mästarbältet: {e}")
    json_master_belt = json.dumps({}, ensure_ascii=False)

# Förbered JSON data
json_match_data = df.to_json(orient="records", force_ascii=False)
json_teams_data = json.dumps(all_teams, ensure_ascii=False)
json_seasons_data = json.dumps(all_seasons, ensure_ascii=False)
json_season_info = json.dumps(season_info, ensure_ascii=False)
json_decades_data = json.dumps(decades, ensure_ascii=False)
json_custom_epochs_data = json.dumps(custom_epochs, ensure_ascii=False)
json_team_merits_data = json.dumps(team_merits, ensure_ascii=False)

# ==========================================
# 3. HTML / FRONTEND
# ==========================================
html_template = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Allsvenskan Matchhistorik</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .custom-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        .tab-btn.active { border-bottom: 2px solid #2563eb; color: #1e3a8a; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        optgroup { font-weight: 700; color: #475569; background-color: #f8fafc; }
        optgroup[disabled] { color: #94a3b8; background-color: #f1f5f9; }
        option { font-weight: normal; color: #0f172a; background-color: #fff; }
        .sortable-th { cursor: pointer; user-select: none; }
        .sortable-th:hover { background-color: #e2e8f0; }
        .tooltip-container:hover .tooltip-content { display: block; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen">

    <header class="bg-blue-900 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight">Allsvenskan Matchhistorik</h1>
                <p class="text-blue-200 mt-1">Utforska varje enskilt resultat från 1924 och framåt</p>
            </div>
            <a href="nationella_index.html" class="inline-flex items-center text-blue-100 hover:text-white transition-colors text-sm font-medium bg-blue-800 hover:bg-blue-700 px-4 py-2 rounded-md shadow-sm border border-blue-700">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Tillbaka till översikten
            </a>
        </div>
    </header>

    <nav class="bg-white shadow-sm sticky top-0 z-20">
        <div class="max-w-7xl mx-auto px-4 flex overflow-x-auto custom-scroll">
            <button onclick="switchTab('h2h')" id="btn-h2h" class="tab-btn active whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Head-to-Head</button>
            <button onclick="switchTab('search')" id="btn-search" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Matchsök / Historik</button>
            <button onclick="switchTab('records')" id="btn-records" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Topplistor</button>
            <button onclick="switchTab('streaks')" id="btn-streaks" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Långa sviter</button>
            <button onclick="switchTab('tables')" id="btn-tables" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Tabeller</button>
            <button onclick="switchTab('profiles')" id="btn-profiles" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Säsongens Profiler</button>
            <button onclick="switchTab('strength')" id="btn-strength" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Säsongsstyrka</button>
            <button onclick="switchTab('goldrace')" id="btn-goldrace" class="tab-btn whitespace-nowrap py-4 px-6 text-yellow-600 font-bold hover:text-yellow-700 bg-yellow-50">Guldstriden</button>
            <button onclick="switchTab('analysis')" id="btn-analysis" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Förutsägbarhet</button>
            <button onclick="switchTab('results')" id="btn-results" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Matchresultat</button>
            <button onclick="switchTab('gkref')" id="btn-gkref" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Målvakter & Domare</button>
            <button onclick="switchTab('belt')" id="btn-belt" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-700">Mästarbältet</button>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 py-8">
        
        <!-- FLIK 1: H2H -->
        <section id="tab-h2h" class="tab-content active">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Analysera inbördes möten</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag A (Fokuslag) <span id="rank-team-a" class="text-xs text-blue-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-a" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                    <div class="flex justify-center pb-2"><span class="text-slate-400 font-bold">VS</span></div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag B (Motståndare) <span id="rank-team-b" class="text-xs text-blue-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-b" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                </div>
                <div class="mt-5 flex flex-col lg:flex-row justify-between items-center gap-4 border-t border-slate-100 pt-5 mb-2">
                    <!-- Vänstra sidan: Filtreringsval -->
                    <div class="flex flex-wrap gap-4 text-sm w-full lg:w-auto justify-center lg:justify-start">
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="all" checked onchange="calculateH2H()"> Alla möten</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="home" onchange="calculateH2H()"> Endast Lag A Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="away" onchange="calculateH2H()"> Endast Lag A Borta</label>
                    </div>
                    
                    <!-- Högra sidan: Knappar och Ghost Switch i samma rad -->
                    <div class="flex flex-wrap justify-center lg:justify-end items-center gap-2 w-full lg:w-auto">
                        <button onclick="renderH2HOverview()" class="bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-4 rounded-md transition-colors text-sm">Statistik mot alla lag</button>
                        <button onclick="calculateH2H()" class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition-colors shadow-sm text-sm">Analysera VS</button>
                        
                        <!-- Ghost Switch med Smart Vy-detektor och en liten vänstermarginal (ml-1) -->
                        <label class="flex items-center gap-2 text-xs font-medium text-slate-600 hover:text-slate-900 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md cursor-pointer transition-colors shadow-sm ml-1" title="Visar matcher som strukits ur de officiella tabellerna">
                            <input type="checkbox" id="toggle-annulled-h2h" onchange="if(document.getElementById('h2h-overview').classList.contains('hidden')) { calculateH2H(); } else { renderH2HOverview(); }" class="rounded border-amber-300 text-amber-600 focus:ring-amber-500 w-3.5 h-3.5 mt-0.5">
                            <span class="whitespace-nowrap">Inkludera annullerade (ex. MFF 1933)</span>
                        </label>
                    </div>
                </div>
            <!-- ---------------------------------------- -->
            
            <div id="h2h-results" class="hidden">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="h2h-summary-cards"></div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag</th><th class="px-4 py-3 text-center">Resultat</th>
                                    <th class="px-4 py-3">Bortalag</th><th class="px-4 py-3 text-right">Publik</th>
                                </tr>
                            </thead>
                            <tbody id="h2h-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                    <div id="h2h-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
                </div>
            </div>

            <div id="h2h-overview" class="hidden">
                <h3 class="text-lg font-bold mb-3 text-slate-700" id="overview-title">Sammanställning</h3>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3 sortable-th" onclick="sortOverview('team')">Motståndare ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('played')">Spelade ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-emerald-600" onclick="sortOverview('w')">V ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortOverview('d')">O ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-rose-600" onclick="sortOverview('l')">F ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('gf')">GM ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('ga')">IM ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center font-bold" onclick="sortOverview('gd')">+/- ↕</th>
                                </tr>
                            </thead>
                            <tbody id="h2h-overview-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 2: Matchsök -->
        <section id="tab-search" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-8">
                
                <!-- NYTT: Rubrik och Ghost Switch på samma rad -->
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-5 gap-3 border-b border-slate-100 pb-3">
                    <h2 class="text-xl font-bold text-slate-800 m-0">Avancerad Matchsökning</h2>
                    
                    <label class="flex items-center gap-2 text-xs font-medium text-slate-600 hover:text-slate-900 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md cursor-pointer transition-colors shadow-sm" title="Visar matcher som strukits ur de officiella tabellerna">
                        <input type="checkbox" id="toggle-annulled-search" onchange="performSearch()" class="rounded border-amber-300 text-amber-600 focus:ring-amber-500 w-3.5 h-3.5 mt-0.5">
                        <span class="whitespace-nowrap">Inkludera annullerade (ex. MFF 1933)</span>
                    </label>
                </div>
                <!-- --------------------------------------- -->

                <div class="grid grid-cols-1 lg:grid-cols-5 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <div class="flex items-center gap-1">
                            <button onclick="changeSeasonLocal('search-season', 1)" class="p-2 bg-slate-100 hover:bg-indigo-100 text-slate-600 hover:text-indigo-700 rounded-md transition-colors border border-slate-200" title="Föregående säsong i listan">◀</button>
                            <select id="search-season" onchange="updateSearchPhaseDropdown()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                            <button onclick="changeSeasonLocal('search-season', -1)" class="p-2 bg-slate-100 hover:bg-indigo-100 text-slate-600 hover:text-indigo-700 rounded-md transition-colors border border-slate-200" title="Nästa säsong i listan">▶</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Omgång</label>
                        <input type="text" id="search-round" placeholder="T.ex. 15 eller M1" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag</label>
                        <select id="search-team" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1" title="Lagets mål - Motståndarens mål">Resultat (Mål)</label>
                        <div class="flex items-center gap-2">
                            <input type="number" id="search-hm" placeholder="Gjorda" min="0" class="w-full border border-slate-300 rounded-md p-2 text-center bg-slate-50">
                            <span class="font-bold text-slate-400">-</span>
                            <input type="number" id="search-bm" placeholder="Insläppta" min="0" class="w-full border border-slate-300 rounded-md p-2 text-center bg-slate-50">
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="clearSearch()" class="w-1/3 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm" title="Rensa filter">Rensa</button>
                        <button onclick="performSearch()" class="w-2/3 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm">Sök</button>
                    </div>
                </div>
            </div>

            <div id="search-results" class="hidden">
                <div class="mb-2 text-sm text-slate-600 font-medium" id="search-summary-text"></div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Omgång</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag</th><th class="px-4 py-3 text-center">Resultat (HT)</th>
                                    <th class="px-4 py-3">Bortalag</th><th class="px-4 py-3 text-right">Publik</th>
                                </tr>
                            </thead>
                            <tbody id="search-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                    <div id="search-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
                </div>
            </div>
        </section>

<!-- FLIK 3: Rekord -->
<section id="tab-records" class="tab-content">
    <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
        
        <!-- Ny navigering inom fliken (Switch) -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4 border-b border-slate-200 pb-4">
            <div>
                <h2 class="text-xl font-bold">Historiska Topplistor & Rekord</h2>
                <p class="text-sm text-slate-500">Utforska lagens matchrekord och spelarnas individuella utmärkelser.</p>
            </div>
            <div class="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
                <button id="btn-view-match" onclick="toggleRecordsView('match')" class="px-4 py-2 bg-white text-slate-800 shadow-sm rounded-md font-bold text-sm transition-all">🛡️ Matchrekord (Lag)</button>
                <button id="btn-view-players" onclick="toggleRecordsView('players')" class="px-4 py-2 text-slate-500 hover:text-slate-700 rounded-md font-bold text-sm transition-all">⚽ Skyttar & Priser</button>
            </div>
        </div>

        <!-- CONTAINER 1: MATCHREKORD (Din befintliga design) -->
        <div id="records-match-container">
            <div class="flex justify-end mb-4 w-full md:w-64 ml-auto">
                <select id="records-team" onchange="renderRecords()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-wins">Största segrarna</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-wins"></tbody></table></div>
                </div>
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-losses">Största förlusterna</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-losses"></tbody></table></div>
                </div>
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-goals">Målrikaste matcherna</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-goals"></tbody></table></div>
                </div>
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center"><h3 class="font-bold text-slate-700" id="rec-title-comebacks">Största halvtidsvändningarna</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-comebacks"></tbody></table></div>
                </div>
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-att-high">Högsta publiksiffrorna</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-att-high"></tbody></table></div>
                </div>
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-att-low">Lägsta publiksiffrorna (>10)</h3></div>
                    <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-att-low"></tbody></table></div>
                    <div class="px-4 py-2 bg-slate-50 text-xs text-slate-500 border-t border-slate-200">* Matcher med 10 åskådare eller färre är exkluderade.</div>
                </div>
            </div>
        </div>

        <!-- CONTAINER 2: SPELARSTATISTIK (Ny) -->
        <div id="records-players-container" class="hidden">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <!-- Topplista: Skyttekungar -->
                <div class="border border-slate-200 rounded-lg overflow-hidden flex flex-col">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center">
                        <h3 class="font-bold text-slate-700 text-xs uppercase tracking-wider">Flest Guldskor</h3>
                        <span class="text-xs cursor-help" title="Visar de spelare som har vunnit skytteligan flest gånger i den Allsvenska historien.">🏆</span>
                    </div>
                    <div class="p-0 overflow-y-auto max-h-64 flex-1"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-top-players-scorers"></tbody></table></div>
                </div>
                <!-- Topplista: Klubbar -->
                <div class="border border-slate-200 rounded-lg overflow-hidden flex flex-col">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center">
                        <h3 class="font-bold text-slate-700 text-xs uppercase tracking-wider">Målmaskiner (Klubb)</h3>
                        <span class="text-xs cursor-help" title="Visar vilka klubbar som spelarna representerade när de vann skytteligan i Allsvenskan. Om en spelare bytt klubb under säsongen tillgodoräknas båda klubbarna.">🛡️</span>
                    </div>
                    <div class="p-0 overflow-y-auto max-h-64 flex-1"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-top-clubs-scorers"></tbody></table></div>
                </div>
                <!-- Topplista: DN-klockan / Snabbaste -->
                <div class="border border-slate-200 rounded-lg overflow-hidden flex flex-col">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center">
                        <h3 class="font-bold text-slate-700 text-xs uppercase tracking-wider">DN-Klockan/Snabbaste</h3>
                        <span class="text-xs cursor-help" title="Visar de spelare som har gjort det absolut snabbaste målet i den första omgången för säsongen (och därmed tagit hem DN-klockan (från 1959) eller den historiska guldmedaljen).">⏱️</span>
                    </div>
                    <div class="p-0 overflow-y-auto max-h-64 flex-1"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-top-players-dn"></tbody></table></div>
                </div>
                <!-- Topplista: Premiärmål totalt -->
                <div class="border border-slate-200 rounded-lg overflow-hidden flex flex-col">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200 flex justify-between items-center">
                        <h3 class="font-bold text-slate-700 text-xs uppercase tracking-wider">Flest Premiärmål</h3>
                        <span class="text-xs cursor-help" title="Visar de spelare som nätat i lagets allra första match för säsongen flest gånger totalt. Självmål är exkluderade ur statistiken.">🎯</span>
                    </div>
                    <div class="p-0 overflow-y-auto max-h-64 flex-1"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-top-players-premiere"></tbody></table></div>
                </div>
            </div>

            <hr class="border-slate-200 mb-8">

            <!-- KRONOLOGISKA LISTOR -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Alla Skyttekungar (Kronologisk) -->
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-800 text-white px-4 py-3 flex justify-between items-center"><h3 class="font-bold text-sm uppercase tracking-wider flex items-center gap-2">🏅 Alla Skyttekungar</h3></div>
                    <div class="p-0 overflow-y-auto max-h-[600px]">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-xs text-slate-500 uppercase sticky top-0 shadow-sm"><tr><th class="px-4 py-2">Säsong</th><th class="px-4 py-2">Spelare</th><th class="px-4 py-2 text-right">Mål</th></tr></thead>
                            <tbody id="rec-chrono-scorers" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
                <!-- Alla DN-klockan / Snabbaste -->
                <div class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="bg-slate-800 text-white px-4 py-3 flex justify-between items-center"><h3 class="font-bold text-sm uppercase tracking-wider flex items-center gap-2">⏱️ Historiska Tidsmästare</h3></div>
                    <div class="p-0 overflow-y-auto max-h-[600px]">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-xs text-slate-500 uppercase sticky top-0 shadow-sm"><tr><th class="px-4 py-2">Säsong</th><th class="px-4 py-2">Spelare</th><th class="px-4 py-2 text-right">Minut</th></tr></thead>
                            <tbody id="rec-chrono-dn" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>

        <!-- FLIK 4: Sviter -->
        <section id="tab-streaks" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 items-end mb-6">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Välj lag för att beräkna sviter</label>
                        <select id="streaks-team" onchange="calculateStreaks()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                        </select>
                    </div>
                    <div class="flex gap-4 bg-slate-100 p-2 rounded-md justify-center">
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="all" checked onchange="calculateStreaks()"> Totalt</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="home" onchange="calculateStreaks()"> Endast Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="away" onchange="calculateStreaks()"> Endast Borta</label>
                    </div>
                    <div class="flex flex-col gap-2">
                        <div class="bg-blue-50 border border-blue-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-blue-800">
                                <input type="checkbox" id="streak-from-start" onchange="calculateStreaks()" class="w-4 h-4 text-blue-600"> Enbart från säsongsstart
                            </label>
                        </div>
                        <div class="bg-blue-50 border border-blue-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-blue-800">
                                <input type="checkbox" id="streak-same-season" onchange="calculateStreaks()" class="w-4 h-4 text-blue-600"> Bryt svit vid säsongsslut
                            </label>
                        </div>
                    </div>
                </div>
                
                <h3 class="text-lg font-bold mb-4 text-slate-700" id="streaks-main-title">Längsta Sviterna (Klicka på korten för lista)</h3>
                <div id="streaks-results" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 hidden mb-8"></div>
                
                <div id="season-records-section" class="hidden">
                    <h3 class="text-lg font-bold mb-4 text-slate-700" id="season-records-title">Max totalt under en säsong</h3>
                    <div id="season-records-results" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"></div>
                </div>

                <div class="mt-8 pt-8 border-t border-slate-200">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                        <h3 class="font-bold text-lg text-slate-700">Topp 10: Historiska Sviter</h3>
                        <select id="streak-toplist-type" onchange="renderStreakToplist()" class="w-full md:w-64 border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                            <option value="">-- Välj svit att visa --</option>
                            <option value="win">Längsta Segersvit</option>
                            <option value="unb">Längst Obesegrade</option>
                            <option value="loss">Längsta Förlustsvit</option>
                            <option value="winless">Längst Utan Seger</option>
                            <option value="draw">Flest Oavgjorda i rad</option>
                            <option value="cs">Flest Hållna Nollor i rad</option>
                            <option value="ns">Längsta Måltorka i rad</option>
                            <option value="scored">Flest matcher med gjorda mål i rad</option>
                            <option value="conceded">Flest matcher med insläppta mål i rad</option>
                        </select>
                    </div>
                    
                    <div id="streak-toplist-container" class="hidden bg-white rounded-lg border border-slate-200 overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200">
                                    <tr>
                                        <th class="p-3 w-10">#</th>
                                        <th class="p-3">Lag</th>
                                        <th class="p-3 text-center">Antal Matcher</th>
                                        <th class="p-3 text-slate-500">Start (Datum / Säsong)</th>
                                        <th class="p-3 text-slate-500">Slut (Datum / Säsong)</th>
                                        <th class="p-3 text-center">Målskillnad</th>
                                    </tr>
                                </thead>
                                <tbody id="streak-toplist-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="streaks-placeholder" class="text-center py-10 text-slate-500">Kalkylatorn letar fram de längsta sviterna.</div>
            </div>
        </section>

        <!-- FLIK 5: Tabeller -->
        <section id="tab-tables" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Dynamisk Serietabell</h2>
                <div class="grid grid-cols-1 md:grid-cols-5 gap-4 items-end mb-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <div class="flex items-center gap-1"><button onclick="changeSeasonLocal('table-season', 1)" class="p-2 bg-slate-100 hover:bg-indigo-100 text-slate-600 hover:text-indigo-700 rounded-md transition-colors border border-slate-200" title="Föregående säsong i listan">◀</button><select id="table-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select><button onclick="changeSeasonLocal('table-season', -1)" class="p-2 bg-slate-100 hover:bg-indigo-100 text-slate-600 hover:text-indigo-700 rounded-md transition-colors border border-slate-200" title="Nästa säsong i listan">▶</button></div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Fas i serien</label>
                        <select id="table-phase" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                            <option value="ALL">Alla matcher</option>
                            <option value="GRUND">Grundserien</option>
                            <option value="MASTER">Mästerskapsserien</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Efter omgång</label>
                        <input type="text" id="table-round" placeholder="T.ex. 15 eller M1" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                    </div>
                    <div class="col-span-2 grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-sm font-medium text-slate-700 mb-1">Perspektiv</label>
                            <select id="table-perspective" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                                <option value="ALL_FULL">Totalt (Fulltid)</option>
                                <option value="HOME_FULL">Hemmatabell</option>
                                <option value="AWAY_FULL">Bortatabell</option>
                                <option value="ALL_1H">Första halvlek (HT)</option>
                                <option value="ALL_2H">Andra halvlek (HT2)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-slate-700 mb-1">Poäng</label>
                            <div class="flex gap-1">
                                <select id="table-points" onchange="if(!document.getElementById('table-results').classList.contains('hidden')){ if(document.getElementById('table-title').innerText.includes('Maratontabell')) renderDynamicAllTimeTable(); else calculateLeagueTable(); }" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                                    <option value="3">3 p</option><option value="2">2 p</option>
                                </select>
                                <button onclick="calculateLeagueTable()" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium p-2 rounded-md shadow-sm">Bygg</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end border-t border-slate-100 pt-4">
                    <div class="md:col-span-2">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Maratontabell (Välj epok eller totalt)</label>
                        <div class="flex gap-2">
                            <select id="table-epoch" class="w-2/3 border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                            <button onclick="renderDynamicAllTimeTable()" class="w-1/3 bg-slate-800 hover:bg-slate-900 text-white font-medium py-2 px-4 rounded-md shadow-sm text-sm">Visa</button>
                        </div>
                        <label class="flex items-center gap-2 mt-2 text-sm text-slate-600 cursor-pointer">
                            <input type="checkbox" id="maraton-exclude-master" onchange="renderDynamicAllTimeTable()" class="rounded text-blue-600"> Exklusive Mästerskapsserien
                        </label>
                    </div>
                </div>
            </div>
                    
            <div id="table-results" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mb-6">
                <div class="bg-slate-50 p-3 border-b border-slate-200 flex flex-col md:flex-row justify-between items-start md:items-center">
                    <div class="flex items-center gap-4">
                        <h3 class="font-bold text-slate-700" id="table-title">Tabell</h3>
                        <span id="table-goal-stats" class="text-xs font-semibold text-blue-600 bg-blue-100 px-3 py-1 rounded hidden border border-blue-200 shadow-sm"></span>
                    </div>
                    <div id="table-legend" class="text-[10px] text-slate-500 flex flex-wrap gap-3 mt-2 md:mt-0 hidden">
                        <span class="flex items-center"><span class="text-amber-500 mr-1 text-sm">👑</span> Regerande mästare</span>
                        <span class="flex items-center"><span class="text-yellow-500 mr-1 text-sm">🥇</span> Mästare</span>
                        <span class="flex items-center"><span class="text-slate-400 mr-1 text-sm">🥈</span> Medalj</span>
                        <span class="flex items-center"><span class="bg-blue-100 text-blue-600 px-1 rounded font-bold mr-1">NY</span> Nykomling</span>
                        <span class="flex items-center"><span class="bg-rose-100 text-rose-600 px-1 rounded font-bold mr-1">↓</span> Degraderad</span>
                    </div>
                </div>
                <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm" id="league-table-head"></thead>
                        <tbody id="league-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
                <div id="table-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
            </div>

            <!-- ====== NYTT: SKYTTEKUNG BEHÅLLARE ====== -->
            <div id="top-scorer-container" class="hidden mb-6 w-full fade-in"></div>
            <!-- ======================================== -->

            <div id="team-trend-section" class="hidden bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 border-b border-slate-100 pb-4">
                    <h3 class="font-bold text-lg text-slate-700" id="trend-title">Placeringsutveckling under säsongen</h3>
                    <div class="w-full md:w-64 mt-2 md:mt-0">
                        <select id="trend-team-select" onchange="renderTeamTrend()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                </div>
                <div class="relative h-72 w-full"><canvas id="teamTrendChart"></canvas></div>
            </div>
        </section>

        <!-- FLIK 6: SÄSONGENS PROFILER -->
        <section id="tab-profiles" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-2">Säsongens Profiler (Mästare & Nykomlingar)</h2>
                <p class="text-slate-500 text-sm mb-4">Fokusera på hur årets Mästare, de Regerande mästarna, samt Nykomlingarna presterade under en specifik säsong.</p>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Välj Säsong</label>
                        <select id="profiles-season" onchange="renderProfiles()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                </div>
            </div>
            <div id="profiles-results" class="hidden flex flex-col gap-6">
                <div id="profile-champions"></div>
                <div id="profile-defending"></div>
                <div id="profile-promoted"></div>
            </div>
            <div id="profiles-placeholder" class="text-center py-10 text-slate-500">Välj en säsong ovan för att se detaljerad historik.</div>
        </section>

        <!-- FLIK 7: SÄSONGSSTYRKA -->
        <section id="tab-strength" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-2xl">💪</span>
                            <h2 class="text-xl font-bold text-slate-800">Säsongsstyrka (Historisk Ranking)</h2>
                        </div>
                        <p class="text-slate-500 text-sm max-w-3xl">Vilken säsong var egentligen tuffast? Genom att värdera varje deltagande lag utifrån deras <b class="text-slate-700">historiska totalpoäng</b> och <b class="text-slate-700">Maratonplacering</b> får vi fram ett styrkeindex för hela ligan respektive toppstriden.</p>
                    </div>
                    
                    <div class="tooltip-container relative cursor-pointer z-50">
                        <div class="bg-blue-100 text-blue-800 rounded-full w-8 h-8 flex items-center justify-center font-bold font-serif">i</div>
                        <div class="tooltip-content hidden absolute right-0 top-10 w-96 bg-slate-800 text-white text-xs p-4 rounded shadow-xl">
                            <p class="font-bold mb-2 text-sm text-blue-300">Så här fungerar kolumnerna:</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Snitt Maratontabell (Topp 3):</span> Ett värde på 2.0 innebär att platserna 1, 2 och 3 togs av de tre lag som leder den historiska maratontabellen (1+2+3 delat på 3). Ett lägre värde = fler historiska giganter i toppen.</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Snitt Maratontabell (Hela Serien):</span> Samma princip men för alla lag i serien. Observera att äldre säsonger med färre lag naturligt får ett lägre (bättre) snitt.</p>
                            <p><span class="font-bold text-blue-300">Styrkeindex (0-100):</span> Löser problemet med varierande antal lag. Beräknas genom att ta de deltagande lagens <i>historiska poängsnitt per match (PPG)</i> under hela sin existens, slå ihop det till ett snitt för säsongen, och multiplicera med 50. <b>Ju högre index, desto fler klassiska tungviktare deltog det året.</b></p>
                        </div>
                    </div>
                </div>

                <button onclick="runStrengthAnalysis()" id="btn-run-strength" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-md shadow-sm transition-colors flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Beräkna Historisk Säsongsstyrka
                </button>
            </div>
            
            <div id="strength-loading" class="hidden text-center py-10">
                <div class="inline-block animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mb-4"></div>
                <p class="text-slate-500 font-medium">Sammanställer All-Time-data och utvärderar alla säsonger...</p>
            </div>

            <div id="strength-results" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="bg-slate-50 p-4 border-b border-slate-200">
                    <h3 class="font-bold text-slate-800">Ranking av Allsvenska säsonger</h3>
                </div>
                <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th class="px-4 py-3 sortable-th" onclick="sortStrength('season')">Säsong ↕</th>
                                <th class="px-4 py-3 sortable-th text-center" onclick="sortStrength('nTeams')">Antal Lag ↕</th>
                                <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortStrength('avgRank')" title="Lägst är bäst">Snitt Maratontabell (Hela Serien) ↕</th>
                                <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortStrength('avgTop3Rank')" title="Lägst är bäst">Snitt Maratontabell (Topp 3) ↕</th>
                                <th class="px-4 py-3 sortable-th text-center font-bold text-blue-600" onclick="sortStrength('index')" title="Baserat på lagens historiska PPG (Points per game). Högst är starkast!">Styrkeindex ↕</th>
                            </tr>
                        </thead>
                        <tbody id="strength-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 8: GULDSTRIDEN -->
        <section id="tab-goldrace" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex items-center gap-3 mb-2">
                    <span class="text-2xl">🏆</span>
                    <h2 class="text-xl font-bold text-slate-800">Guldstriden & Serieledning</h2>
                </div>
                <p class="text-slate-500 text-sm mb-6 max-w-3xl">Här analyseras 100 år av guldstrider. Vem har lett serien flest gånger? Vilka tappade guldet på målsnöret? När säkrades gulden?</p>
                <button onclick="runGoldRaceAnalysis()" id="btn-run-gold" class="bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-3 px-6 rounded-md shadow-sm transition-colors flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    Kör Historisk Guld-analys
                </button>
            </div>
            <div id="goldrace-loading" class="hidden text-center py-10">
                <div class="inline-block animate-spin w-8 h-8 border-4 border-yellow-500 border-t-transparent rounded-full mb-4"></div>
                <p class="text-slate-500 font-medium">Processar och bygger omgångstabeller för över 100 säsonger...</p>
            </div>
            <div id="goldrace-results" class="hidden flex flex-col gap-6">
                <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                    <div class="bg-slate-50 border-b border-slate-200 p-4">
                        <h3 class="font-bold text-slate-800">Dramatik i sista omgången (Sena Guldryck)</h3>
                        <p class="text-xs text-slate-500 mt-1">Säsonger där de blivande mästarna <b>inte</b> låg etta inför den allra sista omgången.</p>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">Säsong</th><th class="p-3 text-yellow-600">Svenska Mästare</th><th class="p-3 text-rose-600">Lag som passerades i sista omgången</th></tr></thead>
                            <tbody id="gr-late-winners" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-slate-50 border-b border-slate-200 p-4"><h3 class="font-bold text-slate-800">Dominanterna</h3><p class="text-xs text-slate-500 mt-1">Flest omgångar i serieledning under en och samma säsong.</p></div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">#</th><th class="p-3">Lag</th><th class="p-3">Säsong</th><th class="p-3 text-center">Omgångar</th></tr></thead><tbody id="gr-most-lead" class="divide-y divide-slate-100"></tbody></table>
                        </div>
                    </div>
                    <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-slate-50 border-b border-slate-200 p-4"><h3 class="font-bold text-slate-800">Snubblarna</h3><p class="text-xs text-slate-500 mt-1">Flest omgångar i serieledning <b>utan</b> att till slut vinna guld.</p></div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">#</th><th class="p-3 text-rose-600">Tappade Guldet</th><th class="p-3">Säsong</th><th class="p-3 text-center">Omgångar</th></tr></thead><tbody id="gr-most-lead-nowin" class="divide-y divide-slate-100"></tbody></table>
                        </div>
                    </div>
                    <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-slate-50 border-b border-slate-200 p-4"><h3 class="font-bold text-slate-800">Smygarna</h3><p class="text-xs text-slate-500 mt-1">Svenska Mästare med <b>färst</b> antal omgångar i serieledning.</p></div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">#</th><th class="p-3 text-emerald-600">Svenska Mästare</th><th class="p-3">Säsong</th><th class="p-3 text-center">Omgångar i Topp</th></tr></thead><tbody id="gr-least-lead-win" class="divide-y divide-slate-100"></tbody></table>
                        </div>
                    </div>
                </div>
                <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                    <div class="bg-slate-50 border-b border-slate-200 p-4 flex justify-between items-center">
                        <div>
                            <h3 class="font-bold text-slate-800">När säkrades Guldet?</h3>
                            <p class="text-xs text-slate-500 mt-1">När gapet till tvåan blev matematiskt ointagligt.</p>
                        </div>
                    </div>
                    <div class="overflow-x-auto custom-scroll" style="max-height: 500px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 sticky top-0 z-10 shadow-sm"><tr><th class="p-3">Säsong</th><th class="p-3 text-yellow-600">Mästare</th><th class="p-3 text-center">Säkrades i omgång</th><th class="p-3 text-center font-bold">Matcher kvar</th></tr></thead>
                            <tbody id="gr-clinch" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 9: Analys (Förutsägbarhet) -->
        <section id="tab-analysis" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h2 class="text-xl font-bold mb-1">Har serien "satt sig"?</h2>
                        <p class="text-slate-500 text-sm max-w-3xl">Mät tabellens förutsägbarhet över tid. Välj mellan att se utvecklingen över en säsong/epok i en graf, eller jämför alla säsonger i en specifik omgång.</p>
                    </div>
                    <div class="tooltip-container relative cursor-pointer z-50">
                        <div class="bg-blue-100 text-blue-800 rounded-full w-8 h-8 flex items-center justify-center font-bold font-serif">i</div>
                        <div class="tooltip-content hidden absolute right-0 top-10 w-80 bg-slate-800 text-white text-xs p-4 rounded shadow-xl">
                            <p class="font-bold mb-2 text-sm text-blue-300">Analysmetoder:</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Positionsfel (MAE):</span> Visar hur många placeringar lagen i snitt ligger ifrån sin slutgiltiga placering. Ett värde på 1.5 betyder att lagen i snitt skiljer sig 1.5 placeringar från facit.</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Spearmans Rangkorrelation:</span> Ett matematiskt mått mellan -1 och 1. Värdet 1.0 betyder att tabellen är 100% identisk med sluttabellen. Allt över 0.8 anses vara ett mycket starkt samband.</p>
                            <p><span class="font-bold text-blue-300">Delstrider (Topp/Botten 3):</span> Rankingen skalas om från 1 till 3 internt för dessa lag innan Spearmans beräknas, för att säkerställa att värdet håller sig strikt inom -1 till 1.</p>
                        </div>
                    </div>
                </div>

                <div class="flex gap-4 mb-6 border-b border-slate-200 pb-2">
                    <button onclick="toggleAnalysisMode('chart')" id="btn-mode-chart" class="font-bold text-blue-600 border-b-2 border-blue-600 px-2 pb-1 transition-colors">Utveckling över omgångar</button>
                    <button onclick="toggleAnalysisMode('table')" id="btn-mode-table" class="font-medium text-slate-500 hover:text-blue-600 px-2 pb-1 transition-colors">Jämför vid specifik omgång</button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1" id="lbl-analysis-season">Välj Epok / Säsong</label>
                        <select id="analysis-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500"></select>
                    </div>
                    <div id="div-analysis-round" class="hidden">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Utvärdera efter omgång</label>
                        <input type="number" id="analysis-round" value="10" min="1" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Fokusområde</label>
                        <select id="analysis-focus" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                            <option value="all">Hela tabellen</option><option value="top">Toppstriden (3 lag)</option><option value="bottom">Bottenstriden (3 lag)</option>
                        </select>
                    </div>
                    <div>
                        <button onclick="runPredictabilityAnalysis()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 px-4 rounded-md shadow-sm">Kör Analys</button>
                    </div>
                </div>
            </div>
            
            <div id="analysis-results" class="hidden">
                <div id="analysis-warning" class="hidden mb-4 p-4 rounded-md text-sm border"></div>
                <div id="analysis-chart-container" class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                    <div class="relative h-96 w-full"><canvas id="analysisChart"></canvas></div>
                </div>
                <div id="analysis-comparison-table" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mb-6">
                    <div class="bg-slate-50 p-3 border-b border-slate-200 flex justify-between items-center"><h3 class="font-bold text-slate-700" id="comparison-title">Jämförelse vid omgång X</h3></div>
                    <div class="overflow-x-auto custom-scroll" style="max-height: 500px;">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr><th class="p-3">Säsong</th><th class="p-3 text-center">Positionsfel (MAE)</th><th class="p-3 text-center">Spearmans Korrelation</th></tr>
                            </thead>
                            <tbody id="comparison-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>
                <div id="analysis-details" class="hidden bg-slate-800 rounded-lg shadow-lg border border-slate-700 p-6 text-white mb-6">
                    <div class="flex justify-between items-end mb-6">
                        <div>
                            <h3 class="text-xl font-bold text-blue-300" id="details-title">Omgång X</h3>
                            <p class="text-sm text-slate-400">Jämförelse mellan denna omgång och sluttabellen.</p>
                        </div>
                        <div class="text-right">
                            <div class="text-sm text-slate-400">Genomsnittligt fel: <span id="details-mae" class="text-white font-bold"></span> placeringar</div>
                            <div class="text-sm text-slate-400">Spearmans Korrelation: <span id="details-spearman" class="text-emerald-400 font-bold"></span></div>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm whitespace-nowrap bg-slate-900 rounded-lg overflow-hidden">
                            <thead class="bg-slate-700 text-slate-300 border-b border-slate-600">
                                <tr><th class="p-3">Lag</th><th class="p-3 text-center">Placering Nu</th><th class="p-3 text-center text-emerald-300">Slutplacering (Facit)</th><th class="p-3 text-center font-bold">Diff</th></tr>
                            </thead>
                            <tbody id="details-body" class="divide-y divide-slate-800"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 10: Matchresultat -->
        <section id="tab-results" class="tab-content">
            <div class="max-w-7xl mx-auto px-4 py-8">
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 mb-8 overflow-hidden">
                    <table class="w-full text-sm text-left">
                        <thead id="results-head"></thead>
                        <tbody id="results-body"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 11: Målvakter & Domare -->
        <section id="tab-gkref" class="tab-content">
            <div class="max-w-7xl mx-auto px-4 py-2">
                
                <!-- Kontrollpanel -->
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 p-4 mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
                    <div class="flex bg-slate-100 p-1 rounded-lg border border-slate-200 shrink-0">
                        <button onclick="window.gkref_mode='gk'; renderGkRef()" id="btn-mode-gk" class="px-6 py-2 rounded-md font-bold text-sm transition-colors bg-white text-blue-700 shadow-sm">🧤 Målvakter</button>
                        <button onclick="window.gkref_mode='ref'; renderGkRef()" id="btn-mode-ref" class="px-6 py-2 rounded-md font-bold text-sm transition-colors text-slate-500 hover:text-slate-800">⚖️ Domare</button>
                    </div>
                    
                    <div class="flex flex-col sm:flex-row w-full gap-3">
                        <!-- Ny Rullista: Fas i serien -->
                        <select id="gkref-fas" onchange="window.gkref_fas=this.value; renderGkRef()" class="w-full sm:w-48 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium text-slate-700 bg-slate-50">
                            <option value="ALL">Alla matcher</option>
                            <option value="GRUND">Endast Grundserien</option>
                            <option value="MASTER">Endast Mästerskapsserien</option>
                        </select>
                        
                        <!-- Ny Rullista: Säsong för Målvakter/Domare -->
                        <select id="gkref-season" onchange="window.gkref_season=this.value; renderGkRef()" class="w-full sm:w-48 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium text-slate-700 bg-slate-50">
                            <option value="ALL">Alla säsonger (Totalt)</option>
                            <!-- Fylls på dynamiskt av JavaScript -->
                        </select>
                        
                        <!-- Dynamiskt Sökfält -->
                        <div class="relative w-full">
                            <input type="text" id="gkref-search" onkeyup="renderGkRef()" placeholder="Sök namn, klubb eller ort (räknar om statistiken!)..." class="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                            <span class="absolute left-3 top-2.5 text-slate-400">🔍</span>
                        </div>
                    </div>
                </div>

                <!-- --- NY KOD: GHOST SWITCH ([Spöksaken] Slimmad och högerjusterad) --- -->
                <div class="flex justify-end mb-4 mt-2">
                    <label class="flex items-center gap-2 text-xs font-medium text-slate-600 hover:text-slate-900 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-md cursor-pointer transition-colors shadow-sm">
                        <input type="checkbox" id="toggle-annulled" onchange="toggleAnnulledMatches()" class="rounded border-amber-300 text-amber-600 focus:ring-amber-500 w-3.5 h-3.5 mt-0.5">
                        <span>Inkludera annullerade matcher (ex. MFF 1933) i den individuella statistiken</span>
                    </label>
                </div>
                <!-- ---------------------------------------- -->

                <!-- Tabell -->
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="max-h-[70vh] overflow-y-auto custom-scroll">
                        <table class="w-full text-sm text-left">
                            <thead id="gkref-head" class="bg-slate-800 text-slate-200 sticky top-0 z-10"></thead>
                            <tbody id="gkref-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- MODAL FÖR SVIT-MATCHER -->
        <div id="streak-modal" class="hidden fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
                <div class="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-lg">
                    <h3 id="modal-title" class="text-lg font-bold text-slate-800"></h3>
                    <button onclick="closeStreakModal()" class="text-slate-500 hover:text-slate-800 p-1"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
                <div class="p-0 overflow-y-auto custom-scroll flex-1">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead class="bg-slate-100 sticky top-0 shadow-sm border-b border-slate-200">
                            <tr><th class="p-3">Säsong</th><th class="p-3">Omg.</th><th class="p-3">Datum</th><th class="p-3 text-right">Hemmalag</th><th class="p-3 text-center">Resultat</th><th class="p-3">Bortalag</th></tr>
                        </thead>
                        <tbody id="modal-tbody" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- FLIK 12: Mästarbältet -->
<section id="tab-belt" class="tab-content hidden">
    <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">

    <!-- UNDERMENY FÖR REGELVERK -->
            <div class="flex gap-2 mb-8 bg-slate-100 p-2 rounded-lg inline-flex overflow-x-auto w-full md:w-auto">
                <button onclick="renderBeltView('STRICT')" id="btn-belt-strict" class="belt-tab-btn px-4 py-2 rounded-md text-sm font-bold bg-white shadow-sm text-blue-700 transition-all">Original (Dvala)</button>
                <button onclick="renderBeltView('VACANT_IMMEDIATE')" id="btn-belt-vacant_immediate" class="belt-tab-btn px-4 py-2 rounded-md text-sm font-bold text-slate-500 hover:text-slate-800 transition-all">Direkt Vakant</button>
                <button onclick="renderBeltView('TIME_LIMIT')" id="btn-belt-time_limit" class="belt-tab-btn px-4 py-2 rounded-md text-sm font-bold text-slate-500 hover:text-slate-800 transition-all">5-årsgränsen</button>
            </div>
        
        <!-- INTRO & NUVARANDE MÄSTARE -->
        <div class="mb-8">
            <div class="flex items-center gap-3 mb-2">
                <h2 class="text-2xl font-black text-slate-800">🥊 Inofficiella Mästarbältet</h2>
                <button onclick="document.getElementById('ufwc-info-modal').classList.remove('hidden')" class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 font-bold text-xs flex items-center justify-center hover:bg-blue-200 hover:text-blue-700 transition-colors shadow-sm" title="Läs om reglerna">i</button>
            </div>
            <p class="text-sm text-slate-600 mb-6">
                Här spåras ett inofficiellt "mästarbälte" (UFWC-logik) som vandrar från lag till lag. Den som besegrar mästaren i en match tar över bältet. Startade vid Allsvenskans begynnelse den 3 augusti 1924.
            </p>
            
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center max-w-md mx-auto shadow-sm">
                <div class="text-xs font-bold text-yellow-700 uppercase tracking-widest mb-1">Nuvarande Mästare</div>
                <div id="belt-current-champ" class="text-3xl font-black text-slate-900 mb-2">Laddar...</div>
                <div id="belt-current-defenses" class="text-sm font-semibold text-yellow-800"></div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- VÄNSTER SPALT: TITELNS VÄG (Historik) -->
            <div class="lg:col-span-2 border border-slate-200 rounded-lg overflow-hidden bg-white flex flex-col h-[600px]">
                <div class="bg-slate-50 px-4 py-3 border-b border-slate-200">
                    <h3 class="font-bold text-slate-800">Titelns väg genom historien</h3>
                </div>
                <div class="p-0 overflow-y-auto flex-1">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead class="bg-white text-slate-500 font-medium sticky top-0 shadow-sm z-10 border-b border-slate-200">
                            <tr>
                                <th class="p-3">Datum</th>
                                <th class="p-3">Omgång (Resultat)</th>
                                <th class="p-3">Lag</th>
                                <th class="p-3 text-center">Titelmatcher</th>
                            </tr>
                        </thead>
                        <tbody id="belt-history-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>

            <!-- HÖGER SPALT: TOPPLISTOR -->
            <div class="flex flex-col gap-6">
                
                <!-- Flest Titelmatcher -->
                <div class="border border-slate-200 rounded-lg overflow-hidden bg-white">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200">
                        <h3 class="font-bold text-slate-800">Flest titelmatcher (Totalt)</h3>
                    </div>
                    <div class="p-4" id="belt-top-total"></div>
                </div>

                <!-- Längsta svit -->
                <div class="border border-slate-200 rounded-lg overflow-hidden bg-white">
                    <div class="bg-slate-50 px-4 py-3 border-b border-slate-200">
                        <h3 class="font-bold text-slate-800">Längsta oavbrutna försvarssvit</h3>
                    </div>
                    <div class="p-4" id="belt-top-streak"></div>
                </div>

            </div>
        </div>
    </div>
    <!-- UFWC INFO MODAL -->
<div id="ufwc-info-modal" class="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 hidden backdrop-blur-sm transition-all">
    <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 m-4 relative max-h-[90vh] overflow-y-auto border border-slate-200">
        <!-- Stäng-knapp -->
        <button onclick="document.getElementById('ufwc-info-modal').classList.add('hidden')" class="absolute top-4 right-4 text-slate-400 hover:text-slate-700 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
        
        <h3 class="text-xl font-black text-slate-800 mb-4 flex items-center gap-2">🥊 Vad är Mästarbältet?</h3>
        
        <div class="text-sm text-slate-600 space-y-4">
            <p><strong>UFWC-logik (Unofficial Football World Championships)</strong> innebär att en mästartitel försvaras match för match, precis som i boxning. Den som besegrar den regerande mästaren tar över bältet. Vid oavgjort behåller mästaren titeln.</p>
            <p>För Allsvenskan innebär det att det första mästarbältet "delades ut" till IK Sleipner den 3 augusti 1924. Detta då deras segermatch borta mot IFK Eskilstina startade 13:00. Övriga fem matcher började klockan 13:30.</p>
            <p>I en nationell serie uppstår ett problem när laget som håller bältet degraderas. För att lösa detta kan historien betraktas genom tre olika "tidslinjer":</p>
            
            <ul class="space-y-3 mt-4">
                <li class="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <strong class="text-blue-700 block mb-1">1. Original (Dvala)</strong>
                    Bältet följer strikt med det nedflyttade laget ner i seriesystemet. Titeln är osynlig (i dvala) tills laget eventuellt tar sig tillbaka till Allsvenskan.
                </li>
                <li class="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <strong class="text-slate-700 block mb-1">2. Direkt Vakant</strong>
                    Bältet är exklusivt för Allsvenskan. Om ett lag åker ur lämnas bältet tillbaka omedelbart. Det delas ut till vinnaren av den först spelade matchen i nästa säsongs allsvenska premiär. Om flera matcher spelas samtidigt delas det ut till vinnaren i den match som har störst segermarginal.
                </li>
                <li class="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <strong class="text-slate-700 block mb-1">3. 5-årsgränsen</strong>
                    En hybridlösning. Bältet följer med ner i dvala, men om laget misslyckas med att återvända till Allsvenskan inom 5 säsonger, förlorar de rätten till det och bältet förklaras vakant.
                </li>
            </ul>
        </div>
    </div>
</div>
</section>
    </main>

    <script>
        const MATCH_DATA = %%MATCH_DATA_JSON%%;
        const TEAMS = %%TEAMS_JSON%%;
        const SEASONS = %%SEASONS_JSON%%;
        const SEASON_INFO = %%SEASON_INFO_JSON%%; 
        const DECADES = %%DECADES_JSON%%;
        const CUSTOM_EPOCHS = %%CUSTOM_EPOCHS_JSON%%;
        const TEAM_MERITS = %%TEAM_MERITS_JSON%%; 
        
        // --- NYA VARIABLER FÖR MODALER & SKYTTEKUNGAR ---
        const GK_INFO = %%GK_INFO_JSON%%;
        const REF_INFO = %%REF_INFO_JSON%%;
        const TOP_SCORERS = %%TOP_SCORERS_JSON%%;
        const FIRST_SCORERS = %%FIRST_SCORERS_JSON%%; // <-- NY: Fångar upp premiärmålskyttarna från Python!
        const MASTER_BELT_DATA = %%MASTER_BELT_JSON%%;

        // --- GLOBAL FLAGGA FÖR "SPÖK-MATCHER" (Soft Delete) ---
        window.forceIncludeAnnulled = false; // <-- NY: Kontrollerar om MFF 1933 ska visas

        // Funktionen som triggas när du klickar på checkboxen
        function toggleAnnulledMatches() {
            window.forceIncludeAnnulled = document.getElementById('toggle-annulled').checked;
    
            // Kalla på funktionen som ritar om din domar/målvakts-lista!
            // OBS: Byt ut namnet nedan till den funktion som du använder för att uppdatera modalen.
            // T.ex. updateGkRefView() eller vad den nu heter i ditt skript.
            if (typeof uppdateraDashboard === "function") {
                uppdateraDashboard(); 
            }
        }

        let currentOverviewData = []; let currentOverviewSort = { col: 'played', asc: false }; let currentStreakMatches = {}; 
        let globalAllStreaks = []; 
        let ALL_TIME_TABLE = []; let TEAM_RANKS = {}; let TEAM_ALLTIME_PPG = {}; let analysisChartInstance = null; let globalAnalysisData = {}; 
        let analysisMode = 'chart'; let globalSeasonRanks = {}; let globalSeasonTeams = []; let trendChartInstance = null;
        let currentStrengthData = []; let currentStrengthSort = { col: 'index', asc: false };

        function formatDate(val, fallbackYear) {
            if (val === null || val === "" || val === undefined) return fallbackYear || '-';
            if (typeof val === 'number') {
                if (Math.abs(val) > 0 && Math.abs(val) < 10000) return String(val); 
                return new Date(val).toISOString().split('T')[0]; 
            }
            let s = String(val); return s.length > 10 ? s.substring(0, 10) : s;
        }

        function extractYear(dateVal, fallback) {
            if (dateVal === null || dateVal === "" || dateVal === undefined) return fallback || '-';
            if (typeof dateVal === 'number') {
                if (Math.abs(dateVal) > 10000) return new Date(dateVal).getFullYear().toString();
                return String(dateVal);
            }
            const s = String(dateVal); return s.length >= 4 ? s.substring(0, 4) : fallback || '-';
        }

        function getSeasonName(sasId) { return (SEASON_INFO[sasId] && SEASON_INFO[sasId].name) ? SEASON_INFO[sasId].name : String(sasId); }

        function getNoteString(team1, team2, notText, dateStr) {
            if (!notText) return null;
            let nTxt = String(notText).toUpperCase();
            let noteFound = null;

            if (nTxt.includes("EJ KVALIFICERAD SPELARE; V")) noteFound = "Ej kvalificerad spelare, dömt till hemmaseger.";
            else if (nTxt.includes("EJ KVALIFICERAD SPELARE; F")) noteFound = "Ej kvalificerad spelare, dömt till bortaseger.";
            else if (nTxt.includes("W.O; H")) noteFound = "W.O. till hemmalaget.";
            else if (nTxt.includes("W.O; B")) noteFound = "W.O. till bortalaget.";
            else if (nTxt.includes("AVBRUTEN; V")) noteFound = "Avbruten, dömt till hemmaseger.";
            else if (nTxt.includes("AVBRUTEN; F")) noteFound = "Avbruten, dömt till bortaseger.";
            else if (nTxt.includes("AVBRUTEN; O")) noteFound = "Avbruten, dömt till en poäng vardera.";
            else if (nTxt.includes("AVBRUTEN")) noteFound = "Avbruten match.";
            
            if (noteFound) {
                return dateStr ? `${dateStr} (${team1}-${team2}): ${noteFound}` : `(${team1}-${team2}): ${noteFound}`;
            }
            return null;
        }

        function updatePhaseDropdown() {
            const season = document.getElementById('table-season').value;
            const phaseSelect = document.getElementById('table-phase');
            if (!phaseSelect) return;
            let isM = ["67", "68", "1991", "1992"].includes(String(season));
            Array.from(phaseSelect.options).forEach(opt => {
                if(opt.value !== "ALL") {
                    opt.disabled = !isM;
                    if(!isM) opt.classList.add('text-slate-300'); else opt.classList.remove('text-slate-300');
                }
            });
            if(!isM && phaseSelect.value !== "ALL") phaseSelect.value = "ALL";
        }

        document.addEventListener('DOMContentLoaded', () => {
            initAllTimeTable(); populateAllDropdowns();
            if(ALL_TIME_TABLE.length >= 2) {
                document.getElementById('h2h-team-a').value = ALL_TIME_TABLE[0].team;
                updateOpponentDropdown('h2h-team-a', 'h2h-team-b');
                
                let bOpts = Array.from(document.getElementById('h2h-team-b').options);
                let validB = bOpts.filter(o => !o.disabled && o.value !== "").map(o => o.value);
                if (validB.includes(ALL_TIME_TABLE[1].team)) {
                    document.getElementById('h2h-team-b').value = ALL_TIME_TABLE[1].team;
                } else if (validB.length > 0) {
                    document.getElementById('h2h-team-b').value = validB[0];
                }
            }
            updateRankDisplays();
            
            calculateH2H();
            
            document.getElementById('h2h-team-a').addEventListener('change', () => { updateOpponentDropdown('h2h-team-a', 'h2h-team-b'); updateRankDisplays(); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
            document.getElementById('h2h-team-b').addEventListener('change', () => { updateOpponentDropdown('h2h-team-b', 'h2h-team-a'); updateRankDisplays(); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
            document.getElementById('search-season').addEventListener('change', () => { updateSearchTeamDropdown(); });
            document.getElementById('table-season').addEventListener('change', (e) => { 
                const sas = e.target.value; 
                if (SEASON_INFO[sas] && SEASON_INFO[sas].pts) document.getElementById('table-points').value = SEASON_INFO[sas].pts; 
                updatePhaseDropdown();
            });
            if (SEASONS.length > 0) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
            
            updatePhaseDropdown();
            
            renderRecords(); 
            calculateStreaks(); 
        });

        function initAllTimeTable() {
            let table = {};
            MATCH_DATA.forEach(m => {
                // --- NY DÖRRVAKT: Mjuk radering för Maratontabellen ---
                if (m.Annullerad) return;

                [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, seasons: new Set() }; });
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return;
                    hm = 0; bm = 0; 
                } 
                table[m.Hemmalag].pld++; table[m.Bortalag].pld++;
                table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm;
                table[m.Hemmalag].ga += bm; table[m.Bortalag].ga += hm;
                
                if (isWOH) { table[m.Hemmalag].w++; table[m.Bortalag].l++; table[m.Hemmalag].pts += 3; }
                else if (isWOB) { table[m.Bortalag].w++; table[m.Hemmalag].l++; table[m.Bortalag].pts += 3; }
                else if (hm > bm) { table[m.Hemmalag].w++; table[m.Bortalag].l++; table[m.Hemmalag].pts += 3; }
                else if (hm < bm) { table[m.Bortalag].w++; table[m.Hemmalag].l++; table[m.Bortalag].pts += 3; }
                else { table[m.Hemmalag].d++; table[m.Bortalag].d++; table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                table[m.Hemmalag].seasons.add(String(m.Säs)); table[m.Bortalag].seasons.add(String(m.Säs));
            });
            
            Object.values(table).forEach(t => {
                let totalDeduction = 0;
                t.seasons.forEach(sas => {
                    let mInfo = TEAM_MERITS[sas] && TEAM_MERITS[sas][t.team];
                    if (mInfo && mInfo.start_pts < 0) {
                        totalDeduction += mInfo.start_pts;
                    }
                });
                t.pts += totalDeduction;
            });

            let arr = Object.values(table);
            arr.forEach(r => { r.gd = r.gf - r.ga; TEAM_ALLTIME_PPG[r.team] = r.pts / r.pld; });
            arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
            ALL_TIME_TABLE = arr;
            arr.forEach((r, i) => { TEAM_RANKS[r.team] = i + 1; });
        }

        function updateRankDisplays() {
            const teamA = document.getElementById('h2h-team-a').value; const teamB = document.getElementById('h2h-team-b').value;
            const elA = document.getElementById('rank-team-a'); const elB = document.getElementById('rank-team-b');
            if(teamA && TEAM_RANKS[teamA]) elA.innerText = `(Maratonplacering: ${TEAM_RANKS[teamA]})`; else elA.innerText = '';
            if(teamB && TEAM_RANKS[teamB]) elB.innerText = `(Maratonplacering: ${TEAM_RANKS[teamB]})`; else elB.innerText = '';
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('btn-' + tabId).classList.add('active');

            // NYTT: Rita ut resultat-analysen när fliken aktiveras
            if (tabId === 'results') {
                if (typeof renderResultatAnalys === 'function') renderResultatAnalys();
            }
            // LÄGG TILL DETTA:
            if (tabId === 'gkref') {
                if (typeof renderGkRef === 'function') renderGkRef();
            }
            // LÄGG TILL DENNA FÖR MÄSTARBÄLTET:
            if (tabId === 'belt') {
                if (typeof renderMasterBelt === 'function') renderMasterBelt();
            }
            if (tabId === 'tables') { // Byt ut 'tables' mot det ID din tabell-flik har
                // Byt ut namnet nedan till vad din bygg-knapp faktiskt anropar!
                if (typeof buildTable === 'function') buildTable(); 
            }
            if (tabId === 'profiles') { // Byt ut 'profiles' mot rätt ID för din profil-flik
                // Kolla vad din bygg-knapp för profiler anropar (t.ex. renderProfiles() eller buildProfiles())
                if (typeof renderProfiles === 'function') renderProfiles(); 
            }
        }

        function populateAllDropdowns() {
            let teamOpts = ''; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
            document.getElementById('h2h-team-a').innerHTML = '<option value="">-- Välj ett lag --</option>' + teamOpts;
            document.getElementById('h2h-team-b').innerHTML = '<option value="">-- Välj ett lag --</option>' + teamOpts;
            document.getElementById('search-team').innerHTML = '<option value="">-- Alla lag --</option>' + teamOpts;
            document.getElementById('records-team').innerHTML = '<option value="">-- Totalt i Allsvenskan --</option>' + teamOpts;
            document.getElementById('streaks-team').innerHTML = '<option value="ALL">-- Alla Lag (Historiska Rekord) --</option>' + teamOpts;

            let seasonOpts = '<option value="">-- Alla säsonger --</option>';
            [...SEASONS].reverse().forEach(s => { if(s) seasonOpts += `<option value="${s}">${getSeasonName(s)}</option>`; });
            document.getElementById('search-season').innerHTML = seasonOpts;
            document.getElementById('table-season').innerHTML = seasonOpts.replace('<option value="">-- Alla säsonger --</option>', '<option value="">-- Välj säsong --</option>');
            document.getElementById('profiles-season').innerHTML = seasonOpts.replace('<option value="">-- Alla säsonger --</option>', '<option value="">-- Välj säsong --</option>');
            
            if (SEASONS.length > 0) {
                let latestSeason = [...SEASONS].reverse()[0]; // Plockar automatiskt senaste året
                
                // 1. Sätt default för H2H/Sök
                document.getElementById('search-season').value = latestSeason;
                
                // 2. Sätt default för Serietabellen
                let tableSeasonEl = document.getElementById('table-season');
                if (tableSeasonEl) {
                    tableSeasonEl.value = latestSeason;
                    // KRITISKT MAGISKT TRICK: Vi säger åt webbläsaren att låtsas som att användaren 
                    // precis klickade på rullistan. Då uppdateras poäng (2 eller 3) och Fas-menyn korrekt!
                    tableSeasonEl.dispatchEvent(new Event('change')); 
                }
                // 3. NYTT: Sätt default för Säsongens Profiler
                let profilesSeasonEl = document.getElementById('profiles-season');
                if (profilesSeasonEl) {
                    profilesSeasonEl.value = latestSeason;
                    // Samma magiska trick här: simulerar ett klick så att profillistan laddas direkt!
                    profilesSeasonEl.dispatchEvent(new Event('change')); 
                }
                // --- NYTT: Fyll på och sätt default för Målvakter & Domare ---
                let gkrefSeasonEl = document.getElementById('gkref-season');
                if (gkrefSeasonEl) {
                    let gkSeasonOpts = '<option value="ALL">Alla säsonger (Totalt)</option>';
                    [...SEASONS].reverse().forEach(s => { 
                        if(s) gkSeasonOpts += `<option value="${s}">${typeof getSeasonName === 'function' ? getSeasonName(s) : s}</option>`; 
                    });
                    gkrefSeasonEl.innerHTML = gkSeasonOpts;
                    gkrefSeasonEl.value = latestSeason; // Väljer senaste året direkt!
                }
            }
            updateSearchTeamDropdown();
            
            let epokOpts = '<option value="ALL">Totalt (Alla säsonger)</option>';
            let analysisOpts = '<option value="">-- Välj säsong/epok --</option><option value="ALL_SEASONS">-- Alla säsonger --</option>';
            
            if (Object.keys(CUSTOM_EPOCHS).length > 0) {
                let block = '<optgroup label="Egna Epoker">';
                Object.keys(CUSTOM_EPOCHS).forEach(d => { block += `<option value="EPOCH_CUSTOM_${d}">${d}</option>`; });
                block += '</optgroup>'; epokOpts += block; analysisOpts += block;
            }
            if (Object.keys(DECADES).length > 0) {
                let block = '<optgroup label="Årtionden">';
                Object.keys(DECADES).reverse().forEach(d => { block += `<option value="EPOCH_DECADE_${d}">${d}</option>`; });
                block += '</optgroup>'; epokOpts += block; analysisOpts += block;
            }
            analysisOpts += '<optgroup label="Enskilda Säsonger">';
            [...SEASONS].reverse().forEach(s => { if(s) analysisOpts += `<option value="${s}">${getSeasonName(s)}</option>`; });
            analysisOpts += '</optgroup>';
            document.getElementById('table-epoch').innerHTML = epokOpts;
            document.getElementById('analysis-season').innerHTML = analysisOpts;
        }

        function updateSearchTeamDropdown() {
            const season = document.getElementById('search-season').value; const targetSelect = document.getElementById('search-team');
            const currentTargetValue = targetSelect.value;
            if (!season) {
                let teamOpts = '<option value="">-- Alla lag --</option>'; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
                targetSelect.innerHTML = teamOpts; targetSelect.value = currentTargetValue; return;
            }
            const validTeams = new Set();
            MATCH_DATA.forEach(m => { if (String(m.Säs) === String(season)) { validTeams.add(m.Hemmalag); validTeams.add(m.Bortalag); } });
            const activeTeams = TEAMS.filter(t => validTeams.has(t)); const inactiveTeams = TEAMS.filter(t => !validTeams.has(t));
            let html = '<option value="">-- Alla lag --</option>';
            if (activeTeams.length > 0) { html += '<optgroup label="Spelade i Allsvenskan denna säsong">'; activeTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            if (inactiveTeams.length > 0) { html += '<optgroup label="Spelade ej i Allsvenskan" disabled>'; inactiveTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            targetSelect.innerHTML = html; targetSelect.value = validTeams.has(currentTargetValue) ? currentTargetValue : "";
        }

        function updateOpponentDropdown(sourceId, targetId) {
            const sourceTeam = document.getElementById(sourceId).value; const targetSelect = document.getElementById(targetId);
            const currentTargetValue = targetSelect.value;
            if (!sourceTeam) {
                let options = '<option value="">-- Välj ett lag --</option>'; TEAMS.forEach(team => { options += `<option value="${team}">${team}</option>`; });
                targetSelect.innerHTML = options; targetSelect.value = currentTargetValue; return;
            }
            const opponents = new Set();
            MATCH_DATA.forEach(m => { if (m.Hemmalag === sourceTeam) opponents.add(m.Bortalag); if (m.Bortalag === sourceTeam) opponents.add(m.Hemmalag); });
            const validOpponents = TEAMS.filter(t => opponents.has(t)); const invalidOpponents = TEAMS.filter(t => !opponents.has(t) && t !== sourceTeam);
            let html = '<option value="">-- Välj motståndare --</option>';
            if (validOpponents.length > 0) { html += '<optgroup label="Tidigare motståndare">'; validOpponents.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            if (invalidOpponents.length > 0) { html += '<optgroup label="Har ej mött" disabled>'; invalidOpponents.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            targetSelect.innerHTML = html; targetSelect.value = validOpponents.includes(currentTargetValue) ? currentTargetValue : "";
        }

        // --- H2H ---
        function calculateH2H() {
            const teamA = document.getElementById('h2h-team-a').value; const teamB = document.getElementById('h2h-team-b').value;
            const context = document.querySelector('input[name="h2h-context"]:checked').value;
            if (!teamA || !teamB || teamA === teamB) return;
            document.getElementById('h2h-overview').classList.add('hidden');
            
            // --- NYTT: Läs av Ghost Switch ---
            const includeAnnulled = document.getElementById('toggle-annulled-h2h')?.checked || false;

            let h2hMatches = MATCH_DATA.filter(m => (m.Hemmalag === teamA && m.Bortalag === teamB) || (m.Hemmalag === teamB && m.Bortalag === teamA));
            if (context === 'home') h2hMatches = h2hMatches.filter(m => m.Hemmalag === teamA);
            if (context === 'away') h2hMatches = h2hMatches.filter(m => m.Bortalag === teamA);
            
            // --- NYTT: Filtrera bort annullerade matcher om switchen är av ---
            if (!includeAnnulled) {
                h2hMatches = h2hMatches.filter(m => !m.Annullerad);
            }

            h2hMatches.sort((a, b) => {
                let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime();
                let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
                if(d1!==d2) return d1-d2;
                return a.Match_ID - b.Match_ID;
            });
            
            let winsA = 0, draws = 0, winsB = 0, tableHTML = '';
            let matchNotes = new Set();
            
            h2hMatches.forEach(match => {
                const isHomeA = match.Hemmalag === teamA;
                let hm = parseInt(match.HM); let bm = parseInt(match.BM);
                let notText = String(match.NOT).toUpperCase();
                
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                let origH = match.Hemmalag_Org || match.Hemmalag;
                let origB = match.Bortalag_Org || match.Bortalag;
                let displayDate = formatDate(match.Matchdatum, match.År);
                let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                if (noteStr) matchNotes.add(noteStr);

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return; hm = 0; bm = 0;
                }
                const matchGoalsA = isHomeA ? hm : bm; const matchGoalsB = isHomeA ? bm : hm;
                
                if (isWOH) { if (isHomeA) winsA++; else winsB++; }
                else if (isWOB) { if (!isHomeA) winsA++; else winsB++; }
                else if (matchGoalsA > matchGoalsB) winsA++; else if (matchGoalsA < matchGoalsB) winsB++; else draws++;

                const homeBold = hm > bm ? 'font-bold text-blue-600' : (bm > hm ? 'text-rose-600' : 'text-slate-900');
                const awayBold = bm > hm ? 'font-bold text-blue-600' : (hm > bm ? 'text-rose-600' : 'text-slate-900');
                tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${getSeasonName(match.Säs)}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeBold}">${origH}</td><td class="px-4 py-2 text-center font-mono bg-slate-50 border-x border-slate-100 font-semibold">${hm} - ${bm}</td><td class="px-4 py-2 ${awayBold}">${origB}</td><td class="px-4 py-2 text-right text-slate-500">${match.Publik ? match.Publik.toLocaleString('sv-SE') : '-'}</td></tr>`;
            });
            document.getElementById('h2h-table-body').innerHTML = tableHTML || '<tr><td colspan="6" class="text-center py-6 text-slate-500">Inga möten hittades.</td></tr>';
            
            let nHtml = "";
            matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
            const notesEl = document.getElementById('h2h-notes');
            if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }

            document.getElementById('h2h-summary-cards').innerHTML = `<div class="bg-blue-50 p-3 rounded-lg border border-blue-100 text-center"><div class="text-xs text-blue-600 font-medium uppercase tracking-wider mb-1">Möten</div><div class="text-2xl font-bold text-blue-900">${h2hMatches.length}</div></div><div class="bg-emerald-50 p-3 rounded-lg border border-emerald-100 text-center"><div class="text-xs text-emerald-600 font-medium uppercase tracking-wider mb-1">Vinster ${teamA}</div><div class="text-2xl font-bold text-emerald-900">${winsA}</div></div><div class="bg-slate-100 p-3 rounded-lg border border-slate-200 text-center"><div class="text-xs text-slate-600 font-medium uppercase tracking-wider mb-1">Oavgjorda</div><div class="text-2xl font-bold text-slate-800">${draws}</div></div><div class="bg-rose-50 p-3 rounded-lg border border-rose-100 text-center"><div class="text-xs text-rose-600 font-medium uppercase tracking-wider mb-1">Vinster ${teamB}</div><div class="text-2xl font-bold text-rose-900">${winsB}</div></div>`;
            document.getElementById('h2h-results').classList.remove('hidden');
        }

        function renderH2HOverview() {
            const teamA = document.getElementById('h2h-team-a').value; const context = document.querySelector('input[name="h2h-context"]:checked').value;
            if (!teamA) { alert("Välj Lag A först."); return; }
            document.getElementById('h2h-results').classList.add('hidden');
            
            // --- NYTT: Läs av Ghost Switch ---
            const includeAnnulled = document.getElementById('toggle-annulled-h2h')?.checked || false;

            let oppStats = {}; let matches = MATCH_DATA.filter(m => m.Hemmalag === teamA || m.Bortalag === teamA);
            if (context === 'home') matches = matches.filter(m => m.Hemmalag === teamA);
            if (context === 'away') matches = matches.filter(m => m.Bortalag === teamA);
            
            matches.forEach(m => {
                // --- NYTT: Dörrvakten kopplad till switchen ---
                if (!includeAnnulled && m.Annullerad) return;
                
                const isHome = m.Hemmalag === teamA; const opp = isHome ? m.Bortalag : m.Hemmalag;
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                if(isNaN(hm) || isNaN(bm)) { if (!(isWOH||isWOB)) return; hm=0; bm=0; }
                const gf = isHome ? hm : bm; const ga = isHome ? bm : hm;
                if (!oppStats[opp]) oppStats[opp] = { team: opp, played: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, gd: 0 };
                oppStats[opp].played++; oppStats[opp].gf += gf; oppStats[opp].ga += ga;
                
                if (isWOH) { if (isHome) oppStats[opp].w++; else oppStats[opp].l++; }
                else if (isWOB) { if (!isHome) oppStats[opp].w++; else oppStats[opp].l++; }
                else if (gf > ga) oppStats[opp].w++; else if (gf < ga) oppStats[opp].l++; else oppStats[opp].d++;
                
                oppStats[opp].gd = oppStats[opp].gf - oppStats[opp].ga;
            });
            currentOverviewData = Object.values(oppStats);
            document.getElementById('overview-title').innerText = `Sammanställning: ${teamA} ${context === 'home' ? '(Endast Hemma)' : context === 'away' ? '(Endast Borta)' : '(Alla Möten)'}`;
            sortOverview('played', true); document.getElementById('h2h-overview').classList.remove('hidden');
        }

        function sortOverview(col, forceDesc = false) {
            if (forceDesc) { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
            else if (currentOverviewSort.col === col) { currentOverviewSort.asc = !currentOverviewSort.asc; }
            else { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
            currentOverviewData.sort((a, b) => {
                let valA = a[col], valB = b[col];
                if (typeof valA === 'string') return currentOverviewSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                return currentOverviewSort.asc ? valA - valB : valB - valA;
            });
            let html = currentOverviewData.map(r => `<tr class="hover:bg-slate-50"><td class="px-4 py-2 font-medium">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100">${r.played}</td><td class="px-4 py-2 text-center text-emerald-600 font-semibold">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf}</td><td class="px-4 py-2 text-center">${r.ga}</td><td class="px-4 py-2 text-center font-bold ${r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : ''}">${r.gd > 0 ? '+'+r.gd : r.gd}</td></tr>`).join('');
            document.getElementById('h2h-overview-body').innerHTML = html;
        }

        function clearSearch() {
            document.getElementById('search-round').value = ""; document.getElementById('search-hm').value = ""; document.getElementById('search-bm').value = "";
            if (SEASONS.length > 0) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
            updateSearchTeamDropdown(); document.getElementById('search-team').value = ""; performSearch();
        }

        function performSearch() {
            const season = document.getElementById('search-season').value; const roundRaw = document.getElementById('search-round').value.trim().toUpperCase();
            const team = document.getElementById('search-team').value; const searchGoalsTeam = document.getElementById('search-hm').value; const searchGoalsOpp = document.getElementById('search-bm').value;
            
            // --- NYTT: Läs av Ghost Switch för Matchsök ---
            const includeAnnulled = document.getElementById('toggle-annulled-search')?.checked || false;

            let filtered = MATCH_DATA;
            if (season) filtered = filtered.filter(m => String(m.Säs) === String(season));
            if (roundRaw !== "") filtered = filtered.filter(m => String(m.Omgång).trim().toUpperCase() === roundRaw);
            filtered = filtered.filter(m => {
                // --- NYTT: Dölj annullerade om switchen är av ---
                if (!includeAnnulled && m.Annullerad) return false;

                if (team && m.Hemmalag !== team && m.Bortalag !== team) return false;
                let mHm = parseInt(m.HM); let mBm = parseInt(m.BM);
                if (isNaN(mHm) || isNaN(mBm)) return true; 
                if (team) {
                    let teamGoals = (m.Hemmalag === team) ? mHm : mBm; let oppGoals = (m.Hemmalag === team) ? mBm : mHm;
                    if (searchGoalsTeam !== "" && teamGoals !== parseInt(searchGoalsTeam)) return false;
                    if (searchGoalsOpp !== "" && oppGoals !== parseInt(searchGoalsOpp)) return false;
                } else {
                    if (searchGoalsTeam !== "" && mHm !== parseInt(searchGoalsTeam)) return false;
                    if (searchGoalsOpp !== "" && mBm !== parseInt(searchGoalsOpp)) return false;
                }
                return true;
            });
            
            // --- NYTT: Tvinga kronologisk sortering istället för Match_ID ---
            filtered.sort((a, b) => {
                let dateA = formatDate(a.Matchdatum, a.År) || "";
                let dateB = formatDate(b.Matchdatum, b.År) || "";
                
                // Fallback om datumet saknas (bör inte hända, men för säkerhets skull)
                if (dateA === dateB) {
                    return b.Match_ID - a.Match_ID; // Fallback till ID om datumen är identiska
                }
                
                // Sorterar i fallande ordning (nyaste matchen överst)
                return dateB.localeCompare(dateA); 
            });
            
            let tableHTML = ''; let totalPublik = 0, matcherMedPublik = 0;
            let matchNotes = new Set();

            filtered.forEach(match => {
                let displayDate = formatDate(match.Matchdatum, match.År); let htText = (match.HMF !== "" && match.BMF !== "") ? `<span class="text-[10px] text-slate-400 block">(${match.HMF}-${match.BMF})</span>` : "";
                if (match.Publik !== "") { totalPublik += match.Publik; matcherMedPublik++; }

                let hm = parseInt(match.HM); let bm = parseInt(match.BM);
                let notText = String(match.NOT).toUpperCase();
                
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                let origH = match.Hemmalag_Org || match.Hemmalag;
                let origB = match.Bortalag_Org || match.Bortalag;
                let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                if (noteStr) matchNotes.add(noteStr);

                let homeWon = hm > bm; let awayWon = bm > hm;
                if (isWOH) { homeWon = true; awayWon = false; } else if (isWOB) { awayWon = true; homeWon = false; }

                let homeColor = homeWon ? 'text-blue-600' : (awayWon ? 'text-rose-600' : 'text-slate-700');
                let awayColor = awayWon ? 'text-blue-600' : (homeWon ? 'text-rose-600' : 'text-slate-700');
                let homeBold = ''; let awayBold = '';
                
                if (team) {
                    if (match.Hemmalag === team) homeBold = 'font-bold';
                    if (match.Bortalag === team) awayBold = 'font-bold';
                } else {
                    if (homeWon) homeBold = 'font-bold';
                    if (awayWon) awayBold = 'font-bold';
                }

                let homeClass = `${homeColor} ${homeBold}`;
                let awayClass = `${awayColor} ${awayBold}`;

                tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${getSeasonName(match.Säs)}</td><td class="px-4 py-2 text-slate-500">${match.Omgång || '-'}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeClass}">${origH}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100"><span class="font-mono font-bold">${match.HM} - ${match.BM}</span>${htText}</td><td class="px-4 py-2 ${awayClass}">${origB}</td><td class="px-4 py-2 text-right text-slate-500">${match.Publik !== "" ? match.Publik.toLocaleString('sv-SE') : '-'}</td></tr>`;
            });
            
            document.getElementById('search-table-body').innerHTML = tableHTML || '<tr><td colspan="7" class="text-center py-6 text-slate-500">Inga matcher matchade sökningen.</td></tr>';
            
            let nHtml = "";
            matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
            const notesEl = document.getElementById('search-notes');
            if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }

            let snitt = matcherMedPublik > 0 ? Math.round(totalPublik / matcherMedPublik).toLocaleString('sv-SE') : 0;
            document.getElementById('search-summary-text').innerHTML = `Hittade <span class="font-bold text-blue-600">${filtered.length}</span> matcher. ${matcherMedPublik > 0 ? `Snitt: <span class="font-bold">${snitt}</span>` : ''}`;
            document.getElementById('search-results').classList.remove('hidden');
        }

        function renderRecords() {
            const team = document.getElementById('records-team').value; const suffix = team ? ` (${team})` : '';
            document.getElementById('rec-title-wins').innerText = team ? `Största segrar för ${team}` : 'Största segrarna totalt';
            document.getElementById('rec-title-losses').innerText = team ? `Största förluster för ${team}` : 'Största förlusterna totalt';
            let teamData = team ? MATCH_DATA.filter(m => m.Hemmalag === team || m.Bortalag === team) : MATCH_DATA;
            const buildRows = (matches, valueKeyFn, valueLabel = "") => {
                if (matches.length === 0) return `<tr><td colspan="5" class="py-4 text-center text-slate-500 italic">Inga rekord hittades.</td></tr>`;
                return matches.map(m => {
                    let htText = (m.HMF !== "" && m.BMF !== "") ? `(${m.HMF}-${m.BMF})` : '';
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;
                    let hClass = (team && m.Hemmalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                    let aClass = (team && m.Bortalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                    return `<tr class="border-b border-slate-100 hover:bg-slate-50"><td class="py-2 px-2 text-xs text-slate-500 w-12 font-medium">${extractYear(m.Matchdatum, m.År)}</td><td class="py-2 px-2 text-right ${hClass} truncate max-w-[100px]" title="${origH}">${origH}</td><td class="py-2 px-2 text-center bg-slate-50/50 w-16"><span class="font-mono font-bold text-sm block">${m.HM} - ${m.BM}</span><span class="text-[10px] text-slate-400 block -mt-1">${htText}</span></td><td class="py-2 px-2 ${aClass} truncate max-w-[100px]" title="${origB}">${origB}</td><td class="py-2 px-2 text-right font-semibold text-blue-600">${valueKeyFn(m)} ${valueLabel}</td></tr>`;
                }).join('');
            };
            let winsData = team ? teamData.filter(m => (m.Hemmalag === team && parseInt(m.HM) > parseInt(m.BM)) || (m.Bortalag === team && parseInt(m.BM) > parseInt(m.HM))) : MATCH_DATA;
            let biggestWins = [...winsData].sort((a, b) => Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM)) || Math.max(parseInt(b.HM), parseInt(b.BM)) - Math.max(parseInt(a.HM), parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-wins').innerHTML = buildRows(biggestWins, m => `+${Math.abs(parseInt(m.HM) - parseInt(m.BM))}`, 'mål');
            let lossesData = team ? teamData.filter(m => (m.Hemmalag === team && parseInt(m.HM) < parseInt(m.BM)) || (m.Bortalag === team && parseInt(m.BM) < parseInt(m.HM))) : MATCH_DATA;
            let biggestLosses = [...lossesData].sort((a, b) => Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM)) || Math.max(parseInt(b.HM), parseInt(b.BM)) - Math.max(parseInt(a.HM), parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-losses').innerHTML = buildRows(biggestLosses, m => `-${Math.abs(parseInt(m.HM) - parseInt(m.BM))}`, 'mål');
            let mostGoals = [...teamData].sort((a, b) => (parseInt(b.HM) + parseInt(b.BM)) - (parseInt(a.HM) + parseInt(a.BM)) || Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-goals').innerHTML = buildRows(mostGoals, m => (parseInt(m.HM) + parseInt(m.BM)), 'mål');
            let comebacksData = teamData.map(m => {
                if (m.HMF === "" || m.BMF === "") return null;
                let hmf = parseInt(m.HMF); let bmf = parseInt(m.BMF); let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                let overcome = 0, isComeback = false, winningTeam = null;
                if (hmf < bmf && hm > bm) { overcome = bmf - hmf; isComeback = true; winningTeam = m.Hemmalag; } 
                else if (bmf < hmf && bm > hm) { overcome = hmf - bmf; isComeback = true; winningTeam = m.Bortalag; }
                if (!isComeback || (team && winningTeam !== team)) return null; return {...m, overcome};
            }).filter(m => m !== null);
            let topComebacks = comebacksData.sort((a, b) => b.overcome - a.overcome || (parseInt(b.HM) + parseInt(b.BM)) - (parseInt(a.HM) + parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-comebacks').innerHTML = buildRows(topComebacks, m => `${m.overcome}`, 'mål');
            let validPublik = teamData.filter(m => typeof m.Publik === 'number');
            let highestAtt = [...validPublik].sort((a, b) => b.Publik - a.Publik).slice(0, 10);
            document.getElementById('rec-list-att-high').innerHTML = buildRows(highestAtt, m => m.Publik.toLocaleString('sv-SE'), '');
            let lowestAtt = [...validPublik].filter(m => m.Publik > 10).sort((a, b) => a.Publik - b.Publik).slice(0, 10);
            document.getElementById('rec-list-att-low').innerHTML = buildRows(lowestAtt, m => m.Publik.toLocaleString('sv-SE'), '');
        }

        // ==========================================
// VÄXLING MELLAN LAG- OCH SPELARREKORD
// ==========================================
function toggleRecordsView(view) {
    let matchCont = document.getElementById('records-match-container');
    let playCont = document.getElementById('records-players-container');
    let btnMatch = document.getElementById('btn-view-match');
    let btnPlay = document.getElementById('btn-view-players');

    let activeCls = "px-4 py-2 bg-white text-slate-800 shadow-sm rounded-md font-bold text-sm transition-all";
    let inactiveCls = "px-4 py-2 text-slate-500 hover:text-slate-700 rounded-md font-bold text-sm transition-all";

    if (view === 'players') {
        matchCont.classList.add('hidden');
        playCont.classList.remove('hidden');
        btnPlay.className = activeCls;
        btnMatch.className = inactiveCls;
        // Rendera bara om vi vill se datan (realtidsberäkning)
        renderPlayerToplists(); 
    } else {
        playCont.classList.add('hidden');
        matchCont.classList.remove('hidden');
        btnMatch.className = activeCls;
        btnPlay.className = inactiveCls;
    }
}

// ==========================================
// DATA-GRUVAN: BYGG SPELARSTATISTIKEN
// ==========================================
function renderPlayerToplists() {
    let tsPlayers = {}; let tsClubs = {}; let chronoTS = [];
    let psPlayers = {}; let dnPlayers = {}; let chronoDN = [];

    // --- NYTT: "Fotografiskt minne" för att stoppa dubbletter ---
    let processedTSSeasons = new Set();
    let processedDNSeasons = new Set();

    // --- 1. PROCESSA SKYTTEKUNGAR (TOP_SCORERS) ---
    if (typeof TOP_SCORERS !== 'undefined') {
        for (let season in TOP_SCORERS) {
            if (season === "ALL" || !TOP_SCORERS[season] || TOP_SCORERS[season].length === 0) continue;
            
            let winners = TOP_SCORERS[season];
            let displaySeason = winners[0].SäsongText || season;
            
            // DUBBLETT-SPÄRR: Har vi redan räknat denna säsong?
            if (processedTSSeasons.has(displaySeason)) continue;
            processedTSSeasons.add(displaySeason);
            
            chronoTS.push({ season: displaySeason, rawSeason: season, winners: winners });

            winners.forEach(w => {
                let pName = w.Namn;
                if(!tsPlayers[pName]) tsPlayers[pName] = { count: 0, clubs: new Set() };
                tsPlayers[pName].count++; tsPlayers[pName].clubs.add(w.Klubb);

                // --- NYTT: Klyv på snedstreck (/), kommatecken (,) OCH och-tecken (&) ---
                let clubs = String(w.Klubb).split(/[\/,&]/).map(c => c.trim());
                clubs.forEach(cName => {
                    if (!cName) return;
                    if(!tsClubs[cName]) tsClubs[cName] = { count: 0 };
                    tsClubs[cName].count++;
                });
            });
        }
    }

    // --- 2. PROCESSA PREMIÄRMÅL & DN-KLOCKAN (FIRST_SCORERS) ---
    if (typeof FIRST_SCORERS !== 'undefined') {
        for (let season in FIRST_SCORERS) {
            if (season === "ALL" || !FIRST_SCORERS[season] || Object.keys(FIRST_SCORERS[season]).length === 0) continue;
            
            let displaySeason = (typeof getSeasonName === 'function') ? getSeasonName(season) : season;
            
            // DUBBLETT-SPÄRR
            if (processedDNSeasons.has(displaySeason)) continue;
            processedDNSeasons.add(displaySeason);
            
            let flatList = [];
            for (const [lag, skyttar] of Object.entries(FIRST_SCORERS[season])) {
                skyttar.forEach(item => {
                    let pName = item.skytt;
                    
                    if (String(pName).toLowerCase().includes('självmål')) return;

                    let matchNr = (typeof getMatchCountBeforeGoal === 'function') ? getMatchCountBeforeGoal(lag, item.datum, item.motstandare) : 1;
                    let rawMin = (typeof formatGoalTime === 'function') ? formatGoalTime(item.minut) : item.minut;
                    let sortMin = parseInt(rawMin.split(':')[0]) || 999; 
                    let mNrNum = parseInt(matchNr) || 99; 

                    flatList.push({ lag, mNrNum, sortMin, rawMin, ...item });
                    
                    if(!psPlayers[pName]) psPlayers[pName] = { count: 0, clubs: new Set() };
                    psPlayers[pName].count++; psPlayers[pName].clubs.add(lag);
                });
            }

            let searchList = [...flatList];
            searchList.sort((a, b) => {
                if (a.mNrNum !== b.mNrNum) return a.mNrNum - b.mNrNum;
                return a.sortMin - b.sortMin;
            });

            let fastestItem = searchList.length > 0 ? searchList[0] : null;
            let seasonWinners = [];

            let hasDN = flatList.some(x => (x.not || "").toLowerCase().includes('dn'));
            if (hasDN) {
                seasonWinners = flatList.filter(x => (x.not || "").toLowerCase().includes('dn'));
            } else if (fastestItem) {
                seasonWinners = searchList.filter(x => x.mNrNum === fastestItem.mNrNum && x.sortMin === fastestItem.sortMin);
            }

            if (seasonWinners.length > 0) {
                chronoDN.push({ season: displaySeason, rawSeason: season, winners: seasonWinners });
                seasonWinners.forEach(w => {
                    let pName = w.skytt;
                    if(!dnPlayers[pName]) dnPlayers[pName] = { count: 0, clubs: new Set() };
                    dnPlayers[pName].count++; dnPlayers[pName].clubs.add(w.lag);
                });
            }
        }
    }

    // --- 3. HJÄLPFUNKTION: RITA UPP TOPPLISTOR ---
    function buildToplistHTML(dictObj, maxRows) {
        let sorted = Object.entries(dictObj).sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0], 'sv'));
        let html = "";
        let currentRank = 1; let previousCount = -1;
        
        sorted.slice(0, maxRows).forEach((item, i) => {
            if (item[1].count !== previousCount) { currentRank = i + 1; previousCount = item[1].count; }
            let medal = currentRank === 1 ? '🥇' : (currentRank === 2 ? '🥈' : (currentRank === 3 ? '🥉' : `${currentRank}.`));
            let clubsHtml = item[1].clubs ? `<div class="text-[10px] text-slate-400 mt-0.5 truncate max-w-[150px]">${Array.from(item[1].clubs).join(', ')}</div>` : "";
            
            // --- NYTT: Tvätta bort årtalet i parentes för visningen ---
            let displayName = String(item[0]).replace(/\s*\(\d{4}\)/g, '').trim();
            
            html += `<tr class="hover:bg-slate-50 border-b border-slate-100">
                <td class="px-3 py-2 w-8 text-center font-bold text-slate-400">${medal}</td>
                <td class="px-3 py-2"><div class="font-bold text-slate-800">${displayName}</div>${clubsHtml}</td>
                <td class="px-3 py-2 text-right font-black text-slate-700">${item[1].count}</td>
            </tr>`;
        });
        return html || `<tr><td colspan="3" class="px-4 py-2 text-slate-400 italic">Saknar data</td></tr>`;
    }

    document.getElementById('rec-top-players-scorers').innerHTML = buildToplistHTML(tsPlayers, 15);
    document.getElementById('rec-top-clubs-scorers').innerHTML = buildToplistHTML(tsClubs, 15);
    document.getElementById('rec-top-players-dn').innerHTML = buildToplistHTML(dnPlayers, 15);
    document.getElementById('rec-top-players-premiere').innerHTML = buildToplistHTML(psPlayers, 15);

    // --- 4. RITA KRONOLOGISKA LISTOR ---
    let sortChrono = (a, b) => {
        let yA = parseInt(a.season.substring(0, 4)) || 0;
        let yB = parseInt(b.season.substring(0, 4)) || 0;
        return yB - yA;
    };

    chronoTS.sort(sortChrono);
    let chronoTSHtml = "";
    chronoTS.forEach(row => {
        row.winners.forEach((w, i) => {
            let sLabel = i === 0 ? `<span class="font-bold text-slate-700">${row.season}</span>` : `<span class="text-transparent">---</span>`;
            
            // --- NYTT: Tvätta bort årtalet ---
            let displayName = String(w.Namn).replace(/\s*\(\d{4}\)/g, '').trim();

            chronoTSHtml += `<tr class="hover:bg-amber-50">
                <td class="px-4 py-2 w-20">${sLabel}</td>
                <td class="px-4 py-2"><span class="font-bold text-amber-700">${displayName}</span> <span class="text-xs text-slate-500">(${w.Klubb})</span></td>
                <td class="px-4 py-2 text-right font-black text-amber-600">${w.Mål}</td>
            </tr>`;
        });
    });
    document.getElementById('rec-chrono-scorers').innerHTML = chronoTSHtml || `<tr><td colspan="3" class="px-4 py-2 text-slate-400 italic">Saknar data</td></tr>`;

    // Kronologisk: DN-klockan / Tidsmästare
    chronoDN.sort(sortChrono);
    let chronoDNHtml = "";
    
    // NYTT: Variabel för att hålla koll på årtalet i loopen
    let prevYearDN = 9999; 

    chronoDN.forEach(row => {
        let currentYear = parseInt(row.season.substring(0, 4)) || 0;
        
        // --- NYTT: Injicera skiljelinje när vi passerar 1959-gränsen nedåt ---
        if (prevYearDN >= 1959 && currentYear < 1959) {
            chronoDNHtml += `
            <tr class="bg-slate-200 border-y border-slate-300">
                <td colspan="3" class="px-4 py-2 text-center text-xs font-bold text-slate-600 uppercase tracking-widest">
                    Innan 1959 (Snabbaste premiärmålet kröns med guld)
                </td>
            </tr>`;
        }
        prevYearDN = currentYear;

        row.winners.forEach((w, i) => {
            let sLabel = i === 0 ? `<span class="font-bold text-slate-700">${row.season}</span>` : `<span class="text-transparent">---</span>`;
            let minText = w.rawMin || "?";
            
            // --- NYTT: Tvätta bort årtalet ---
            let displayName = String(w.skytt).replace(/\s*\(\d{4}\)/g, '').trim();

            chronoDNHtml += `<tr class="hover:bg-blue-50">
                <td class="px-4 py-2 w-20">${sLabel}</td>
                <td class="px-4 py-2"><span class="font-bold text-blue-700">${displayName}</span> <span class="text-xs text-slate-500">(${w.lag})</span></td>
                <td class="px-4 py-2 text-right font-black text-blue-600">${minText}</td>
            </tr>`;
        });
    });
    document.getElementById('rec-chrono-dn').innerHTML = chronoDNHtml || `<tr><td colspan="3" class="px-4 py-2 text-slate-400 italic">Saknar data</td></tr>`;
}

        // --- Sviter Logik ---
        function calculateStreaks() {
    const teamFilter = document.getElementById('streaks-team').value; 
    const context = document.querySelector('input[name="streak-context"]:checked').value;
    const fromStart = document.getElementById('streak-from-start').checked; 
    let sameSeason = document.getElementById('streak-same-season').checked;

    // --- NYTT: Identifiera om vi tittar på en Säsongsprofil (Meta-lag) ---
    const isProfile = teamFilter.startsWith("PROFILE_");
    
    // Tvinga sviterna att brytas vid säsongsslut för profiler (så vi inte bygger sviter över årtionden!)
    const effectiveSameSeason = sameSeason || isProfile;

    document.getElementById('streaks-placeholder').classList.add('hidden');
    
    // Om vi valt ALLA eller en PROFIL, måste vi processa alla lag i databasen
    let teamsToProcess = (teamFilter === "ALL" || isProfile) ? TEAMS : [teamFilter];
    
    let absoluteMax = { win: { len: 0, arr: [], team: "" }, unb: { len: 0, arr: [], team: "" }, loss: { len: 0, arr: [], team: "" }, winless: { len: 0, arr: [], team: "" }, draw: { len: 0, arr: [], team: "" }, cs: { len: 0, arr: [], team: "" }, ns: { len: 0, arr: [], team: "" }, scored: { len: 0, arr: [], team: "" }, conceded: { len: 0, arr: [], team: "" } };
    let seasonMax = { w:0, wS:"", wT:"", l:0, lS:"", lT:"", gf:0, gfS:"", gfT:"", ga:0, gaS:"", gaT:"" };
    globalAllStreaks = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[], scored:[], conceded:[] };

    teamsToProcess.forEach(team => {
        let matches = MATCH_DATA.filter(m => m.Hemmalag === team || m.Bortalag === team);
        if (context === 'home') matches = matches.filter(m => m.Hemmalag === team);
        if (context === 'away') matches = matches.filter(m => m.Bortalag === team);

        // --- NY DÖRRVAKT FÖR PROFILER ---
        if (isProfile) {
            matches = matches.filter(m => {
                let info = (TEAM_MERITS[m.Säs] && TEAM_MERITS[m.Säs][team]) ? TEAM_MERITS[m.Säs][team] : {};
                if (teamFilter === 'PROFILE_CHAMPS') return info.merit === 'Mästare';
                if (teamFilter === 'PROFILE_DEFENDING') return !!info.regerande; // Sant om regerande
                if (teamFilter === 'PROFILE_PROMOTED') return info.nya === 'Nykomling';
                if (teamFilter === 'PROFILE_RELEGATED') return info.merit && (String(info.merit).toLowerCase().includes('nedflyttad') || String(info.merit).toLowerCase().includes('degraderad') || String(info.merit).toLowerCase().includes('uteslut'));
                return false;
            });
        }

        if (matches.length === 0) return; // Inga matcher uppfyllde profilen för detta lag, hoppa över!

        matches.sort((a, b) => {
            let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime();
            let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
            if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
            if(d1!==d2) return d1-d2;
            return a.Match_ID - b.Match_ID;
        });

        let max = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[], scored:[], conceded:[] };
        let cur = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[], scored:[], conceded:[] };
        let valid = { win:true, unb:true, loss:true, winless:true, draw:true, cs:true, ns:true, scored:true, conceded:true }; 

        const processMatch = (m) => {
            const isHome = m.Hemmalag === team;
            const gf = isHome ? parseInt(m.HM) : parseInt(m.BM); const ga = isHome ? parseInt(m.BM) : parseInt(m.HM);
            let notText = String(m.NOT).toUpperCase();
            let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
            let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
            if (isNaN(gf) || isNaN(ga)) { if (!(isWOH || isWOB)) return; }
            
            let matchWon = false, matchLost = false, matchDrawn = false;
            if (isWOH) { if (isHome) matchWon = true; else matchLost = true; }
            else if (isWOB) { if (!isHome) matchWon = true; else matchLost = true; }
            else if (gf > ga) matchWon = true;
            else if (gf < ga) matchLost = true;
            else matchDrawn = true;

            const c = { win: matchWon, unb: matchWon || matchDrawn, loss: matchLost, winless: matchLost || matchDrawn, draw: matchDrawn, cs: ga === 0, ns: gf === 0, scored: gf > 0, conceded: ga > 0 };
            Object.keys(c).forEach(k => {
                if (c[k]) { if (valid[k]) cur[k].push(m); } else {
                    if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                    if (cur[k].length > max[k].length) max[k] = [...cur[k]];
                    cur[k] = []; if (fromStart) valid[k] = false; 
                }
            });
        };

        let seasonMap = {}; matches.forEach(m => { if (!seasonMap[m.Säs]) seasonMap[m.Säs] = []; seasonMap[m.Säs].push(m); });
        
        if (effectiveSameSeason || fromStart) {
            Object.values(seasonMap).forEach(sMatches => {
                cur = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[], scored:[], conceded:[] };
                if (fromStart) valid = { win:true, unb:true, loss:true, winless:true, draw:true, cs:true, ns:true, scored:true, conceded:true };
                
                let sW=0, sL=0, sGf=0, sGa=0;

                sMatches.forEach(m => {
                    if (m.Annullerad) return;
                    processMatch(m);
                    const isHome = m.Hemmalag === team;
                    const gf = isHome ? parseInt(m.HM) : parseInt(m.BM); const ga = isHome ? parseInt(m.BM) : parseInt(m.HM);
                    let notText = String(m.NOT).toUpperCase();
                    let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                    let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                    
                    if (isWOH) { if(isHome) sW++; else sL++; }
                    else if (isWOB) { if(!isHome) sW++; else sL++; }
                    else if (!isNaN(gf) && !isNaN(ga)) {
                        sGf += gf; sGa += ga;
                        if (gf > ga) sW++; else if (gf < ga) sL++;
                    }
                });
                Object.keys(cur).forEach(k => { 
                    if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                    if (cur[k].length > max[k].length) max[k] = [...cur[k]]; 
                });

                let sasName = getSeasonName(sMatches[0].Säs);
                if (sW > seasonMax.w) { seasonMax.w = sW; seasonMax.wS = sasName; seasonMax.wT = team; }
                if (sL > seasonMax.l) { seasonMax.l = sL; seasonMax.lS = sasName; seasonMax.lT = team; }
                if (sGf > seasonMax.gf) { seasonMax.gf = sGf; seasonMax.gfS = sasName; seasonMax.gfT = team; }
                if (sGa > seasonMax.ga) { seasonMax.ga = sGa; seasonMax.gaS = sasName; seasonMax.gaT = team; }
            });
        } else {
            matches.forEach(processMatch);
            Object.keys(cur).forEach(k => { 
                if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                if (cur[k].length > max[k].length) max[k] = [...cur[k]]; 
            });
        }

        Object.keys(max).forEach(k => {
            if (max[k].length > absoluteMax[k].len) absoluteMax[k] = { len: max[k].length, arr: [...max[k]], team: team };
        });
    });

    currentStreakMatches = {}; Object.keys(absoluteMax).forEach(k => { currentStreakMatches[k] = absoluteMax[k].arr; });

    const showTeamLabel = (teamFilter === "ALL" || isProfile);

    const renderCard = (title, dataObj, key, color) => {
        const teamLabel = showTeamLabel ? `<div class="text-[11px] font-bold text-slate-800 mt-1 truncate px-2" title="${dataObj.team}">${dataObj.team}</div>` : "";
        return `<div onclick="openStreakModal('${key}', '${title}', '${dataObj.team}')" class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm text-center cursor-pointer hover:shadow-md hover:border-slate-300 transition-all group relative overflow-hidden flex flex-col justify-center"><div class="absolute inset-0 bg-${color.split('-')[1]}-50 opacity-0 group-hover:opacity-100 transition-opacity z-0"></div><div class="relative z-10"><div class="text-xs font-semibold uppercase tracking-wider mb-1 text-slate-500 group-hover:text-slate-800 transition-colors">${title}</div><div class="text-4xl font-black ${color}">${dataObj.len}</div>${teamLabel}<div class="text-[10px] text-slate-400 mt-1 uppercase flex items-center justify-center gap-1 group-hover:text-slate-600 transition-colors">Klicka för lista</div></div></div>`;
    };

    document.getElementById('streaks-results').innerHTML = `
        ${renderCard('Segrar', absoluteMax.win, 'win', 'text-emerald-600')}
        ${renderCard('Obesegrade', absoluteMax.unb, 'unb', 'text-emerald-500')}
        ${renderCard('Förluster', absoluteMax.loss, 'loss', 'text-rose-600')}
        ${renderCard('Utan Seger', absoluteMax.winless, 'winless', 'text-orange-500')}
        ${renderCard('Oavgjorda', absoluteMax.draw, 'draw', 'text-slate-600')}
        ${renderCard('Hållna Nollor', absoluteMax.cs, 'cs', 'text-blue-500')}
        ${renderCard('Måltorka', absoluteMax.ns, 'ns', 'text-slate-400')}
    `;
    document.getElementById('streaks-results').classList.remove('hidden');

    if (effectiveSameSeason) {
        const renderSeasonCard = (title, val, sTeam, sSeason, color) => {
            const tLabel = showTeamLabel ? `<div class="text-[11px] font-bold text-slate-800 mt-1 truncate px-2">${sTeam}</div>` : "";
            return `<div class="bg-slate-50 p-4 rounded-lg border border-slate-200 shadow-sm text-center flex flex-col justify-center"><div class="text-xs font-semibold uppercase tracking-wider mb-1 text-slate-500">${title}</div><div class="text-3xl font-black ${color}">${val}</div>${tLabel}<div class="text-[11px] text-slate-500 mt-1">${sSeason}</div></div>`;
        };
        document.getElementById('season-records-results').innerHTML = `
            ${renderSeasonCard('Flest Segrar', seasonMax.w, seasonMax.wT, seasonMax.wS, 'text-emerald-600')}
            ${renderSeasonCard('Flest Förluster', seasonMax.l, seasonMax.lT, seasonMax.lS, 'text-rose-600')}
            ${renderSeasonCard('Flest Gjorda Mål', seasonMax.gf, seasonMax.gfT, seasonMax.gfS, 'text-blue-600')}
            ${renderSeasonCard('Flest Insläppta Mål', seasonMax.ga, seasonMax.gaT, seasonMax.gaS, 'text-orange-600')}
        `;
        document.getElementById('season-records-section').classList.remove('hidden');
    } else {
        document.getElementById('season-records-section').classList.add('hidden');
    }
    renderStreakToplist();
}

        function renderStreakToplist() {
            const type = document.getElementById('streak-toplist-type').value;
            if (!type) { document.getElementById('streak-toplist-container').classList.add('hidden'); return; }
            
            let allOfType = globalAllStreaks[type];
            allOfType.sort((a, b) => b.len - a.len); 
            
            let uniqueStreaks = []; let seen = new Set();
            for (let s of allOfType) {
                if (s.len === 0) continue;
                let startM = s.arr[0]; let endM = s.arr[s.arr.length-1];
                let key = `${s.team}_${startM.Match_ID}_${endM.Match_ID}`;
                
                let isSubset = false;
                for (let u of uniqueStreaks) {
                    if (u.team === s.team && u.arr[0].Match_ID <= startM.Match_ID && u.arr[u.arr.length-1].Match_ID >= endM.Match_ID) {
                        isSubset = true; break;
                    }
                }
                
                if (!seen.has(key) && !isSubset) {
                    seen.add(key);
                    let gf = 0, ga = 0;
                    s.arr.forEach(m => {
                        let mHm = parseInt(m.HM)||0; let mBm = parseInt(m.BM)||0;
                        if (m.Hemmalag === s.team) { gf += mHm; ga += mBm; } else { gf += mBm; ga += mHm; }
                    });
                    s.gd = gf - ga; uniqueStreaks.push(s);
                }
                if (uniqueStreaks.length >= 10) break;
            }
            
            let html = uniqueStreaks.map((s, i) => {
                let startD = formatDate(s.arr[0].Matchdatum, s.arr[0].År);
                let endD = formatDate(s.arr[s.arr.length-1].Matchdatum, s.arr[s.arr.length-1].År);
                let gdColor = s.gd > 0 ? 'text-emerald-600' : (s.gd < 0 ? 'text-rose-600' : '');
                let gdSign = s.gd > 0 ? '+' : '';
                return `<tr class="hover:bg-slate-50 cursor-pointer" onclick="openStreakModalFromToplist('${type}', ${i})"><td class="p-3 font-bold text-slate-500">${i+1}</td><td class="p-3 font-medium text-slate-800">${s.team}</td><td class="p-3 text-center font-bold text-blue-600 text-lg">${s.len}</td><td class="p-3 text-xs text-slate-500">${startD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${getSeasonName(s.arr[0].Säs)}</span></td><td class="p-3 text-xs text-slate-500">${endD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${getSeasonName(s.arr[s.arr.length-1].Säs)}</span></td><td class="p-3 text-center font-bold font-mono ${gdColor}">${gdSign}${s.gd}</td></tr>`;
            }).join('');
            
            window._currentToplistMatches = uniqueStreaks;
            document.getElementById('streak-toplist-body').innerHTML = html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga sviter hittades.</td></tr>';
            document.getElementById('streak-toplist-container').classList.remove('hidden');
        }

        function openStreakModalFromToplist(type, index) {
            const streakObj = window._currentToplistMatches[index];
            const selectEl = document.getElementById('streak-toplist-type');
            const title = selectEl.options[selectEl.selectedIndex].text;
            
            document.getElementById('modal-title').innerText = `${title}: ${streakObj.team} (${streakObj.len} matcher)`;
            let html = '';
            streakObj.arr.forEach(m => {
                let origH = m.Hemmalag_Org || m.Hemmalag;
                let origB = m.Bortalag_Org || m.Bortalag;
                let hClass = m.Hemmalag === streakObj.team ? 'font-bold text-slate-900' : ''; 
                let aClass = m.Bortalag === streakObj.team ? 'font-bold text-slate-900' : '';
                let displayDate = formatDate(m.Matchdatum, m.År);
                html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${getSeasonName(m.Säs)}</td><td class="p-3 text-slate-500 text-xs">${m.Omgång || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${m.HM} - ${m.BM}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
            });
            document.getElementById('modal-tbody').innerHTML = html;
            document.getElementById('streak-modal').classList.remove('hidden');
        }

        function openStreakModal(type, title, holderTeam) {
            const matches = currentStreakMatches[type];
            document.getElementById('modal-title').innerText = `${title}: ${holderTeam} (${matches.length} matcher i rad)`;
            let html = '';
            matches.forEach(m => {
                // --- NY DÖRRVAKT: Mjuk radering ---
                if (m.Annullerad) return;
                let origH = m.Hemmalag_Org || m.Hemmalag;
                let origB = m.Bortalag_Org || m.Bortalag;
                let hClass = m.Hemmalag === holderTeam ? 'font-bold text-slate-900' : ''; let aClass = m.Bortalag === holderTeam ? 'font-bold text-slate-900' : '';
                let displayDate = formatDate(m.Matchdatum, m.År);
                html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${getSeasonName(m.Säs)}</td><td class="p-3 text-slate-500 text-xs">${m.Omgång || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${m.HM} - ${m.BM}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
            });
            document.getElementById('modal-tbody').innerHTML = html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga matcher att visa.</td></tr>';
            document.getElementById('streak-modal').classList.remove('hidden');
        }
        function closeStreakModal() { document.getElementById('streak-modal').classList.add('hidden'); }

        // --- Tabeller Logik ---
        function getMeritBadges(team, sas) {
            if (!TEAM_MERITS[sas] || !TEAM_MERITS[sas][team]) return '';
            const info = TEAM_MERITS[sas][team]; let badges = '';
            if (info.regerande) badges += '<span title="Regerande mästare" class="cursor-help ml-1 text-amber-500" style="font-size: 0.8em;">👑</span>';
            if (info.nya === 'Nykomling') badges += '<span title="Nykomling" class="cursor-help ml-1 text-blue-600 font-bold text-[10px] bg-blue-100 rounded px-1">NY</span>';
            if (info.merit === 'Mästare') badges += '<span title="Svenska Mästare" class="cursor-help ml-1 text-yellow-500" style="font-size: 0.9em;">🥇</span>';
            else if (info.merit === 'Medalj') badges += '<span title="Medalj" class="cursor-help ml-1 text-slate-400" style="font-size: 0.9em;">🥈</span>';
            else if (info.merit === 'Degraderade' || info.merit === 'Degraderade uteslutning') {
                let hoverText = info.merit === 'Degraderade uteslutning' ? 'Degraderad (Uteslutning)' : 'Degraderad';
                badges += `<span title="${hoverText}" class="cursor-help ml-1 text-rose-600 font-bold text-[10px] bg-rose-100 rounded px-1">↓</span>`;
            }
            else if (info.merit === 'Degraderade kval') badges += '<span title="Degraderade efter kval" class="cursor-help ml-1 text-rose-500 font-bold text-[10px] bg-rose-100 rounded px-1">↓K</span>';
            else if (info.merit === 'Kval kvar') badges += '<span title="Kvar efter kval" class="cursor-help ml-1 text-emerald-600 font-bold text-[10px] bg-emerald-100 rounded px-1">↔K</span>';
            return badges;
        }

        function calculateLeagueTable() {
            const season = document.getElementById('table-season').value; 
            const maxRoundRaw = document.getElementById('table-round').value.trim().toUpperCase();
            const phase = document.getElementById('table-phase').value;
            const pointsForWin = parseInt(document.getElementById('table-points').value);
            const perspective = document.getElementById('table-perspective').value;
            const pCtx = perspective.split('_')[0]; 
            const pHalf = perspective.split('_')[1]; 
            
            if(!season) { alert("Välj en säsong."); return; }
            document.getElementById('table-title').innerText = `Tabell: ${getSeasonName(season)} ${maxRoundRaw ? '(Efter omgång ' + maxRoundRaw + ')' : ''}`;
            document.getElementById('table-legend').classList.remove('hidden'); 

            let seasonYear = parseInt(extractYear(null, getSeasonName(season)).substring(0,4));
            let useGoalRatio = seasonYear < 1940;

            let isMSeriesSeason = (String(season) === "67" || String(season) === "68" || String(season) === "1991" || String(season) === "1992");
            let is1933 = (String(season) === "10" || String(season) === "1933/34");
            
            // HUVUDDÖRRVAKT: Släpper aldrig in annullerade matcher i tabell-motorn!
            let matches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && !m.Annullerad);
            if (phase === "GRUND") matches = matches.filter(m => !String(m.NOT).toLowerCase().includes("mästerskap"));
            else if (phase === "MASTER") matches = matches.filter(m => String(m.NOT).toLowerCase().includes("mästerskap"));

            matches = matches.filter(m => {
                if (maxRoundRaw === "ALL" || maxRoundRaw === "") return true;
                let rRaw = String(m.Omgång).trim().toUpperCase();
                if (rRaw === "") {
                    let limit = is1933 ? 19 : 21; let maxR = parseInt(maxRoundRaw);
                    if (!isNaN(maxR) && maxR >= limit) return true;
                    if (maxRoundRaw.startsWith("M")) return true;
                    return false;
                }
                let isMRound = rRaw.startsWith("M"); let isMaxMRound = maxRoundRaw.startsWith("M");
                if (isMaxMRound) {
                    if (!isMRound) return true;
                    return parseInt(rRaw.replace("M", "")) <= parseInt(maxRoundRaw.replace("M", ""));
                } else {
                    if (isMRound) return false; return parseInt(rRaw) <= parseInt(maxRoundRaw);
                }
            });
            
            let table = {};
            let seasonTeamNames = {};
            let notesSet = new Set();
            let totalGoals = 0; let totalMatchesPlayed = 0;
            let totalAttendance = 0; let matchesWithAttendance = 0;

            matches.forEach(m => {
                // --- NY DÖRRVAKT: Mjuk radering för dynamiska tabeller ---
                if (m.Annullerad) return;

                seasonTeamNames[m.Hemmalag] = m.Hemmalag_Org || m.Hemmalag;
                seasonTeamNames[m.Bortalag] = m.Bortalag_Org || m.Bortalag;
                [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0 }; });
                
                let hm, bm;
                if (pHalf === '1H') { hm = parseInt(m.HMF); bm = parseInt(m.BMF); }
                else if (pHalf === '2H') { hm = parseInt(m.HMA); bm = parseInt(m.BMA); }
                else { hm = parseInt(m.HM); bm = parseInt(m.BM); }

                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                let isAvbrutenO = notText.includes("AVBRUTEN; O");

                let noteStr = getNoteString(m.Hemmalag_Org || m.Hemmalag, m.Bortalag_Org || m.Bortalag, m.NOT, null);
                if (noteStr) notesSet.add(noteStr);

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(pHalf === 'FULL' && (isWOH || isWOB))) return;
                    hm = 0; bm = 0; 
                }

                let hPts = 0, bPts = 0, hW = 0, hD = 0, hL = 0, bW = 0, bD = 0, bL = 0;

                if (pHalf === 'FULL' && (isWOH || isWOB || isAvbrutenO)) {
                    if (isWOH) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (isWOB) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else if (isAvbrutenO) { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                } else {
                    if (hm > bm) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (hm < bm) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                }

                if (pCtx === 'ALL' || pCtx === 'HOME') {
                    table[m.Hemmalag].pld++; table[m.Hemmalag].gf += hm; table[m.Hemmalag].ga += bm;
                    table[m.Hemmalag].w += hW; table[m.Hemmalag].d += hD; table[m.Hemmalag].l += hL; table[m.Hemmalag].pts += hPts;
                }
                if (pCtx === 'ALL' || pCtx === 'AWAY') {
                    table[m.Bortalag].pld++; table[m.Bortalag].gf += bm; table[m.Bortalag].ga += hm;
                    table[m.Bortalag].w += bW; table[m.Bortalag].d += bD; table[m.Bortalag].l += bL; table[m.Bortalag].pts += bPts;
                }

                totalGoals += (hm + bm);
                totalMatchesPlayed++;
                let pub = parseInt(m.Publik);
                if (!isNaN(pub) && pub > 0) { totalAttendance += pub; matchesWithAttendance++; }
            });

            if (pHalf === 'FULL' && pCtx === 'ALL') {
                Object.values(table).forEach(t => {
                    let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                    if (mInfo && mInfo.start_pts !== 0) {
                        let adj = mInfo.start_pts;
                        if (adj === -3 && pointsForWin === 2) adj = -2;
                        if (isMSeriesSeason) { if (phase === "MASTER") t.pts += adj; } 
                        else { t.pts += adj; }
                    }
                });
            }

            document.getElementById('league-table-head').innerHTML = `
                <tr><th class="px-4 py-3 w-10">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">GM-IM</th><th class="px-4 py-3 text-center">${useGoalRatio ? 'Målkvot' : '+/-'}</th><th class="px-4 py-3 text-center font-bold">P</th></tr>
            `;

            let tableArr = Object.values(table).filter(r => r.pld > 0);
            tableArr.forEach(r => r.gd = r.gf - r.ga);
            tableArr.sort((a, b) => {
                if (b.pts !== a.pts) return b.pts - a.pts;
                if (useGoalRatio) {
                    let ratioA = a.ga === 0 ? (a.gf > 0 ? 999 : 0) : a.gf / a.ga;
                    let ratioB = b.ga === 0 ? (b.gf > 0 ? 999 : 0) : b.gf / b.ga;
                    if (ratioB !== ratioA) return ratioB - ratioA;
                } else {
                    if (b.gd !== a.gd) return b.gd - a.gd;
                }
                return b.gf - a.gf;
            });

            let html = tableArr.map((r, i) => {
                let origTeamName = seasonTeamNames[r.team] || r.team;
                let badges = getMeritBadges(r.team, season);
                let gdCell = useGoalRatio ? (r.ga === 0 ? (r.gf > 0 ? 'MAX' : '0.00') : (r.gf / r.ga).toFixed(2)) : (r.gd > 0 ? '+'+r.gd : r.gd);
                let gdColor = useGoalRatio ? 'text-slate-700' : (r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : '');
                
                return `<tr class="hover:bg-slate-50"><td class="px-4 py-2 font-bold text-slate-500">${i+1}</td><td class="px-4 py-2 font-medium"><div class="flex items-center">${origTeamName}${badges}</div></td><td class="px-4 py-2 text-center bg-slate-50">${r.pld}</td><td class="px-4 py-2 text-center text-emerald-600">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf} - ${r.ga}</td><td class="px-4 py-2 text-center font-bold ${gdColor}">${gdCell}</td><td class="px-4 py-2 text-center font-black bg-blue-50/50">${r.pts}</td></tr>`;
            }).join('');

            document.getElementById('league-table-body').innerHTML = html || '<tr><td colspan="9" class="text-center py-6 text-slate-500">Inga matcher hittades.</td></tr>';
            
            let notesHTML = "";
            let is1990 = (String(season) === "66" || String(season) === "1990");
            if (is1990 && pCtx === 'ALL') notesHTML += "<div class='flex gap-1 items-center text-slate-500'><span>*</span><span>3 poäng för seger fr.o.m. 1990.</span></div>";

            let is2006 = (String(season) === "82" || String(season) === "2006");
            if (is2006 && pHalf === 'FULL' && pCtx === 'ALL') notesHTML += "<div class='flex gap-1 items-center'><span>*</span><span>Hammarby IF tilldelades poängavdrag denna säsong.</span></div>";
            if (is1933) notesHTML += "<div class='flex gap-1 items-center'><span>*</span><span>Malmö FF uteslöts ur serien efter höstsäsongen 1933.</span></div>";
            if (isMSeriesSeason && phase === "MASTER" && pHalf === 'FULL' && pCtx === 'ALL') notesHTML += "<div class='flex gap-1 items-center text-blue-600'><span>*</span><span>Tabellen inkluderar lagens medhavda startpoäng från grundserien.</span></div>";
            if (useGoalRatio) notesHTML += "<div class='flex gap-1 items-center text-slate-500'><span>*</span><span>Tabellen sorteras med Målkvot (Gjorda/Insläppta) vid lika poäng (regelverk t.o.m 1939/40).</span></div>";
            if (seasonYear === 1940) notesHTML += "<div class='flex gap-1 items-center text-blue-600'><span>*</span><span>Från och med denna säsong infördes Målskillnad för att särskilja lag på samma poäng.</span></div>";
            
            notesSet.forEach(n => { notesHTML += `<div class='flex gap-1 items-center'><span>*</span><span>${n}</span></div>`; });

            document.getElementById('table-notes').innerHTML = notesHTML;
            if(notesHTML === "") document.getElementById('table-notes').classList.add('hidden');
            else document.getElementById('table-notes').classList.remove('hidden');
            
            // Uppdatera målstatistik och Publiksnitt
            let goalAvg = totalMatchesPlayed > 0 ? (totalGoals / totalMatchesPlayed).toFixed(2) : "0.00";
            let pubAvg = matchesWithAttendance > 0 ? Math.round(totalAttendance / matchesWithAttendance).toLocaleString('sv-SE') : "0";
            document.getElementById('table-goal-stats').innerText = `${totalGoals} Mål (${goalAvg} per match) | Publiksnitt: ${pubAvg}`;
            document.getElementById('table-goal-stats').classList.remove('hidden');

            document.getElementById('table-results').classList.remove('hidden');

            // --- TREND DATA ---
            if (pCtx === 'ALL' && pHalf === 'FULL') {
                globalSeasonRanks = {}; globalSeasonTeams = Object.keys(table); 
                let sMaxRound = 0; let mRoundsActive = false;
                matches.forEach(m => {
                    // --- NY DÖRRVAKT: Mjuk radering ---
                    if (m.Annullerad) return; 
                    let rStr = String(m.Omgång).toUpperCase();
                    if (rStr.startsWith("M")) { mRoundsActive = true; sMaxRound = Math.max(sMaxRound, parseInt(rStr.replace("M", ""))||0); } 
                    else { sMaxRound = Math.max(sMaxRound, parseInt(m.Omgång)||0); }
                });
                
                if (!mRoundsActive) {
                    for(let r = 1; r <= sMaxRound; r++) {
                        
                        // --- NY SKOTTSÄKER 50%-SPÄRR ---
                        let matchesInThisRound = matches.filter(m => parseInt(m.Omgång) === r);
                        let playedInThisRound = matchesInThisRound.filter(m => m.HM !== "" && m.HM !== null && m.HM !== undefined);
                        
                        let reqMatches = globalSeasonTeams.length / 4; // Minst 4 matcher för en 16-lagsserie
                        
                        if (playedInThisRound.length < reqMatches) {
                            // Mindre än 50% är spelade -> Spärra denna omgång helt
                            globalSeasonRanks[r] = null;
                        } else {
                            // Mer än 50% spelade -> Räkna ut tabellen
                            let rTable = {}; globalSeasonTeams.forEach(t => { rTable[t] = { team: t, pts:0, gd:0, gf:0 }; });
                            matches.filter(m => parseInt(m.Omgång) <= r).forEach(m => {
                                let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                                let nTxt = String(m.NOT).toUpperCase();
                                let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                                let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                                let isAvbrutenO = nTxt.includes("AVBRUTEN; O");
                                if (isNaN(hm) || isNaN(bm)) { hm = 0; bm = 0; }
                                rTable[m.Hemmalag].gf += hm; rTable[m.Bortalag].gf += bm; rTable[m.Hemmalag].gd += (hm - bm); rTable[m.Bortalag].gd += (bm - hm);
                                
                                if (isWOH) { rTable[m.Hemmalag].pts += pointsForWin; }
                                else if (isWOB) { rTable[m.Bortalag].pts += pointsForWin; }
                                else if (isAvbrutenO) { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                                else if (hm > bm) rTable[m.Hemmalag].pts += pointsForWin; 
                                else if (hm < bm) rTable[m.Bortalag].pts += pointsForWin;
                                else { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                            });
                            
                            Object.values(rTable).forEach(t => {
                                let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                                if (mInfo && mInfo.start_pts < 0) {
                                    let adj = mInfo.start_pts;
                                    if (adj === -3 && pointsForWin === 2) adj = -2;
                                    t.pts += adj;
                                }
                            });
                            
                            let tArr = Object.values(rTable); 
                            tArr.sort((a, b) => {
                                if (b.pts !== a.pts) return b.pts - a.pts;
                                if (useGoalRatio) {
                                    let ratioA = a.ga === 0 ? (a.gf > 0 ? 999 : 0) : a.gf / a.ga; let ratioB = b.ga === 0 ? (b.gf > 0 ? 999 : 0) : b.gf / b.ga;
                                    if (ratioB !== ratioA) return ratioB - ratioA;
                                } else { if (b.gd !== a.gd) return b.gd - a.gd; }
                                return b.gf - a.gf;
                            });
                            globalSeasonRanks[r] = {}; tArr.forEach((row, i) => { globalSeasonRanks[r][row.team] = i + 1; });
                        }
                    }
                    let trendSelect = document.getElementById('trend-team-select');
                    let options = '<option value="">-- Välj lag --</option>'; globalSeasonTeams.sort().forEach(t => { options += `<option value="${t}">${t}</option>`; });
                    trendSelect.innerHTML = options; document.getElementById('team-trend-section').classList.remove('hidden');
                    if (typeof trendChartInstance !== 'undefined' && trendChartInstance) trendChartInstance.destroy();
                } else { document.getElementById('team-trend-section').classList.add('hidden'); }
            } else { document.getElementById('team-trend-section').classList.add('hidden'); }

            // --- NYTT: RITA UT SKYTTEKUNG UNDER TABELLEN ---
            if (pCtx === 'ALL' && pHalf === 'FULL' && typeof renderTopScorers === 'function') {
                renderTopScorers(season);
            } else {
                // Dölj skyttekungen om vi tittar på typ Hemma/Borta-tabell eller Halvtid
                let tsc = document.getElementById('top-scorer-container');
                if (tsc) tsc.classList.add('hidden');
            }
        }

        // ==========================================
// 1. HJÄLPFUNKTIONER (Tid och Matchräkning)
// ==========================================
// Tvättar Excel-tider (ex "07:41:00" -> "7:41", "16.18" -> "16:18", "'32:32" -> "32:32")
function formatGoalTime(timeStr) {
    if (!timeStr || timeStr === 'nan') return "?";
    let s = String(timeStr).trim().replace('.', ':').replace("'", "");
    if (s.split(':').length === 3) {
        let p = s.split(':');
        s = p[0] + ':' + p[1];
    }
    if (s.startsWith('0')) s = s.substring(1);
    return s;
}

// Blixtsnabb, 100% felsäker matchräknare som hittar säsongen via databasen
function getMatchCountBeforeGoal(team, matchDate, opponent) {
    if (typeof MATCH_DATA === 'undefined' || !MATCH_DATA) return "?";
    
    try {
        let targetDate = String(matchDate || "").substring(0, 10).trim();
        let targetOpp = String(opponent || "").trim();
        
        // 1. Hitta matchen i databasen för att fastställa exakt vilken 'Säs' den tillhör
        let theMatch = MATCH_DATA.find(m => {
            let d = String(m.Datum || "").substring(0, 10).trim();
            let isTeam = m.Hemmalag === team || m.Bortalag === team;
            let isOpp = m.Hemmalag === targetOpp || m.Bortalag === targetOpp;
            return isTeam && isOpp && d === targetDate;
        });
        
        // (Fuzzy match ifall datumet diffar en dag i databasen)
        if (!theMatch && targetDate.length >= 4) {
            let tYear = targetDate.substring(0, 4);
            theMatch = MATCH_DATA.find(m => {
                let isTeam = m.Hemmalag === team || m.Bortalag === team;
                let isOpp = m.Hemmalag === targetOpp || m.Bortalag === targetOpp;
                let mYear = String(m.Datum || "").substring(0, 4);
                return isTeam && isOpp && mYear === tYear; 
            });
        }
        
        if (!theMatch) return "?";
        
        let matchSas = theMatch.Säs;
        
        // 2. Hämta alla lagets matcher för DENNA säsong
        let seasonMatches = MATCH_DATA.filter(m => {
            if (m.Annullerad && !window.forceIncludeAnnulled) return false;
            return (m.Hemmalag === team || m.Bortalag === team) && m.Säs === matchSas;
        });
        
        // 3. Sortera kronologiskt och hitta numret
        seasonMatches.sort((a, b) => new Date(a.Datum || '1900') - new Date(b.Datum || '1900'));
        for (let i = 0; i < seasonMatches.length; i++) {
            if (seasonMatches[i] === theMatch) return i + 1;
        }
    } catch(e) { console.error("Fel i matchräkning:", e); }
    return "?"; 
}

// Global sorteringsvariabel för premiärmålskyttar
window.prem_sort = window.prem_sort || 'team';

// ==========================================
// 2. FUNKTION: BYGG HTML FÖR PREMIÄRMÅLSKYTTAR
// ==========================================
function buildPremiereScorersHTML(originalSeasonStr, displaySeason) {
    let scorersObj = null;
    if (typeof FIRST_SCORERS !== 'undefined') {
        scorersObj = FIRST_SCORERS[displaySeason] || FIRST_SCORERS[originalSeasonStr];
    }
    if (!scorersObj || Object.keys(scorersObj).length === 0) return ""; 

    let startYear = parseInt(String(displaySeason).substring(0, 4));
    let isPre1959 = !isNaN(startYear) && startYear < 1959;

    // --- PLATTA UT OCH BERÄKNA DATA ---
    let flatList = [];
    for (const [lag, skyttar] of Object.entries(scorersObj)) {
        skyttar.forEach(item => {
            let matchNr = getMatchCountBeforeGoal(lag, item.datum, item.motstandare);
            let rawMin = formatGoalTime(item.minut);
            let sortMin = parseInt(rawMin.split(':')[0]) || 999; 
            let mNrNum = parseInt(matchNr) || 99; 

            flatList.push({ lag: lag, matchNr: matchNr, mNrNum: mNrNum, sortMin: sortMin, rawMin: rawMin, ...item });
        });
    }

    // --- HITTA SNABBASTE MÅLET FÖRE 1959 ---
    let fastestItem = null;
    if (isPre1959) {
        let firstRoundGoals = flatList.filter(x => x.mNrNum === 1);
        if (firstRoundGoals.length > 0) {
            firstRoundGoals.sort((a, b) => a.sortMin - b.sortMin);
            fastestItem = firstRoundGoals[0];
        }
    }

    // --- SORTERA LISTAN ---
    if (window.prem_sort === 'player') {
        flatList.sort((a, b) => String(a.skytt).localeCompare(String(b.skytt), 'sv'));
    } else if (window.prem_sort === 'time') {
        flatList.sort((a, b) => {
            if (a.mNrNum !== b.mNrNum) return a.mNrNum - b.mNrNum;
            return a.sortMin - b.sortMin;
        });
    } else {
        flatList.sort((a, b) => String(a.lag).localeCompare(String(b.lag), 'sv'));
    }

    // --- BYGG UTRITNING ---
    let html = `
    <div class="mt-4 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden w-full">
        <div class="bg-slate-800 text-white px-4 py-3 flex flex-wrap justify-between items-center cursor-pointer hover:bg-slate-700 transition-colors" onclick="document.getElementById('prem-scorers-list').classList.toggle('hidden')">
            <h3 class="font-bold text-sm uppercase tracking-wider flex items-center gap-2">🎯 Årets Premiärmålskyttar</h3>
            <div class="flex items-center gap-3 mt-2 sm:mt-0">
                <select onchange="window.prem_sort=this.value; window.renderTopScorers('${originalSeasonStr}'); event.stopPropagation();" onclick="event.stopPropagation();" class="text-xs text-slate-800 bg-slate-100 border border-slate-300 rounded px-2 py-1 outline-none font-semibold cursor-pointer">
                    <option value="team" ${window.prem_sort === 'team' ? 'selected' : ''}>Klubb (A-Ö)</option>
                    <option value="player" ${window.prem_sort === 'player' ? 'selected' : ''}>Spelare (A-Ö)</option>
                    <option value="time" ${window.prem_sort === 'time' ? 'selected' : ''}>Snabbaste mål (Match + Tid)</option>
                </select>
                <span class="text-xs text-slate-300 bg-slate-600 px-2 py-1 rounded-md">Fäll ut/in</span>
            </div>
        </div>
        <div id="prem-scorers-list" class="divide-y divide-slate-100 hidden">
    `;

    flatList.forEach(item => {
        let isDN = (item.not || "").toLowerCase().includes('dn-klockan') || (item.not || "").toLowerCase().includes('dn');
        let isFastestPre1959 = (fastestItem && item.lag === fastestItem.lag && item.skytt === fastestItem.skytt && item.sortMin === fastestItem.sortMin && item.mNrNum === 1);

        // --- NYTT: Tvätta bort årtalet i parentes ---
        let displayName = String(item.skytt).replace(/\s*\(\d{4}\)/g, '').trim();
        
        let isGold = isDN || isFastestPre1959;
        let icon = isDN ? '⏱️' : (isFastestPre1959 ? '🏅' : '⚽'); 
        
        // --- NY LOGIK FÖR UPPSKJUTNA MATCHER (DN-KLOCKAN) ---
        let displayNot = item.not || "";
        if (isFastestPre1959 && !displayNot) displayNot = "Snabbaste premiärmålet";
        
        // Om det är en DN-klocka men målet gjordes i lagets 2:a, 3:e match (uppskjuten premiär)
        if (isDN && item.mNrNum > 1) {
            if (!displayNot.toLowerCase().includes("uppskjut")) {
                displayNot = displayNot ? displayNot + " (Uppskjuten match)" : "Uppskjuten match";
            }
        }
        // ---------------------------------------------------

        let nameStyle = isGold ? 'text-amber-600 font-extrabold' : 'text-slate-800 font-bold';
        let timeStyle = isGold ? 'text-amber-600 font-black' : 'text-slate-700 font-semibold';
        let notText = displayNot ? `<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 ${isGold ? 'bg-amber-100 text-amber-700 border-amber-300' : 'bg-slate-100 text-slate-600 border-slate-200'} rounded border ml-2">${displayNot}</span>` : "";
        
        let isHome = item.hemmalag === item.lag;
        let hm = parseInt(item.hm); let bm = parseInt(item.bm);
        let teamGoals = isHome ? hm : bm;
        let oppGoals = isHome ? bm : hm;
        
        let resText = (!isNaN(teamGoals) && !isNaN(oppGoals)) ? `${teamGoals}-${oppGoals}` : "Okänt";
        let resColor = teamGoals > oppGoals ? 'text-emerald-600 font-bold' : (teamGoals < oppGoals ? 'text-red-500 font-bold' : 'text-slate-500 font-bold');
        let homeAwayStr = isHome ? 'H' : 'B';
        
        let ageText = item.alder ? `<span class="text-xs font-normal text-slate-500 ml-1">(${item.alder} år)</span>` : "";

        html += `
        <div class="p-4 hover:bg-slate-50 transition-colors flex flex-col sm:flex-row justify-between sm:items-center gap-3">
            <div>
                <div class="flex items-center">
                    <span class="text-lg mr-2" title="Guldmarkerad vid snabbaste mål">${icon}</span>
                    <span class="${nameStyle} text-base">${displayName}</span>
                    ${ageText} ${notText}
                </div>
                <div class="text-xs text-slate-500 mt-1 uppercase tracking-wider font-semibold flex items-center gap-2">
                    <span class="text-slate-700">${item.lag}</span> 
                    <span class="w-1 h-1 rounded-full bg-slate-300"></span> 
                    <span class="normal-case">Minut: <span class="${timeStyle} text-[13px]">${item.rawMin}</span></span>
                </div>
            </div>
            <div class="text-left sm:text-right bg-slate-50 sm:bg-transparent p-2 sm:p-0 rounded border border-slate-100 sm:border-none">
                <div class="text-sm text-slate-700">
                    ${homeAwayStr} mot <span class="font-medium">${item.motstandare}</span> 
                    (<span class="${resColor}">${resText}</span>)
                </div>
                <div class="text-xs text-slate-400 mt-1 font-medium">
                    Lagets ${item.matchNr}:e match <span class="font-normal">(${item.datum})</span>
                </div>
            </div>
        </div>
        `;
    });
    
    html += `</div></div>`;
    return html;
}

// ==========================================
// 3. FUNKTION: SKYTTEKUNGAR (HUVUDUTSKRIFTEN)
// ==========================================
window.renderTopScorers = function(seasonStr) {
    let container = document.getElementById('top-scorer-container');
    if (!container) return;
    container.innerHTML = ""; 

    try {
        if (!seasonStr || seasonStr === 'ALL') {
            container.classList.add('hidden');
            return;
        }

        // --- LÖSNING FÖR 2026: Hämta det riktiga namnet direkt! ---
        let displaySeason = seasonStr; 
        if (typeof getSeasonName === 'function') {
            displaySeason = getSeasonName(seasonStr);
        }

        let hasTopScorers = typeof TOP_SCORERS !== 'undefined' && TOP_SCORERS[seasonStr] && TOP_SCORERS[seasonStr].length > 0;
        
        // Överskrid med Skyttekungens inbäddade SäsongText (om den finns och avviker)
        if (hasTopScorers && TOP_SCORERS[seasonStr][0].SäsongText) {
            displaySeason = TOP_SCORERS[seasonStr][0].SäsongText;
        }

        let hasFirstScorers = false;
        if (typeof FIRST_SCORERS !== 'undefined') {
            if (FIRST_SCORERS[displaySeason] && Object.keys(FIRST_SCORERS[displaySeason]).length > 0) hasFirstScorers = true;
            else if (FIRST_SCORERS[seasonStr] && Object.keys(FIRST_SCORERS[seasonStr]).length > 0) hasFirstScorers = true;
        }

        if (!hasTopScorers && !hasFirstScorers) {
            container.classList.add('hidden');
            return;
        }

        let htmlParts = [];
        if (hasTopScorers) {
            htmlParts = TOP_SCORERS[seasonStr].map(player => {
                let fodd = player.Född;
                let ageText = "";
                let localDispSeason = player.SäsongText || displaySeason;

                // NYTT: Tvätta bort eventuella årtal i parentes för visningen på skärmen
                let displayName = player.Namn.replace(/\s*\(\d{4}\)/g, '').trim();
                
                if (fodd && typeof calculateExactAge === 'function') {
                    let calcDate = "";
                    
                    // Om Python redan har skickat med ett slutdatum, använd det.
                    if (player.Slutdatum) {
                        calcDate = player.Slutdatum;
                    } else {
                        // Annars: Bygg slutdatumet dynamiskt utifrån säsongens namn i JavaScript
                        let seasonStr = String(localDispSeason).trim();
                        
                        if (seasonStr.includes('/')) {
                            // Höst/Vår (ex: "1924/25" -> slutår 1925, slutdatum 30 juni)
                            let parts = seasonStr.split('/');
                            if (parts.length === 2 && parts[1].length === 2) {
                                let century = parts[0].substring(0, 2); // "19" eller "20"
                                let endYear = century + parts[1]; // "1925"
                                calcDate = `${endYear}-06-30`;
                            } else {
                                calcDate = `${seasonStr.substring(0, 4)}-06-30`;
                            }
                        } else {
                            // Vår/Höst (ex: "1959" -> slutår 1959, slutdatum 30 november)
                            calcDate = `${seasonStr.substring(0, 4)}-11-30`;
                        }
                    }

                    let age = calculateExactAge(fodd, calcDate);
                    ageText = age !== "" ? `<span class="text-sm font-normal text-slate-500 ml-1 block mt-1">Ålder: ${age} år</span>` : "";
                }

                return `
                <div class="flex flex-col p-4 bg-gradient-to-br from-amber-50 to-white rounded-xl shadow-sm border border-amber-200 flex-1 min-w-[240px]">
                    <div class="text-amber-600 text-[10px] font-black uppercase tracking-widest mb-1">Skyttekung ${localDispSeason}</div>
                    <div class="text-slate-800 font-black text-xl leading-none">${displayName}</div>
                    ${ageText}
                    <div class="text-slate-500 text-sm font-medium mt-2">Klubb: <span class="text-slate-700">${player.Klubb}</span></div>
                    <div class="mt-3 flex items-end gap-1">
                        <span class="text-3xl font-black text-amber-500 leading-none">${player.Mål}</span>
                        <span class="text-sm text-amber-600 font-bold mb-1">mål</span>
                    </div>
                </div>`;
            });
        }

        let firstScorersHTML = "";
        try {
            firstScorersHTML = buildPremiereScorersHTML(seasonStr, displaySeason);
        } catch(e) { console.error("Kunde inte bygga premiärmålskyttar: ", e); }

        container.innerHTML = `
        <div class="flex flex-col gap-3 w-full">
            <div class="flex gap-4 flex-wrap w-full">
                ${htmlParts.join('')}
            </div>
            ${firstScorersHTML}
        </div>`;
        
        container.classList.remove('hidden');

    } catch (criticalError) { console.error("Kritiskt fel i renderTopScorers:", criticalError); }
}
        
        function renderTeamTrend() {
            const team = document.getElementById('trend-team-select').value; if(!team) return;
            const season = document.getElementById('table-season').value;
            document.getElementById('trend-title').innerText = `Placeringsutveckling: ${team} (${getSeasonName(season)})`;
            let labels = []; let data = []; let r_keys = Object.keys(globalSeasonRanks).map(Number).sort((a,b)=>a-b);
            let maxR = r_keys.length > 0 ? r_keys[r_keys.length-1] : 0;
            for(let r=1; r<=maxR; r++) { 
                labels.push(`Omg ${r}`); 
                // Om omgången spärrades av databasen, tryck in null
                if (globalSeasonRanks[r] === null) {
                    data.push(null);
                } else {
                    data.push(globalSeasonRanks[r] ? globalSeasonRanks[r][team] || null : null); 
                }
            }
            const ctx = document.getElementById('teamTrendChart').getContext('2d');
            if(trendChartInstance) trendChartInstance.destroy();
            trendChartInstance = new Chart(ctx, { type: 'line', data: { labels: labels, datasets: [{ label: 'Placering', data: data, borderColor: '#2563eb', backgroundColor: '#2563eb', borderWidth: 3, tension: 0.1, pointBackgroundColor: '#1e3a8a', pointRadius: 4, spanGaps: true, }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { reverse: true, min: 1, max: globalSeasonTeams.length, ticks: { stepSize: 1 }, title: { display: true, text: 'Tabellplacering' } } } } });
        }

        function renderDynamicAllTimeTable() {
            const epochSelection = document.getElementById('table-epoch').value;
            const pointsForWin = parseInt(document.getElementById('table-points').value) || 3;
            const perspective = document.getElementById('table-perspective').value;
            const excludeMaster = document.getElementById('maraton-exclude-master').checked;
            
            const pCtx = perspective.split('_')[0]; 
            const pHalf = perspective.split('_')[1]; 
            
            document.getElementById('team-trend-section').classList.add('hidden');
            document.getElementById('table-legend').classList.add('hidden');
            document.getElementById('table-notes').classList.add('hidden'); 
            // --- NY KOD: Dölj skyttekungen när Maratontabellen visas ---
            let tsc = document.getElementById('top-scorer-container');
            if (tsc) tsc.classList.add('hidden');
            // -----------------------------------------------------------
            
            let seasonsToInclude = []; let titleSuffix = "Totalt (Alla säsonger)";
            if (epochSelection === "ALL") { seasonsToInclude = SEASONS; } 
            else if (epochSelection.startsWith("EPOCH_CUSTOM_")) { let epochName = epochSelection.replace("EPOCH_CUSTOM_", ""); seasonsToInclude = CUSTOM_EPOCHS[epochName]; titleSuffix = `Egen Epok: ${epochName}`; } 
            else if (epochSelection.startsWith("EPOCH_DECADE_")) { let epochName = epochSelection.replace("EPOCH_DECADE_", ""); seasonsToInclude = DECADES[epochName]; titleSuffix = `Årtionde: ${epochName}`; }

            const seasonSet = new Set(seasonsToInclude.map(String));
            let matches = MATCH_DATA.filter(m => seasonSet.has(String(m.Säs)));
            
            if (excludeMaster) {
                matches = matches.filter(m => !String(m.NOT).toUpperCase().includes("MÄSTERSKAP"));
            }

            if (matches.length === 0) { alert("Inga matcher hittades för denna period/epok."); return; }

            let persText = "";
            if (pCtx === 'HOME') persText = " (Endast Hemmamatcher)"; if (pCtx === 'AWAY') persText = " (Endast Bortamatcher)";
            if (pHalf === '1H') persText += " (Första Halvlek)"; if (pHalf === '2H') persText += " (Andra Halvlek)";
            if (excludeMaster) persText += " - Exklusive Mästerskapsserien";

            document.getElementById('table-title').innerText = `Maratontabell - ${titleSuffix}${persText} (${pointsForWin} poäng för seger)`;

            let table = {};
            let totalGoals = 0; let totalMatchesPlayed = 0;
            let totalAttendance = 0; let matchesWithAttendance = 0;

            matches.forEach(m => {
                // --- NY DÖRRVAKT: Mjuk radering ---
                if (m.Annullerad) return;

                [m.Hemmalag, m.Bortalag].forEach(t => {
                    if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, firstS: null, lastS: null, seasons: new Set() };
                });
                
                let hm, bm;
                if (pHalf === '1H') { hm = parseInt(m.HMF); bm = parseInt(m.BMF); }
                else if (pHalf === '2H') { hm = parseInt(m.HMA); bm = parseInt(m.BMA); }
                else { hm = parseInt(m.HM); bm = parseInt(m.BM); }

                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                let isAvbrutenO = notText.includes("AVBRUTEN; O");

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(pHalf === 'FULL' && (isWOH || isWOB))) return;
                    hm = 0; bm = 0; 
                }

                let hPts = 0, bPts = 0, hW = 0, hD = 0, hL = 0, bW = 0, bD = 0, bL = 0;
                if (pHalf === 'FULL' && (isWOH || isWOB || isAvbrutenO)) {
                    if (isWOH) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (isWOB) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else if (isAvbrutenO) { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                } else {
                    if (hm > bm) { hPts = pointsForWin; hW = 1; bL = 1; } else if (hm < bm) { bPts = pointsForWin; bW = 1; hL = 1; } else { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                }

                if (pCtx === 'ALL' || pCtx === 'HOME') {
                    table[m.Hemmalag].pld++; table[m.Hemmalag].gf += hm; table[m.Hemmalag].ga += bm;
                    table[m.Hemmalag].w += hW; table[m.Hemmalag].d += hD; table[m.Hemmalag].l += hL; table[m.Hemmalag].pts += hPts; table[m.Hemmalag].seasons.add(String(m.Säs));
                }
                if (pCtx === 'ALL' || pCtx === 'AWAY') {
                    table[m.Bortalag].pld++; table[m.Bortalag].gf += bm; table[m.Bortalag].ga += hm;
                    table[m.Bortalag].w += bW; table[m.Bortalag].d += bD; table[m.Bortalag].l += bL; table[m.Bortalag].pts += bPts; table[m.Bortalag].seasons.add(String(m.Säs));
                }

                totalGoals += (hm + bm);
                totalMatchesPlayed++;
                let pub = parseInt(m.Publik);
                if (!isNaN(pub) && pub > 0) { totalAttendance += pub; matchesWithAttendance++; }
            });

            if (pCtx === 'ALL' && pHalf === 'FULL') {
                Object.values(table).forEach(t => {
                    let totalDeduction = 0;
                    t.seasons.forEach(sas => {
                        let mInfo = TEAM_MERITS[sas] && TEAM_MERITS[sas][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            if (adj === -3 && pointsForWin === 2) adj = -2;
                            totalDeduction += adj;
                        }
                    });
                    t.pts += totalDeduction;
                });
            }

            let arr = Object.values(table).filter(r => r.pld > 0);
            arr.forEach(r => {
                r.gd = r.gf - r.ga;
                let s_arr = Array.from(r.seasons).sort((a,b) => parseFloat(a) - parseFloat(b));
                if (s_arr.length > 0) { r.firstS = getSeasonName(s_arr[0]); r.lastS = getSeasonName(s_arr[s_arr.length-1]); }
            });
            arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
            
            document.getElementById('league-table-head').innerHTML = `
                <tr><th class="px-4 py-3 w-10">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center bg-slate-50">Första-Sista</th><th class="px-4 py-3 text-center bg-slate-50">Säsonger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">GM-IM</th><th class="px-4 py-3 text-center">+/-</th><th class="px-4 py-3 text-center font-bold">P</th></tr>
            `;

            let html = arr.map((r, i) => `
                <tr class="hover:bg-slate-50"><td class="px-4 py-2 font-bold text-slate-500">${i+1}</td><td class="px-4 py-2 font-medium">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 text-xs text-slate-500">${r.firstS} - ${r.lastS}</td><td class="px-4 py-2 text-center bg-slate-50 font-bold">${r.seasons.size}</td><td class="px-4 py-2 text-center">${r.pld}</td><td class="px-4 py-2 text-center text-emerald-600">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf} - ${r.ga}</td><td class="px-4 py-2 text-center font-bold ${r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : ''}">${r.gd > 0 ? '+'+r.gd : r.gd}</td><td class="px-4 py-2 text-center font-black bg-blue-50/50">${r.pts}</td></tr>
            `).join('');

            let goalAvg = totalMatchesPlayed > 0 ? (totalGoals / totalMatchesPlayed).toFixed(2) : "0.00";
            let pubAvg = matchesWithAttendance > 0 ? Math.round(totalAttendance / matchesWithAttendance).toLocaleString('sv-SE') : "0";
            document.getElementById('table-goal-stats').innerText = `${totalGoals} Mål (${goalAvg} per match) | Publiksnitt: ${pubAvg}`;
            document.getElementById('table-goal-stats').classList.remove('hidden');

            document.getElementById('league-table-body').innerHTML = html || '<tr><td colspan="11" class="text-center py-6 text-slate-500">Inga matcher hittades.</td></tr>';
            document.getElementById('table-results').classList.remove('hidden');
        }

        // --- SÄSONGENS PROFILER ---
        function renderProfiles() {
            const season = document.getElementById('profiles-season').value;
            if(!season) {
                document.getElementById('profiles-results').classList.add('hidden');
                document.getElementById('profiles-placeholder').classList.remove('hidden');
                return;
            }
            
            document.getElementById('profiles-placeholder').classList.add('hidden');
            document.getElementById('profiles-results').classList.remove('hidden');
            
            let champs = []; let defending = []; let promoted = [];
            if(TEAM_MERITS[season]) {
                Object.keys(TEAM_MERITS[season]).forEach(team => {
                    const info = TEAM_MERITS[season][team];
                    if(info.merit === 'Mästare') champs.push(team);
                    if(info.regerande) defending.push(team);
                    if(info.nya === 'Nykomling') promoted.push(team);
                });
            }
            
            const seasonMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season));
            
            document.getElementById('profile-champions').innerHTML = buildProfileSection("Årets Mästare", champs, seasonMatches, "text-yellow-600", "bg-yellow-50", "border-yellow-200", "🥇");
            document.getElementById('profile-defending').innerHTML = buildProfileSection("Regerande Mästare", defending, seasonMatches, "text-amber-600", "bg-amber-50", "border-amber-200", "👑");
            document.getElementById('profile-promoted').innerHTML = buildProfileSection("Nykomlingar", promoted, seasonMatches, "text-blue-600", "bg-blue-50", "border-blue-200", "NY");
        }

        function buildProfileSection(title, teams, matches, textColor, bgColor, borderColor, icon) {
            if(teams.length === 0) return '';
            let html = `<div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"><div class="${bgColor} px-4 py-3 border-b ${borderColor} flex items-center gap-2"><span class="text-xl font-bold bg-white px-2 py-0.5 rounded shadow-sm border ${borderColor}">${icon}</span><h3 class="font-bold text-lg ${textColor}">${title}</h3></div><div class="p-4 flex flex-col gap-6">`;
                
            teams.forEach(team => {
                let tMatches = matches.filter(m => m.Hemmalag === team || m.Bortalag === team);
                tMatches.sort((a,b) => {
                    let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime(); let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                    if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
                    if(d1!==d2) return d1-d2; return a.Match_ID - b.Match_ID;
                });
                
                let displayTeamName = tMatches.length > 0 ? (tMatches[0].Hemmalag === team ? (tMatches[0].Hemmalag_Org || tMatches[0].Hemmalag) : (tMatches[0].Bortalag_Org || tMatches[0].Bortalag)) : team;
                
                let w=0, d=0, l=0, gf=0, ga=0; let mHtml = '';
                tMatches.forEach(m => {
                    // --- NY DÖRRVAKT: Mjuk radering ---
                    if (m.Annullerad) return;

                    const isHome = m.Hemmalag === team;
                    let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                    if(!isNaN(hm) && !isNaN(bm)) {
                        let tg = isHome ? hm : bm; let og = isHome ? bm : hm;
                        gf+=tg; ga+=og;
                        if(tg>og) w++; else if(tg<og) l++; else d++;
                    }
                    let resClass = "";
                    if (hm === bm) resClass = "bg-slate-100 text-slate-800";
                    else if (isHome && hm>bm || !isHome && bm>hm) resClass = "bg-emerald-100 text-emerald-800";
                    else resClass = "bg-rose-100 text-rose-800";
                    
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;

                    mHtml += `<div class="flex justify-between items-center text-xs p-2 border-b border-slate-50 hover:bg-slate-50"><span class="w-1/4 text-slate-500">${m.Omgång||'-'} | ${formatDate(m.Matchdatum, m.År)}</span><span class="w-1/4 text-right ${isHome?'font-bold':''}">${origH}</span><span class="w-1/6 text-center font-mono font-bold ${resClass} rounded px-1">${m.HM}-${m.BM}</span><span class="w-1/4 ${!isHome?'font-bold':''}">${origB}</span></div>`;
                });
                
                html += `<div><h4 class="font-bold text-slate-800 mb-2">${displayTeamName}</h4><div class="flex gap-4 text-sm mb-3"><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100">Matcher: <b>${tMatches.length}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-emerald-600">V: <b>${w}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-slate-600">O: <b>${d}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-rose-600">F: <b>${l}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100">Mål: <b>${gf}-${ga}</b></div></div><div class="border border-slate-200 rounded max-h-64 overflow-y-auto custom-scroll">${mHtml}</div></div>`;
            });
            html += `</div></div>`; return html;
        }

        // --- SÄSONGSSTYRKA ---
        function runStrengthAnalysis() {
            document.getElementById('strength-loading').classList.remove('hidden');
            document.getElementById('strength-results').classList.add('hidden');
            
            setTimeout(() => {
                let strengthData = [];
                
                SEASONS.forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && m.Omgång !== "" && !m.Annullerad);
                    if(sMatches.length === 0) return;
                    
                    let table = {};
                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;
                    
                    sMatches.forEach(m => {
                        // --- NY DÖRRVAKT: Mjuk radering ---
                        if (m.Annullerad) return;

                        [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0, pld:0 }; });
                        let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                        let nTxt = String(m.NOT).toUpperCase();
                        let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                        let isO = nTxt.includes("AVBRUTEN; O");
                        
                        if(isNaN(hm) || isNaN(bm)) {
                            if(!(isWOH||isWOB)) return; hm=0; bm=0;
                        }
                        
                        table[m.Hemmalag].pld++; table[m.Bortalag].pld++;
                        table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm;
                        table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                        
                        if (isWOH) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                        else if (isO) { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                        else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                        else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                    });
                    
                    Object.values(table).forEach(t => {
                        let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            t.pts += adj;
                        }
                    });

                    let tArr = Object.values(table).filter(r => r.pld > 0);
                    if(tArr.length === 0) return;
                    tArr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                    
                    let nTeams = tArr.length;
                    let sumRank = 0; let sumPPG = 0;
                    
                    tArr.forEach(t => {
                        sumRank += (TEAM_RANKS[t.team] || 999);
                        sumPPG += (TEAM_ALLTIME_PPG[t.team] || 0);
                    });
                    
                    let avgRank = sumRank / nTeams;
                    let avgPPG = sumPPG / nTeams;
                    
                    let top3SumRank = 0;
                    let top3Count = Math.min(3, nTeams);
                    for(let i=0; i<top3Count; i++) {
                        top3SumRank += (TEAM_RANKS[tArr[i].team] || 999);
                    }
                    let avgTop3Rank = top3SumRank / top3Count;
                    
                    strengthData.push({
                        season: season,
                        name: getSeasonName(season),
                        nTeams: nTeams,
                        avgRank: avgRank,
                        avgTop3Rank: avgTop3Rank,
                        avgPPG: avgPPG,
                        index: avgPPG * 50 
                    });
                });
                
                currentStrengthData = strengthData;
                sortStrength('index', true);
                
                document.getElementById('strength-loading').classList.add('hidden');
                document.getElementById('strength-results').classList.remove('hidden');
            }, 100);
        }

        function sortStrength(col, forceDesc = false) {
            if (forceDesc) { currentStrengthSort.col = col; currentStrengthSort.asc = false; }
            else if (currentStrengthSort.col === col) { currentStrengthSort.asc = !currentStrengthSort.asc; }
            else { currentStrengthSort.col = col; currentStrengthSort.asc = false; }
            
            currentStrengthData.sort((a, b) => {
                let valA = a[col], valB = b[col];
                if (typeof valA === 'string') return currentStrengthSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                return currentStrengthSort.asc ? valA - valB : valB - valA;
            });
            
            let html = currentStrengthData.map(r => `
                <tr class="hover:bg-slate-50">
                    <td class="px-4 py-3 font-medium">${r.name}</td>
                    <td class="px-4 py-3 text-center">${r.nTeams}</td>
                    <td class="px-4 py-3 text-center font-mono ${r.avgRank < 10 ? 'text-emerald-600 font-bold' : 'text-slate-500'}">${r.avgRank.toFixed(1)}</td>
                    <td class="px-4 py-3 text-center font-mono ${r.avgTop3Rank < 5 ? 'text-emerald-600 font-bold' : 'text-slate-500'}">${r.avgTop3Rank.toFixed(1)}</td>
                    <td class="px-4 py-3 text-center font-mono font-bold text-blue-600 text-lg bg-blue-50/50">${r.index.toFixed(1)}</td>
                </tr>
            `).join('');
            
            document.getElementById('strength-table-body').innerHTML = html;
        }

        // --- Analys: GULDSTRIDEN ---
        function runGoldRaceAnalysis() {
            document.getElementById('goldrace-loading').classList.remove('hidden');
            document.getElementById('goldrace-results').classList.add('hidden');
            
            setTimeout(() => {
                let allSeasonsData = []; let leaderCounts = []; let clinchData = [];

                SEASONS.forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && m.Omgång !== "" && !m.Annullerad);
                    if (sMatches.length === 0) return;

                    let roundSet = new Set();
                    sMatches.forEach(m => roundSet.add(String(m.Omgång).trim().toUpperCase()));
                    let rounds = Array.from(roundSet).sort((a, b) => {
                        let aIsM = a.startsWith('M'); let bIsM = b.startsWith('M');
                        if (aIsM && !bIsM) return 1; if (!aIsM && bIsM) return -1;
                        let aNum = parseInt(a.replace('M', '')) || 0; let bNum = parseInt(b.replace('M', '')) || 0;
                        return aNum - bNum;
                    });

                    if (rounds.length < 2) return;

                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;
                    let isMSeriesSeason = ["67", "68", "1991", "1992"].includes(String(season));
                    let useGoalRatio = parseInt(extractYear(null, getSeasonName(season)).substring(0,4)) < 1940;

                    let sTeams = new Set();
                    sMatches.forEach(m => { sTeams.add(m.Hemmalag); sTeams.add(m.Bortalag); });

                    let leadersPerRound = [];
                    
                    for (let i = 0; i < rounds.length; i++) {
                        let currentRound = rounds[i];
                        let isMasterPhase = currentRound.startsWith("M");
                        
                        let rTable = {};
                        sTeams.forEach(t => { rTable[t] = { team: t, pts: 0, gd: 0, gf: 0, ga: 0, pld: 0 }; });
                        
                        let matchesUpTo = sMatches.filter(m => {
                            let mRound = String(m.Omgång).trim().toUpperCase();
                            return rounds.indexOf(mRound) <= i;
                        });

                        matchesUpTo.forEach(m => {
                            // --- NY DÖRRVAKT: Mjuk radering för tabellen ---
                            if (m.Annullerad) return;
                            let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                            if (isNaN(hm) || isNaN(bm)) { hm = 0; bm = 0; }
                            
                            let nTxt = String(m.NOT).toUpperCase();
                            let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                            let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                            
                            rTable[m.Hemmalag].gf += hm; rTable[m.Bortalag].gf += bm;
                            rTable[m.Hemmalag].ga += bm; rTable[m.Bortalag].ga += hm;
                            rTable[m.Hemmalag].gd += (hm - bm); rTable[m.Bortalag].gd += (bm - hm);
                            rTable[m.Hemmalag].pld++; rTable[m.Bortalag].pld++;

                            if (isWOH) { rTable[m.Hemmalag].pts += ptsForWin; }
                            else if (isWOB) { rTable[m.Bortalag].pts += ptsForWin; }
                            else if (hm > bm) { rTable[m.Hemmalag].pts += ptsForWin; }
                            else if (hm < bm) { rTable[m.Bortalag].pts += ptsForWin; }
                            else { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                        });

                        let applyStartPts = isMSeriesSeason && isMasterPhase;
                        if (applyStartPts) {
                            Object.values(rTable).forEach(t => { let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team]; if (mInfo && mInfo.start_pts) t.pts += mInfo.start_pts; });
                        } else if (!isMSeriesSeason) {
                            Object.values(rTable).forEach(t => { 
                                let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team]; 
                                if (mInfo && mInfo.start_pts < 0) {
                                    let adj = mInfo.start_pts;
                                    if (adj === -3 && ptsForWin === 2) adj = -2;
                                    t.pts += adj;
                                }
                            });
                        }

                        let tArr = Object.values(rTable).filter(r => r.pld > 0);
                        tArr.sort((a, b) => {
                            if (b.pts !== a.pts) return b.pts - a.pts;
                            if (useGoalRatio) {
                                let ratioA = a.ga === 0 ? (a.gf > 0 ? 999 : 0) : a.gf / a.ga; let ratioB = b.ga === 0 ? (b.gf > 0 ? 999 : 0) : b.gf / b.ga;
                                if (ratioB !== ratioA) return ratioB - ratioA;
                            } else { if (b.gd !== a.gd) return b.gd - a.gd; }
                            return b.gf - a.gf;
                        });

                        leadersPerRound.push({ round: currentRound, leader: tArr[0], second: tArr[1] });
                    }

                    if(leadersPerRound.length < 2) return;

                    let winner = leadersPerRound[leadersPerRound.length - 1].leader.team;
                    let leaderBeforeLast = leadersPerRound[leadersPerRound.length - 2].leader.team;

                    let clinchedRound = null;
                    for (let i = 0; i < leadersPerRound.length; i++) {
                        let ld = leadersPerRound[i].leader; let sec = leadersPerRound[i].second;
                        let roundsRemaining = rounds.length - 1 - i;
                        let maxPtsSecondCanGet = sec ? (sec.pts + (roundsRemaining * ptsForWin)) : 0;
                        if (sec && ld.pts > maxPtsSecondCanGet) { clinchedRound = leadersPerRound[i].round; break; }
                    }

                    let tCounts = {}; leadersPerRound.forEach(r => { tCounts[r.leader.team] = (tCounts[r.leader.team] || 0) + 1; });

                    if (winner !== leaderBeforeLast) { allSeasonsData.push({ type: 'LATE_WINNER', seasonName: getSeasonName(season), winner: winner, passed: leaderBeforeLast }); }
                    clinchData.push({ seasonName: getSeasonName(season), winner: winner, clinchedRound: clinchedRound || "Sista omgången", roundsLeft: clinchedRound ? (rounds.length - 1 - rounds.indexOf(clinchedRound)) : 0 });
                    Object.keys(tCounts).forEach(t => { leaderCounts.push({ team: t, seasonName: getSeasonName(season), ledRounds: tCounts[t], won: (t === winner) }); });
                });

                let lateWinnersHTML = allSeasonsData.filter(d => d.type === 'LATE_WINNER').map(d => `<tr class="hover:bg-slate-50"><td class="p-3 font-medium">${d.seasonName}</td><td class="p-3 font-bold text-yellow-600">${d.winner}</td><td class="p-3 text-rose-600">${d.passed}</td></tr>`).join('');
                document.getElementById('gr-late-winners').innerHTML = lateWinnersHTML || '<tr><td colspan="3" class="p-3 text-center text-slate-500">Inga sena guldryck hittades.</td></tr>';

                let mostLeadHTML = [...leaderCounts].sort((a,b) => b.ledRounds - a.ledRounds).slice(0,10).map((d,i) => `<tr class="hover:bg-slate-50"><td class="p-3 text-slate-400 font-bold">${i+1}</td><td class="p-3 font-medium ${d.won?'text-yellow-600':'text-slate-800'}">${d.team} ${d.won?'🥇':''}</td><td class="p-3 text-slate-500 text-xs">${d.seasonName}</td><td class="p-3 text-center font-bold text-lg text-blue-600">${d.ledRounds}</td></tr>`).join('');
                document.getElementById('gr-most-lead').innerHTML = mostLeadHTML;

                let mostLeadNoWinHTML = [...leaderCounts].filter(d => !d.won).sort((a,b) => b.ledRounds - a.ledRounds).slice(0,10).map((d,i) => `<tr class="hover:bg-slate-50"><td class="p-3 text-slate-400 font-bold">${i+1}</td><td class="p-3 font-medium text-rose-600">${d.team}</td><td class="p-3 text-slate-500 text-xs">${d.seasonName}</td><td class="p-3 text-center font-bold text-lg text-rose-600">${d.ledRounds}</td></tr>`).join('');
                document.getElementById('gr-most-lead-nowin').innerHTML = mostLeadNoWinHTML;

                let leastLeadWinHTML = [...leaderCounts].filter(d => d.won).sort((a,b) => a.ledRounds - b.ledRounds).slice(0,10).map((d,i) => `<tr class="hover:bg-slate-50"><td class="p-3 text-slate-400 font-bold">${i+1}</td><td class="p-3 font-medium text-emerald-600">${d.team} 🥇</td><td class="p-3 text-slate-500 text-xs">${d.seasonName}</td><td class="p-3 text-center font-bold text-lg text-emerald-600">${d.ledRounds}</td></tr>`).join('');
                document.getElementById('gr-least-lead-win').innerHTML = leastLeadWinHTML;

                let clinchHTML = clinchData.sort((a,b) => b.roundsLeft - a.roundsLeft).map(d => `<tr class="hover:bg-slate-50"><td class="p-3 font-medium text-slate-600">${d.seasonName}</td><td class="p-3 font-bold text-slate-800">${d.winner}</td><td class="p-3 text-center font-mono">${d.clinchedRound}</td><td class="p-3 text-center font-bold ${d.roundsLeft>0?'text-emerald-600':'text-slate-400'}">${d.roundsLeft}</td></tr>`).join('');
                document.getElementById('gr-clinch').innerHTML = clinchHTML;

                document.getElementById('goldrace-loading').classList.add('hidden'); document.getElementById('goldrace-results').classList.remove('hidden');
            }, 100);
        }

        // --- Analys: Förutsägbarhet ---
        function toggleAnalysisMode(mode) {
            analysisMode = mode;
            document.getElementById('btn-mode-chart').className = mode === 'chart' ? "font-bold text-blue-600 border-b-2 border-blue-600 px-2 pb-1 transition-colors" : "font-medium text-slate-500 hover:text-blue-600 px-2 pb-1 transition-colors";
            document.getElementById('btn-mode-table').className = mode === 'table' ? "font-bold text-blue-600 border-b-2 border-blue-600 px-2 pb-1 transition-colors" : "font-medium text-slate-500 hover:text-blue-600 px-2 pb-1 transition-colors";
            if (mode === 'table') { document.getElementById('div-analysis-round').classList.remove('hidden'); document.getElementById('analysis-chart-container').classList.add('hidden'); document.getElementById('analysis-details').classList.add('hidden'); document.getElementById('analysis-comparison-table').classList.remove('hidden'); } 
            else { document.getElementById('div-analysis-round').classList.add('hidden'); document.getElementById('analysis-chart-container').classList.remove('hidden'); document.getElementById('analysis-comparison-table').classList.add('hidden'); }
        }

        function calculateSpearman(ranks1, ranks2, teams) {
            let n = teams.length; if (n <= 1) return 0;
            let sumDSq = 0; teams.forEach(t => { let d = (ranks1[t] || 0) - (ranks2[t] || 0); sumDSq += (d * d); });
            return 1 - ((6 * sumDSq) / (n * (n * n - 1)));
        }

        function calculateSubsetSpearman(currentRanks, finalRanks, teamsSubset) {
            let n = teamsSubset.length; if (n <= 1) return 0;
            let cRanks = {}; let sortedC = [...teamsSubset].sort((a, b) => currentRanks[a] - currentRanks[b]);
            sortedC.forEach((t, i) => { cRanks[t] = i + 1; });
            let fRanks = {}; let sortedF = [...teamsSubset].sort((a, b) => finalRanks[a] - finalRanks[b]);
            sortedF.forEach((t, i) => { fRanks[t] = i + 1; });
            
            let sumDSq = 0;
            teamsSubset.forEach(t => { let d = cRanks[t] - fRanks[t]; sumDSq += (d * d); });
            return 1 - ((6 * sumDSq) / (n * (n * n - 1)));
        }

        function runPredictabilityAnalysis() {
            const selection = document.getElementById('analysis-season').value; const focus = document.getElementById('analysis-focus').value;
            if(!selection) { alert("Välj en säsong eller epok att analysera."); return; }
            document.getElementById('analysis-details').classList.add('hidden'); 
            let seasonsToAnalyze = [];

            if (selection === "ALL_SEASONS") { seasonsToAnalyze = [...SEASONS].reverse(); document.getElementById('analysis-warning').classList.add('hidden'); } 
            else if (selection.startsWith("EPOCH_CUSTOM_")) { let epoch = selection.replace("EPOCH_CUSTOM_", ""); seasonsToAnalyze = CUSTOM_EPOCHS[epoch]; if (analysisMode === 'chart') { document.getElementById('analysis-warning').innerText = `Analyserar egen epok: ${epoch}. Detta är ett genomsnitt av ${seasonsToAnalyze.length} säsonger.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-blue-800', 'bg-blue-50'); document.getElementById('analysis-warning').classList.add('text-blue-800', 'bg-blue-50'); } else { document.getElementById('analysis-warning').classList.add('hidden'); } } 
            else if (selection.startsWith("EPOCH_DECADE_")) { let epoch = selection.replace("EPOCH_DECADE_", ""); seasonsToAnalyze = DECADES[epoch]; if (analysisMode === 'chart') { document.getElementById('analysis-warning').innerText = `Analyserar årtionde: ${epoch}. Detta är ett genomsnitt av ${seasonsToAnalyze.length} säsonger.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-blue-800', 'bg-blue-50'); document.getElementById('analysis-warning').classList.add('text-blue-800', 'bg-blue-50'); } else { document.getElementById('analysis-warning').classList.add('hidden'); } } 
            else { seasonsToAnalyze = [selection]; document.getElementById('analysis-warning').classList.add('hidden'); }

            if (analysisMode === 'table') {
                document.getElementById('analysis-chart-container').classList.add('hidden'); document.getElementById('analysis-details').classList.add('hidden'); document.getElementById('analysis-comparison-table').classList.remove('hidden');
                const targetRound = parseInt(document.getElementById('analysis-round').value) || 10; let tableData = [];

                seasonsToAnalyze.forEach(season => {
                    // --- NY DÖRRVAKT I FILTRET: Exkluderar annullerade matcher direkt! ---
                    let sMatches = MATCH_DATA.filter(m => !m.Annullerad && String(m.Säs) === String(season) && m.Omgång !== "" && !isNaN(parseInt(m.Omgång)));
                    if (sMatches.length === 0) return;
                    let maxRound = 0; sMatches.forEach(m => { maxRound = Math.max(maxRound, parseInt(m.Omgång)); });
                    if (maxRound < targetRound) return; 
                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;

                    const getTableAtRound = (rnd) => {
                        let table = {}; sMatches.forEach(m => { [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0 }; }); });
                        sMatches.filter(m => parseInt(m.Omgång) <= rnd).forEach(m => {
                            let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                            let nTxt = String(m.NOT).toUpperCase();
                            let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                            let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                            
                            if (isNaN(hm) || isNaN(bm)) { hm=0; bm=0; }
                            table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm; table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                            if (isWOH) { table[m.Hemmalag].pts += ptsForWin; } else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                            else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; } else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                            else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                        });
                        
                        Object.values(table).forEach(t => {
                            let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                            if (mInfo && mInfo.start_pts < 0) {
                                let adj = mInfo.start_pts;
                                if (adj === -3 && ptsForWin === 2) adj = -2;
                                t.pts += adj;
                            }
                        });
                        
                        let arr = Object.values(table); arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                        let rankMap = {}; arr.forEach((r, i) => { rankMap[r.team] = i + 1; }); return { ranks: rankMap, sortedArray: arr };
                    };

                    const finalTable = getTableAtRound(maxRound); const targetTable = getTableAtRound(targetRound);
                    let teamsToAnalyze = Object.keys(finalTable.ranks);
                    if (focus === 'top') teamsToAnalyze = finalTable.sortedArray.slice(0, 3).map(r => r.team);
                    else if (focus === 'bottom') teamsToAnalyze = finalTable.sortedArray.slice(-3).map(r => r.team);

                    let totalError = 0; teamsToAnalyze.forEach(t => { totalError += Math.abs(targetTable.ranks[t] - finalTable.ranks[t]); });
                    let mae = totalError / teamsToAnalyze.length; 
                    
                    let spearman = focus === 'all' ? calculateSpearman(targetTable.ranks, finalTable.ranks, teamsToAnalyze) : calculateSubsetSpearman(targetTable.ranks, finalTable.ranks, teamsToAnalyze);
                    
                    tableData.push({ season: season, name: getSeasonName(season), mae: mae, spearman: spearman });
                });

                if (tableData.length === 0) {
                    document.getElementById('analysis-warning').innerText = `Kunde inte hitta data för omgång ${targetRound} i de valda säsongerna.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-blue-800', 'bg-blue-50'); document.getElementById('analysis-warning').classList.add('text-amber-800', 'bg-amber-50'); document.getElementById('analysis-comparison-table').classList.add('hidden');
                } else {
                    document.getElementById('comparison-title').innerText = `Jämförelse vid omgång ${targetRound}`;
                    
                    let avgMae = (tableData.reduce((sum, d) => sum + d.mae, 0) / tableData.length).toFixed(2);
                    let avgSpearman = (tableData.reduce((sum, d) => sum + d.spearman, 0) / tableData.length).toFixed(3);
                    let summaryRow = `<tr class="bg-blue-50 border-b-2 border-blue-200"><td class="p-3 font-bold text-blue-800">Snitt (Vald period)</td><td class="p-3 text-center font-bold text-blue-800 font-mono">${avgMae}</td><td class="p-3 text-center font-bold text-blue-800 font-mono">${avgSpearman}</td></tr>`;
                    
                    let html = summaryRow + tableData.map(d => `<tr class="hover:bg-slate-50 border-b border-slate-100"><td class="p-3 font-medium">${d.name}</td><td class="p-3 text-center font-mono ${d.mae < 1.0 ? 'text-emerald-600 font-bold' : ''}">${d.mae.toFixed(2)}</td><td class="p-3 text-center font-mono ${d.spearman > 0.8 ? 'text-emerald-600 font-bold' : ''}">${d.spearman.toFixed(3)}</td></tr>`).join('');
                    document.getElementById('comparison-body').innerHTML = html;
                }
                document.getElementById('analysis-results').classList.remove('hidden'); return; 
            }

            // --- CHART MODE ---
            document.getElementById('analysis-comparison-table').classList.add('hidden'); document.getElementById('analysis-chart-container').classList.remove('hidden');
            let allErrors = []; globalAnalysisData = {}; 

           seasonsToAnalyze.forEach(season => {
                let sMatches = MATCH_DATA.filter(m => !m.Annullerad && String(m.Säs) === String(season) && m.Omgång !== "" && !isNaN(parseInt(m.Omgång)));
                if (sMatches.length === 0) return; 
                const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;
                let maxRound = 0; sMatches.forEach(m => { maxRound = Math.max(maxRound, parseInt(m.Omgång)); });

                const getTableAtRound = (rnd) => {
                    let table = {}; sMatches.forEach(m => { [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0 }; }); });
                    sMatches.filter(m => parseInt(m.Omgång) <= rnd).forEach(m => {
                        let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                        let nTxt = String(m.NOT).toUpperCase();
                        let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                        
                        if (isNaN(hm) || isNaN(bm)) { hm=0; bm=0; }
                        table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm; table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                        if (isWOH) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                        else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                        else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                    });
                    
                    Object.values(table).forEach(t => {
                        let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            if (adj === -3 && ptsForWin === 2) adj = -2;
                            t.pts += adj;
                        }
                    });
                    
                    let arr = Object.values(table); arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                    let rankMap = {}; arr.forEach((r, i) => { rankMap[r.team] = i + 1; }); return { ranks: rankMap, sortedArray: arr };
                };

                // --- NY VAKT: 50%-SPÄRREN ---
                const isRoundValid = (rnd) => {
                    let mInRnd = sMatches.filter(m => parseInt(m.Omgång) === rnd);
                    let playedInRnd = mInRnd.filter(m => m.HM !== "" && m.HM !== null && m.HM !== undefined);
                    return mInRnd.length === 0 || playedInRnd.length >= (mInRnd.length / 2);
                };

                const finalTable = getTableAtRound(maxRound); const finalRanks = finalTable.ranks;
                let teamsToAnalyze = Object.keys(finalRanks);
                if (focus === 'top') teamsToAnalyze = finalTable.sortedArray.slice(0, 3).map(r => r.team);
                else if (focus === 'bottom') teamsToAnalyze = finalTable.sortedArray.slice(-3).map(r => r.team);

                let seasonErrors = []; let seasonDataObj = {};
                for (let r = 1; r <= maxRound; r++) {
                    
                    // --- DEN SKOTTSÄKRA SPÄRREN FÖR GRAFEN ---
                    let mInRnd = sMatches.filter(m => parseInt(m.Omgång) === r);
                    let playedInRnd = mInRnd.filter(m => m.HM !== "" && m.HM !== null && m.HM !== undefined);
                    let reqMatches = Object.keys(finalRanks).length / 4; // Minst 4 matcher för en 16-lagsserie
                    
                    if (playedInRnd.length < reqMatches) {
                        seasonErrors.push(null);
                        if (seasonsToAnalyze.length === 1) {
                            seasonDataObj[r] = { mae: null, spearman: null, teams: [] };
                        }
                        continue; 
                    }
                    // -----------------------------------------

                    let currentTable = getTableAtRound(r); let currentRanks = currentTable.ranks;
                    let totalError = 0; teamsToAnalyze.forEach(t => { totalError += Math.abs(currentRanks[t] - finalRanks[t]); });
                    let meanError = totalError / teamsToAnalyze.length; 
                    
                    let spearman = focus === 'all' ? calculateSpearman(currentRanks, finalRanks, teamsToAnalyze) : calculateSubsetSpearman(currentRanks, finalRanks, teamsToAnalyze);
                    
                    seasonErrors.push(meanError);
                    if (seasonsToAnalyze.length === 1) {
                        seasonDataObj[r] = { mae: meanError, spearman: spearman, teams: teamsToAnalyze.map(t => ({ name: t, currentRank: currentRanks[t], finalRank: finalRanks[t], diff: currentRanks[t] - finalRanks[t] })).sort((a,b) => a.currentRank - b.currentRank) };
                    }
                }

                allErrors.push(seasonErrors);
                if (seasonsToAnalyze.length === 1) globalAnalysisData = seasonDataObj;
            });

            if (allErrors.length === 0) {
                document.getElementById('analysis-warning').innerText = "Data saknas! Omgångar är inte ifyllda för valt år, analysen kan inte genomföras."; document.getElementById('analysis-warning').classList.remove('hidden', 'text-blue-800', 'bg-blue-50'); document.getElementById('analysis-warning').classList.add('text-amber-800', 'bg-amber-50'); document.getElementById('analysis-results').classList.remove('hidden'); document.getElementById('analysis-chart-container').classList.add('hidden'); if (analysisChartInstance) analysisChartInstance.destroy(); return;
            }

            let maxLen = Math.max(...allErrors.map(e => e.length)); let averagedErrors = [];
            for(let i=0; i<maxLen; i++) { let sum = 0, count = 0; allErrors.forEach(errArr => { if (errArr[i] !== undefined) { sum += errArr[i]; count++; } }); averagedErrors.push(sum / count); }

            let labels = Array.from({length: maxLen}, (_, i) => `Omg ${i+1}`);
            document.getElementById('analysis-results').classList.remove('hidden'); const ctx = document.getElementById('analysisChart').getContext('2d');
            if (analysisChartInstance) { analysisChartInstance.destroy(); }
            analysisChartInstance = new Chart(ctx, {
                type: 'line', data: { labels: labels, datasets: [{ label: 'Genomsnittligt Positionsfel (MAE)', data: averagedErrors, borderColor: '#2563eb', backgroundColor: 'rgba(37, 99, 235, 0.1)', borderWidth: 3, pointBackgroundColor: '#1e3a8a', pointHoverRadius: 8, pointHoverBackgroundColor: '#f59e0b', fill: true, tension: 0.3, spanGaps: true }] },
                options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { return ` MAE: ${c.parsed.y.toFixed(2)}`; } } } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Positionsfel' } }, x: { grid: { display: false } } },
                    onClick: (e, activeEls) => { if (seasonsToAnalyze.length > 1) { alert("Detaljerad tabell är endast tillgänglig när du granskar en enskild säsong, inte hela epoker/perioder."); return; } if (activeEls.length > 0) { const round = activeEls[0].index + 1; showAnalysisDetails(round); } }
                }
            });
        }

        function showAnalysisDetails(round) {
            const data = globalAnalysisData[round]; if (!data) return;
            document.getElementById('details-title').innerText = `Tabellstatus i omgång ${round}`; document.getElementById('details-mae').innerText = data.mae.toFixed(2); document.getElementById('details-spearman').innerText = data.spearman.toFixed(3);
            let html = data.teams.map(t => {
                let diffStr = '<span class="text-slate-500">-</span>';
                if (t.diff > 0) diffStr = `<span class="text-emerald-400 font-bold">+${t.diff}</span> <span class="text-[10px] text-emerald-200/70 uppercase tracking-widest">(Upp)</span>`;
                else if (t.diff < 0) diffStr = `<span class="text-rose-400 font-bold">${t.diff}</span> <span class="text-[10px] text-rose-200/70 uppercase tracking-widest">(Ner)</span>`;
                return `<tr class="hover:bg-slate-800 transition-colors"><td class="p-3 font-medium text-blue-200">${t.name}</td><td class="p-3 text-center">${t.currentRank}</td><td class="p-3 text-center text-emerald-300 font-semibold">${t.finalRank}</td><td class="p-3 text-center">${diffStr}</td></tr>`;
            }).join('');
            document.getElementById('details-body').innerHTML = html; document.getElementById('analysis-details').classList.remove('hidden'); document.getElementById('analysis-details').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        function changeSeasonLocal(selectId, dir) {
            let sel = document.getElementById(selectId);
            if (!sel) return;
            
            let newIdx = sel.selectedIndex + dir;
            // Förhindra att man bläddrar till en tom rad/väljare (t.ex. "-- Alla --") på index 0
            let minIdx = (sel.options.length > 0 && sel.options[0].value === "") ? 1 : 0; 
            
            if (newIdx >= minIdx && newIdx < sel.options.length) {
                sel.selectedIndex = newIdx;
                
                // Detta eldar av ett "change"-event i bakgrunden så att webbläsaren fattar 
                // att rullistan har ändrats och automatiskt kör igång dina tabell-ritar-funktioner
                sel.dispatchEvent(new Event('change'));
                
                // Specifika extra-anrop för Matchsök om du använder det där också:
                if (selectId === 'search-season') {
                    if (typeof updateSearchPhaseDropdown === 'function') updateSearchPhaseDropdown();
                    if (typeof performSearch === 'function') performSearch();
                }
            }
        }
        // ==========================================
        // NY FUNKTION: FREKVENS AV MATCHRESULTAT (Med HMF/HMA & Totala Mål!)
        // ==========================================
        if (typeof window.res_epoch === 'undefined') window.res_epoch = 'ALL';
        if (typeof window.res_mode === 'undefined') window.res_mode = 'full';

        function renderResultatAnalys() {
            let headEl = document.getElementById('results-head');
            let bodyEl = document.getElementById('results-body');
            if (!headEl || !bodyEl) return;

            if (typeof MATCH_DATA === 'undefined') {
                bodyEl.innerHTML = `<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500">Databasen laddades inte.</td></tr>`;
                return;
            }

            // 1. DYNAMISK EPOK-BYGGARE (Årtionden)
            let autoDecades = {};
            MATCH_DATA.forEach(bm => {
                let yr = parseInt(bm.År);
                if (!isNaN(yr)) {
                    let dec = Math.floor(yr / 10) * 10 + "-talet";
                    if (!autoDecades[dec]) autoDecades[dec] = [];
                    // Sparar årtalet i årtiondet
                    if (!autoDecades[dec].includes(String(yr))) autoDecades[dec].push(String(yr));
                }
            });

            let epochOptions = `<option value="ALL">Totalt (Alla säsonger)</option>`;
            
            if (typeof CUSTOM_EPOCHS !== 'undefined' && Object.keys(CUSTOM_EPOCHS).length > 0) {
                epochOptions += `<optgroup label="Egna Epoker">`;
                Object.keys(CUSTOM_EPOCHS).forEach(d => {
                    let sel = window.res_epoch === `EPOCH_CUSTOM_${d}` ? 'selected' : '';
                    epochOptions += `<option value="EPOCH_CUSTOM_${d}" ${sel}>${d}</option>`;
                });
                epochOptions += `</optgroup>`;
            }

            if (Object.keys(autoDecades).length > 0) {
                epochOptions += `<optgroup label="Årtionden">`;
                Object.keys(autoDecades).sort((a,b) => b.localeCompare(a)).forEach(d => {
                    let sel = window.res_epoch === `EPOCH_AUTO_${d}` ? 'selected' : '';
                    epochOptions += `<option value="EPOCH_AUTO_${d}" ${sel}>${d}</option>`;
                });
                epochOptions += `</optgroup>`;
            }

            // 2. RITA SIDHUVUD
            headEl.innerHTML = `
                <tr>
                    <th colspan="4" class="px-4 py-3 bg-slate-800 border-b border-slate-700 text-white rounded-tl-lg rounded-tr-lg">
                        <div class="flex flex-col lg:flex-row items-start lg:items-center gap-4 justify-between">
                            <span class="font-bold text-slate-200">Frekvens av matchresultat</span>
                            
                            <div class="flex flex-wrap gap-3 items-center">
                                <select onchange="window.res_epoch = this.value; renderResultatAnalys()" class="bg-slate-700 text-white text-xs font-bold p-1.5 rounded border border-slate-600 focus:ring-blue-500 focus:border-blue-500 cursor-pointer outline-none">
                                    ${epochOptions}
                                </select>
                                
                                <div class="flex flex-wrap gap-3 text-xs font-normal bg-slate-700 p-1.5 rounded border border-slate-600">
                                    <label class="flex items-center gap-1 cursor-pointer hover:text-white">
                                        <input type="radio" name="res_time" value="full" ${window.res_mode === 'full' ? 'checked' : ''} onclick="window.res_mode = 'full'; renderResultatAnalys()" class="text-blue-500 cursor-pointer"> 
                                        Slutresultat
                                    </label>
                                    <label class="flex items-center gap-1 cursor-pointer hover:text-white">
                                        <input type="radio" name="res_time" value="half1" ${window.res_mode === 'half1' ? 'checked' : ''} onclick="window.res_mode = 'half1'; renderResultatAnalys()" class="text-amber-500 cursor-pointer"> 
                                        1:a Halvlek
                                    </label>
                                    <label class="flex items-center gap-1 cursor-pointer hover:text-white">
                                        <input type="radio" name="res_time" value="half2" ${window.res_mode === 'half2' ? 'checked' : ''} onclick="window.res_mode = 'half2'; renderResultatAnalys()" class="text-emerald-500 cursor-pointer"> 
                                        2:a Halvlek
                                    </label>
                                </div>
                            </div>
                        </div>
                    </th>
                </tr>
                <tr>
                    <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-24">Resultat</th>
                    <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100">Antal Matcher</th>
                    <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100">Andel (%)</th>
                    <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-50 text-slate-600">Historik (Första - Senaste)</th>
                </tr>
            `;

            let resultsMap = {};
            let totalMatches = 0;
            let totalGoalsMap = {};
            let cleanSheets = 0;
            let doubleDigits = 0;
            let absoluteTotalGoals = 0; // NY VARIABEL FÖR ALLA MÅL

            // 3. LOOPA OCH SAMLA DATA
            MATCH_DATA.forEach(bm => {
                if (!bm) return;

                // --- NY DÖRRVAKT: Mjuk radering ---
                if (bm.Annullerad) return;

                let checkYear = String(bm.År || '').trim();
                let checkSas = String(bm.Säs || '').trim();
                let checkHybrid = checkYear ? checkYear + "/" + (parseInt(checkYear)+1).toString().slice(2) : ""; 

                if (window.res_epoch !== 'ALL') {
                    let validSeasons = [];
                    if (window.res_epoch.startsWith('EPOCH_CUSTOM_')) {
                        validSeasons = CUSTOM_EPOCHS[window.res_epoch.replace('EPOCH_CUSTOM_', '')] || [];
                    } else if (window.res_epoch.startsWith('EPOCH_AUTO_')) {
                        validSeasons = autoDecades[window.res_epoch.replace('EPOCH_AUTO_', '')] || [];
                    }
                    
                    let isMatch = validSeasons.includes(checkYear) || validSeasons.includes(checkSas) || validSeasons.includes(checkHybrid);
                    if (!isMatch) return;
                }

                let finalH, finalB;
                if (window.res_mode === 'half1') {
                    finalH = parseInt(bm.HMF);
                    finalB = parseInt(bm.BMF);
                } else if (window.res_mode === 'half2') {
                    finalH = parseInt(bm.HMA);
                    finalB = parseInt(bm.BMA);
                } else {
                    finalH = parseInt(bm.HM);
                    finalB = parseInt(bm.BM);
                }

                if (isNaN(finalH) || isNaN(finalB)) return;

                let sumGoals = finalH + finalB;
                absoluteTotalGoals += sumGoals; // LÄGGER TILL I TOTALEN

                if (!totalGoalsMap[sumGoals]) totalGoalsMap[sumGoals] = 0;
                totalGoalsMap[sumGoals]++;

                if (finalH === 0) cleanSheets++;
                if (finalB === 0) cleanSheets++;
                if (finalH >= 10) doubleDigits++;
                if (finalB >= 10) doubleDigits++;

                let high = Math.max(finalH, finalB);
                let low = Math.min(finalH, finalB);
                let resKey = `${high}-${low}`;
                
                if (!resultsMap[resKey]) resultsMap[resKey] = { key: resKey, count: 0, seasons: [] };
                
                resultsMap[resKey].count++;
                totalMatches++;

                let matchYear = parseInt(checkYear);
                if (!isNaN(matchYear)) resultsMap[resKey].seasons.push(matchYear);
            });

            // 4. BYGG TABELLERNA
            let resArr = Object.values(resultsMap).sort((a, b) => b.count - a.count);

            let mainTableHtml = resArr.map((r) => {
                let pct = ((r.count / totalMatches) * 100).toFixed(1);
                let minS = Math.min(...r.seasons);
                let maxS = Math.max(...r.seasons);
                let seasonText = (isFinite(minS) && isFinite(maxS)) ? (minS === maxS ? `${minS}` : `${minS} - ${maxS}`) : "Okänt";

                let barColor = window.res_mode === 'half1' ? 'bg-amber-500' : (window.res_mode === 'half2' ? 'bg-emerald-500' : 'bg-indigo-500');
                let textColor = window.res_mode === 'half1' ? 'text-amber-700' : (window.res_mode === 'half2' ? 'text-emerald-700' : 'text-indigo-700');

                return `
                <tr class="hover:bg-slate-50 border-b border-slate-50">
                    <td class="px-4 py-3 font-black ${textColor} text-lg">${r.key}</td>
                    <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-800">${r.count}</td>
                    <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-500">
                        <div class="flex items-center justify-between gap-2"><span>${pct}%</span><div class="w-20 h-2 bg-slate-200 rounded overflow-hidden flex-shrink-0"><div class="h-full ${barColor}" style="width: ${pct}%"></div></div></div>
                    </td>
                    <td class="px-4 py-3 border-l border-slate-100 font-bold text-slate-600">${seasonText}</td>
                </tr>`;
            }).join('');
            
            if (resArr.length === 0) mainTableHtml = `<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500 italic">Inga resultat hittades för detta val.</td></tr>`;

            let tgArr = Object.keys(totalGoalsMap).map(Number).sort((a, b) => a - b);
            let tgHtml = tgArr.map(g => {
                let pct = ((totalGoalsMap[g] / totalMatches) * 100).toFixed(1);
                let tColor = window.res_mode === 'half1' ? 'text-amber-600' : (window.res_mode === 'half2' ? 'text-emerald-600' : 'text-indigo-600');
                return `<tr class="border-b border-slate-50 hover:bg-slate-50"><td class="px-3 py-2 font-bold text-slate-700">${g} mål</td><td class="px-3 py-2 text-right font-bold ${tColor}">${totalGoalsMap[g]} <span class="text-xs text-slate-400 font-normal ml-1">(${pct}%)</span></td></tr>`;
            }).join('');
            if (tgArr.length === 0) tgHtml = `<tr><td colspan="2" class="px-3 py-4 text-center text-slate-400 italic">Ingen data</td></tr>`;

            let extColor = window.res_mode === 'half1' ? 'amber' : (window.res_mode === 'half2' ? 'emerald' : 'indigo');
            let avgGoals = totalMatches > 0 ? (absoluteTotalGoals / totalMatches).toFixed(2) : "0.00";
            
            let statsGrid = `
            <div class="p-6 bg-slate-50 border-t border-slate-200">
                <h4 class="font-bold text-slate-700 mb-4 text-lg">Sammanfattande Statistik <span class="text-sm font-normal text-slate-500 ml-2">(${totalMatches} st matcher)</span></h4>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
                        <div class="bg-slate-700 text-white px-4 py-2 font-bold text-sm">Fördelning: Antal mål i perioden</div>
                        <div class="max-h-64 overflow-y-auto">
                            <table class="w-full text-sm text-left">
                                <thead class="bg-slate-100 text-slate-500 sticky top-0"><tr><th class="px-3 py-2">Mål totalt</th><th class="px-3 py-2 text-right">Antal matcher</th></tr></thead>
                                <tbody>${tgHtml}</tbody>
                            </table>
                        </div>
                    </div>
                    <div class="flex flex-col gap-4">
                        <!-- NY BOX FÖR TOTALA MÅL OCH SNITT -->
                        <div class="bg-sky-50 rounded-lg border border-sky-100 p-4 shadow-sm flex items-center justify-between">
                            <div><div class="text-sky-500 text-xs font-bold uppercase tracking-wider">Målproduktion</div><div class="text-sky-900 font-black text-lg">Totalt antal mål</div><div class="text-xs text-sky-600 mt-1">Snitt per vald period: <span class="font-bold">${avgGoals} mål</span></div></div>
                            <div class="text-3xl font-black text-sky-600">${absoluteTotalGoals} <span class="text-sm font-normal text-sky-500">st</span></div>
                        </div>

                        <div class="bg-${extColor}-50 rounded-lg border border-${extColor}-100 p-4 shadow-sm flex items-center justify-between">
                            <div><div class="text-${extColor}-400 text-xs font-bold uppercase tracking-wider">Defensiv styrka</div><div class="text-${extColor}-900 font-black text-lg">Hållna nollor</div></div>
                            <div class="text-3xl font-black text-${extColor}-600">${cleanSheets} <span class="text-sm font-normal text-${extColor}-400">ggr</span></div>
                        </div>
                        <div class="bg-red-50 rounded-lg border border-red-100 p-4 shadow-sm flex items-center justify-between">
                            <div><div class="text-red-500 text-xs font-bold uppercase tracking-wider">Offensiv kross</div><div class="text-red-900 font-black text-lg">Tvåsiffrigt antal mål</div></div>
                            <div class="text-3xl font-black text-red-600">${doubleDigits} <span class="text-sm font-normal text-red-500">ggr</span></div>
                        </div>
                    </div>
                </div>
            </div>
            `;

            bodyEl.innerHTML = mainTableHtml;
            if (totalMatches > 0) bodyEl.insertAdjacentHTML('beforeend', `<tr><td colspan="4" class="p-0">${statsGrid}</td></tr>`);
        }

        // ==========================================
        // NY FUNKTION: MÅLVAKTER & DOMARE (Med nummertvätt för UI och Med Klickbar Sortering)
        // ==========================================
        if (typeof window.gkref_mode === 'undefined') window.gkref_mode = 'gk';
        if (typeof window.gkref_fas === 'undefined') window.gkref_fas = 'ALL';
        if (typeof window.gkref_sortCol === 'undefined') window.gkref_sortCol = 'default';
        if (typeof window.gkref_sortAsc === 'undefined') window.gkref_sortAsc = false;
        if (typeof window.gkref_lastMode === 'undefined') window.gkref_lastMode = 'gk';

        // Global funktion för att hantera klick på tabellrubriker
        window.doSortGkRef = function(col) {
            if (window.gkref_sortCol === col) {
                window.gkref_sortAsc = !window.gkref_sortAsc; // Vänd håll om man klickar igen
            } else {
                window.gkref_sortCol = col;
                window.gkref_sortAsc = false; // Standard är fallande (högst först)
            }
            renderGkRef();
        };

        // --- NY KOD: GLOBAL FLAGGA OCH KNAPP-FUNKTION (Spöksaken) ---
        window.forceIncludeAnnulled = false;

        window.toggleAnnulledMatches = function() {
            // 1. Läs av checkboxen
            window.forceIncludeAnnulled = document.getElementById('toggle-annulled').checked;
            
            // 2. Tvinga dashboarden att rita om tabellen!
            renderGkRef(); 
        };
        // ------------------------------------------------------------

        function renderGkRef() {
            let headEl = document.getElementById('gkref-head');
            let bodyEl = document.getElementById('gkref-body');
            let searchQ = document.getElementById('gkref-search') ? document.getElementById('gkref-search').value.toLowerCase().trim() : "";
            
            if (!headEl || !bodyEl || typeof MATCH_DATA === 'undefined') return;

            // Återställ sortering om vi byter flik mellan Målvakt/Domare
            if (window.gkref_lastMode !== window.gkref_mode) {
                window.gkref_sortCol = 'default';
                window.gkref_sortAsc = false;
                window.gkref_lastMode = window.gkref_mode;
            }

            // Uppdatera UI
            document.getElementById('btn-mode-gk').className = window.gkref_mode === 'gk' ? "px-6 py-2 rounded-md font-bold text-sm transition-colors bg-white text-blue-700 shadow-sm" : "px-6 py-2 rounded-md font-bold text-sm transition-colors text-slate-500 hover:text-slate-800";
            document.getElementById('btn-mode-ref').className = window.gkref_mode === 'ref' ? "px-6 py-2 rounded-md font-bold text-sm transition-colors bg-white text-blue-700 shadow-sm" : "px-6 py-2 rounded-md font-bold text-sm transition-colors text-slate-500 hover:text-slate-800";
            if (document.getElementById('gkref-fas')) document.getElementById('gkref-fas').value = window.gkref_fas;

            let gkStats = {};
            let refStats = {};

            const cleanNameUI = (nameStr) => nameStr.replace(/\s\d+$/, '').trim();

            if (typeof window.gkref_season === 'undefined') window.gkref_season = 'ALL'; // Standardvärde fallback
            
            // ==========================================
            // ALIAS-ORDLISTA FÖR NAMNBYTEN
            // Skriv in: "Gammalt Namn": "Nytt Namn" / Ej längre använt här. SDe högt upp i filen.
            // ==========================================
            const NAME_ALIASES = {
                "Nilsson, Kalle": "Nyberg, Kalle", // Exempel: Kalle Nilsson bytte namn till Nyberg
                "Johansson, Anna": "Lindqvist, Anna",
                "Domargammal, Per": "Domarnytt, Per",
                // Lägg till fler vid behov, glöm inte kommatecken mellan raderna (förutom den sista)!
            };

            // LOOPA GENOM DATABASEN (Med alla tidigare filter)
            MATCH_DATA.forEach(bm => {
                if (!bm) return;
                
                // --- DEN DYNAMISKA DÖRRVAKTEN ---
                // Kastar bort matchen OM den är annullerad OCH vi INTE har klickat i rutan
                if (bm.Annullerad && !window.forceIncludeAnnulled) return;

                // NYTT: SÄSONGS-FILTER
                // Om användaren har valt ett specifikt år i rullistan, matcha det mot databasen
                let currentFlikSeason = document.getElementById('gkref-season') ? document.getElementById('gkref-season').value : window.gkref_season;
                let checkYear = String(bm.År || bm.Säsong || '').replace(/\.0$/, '').trim();
                let checkSas = String(bm.Säs || '').trim();
                let checkHybrid = checkYear ? checkYear + "/" + (parseInt(checkYear)+1).toString().slice(2) : ""; 
                
                if (currentFlikSeason !== 'ALL') {
                    if (checkYear !== currentFlikSeason && checkSas !== currentFlikSeason && checkHybrid !== currentFlikSeason) return; // Kasta bort om fel år
                }

                // (Befintlig kod för Fas-filter och mål-sammanställning fortsätter här...)
                
                if (window.gkref_fas !== 'ALL') {
                    let note = String(bm.NOT || '').toLowerCase();
                    if (window.gkref_fas === 'GRUND' && note.includes("mästerskap")) return; 
                    if (window.gkref_fas === 'MASTER' && !note.includes("mästerskap")) return;
                }

                let hm = parseInt(bm.HM);
                let b_m = parseInt(bm.BM); 
                if (isNaN(hm) || isNaN(b_m)) return;

                let yr = parseInt(String(bm.År || bm.Säsong || '').substring(0, 4));

                // --- MÅLVAKTER ---
                if (window.gkref_mode === 'gk') {
                    let hGk = bm.Hemmamålvakt ? String(bm.Hemmamålvakt).trim() : "";
                    if (NAME_ALIASES[hGk]) hGk = NAME_ALIASES[hGk]; // <-- NY RAD: Byt till nytt namn om det finns i listan
                    let hTeam = bm.Hemmalag ? String(bm.Hemmalag).trim() : "";
                    
                    if (hGk && hGk.toLowerCase() !== "okänd") {
                        let cleanSearchGk = cleanNameUI(hGk).toLowerCase();
                        let matchQ = searchQ === "" || cleanSearchGk.includes(searchQ) || hTeam.toLowerCase().includes(searchQ);
                        if (matchQ) {
                            if (!gkStats[hGk]) gkStats[hGk] = { matches: 0, cleanSheets: 0, conceded: 0, teams: new Set(), seasons: [] };
                            gkStats[hGk].matches++;
                            gkStats[hGk].conceded += b_m; 
                            if (b_m === 0) gkStats[hGk].cleanSheets++;
                            gkStats[hGk].teams.add(hTeam);
                            if (!isNaN(yr) && !gkStats[hGk].seasons.includes(yr)) gkStats[hGk].seasons.push(yr);
                        }
                    }
                    
                    let bGk = bm.Bortamålvakt ? String(bm.Bortamålvakt).trim() : "";
                    if (NAME_ALIASES[bGk]) bGk = NAME_ALIASES[bGk]; // <-- NY RAD HÄR OCKSÅ
                    let bTeam = bm.Bortalag ? String(bm.Bortalag).trim() : "";
                    
                    if (bGk && bGk.toLowerCase() !== "okänd") {
                        let cleanSearchGk = cleanNameUI(bGk).toLowerCase();
                        let matchQ = searchQ === "" || cleanSearchGk.includes(searchQ) || bTeam.toLowerCase().includes(searchQ);
                        if (matchQ) {
                            if (!gkStats[bGk]) gkStats[bGk] = { matches: 0, cleanSheets: 0, conceded: 0, teams: new Set(), seasons: [] };
                            gkStats[bGk].matches++;
                            gkStats[bGk].conceded += hm; 
                            if (hm === 0) gkStats[bGk].cleanSheets++;
                            gkStats[bGk].teams.add(bTeam);
                            if (!isNaN(yr) && !gkStats[bGk].seasons.includes(yr)) gkStats[bGk].seasons.push(yr);
                        }
                    }
                }

                // --- DOMARE ---
                if (window.gkref_mode === 'ref') {
                    let domare = bm.Domare ? String(bm.Domare).trim() : "";
                    if (NAME_ALIASES[domare]) domare = NAME_ALIASES[domare]; // <-- NY RAD FÖR DOMARE
                    let ort = bm.Domarort ? String(bm.Domarort).trim() : "";
                    
                    if (domare && domare.toLowerCase() !== "okänd") {
                        let cleanSearchRef = cleanNameUI(domare).toLowerCase();
                        let matchQ = searchQ === "" || cleanSearchRef.includes(searchQ) || ort.toLowerCase().includes(searchQ);
                        if (matchQ) {
                            let key = domare; 
                            if (!refStats[key]) refStats[key] = { matches: 0, hWin: 0, draw: 0, aWin: 0, orter: new Set(), seasons: [] };
                            
                            refStats[key].matches++;
                            if (hm > b_m) refStats[key].hWin++;
                            else if (hm < b_m) refStats[key].aWin++;
                            else refStats[key].draw++;
                            
                            if (ort) refStats[key].orter.add(ort);
                            if (!isNaN(yr) && !refStats[key].seasons.includes(yr)) refStats[key].seasons.push(yr);
                        }
                    }
                }
            });

            // Hjälpfunktioner för att rita sorteringspilar
            const thClass = "px-4 py-3 cursor-pointer hover:bg-slate-700 select-none transition-colors border-l border-slate-700";
            const getIcon = (col, defaultCol) => {
                if (window.gkref_sortCol === col) return window.gkref_sortAsc ? ' <span class="text-blue-400">🔼</span>' : ' <span class="text-blue-400">🔽</span>';
                if (window.gkref_sortCol === 'default' && col === defaultCol) return ' <span class="text-slate-400">🔽</span>';
                return ' <span class="text-slate-600 opacity-50">↕</span>'; // Visar att den är klickbar
            };

            // ----------------------------------------------------
            // RENDERA MÅLVAKTER
            // ----------------------------------------------------
            if (window.gkref_mode === 'gk') {
                headEl.innerHTML = `<tr>
                    <th class="px-4 py-3 w-12 text-center">#</th>
                    <th class="${thClass}" onclick="doSortGkRef('name')">Målvakt${getIcon('name', '')}</th>
                    <th class="px-4 py-3 border-l border-slate-700">Klubb(ar) (Vid filter)</th>
                    <th class="px-4 py-3 text-center border-l border-slate-700">Säsonger</th>
                    <th class="${thClass} text-center" onclick="doSortGkRef('matches')">Matcher${getIcon('matches', '')}</th>
                    <th class="${thClass} text-center text-emerald-400" onclick="doSortGkRef('cleanSheets')">Nollor${getIcon('cleanSheets', 'cleanSheets')}</th>
                    <th class="${thClass} text-center" onclick="doSortGkRef('conceded')">Insläppta${getIcon('conceded', '')}</th>
                    <th class="${thClass} text-center" onclick="doSortGkRef('pct')">Noll-procent${getIcon('pct', '')}</th>
                </tr>`;
                
                let arr = Object.keys(gkStats).map(k => {
                    return { rawName: k, displayName: cleanNameUI(k), ...gkStats[k] };
                });
                
                // --- DEN NYA DYNAMISKA SORTERINGEN ---
                arr.sort((a, b) => {
                    let valA, valB;
                    if (window.gkref_sortCol === 'name') {
                        valA = a.displayName; valB = b.displayName;
                        return window.gkref_sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    } else if (window.gkref_sortCol === 'matches') {
                        valA = a.matches; valB = b.matches;
                    } else if (window.gkref_sortCol === 'conceded') {
                        valA = a.conceded; valB = b.conceded;
                    } else if (window.gkref_sortCol === 'pct') {
                        valA = a.matches > 0 ? (a.cleanSheets/a.matches) : 0; 
                        valB = b.matches > 0 ? (b.cleanSheets/b.matches) : 0;
                    } else { // 'cleanSheets' eller 'default'
                        valA = a.cleanSheets; valB = b.cleanSheets;
                        // Extra sortering om nollorna är lika
                        if (valA === valB && window.gkref_sortCol === 'default') return b.matches - a.matches;
                    }
                    return window.gkref_sortAsc ? valA - valB : valB - valA;
                });

                bodyEl.innerHTML = arr.map((r, i) => {
                    let pct = ((r.cleanSheets / r.matches) * 100).toFixed(1);
                    let teamStr = Array.from(r.teams).join(', ');
                    let minS = Math.min(...r.seasons);
                    let maxS = Math.max(...r.seasons);
                    let sText = (isFinite(minS) && isFinite(maxS)) ? (minS === maxS ? `${minS}` : `${minS}-${maxS}`) : "-";
                    let finalName = typeof formatName === 'function' ? formatName(r.displayName) : r.displayName;

                    return `
                    <tr class="hover:bg-slate-50 border-b border-slate-100">
                        <td class="px-4 py-3 text-center font-bold text-slate-400">${i+1}</td>
                        
                        <!-- HÄR ÄR DEN MAGISKA LÄNKEN SOM ÖPPNAR MODALEN -->
                        <td class="px-4 py-3 font-bold text-slate-800 hover:text-blue-600 hover:underline cursor-pointer transition-colors" 
                            title="Klicka för att se karriär och åldersdata. Databas-ID: ${r.rawName}" 
                            onclick="openPersonModal('${r.rawName}', window.gkref_mode)">
                            ${finalName}
                        </td>
                        <!-- ============================================= -->

                        <td class="px-4 py-3 text-xs text-slate-500 font-medium">${teamStr}</td>
                        <td class="px-4 py-3 text-center text-xs text-slate-500">${sText}</td>
                        <td class="px-4 py-3 text-center font-medium">${r.matches}</td>
                        <td class="px-4 py-3 text-center font-black text-emerald-600 bg-emerald-50">${r.cleanSheets}</td>
                        <td class="px-4 py-3 text-center text-slate-600">${r.conceded}</td>
                        <td class="px-4 py-3 text-center font-bold text-slate-600">${pct}%</td>
                    </tr>`;
                }).join('');
                
                if (arr.length === 0) bodyEl.innerHTML = `<tr><td colspan="8" class="px-4 py-8 text-center text-slate-500">Inga målvakter hittades för denna kombination.</td></tr>`;
            }

            // ----------------------------------------------------
            // RENDERA DOMARE
            // ----------------------------------------------------
            else if (window.gkref_mode === 'ref') {
                headEl.innerHTML = `<tr>
                    <th class="px-4 py-3 w-12 text-center">#</th>
                    <th class="${thClass}" onclick="doSortGkRef('name')">Domare${getIcon('name', '')}</th>
                    <th class="px-4 py-3 border-l border-slate-700">Ort(er)</th>
                    <th class="px-4 py-3 text-center border-l border-slate-700">Säsonger</th>
                    <th class="${thClass} text-center" onclick="doSortGkRef('matches')">Matcher${getIcon('matches', 'matches')}</th>
                    <th class="${thClass} text-center" title="Hemmaseger" onclick="doSortGkRef('1')">1${getIcon('1', '')}</th>
                    <th class="${thClass} text-center" title="Oavgjort" onclick="doSortGkRef('X')">X${getIcon('X', '')}</th>
                    <th class="${thClass} text-center" title="Bortaseger" onclick="doSortGkRef('2')">2${getIcon('2', '')}</th>
                </tr>`;
                
                let arr = Object.keys(refStats).map(k => {
                    return { rawName: k, displayName: cleanNameUI(k), ...refStats[k] };
                });
                
                // --- DEN NYA DYNAMISKA SORTERINGEN ---
                arr.sort((a, b) => {
                    let valA, valB;
                    if (window.gkref_sortCol === 'name') {
                        valA = a.displayName; valB = b.displayName;
                        return window.gkref_sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    } else if (window.gkref_sortCol === '1') {
                        valA = a.hWin; valB = b.hWin;
                    } else if (window.gkref_sortCol === 'X') {
                        valA = a.draw; valB = b.draw;
                    } else if (window.gkref_sortCol === '2') {
                        valA = a.aWin; valB = b.aWin;
                    } else { // 'matches' eller 'default'
                        valA = a.matches; valB = b.matches;
                        if (valA === valB && window.gkref_sortCol === 'default') return a.displayName.localeCompare(b.displayName);
                    }
                    return window.gkref_sortAsc ? valA - valB : valB - valA;
                });

                bodyEl.innerHTML = arr.map((r, i) => {
                    let pct1 = ((r.hWin / r.matches) * 100).toFixed(0);
                    let pctx = ((r.draw / r.matches) * 100).toFixed(0);
                    let pct2 = ((r.aWin / r.matches) * 100).toFixed(0);
                    let ortStr = Array.from(r.orter).join(', ') || '-';
                    let minS = Math.min(...r.seasons);
                    let maxS = Math.max(...r.seasons);
                    let sText = (isFinite(minS) && isFinite(maxS)) ? (minS === maxS ? `${minS}` : `${minS}-${maxS}`) : "-";
                    let finalName = typeof formatName === 'function' ? formatName(r.displayName) : r.displayName;

                    return `
                    <tr class="hover:bg-slate-50 border-b border-slate-100">
                        <td class="px-4 py-3 text-center font-bold text-slate-400">${i+1}</td>
                        
                        <!-- NY KLICKBAR RAD FÖR DOMARE -->
                        <td class="px-4 py-3 font-bold text-slate-800 hover:text-blue-600 hover:underline cursor-pointer transition-colors" 
                            title="Klicka för att se detaljer. Databas-ID: ${r.rawName}" 
                            onclick="openPersonModal('${r.rawName}', 'ref')">
                            ${finalName}
                        </td>
                        
                        <td class="px-4 py-3 text-xs text-slate-500">${ortStr}</td>
                        <td class="px-4 py-3 text-center text-xs text-slate-500">${sText}</td>
                        <td class="px-4 py-3 text-center font-black text-slate-700 bg-slate-100">${r.matches}</td>
                        <td class="px-4 py-3 text-center text-emerald-600 font-medium">${r.hWin} <span class="text-[10px] text-slate-400 ml-1">(${pct1}%)</span></td>
                        <td class="px-4 py-3 text-center text-amber-500 font-medium">${r.draw} <span class="text-[10px] text-slate-400 ml-1">(${pctx}%)</span></td>
                        <td class="px-4 py-3 text-center text-sky-600 font-medium">${r.aWin} <span class="text-[10px] text-slate-400 ml-1">(${pct2}%)</span></td>
                    </tr>`;
                }).join('');

                if (arr.length === 0) bodyEl.innerHTML = `<tr><td colspan="8" class="px-4 py-8 text-center text-slate-500">Inga domare hittades för denna kombination.</td></tr>`;
            }
        }
        // ==========================================
        // MODAL & ÅLDERSMATEMATIK
        // ==========================================

        function calculateExactAge(birthDateString, referenceDateString) {
    if (!birthDateString) return "";
    
    let birthDate = new Date(birthDateString);
    if (isNaN(birthDate.getTime())) return "";

    let refDate = referenceDateString ? new Date(referenceDateString) : new Date();
    if (isNaN(refDate.getTime())) refDate = new Date();

    let age = refDate.getFullYear() - birthDate.getFullYear();
    let m = refDate.getMonth() - birthDate.getMonth();
    
    if (m < 0 || (m === 0 && refDate.getDate() < birthDate.getDate())) {
        age--;
    }
    
    return age >= 0 ? age : "";
}

        window.formatPersonName = function(name) {
                    if (!name) return "";
                    
                    // Tvätta bort alla siffror från namnsträngen (t.ex. "Sven 1" -> "Sven ")
                    let cleanName = name.replace(/[0-9]/g, '').trim();
                    
                    if (cleanName.includes(",")) {
                        let parts = cleanName.split(",");
                        // Sätt ihop och ta bort eventuella dubbla mellanslag som uppstått när siffran försvann
                        return (parts[1].trim() + " " + parts[0].trim()).replace(/\s+/g, ' ');
                    }
                    return cleanName.replace(/\s+/g, ' ');
                };

        function formatDateSv(dateStr) {
            if (!dateStr || dateStr.trim() === "") return "";
            try {
                let d = new Date(dateStr);
                if (isNaN(d.getTime())) return dateStr;
                let months = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"];
                return d.getDate() + " " + months[d.getMonth()] + " " + d.getFullYear();
            } catch(e) { return dateStr; }
        }

        function closePersonModal() {
            document.getElementById('person-modal').classList.add('hidden');
        }

        function openPersonModal(rawName, mode) {
            let infoSource = mode === 'gk' ? (typeof GK_INFO !== 'undefined' ? GK_INFO : {}) : (typeof REF_INFO !== 'undefined' ? REF_INFO : {});
// Slå upp datan med den exakta, otvättade originalnyckeln (t.ex. "Andersson, Sven 2")
let personData = infoSource[rawName] || {};

let fodd = personData.Född || null;
let avliden = personData.Avliden || null;
let fodelseAr = personData.År || null; 
let nyttNamn = personData.NyttNamn || null; 

// Vänd namnet till "Förnamn Efternamn" enbart för utskriften på bildskärmen
let formattedMainName = typeof window.formatPersonName === 'function' ? window.formatPersonName(rawName) : rawName;

if (nyttNamn) {
    let formattedNewName = typeof window.formatPersonName === 'function' ? window.formatPersonName(nyttNamn) : nyttNamn;
    document.getElementById('modal-name').innerText = `${formattedMainName} (${formattedNewName})`;
} else {
    document.getElementById('modal-name').innerText = formattedMainName;
}
            // 1. Datum & Ålder (Med 100-års spärr)
            let foddSv = fodd ? formatDateSv(fodd) : (fodelseAr ? fodelseAr : "");
            let avlidenSv = avliden ? formatDateSv(avliden) : "";
            let ageText = "";

            if (fodd) {
                if (avliden) {
                    ageText = `Född: ${foddSv} &nbsp;|&nbsp; Avled: ${avlidenSv} (Blev ${calculateExactAge(fodd, avliden)} år)`;
                } else {
                    let currentAge = calculateExactAge(fodd, new Date());
                    if (currentAge > 100) {
                        ageText = `Född: ${foddSv}`; 
                    } else {
                        ageText = `Född: ${foddSv} &nbsp;|&nbsp; Ålder just nu: ${currentAge} år`;
                    }
                }
            } else if (fodelseAr) {
                ageText = `Född år: ${fodelseAr}`;
            }

            document.getElementById('modal-age-text').innerHTML = ageText;

            // 2. Loopa matcher
            // NYTT: Lade till 'totGoals' för domarna
            let stats = { m: 0, v: 0, o: 0, f: 0, gm: 0, im: 0, nollor: 0, hWin: 0, draw: 0, aWin: 0, totGoals: 0 };
            let clubs = new Set();
            let personMatches = [];
            // --- NY RAD: Skapa ett Set för att samla unika säsonger ---
            let activeSeasons = new Set();

            MATCH_DATA.forEach(bm => {
                if (!bm) return;
                // --- NY DÖRRVAKT: Mjuk radering ---
                if (bm.Annullerad) return; 

                let checkYear = String(bm.År || '').trim();
                // ... din existerande kod ...
                let hm = parseInt(bm.HM);
                let b_m = parseInt(bm.BM); 
                if (isNaN(hm) || isNaN(b_m)) return;

                let hemmalag = bm.Hemmalag ? String(bm.Hemmalag).trim() : "";
                let bortalag = bm.Bortalag ? String(bm.Bortalag).trim() : "";
                let matchDate = bm.Datum ? String(bm.Datum).trim() : (String(bm.År) + "-06-15"); 
                let resStr = `${hm}–${b_m}`; 

                if (mode === 'gk') {
                    let hGk = bm.Hemmamålvakt ? String(bm.Hemmamålvakt).trim() : "";
                    let bGk = bm.Bortamålvakt ? String(bm.Bortamålvakt).trim() : "";
                    if (typeof NAME_ALIASES !== 'undefined') {
                        if (NAME_ALIASES[hGk]) hGk = NAME_ALIASES[hGk];
                        if (NAME_ALIASES[bGk]) bGk = NAME_ALIASES[bGk];
                    }
                    
                    let isHome = (hGk === rawName);
                    let isAway = (bGk === rawName);

                    // HÄR ÄR SÄKERHETSZONEN FÖR MÅLVAKTER
                    if (isHome || isAway) {
                        stats.m++;
                        
                        // --- NY KOD: Fånga säsongen för Målvakt ---
                        let currentSeason = bm.Säs ? String(bm.Säs).trim() : (bm.År ? String(bm.År).trim() : null);
                        if (currentSeason) activeSeasons.add(currentSeason);
                        // ------------------------------------------

                        let pTeam = isHome ? hemmalag : bortalag;
                        let oppTeam = isHome ? bortalag : hemmalag;
                        clubs.add(pTeam);

                        let pGoals = isHome ? hm : b_m;
                        let oppGoals = isHome ? b_m : hm;

                        if (pGoals > oppGoals) stats.v++;
                        else if (pGoals < oppGoals) stats.f++;
                        else stats.o++;

                        stats.gm += pGoals;
                        stats.im += oppGoals;
                        if (oppGoals === 0) stats.nollor++;

                        // --- NY KOD: Skapa ett spelarcentrerat resultat ---
                        let utfall = pGoals > oppGoals ? "(V)" : (pGoals < oppGoals ? "(F)" : "(O)");
                        let gkResStr = `${pGoals}–${oppGoals} ${utfall}`; 
                        // --------------------------------------------------

                        personMatches.push({ 
                        dateRaw: matchDate, 
                        dateSv: typeof window.formatDateSv === 'function' ? window.formatDateSv(matchDate) : formatDateSv(matchDate),
                        ha: isHome ? '(H)' : '(B)', 
                        pTeam: pTeam, 
                        opp: oppTeam, 
                        res: gkResStr 
                    });
                    }
                } else if (mode === 'ref') {
                    let ref = bm.Domare ? String(bm.Domare).trim() : "";
                    let ort = bm.Domarort ? String(bm.Domarort).trim() : ""; 
                    
                    if (typeof NAME_ALIASES !== 'undefined' && NAME_ALIASES[ref]) ref = NAME_ALIASES[ref];
                    
                    // HÄR ÄR SÄKERHETSZONEN FÖR DOMARE
                    if (ref === rawName) {
                        stats.m++;
                        
                        // --- NY KOD: Fånga säsongen för Domare ---
                        let currentSeason = bm.Säs ? String(bm.Säs).trim() : (bm.År ? String(bm.År).trim() : null);
                        if (currentSeason) activeSeasons.add(currentSeason);
                        // -----------------------------------------

                        stats.totGoals += (hm + b_m); 
                        
                        if (ort && ort.toLowerCase() !== "okänd" && ort !== "-") clubs.add(ort); 

                        if (hm > b_m) stats.hWin++;
                        else if (hm < b_m) stats.aWin++;
                        else stats.draw++;

                        personMatches.push({ dateRaw: matchDate, dateSv: formatDateSv(matchDate), matchStr: `${hemmalag} – ${bortalag}`, res: resStr });
                    }
                }
            });

            // 3. Klubbar/Orter och Tabellrad
            if (mode === 'gk') {
                document.getElementById('modal-clubs').innerText = Array.from(clubs).join(", ");
                document.getElementById('modal-stats-text').innerHTML = `<span class="font-bold text-slate-800">Aktiva säsonger: ${activeSeasons.size}</span><br>${stats.m} matcher. ${stats.im} insläppta mål. ${stats.nollor} nollor.`;
                document.getElementById('modal-tabellrad').innerHTML = `Tabellrad: &nbsp;<span class="tracking-widest font-mono">${stats.m} &nbsp;${stats.v} &nbsp;${stats.o} &nbsp;${stats.f} &nbsp;&nbsp;${stats.gm}–${stats.im}</span>`;
            } else {
                // Skriver ut ort om den finns, annars bara "Domare"
                let ortList = Array.from(clubs).join(", ");
                document.getElementById('modal-clubs').innerText = ortList ? `Domare från ${ortList}` : "Domare";
                
                // Skriver ut det totala antalet mål och AKTIVA SÄSONGER FÖR DOMARE
                document.getElementById('modal-stats-text').innerHTML = `<span class="font-bold text-slate-800">Aktiva säsonger: ${activeSeasons.size}</span><br>${stats.m} dömda matcher. Totalt ${stats.totGoals} mål i dessa matcher.`;
                document.getElementById('modal-tabellrad').innerHTML = `Tabellrad (1 X 2): &nbsp;<span class="tracking-widest font-mono">${stats.hWin} &nbsp;${stats.draw} &nbsp;${stats.aWin}</span>`;
            }

            // 4. Debut och Senaste (med Klubb info)
            personMatches.sort((a, b) => new Date(a.dateRaw) - new Date(b.dateRaw));

            if (personMatches.length > 0) {
                let debut = personMatches[0];
                let latest = personMatches[personMatches.length - 1];

                let debutAgeStr = fodd ? ` (${calculateExactAge(fodd, debut.dateRaw)} år)` : "";
                let latestAgeStr = fodd ? ` (${calculateExactAge(fodd, latest.dateRaw)} år)` : "";

                if (mode === 'gk') {
                    document.getElementById('modal-debut-text').innerHTML = `Debut: ${debut.dateSv} för <b>${debut.pTeam}</b> ${debut.ha} mot ${debut.opp} ${debut.res}.${debutAgeStr}`;
                    document.getElementById('modal-latest-text').innerHTML = `Senaste: ${latest.dateSv} för <b>${latest.pTeam}</b> ${latest.ha} mot ${latest.opp} ${latest.res}.${latestAgeStr}`;
                } else {
                    document.getElementById('modal-debut-text').innerHTML = `Debut: ${debut.dateSv}: ${debut.matchStr} ${debut.res}.${debutAgeStr}`;
                    document.getElementById('modal-latest-text').innerHTML = `Senaste: ${latest.dateSv}: ${latest.matchStr} ${latest.res}.${latestAgeStr}`;
                }
            } else {
                document.getElementById('modal-debut-text').innerHTML = "";
                document.getElementById('modal-latest-text').innerHTML = "";
            }

            document.getElementById('person-modal').classList.remove('hidden');
        }

        // ==========================================
// RITA UPP INOFFICIELLA MÄSTARBÄLTET (MULTIVERSUM)
// ==========================================
function renderMasterBelt() {
    if (typeof MASTER_BELT_DATA === 'undefined' || !MASTER_BELT_DATA.STRICT) return;
    renderBeltView('STRICT'); // Startar alltid i Original-läget
}

function renderBeltView(ruleKey) {
    if (!MASTER_BELT_DATA[ruleKey]) return;
    
    // Hantera knapp-designen (Gör klickad knapp blå)
    document.querySelectorAll('.belt-tab-btn').forEach(btn => {
        btn.classList.remove('bg-white', 'shadow-sm', 'text-blue-700');
        btn.classList.add('text-slate-500');
    });
    let activeBtn = document.getElementById('btn-belt-' + ruleKey.toLowerCase());
    if(activeBtn) {
        activeBtn.classList.remove('text-slate-500');
        activeBtn.classList.add('bg-white', 'shadow-sm', 'text-blue-700');
    }

    const data = MASTER_BELT_DATA[ruleKey];
    
    // 1. Nuvarande Mästare
    document.getElementById('belt-current-champ').innerText = data.current_champion || "VAKANT";
    let defenseText = data.current_defenses === 1 ? "1 spelad titelmatch just nu" : `${data.current_defenses} spelade titelmatcher i rad just nu`;
    if (!data.current_champion) defenseText = "Väntar på en avgörande match!";
    document.getElementById('belt-current-defenses').innerText = defenseText;

    // 2. Statistik och Historik
    let stats = {};
    let historyHtml = '';
    
    [...data.history].reverse().forEach(reign => {
        let team = reign.Lag;
        
        // Räkna inte statistik för tillfälliga vakanser
        if (team !== "VAKANT" && !reign.Status.includes("Dvala")) {
            if (!stats[team]) stats[team] = { totalMatches: 0, maxStreak: 0 };
            stats[team].totalMatches += reign.Titelmatcher;
            if (reign.Titelmatcher > stats[team].maxStreak) stats[team].maxStreak = reign.Titelmatcher;
        }

        // FÄRGMARKERINGAR FÖR EXIL OCH VAKANSER
        let rowClass = "hover:bg-slate-50 transition-colors";
        let titleMatchesDisplay = reign.Titelmatcher;
        let lagDisplay = `<span class="font-bold text-slate-800">${team}</span>`;
        let statusDisplay = reign.Status || "";

        if (reign.Status.includes("Dvala") || reign.Status.includes("Återkomst")) {
            rowClass = "bg-amber-50 text-amber-800 border-y border-amber-200 font-medium";
            lagDisplay = team;
            titleMatchesDisplay = "-";
        } else if (team === "VAKANT") {
            // Träffar BARA övergångsraden när ingen har bältet
            rowClass = "bg-rose-50 text-rose-800 border-y border-rose-200 font-bold tracking-wider";
            lagDisplay = team;
            titleMatchesDisplay = "⚠️";
        } else if (reign.Status.includes("Vinner Vakant")) {
            // Ger en subtil grön markering till laget som plockar upp det vakanta bältet
            rowClass = "bg-emerald-50 text-emerald-900 border-y border-emerald-100";
        }

        let displayDate = reign.Datum || reign.Säsong;
        let displayResult = reign.Resultat !== "-" ? `<span class="text-xs opacity-60 font-mono ml-1">(${reign.Resultat})</span>` : '';
        
        historyHtml += `
            <tr class="${rowClass}">
                <td class="p-3 text-sm">${displayDate}</td>
                <td class="p-3 text-sm">${reign.Omgång || '-'} ${displayResult} <div class="text-[10px] opacity-70 uppercase tracking-widest mt-0.5">${statusDisplay}</div></td>
                <td class="p-3">${lagDisplay}</td>
                <td class="p-3 font-black text-center text-lg">${titleMatchesDisplay}</td>
            </tr>
        `;
    });
    
    document.getElementById('belt-history-body').innerHTML = historyHtml || `<tr><td colspan="4" class="p-6 text-center text-slate-500">Kunde inte ladda historik.</td></tr>`;

    // 3. Bygg Topplistor (exkludera "VAKANT")
    let topTotal = Object.entries(stats).sort((a, b) => b[1].totalMatches - a[1].totalMatches).slice(0, 10);
    document.getElementById('belt-top-total').innerHTML = topTotal.map((item, i) => `
        <div class="flex justify-between items-center py-2 ${i !== topTotal.length - 1 ? 'border-b border-slate-100' : ''}">
            <div class="flex items-center gap-3"><span class="text-slate-400 text-sm font-mono w-4">${i + 1}</span><span class="font-medium text-slate-700">${item[0]}</span></div>
            <span class="font-bold text-blue-700">${item[1].totalMatches}</span>
        </div>
    `).join('');

    let topStreak = Object.entries(stats).sort((a, b) => b[1].maxStreak - a[1].maxStreak).slice(0, 10);
    document.getElementById('belt-top-streak').innerHTML = topStreak.map((item, i) => `
        <div class="flex justify-between items-center py-2 ${i !== topStreak.length - 1 ? 'border-b border-slate-100' : ''}">
            <div class="flex items-center gap-3"><span class="text-slate-400 text-sm font-mono w-4">${i + 1}</span><span class="font-medium text-slate-700">${item[0]}</span></div>
            <span class="font-bold text-blue-700">${item[1].maxStreak}</span>
        </div>
    `).join('');
}

// ==========================================
// VÄCK MÄSTARBÄLTET NÄR SIDAN LADDAS
// ==========================================
window.addEventListener('DOMContentLoaded', () => {
    // Kör funktionen så fort webbläsaren har läst in hela HTML-sidan
    if (typeof renderMasterBelt === 'function') {
        renderMasterBelt();
    }
});

        // ==========================================
// INJICERA SÄSONGENS PROFILER I RULLISTAN
// ==========================================
window.addEventListener('DOMContentLoaded', () => {
    // Vi väntar lite (1 sekund) så att grundkoden hinner fylla listan med vanliga lag först
    setTimeout(() => {
        const select = document.getElementById('streaks-team');
        if (select) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = "--- SÄSONGENS PROFILER ---";
            optgroup.innerHTML = `
                <option value="PROFILE_CHAMPS" class="font-bold text-amber-700">🏆 Årets Mästare</option>
                <option value="PROFILE_DEFENDING" class="font-bold text-blue-700">🛡️ Regerande Mästare</option>
                <option value="PROFILE_PROMOTED" class="font-bold text-emerald-700">⭐ Nykomlingar</option>
                <option value="PROFILE_RELEGATED" class="font-bold text-rose-700">🔻 Nedflyttade</option>
            `;
            select.appendChild(optgroup);
        }
    }, 1000); 
});

    </script>
    <!-- MODAL: Personinformation (Målvakter & Domare) -->
<div id="person-modal" class="fixed inset-0 bg-slate-900 bg-opacity-75 z-[9999] hidden flex items-center justify-center p-4 backdrop-blur-sm transition-opacity">
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden relative border border-slate-200">
        
        <!-- Header (Svart) -->
        <div class="bg-slate-900 text-white px-6 py-5 relative">
            <div class="flex justify-between items-start">
                <div>
                    <h3 id="modal-name" class="text-2xl font-bold tracking-tight mb-1">Namn</h3>
                    <!-- Klubbar och Ålder uppflyttat hit -->
                    <div id="modal-clubs" class="text-sm font-semibold text-slate-300 mb-2"></div>
                    <div id="modal-age-text" class="text-sm text-slate-400"></div>
                </div>
                <button onclick="closePersonModal()" class="text-slate-400 hover:text-white transition-colors p-1 bg-slate-800 hover:bg-slate-700 rounded-lg">
                    <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
        </div>

        <!-- Body (Ren textdesign) -->
        <div class="p-6 overflow-y-auto bg-white flex-grow text-slate-900 text-base sm:text-lg leading-relaxed">
            <div id="modal-stats-text" class="mb-1"></div>
            <div id="modal-tabellrad" class="mb-8"></div>

            <div id="modal-debut-text" class="mb-2"></div>
            <div id="modal-latest-text"></div>
        </div>
    </div>
</div>
</body>
</html>
"""



# ---------------------------------------------------------
# KONVERTERA DEN NYA DATAN TILL JSON-STRÄNGAR
# ---------------------------------------------------------
json_gk_info = json.dumps(gk_info, ensure_ascii=False)
json_ref_info = json.dumps(ref_info, ensure_ascii=False)
json_top_scorers = json.dumps(top_scorers, ensure_ascii=False)
json_first_scorers = json.dumps(first_scorers, ensure_ascii=False)

# ---------------------------------------------------------
# BYGG IHOP OCH SKRIV HTML-FILEN
# ---------------------------------------------------------
final_html = html_template.replace("%%MATCH_DATA_JSON%%", json_match_data) \
    .replace("%%TEAMS_JSON%%", json_teams_data) \
    .replace("%%SEASONS_JSON%%", json_seasons_data) \
    .replace("%%SEASON_INFO_JSON%%", json_season_info) \
    .replace("%%DECADES_JSON%%", json_decades_data) \
    .replace("%%CUSTOM_EPOCHS_JSON%%", json_custom_epochs_data) \
    .replace("%%TEAM_MERITS_JSON%%", json_team_merits_data) \
    .replace("%%GK_INFO_JSON%%", json_gk_info) \
    .replace("%%REF_INFO_JSON%%", json_ref_info) \
    .replace("%%TOP_SCORERS_JSON%%", json_top_scorers) \
    .replace("%%FIRST_SCORERS_JSON%%", json_first_scorers) \
    .replace("%%MASTER_BELT_JSON%%", json_master_belt)

output_file = os.path.join(main_folder, "Matchanalys_Dashboard.html")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"SUCCÉ! Filen '{output_file}' har skapats. All person- och skyttekungsdata är nu integrerad.")