import requests
import pandas as pd
import json
import os
import csv
import re
from datetime import datetime

# =========================================================
# SÄKERSTÄLL RÄTT ARBETSKATALOG
# =========================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    print(f"📁 Arbetskatalog satt till: {os.getcwd()}")
except NameError:
    pass

# =========================================================
# HUVUDINSTÄLLNINGAR (DU BEHÖVER BARA ÄNDRA HÄR!)
# =========================================================

# 1. DIN API-NYCKEL (Används bara för API-lägena)
API_KEY = "5b127369725a499efefeb7204adb169d" 

# 2. VAD VILL DU GÖRA? 
# "PARSE_LOCAL_CSV" = NY! Extrahera spelardata från inklistrad FIFA-data i Excel
# "FIND_LEAGUE"     = Leta efter ID för en liga via API
# "CHECK_SEASONS"   = Kollar vilka årtal som finns för en vald liga via API
# "FIND_MATCHES"    = Lista alla matcher (och Match-ID:n) för en liga/år via API
# "FETCH"           = Ladda ner detaljerad matchdata till CSV via API
ACTION = "PARSE_LOCAL_CSV"

# --- INSTÄLLNINGAR FÖR LOKAL CSV-TOLK (När ACTION = "PARSE_LOCAL_CSV") ---
# Skriptet letar nu automatiskt i din undermapp "csv_filer"
LOCAL_CSV_FILE = os.path.join("csv_filer", "Match_fakta_WC_2026.csv") 

# --- INSTÄLLNINGAR FÖR API (När ACTION = FIND_LEAGUE / FETCH etc) ---
SEARCH_WORD = "Sweden"        
SEARCH_LEAGUE_ID = 1          
SEARCH_YEAR = "2026"          
MATCH_IDS = [863833] 

# 3. NAMN PÅ UTDATAFIL (SUFFIX)
# Lämna tomt ("") så lägger skriptet automatiskt till dagens datum och tid!
# På så sätt undviker du att gamla filer skrivs över.
FILE_SUFFIX = "" 


# =========================================================
# SYSTEMKOD BÖRJAR HÄR
# =========================================================

def format_api_name(raw_name):
    """Omvandlar 'FÖRNAMN EFTERNAMN' till 'Efternamn, Förnamn' med inledande versal."""
    if not raw_name: return ""
    parts = str(raw_name).strip().split()
    
    # Gör om alla delar till inledande versal och gemener (t.ex. 'MESSI' -> 'Messi')
    parts = [p.capitalize() for p in parts]
    
    if len(parts) > 1:
        return f"{parts[-1]}, {' '.join(parts[:-1])}"
    return str(raw_name).strip().capitalize()

def is_shirt_token(t):
    """Kollar om en textsträng börjar med ett tröjnummer (t.ex. '14' eller '14Chicharito')"""
    return bool(re.match(r'^(\d+)(.*)$', str(t).strip()))

