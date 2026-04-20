import os
import pandas as pd
import numpy as np
import json

# ==========================================
# 1. ANVÄNDARINSTÄLLNINGAR FÖR VYER
# ==========================================
# Ange år för en pågående/kommande säsong (t.ex. 2026) som ska döljas från 
# Maratontabell och Serietabeller tills den är färdigspelad, men som redan
# nu ska få påverka färgmarkeringar (upp/ned) och Serievandringar.
# Sätt till None om ingen säsong ska döljas.
PAGAENDE_SASONG = 2026

# ==========================================
# 2. GENERELL SETUP OCH DATA-LADDNING
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
except NameError:
    project_root = os.getcwd()
    pass 

def find_target_file(keyword, search_root):
    for root, dirs, files in os.walk(search_root):
        for filename in files:
            if keyword.lower() in filename.lower() and filename.lower().endswith(".xlsx") and not filename.startswith("~$"):
                return os.path.join(root, filename)
    return None

def fix_text(text):
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text.strip()

def clean_dataframe(df):
    if df is None: return None
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].apply(fix_text)
    return df

def get_master_data():
    """Hämtar och förbereder master-datan."""
    excel_path = find_target_file("Serietabellerna_samlade", project_root)
    if not excel_path:
        print("FEL: Hittade inte filen Serietabellerna_samlade.")
        return None, None
        
    print(f"Laddar databasen från: {os.path.basename(excel_path)}...")
    excel_dict = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    
    df_tabeller = clean_dataframe(excel_dict.get('Tabeller'))
    df_lag_nr = clean_dataframe(excel_dict.get('Lag_nr'))
    df_lag_id = clean_dataframe(excel_dict.get('Lag_id'))
    df_serieniva = clean_dataframe(excel_dict.get('Serienivå'))
    
    df_tabeller = df_tabeller.rename(columns={'Lag': 'Laget i tabell'}) 
    
    # Slå ihop
    master = pd.merge(df_tabeller, df_lag_nr[['Laget', 'Lag_ID']], left_on='Laget i tabell', right_on='Laget', how='left')
    master = pd.merge(master, df_lag_id[['Lag_ID', 'Lag', 'Distrikt', 'Kommun']], on='Lag_ID', how='left').rename(columns={'Lag': 'Standard_Lagnamn'})
    master = pd.merge(master, df_serieniva[['Säsnr', 'Poäng_seger']], on='Säsnr', how='left')
    
    # Rensa och förbereda
    master['Analys_Lagnamn'] = master['Standard_Lagnamn'].fillna(master['Laget i tabell'])
    master['Startår_Numerisk'] = master['Säsong'].astype(str).str.extract(r'^(\d{4})').astype(float)
    
    if 'Poängjustering_Startpoäng' in master.columns:
        master['Poängjustering_Startpoäng'] = pd.to_numeric(master['Poängjustering_Startpoäng'], errors='coerce').fillna(0)
        master['Giltig_Poängavdrag'] = master['Poängjustering_Startpoäng'].apply(lambda x: x if x < 0 else 0)
    else:
        master['Giltig_Poängavdrag'] = 0
        master['Poängjustering_Startpoäng'] = 0

    # Läs in numeriska värden, INKLUSIVE P (Faktiska poäng)
    for col in ['Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P']:
        master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)

    master['Målskillnad'] = master['Gjorda'] - master['Insl']
    
    return master, df_tabeller

