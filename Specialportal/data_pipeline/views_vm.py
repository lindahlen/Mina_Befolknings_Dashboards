import os
import sys

# =========================================================
# 1. SETUP & SÖKVÄGAR
# =========================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    root_folder = os.path.dirname(current_folder)
    os.chdir(root_folder)
except NameError:
    pass

JSON_FILE = os.path.join("json_data", "vm_data.json")
OUTPUT_HTML = "VM_Dashboard.html"

# =========================================================
# 2. BYGG HTML-MALLEN
# =========================================================
def build_dashboard():
    if not os.path.exists(JSON_FILE):
        print("❌ Hittar inte vm_data.json. Kör bygg_vm_data.py först!")
        sys.exit(1)

    print(f"📖 Läser in data från {JSON_FILE}...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        json_str = f.read()

    print("⚙️ Genererar HTML...")
    
    html_template = """<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fotbolls-VM Historik</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .modal-backdrop { background-color: rgba(0, 0, 0, 0.5); backdrop-filter: blur(2px); }
        .pen-goal { color: #16a34a; font-weight: bold; } 
        .pen-miss { color: #dc2626; font-weight: bold; } 
        .card-yellow { display: inline-block; width: 10px; height: 14px; background-color: #facc15; border-radius: 2px; box-shadow: 0 1px 2px rgba(0,0,0,0.2); margin-left: 4px; vertical-align: middle; }
        .card-red { display: inline-block; width: 10px; height: 14px; background-color: #ef4444; border-radius: 2px; box-shadow: 0 1px 2px rgba(0,0,0,0.2); margin-left: 4px; vertical-align: middle; }
    </style>
</head>
<body class="bg-slate-100 text-slate-800 font-sans min-h-screen flex flex-col">

    <header class="bg-blue-900 text-white shadow-md sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold tracking-tight">🏆 VM-Databasen</h1>
            <a href="internationella_index.html" class="text-blue-200 hover:text-white text-sm font-medium transition flex items-center">
                <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                Tillbaka
            </a>
        </div>
        
        <nav class="max-w-7xl mx-auto px-4 flex space-x-1 overflow-x-auto no-scrollbar pb-2">
            <button onclick="switchTab('tab-turneringar')" class="tab-btn px-4 py-2 rounded-t-lg bg-white text-blue-900 font-semibold transition whitespace-nowrap">Turneringar</button>
            <button onclick="switchTab('tab-matcher')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap">Turneringsdata & Matcher</button>
            <button onclick="switchTab('tab-h2h')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap">Head-to-Head</button>
            <button onclick="switchTab('tab-maraton')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap">Maratontabell</button>
            <button onclick="switchTab('tab-admin')" class="tab-btn px-4 py-2 rounded-t-lg bg-red-800 text-red-200 hover:bg-red-700 transition flex items-center gap-2 whitespace-nowrap">
                <span>⚠️ Admin Kontroll</span>
                <span id="admin-badge" class="bg-red-500 text-white text-xs px-2 py-1 rounded-full hidden">0</span>
            </button>
        </nav>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6 flex-grow w-full">
        
        <!-- FLIK 1: Turneringar -->
        <div id="tab-turneringar" class="tab-content">
            <h2 class="text-2xl font-bold mb-6 text-slate-700">Turneringar genom tiderna</h2>
            <div id="tournaments-grid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"></div>
        </div>

        <!-- FLIK 2: Matcher & Grupper & Träd -->
        <div id="tab-matcher" class="tab-content hidden">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
                <div>
                    <h2 class="text-xl font-bold text-slate-800">Utforska data & resultat</h2>
                    <p class="text-xs text-slate-400 mt-0.5">Välj ett specifikt år för att låsa upp grupptabeller och slutspelsträd</p>
                </div>
                
                <div class="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                    <div class="flex items-center gap-1 bg-slate-50 border border-slate-300 rounded-lg p-1">
                        <button onclick="navigateYear(-1)" class="p-1 px-3 text-slate-600 hover:text-blue-700 hover:bg-blue-50 rounded transition text-xl font-black" title="Föregående turnering">&#10094;</button>
                        <select id="filter-year" class="p-1 bg-transparent border-none focus:outline-none focus:ring-0 font-bold text-slate-700 cursor-pointer" onchange="onYearFilterChange()">
                            <option value="all">Alla turneringar (Endast matchlista)</option>
                        </select>
                        <button onclick="navigateYear(1)" class="p-1 px-3 text-slate-600 hover:text-blue-700 hover:bg-blue-50 rounded transition text-xl font-black" title="Nästa turnering">&#10095;</button>
                    </div>
                    <input type="text" id="search-input" placeholder="Sök lag, arena, fas..." class="p-2 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-64" onkeyup="renderMatches()">
                </div>
            </div>

            <div id="tournament-sub-nav" class="flex border-b border-slate-300 mb-6 hidden space-x-2">
                <button id="sub-tab-btn-list" onclick="switchSubTab('sub-view-list')" class="px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm">📋 Matchlista</button>
                <button id="sub-tab-btn-groups" onclick="switchSubTab('sub-view-groups')" class="px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition">📊 Grupptabeller</button>
                <button id="sub-tab-btn-tree" onclick="switchSubTab('sub-view-tree')" class="px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition">🌿 Slutspelsträd</button>
            </div>
            
            <div id="sub-view-list" class="sub-view-content bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="max-h-[70vh] overflow-y-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                            <tr>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                            </tr>
                        </thead>
                        <tbody id="matches-list" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
                <p id="matches-count" class="text-sm text-slate-500 p-2 text-right bg-slate-50 border-t border-slate-200"></p>
            </div>

            <div id="sub-view-groups" class="sub-view-content hidden space-y-8">
                <div id="group-stage-container" class="grid grid-cols-1 lg:grid-cols-2 gap-8"></div>
            </div>

            <div id="sub-view-tree" class="sub-view-content hidden overflow-x-auto p-4 bg-white rounded-xl border border-slate-200 shadow-sm relative">
                <div class="flex justify-between items-center mb-4 sticky left-0">
                    <h3 class="font-bold text-slate-700">Slutspelsträd</h3>
                    <select id="tree-start-filter" onchange="renderKnockoutTree(document.getElementById('filter-year').value)" class="p-1.5 text-xs font-medium border border-slate-300 rounded shadow-sm focus:outline-none">
                        <option value="Sextondelsfinal">Från 1/16-final</option>
                        <option value="Åttondelsfinal" selected>Från 1/8-final</option>
                        <option value="Kvartsfinal">Från Kvartsfinal</option>
                        <option value="Semifinal">Från Semifinal</option>
                    </select>
                </div>
                <div id="knockout-tree-container" class="flex space-x-6 min-w-[1000px] pb-4"></div>
            </div>
        </div>

        <!-- FLIK 3: HEAD TO HEAD (H2H) -->
        <div id="tab-h2h" class="tab-content hidden">
            <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-6 flex justify-between items-center">
                    Analysera inbördes möten
                    <span class="text-blue-500 cursor-help" title="Statistik baserad på ordinarie tid och eventuell förlängning.">ⓘ</span>
                </h2>
                
                <div class="flex flex-col md:flex-row gap-8 items-center justify-center">
                    <div class="w-full md:w-1/3">
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Lag A (Fokuslag)</label>
                        <select id="h2h-team-a" class="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg font-bold text-slate-800 shadow-inner focus:outline-none focus:ring-2 focus:ring-blue-500" onchange="renderH2H()"></select>
                    </div>
                    <div class="text-2xl font-black text-slate-300">VS</div>
                    <div class="w-full md:w-1/3">
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Lag B (Motståndare)</label>
                        <select id="h2h-team-b" class="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg font-bold text-slate-800 shadow-inner focus:outline-none focus:ring-2 focus:ring-blue-500" onchange="renderH2H()"></select>
                    </div>
                </div>
                <div class="mt-6 flex justify-center">
                    <button onclick="renderH2H()" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-8 rounded shadow transition">Analysera VS</button>
                </div>
            </div>

            <!-- H2H Resultatboxar -->
            <div id="h2h-summary" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6"></div>

            <!-- H2H Matchlista -->
            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="max-h-[60vh] overflow-y-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                            <tr>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Turnering / Fas</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                            </tr>
                        </thead>
                        <tbody id="h2h-matches-list" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- FLIK 4: MARATONTABELL -->
        <div id="tab-maraton" class="tab-content hidden">
            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
                    <h2 class="text-xl font-bold text-slate-800">Historisk Maratontabell</h2>
                    <span class="text-xs text-slate-500 font-medium">Poängberäkning: 3p för vinst, Straffavgöranden räknas som oavgjort</span>
                </div>
                <div class="max-h-[75vh] overflow-y-auto">
                    <table class="w-full text-sm text-left border-collapse">
                        <thead class="bg-blue-900 text-white sticky top-0 z-10">
                            <tr>
                                <th class="p-3 font-semibold w-10 text-center">#</th>
                                <th class="p-3 font-semibold">Nation</th>
                                <th class="p-3 font-semibold text-center w-12" title="Spelade matcher">S</th>
                                <th class="p-3 font-semibold text-center w-12" title="Vinster">V</th>
                                <th class="p-3 font-semibold text-center w-12" title="Oavgjorda">O</th>
                                <th class="p-3 font-semibold text-center w-12" title="Förluster">F</th>
                                <th class="p-3 font-semibold text-center w-20" title="Gjorda-Insläppta">Mål</th>
                                <th class="p-3 font-semibold text-center w-16" title="Målskillnad">MS</th>
                                <th class="p-3 font-bold text-center w-12 text-yellow-300">P</th>
                            </tr>
                        </thead>
                        <tbody id="marathon-table-body" class="divide-y divide-slate-200 bg-white"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- FLIK 5: Admin -->
        <div id="tab-admin" class="tab-content hidden">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-red-800">Kvalitetssäkring & Felsökning</h2>
                <button onclick="renderAdminWarnings()" class="text-sm bg-slate-200 hover:bg-slate-300 px-3 py-1 rounded">Uppdatera logg</button>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-red-200 p-6" id="admin-list-container"></div>
        </div>
    </main>

    <!-- MATCH MODAL -->
    <div id="match-modal" class="fixed inset-0 z-50 hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden relative">
            <div class="bg-blue-900 text-white p-4 flex items-center relative min-h-[60px]">
                <div class="absolute left-4">
                    <span class="text-xl font-black text-blue-200 tracking-wider" id="modal-year"></span>
                </div>
                <div class="flex-1 text-center mt-1">
                    <h3 class="text-lg font-bold uppercase tracking-widest text-white" id="modal-title-center"></h3>
                    <div class="text-[11px] text-blue-300 font-medium uppercase mt-1 tracking-wider" id="modal-match-id"></div>
                </div>
                <div class="absolute right-4">
                    <button onclick="closeModal()" class="text-white hover:text-blue-200 p-2 flex items-center gap-2 transition">
                        <span class="text-sm font-semibold uppercase tracking-widest hidden sm:inline">Stäng</span>
                        <span class="text-3xl leading-none">&times;</span>
                    </button>
                </div>
            </div>
            <div class="p-0 overflow-y-auto flex-1">
                <div class="bg-white p-6 border-b border-slate-200 text-center">
                    <div class="text-sm text-slate-500 mb-4">
                        <span id="modal-arena"></span>, <span id="modal-city"></span> 
                        &bull; Publik: <span id="modal-attendance"></span> 
                        &bull; Domare: <span id="modal-referee"></span>
                    </div>
                    <div class="flex justify-center items-center gap-6 md:gap-12">
                        <div class="flex-1 text-right text-2xl md:text-3xl font-bold truncate" id="modal-home"></div>
                        <div class="text-4xl md:text-5xl font-black text-blue-900 bg-slate-50 px-4 py-2 rounded-lg border border-slate-200 shadow-inner" id="modal-score"></div>
                        <div class="flex-1 text-left text-2xl md:text-3xl font-bold truncate" id="modal-away"></div>
                    </div>
                    <div id="modal-score-details" class="text-sm text-slate-500 mt-3 font-medium"></div>
                </div>
                
                <div class="p-6 bg-slate-50">
                    <h4 class="text-sm font-bold uppercase text-slate-400 mb-3 text-center tracking-widest">Matchhändelser</h4>
                    <div class="max-w-xl mx-auto bg-white border border-slate-200 rounded-lg shadow-sm p-4" id="modal-events"></div>
                    <div id="modal-penalties-container" class="max-w-xl mx-auto mt-4 hidden">
                        <h5 class="text-xs font-bold uppercase text-slate-500 mb-2 text-center border-b border-slate-200 pb-1">Straffsparksläggning</h5>
                        <div class="grid grid-cols-2 gap-4 text-sm" id="modal-penalties"></div>
                    </div>
                </div>

                <div class="p-6 bg-white border-t border-slate-200">
                    <h4 class="text-sm font-bold uppercase text-slate-400 mb-4 text-center tracking-widest">Laguppställningar</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div>
                            <div class="font-bold text-lg mb-3 border-b-2 border-blue-900 pb-1" id="modal-lineup-home-title"></div>
                            <ul id="modal-lineup-home" class="space-y-1 text-sm"></ul>
                            <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500"><strong>Förbundskapten:</strong> <span id="modal-coach-home"></span></div>
                        </div>
                        <div>
                            <div class="font-bold text-lg mb-3 border-b-2 border-blue-900 pb-1" id="modal-lineup-away-title"></div>
                            <ul id="modal-lineup-away" class="space-y-1 text-sm"></ul>
                            <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500"><strong>Förbundskapten:</strong> <span id="modal-coach-away"></span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const db = __JSON_DATA_PLACEHOLDER__;
        const safeText = (text) => text === null || text === undefined || text === "null" ? "" : text;
        const formatScore = (m) => m.score.home_total !== null ? `${m.score.home_total} - ${m.score.away_total}` : 'Ej spelad';

        const formatName = (nameStr) => {
            if (!nameStr || nameStr === "null") return "";
            let s = String(nameStr);
            if (s.includes(',')) {
                const parts = s.split(',');
                return `${parts[1].trim()} ${parts[0].trim()}`;
            }
            return s.trim();
        };

        // Extraherar alla unika lag för dropdowns och maratontabell
        function getAllTeams() {
            let teams = new Set();
            Object.values(db.matches).forEach(m => {
                if(m.home_team) teams.add(m.home_team);
                if(m.away_team) teams.add(m.away_team);
            });
            return Array.from(teams).sort();
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-white', 'text-blue-900', 'font-semibold');
                btn.classList.add('bg-blue-800', 'text-blue-200');
                if(btn.innerText.includes('Admin')) {
                    btn.classList.remove('bg-red-800', 'text-red-200');
                    btn.classList.add('bg-red-800', 'text-red-200');
                }
            });
            document.getElementById(tabId).classList.remove('hidden');
            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
            if(activeBtn && !tabId.includes('admin')) {
                activeBtn.classList.remove('bg-blue-800', 'text-blue-200');
                activeBtn.classList.add('bg-white', 'text-blue-900', 'font-semibold');
            } else if (activeBtn && tabId.includes('admin')) {
                 activeBtn.classList.remove('bg-red-800', 'text-red-200');
                 activeBtn.classList.add('bg-white', 'text-red-900', 'font-semibold');
            }
            
            // Ladda specifikt innehåll när en tab öppnas
            if(tabId === 'tab-h2h') populateH2HSelectors();
            if(tabId === 'tab-maraton') renderMarathonTable();
        }

        function switchSubTab(subViewId) {
            document.querySelectorAll('.sub-view-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(subViewId).classList.remove('hidden');
            
            const tabs = [
                {id: 'sub-view-list', btn: 'sub-tab-btn-list'},
                {id: 'sub-view-groups', btn: 'sub-tab-btn-groups'},
                {id: 'sub-view-tree', btn: 'sub-tab-btn-tree'}
            ];
            
            tabs.forEach(t => {
                const btn = document.getElementById(t.btn);
                if (t.id === subViewId) {
                    btn.className = "px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm";
                } else {
                    btn.className = "px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition";
                }
            });
        }

        function onYearFilterChange() {
            const year = document.getElementById('filter-year').value;
            const subNav = document.getElementById('tournament-sub-nav');
            
            if (year === 'all') {
                subNav.classList.add('hidden');
                switchSubTab('sub-view-list');
            } else {
                subNav.classList.remove('hidden');
                renderGroupStage(year);
                renderKnockoutTree(year);
            }
            renderMatches();
        }

        function renderTournaments() {
            const container = document.getElementById('tournaments-grid');
            const years = Object.keys(db.tournaments).sort((a, b) => b - a);
            
            let html = '';
            years.forEach(year => {
                const t = db.tournaments[year];
                const stats = t.stats || {total_goals: 0, total_attendance: 0, matches_played: 0};
                const avgGoals = stats.matches_played > 0 ? (stats.total_goals / stats.matches_played).toFixed(2) : "0";
                const avgAtt = stats.matches_played > 0 ? Math.round(stats.total_attendance / stats.matches_played).toLocaleString('sv-SE') : "0";

                html += `
                    <div onclick="filterByYear('${year}')" class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 cursor-pointer hover:shadow-md hover:border-blue-300 transition group flex justify-between gap-2">
                        <div class="flex flex-col justify-between">
                            <div>
                                <h3 class="text-3xl font-black text-blue-900 leading-none group-hover:text-blue-600 transition">${year}</h3>
                                <p class="text-sm font-medium text-slate-500 mt-1">${t.host}</p>
                            </div>
                            <div class="mt-3 inline-block bg-yellow-50 border border-yellow-200 text-yellow-800 text-[11px] px-2 py-1 rounded font-bold truncate self-start">
                                🏆 ${t.winner || 'Okänd'}
                            </div>
                        </div>
                        <div class="flex flex-col items-end justify-between min-w-[85px]">
                            <div class="bg-slate-100 text-slate-600 text-[11px] px-2 py-1 rounded w-full text-center font-bold shadow-sm border border-slate-200">${t.matches.length} matcher</div>
                            <div class="text-[11px] text-slate-500 w-full bg-slate-50 p-1.5 rounded border border-slate-100 mt-2 flex flex-col gap-0.5">
                                <div class="flex justify-between"><span>⚽</span> <span class="font-bold text-slate-700">${stats.total_goals}</span></div>
                                <div class="flex justify-between"><span>📈</span> <span class="font-bold text-slate-700">${avgGoals}</span></div>
                                <div class="flex justify-between"><span>👥</span> <span class="font-bold text-slate-700">${avgAtt}</span></div>
                            </div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        function navigateYear(direction) {
            const select = document.getElementById('filter-year');
            const validYears = Object.keys(db.tournaments).sort((a, b) => a - b); 
            let currentIndex = validYears.indexOf(select.value);
            if (select.value === 'all') { currentIndex = direction > 0 ? -1 : validYears.length; }
            let newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < validYears.length) { filterByYear(validYears[newIndex]); }
        }

        function filterByYear(year) {
            document.getElementById('filter-year').value = year;
            switchTab('tab-matcher');
            onYearFilterChange();
        }

        function populateYearFilter() {
            const select = document.getElementById('filter-year');
            const years = Object.keys(db.tournaments).sort((a, b) => b - a);
            years.forEach(year => {
                const opt = document.createElement('option');
                opt.value = year;
                opt.innerText = year;
                select.appendChild(opt);
            });
        }

        function renderMatches() {
            const container = document.getElementById('matches-list');
            const counter = document.getElementById('matches-count');
            const filterYear = document.getElementById('filter-year').value;
            const searchTerm = document.getElementById('search-input').value.toLowerCase();
            
            let html = '';
            let count = 0;
            let currentPhase = ''; 
            
            const getPhaseWeight = (m) => {
                if (!m.phase) return 0;
                let p = m.phase.toLowerCase();
                
                // --- NY LOGIK FÖR FINAL 1950 (Eller andra specialfinaler med kod 5/6) ---
                if (m.advancement && (m.advancement.code === 5 || m.advancement.code === 6 || m.advancement.is_final === true)) {
                    return 1000; // Överordnad all annan text!
                }
                
                if (p.includes("final") && !p.includes("kvarts") && !p.includes("semi") && !p.includes("åtton") && !p.includes("sexton") && !p.includes("omgång")) return 100;
                // --- NY LOGIK FÖR MATCH OM 3:E PRIS / BRONS ---
                if (p.includes("tredje") || p.includes("brons") || p.includes("3:e")) return 90;
                if (p.includes("semi")) return 80;
                if (p.includes("kvarts")) return 70;
                if (p.includes("åtton")) return 60;
                if (p.includes("sexton")) return 50;
                return 10;
            };

            let matchArray = Object.values(db.matches).sort((a, b) => {
                let diff = new Date(b.date) - new Date(a.date);
                if (diff !== 0 && !isNaN(diff)) return diff;
                // Om datumet är exakt samma, låt viktningen avgöra (Högst vikt visas först)
                return getPhaseWeight(b) - getPhaseWeight(a);
            });

            matchArray.forEach(m => {
                const matchYear = m.date.substring(0, 4);
                if (filterYear !== 'all' && matchYear !== filterYear) return;
                if (searchTerm && !`${m.home_team} ${m.away_team} ${m.arena} ${m.city} ${m.phase} ${matchYear}`.toLowerCase().includes(searchTerm)) return;

                if (m.phase !== currentPhase) {
                    html += `<tr><td colspan="4" class="bg-slate-200 text-slate-700 font-bold text-xs uppercase px-3 py-2 border-y border-slate-300 tracking-wider">${m.phase}</td></tr>`;
                    currentPhase = m.phase;
                }

                count++;
                const isPlayed = m.score.home_total !== null;
                const scoreClass = isPlayed ? "font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200" : "text-slate-400 text-xs";
                
                html += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100"><div class="text-xs font-semibold text-slate-500">${m.date}</div></td>
                        <td class="p-3 border-t border-slate-100 text-right font-medium group-hover:text-blue-700">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="${scoreClass}">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 font-medium group-hover:text-blue-700">${m.away_team}</td>
                    </tr>
                `;
            });
            container.innerHTML = html;
            counter.innerText = `Visar ${count} matcher`;
        }

        // =========================================================
        // 📊 GRUPPSTABELLER
        // =========================================================
        function renderGroupStage(year) {
            const container = document.getElementById('group-stage-container');
            let groupMatches = Object.values(db.matches).filter(m => m.date.substring(0,4) === year && m.advancement.is_group_match);
            
            if (groupMatches.length === 0) {
                container.innerHTML = '<div class="col-span-2 p-8 text-center text-slate-400 italic bg-white rounded-xl border">Denna turnering innehöll inget traditionellt gruppspel i databasen.</div>';
                return;
            }

            let groups = {};
            groupMatches.forEach(m => {
                let phase = m.phase || "Gruppspel";
                if (!groups[phase]) groups[phase] = { teams: {} };
                
                [m.home_team, m.away_team].forEach(t => {
                    if (!groups[phase].teams[t]) {
                        groups[phase].teams[t] = { name: t, S: 0, V: 0, O: 0, F: 0, GM: 0, IM: 0, P: 0 };
                    }
                });

                if (m.score.home_total !== null && m.score.away_total !== null) {
                    let h = groups[phase].teams[m.home_team];
                    let a = groups[phase].teams[m.away_team];
                    let hg = m.score.home_total;
                    let ag = m.score.away_total;
                    let ptsWin = m.advancement.points_for_win || 2; 

                    h.S++; a.S++;
                    h.GM += hg; h.IM += ag;
                    a.GM += ag; a.IM += hg;

                    if (hg > ag) { h.V++; h.P += ptsWin; a.F++; }
                    else if (ag > hg) { a.V++; a.P += ptsWin; h.F++; }
                    else { h.O++; a.O++; h.P += 1; a.P += 1; }
                }
            });

            let html = '';
            Object.keys(groups).sort().forEach(gName => {
                let sortedTeams = Object.values(groups[gName].teams).sort((a,b) => {
                    if (b.P !== a.P) return b.P - a.P;
                    let diffA = a.GM - a.IM;
                    let diffB = b.GM - b.IM;
                    if (diffB !== diffA) return diffB - diffA;
                    return b.GM - a.GM;
                });

                html += `
                    <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
                        <h3 class="font-black text-lg text-blue-900 border-b pb-1.5 mb-3 uppercase tracking-wider">${gName}</h3>
                        <table class="w-full text-sm text-left border-collapse">
                            <thead>
                                <tr class="text-slate-400 text-xs border-b">
                                    <th class="pb-1 font-semibold">Lag</th>
                                    <th class="pb-1 font-semibold text-center w-8">S</th>
                                    <th class="pb-1 font-semibold text-center w-8">V</th>
                                    <th class="pb-1 font-semibold text-center w-8">O</th>
                                    <th class="pb-1 font-semibold text-center w-8">F</th>
                                    <th class="pb-1 font-semibold text-center w-16">Mål</th>
                                    <th class="pb-1 font-bold text-center w-8 text-blue-900">P</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                `;

                sortedTeams.forEach((t, idx) => {
                    let diff = t.GM - t.IM;
                    let diffStr = diff > 0 ? `+${diff}` : diff;
                    let rowClass = idx < 2 ? "bg-blue-50/40 font-bold" : ""; 
                    html += `
                        <tr class="${rowClass}">
                            <td class="py-2 text-slate-900">${t.name}</td>
                            <td class="py-2 text-center text-slate-500">${t.S}</td>
                            <td class="py-2 text-center text-green-600">${t.V}</td>
                            <td class="py-2 text-center text-slate-400">${t.O}</td>
                            <td class="py-2 text-center text-red-500">${t.F}</td>
                            <td class="py-2 text-center text-xs text-slate-500">${t.GM}-${t.IM} <span class="text-[10px] font-normal">(${diffStr})</span></td>
                            <td class="py-2 text-center font-black text-blue-900">${t.P}</td>
                        </tr>
                    `;
                });
                html += `</tbody></table></div>`;
            });
            container.innerHTML = html;
        }

        // =========================================================
        // 🌿 SLUTSPELSTRÄD MED FILTRERING & BRONS UNDER FINAL
        // =========================================================
        function buildMatchCard(m, theme = 'slate') {
            let homeWinner = m.advancement.advancing_team === m.home_team;
            let awayWinner = m.advancement.advancing_team === m.away_team;
            let borderColor = theme === 'amber' ? 'border-amber-300' : 'border-slate-200';
            let hoverBorder = theme === 'amber' ? 'hover:border-amber-500' : 'hover:border-blue-400';
            let textColorHome = homeWinner ? (theme==='amber'?'text-amber-800':'text-blue-900') : 'text-slate-500';
            let textColorAway = awayWinner ? (theme==='amber'?'text-amber-800':'text-blue-900') : 'text-slate-500';

            return `
                <div onclick="openMatchModal('${m.id}')" class="bg-white p-3 rounded-lg border ${borderColor} shadow-sm my-3 ${hoverBorder} hover:shadow transition cursor-pointer group text-xs">
                    <div class="text-[10px] text-slate-400 font-bold mb-1.5 flex justify-between">
                        <span>ID: ${m.id}</span> <span>${m.date}</span>
                    </div>
                    <div class="space-y-1.5 font-medium">
                        <div class="flex justify-between items-center ${homeWinner ? 'font-black '+textColorHome : 'text-slate-500'}">
                            <span class="truncate pr-1">${m.home_team}</span>
                            <span>${m.score.home_total !== null ? m.score.home_total : '-'}</span>
                        </div>
                        <div class="flex justify-between items-center ${awayWinner ? 'font-black '+textColorAway : 'text-slate-500'}">
                            <span class="truncate pr-1">${m.away_team}</span>
                            <span>${m.score.away_total !== null ? m.score.away_total : '-'}</span>
                        </div>
                    </div>
                    ${m.score.home_pen !== null ? `<div class="text-[9px] text-center text-slate-400 font-bold mt-1 border-t pt-1">Str: ${m.score.home_pen}-${m.score.away_pen}</div>` : ''}
                </div>
            `;
        }

        function renderKnockoutTree(year) {
            const container = document.getElementById('knockout-tree-container');
            let koMatches = Object.values(db.matches).filter(m => m.date.substring(0,4) === year && (!m.advancement.is_group_match || m.phase.toLowerCase().includes('finalomgång')));
            
            if (koMatches.length === 0) {
                container.innerHTML = '<div class="p-8 text-center text-slate-400 italic w-full">Denna turnering avgjordes helt via gruppspel / slutgrupper.</div>';
                return;
            }

            let allPhases = ["Sextondelsfinal", "Åttondelsfinal", "Kvartsfinal", "Semifinal", "Finalomgång", "Final"];
            let treeData = {};
            allPhases.forEach(p => treeData[p] = []);
            treeData["Bronsmatch"] = [];
            
            koMatches.forEach(m => {
                let p_lower = m.phase.toLowerCase();
                
                // --- NY LOGIK FÖR ATT FÅNGA BRONS/3:E PRIS ---
                if (p_lower.includes("tredje") || p_lower.includes("brons") || p_lower.includes("3:e")) {
                    treeData["Bronsmatch"].push(m);
                } else if (p_lower.includes("sextondelsfinal")) {
                    treeData["Sextondelsfinal"].push(m);
                } else if (p_lower.includes("åttondelsfinal")) {
                    treeData["Åttondelsfinal"].push(m);
                } else if (p_lower.includes("kvartsfinal")) {
                    treeData["Kvartsfinal"].push(m);
                } else if (p_lower.includes("semifinal")) {
                    treeData["Semifinal"].push(m);
                } else if (p_lower.includes("finalomgång")) {
                    treeData["Finalomgång"].push(m);
                } else if (p_lower.includes("final")) {
                    treeData["Final"].push(m);
                }
            });

            const startFilter = document.getElementById('tree-start-filter') ? document.getElementById('tree-start-filter').value : "Sextondelsfinal";
            let startIndex = allPhases.indexOf(startFilter);
            if(startIndex === -1) startIndex = 0;
            
            let visiblePhases = allPhases.slice(startIndex);
            if(!visiblePhases.includes("Finalomgång")) visiblePhases.push("Finalomgång");
            if(!visiblePhases.includes("Final")) visiblePhases.push("Final");
            visiblePhases = [...new Set(visiblePhases)];

            let html = '';
            visiblePhases.forEach(pName => {
                let mList = treeData[pName];
                
                if (mList.length === 0 && pName !== "Final") return;
                if (mList.length === 0 && pName === "Final" && treeData["Bronsmatch"].length === 0) return;

                html += `<div class="flex-1 flex flex-col justify-around bg-slate-50/60 p-3 rounded-xl border border-slate-200/80 min-w-[220px]">`;
                html += `<h4 class="text-center font-black text-xs uppercase tracking-widest text-slate-400 border-b pb-2 mb-4">${pName}</h4>`;
                
                mList.sort((a,b) => new Date(a.date) - new Date(b.date));
                mList.forEach(m => { html += buildMatchCard(m); });
                
                if (pName === "Final" && treeData["Bronsmatch"].length > 0) {
                    html += `<div class="mt-8 border-t-2 border-dashed border-amber-200 pt-4">`;
                    html += `<h4 class="text-center font-black text-xs uppercase tracking-widest text-amber-600 mb-2">🏆 Bronsmatch</h4>`;
                    treeData["Bronsmatch"].sort((a,b) => new Date(a.date) - new Date(b.date)).forEach(bm => {
                        html += buildMatchCard(bm, 'amber');
                    });
                    html += `</div>`;
                }
                
                html += `</div>`;
            });
            container.innerHTML = html;
        }

        // =========================================================
        // 📊 NYTT: MARATONTABELL
        // =========================================================
        function renderMarathonTable() {
            const container = document.getElementById('marathon-table-body');
            let teams = {};

            Object.values(db.matches).forEach(m => {
                if (m.score.home_total === null) return; // Matchen ej spelad ännu
                
                [m.home_team, m.away_team].forEach(t => {
                    if (!teams[t]) teams[t] = { name: t, S:0, V:0, O:0, F:0, GM:0, IM:0, P:0 };
                });

                let h = teams[m.home_team];
                let a = teams[m.away_team];
                
                let hg = m.score.home_total;
                let ag = m.score.away_total;

                h.S++; a.S++;
                h.GM += hg; h.IM += ag;
                a.GM += ag; a.IM += hg;

                // Historisk statistik-regel: Matcher avgjorda på straffar bokförs som Oavgjort i maratontabeller!
                if (hg > ag) {
                    h.V++; h.P += 3; a.F++;
                } else if (ag > hg) {
                    a.V++; a.P += 3; h.F++;
                } else {
                    h.O++; a.O++; h.P += 1; a.P += 1;
                }
            });

            let sortedTeams = Object.values(teams).sort((a,b) => {
                if (b.P !== a.P) return b.P - a.P;
                let diffA = a.GM - a.IM;
                let diffB = b.GM - b.IM;
                if (diffB !== diffA) return diffB - diffA;
                return b.GM - a.GM; // Flest gjorda mål avgör
            });

            let html = '';
            sortedTeams.forEach((t, idx) => {
                let diff = t.GM - t.IM;
                let diffStr = diff > 0 ? `+${diff}` : diff;
                let rankClass = idx < 10 ? "font-bold text-slate-800" : "text-slate-600";
                
                html += `
                    <tr class="hover:bg-blue-50 transition border-b border-slate-100 last:border-0">
                        <td class="p-3 text-center text-xs text-slate-400 font-bold">${idx + 1}</td>
                        <td class="p-3 ${rankClass}">${t.name}</td>
                        <td class="p-3 text-center font-medium">${t.S}</td>
                        <td class="p-3 text-center text-green-600">${t.V}</td>
                        <td class="p-3 text-center text-slate-500">${t.O}</td>
                        <td class="p-3 text-center text-red-500">${t.F}</td>
                        <td class="p-3 text-center text-xs text-slate-500">${t.GM}-${t.IM} <span class="font-normal text-[10px]">(${diffStr})</span></td>
                        <td class="p-3 text-center font-medium text-slate-700">${diffStr}</td>
                        <td class="p-3 text-center font-black text-blue-900">${t.P}</td>
                    </tr>
                `;
            });
            
            container.innerHTML = html;
        }

        // =========================================================
        // 📊 NYTT: HEAD-TO-HEAD (H2H)
        // =========================================================
        function populateH2HSelectors() {
            const selectA = document.getElementById('h2h-team-a');
            const selectB = document.getElementById('h2h-team-b');
            
            // Kolla om de redan är fyllda
            if (selectA.options.length > 0) return; 

            const teams = getAllTeams();
            
            teams.forEach(t => {
                selectA.add(new Option(t, t));
                selectB.add(new Option(t, t));
            });

            // Sätt defaultvärden (Om de finns, annars tar den de första i listan)
            if (teams.includes("Brasilien")) selectA.value = "Brasilien";
            if (teams.includes("Tyskland")) selectB.value = "Tyskland";
            
            renderH2H(); // Kör renderingen direkt när fliken öppnas
        }

        function renderH2H() {
            const teamA = document.getElementById('h2h-team-a').value;
            const teamB = document.getElementById('h2h-team-b').value;
            const container = document.getElementById('h2h-matches-list');
            const summaryContainer = document.getElementById('h2h-summary');
            
            if(!teamA || !teamB) return;

            let h2hMatches = Object.values(db.matches).filter(m => {
                if(m.score.home_total === null) return false;
                return (m.home_team === teamA && m.away_team === teamB) || (m.home_team === teamB && m.away_team === teamA);
            });

            // Sortera kronologiskt (äldst först)
            h2hMatches.sort((a,b) => new Date(a.date) - new Date(b.date));

            let winsA = 0;
            let winsB = 0;
            let draws = 0;

            let html = '';
            h2hMatches.forEach(m => {
                // Summera statistik
                if(m.score.home_total > m.score.away_total) {
                    if(m.home_team === teamA) winsA++; else winsB++;
                } else if(m.score.away_total > m.score.home_total) {
                    if(m.away_team === teamA) winsA++; else winsB++;
                } else {
                    // Straffar avgör vinnare
                    if(m.score.home_pen !== null && m.score.away_pen !== null) {
                        if(m.score.home_pen > m.score.away_pen) {
                            if(m.home_team === teamA) winsA++; else winsB++;
                        } else {
                            if(m.away_team === teamA) winsA++; else winsB++;
                        }
                    } else {
                        draws++;
                    }
                }

                const scoreClass = "font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200";
                const isHomeA = m.home_team === teamA;
                
                html += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100">
                            <div class="text-[10px] uppercase font-bold text-blue-900">${m.date.substring(0,4)}</div>
                            <div class="text-xs text-slate-500">${m.phase}</div>
                        </td>
                        <td class="p-3 border-t border-slate-100">
                            <div class="text-xs text-slate-500">${m.date}</div>
                        </td>
                        <td class="p-3 border-t border-slate-100 text-right ${isHomeA ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="${scoreClass}">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 ${!isHomeA ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.away_team}</td>
                    </tr>
                `;
            });

            container.innerHTML = html;

            // Bygg H2H Summary Boxar
            let total = h2hMatches.length;
            summaryContainer.innerHTML = `
                <div class="bg-indigo-50 border border-indigo-100 p-4 rounded-xl text-center shadow-sm">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-indigo-400 mb-1">Möten</div>
                    <div class="text-3xl font-black text-indigo-900">${total}</div>
                </div>
                <div class="bg-emerald-50 border border-emerald-100 p-4 rounded-xl text-center shadow-sm">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">Vinster ${teamA}</div>
                    <div class="text-3xl font-black text-emerald-700">${winsA}</div>
                </div>
                <div class="bg-slate-50 border border-slate-200 p-4 rounded-xl text-center shadow-sm">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Oavgjorda</div>
                    <div class="text-3xl font-black text-slate-600">${draws}</div>
                </div>
                <div class="bg-rose-50 border border-rose-100 p-4 rounded-xl text-center shadow-sm md:col-start-2 md:col-span-2 lg:col-start-auto lg:col-span-1">
                    <div class="text-[10px] font-bold uppercase tracking-widest text-rose-500 mb-1">Vinster ${teamB}</div>
                    <div class="text-3xl font-black text-rose-700">${winsB}</div>
                </div>
            `;
        }

        // =========================================================
        // MATCH MODAL & ADMIN 
        // =========================================================
        function openMatchModal(matchId) {
            const m = db.matches[matchId];
            if (!m) return;
            
            document.getElementById('modal-year').innerText = m.date.substring(0,4);
            document.getElementById('modal-title-center').innerText = `${m.phase} • ${m.date}`;
            document.getElementById('modal-match-id').innerText = `Match-ID: ${m.id}`;
            document.getElementById('modal-arena').innerText = safeText(m.arena);
            document.getElementById('modal-city').innerText = safeText(m.city);
            document.getElementById('modal-attendance').innerText = m.attendance ? m.attendance.toLocaleString('sv-SE') : 'Okänt';
            
            let refName = formatName(m.referee);
            document.getElementById('modal-referee').innerText = refName ? `${refName}${m.referee_country && m.referee_country !== 'null' ? ` (${m.referee_country})` : ''}` : 'Okänd';
            
            document.getElementById('modal-home').innerText = m.home_team;
            document.getElementById('modal-away').innerText = m.away_team;
            document.getElementById('modal-score').innerText = formatScore(m);

            let detailsHtml = '';
            if (m.score.home_ht !== null) detailsHtml += `HT: ${m.score.home_ht}-${m.score.away_ht}`;
            if (m.score.home_et !== null) detailsHtml += ` &bull; Efter full tid: ${m.score.home_et}-${m.score.away_et}`;
            if (m.score.home_pen !== null) detailsHtml += ` &bull; Straffar: ${m.score.home_pen}-${m.score.away_pen}`;
            document.getElementById('modal-score-details').innerHTML = detailsHtml;

            // --- MATCHHÄNDELSER (Mål & Kort) ---
            const eventsContainer = document.getElementById('modal-events');
            let eventsArray = [];
            
            m.events.goals.forEach(g => {
                let goalText = "";
                const pName = g.player ? g.player.trim() : "";
                const noteText = g.note ? g.note.trim() : "";
                
                if (pName.toLowerCase() === "självmål") {
                    if (noteText && noteText !== "null" && noteText !== "") goalText = `⚽ Självmål av ${formatName(noteText)}`;
                    else goalText = `⚽ Självmål`;
                } else {
                    let typeStr = g.type && g.type !== 'Spelmål' && g.type !== 'Okänt' && g.type !== 'null' ? ` - ${g.type}` : '';
                    let noteStr = noteText && noteText !== 'null' ? ` (${noteText})` : '';
                    goalText = `⚽ ${formatName(g.player)}${typeStr}${noteStr}`;
                }
                eventsArray.push({min: parseInt(g.minute) || 999, raw_min: g.minute, text: goalText, team: g.team});
            });
            
            m.events.cards.forEach(c => {
                eventsArray.push({min: parseInt(c.minute) || 999, raw_min: c.minute, text: `<span class="card-red"></span> ${formatName(c.player)}`, team: m.home_team});
            });
            
            eventsArray.sort((a,b) => a.min - b.min);
            
            if (eventsArray.length > 0) {
                let evHtml = '<ul class="space-y-2 text-sm">';
                eventsArray.forEach(ev => {
                    const isHome = ev.team === m.home_team;
                    const alignClass = ev.team ? (isHome ? 'text-left' : 'text-right') : 'text-center text-slate-500';
                    evHtml += `<li class="${alignClass} border-b border-slate-100 pb-1 last:border-0"><span class="font-bold text-slate-400 text-xs w-8 inline-block">${ev.raw_min}'</span> ${ev.text}</li>`;
                });
                evHtml += '</ul>';
                eventsContainer.innerHTML = evHtml;
            } else {
                eventsContainer.innerHTML = '<p class="text-center text-slate-400 text-sm italic">Inga specifika mål- eller kortuppgifter registrerade.</p>';
            }

            // --- STRAFFAR ---
            const penContainerBox = document.getElementById('modal-penalties-container');
            const penContainer = document.getElementById('modal-penalties');
            
            if (m.events.penalties && m.events.penalties.length > 0) {
                penContainerBox.classList.remove('hidden');
                let homePens = m.events.penalties.filter(p => p.team === m.home_team).sort((a, b) => a.penalty_nr - b.penalty_nr);
                let awayPens = m.events.penalties.filter(p => p.team === m.away_team).sort((a, b) => a.penalty_nr - b.penalty_nr);
                
                const buildPens = (pens, isHome) => {
                    let p_html = `<div class="${isHome ? '' : 'text-right'}"><ul class="space-y-1">`;
                    pens.forEach(p => {
                        let outcomeText = p.outcome ? String(p.outcome).trim() : '';
                        let outcomeLower = outcomeText.toLowerCase();
                        let isGoal = !outcomeLower.includes('miss') && outcomeText !== ''; 
                        let icon = isGoal ? '<span class="pen-goal text-lg leading-none align-middle">✓</span>' : '<span class="pen-miss text-lg leading-none align-middle">✗</span>';
                        let outcomeDisplay = '';
                        if (outcomeLower !== 'mål' && outcomeLower !== 'miss' && outcomeLower !== 'ja' && outcomeLower !== '1' && outcomeText !== '') {
                            outcomeDisplay = ` <span class="text-xs font-bold text-slate-500">${outcomeText}</span>`;
                        }
                        let nrVal = p.penalty_nr;
                        let hasNr = nrVal !== null && nrVal !== undefined && nrVal !== "" && String(nrVal) !== "null";
                        let leftText = isHome ? (hasNr ? `${nrVal}. ` : '') + icon + outcomeDisplay : formatName(p.player);
                        let rightText = isHome ? formatName(p.player) : outcomeDisplay + ' ' + icon + (hasNr ? ` <span class="text-xs text-slate-400">(${nrVal})</span>` : '');
                        p_html += `<li class="border-b border-slate-100 pb-1 last:border-0">${leftText} ${rightText}</li>`;
                    });
                    return p_html + '</ul></div>';
                };
                
                penContainer.innerHTML = buildPens(homePens, true) + buildPens(awayPens, false);
            } else {
                penContainerBox.classList.add('hidden');
            }

            // --- LAGUPPSTÄLLNINGAR ---
            const renderLineup = (teamData, elementId) => {
                const el = document.getElementById(elementId);
                if (!teamData || teamData.length === 0) { el.innerHTML = '<li class="text-slate-400 italic">Laguppställning saknas</li>'; return; }
                
                teamData.sort((a, b) => {
                    let posA = parseInt(a.position); let posB = parseInt(b.position);
                    if (isNaN(posA)) posA = 99; if (isNaN(posB)) posB = 99;
                    return posA - posB;
                });

                let lHtml = '';
                teamData.forEach((p, index) => {
                    if (index === 11) lHtml += `<li class="py-3 mt-3 mb-1 border-t-2 border-slate-200 text-center text-xs font-black text-slate-400 uppercase tracking-widest bg-slate-50">Avbytare</li>`;

                    const subStr = p.sub ? String(p.sub).toLowerCase().trim() : '';
                    const cardStr = p.card ? String(p.card).toLowerCase().trim() : (p.status ? String(p.status).toLowerCase().trim() : '');
                    const isCap = p.captain && String(p.captain).toLowerCase().includes('c');
                    
                    let subIcon = '', cardIcon = '', capIcon = isCap ? `<span class="text-blue-700 font-black ml-1 text-[10px] bg-blue-100 px-1 rounded shadow-sm">C</span>` : '', eventMin = '';
                    
                    if (subStr.includes('in') && subStr.includes('ut')) subIcon = `<span class="text-green-600 font-bold ml-1 text-[12px]">↑</span><span class="text-red-500 font-bold ml-0.5 text-[12px]">↓</span>`;
                    else if (subStr.includes('in')) subIcon = `<span class="text-green-600 font-bold ml-1 text-[14px]">↑</span>`;
                    else if (subStr.includes('ut')) subIcon = `<span class="text-red-500 font-bold ml-1 text-[14px]">↓</span>`;

                    if (cardStr.includes('v') && cardStr.includes('utv')) cardIcon = `<span class="card-yellow"></span><span class="card-red"></span>`;
                    else if (cardStr.includes('utv')) cardIcon = `<span class="card-red"></span>`;
                    else if (cardStr.includes('v')) cardIcon = `<span class="card-yellow"></span>`;
                    
                    if (subStr) eventMin = `<span class="text-xs text-slate-400 ml-1">(${subStr})</span>`;
                    const nrText = p.shirt_nr && p.shirt_nr !== 'null' ? `<span class="inline-block w-6 font-bold text-slate-400 text-xs">${p.shirt_nr}.</span>` : `<span class="inline-block w-6 text-slate-300">-</span>`;
                    
                    lHtml += `<li class="py-1 border-b border-slate-50 last:border-0 flex items-center">${nrText} <span class="${subStr.includes('in') ? 'text-slate-600' : 'font-medium'}">${formatName(p.name)}</span>${capIcon}${subIcon}${cardIcon} ${eventMin}</li>`;
                });
                el.innerHTML = lHtml;
            };

            document.getElementById('modal-lineup-home-title').innerText = m.home_team;
            document.getElementById('modal-lineup-away-title').innerText = m.away_team;
            renderLineup(m.events.lineups.home, 'modal-lineup-home');
            renderLineup(m.events.lineups.away, 'modal-lineup-away');
            
            document.getElementById('modal-coach-home').innerText = formatName(safeText(m.coaches.home));
            document.getElementById('modal-coach-away').innerText = formatName(safeText(m.coaches.away));
            document.getElementById('match-modal').classList.remove('hidden');
        }

        function closeModal() { document.getElementById('match-modal').classList.add('hidden'); }
        
        function renderAdminWarnings() {
            const container = document.getElementById('admin-list-container');
            const badge = document.getElementById('admin-badge');
            const warnings = db.admin_warnings || [];
            
            if (warnings.length > 0) {
                badge.innerText = warnings.length; badge.classList.remove('hidden');
                
                let groups = { "🔴 Kritiska Fel & Datafel": [], "🟠 Logikfel (Resultat & Slutspel)": [], "🟡 Saknas i 'Namn' eller 'Trupper'": [], "⚪ Övriga varningar": [] };
                warnings.forEach(w => {
                    if (w.includes("Kritisk") || w.includes("Allvarlig") || w.includes("Datafel")) groups["🔴 Kritiska Fel & Datafel"].push(w);
                    else if (w.includes("Logikfel")) groups["🟠 Logikfel (Resultat & Slutspel)"].push(w);
                    else if (w.includes("Saknas i")) groups["🟡 Saknas i 'Namn' eller 'Trupper'"].push(w);
                    else groups["⚪ Övriga varningar"].push(w);
                });

                let html = '';
                for (let [title, list] of Object.entries(groups)) {
                    if (list.length === 0) continue;
                    html += `<h3 class="font-bold text-slate-700 mt-6 mb-2 border-b pb-1">${title} <span class="text-xs font-normal text-slate-400">(${list.length})</span></h3><div class="space-y-2 mb-6">`;
                    list.forEach(w => {
                        let c = title.includes("Kritiska") ? "border-red-200 bg-red-50 text-red-800 font-medium" : title.includes("Logikfel") ? "border-orange-200 bg-orange-50 text-orange-800" : title.includes("Saknas") ? "border-yellow-200 bg-yellow-50 text-yellow-800" : "border-slate-200 bg-slate-50 text-slate-800";
                        html += `<div class="p-2.5 border-l-4 rounded ${c} text-xs shadow-sm">${w}</div>`;
                    });
                    html += `</div>`;
                }
                container.innerHTML = html;
            } else {
                badge.classList.add('hidden');
                container.innerHTML = `<div class="p-6 text-center text-green-700 bg-green-50 rounded border border-green-200"><span class="text-2xl block mb-2">🎉</span>Inga varningar! Databasen är helt felfri.</div>`;
            }
        }

        document.getElementById('match-modal').addEventListener('click', function(e) { if (e.target === this) closeModal(); });

        window.onload = () => {
            populateYearFilter();
            renderTournaments();
            renderMatches();
            renderAdminWarnings();
        };
    </script>
</body>
</html>"""

    final_html = html_template.replace("__JSON_DATA_PLACEHOLDER__", json_str)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    print(f"✅ Dashboard framgångsrikt uppgraderad till version med tabeller och slutspelsträd: {OUTPUT_HTML}")

if __name__ == "__main__":
    build_dashboard()