def parse_local_csv(filename):
    """Läser in och städar den manuellt inklistrade FIFA-datan från Excel."""
    if not os.path.exists(filename):
        print(f"❌ Hittar inte filen: {filename}")
        print("Se till att namnet stämmer överens med LOCAL_CSV_FILE i inställningarna.")
        return []

    print(f"📖 Läser in lokal data från {filename}...")
    
    # ---------------------------------------------------------
    # ROBUST INLÄSNING: Hantera olika format och separatorer
    # ---------------------------------------------------------
    df = None
    try:
        # Försök 1: Auto-detektera med utf-8
        df = pd.read_csv(filename, header=None, dtype=str, sep=None, engine='python', encoding='utf-8')
    except Exception:
        try:
            # Försök 2: Auto-detektera med svensk Excel-standard (cp1252)
            df = pd.read_csv(filename, header=None, dtype=str, sep=None, engine='python', encoding='cp1252')
        except Exception as e:
            print(f"❌ Kunde inte läsa filen överhuvudtaget: {e}")
            return []
            
    # Om det bara blev 1 kolumn (feldetekterad separator), tvinga semikolon
    if df is not None and df.shape[1] == 1:
        try:
            df = pd.read_csv(filename, header=None, dtype=str, sep=';', encoding='utf-8')
        except Exception:
            df = pd.read_csv(filename, header=None, dtype=str, sep=';', encoding='cp1252')
            
        # Sista utvägen: tvinga kommatecken
        if df.shape[1] == 1:
            try:
                df = pd.read_csv(filename, header=None, dtype=str, sep=',', encoding='utf-8')
            except Exception:
                df = pd.read_csv(filename, header=None, dtype=str, sep=',', encoding='cp1252')

    if df is None:
        return []

    all_spelare = []
    
    # Loopa igenom varje kolumn i filen (Varje kolumn är en match)
    for col_idx in range(df.shape[1]):
        # Läs den råa kolumnen och behåll tomma rader tillfälligt för att veta exakt var vi är
        raw_col = df.iloc[:, col_idx].fillna("").astype(str).str.strip().tolist()
        
        # Om kolumnen är helt tom, hoppa över
        if not any(raw_col): 
            continue
            
        # Leta efter "Goalkeeper"
        gk_indices = [i for i, x in enumerate(raw_col) if x.lower() == "goalkeeper"]
        if not gk_indices:
            continue # Inte en match-kolumn
            
        gk_idx = gk_indices[0]
        
        # SMART SÖKNING AV MATCH-ID: Skanna upp till 10 rader ovanför "Goalkeeper"
        match_id = ""
        for offset in range(1, 11):
            if gk_idx - offset >= 0:
                val = raw_col[gk_idx - offset]
                if val.isdigit():
                    match_id = val
                    break
                    
        if not match_id:
            print(f"⚠️ Hittade inget Match-ID (enbart siffror) ovanför 'Goalkeeper' i kolumn {col_idx+1}. Hoppar över matchen.")
            continue
            
        print(f"⚽ Bearbetar Match-ID: {match_id} (Kolumn {col_idx+1})")
        
        # Nu kan vi ta bort tomma rader men BARA för datan efter Goalkeeper
        col_tokens = [t for t in raw_col[gk_idx+1:] if t]
        
        players = []
        team_turn = 'home' # Håller koll på vems tur det är (varannan spelare)
        section = 'starters'
        
        # Börja analysera alla tokens efter "Goalkeeper"
        for t in col_tokens:
            t_str = str(t).strip()
            t_low = t_str.lower()
            
            # Avbryt om vi når tränarsektionen längst ner
            if t_low in ["manager", "coach", "förbundskapten", "head coach"]:
                break
                
            # Ignorera positionsord som sabbar namnkolumnen
            ignore_words = ["goalkeeper", "defender", "midfield", "midfielder", "attack", "attacker", "forward", "starting line up"]
            if t_low in ignore_words:
                continue

            if t_low in ["substitutes", "substitutions", "avbytare"]:
                section = 'subs'
                team_turn = 'home' # Nollställ för säkerhets skull om lagen hade olika antal
                continue

            # Identifiera händelser (Minut eller Kapten)
            is_minute = re.search(r'\d+\'|ht', t_low)
            is_cap = t_low in ['c', '(c)']

            if is_minute or is_cap:
                # Tilldela händelsen till den senast tillagda spelaren som har ett namn (eller sista spelaren)
                if players:
                    target_p = players[-1]
                    for p in reversed(players):
                        if p["Namn"] != "":
                            target_p = p
                            break
                            
                    if is_minute:
                        min_match = re.search(r'(\d+)', t_str)
                        target_p["Minut"] = min_match.group(1) if min_match else "45"
                        target_p["Byte"] = "ut" if section == 'starters' else "in"
                    if is_cap:
                        target_p["Händelse"] = "Kapten"
                continue

            # Identifiera om det är en ny spelare (Börjar på en siffra)
            match_shirt = re.match(r'^(\d+)(.*)$', t_str)
            if match_shirt:
                shirt = match_shirt.group(1)
                rest = match_shirt.group(2).strip()

                new_p = {
                    "Match_ID": match_id,
                    "HB": "1" if team_turn == 'home' else "2",
                    "Tröjnr": shirt,
                    "Namn": rest, # Kan vara tomt (fylls i senare från kön)
                    "Position": "",
                    "Händelse": "",
                    "Minut": "",
                    "Byte": "",
                    "section": section
                }
                players.append(new_p)
                
                # Byt tur mellan hemma/borta
                team_turn = 'away' if team_turn == 'home' else 'home'
                continue

            # Om vi kommer hit, är det ett Namn (eller del av ett namn)
            # Vi tilldelar namnet till den FÖRSTA spelaren i vår lista som saknar namn
            assigned = False
            for p in players:
                if p["Namn"] == "":
                    p["Namn"] = t_str
                    assigned = True
                    break
                    
            # Om alla redan hade namn, tillhör antagligen ordet den sista spelaren
            if not assigned and players:
                players[-1]["Namn"] += " " + t_str

        # Formatera namnen snyggt innan vi sparar ner matchen
        for p in players:
            p["Namn"] = format_api_name(p["Namn"])
            # Ta bort temporär data
            if "section" in p:
                del p["section"]
                
        all_spelare.extend(players)

    return all_spelare