# ==========================================
# 3. HTML DASHBOARD GENERATOR (FLIKAR)
# ==========================================
def export_html_dashboard(df):
    print("\nSkapar interaktiv flik-baserad HTML-dashboard...")
    
    # --- 1. Bygg JSON för matchdata ---
    export_cols = [
        'Startår_Numerisk', 'Säsong', 'Nivå', 'Division', 'Serie', 'Plac', 
        'Analys_Lagnamn', 'Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P',
        'Giltig_Poängavdrag', 'Poängjustering_Startpoäng', 'Lag_ID', 'Laget i tabell', 'Standard_Lagnamn'
    ]
    available_cols = [c for c in export_cols if c in df.columns]
    df_export = df[available_cols].copy()
    
    df_export = df_export.fillna('')
    df_export['Nivå'] = pd.to_numeric(df_export['Nivå'], errors='coerce').fillna(0).astype(int)
    
    # Säkerställ att vi bara har nivå 1-5
    df_export = df_export[(df_export['Nivå'] > 0) & (df_export['Nivå'] <= 5)]
    
    json_data = df_export.to_json(orient='records').replace('</script>', '<\/script>')
    
    # --- 2. Bygg JSON för admin-data ---
    orphans = df_export[df_export['Lag_ID'] == '']['Laget i tabell'].unique().tolist()
    
    name_changes = []
    valid_teams = df_export[df_export['Lag_ID'] != '']
    grouped_teams = valid_teams.groupby('Analys_Lagnamn')
    
    for std_name, group in grouped_teams:
        aliases = group['Laget i tabell'].unique()
        if len(aliases) > 1:
            alias_info = []
            for alias in aliases:
                alias_rows = group[group['Laget i tabell'] == alias]
                if not alias_rows.empty:
                    min_year = int(alias_rows['Startår_Numerisk'].min())
                    max_year = int(alias_rows['Startår_Numerisk'].max())
                    if min_year == max_year:
                        alias_info.append(f"{alias} ({min_year})")
                    else:
                        alias_info.append(f"{alias} ({min_year}-{max_year})")
                else:
                    alias_info.append(alias)
            name_changes.append({"standard": std_name, "aliases": alias_info})
            
    admin_stats = {
        "total_rows": len(df_export),
        "unique_teams": df_export['Analys_Lagnamn'].nunique(),
        "orphans_count": len(orphans),
        "orphans_list": orphans,
        "name_changes": sorted(name_changes, key=lambda x: x['standard'])
    }
    json_admin = json.dumps(admin_stats)

    # --- 3. HTML Mall ---
    html_template = """<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Svensk Fotbollshistoria - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #f3f4f6; font-family: ui-sans-serif, system-ui, sans-serif; }
        th { position: sticky; top: 0; background-color: #e5e7eb; z-index: 10; }
        .table-container { max-height: 60vh; overflow-y: auto; }
        .tab-btn.active { border-bottom: 2px solid #2563eb; color: #2563eb; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .row-promoted { background-color: #f0fdf4 !important; } /* Light green */
        .row-promoted:hover { background-color: #dcfce7 !important; }
        .row-relegated { background-color: #fef2f2 !important; } /* Light red */
        .row-relegated:hover { background-color: #fee2e2 !important; }
    </style>
</head>
<body class="p-4 md:p-6">

    <div class="max-w-7xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
            <h1 class="text-3xl font-bold text-gray-800">Svensk Fotbollshistoria</h1>
            <button onclick="exportCSV()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded shadow flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                Ladda ner CSV (Aktuell flik)
            </button>
        </div>

        <!-- Flik-navigering -->
        <div class="flex overflow-x-auto border-b border-gray-200 mb-6 pb-1">
            <button class="tab-btn active px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-maraton', this)">Maratontabeller</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-sasong', this)">Serietabeller</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-vandring', this)">Serievandringar</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-admin', this)">Administration</button>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 1: MARATONTABELL                          -->
        <!-- ============================================== -->
        <div id="tab-maraton" class="tab-content active">
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="maratonSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderMaraton()">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Poängsystem</label>
                    <select id="maratonPointsMode" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderMaraton()">
                        <option value="3">3 poäng för seger</option>
                        <option value="2">2 poäng för seger</option>
                        <option value="hist">Historiska poäng (P)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Startår</label>
                    <select id="maratonStartYear" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderMaraton()"></select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Slutår</label>
                    <select id="maratonEndYear" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderMaraton()"></select>
                </div>
                <div>
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('maraton')">
                        Återställ
                    </button>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Serienivå</label>
                    <select id="maratonLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('maratonLevel', 'maratonDivision', 'levelToDiv'); renderMaraton()">
                        <option value="Alla">-- Alla Nivåer --</option>
                        <option value="1">Nivå 1</option>
                        <option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option>
                        <option value="4">Nivå 4</option>
                        <option value="5">Nivå 5</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Seriebeteckning (Division)</label>
                    <select id="maratonDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('maratonDivision', 'maratonLevel', 'divToLevel'); renderMaraton()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                        <!-- Fylls dynamiskt -->
                    </select>
                </div>
            </div>
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="maratonCounter"></span>
                <span class="italic text-xs">Tips: Klicka på ett lag för att se deras tabeller utifrån dina valda filter.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="maratonTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="maratonHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="maratonBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 2: SERIETABELLER (SÄSONG)                 -->
        <!-- ============================================== -->
        <div id="tab-sasong" class="tab-content">
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-2 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Startår</label>
                    <select id="sasongStartYear" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderSasong()"></select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Slutår</label>
                    <select id="sasongEndYear" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderSasong()"></select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Specifikt Lag (Historik)</label>
                    <select id="sasongTeam" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderSasong()">
                        <option value="Alla">-- Alla Lag --</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Filtrera på Nivå</label>
                    <select id="sasongLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv'); renderSasong()">
                        <option value="Alla">-- Alla Nivåer --</option>
                        <option value="1">Nivå 1</option><option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option><option value="4">Nivå 4</option><option value="5">Nivå 5</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Seriebeteckning</label>
                    <select id="sasongDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongDivision', 'sasongLevel', 'divToLevel'); renderSasong()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                    </select>
                </div>
                <div class="md:col-span-6 flex justify-end">
                    <button class="bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-6 rounded border border-gray-300 transition-colors" onclick="resetFilters('sasong')">
                        Återställ & Rensa
                    </button>
                </div>
            </div>
            
            <div class="flex justify-between items-end mb-2">
                <div class="text-sm text-gray-500" id="sasongCounter"></div>
                <div class="text-xs text-gray-500 flex gap-4">
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-green-100 border border-green-200 inline-block mr-1"></span> Uppflyttad året efter</span>
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-red-100 border border-red-200 inline-block mr-1"></span> Degraderad året efter</span>
                </div>
            </div>

            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="sasongTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="sasongHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="sasongBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 3: SERIEVANDRINGAR                        -->
        <!-- ============================================== -->
        <div id="tab-vandring" class="tab-content">
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="vandringSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderVandringar()">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Fokusera på</label>
                    <select id="vandringMode" class="w-full border-gray-300 rounded-md p-2 border" onchange="toggleVandringMode()">
                        <option value="niva">Serienivå (Fast trappsteg)</option>
                        <option value="division">Seriebeteckning (Historiskt namn)</option>
                    </select>
                </div>
                <div id="vandringLevelWrapper">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Serienivå</label>
                    <select id="vandringLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()">
                        <option value="1">Nivå 1 (Allsvenskan etc)</option>
                        <option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option>
                        <option value="4">Nivå 4</option>
                        <option value="5">Nivå 5</option>
                    </select>
                </div>
                <div id="vandringDivisionWrapper" class="hidden">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Seriebeteckning</label>
                    <select id="vandringDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()"></select>
                </div>
                <div>
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('vandring')">
                        Återställ
                    </button>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="vandringCounter">Beräknar sviter och vandringar...</span>
                <span class="italic text-xs">Tips: Klicka på ett lag för att se alla deras tabeller för denna nivå/beteckning.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="vandringTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="vandringHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="vandringBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 4: ADMINISTRATION                         -->
        <!-- ============================================== -->
        <div id="tab-admin" class="tab-content">
            <div class="bg-blue-50 border border-blue-200 p-4 rounded-lg shadow-sm mb-6">
                <h3 class="text-blue-800 font-bold mb-2 flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                    Information: Vår- och höstserier (1991-1992)
                </h3>
                <p class="text-sm text-blue-900 mb-2">Säsongerna 1991 och 1992 spelades det ofta uppdelade vår- och höstserier i seriesystemet. Systemet är byggt för att hantera denna komplexitet logiskt:</p>
                <ul class="list-disc pl-5 text-sm text-blue-900 space-y-1">
                    <li><strong>I Maratontabeller:</strong> Både vår- och höstsäsongens matcher summeras ihop. Ev. bonuspoäng i starten av höstserier räknas ej med i totalen (förutom minuspoäng). Resultatet är all faktiskt spelad statistik för det kalenderåret.</li>
                    <li><strong>I Serievandringar & Sviter:</strong> Båda säsongshalvornas rad läses in kronologiskt, men "År på serienivån" grupperas per kalenderår så att inget lag ser ut att ha spelat två år under samma säsong, vilket ger korrekta sviter.</li>
                </ul>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-6">
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                        <h2 class="text-lg font-bold text-gray-800 mb-4">Databasens Hälsa (Nivå 1-5)</h2>
                        <ul class="space-y-3 text-sm text-gray-700" id="adminStatsList"></ul>
                    </div>
                    
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                        <h2 class="text-lg font-bold text-gray-800 mb-2">Registrerade Namnbyten</h2>
                        <p class="text-xs text-gray-500 mb-3">Lag som har haft flera olika inskrivna namn i nationellt seriespel.</p>
                        <div class="max-h-60 overflow-y-auto bg-white p-3 rounded border border-gray-200">
                            <ul class="space-y-2 text-sm text-gray-800" id="adminNameChanges"></ul>
                        </div>
                    </div>
                </div>

                <div class="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm h-full flex flex-col">
                    <h2 class="text-lg font-bold text-red-800 mb-2">Föräldralösa lag (Saknar Alias)</h2>
                    <p class="text-sm text-red-600 mb-3">Dessa lagnamn hittades i fliken "Tabeller" men saknar koppling i fliken "Lag_nr". Deras statistik kommer inte matchas till något Standard-namn.</p>
                    <div class="flex-grow overflow-y-auto bg-white p-3 rounded border border-red-100">
                        <ul class="list-disc pl-5 text-sm text-gray-800" id="adminOrphansList"></ul>
                    </div>
                </div>
            </div>
            
            <!-- Hidden table for CSV export -->
            <div class="mt-8 hidden" id="adminTableContainer">
               <table id="adminTable">
                   <thead><tr><th>Information</th></tr></thead>
                   <tbody id="adminBody"></tbody>
               </table>
            </div>
        </div>

    </div>

    <!-- DATA INJECTION OCH LOGIK -->
    <script>
        const matchData = __JSON_DATA__;
        const adminData = __ADMIN_JSON__;
        const ongoingSeason = __ONGOING_SEASON__;
        let currentTabId = 'tab-maraton';
        
        // 1. KARTLÄGG BEROENDEN MELLAN NIVÅ OCH DIVISION SAMT FRAMTIDA NIVÅER FÖR FÄRGLÄGGNING
        const levelDivMap = { levels: {}, divs: {} };
        const teamYearLevel = {}; 
        
        matchData.forEach(d => {
            let lvl = String(d.Nivå);
            let div = d.Division;
            if(lvl && div) {
                if(!levelDivMap.levels[lvl]) levelDivMap.levels[lvl] = new Set();
                levelDivMap.levels[lvl].add(div);
                
                if(!levelDivMap.divs[div]) levelDivMap.divs[div] = new Set();
                levelDivMap.divs[div].add(lvl);
            }
            
            let tName = d.Analys_Lagnamn;
            if(!teamYearLevel[tName]) teamYearLevel[tName] = {};
            teamYearLevel[tName][d.Startår_Numerisk] = d.Nivå;
        });

        const allYears = [...new Set(matchData.map(d => parseInt(d.Startår_Numerisk)))].filter(y => !isNaN(y) && y > 0).sort((a,b) => a-b);
        // Completed years exkluderar pågående säsong, används för Maratontabell och Serietabeller
        const completedYears = ongoingSeason ? allYears.filter(y => y < ongoingSeason) : allYears;
        const allDivisions = [...new Set(matchData.map(d => d.Division))].filter(Boolean).sort((a,b) => a.localeCompare(b));
        const allTeams = [...new Set(matchData.map(d => d.Analys_Lagnamn))].sort((a,b) => a.localeCompare(b));
        
        function populateDropdown(selectId, dataArray, reverse=false, defaultLast=false) {
            const select = document.getElementById(selectId);
            if(!select) return;
            
            let hasPlaceholder = select.options.length > 0 && select.options[0].value === 'Alla';
            let placeholderHTML = hasPlaceholder ? select.options[0].outerHTML : '';
            
            select.innerHTML = placeholderHTML;
            let displayData = reverse ? [...dataArray].reverse() : dataArray;
            
            displayData.forEach(item => {
                let opt = document.createElement('option');
                opt.value = item;
                opt.innerHTML = item;
                select.appendChild(opt);
            });
            
            if(defaultLast && dataArray.length > 0) {
                select.value = dataArray[dataArray.length - 1];
            } else if(!hasPlaceholder && dataArray.length > 0) {
                select.value = dataArray[0];
            }
        }

        // CASCADING DROPDOWNS
        function syncDropdowns(changedSelectId, targetSelectId, mapType) {
            let changedVal = document.getElementById(changedSelectId).value;
            let targetSelect = document.getElementById(targetSelectId);
            
            let validTargets = null;
            if (changedVal !== 'Alla') {
                if (mapType === 'levelToDiv' && levelDivMap.levels[changedVal]) {
                    validTargets = levelDivMap.levels[changedVal];
                } else if (mapType === 'divToLevel' && levelDivMap.divs[changedVal]) {
                    validTargets = levelDivMap.divs[changedVal];
                }
            }

            let options = Array.from(targetSelect.options);
            let allaOption = options.shift();

            options.forEach(opt => {
                if (validTargets === null || validTargets.has(opt.value)) {
                    opt.disabled = false;
                    opt.style.color = "";
                    opt.dataset.valid = "1";
                } else {
                    opt.disabled = true;
                    opt.style.color = "#9ca3af";
                    opt.dataset.valid = "0";
                }
            });

            options.sort((a, b) => {
                if (a.dataset.valid !== b.dataset.valid) return b.dataset.valid.localeCompare(a.dataset.valid);
                return a.text.localeCompare(b.text);
            });

            targetSelect.innerHTML = '';
            targetSelect.appendChild(allaOption);
            options.forEach(opt => targetSelect.appendChild(opt));

            if (targetSelect.options[targetSelect.selectedIndex].disabled) {
                targetSelect.value = 'Alla';
            }
        }

        function resetSelect(selectId) {
            let select = document.getElementById(selectId);
            if(!select) return;
            
            let hasPlaceholder = select.options.length > 0 && select.options[0].value === 'Alla';
            let options = Array.from(select.options);
            let first = hasPlaceholder ? options.shift() : null;
            
            options.forEach(opt => {
                opt.disabled = false;
                opt.style.color = "";
                opt.dataset.valid = "1";
            });
            options.sort((a,b) => a.text.localeCompare(b.text));
            
            select.innerHTML = '';
            if(first) {
                select.appendChild(first);
                select.value = 'Alla';
            } else if (options.length > 0) {
                select.value = options[0].value;
            }
            options.forEach(opt => select.appendChild(opt));
        }

        function resetFilters(tab) {
            if (tab === 'maraton') {
                document.getElementById('maratonSearch').value = '';
                document.getElementById('maratonPointsMode').value = '3';
                document.getElementById('maratonStartYear').value = completedYears[0];
                document.getElementById('maratonEndYear').value = completedYears[completedYears.length - 1];
                resetSelect('maratonLevel');
                resetSelect('maratonDivision');
                renderMaraton();
            } else if (tab === 'sasong') {
                document.getElementById('sasongStartYear').value = completedYears[completedYears.length - 1];
                document.getElementById('sasongEndYear').value = completedYears[completedYears.length - 1];
                document.getElementById('sasongTeam').value = 'Alla';
                resetSelect('sasongLevel');
                resetSelect('sasongDivision');
                renderSasong();
            } else if (tab === 'vandring') {
                document.getElementById('vandringSearch').value = '';
                document.getElementById('vandringMode').value = 'niva';
                document.getElementById('vandringLevel').value = '1';
                let vd = document.getElementById('vandringDivision');
                if (vd.options.length > 0) vd.value = allDivisions[0];
                toggleVandringMode();
            }
        }

        // SMART LÄNK: HOPPA TILL SERIETABELLER MED KONTEXT
        function showTeamHistory(teamName, sourceTab) {
            // Byt flik rent visuellt
            switchTab('tab-sasong', document.querySelector('.tab-btn[onclick*="tab-sasong"]'));
            
            // Sätt laget
            document.getElementById('sasongTeam').value = teamName;
            
            // För över filter beroende på var vi klickade ifrån
            if (sourceTab === 'maraton') {
                document.getElementById('sasongStartYear').value = document.getElementById('maratonStartYear').value;
                document.getElementById('sasongEndYear').value = document.getElementById('maratonEndYear').value;
                document.getElementById('sasongLevel').value = document.getElementById('maratonLevel').value;
                document.getElementById('sasongDivision').value = document.getElementById('maratonDivision').value;
            } else if (sourceTab === 'vandring') {
                document.getElementById('sasongStartYear').value = completedYears[0];
                document.getElementById('sasongEndYear').value = completedYears[completedYears.length - 1];
                
                if(document.getElementById('vandringMode').value === 'niva') {
                    document.getElementById('sasongLevel').value = document.getElementById('vandringLevel').value;
                    document.getElementById('sasongDivision').value = 'Alla';
                } else {
                    document.getElementById('sasongLevel').value = 'Alla';
                    document.getElementById('sasongDivision').value = document.getElementById('vandringDivision').value;
                }
            }
            
            // Uppdatera kaskad-menyerna och rita ut
            syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv');
            renderSasong();
        }

        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btnElement.classList.add('active');
            currentTabId = tabId;
            
            if(tabId === 'tab-maraton') renderMaraton();
            if(tabId === 'tab-sasong') renderSasong();
            if(tabId === 'tab-vandring') renderVandringar();
        }

        function toggleVandringMode() {
            const mode = document.getElementById('vandringMode').value;
            if(mode === 'niva') {
                document.getElementById('vandringLevelWrapper').classList.remove('hidden');
                document.getElementById('vandringDivisionWrapper').classList.add('hidden');
            } else {
                document.getElementById('vandringLevelWrapper').classList.add('hidden');
                document.getElementById('vandringDivisionWrapper').classList.remove('hidden');
            }
            renderVandringar();
        }

        // RENDER: MARATONTABELL
        function renderMaraton() {
            const search = document.getElementById('maratonSearch').value.toLowerCase();
            const pMode = document.getElementById('maratonPointsMode').value;
            const startYear = parseInt(document.getElementById('maratonStartYear').value) || 0;
            const endYear = parseInt(document.getElementById('maratonEndYear').value) || 9999;
            const level = document.getElementById('maratonLevel').value;
            const divFilter = document.getElementById('maratonDivision').value;

            const filtered = matchData.filter(d => {
                if (d.Startår_Numerisk < startYear || d.Startår_Numerisk > endYear) return false;
                if (level !== 'Alla' && String(d.Nivå) !== level) return false;
                if (divFilter !== 'Alla' && d.Division !== divFilter) return false;
                if (search && !d.Analys_Lagnamn.toLowerCase().includes(search)) return false;
                return true;
            });

            let teams = {};
            filtered.forEach(d => {
                let t = d.Analys_Lagnamn;
                if (!teams[t]) teams[t] = { lag: t, saesonger: new Set(), sp: 0, v: 0, o: 0, f: 0, gj: 0, insl: 0, padv: 0, histP: 0 };
                teams[t].saesonger.add(d.Startår_Numerisk);
                teams[t].sp += Number(d.Sp) || 0;
                teams[t].v += Number(d.V) || 0;
                teams[t].o += Number(d.O) || 0;
                teams[t].f += Number(d.F) || 0;
                teams[t].gj += Number(d.Gjorda) || 0;
                teams[t].insl += Number(d.Insl) || 0;
                teams[t].padv += Number(d.Giltig_Poängavdrag) || 0;
                teams[t].histP += Number(d.P) || 0; 
            });

            let arr = Object.values(teams).map(t => {
                t.ant_saesonger = t.saesonger.size;
                t.ms = t.gj - t.insl;
                if(pMode === '3') t.poang = (t.v * 3) + (t.o * 1) + t.padv;
                else if(pMode === '2') t.poang = (t.v * 2) + (t.o * 1) + t.padv;
                else t.poang = t.histP;
                return t;
            });

            arr.sort((a, b) => b.poang - a.poang || b.ms - a.ms || b.gj - a.gj);

            document.getElementById('maratonHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3">Plac</th>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center">Säsonger</th>
                    <th class="px-4 py-3 text-center">Sp</th>
                    <th class="px-4 py-3 text-center">V</th>
                    <th class="px-4 py-3 text-center">O</th>
                    <th class="px-4 py-3 text-center">F</th>
                    <th class="px-4 py-3 text-center">Mål</th>
                    <th class="px-4 py-3 text-center">MS</th>
                    <th class="px-4 py-3 text-center font-bold text-gray-900">P</th>
                </tr>
            `;

            let tbody = '';
            arr.forEach((t, i) => {
                tbody += `
                    <tr class="hover:bg-blue-50 transition-colors">
                        <td class="px-4 py-2 text-gray-500">${i + 1}</td>
                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'maraton')" title="Klicka för att se tabellrader utifrån nuvarande filter">${t.lag}</td>
                        <td class="px-4 py-2 text-center">${t.ant_saesonger}</td>
                        <td class="px-4 py-2 text-center">${t.sp}</td>
                        <td class="px-4 py-2 text-center">${t.v}</td>
                        <td class="px-4 py-2 text-center">${t.o}</td>
                        <td class="px-4 py-2 text-center">${t.f}</td>
                        <td class="px-4 py-2 text-center">${t.gj} - ${t.insl}</td>
                        <td class="px-4 py-2 text-center">${t.ms > 0 ? '+'+t.ms : t.ms}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${t.poang}</td>
                    </tr>
                `;
            });
            document.getElementById('maratonBody').innerHTML = tbody;
            document.getElementById('maratonCounter').innerText = `Visar maratontabell för ${arr.length} lag.`;
        }

        // RENDER: SERIETABELL (ENSKILD SÄSONG / LAGHISTORIK)
        function renderSasong() {
            const startYear = parseInt(document.getElementById('sasongStartYear').value) || 0;
            const endYear = parseInt(document.getElementById('sasongEndYear').value) || 9999;
            const teamFilter = document.getElementById('sasongTeam').value;
            const levelFilter = document.getElementById('sasongLevel').value;
            const divFilter = document.getElementById('sasongDivision').value;
            
            let data = matchData.filter(d => {
                if(d.Startår_Numerisk < startYear || d.Startår_Numerisk > endYear) return false;
                if(teamFilter !== 'Alla' && d.Analys_Lagnamn !== teamFilter) return false;
                if(levelFilter !== 'Alla' && String(d.Nivå) !== levelFilter) return false;
                if(divFilter !== 'Alla' && d.Division !== divFilter) return false;
                return true;
            });
            
            data.sort((a, b) => {
                if(teamFilter !== 'Alla') {
                    // Om vi följer ett lag, sortera kronologiskt framåt
                    return a.Startår_Numerisk - b.Startår_Numerisk || a.Nivå - b.Nivå;
                }
                // Annars sortera omvänt kronologiskt (nyast överst), sedan nivå
                return b.Startår_Numerisk - a.Startår_Numerisk || a.Nivå - b.Nivå || String(a.Serie).localeCompare(String(b.Serie)) || a.Plac - b.Plac;
            });

            document.getElementById('sasongHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3 text-center">År</th>
                    <th class="px-4 py-3 text-center">Nivå</th>
                    <th class="px-4 py-3">Beteckning</th>
                    <th class="px-4 py-3">Serie</th>
                    <th class="px-4 py-3 text-center">Plac</th>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center">Sp</th>
                    <th class="px-4 py-3 text-center">V</th>
                    <th class="px-4 py-3 text-center">O</th>
                    <th class="px-4 py-3 text-center">F</th>
                    <th class="px-4 py-3 text-center">Gj-In</th>
                    <th class="px-4 py-3 text-center font-bold text-gray-900">P</th>
                    <th class="px-4 py-3 text-center">P-Just</th>
                </tr>
            `;

            let tbody = '';
            data.forEach(d => {
                let just = Number(d.Poängjustering_Startpoäng);
                
                // Räkna ut färgmarkering för upp/nedflyttning
                let rowClass = "border-b border-gray-100 transition-colors";
                let nextYearLvl = teamYearLevel[d.Analys_Lagnamn][d.Startår_Numerisk + 1];
                
                if(nextYearLvl) {
                    if(nextYearLvl < d.Nivå) rowClass += " row-promoted"; // Grön
                    else if(nextYearLvl > d.Nivå) rowClass += " row-relegated"; // Röd
                    else rowClass += " hover:bg-blue-50";
                } else {
                    rowClass += " hover:bg-blue-50";
                }

                tbody += `
                    <tr class="${rowClass}">
                        <td class="px-4 py-2 text-center text-gray-500">${d.Startår_Numerisk}</td>
                        <td class="px-4 py-2 text-center font-medium">${d.Nivå}</td>
                        <td class="px-4 py-2 text-gray-600">${d.Division || '-'}</td>
                        <td class="px-4 py-2 text-gray-800">${d.Serie || '-'}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${d.Plac || '-'}</td>
                        <td class="px-4 py-2 font-semibold text-gray-800">${d.Analys_Lagnamn}</td>
                        <td class="px-4 py-2 text-center">${d.Sp}</td>
                        <td class="px-4 py-2 text-center">${d.V}</td>
                        <td class="px-4 py-2 text-center">${d.O}</td>
                        <td class="px-4 py-2 text-center">${d.F}</td>
                        <td class="px-4 py-2 text-center">${d.Gjorda} - ${d.Insl}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${d.P}</td>
                        <td class="px-4 py-2 text-center text-gray-500">${just !== 0 ? just : ''}</td>
                    </tr>
                `;
            });
            document.getElementById('sasongBody').innerHTML = tbody;
            document.getElementById('sasongCounter').innerText = `Hittade ${data.length} rader utifrån valda filter.`;
        }

        // RENDER: SERIEVANDRINGAR
        function renderVandringar() {
            const search = document.getElementById('vandringSearch').value.toLowerCase();
            const mode = document.getElementById('vandringMode').value;
            const focusLevel = parseInt(document.getElementById('vandringLevel').value);
            const focusDivision = document.getElementById('vandringDivision').value;
            
            let teams = {};
            matchData.forEach(d => {
                if (search && !d.Analys_Lagnamn.toLowerCase().includes(search)) return;
                let t = d.Analys_Lagnamn;
                if(!teams[t]) teams[t] = { lag: t, history: [] };
                teams[t].history.push({ year: d.Startår_Numerisk, level: d.Nivå, division: d.Division });
            });

            let results = [];
            Object.values(teams).forEach(t => {
                t.history.sort((a,b) => a.year - b.year);
                
                let yearsOnFocus = new Set();
                let promoToHere = 0;
                let relegToHere = 0;

                for(let i=0; i<t.history.length; i++) {
                    let curr = t.history[i];
                    let isMatch = false;
                    if(mode === 'niva') isMatch = (curr.level === focusLevel);
                    else isMatch = (curr.division === focusDivision);

                    if(isMatch) {
                        yearsOnFocus.add(curr.year);
                        if(i > 0 && t.history[i-1].year === curr.year - 1) {
                            let prevLvl = t.history[i-1].level;
                            if(prevLvl > curr.level) promoToHere++;
                            if(prevLvl < curr.level) relegToHere++;
                        }
                    }
                }

                if(yearsOnFocus.size > 0) {
                    let sortedYears = Array.from(yearsOnFocus).sort((a,b) => a-b);
                    let maxStreak = 1;
                    let currentStreak = 1;
                    let maxGap = 0;

                    for(let j=1; j<sortedYears.length; j++) {
                        let diff = sortedYears[j] - sortedYears[j-1];
                        if(diff === 1) {
                            currentStreak++;
                            if(currentStreak > maxStreak) maxStreak = currentStreak;
                        } else {
                            currentStreak = 1;
                            let gap = diff - 1;
                            if(gap > maxGap) maxGap = gap;
                        }
                    }

                    results.push({
                        lag: t.lag, tot_years: sortedYears.length, max_streak: maxStreak,
                        max_gap: maxGap, promo: promoToHere, releg: relegToHere
                    });
                }
            });

            results.sort((a,b) => b.max_streak - a.max_streak || b.tot_years - a.tot_years);

            document.getElementById('vandringHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center" title="Totalt antal kalenderår de spelat på denna position">Totala År</th>
                    <th class="px-4 py-3 text-center font-bold text-blue-700" title="Hur många år i sträck de som mest spelat här">Längsta Svit (år i sträck)</th>
                    <th class="px-4 py-3 text-center text-red-600" title="Längsta tiden de var borta härifrån innan de kom tillbaka">Längsta Frånvaro (år)</th>
                    <th class="px-4 py-3 text-center text-green-600" title="Gånger de klättrat UPP hit från en lägre nivå">Uppflyttad hit (ggr)</th>
                    <th class="px-4 py-3 text-center text-orange-600" title="Gånger de ramlat NER hit från en högre nivå">Degraderad hit (ggr)</th>
                </tr>
            `;

            let tbody = '';
            results.forEach(r => {
                tbody += `
                    <tr class="hover:bg-blue-50 transition-colors">
                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${r.lag}', 'vandring')" title="Klicka för att se alla tabellrader för denna nivå/beteckning">${r.lag}</td>
                        <td class="px-4 py-2 text-center text-gray-600">${r.tot_years}</td>
                        <td class="px-4 py-2 text-center font-bold text-blue-700">${r.max_streak}</td>
                        <td class="px-4 py-2 text-center text-red-500">${r.max_gap > 0 ? r.max_gap : '-'}</td>
                        <td class="px-4 py-2 text-center text-green-600">${r.promo > 0 ? r.promo : '-'}</td>
                        <td class="px-4 py-2 text-center text-orange-600">${r.releg > 0 ? r.releg : '-'}</td>
                    </tr>
                `;
            });
            document.getElementById('vandringBody').innerHTML = tbody;
            let context = mode === 'niva' ? `Nivå ${focusLevel}` : `Seriebeteckning: ${focusDivision}`;
            document.getElementById('vandringCounter').innerText = `Hittade ${results.length} lag som någon gång spelat på ${context}.`;
        }

        // RENDER: ADMINISTRATION
        function renderAdmin() {
            document.getElementById('adminStatsList').innerHTML = `
                <li><span class="font-semibold text-gray-800">Totalt antal matchrader (Nivå 1-5):</span> ${adminData.total_rows}</li>
                <li><span class="font-semibold text-gray-800">Unika Standard-lagnamn:</span> ${adminData.unique_teams}</li>
                <li><span class="font-semibold ${adminData.orphans_count > 0 ? 'text-red-600' : 'text-gray-800'}">Antal föräldralösa lag:</span> ${adminData.orphans_count} st</li>
            `;
            
            let namesHtml = '';
            if(adminData.name_changes.length > 0) {
                adminData.name_changes.forEach(n => {
                    namesHtml += `<li class="border-b border-gray-100 pb-2"><span class="font-bold text-blue-800">${n.standard}</span> har även spelat under alias: <span class="text-gray-600 italic">${n.aliases.join(', ')}</span></li>`;
                });
            } else {
                namesHtml = '<li class="text-gray-500">Inga namnbyten registrerade för giltiga Lag_ID.</li>';
            }
            document.getElementById('adminNameChanges').innerHTML = namesHtml;

            let orphanHtml = '';
            if(adminData.orphans_list.length > 0) {
                adminData.orphans_list.forEach(o => { orphanHtml += `<li>${o}</li>`; });
            } else {
                orphanHtml = '<li class="text-green-600 font-bold">Allt ser perfekt ut! Inga saknade alias.</li>';
            }
            document.getElementById('adminOrphansList').innerHTML = orphanHtml;
            
            let exportHtml = `<tr><td>STATISTIK OCH NAMNBYTEN</td></tr>`;
            adminData.name_changes.forEach(n => { exportHtml += `<tr><td>${n.standard} (Alias: ${n.aliases.join(', ')})</td></tr>`; });
            exportHtml += `<tr><td>SAKNADE ALIAS (ORPHANS)</td></tr>`;
            adminData.orphans_list.forEach(o => { exportHtml += `<tr><td>${o}</td></tr>`; });
            document.getElementById('adminBody').innerHTML = exportHtml;
        }

        // EXPORT CSV
        function exportCSV() {
            let csv = [];
            let activeTab = document.querySelector('.tab-content.active');
            let rows = activeTab.querySelectorAll("table tr");
            if(rows.length === 0) return alert("Det finns ingen tabell att exportera i denna flik.");

            for (let i = 0; i < rows.length; i++) {
                let row = [], cols = rows[i].querySelectorAll("td, th");
                for (let j = 0; j < cols.length; j++) {
                    let text = cols[j].innerText.replace(/"/g, '""');
                    row.push('"' + text + '"');
                }
                csv.push(row.join(";"));
            }
            let csvFile = new Blob(["\\uFEFF" + csv.join("\\n")], {type: "text/csv;charset=utf-8-sig;"});
            let downloadLink = document.createElement("a");
            downloadLink.download = `Fotbollsdata_${currentTabId}.csv`;
            downloadLink.href = window.URL.createObjectURL(csvFile);
            downloadLink.style.display = "none";
            document.body.appendChild(downloadLink);
            downloadLink.click();
        }

        window.onload = function() {
            populateDropdown('maratonStartYear', completedYears);
            populateDropdown('maratonEndYear', completedYears, true, true);
            
            populateDropdown('sasongStartYear', completedYears);
            populateDropdown('sasongEndYear', completedYears, true, true);

            populateDropdown('sasongTeam', allTeams);
            populateDropdown('maratonDivision', allDivisions);
            populateDropdown('sasongDivision', allDivisions);
            populateDropdown('vandringDivision', allDivisions);
            
            renderMaraton();
            renderAdmin();
        };
    </script>
</body>
</html>
"""
    
    html_output = html_template.replace('__JSON_DATA__', json_data)\
                               .replace('__ADMIN_JSON__', json_admin)\
                               .replace('__ONGOING_SEASON__', str(PAGAENDE_SASONG) if PAGAENDE_SASONG else 'null')
    
    output_path = os.path.join(project_root, "Fotbollsanalys_Dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print(f"✅ HTML Dashboard skapad: {os.path.basename(output_path)}")

if __name__ == "__main__":
    master_df, _ = get_master_data()
    if master_df is not None:
        export_html_dashboard(master_df)
        print("\nAllt klart! Du hittar din nya dashboard-fil i mappen ovanför skriptet.")