# =========================================================
# API-FUNKTIONER (Från tidigare)
# =========================================================

def check_api_status():
    url = "https://v3.football.api-sports.io/status"
    headers = {"x-apisports-key": API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            req_data = data.get("response", {}).get("requests", {})
            current = req_data.get("current", 0)
            limit = req_data.get("limit_day", 100)
            kvar = limit - current
            print(f"📊 API-STATUS: Du har gjort {current} anrop idag. (Du har {kvar} av {limit} anrop kvar)\n")
            if kvar <= 0:
                print("⚠️ VARNING: Du har slut på API-anrop för idag! Försök igen imorgon.")
                return False
            return True
        else:
            return False
    except Exception as e:
        return False

def search_for_league(search_word):
    print(f"🔍 Söker efter ligor/turneringar med ordet: '{search_word}'...")
    url = f"https://v3.football.api-sports.io/leagues?search={search_word}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return
    data = response.json().get('response', [])
    if not data: return
    print(f"\n--- HITTADE {len(data)} LIGOR/TURNERINGAR ---")
    for item in data:
        print(f"LIGA-ID: {item['league']['id']:<4} | Turnering: {item['league']['name']} ({item['country']['name']})")
    print("--------------------------------------------------\n")

def check_available_seasons(league_id):
    print(f"🔍 Kollar vilka säsonger som finns i databasen för Liga-ID {league_id}...")
    url = f"https://v3.football.api-sports.io/leagues?id={league_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return
    data = response.json()
    res = data.get('response', [])
    if not res: return
    available_years = [str(s['year']) for s in res[0]['seasons']]
    print(f"\n--- TILLGÄNGLIGA SÄSONGER FÖR: {res[0]['league']['name']} ---")
    print(", ".join(available_years))
    print("--------------------------------------------------\n")

def find_all_matches(year="2026", league_id=1):
    print(f"🔍 Letar upp ALLA matcher för Liga-ID {league_id} (Säsong {year})...")
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season={year}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return
    data = response.json()
    fixtures = data.get('response', [])
    if not fixtures: return
    fixtures.sort(key=lambda x: x['fixture']['date'])
    print(f"\n--- HITTADE {len(fixtures)} MATCHER ---")
    for f in fixtures:
        home = f['teams']['home']['name'] or "TBD"
        away = f['teams']['away']['name'] or "TBD"
        print(f"MATCH-ID: {f['fixture']['id']:<8} | Datum: {f['fixture']['date'][:10]} | Status: {f['fixture']['status']['short']:<4} | {home} vs {away}")
    print("--------------------------------------------------\n")

def fetch_match_data(fixture_id):
    print(f"🌐 Hämtar matchdata för ID {fixture_id} via API...")
    url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return [], [], []
    data = response.json()
    if not data.get('response'): return [], [], []
        
    fixture = data['response'][0]
    home_id = fixture['teams']['home']['id']
    
    spelare_data, mal_data, kort_data = [], [], []
    if 'players' in fixture and len(fixture['players']) > 0:
        for team_info in fixture['players']:
            hb_val = "1" if team_info['team']['id'] == home_id else "2"
            for player in team_info['players']:
                stats = player['statistics'][0]
                trojnr = stats['games'].get('number', '') 
                namn = format_api_name(player['player']['name'])
                pos = stats['games']['position']
                spelade_minuter = stats['games'].get('minutes', 0)
                if spelade_minuter is None or spelade_minuter == 0: continue
                byte_str = ""
                subs = stats.get('substitutes') or {}
                if subs.get('in') is not None: byte_str += "in "
                if subs.get('out') is not None: byte_str += "ut "
                spelare_data.append({
                    "Match_ID": fixture_id, "HB": hb_val, "Tröjnr": trojnr, "Namn": namn,
                    "Position": pos, "Händelse": "", "Minut": spelade_minuter, "Byte": byte_str.strip()
                })
    return spelare_data, mal_data, kort_data

# =========================================================
# KÖRNING OCH FILSPARNING
# =========================================================
if __name__ == "__main__":
    
    # Förbered filnamn
    suffix = FILE_SUFFIX
    if suffix == "":
        now = datetime.now()
        suffix = now.strftime("_%Y%m%d_%H%M")
    if suffix and not suffix.startswith("_"):
        suffix = "_" + suffix

    # Sparar filerna i din nya undermapp
    CSV_FOLDER = "csv_filer"
    os.makedirs(CSV_FOLDER, exist_ok=True)

    if ACTION == "PARSE_LOCAL_CSV":
        # Kör den lokala CSV-tolken
        all_spelare = parse_local_csv(LOCAL_CSV_FILE)
        
        if all_spelare:
            spelare_file = os.path.join(CSV_FOLDER, f"api_spelare{suffix}.csv")
            pd.DataFrame(all_spelare).to_csv(spelare_file, index=False, encoding='utf-8-sig', sep=';')
            print(f"\n🎉 Färdigt! Tvättade och sparade {len(all_spelare)} spelare till CSV.")
            print(f"📁 Filen hittar du i undermappen: '{os.path.abspath(CSV_FOLDER)}'")
        else:
            print("\n⚠️ Hittade ingen spelardata att spara.")
            
    else:
        # Kör de vanliga API-funktionerna
        if API_KEY == "DIN_API_NYCKEL_HÄR" or API_KEY == "":
            print("⚠️ Varning: Du måste klistra in en giltig API-nyckel för att använda API-funktionerna!")
        else:
            if not check_api_status(): exit()
                
            if ACTION == "FIND_LEAGUE":
                search_for_league(SEARCH_WORD) 
                
            elif ACTION == "CHECK_SEASONS":
                check_available_seasons(SEARCH_LEAGUE_ID)
                
            elif ACTION == "FIND_MATCHES":
                find_all_matches(year=SEARCH_YEAR, league_id=SEARCH_LEAGUE_ID)
                
            elif ACTION == "FETCH":
                if not MATCH_IDS:
                    print("⚠️ Din MATCH_IDS-lista är tom!")
                else:
                    all_spelare, all_mal, all_kort = [], [], []
                    for f_id in MATCH_IDS:
                        s_data, m_data, k_data = fetch_match_data(f_id)
                        all_spelare.extend(s_data)
                        all_mal.extend(m_data)
                        all_kort.extend(k_data)
                    
                    if all_spelare: pd.DataFrame(all_spelare).to_csv(os.path.join(CSV_FOLDER, f"api_spelare{suffix}.csv"), index=False, encoding='utf-8-sig', sep=';')
                    if all_mal: pd.DataFrame(all_mal).to_csv(os.path.join(CSV_FOLDER, f"api_mal{suffix}.csv"), index=False, encoding='utf-8-sig', sep=';')
                    if all_kort: pd.DataFrame(all_kort).to_csv(os.path.join(CSV_FOLDER, f"api_kort{suffix}.csv"), index=False, encoding='utf-8-sig', sep=';')
                    print(f"\n🎉 Färdigt! Sparade {len(all_spelare)} spelare från API till CSV.")