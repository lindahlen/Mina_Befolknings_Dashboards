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

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        json_str = f.read()

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
        .modal-backdrop { background-color: rgba(0, 0, 0, 0.6); backdrop-filter: blur(3px); }
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
            <button onclick="switchTab('tab-teams')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap font-bold text-amber-300">Lagrekord & Sviter</button>
            <button onclick="switchTab('tab-spelare')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap font-bold">Spelare & Statistik</button>
            <button onclick="switchTab('tab-admin')" class="tab-btn px-4 py-2 rounded-t-lg bg-red-800 text-red-200 hover:bg-red-700 transition flex items-center gap-2 whitespace-nowrap">
                <span>⚠️ Admin</span>
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
                    
                    <div class="flex items-center gap-2 w-full sm:w-auto relative">
                        <input type="text" id="search-input" placeholder="Sök lag, arena, fas..." class="p-2 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-64" onkeyup="renderMatches()">
                        <button id="clear-search-btn" onclick="clearSearchAndGoBack()" class="hidden bg-blue-100 text-blue-700 hover:bg-blue-200 px-3 py-2 rounded-lg font-bold transition text-sm flex items-center whitespace-nowrap shadow-sm border border-blue-200">
                            &larr; Tillbaka
                        </button>
                    </div>
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
                    <span class="text-blue-500 cursor-help" title="Statistik baserad på ordinarie tid och eventuell förlängning. Data tar automatiskt hänsyn till historiska landsnamn.">ⓘ</span>
                </h2>
                
                <div class="flex flex-col md:flex-row gap-8 items-center justify-center">
                    <div class="w-full md:w-1/3">
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Lag A (Fokuslag)</label>
                        <select id="h2h-team-a" class="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg font-bold text-slate-800 shadow-inner focus:outline-none focus:ring-2 focus:ring-blue-500" onchange="updateTeamBDropdown()"></select>
                    </div>
                    <div class="text-2xl font-black text-slate-300">VS</div>
                    <div class="w-full md:w-1/3">
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-2">Lag B (Motståndare)</label>
                        <select id="h2h-team-b" class="w-full p-3 bg-slate-50 border border-slate-300 rounded-lg font-bold text-slate-800 shadow-inner focus:outline-none focus:ring-2 focus:ring-blue-500" onchange="renderH2H()"></select>
                    </div>
                </div>
                <div class="mt-6 flex justify-center gap-4 flex-wrap">
                    <button onclick="renderH2H()" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-8 rounded shadow transition">Analysera VS</button>
                    <button onclick="renderH2HAll()" class="bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold py-2 px-8 rounded shadow transition border border-slate-300">Statistik mot alla</button>
                </div>
            </div>
            <div id="h2h-single-view">
                <div id="h2h-summary" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6"></div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="max-h-[50vh] overflow-y-auto">
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
            <div id="h2h-all-container" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"></div>
        </div>

        <!-- FLIK 4: MARATONTABELL -->
        <div id="tab-maraton" class="tab-content hidden">
            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
                <div class="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
                    <h2 class="text-xl font-bold text-slate-800">Historisk Maratontabell</h2>
                    <span class="text-xs text-slate-500 font-medium">Poängberäkning: 3p för vinst, Straffavgöranden räknas som oavgjort</span>
                </div>
                <div class="max-h-[70vh] overflow-y-auto">
                    <table class="w-full text-sm text-left border-collapse">
                        <thead class="bg-blue-900 text-white sticky top-0 z-10">
                            <tr>
                                <th class="py-2 px-2 font-semibold w-10 text-center text-xs">#</th>
                                <th class="py-2 px-2 font-semibold text-xs">Nation</th>
                                <th class="py-2 px-2 font-semibold text-center w-14 text-xs" title="Deltagande turneringar">Turn.</th>
                                <th class="py-2 px-2 font-semibold text-center w-12 text-xs" title="Spelade matcher">S</th>
                                <th class="py-2 px-2 font-semibold text-center w-12 text-xs" title="Vinster">V</th>
                                <th class="py-2 px-2 font-semibold text-center w-12 text-xs" title="Oavgjorda">O</th>
                                <th class="py-2 px-2 font-semibold text-center w-12 text-xs" title="Förluster">F</th>
                                <th class="py-2 px-2 font-semibold text-center w-20 text-xs" title="Gjorda-Insläppta">Mål</th>
                                <th class="py-2 px-2 font-semibold text-center w-14 text-xs" title="Målskillnad">MS</th>
                                <th class="py-2 px-2 font-bold text-center w-12 text-yellow-300 text-xs">P</th>
                            </tr>
                        </thead>
                        <tbody id="marathon-table-body" class="divide-y divide-slate-200 bg-white"></tbody>
                    </table>
                </div>
                <div id="marathon-footer" class="p-3 bg-slate-50 text-xs text-slate-500 border-t border-slate-200"></div>
            </div>
        </div>

        <!-- FLIK 5: LAGREKORD & SVITER -->
        <div id="tab-teams" class="tab-content hidden">
            <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div class="w-full md:w-1/3">
                    <h2 class="text-xl font-bold text-slate-800">Lagrekord & Sviter</h2>
                    <p class="text-xs text-slate-500 mt-1">Filtrera på turnering eller nation.</p>
                </div>
                <div class="w-full md:w-2/3 flex flex-col sm:flex-row gap-3">
                    <select id="team-nation-filter" onchange="renderTeamData()" class="p-3 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-bold text-slate-700 w-full sm:w-1/2">
                        <option value="all">Alla Nationer</option>
                    </select>
                    <select id="team-year-filter" onchange="renderTeamData()" class="p-3 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-bold text-slate-700 w-full sm:w-1/2">
                        <option value="all">Alla Turneringar</option>
                    </select>
                </div>
            </div>

            <div class="flex border-b border-slate-300 mb-6 space-x-2 overflow-x-auto no-scrollbar">
                <button id="team-sub-btn-top" onclick="switchTeamSubTab('team-view-top')" class="px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm whitespace-nowrap">⭐ Topplistor Lag</button>
                <button id="team-sub-btn-streaks" onclick="switchTeamSubTab('team-view-streaks')" class="px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition whitespace-nowrap">🔥 Sviter</button>
            </div>

            <div id="team-view-top" class="team-sub-content">
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-3 gap-2">
                    <h3 class="font-bold text-slate-700 uppercase tracking-wider text-sm">Välj Kategori</h3>
                    <select id="team-top-type" onchange="renderTeamData()" class="p-2 border border-slate-300 rounded-lg shadow-sm text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-64">
                        <option value="biggest_win">Största Segrar</option>
                        <option value="high_score">Målrikaste Matcher</option>
                        <option value="attendance">Högsta Publiksiffror</option>
                        <option value="medals">Flest Medaljer (Endast historik)</option>
                        <option value="placements">Översikt placeringar (Matris)</option>
                        <option value="h2h_most">Flest inbördes möten</option>
                    </select>
                </div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div id="team-top-results" class="max-h-[65vh] overflow-auto"></div>
                </div>
            </div>

            <div id="team-view-streaks" class="team-sub-content hidden">
                <h3 class="font-bold text-slate-700 uppercase tracking-wider text-sm mb-3">Längsta Sviterna (I spelet, straffar = oavgjort)</h3>
                <div id="streak-summary-cards" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"></div>

                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-3 gap-2">
                    <h3 class="font-bold text-slate-700 uppercase tracking-wider text-sm">Topp 10: Historiska Sviter</h3>
                    <select id="team-streak-type" onchange="renderTeamData()" class="p-2 border border-slate-300 rounded-lg shadow-sm text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-64">
                        <option value="W">Längsta Segersvit</option>
                        <option value="U">Längst Obesegrade</option>
                        <option value="L">Längsta Förlustsvit</option>
                        <option value="winless">Längst Utan Seger</option>
                        <option value="CS">Hållna Nollor i rad</option>
                        <option value="drought">Måltorka i rad</option>
                        <option value="scoring">Matcher med gjorda mål i rad</option>
                        <option value="conceding">Matcher med insläppta mål i rad</option>
                    </select>
                </div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div id="team-streak-results" class="max-h-[50vh] overflow-y-auto"></div>
                </div>
            </div>
        </div>
        
        <!-- FLIK 6: SPELARE & STATISTIK -->
        <div id="tab-spelare" class="tab-content hidden">
            <div class="flex border-b border-slate-300 mb-6 space-x-2">
                <button id="player-sub-btn-search" onclick="switchPlayerSubTab('player-view-search')" class="px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm">🔍 Sök Spelarprofil</button>
                <button id="player-sub-btn-top" onclick="switchPlayerSubTab('player-view-top')" class="px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition">⭐ Topplistor</button>
            </div>

            <!-- SPELARPROFILEN -->
            <div id="player-profile-container" class="hidden bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden mb-6">
                <div class="bg-blue-900 p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative">
                    <button onclick="closePlayerProfile()" class="absolute top-2 right-4 text-blue-300 hover:text-white transition text-3xl leading-none" title="Stäng profil">&times;</button>
                    
                    <div class="flex items-center gap-4 mt-2 md:mt-0">
                        <div class="w-16 h-16 bg-white rounded-full flex items-center justify-center text-3xl shadow-lg border-2 border-blue-200 shrink-0">👤</div>
                        <div>
                            <h2 id="profile-name" class="text-2xl md:text-3xl font-black text-white tracking-tight leading-none flex items-center flex-wrap"></h2>
                            <p id="profile-nations" class="text-sm font-semibold text-blue-200 mt-1.5"></p>
                        </div>
                    </div>
                    <div class="text-left md:text-right pr-8 md:pr-12">
                        <div class="text-xs font-bold text-blue-300 uppercase tracking-widest mb-1">Deltagande turneringar</div>
                        <div id="profile-tournaments" class="text-base font-bold text-white flex gap-2 flex-wrap md:justify-end"></div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 md:grid-cols-4 border-b border-slate-200 divide-x divide-y md:divide-y-0 divide-slate-100 bg-slate-50">
                    <div class="p-4 text-center">
                        <div class="text-3xl font-black text-slate-700" id="profile-stat-matches">0</div>
                        <div class="text-[10px] uppercase font-bold text-slate-400 mt-1">Spelade Matcher</div>
                    </div>
                    <div class="p-4 text-center">
                        <div class="text-3xl font-black text-emerald-600" id="profile-stat-goals">0</div>
                        <div class="text-[10px] uppercase font-bold text-slate-400 mt-1">Mål (⚽)</div>
                    </div>
                    <div class="p-4 text-center">
                        <div class="text-3xl font-black text-blue-600" id="profile-stat-minutes">0</div>
                        <div class="text-[10px] uppercase font-bold text-slate-400 mt-1">Spelade Minuter</div>
                    </div>
                    <div class="p-4 text-center">
                        <div class="flex justify-center items-end gap-3 h-9">
                            <div><span class="text-2xl font-black text-slate-700" id="profile-stat-yc">0</span> <span class="card-yellow mb-1"></span></div>
                            <div><span class="text-2xl font-black text-slate-700" id="profile-stat-rc">0</span> <span class="card-red mb-1"></span></div>
                        </div>
                        <div class="text-[10px] uppercase font-bold text-slate-400 mt-2">Varningar & Utv</div>
                    </div>
                </div>

                <div class="p-4 bg-white">
                    <h3 class="font-bold text-slate-800 mb-3 ml-2 text-sm uppercase tracking-wider">Matchhistorik</h3>
                    <div class="max-h-[50vh] overflow-y-auto rounded-lg border border-slate-200">
                        <table class="w-full text-left border-collapse">
                            <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                                <tr>
                                    <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Fas</th>
                                    <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum</th>
                                    <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                                    <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                                    <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                                </tr>
                            </thead>
                            <tbody id="profile-matches-list" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- SPELAR SÖK -->
            <div id="player-view-search" class="player-sub-content">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
                    <div class="w-full md:w-1/3">
                        <h2 class="text-xl font-bold text-slate-800">Sök Spelare</h2>
                        <p class="text-xs text-slate-500 mt-1">Sök på namn eller filtrera på nation.</p>
                    </div>
                    <div class="w-full md:w-2/3 flex flex-col sm:flex-row gap-3">
                        <select id="player-nation-filter" onchange="searchPlayersLive(0)" class="p-3 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-bold text-slate-700 w-full sm:w-1/2">
                            <option value="all">Alla nationer</option>
                        </select>
                        <div class="relative w-full sm:w-1/2">
                            <input type="text" id="player-search-input" placeholder="Sök namn (t.ex. Pelé)..." class="w-full p-3 pl-10 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-base" onkeyup="searchPlayersLive(0)">
                            <svg class="w-5 h-5 absolute left-3 top-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                </div>

                <div id="player-search-results" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6"></div>
            </div>

            <!-- TOPPLISTOR SPELARE -->
            <div id="player-view-top" class="player-sub-content hidden">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
                    <div class="w-full md:w-1/3">
                        <h2 class="text-xl font-bold text-slate-800">Topplistor & Rekord</h2>
                        <p class="text-xs text-slate-500 mt-1">Utforska historiska rekord. Filtrera på nation eller totalt.</p>
                    </div>
                    <div class="w-full md:w-2/3 flex flex-col sm:flex-row gap-3">
                        <select id="top-nation-filter" onchange="renderTopList()" class="p-3 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-bold text-slate-700 w-full sm:w-1/2">
                            <option value="all">Alla nationer</option>
                        </select>
                        <select id="top-type-filter" onchange="renderTopList()" class="p-3 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-bold text-slate-700 w-full sm:w-1/2">
                            <option value="matches">Flest spelade matcher</option>
                            <option value="goals">Flest mål (exkl. straffar)</option>
                            <option value="tournaments">Flest spelade turneringar</option>
                            <option value="tournaments_squad">Flest turneringar i trupp</option>
                            <option value="yellow">Flest varningar (Gula kort)</option>
                            <option value="red">Utvisningar (Röda kort)</option>
                            <option value="oldest_player">Äldsta spelare (Kommer snart)</option>
                            <option value="youngest_player">Yngsta spelare (Kommer snart)</option>
                            <option value="oldest_scorer">Äldsta målskytt (Kommer snart)</option>
                            <option value="youngest_scorer">Yngsta målskytt (Kommer snart)</option>
                        </select>
                    </div>
                </div>

                <div id="top-list-results" class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"></div>
            </div>
        </div>

        <!-- FLIK 7: Admin -->
        <div id="tab-admin" class="tab-content hidden">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-red-800">Kvalitetssäkring & Felsökning</h2>
                <button onclick="renderAdminWarnings()" class="text-sm bg-slate-200 hover:bg-slate-300 px-3 py-1 rounded">Uppdatera logg</button>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-red-200 p-6" id="admin-list-container"></div>
        </div>
    </main>

    <!-- MODALER FÖR DELDETALJER (TURNERING/LAG/SVIT) -->
    
    <!-- Turnerings Modal -->
    <div id="tournament-modal" class="fixed inset-0 z-50 hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden relative">
            <div class="bg-blue-900 text-white p-6 relative">
                <button onclick="closeTournamentModal()" class="absolute top-4 right-4 text-blue-300 hover:text-white transition text-3xl leading-none" title="Stäng">&times;</button>
                <div class="flex justify-between items-end pr-8 md:pr-12">
                    <div>
                        <h2 class="text-3xl font-black tracking-tight" id="tm-year"></h2>
                        <p class="text-blue-200 font-medium" id="tm-host"></p>
                    </div>
                    <div class="text-right">
                        <div class="text-xs uppercase font-bold text-blue-300 tracking-widest mb-1">Världsmästare</div>
                        <div class="text-2xl font-black text-yellow-400 flex items-center justify-end gap-2">🏆 <span id="tm-winner"></span></div>
                    </div>
                </div>
            </div>
            <div class="p-6 overflow-y-auto bg-white flex-1">
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <h4 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 border-b border-slate-200 pb-1">Mästarnas Ledare</h4>
                        <div class="mb-2"><span class="text-xs text-slate-500 block">Förbundskapten</span><span class="font-bold text-slate-700" id="tm-coach"></span></div>
                        <div><span class="text-xs text-slate-500 block">Lagkapten (Final)</span><span class="font-bold text-slate-700" id="tm-captain"></span></div>
                    </div>
                    <div class="bg-slate-50 p-4 rounded-xl border border-slate-200">
                        <h4 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 border-b border-slate-200 pb-1">Turnering i siffror</h4>
                        <div class="grid grid-cols-2 gap-y-2">
                            <div><span class="text-xs text-slate-500 block">Matcher</span><span class="font-bold text-slate-700" id="tm-matches"></span></div>
                            <div><span class="text-xs text-slate-500 block">Mål totalt</span><span class="font-bold text-slate-700" id="tm-goals"></span></div>
                            <div><span class="text-xs text-slate-500 block">Målsnitt</span><span class="font-bold text-slate-700" id="tm-avg-goals"></span></div>
                            <div><span class="text-xs text-slate-500 block">Publiksnitt</span><span class="font-bold text-slate-700" id="tm-avg-att"></span></div>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    <div>
                        <h4 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2 border-b border-slate-200 pb-1">Målstatistik</h4>
                        <table class="w-full text-sm">
                            <tbody class="divide-y divide-slate-100">
                                <tr><td class="py-1.5 text-slate-600">Mål i 1:a halvlek</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-g-h1"></td></tr>
                                <tr><td class="py-1.5 text-slate-600">Mål i 2:a halvlek</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-g-h2"></td></tr>
                                <tr><td class="py-1.5 text-slate-600">Mål i förlängning</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-g-et"></td></tr>
                                <tr><td class="py-1.5 text-slate-600">Mål på straffläggning</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-g-pen"></td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div>
                        <h4 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-2 border-b border-slate-200 pb-1">Spelarfakta</h4>
                        <table class="w-full text-sm">
                            <tbody class="divide-y divide-slate-100">
                                <tr><td class="py-1.5 text-slate-600">Använda spelare totalt</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-p-used"></td></tr>
                                <tr><td class="py-1.5 text-slate-600">VM-debutanter</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-p-debut"></td></tr>
                                <tr><td class="py-1.5 text-slate-600">Antal målskyttar</td><td class="py-1.5 text-right font-bold text-slate-800" id="tm-p-scorers"></td></tr>
                                <tr><td class="py-1.5 text-slate-600 font-bold text-emerald-600">Skyttekung</td><td class="py-1.5 text-right font-bold text-emerald-700" id="tm-p-top"></td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="text-center mt-6">
                    <button id="tm-btn-matches" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg shadow-md transition w-full sm:w-auto">
                        Visa alla matcher från denna turnering
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Team Matches Modal (Från Maratontabellen) -->
    <div id="team-modal" class="fixed inset-0 z-50 hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden relative">
            <div class="bg-blue-900 text-white p-4 flex justify-between items-center relative">
                <h2 class="text-2xl font-black tracking-tight flex items-center gap-3">
                    <span id="team-modal-name"></span>
                </h2>
                <button onclick="closeTeamModal()" class="text-blue-300 hover:text-white transition text-3xl leading-none">&times;</button>
            </div>
            <div class="p-6 bg-slate-50 border-b border-slate-200">
                <div id="team-modal-summary" class="mb-4"></div>
                <div id="team-modal-subtotals" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-2"></div>
            </div>
            <div class="p-0 overflow-y-auto flex-1 bg-white">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                        <tr>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Fas</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                        </tr>
                    </thead>
                    <tbody id="team-modal-matches-list" class="divide-y divide-slate-100"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Streak Matches Modal -->
    <div id="streak-modal" class="fixed inset-0 z-50 hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden relative">
            <div class="bg-amber-500 text-white p-4 flex justify-between items-center relative">
                <div>
                    <h2 class="text-xl font-black tracking-tight" id="streak-modal-title"></h2>
                    <div class="text-sm font-bold text-amber-900 mt-1" id="streak-modal-subtitle"></div>
                </div>
                <button onclick="closeStreakModal()" class="text-amber-900 hover:text-white transition text-3xl leading-none">&times;</button>
            </div>
            <div class="p-0 overflow-y-auto flex-1 bg-white">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                        <tr>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Fas</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                            <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                        </tr>
                    </thead>
                    <tbody id="streak-modal-matches-list" class="divide-y divide-slate-100"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- MATCH MODAL -->
    <div id="match-modal" class="fixed inset-0 z-[60] hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden relative">
            <div class="bg-blue-900 text-white p-4 flex items-center relative min-h-[60px]">
                <div class="absolute left-4"><span class="text-xl font-black text-blue-200 tracking-wider" id="modal-year"></span></div>
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

        const getPhaseColors = (phase) => {
            if (!phase) return "bg-slate-200 text-slate-700 border-slate-300";
            let p = phase.toLowerCase();
            if (p.includes("final") && !p.includes("kvarts") && !p.includes("semi") && !p.includes("åtton") && !p.includes("sexton") && !p.includes("omgång")) return "bg-yellow-200 text-yellow-900 border-yellow-300";
            if (p.includes("tredje") || p.includes("brons") || p.includes("3:e")) return "bg-orange-100 text-orange-800 border-orange-200";
            if (p.includes("semi")) return "bg-indigo-100 text-indigo-800 border-indigo-200";
            if (p.includes("kvarts")) return "bg-blue-100 text-blue-800 border-blue-200";
            if (p.includes("åtton")) return "bg-emerald-100 text-emerald-800 border-emerald-200";
            if (p.includes("sexton")) return "bg-teal-100 text-teal-800 border-teal-200";
            if (p.includes("grupp")) return "bg-slate-200 text-slate-700 border-slate-300";
            return "bg-slate-200 text-slate-700 border-slate-300";
        };

        function getMappedTeamName(teamName) {
            if (db.team_mappings && db.team_mappings[teamName]) return db.team_mappings[teamName];
            return teamName;
        }

        function getAllTeams() {
            let teams = new Set();
            Object.values(db.matches).forEach(m => {
                if(m.home_team) teams.add(getMappedTeamName(m.home_team));
                if(m.away_team) teams.add(getMappedTeamName(m.away_team));
            });
            return Array.from(teams).sort();
        }

        // --- HUVUDNAVIGERING ---
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-white', 'text-blue-900', 'font-semibold', 'text-amber-300');
                btn.classList.add('bg-blue-800', 'text-blue-200');
            });
            document.getElementById(tabId).classList.remove('hidden');
            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
            if(activeBtn) {
                activeBtn.classList.remove('bg-blue-800', 'text-blue-200');
                activeBtn.classList.add('bg-white', 'text-blue-900', 'font-semibold');
            }
            
            if(tabId === 'tab-h2h') populateH2HSelectors();
            if(tabId === 'tab-maraton') renderMarathonTable();
            if(tabId === 'tab-teams') {
                populateTeamFilters();
                renderTeamData();
            }
            if(tabId === 'tab-spelare') {
                populatePlayerNations();
                populateTopNations();
                document.getElementById('player-search-input').focus();
            }
        }

        // --- MATCHER & TURNERINGAR ---
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
                if (t.id === subViewId) btn.className = "px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm";
                else btn.className = "px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition";
            });
        }

        function filterMatchesByGroup(groupName) {
            document.getElementById('search-input').value = groupName;
            window.lastSubTabBeforeSearch = 'sub-view-groups';
            document.getElementById('clear-search-btn').classList.remove('hidden');
            switchSubTab('sub-view-list');
            renderMatches();
        }

        function clearSearchAndGoBack() {
            document.getElementById('search-input').value = '';
            document.getElementById('clear-search-btn').classList.add('hidden');
            if (window.lastSubTabBeforeSearch) {
                switchSubTab(window.lastSubTabBeforeSearch);
                window.lastSubTabBeforeSearch = null;
            }
            renderMatches();
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
                    <div onclick="openTournamentModal('${year}')" class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 cursor-pointer hover:shadow-md hover:border-blue-300 transition group flex justify-between gap-2">
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
                    </div>`;
            });
            container.innerHTML = html;
        }

        function navigateYear(direction) {
            const select = document.getElementById('filter-year');
            const validYears = Object.keys(db.tournaments).sort((a, b) => a - b); 
            let currentIndex = validYears.indexOf(select.value);
            if (select.value === 'all') currentIndex = direction > 0 ? -1 : validYears.length;
            let newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < validYears.length) filterByYear(validYears[newIndex]);
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
            
            let html = ''; let count = 0; let currentPhase = ''; 
            const getPhaseWeight = (m) => {
                if (!m.phase) return 0;
                let p = m.phase.toLowerCase();
                if (m.advancement && (m.advancement.code === 5 || m.advancement.code === 6 || m.advancement.is_final === true)) return 1000;
                if (p.includes("final") && !p.includes("kvarts") && !p.includes("semi") && !p.includes("åtton") && !p.includes("sexton") && !p.includes("omgång")) return 100;
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
                return getPhaseWeight(b) - getPhaseWeight(a);
            });

            matchArray.forEach(m => {
                const matchYear = m.date.substring(0, 4);
                if (filterYear !== 'all' && matchYear !== filterYear) return;
                if (searchTerm && !`${m.home_team} ${m.away_team} ${m.arena} ${m.city} ${m.phase} ${matchYear}`.toLowerCase().includes(searchTerm)) return;

                if (m.phase !== currentPhase) {
                    let pColors = getPhaseColors(m.phase);
                    html += `<tr><td colspan="4" class="${pColors} font-bold text-xs uppercase px-3 py-2 border-y tracking-wider">${m.phase}</td></tr>`;
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
                    </tr>`;
            });
            container.innerHTML = html;
            counter.innerText = `Visar ${count} matcher`;
        }

        function getPhaseSuffixType(n) { let lc=n.trim().slice(-1); if(/\d/.test(lc)) return 'num'; if(/[A-Za-z]/.test(lc)) return 'alpha'; return 'other'; }
        
        function renderGroupStage(year) {
            const container = document.getElementById('group-stage-container');
            let yearMatches = Object.values(db.matches).filter(m => m.date.substring(0,4) === year);
            let groupMatches = yearMatches.filter(m => m.advancement.is_group_match);
            if (groupMatches.length === 0) { container.innerHTML = '<div class="col-span-2 p-8 text-center text-slate-400 italic bg-white rounded-xl border">Denna turnering innehöll inget traditionellt gruppspel i databasen.</div>'; return; }
            let teamPhases = {}; yearMatches.sort((a,b) => new Date(a.date) - new Date(b.date));
            yearMatches.forEach(m => {
                if(!teamPhases[m.home_team]) teamPhases[m.home_team] = []; if(!teamPhases[m.away_team]) teamPhases[m.away_team] = [];
                if(!teamPhases[m.home_team].includes(m.phase)) teamPhases[m.home_team].push(m.phase);
                if(!teamPhases[m.away_team].includes(m.phase)) teamPhases[m.away_team].push(m.phase);
            });
            let groups = {}; let groupStartDates = {};
            groupMatches.forEach(m => {
                let phase = m.phase || "Gruppspel";
                if (!groups[phase]) groups[phase] = { teams: {} };
                if (!groupStartDates[phase] || new Date(m.date) < new Date(groupStartDates[phase])) groupStartDates[phase] = m.date;
                [m.home_team, m.away_team].forEach(t => { if (!groups[phase].teams[t]) groups[phase].teams[t] = { name: t, S: 0, V: 0, O: 0, F: 0, GM: 0, IM: 0, P: 0 }; });
                if (m.score.home_total !== null && m.score.away_total !== null) {
                    let h = groups[phase].teams[m.home_team], a = groups[phase].teams[m.away_team];
                    let hg = m.score.home_total, ag = m.score.away_total, ptsWin = m.advancement.points_for_win || 2; 
                    h.S++; a.S++; h.GM += hg; h.IM += ag; a.GM += ag; a.IM += hg;
                    if (hg > ag) { h.V++; h.P += ptsWin; a.F++; } else if (ag > hg) { a.V++; a.P += ptsWin; h.F++; } else { h.O++; a.O++; h.P += 1; a.P += 1; }
                }
            });
            let sortedGroups = Object.keys(groups).sort((a,b) => new Date(groupStartDates[a]) - new Date(groupStartDates[b]));
            let html = '', lastPhaseType = null;
            sortedGroups.forEach(gName => {
                let currentPhaseType = getPhaseSuffixType(gName);
                if (lastPhaseType && currentPhaseType !== lastPhaseType && currentPhaseType !== 'other' && lastPhaseType !== 'other') html += `<div class="col-span-1 lg:col-span-2 my-2 mt-6 flex items-center"><div class="flex-grow border-t-2 border-dashed border-slate-300"></div><span class="px-4 text-xs font-black text-slate-400 uppercase tracking-widest">Nästa Gruppspelsfas</span><div class="flex-grow border-t-2 border-dashed border-slate-300"></div></div>`;
                lastPhaseType = currentPhaseType;
                let sortedTeams = Object.values(groups[gName].teams).sort((a,b) => {
                    if (b.P !== a.P) return b.P - a.P; let diffA = a.GM - a.IM, diffB = b.GM - b.IM;
                    if (diffB !== diffA) return diffB - diffA; return b.GM - a.GM;
                });
                html += `
                    <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
                        <h3 class="font-black text-lg text-blue-900 border-b pb-1.5 mb-3 uppercase tracking-wider cursor-pointer hover:text-blue-600 transition flex justify-between items-center" onclick="filterMatchesByGroup('${gName}')" title="Klicka för att lista matcher i ${gName}">
                            <span>${gName}</span><span class="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded hover:bg-blue-100 hover:text-blue-700 transition">Visa matcher ➔</span>
                        </h3>
                        <table class="w-full text-sm text-left border-collapse">
                            <thead><tr class="text-slate-400 text-xs border-b"><th class="pb-1 font-semibold">Lag</th><th class="pb-1 text-center w-8">S</th><th class="pb-1 text-center w-8">V</th><th class="pb-1 text-center w-8">O</th><th class="pb-1 text-center w-8">F</th><th class="pb-1 text-center w-16">Mål</th><th class="pb-1 text-center w-8 font-bold text-blue-900">P</th></tr></thead>
                            <tbody class="divide-y divide-slate-100 font-medium text-slate-700">`;
                sortedTeams.forEach((t, idx) => {
                    let diff = t.GM - t.IM, diffStr = diff > 0 ? `+${diff}` : diff, rowClass = idx < 2 ? "bg-blue-50/40 font-bold" : "", advancedStr = "";
                    let tPhases = teamPhases[t.name] || [], currentPhaseIndex = tPhases.indexOf(gName);
                    if (currentPhaseIndex !== -1 && currentPhaseIndex < tPhases.length - 1) advancedStr = ` <span title="Laget avancerade" class="text-emerald-500 text-[10px] ml-1.5 cursor-help bg-emerald-50 px-1 py-0.5 rounded shadow-sm border border-emerald-100">✅ Avancerade</span>`;
                    html += `<tr class="${rowClass}"><td class="py-2 text-slate-900 flex items-center">${t.name}${advancedStr}</td><td class="py-2 text-center text-slate-500">${t.S}</td><td class="py-2 text-center text-green-600">${t.V}</td><td class="py-2 text-center text-slate-400">${t.O}</td><td class="py-2 text-center text-red-500">${t.F}</td><td class="py-2 text-center text-xs text-slate-500">${t.GM}-${t.IM} <span class="text-[10px] font-normal">(${diffStr})</span></td><td class="py-2 text-center font-black text-blue-900">${t.P}</td></tr>`;
                });
                html += `</tbody></table></div>`;
            });
            container.innerHTML = html;
        }

        function buildMatchCard(m, theme = 'slate') {
            let hw = m.advancement.advancing_team === m.home_team, aw = m.advancement.advancing_team === m.away_team;
            let bc = theme === 'orange' ? 'border-orange-300' : 'border-slate-200', hb = theme === 'orange' ? 'hover:border-orange-500' : 'hover:border-blue-400';
            let tch = hw ? (theme==='orange'?'text-orange-800':'text-blue-900') : 'text-slate-500', tca = aw ? (theme==='orange'?'text-orange-800':'text-blue-900') : 'text-slate-500';
            return `<div onclick="openMatchModal('${m.id}')" class="bg-white p-3 rounded-lg border ${bc} shadow-sm my-3 ${hb} hover:shadow transition cursor-pointer group text-xs"><div class="text-[10px] text-slate-400 font-bold mb-1.5 flex justify-between"><span>ID: ${m.id}</span> <span>${m.date}</span></div><div class="space-y-1.5 font-medium"><div class="flex justify-between items-center ${hw ? 'font-black '+tch : 'text-slate-500'}"><span class="truncate pr-1">${m.home_team}</span><span>${m.score.home_total !== null ? m.score.home_total : '-'}</span></div><div class="flex justify-between items-center ${aw ? 'font-black '+tca : 'text-slate-500'}"><span class="truncate pr-1">${m.away_team}</span><span>${m.score.away_total !== null ? m.score.away_total : '-'}</span></div></div>${m.score.home_pen !== null ? `<div class="text-[9px] text-center text-slate-400 font-bold mt-1 border-t pt-1">Str: ${m.score.home_pen}-${m.score.away_pen}</div>` : ''}</div>`;
        }

        function renderKnockoutTree(year) {
            const container = document.getElementById('knockout-tree-container');
            let koMatches = Object.values(db.matches).filter(m => m.date.substring(0,4) === year && (!m.advancement.is_group_match || m.phase.toLowerCase().includes('finalomgång')));
            if (koMatches.length === 0) { container.innerHTML = '<div class="p-8 text-center text-slate-400 italic w-full">Denna turnering avgjordes helt via gruppspel / slutgrupper.</div>'; return; }
            let allPhases = ["Sextondelsfinal", "Åttondelsfinal", "Kvartsfinal", "Semifinal", "Finalomgång", "Final"], treeData = {};
            allPhases.forEach(p => treeData[p] = []); treeData["Bronsmatch"] = [];
            koMatches.forEach(m => {
                let p = m.phase.toLowerCase();
                if (p.includes("tredje") || p.includes("brons") || p.includes("3:e")) treeData["Bronsmatch"].push(m);
                else if (p.includes("sexton")) treeData["Sextondelsfinal"].push(m);
                else if (p.includes("åtton")) treeData["Åttondelsfinal"].push(m);
                else if (p.includes("kvarts")) treeData["Kvartsfinal"].push(m);
                else if (p.includes("semi")) treeData["Semifinal"].push(m);
                else if (p.includes("finalomgång")) treeData["Finalomgång"].push(m);
                else if (p.includes("final")) treeData["Final"].push(m);
            });
            let startIndex = allPhases.indexOf(document.getElementById('tree-start-filter').value);
            if(startIndex === -1) startIndex = 0;
            let visiblePhases = [...new Set(allPhases.slice(startIndex).concat(["Finalomgång", "Final"]))];
            let html = '';
            visiblePhases.forEach(pName => {
                let mList = treeData[pName];
                if (mList.length === 0 && pName !== "Final") return;
                if (mList.length === 0 && pName === "Final" && treeData["Bronsmatch"].length === 0) return;
                html += `<div class="flex-1 flex flex-col justify-around bg-slate-50/60 p-3 rounded-xl border border-slate-200/80 min-w-[220px]">`;
                html += `<h4 class="text-center font-black text-xs uppercase tracking-widest text-slate-400 border-b pb-2 mb-4">${pName === "Final" ? "🏆 Final" : pName}</h4>`;
                mList.sort((a,b) => new Date(a.date) - new Date(b.date)).forEach(m => { html += buildMatchCard(m); });
                if (pName === "Final" && treeData["Bronsmatch"].length > 0) {
                    html += `<div class="mt-8 border-t-2 border-dashed border-orange-200 pt-4"><h4 class="text-center font-black text-xs uppercase tracking-widest text-orange-600 mb-2">🥉 Bronsmatch</h4>`;
                    treeData["Bronsmatch"].sort((a,b) => new Date(a.date) - new Date(b.date)).forEach(bm => { html += buildMatchCard(bm, 'orange'); });
                    html += `</div>`;
                }
                html += `</div>`;
            });
            container.innerHTML = html;
        }

        // =========================================================
        // 📊 H2H & MARATONTABELL
        // =========================================================
        function renderMarathonTable() {
            const container = document.getElementById('marathon-table-body'), footerContainer = document.getElementById('marathon-footer');
            let teams = {};
            Object.values(db.matches).forEach(m => {
                if (m.score.home_total === null) return; 
                let year = m.date.substring(0, 4), hMapped = getMappedTeamName(m.home_team), aMapped = getMappedTeamName(m.away_team);
                [ {orig: m.home_team, mapped: hMapped}, {orig: m.away_team, mapped: aMapped} ].forEach(t => {
                    if (!teams[t.mapped]) teams[t.mapped] = { name: t.mapped, S:0, V:0, O:0, F:0, GM:0, IM:0, P:0, years: new Set(), orig_names: new Set() };
                    teams[t.mapped].orig_names.add(t.orig);
                });
                let h = teams[hMapped], a = teams[aMapped], hg = m.score.home_total, ag = m.score.away_total;
                h.years.add(year); a.years.add(year);
                h.S++; a.S++; h.GM += hg; h.IM += ag; a.GM += ag; a.IM += hg;
                if (hg > ag) { h.V++; h.P += 3; a.F++; } else if (ag > hg) { a.V++; a.P += 3; h.F++; } else { h.O++; a.O++; h.P += 1; a.P += 1; }
            });
            let sortedTeams = Object.values(teams).sort((a,b) => {
                if (b.P !== a.P) return b.P - a.P; let diffA = a.GM - a.IM, diffB = b.GM - b.IM;
                if (diffB !== diffA) return diffB - diffA; return b.GM - a.GM; 
            });
            let html = '';
            sortedTeams.forEach((t, idx) => {
                let diff = t.GM - t.IM, diffStr = diff > 0 ? `+${diff}` : diff, rankClass = idx < 10 ? "font-bold text-slate-800" : "text-slate-600";
                let yearsArr = Array.from(t.years).sort(), yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                html += `<tr class="hover:bg-blue-50 transition border-b border-slate-100 last:border-0 cursor-pointer group" onclick="openTeamModal('${t.name.replace(/'/g, "\\'")}')">
                            <td class="py-1.5 px-2 text-center text-xs text-slate-400 font-bold">${idx + 1}</td>
                            <td class="py-1.5 px-2 ${rankClass} flex items-center group-hover:text-blue-700">${t.name} <span class="text-[10px] font-normal text-slate-400 ml-2">(${yearStr})</span></td>
                            <td class="py-1.5 px-2 text-center text-slate-500 font-medium">${yearsArr.length}</td>
                            <td class="py-1.5 px-2 text-center font-medium">${t.S}</td>
                            <td class="py-1.5 px-2 text-center text-green-600">${t.V}</td>
                            <td class="py-1.5 px-2 text-center text-slate-500">${t.O}</td>
                            <td class="py-1.5 px-2 text-center text-red-500">${t.F}</td>
                            <td class="py-1.5 px-2 text-center text-xs text-slate-500">${t.GM}-${t.IM}</td>
                            <td class="py-1.5 px-2 text-center font-medium text-slate-700">${diffStr}</td>
                            <td class="py-1.5 px-2 text-center font-black text-blue-900">${t.P}</td>
                        </tr>`;
            });
            container.innerHTML = html;
            let mergedTextArray = [];
            Object.values(teams).forEach(t => {
                if (t.orig_names.size > 1 || (t.orig_names.size === 1 && !t.orig_names.has(t.name))) {
                    let origList = Array.from(t.orig_names).filter(n => n !== t.name).join(", ");
                    if (origList) mergedTextArray.push(`<b>${t.name}</b> (inkl. ${origList})`);
                }
            });
            if (mergedTextArray.length > 0) { footerContainer.innerHTML = `<span class="font-bold">Sammanslagna historiska nationer:</span> ${mergedTextArray.join(' &bull; ')}`; footerContainer.classList.remove('hidden'); } 
            else { footerContainer.classList.add('hidden'); }
        }

        function populateH2HSelectors() {
            const selectA = document.getElementById('h2h-team-a');
            if (selectA.options.length > 0) return; 
            const teams = getAllTeams();
            teams.forEach(t => { selectA.add(new Option(t, t)); });
            if (teams.includes("Brasilien")) selectA.value = "Brasilien";
            updateTeamBDropdown(true);
        }

        function updateTeamBDropdown(initialLoad = false) {
            const teamA = document.getElementById('h2h-team-a').value, selectB = document.getElementById('h2h-team-b');
            const currentB = initialLoad ? "Tyskland" : selectB.value;
            let opponents = new Set();
            Object.values(db.matches).forEach(m => {
                if (m.score.home_total === null) return;
                let hMapped = getMappedTeamName(m.home_team), aMapped = getMappedTeamName(m.away_team);
                if (hMapped === teamA) opponents.add(aMapped); if (aMapped === teamA) opponents.add(hMapped);
            });
            selectB.innerHTML = '';
            let oppGroup = document.createElement('optgroup'); oppGroup.label = "Möjliga motståndare (Har mötts)";
            let otherGroup = document.createElement('optgroup'); otherGroup.label = "Har EJ mötts"; otherGroup.style.color = "#94a3b8"; 
            getAllTeams().forEach(t => {
                if (t === teamA) return;
                let opt = new Option(t, t);
                if (opponents.has(t)) { opt.style.color = "#1e293b"; oppGroup.appendChild(opt); } 
                else { opt.style.color = "#94a3b8"; otherGroup.appendChild(opt); }
            });
            selectB.appendChild(oppGroup); selectB.appendChild(otherGroup);
            let optionsArray = Array.from(selectB.options).map(o => o.value);
            if (optionsArray.includes(currentB)) selectB.value = currentB;
            else if (oppGroup.options.length > 0) selectB.value = oppGroup.options[0].value;
            else selectB.value = otherGroup.options[0].value;
            if(!initialLoad) renderH2H();
        }

        function renderH2H() {
            document.getElementById('h2h-all-container').classList.add('hidden');
            document.getElementById('h2h-single-view').classList.remove('hidden');
            const teamA = document.getElementById('h2h-team-a').value, teamB = document.getElementById('h2h-team-b').value;
            const container = document.getElementById('h2h-matches-list'), summaryContainer = document.getElementById('h2h-summary');
            if(!teamA || !teamB) return;
            let h2hMatches = Object.values(db.matches).filter(m => {
                if(m.score.home_total === null) return false;
                let hMapped = getMappedTeamName(m.home_team), aMapped = getMappedTeamName(m.away_team);
                return (hMapped === teamA && aMapped === teamB) || (hMapped === teamB && aMapped === teamA);
            });
            h2hMatches.sort((a,b) => new Date(a.date) - new Date(b.date));
            let winsA = 0, winsB = 0, draws = 0, html = '';
            h2hMatches.forEach(m => {
                let hMapped = getMappedTeamName(m.home_team);
                if(m.score.home_total > m.score.away_total) { if(hMapped === teamA) winsA++; else winsB++; } 
                else if(m.score.away_total > m.score.home_total) { if(getMappedTeamName(m.away_team) === teamA) winsA++; else winsB++; } 
                else {
                    if(m.score.home_pen !== null && m.score.away_pen !== null) {
                        if(m.score.home_pen > m.score.away_pen) { if(hMapped === teamA) winsA++; else winsB++; } 
                        else { if(getMappedTeamName(m.away_team) === teamA) winsA++; else winsB++; }
                    } else draws++;
                }
                const isHomeA = hMapped === teamA;
                html += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100"><div class="text-[10px] uppercase font-bold text-blue-900">${m.date.substring(0,4)}</div><div class="text-xs text-slate-500">${m.phase}</div></td>
                        <td class="p-3 border-t border-slate-100"><div class="text-xs text-slate-500">${m.date}</div></td>
                        <td class="p-3 border-t border-slate-100 text-right ${isHomeA ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 ${!isHomeA ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.away_team}</td>
                    </tr>`;
            });
            container.innerHTML = html;
            summaryContainer.innerHTML = `<div class="bg-indigo-50 border border-indigo-100 p-3 rounded-xl text-center shadow-sm"><div class="text-[10px] font-bold uppercase tracking-widest text-indigo-400 mb-1">Möten</div><div class="text-2xl font-black text-indigo-900">${h2hMatches.length}</div></div><div class="bg-emerald-50 border border-emerald-100 p-3 rounded-xl text-center shadow-sm"><div class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">Vinster ${teamA}</div><div class="text-2xl font-black text-emerald-700">${winsA}</div></div><div class="bg-slate-50 border border-slate-200 p-3 rounded-xl text-center shadow-sm"><div class="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Oavgjorda</div><div class="text-2xl font-black text-slate-600">${draws}</div></div><div class="bg-rose-50 border border-rose-100 p-3 rounded-xl text-center shadow-sm md:col-start-2 md:col-span-2 lg:col-start-auto lg:col-span-1"><div class="text-[10px] font-bold uppercase tracking-widest text-rose-500 mb-1">Vinster ${teamB}</div><div class="text-2xl font-black text-rose-700">${winsB}</div></div>`;
        }

        function renderH2HAll() {
            const teamA = document.getElementById('h2h-team-a').value;
            if(!teamA) return;
            document.getElementById('h2h-single-view').classList.add('hidden');
            const allCont = document.getElementById('h2h-all-container'); allCont.classList.remove('hidden');

            let stats = {};
            Object.values(db.matches).forEach(m => {
                if (m.score.home_total === null) return;
                let hMapped = getMappedTeamName(m.home_team), aMapped = getMappedTeamName(m.away_team);
                let isHome = hMapped === teamA, isAway = aMapped === teamA;
                if (!isHome && !isAway) return;
                
                let opp = isHome ? aMapped : hMapped;
                if (!stats[opp]) stats[opp] = { name: opp, S:0, V:0, O:0, F:0, GM:0, IM:0 };
                
                let myG = isHome ? m.score.home_total : m.score.away_total;
                let oppG = isHome ? m.score.away_total : m.score.home_total;
                let myP = isHome ? m.score.home_pen : m.score.away_pen;
                let oppP = isHome ? m.score.away_pen : m.score.home_pen;
                
                stats[opp].S++; stats[opp].GM += myG; stats[opp].IM += oppG;
                
                if (myG > oppG) stats[opp].V++;
                else if (oppG > myG) stats[opp].F++;
                else {
                    if (myP !== null && oppP !== null) {
                        if (myP > oppP) stats[opp].V++; else stats[opp].F++;
                    } else stats[opp].O++;
                }
            });

            let sortedStats = Object.values(stats).sort((a,b) => {
                if (b.S !== a.S) return b.S - a.S;
                let pA = a.V*3 + a.O, pB = b.V*3 + b.O;
                if (pB !== pA) return pB - pA;
                return (b.GM-b.IM) - (a.GM-a.IM);
            });

            let html = `<div class="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center"><h3 class="font-bold text-slate-800">Summerad historik för <span class="text-blue-700">${teamA}</span> i VM</h3></div><div class="max-h-[60vh] overflow-y-auto"><table class="w-full text-sm text-left border-collapse"><thead class="bg-white sticky top-0 z-10 border-b border-slate-200 shadow-sm"><tr><th class="p-3 font-semibold text-slate-500 uppercase text-xs">Motståndare</th><th class="p-3 font-semibold text-slate-500 uppercase text-xs text-center">S</th><th class="p-3 font-semibold text-slate-500 uppercase text-xs text-center">V</th><th class="p-3 font-semibold text-slate-500 uppercase text-xs text-center">O</th><th class="p-3 font-semibold text-slate-500 uppercase text-xs text-center">F</th><th class="p-3 font-semibold text-slate-500 uppercase text-xs text-center">Mål</th></tr></thead><tbody class="divide-y divide-slate-100">`;
            sortedStats.forEach(t => {
                html += `<tr class="hover:bg-blue-50 transition"><td class="p-3 font-bold text-slate-700 cursor-pointer hover:text-blue-600 group" onclick="document.getElementById('h2h-team-b').value='${t.name}'; renderH2H();" title="Klicka för att visa matcher mot ${t.name}">${t.name} <span class="text-[10px] ml-2 text-slate-300 group-hover:text-blue-400 transition">Visa VS &rarr;</span></td><td class="p-3 text-center text-slate-600">${t.S}</td><td class="p-3 text-center text-emerald-600 font-bold">${t.V}</td><td class="p-3 text-center text-slate-500 font-medium">${t.O}</td><td class="p-3 text-center text-red-500 font-bold">${t.F}</td><td class="p-3 text-center text-slate-500 text-xs">${t.GM}-${t.IM} <span class="text-[10px]">(${t.GM-t.IM > 0 ? '+'+(t.GM-t.IM) : t.GM-t.IM})</span></td></tr>`;
            });
            html += `</tbody></table></div>`;
            allCont.innerHTML = html;
        }

        // =========================================================
        // 🛡️ LAGREKORD & SVITER
        // =========================================================
        function switchTeamSubTab(subViewId) {
            document.querySelectorAll('.team-sub-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(subViewId).classList.remove('hidden');
            
            const tabs = [
                {id: 'team-view-top', btn: 'team-sub-btn-top'},
                {id: 'team-view-streaks', btn: 'team-sub-btn-streaks'}
            ];
            
            tabs.forEach(t => {
                const btn = document.getElementById(t.btn);
                if (t.id === subViewId) btn.className = "px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm whitespace-nowrap";
                else btn.className = "px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition whitespace-nowrap";
            });
            
            renderTeamData();
        }

        function populateTeamFilters() {
            const nationSelect = document.getElementById('team-nation-filter');
            const yearSelect = document.getElementById('team-year-filter');
            if (nationSelect.options.length <= 1) {
                getAllTeams().forEach(t => nationSelect.add(new Option(t, t)));
            }
            if (yearSelect.options.length <= 1) {
                Object.keys(db.tournaments).sort((a, b) => b - a).forEach(y => yearSelect.add(new Option(y, y)));
            }
        }

        function openH2HFromToplist(t1, t2) {
            switchTab('tab-h2h');
            document.getElementById('h2h-team-a').value = t1;
            updateTeamBDropdown(false); 
            document.getElementById('h2h-team-b').value = t2;
            renderH2H();
        }

        function renderTeamData() {
            const activeTab = document.querySelector('.team-sub-content:not(.hidden)').id;
            const nation = document.getElementById('team-nation-filter').value;
            const year = document.getElementById('team-year-filter').value;

            let matches = Object.values(db.matches).filter(m => m.score.home_total !== null);
            if (year !== 'all') matches = matches.filter(m => m.date.startsWith(year));

            if (activeTab === 'team-view-top') renderTeamRecords(matches, nation, year);
            else if (activeTab === 'team-view-streaks') renderTeamStreaks(matches, nation, year);
        }

        function renderTeamRecords(matches, nation, year) {
            const type = document.getElementById('team-top-type').value;
            const container = document.getElementById('team-top-results');
            
            if (type === 'placements') {
                let years = Object.keys(db.tournaments).sort((a,b) => a - b);
                let validTeams = Object.keys(db.placements).sort();
                if (nation !== 'all') validTeams = validTeams.filter(t => t === nation);

                let html = `
                <div id="top-scroll" class="hidden md:block" style="overflow-x: auto; overflow-y: hidden; height: 16px; margin-bottom: 2px;" onscroll="document.getElementById('bottom-scroll').scrollLeft = this.scrollLeft;">
                    <div id="top-scroll-inner" style="height: 1px;"></div>
                </div>
                <div id="bottom-scroll" style="overflow-x: auto;" onscroll="document.getElementById('top-scroll').scrollLeft = this.scrollLeft;">
                <table class="w-full text-left border-collapse" id="matrix-table">
                <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10"><tr>
                <th class="p-3 text-xs font-semibold text-slate-500 uppercase sticky left-0 bg-slate-50 z-20 shadow-[1px_0_0_0_#e2e8f0]">Nation</th>`;
                
                years.forEach(y => html += `<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center min-w-[50px]">${y.substring(2)}</th>`);
                html += '</tr></thead><tbody class="divide-y divide-slate-100">';

                validTeams.forEach(t => {
                    html += `<tr class="hover:bg-blue-50 transition">
                        <td class="p-3 font-bold text-slate-700 sticky left-0 bg-white z-10 shadow-[1px_0_0_0_#e2e8f0] group-hover:bg-blue-50 whitespace-nowrap">${t}</td>`;
                    years.forEach(y => {
                        let place = db.placements[t][y] || '-';
                        place = String(place).replace('.0', '');
                        let placeClass = place === '1' ? 'bg-yellow-100 font-bold text-yellow-800' :
                                         place === '2' ? 'bg-slate-200 font-bold text-slate-700' :
                                         place === '3' ? 'bg-orange-200 font-bold text-orange-800' : 'text-slate-500 font-medium';
                        if(place === '-') placeClass = 'text-slate-300';
                        html += `<td class="p-2 text-center text-xs ${placeClass}">${place}</td>`;
                    });
                    html += '</tr>';
                });
                if (validTeams.length === 0) html += `<tr><td colspan="${years.length + 1}" class="p-6 text-center text-slate-500 italic">Ingen placeringsdata hittades.</td></tr>`;
                
                html += '</tbody></table></div>';
                container.innerHTML = html;

                setTimeout(() => {
                    let table = document.getElementById('matrix-table');
                    let inner = document.getElementById('top-scroll-inner');
                    if(table && inner) inner.style.width = table.offsetWidth + 'px';
                }, 50);

                return; 
            }

            let html = '<table class="w-full text-left border-collapse"><thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10"><tr>';
            html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase w-12 text-center">#</th>';

            if (type === 'biggest_win') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase">Match (Datum)</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Resultat</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Marginal</th></tr></thead><tbody class="divide-y divide-slate-100">';
                let validMatches = matches;
                if (nation !== 'all') validMatches = matches.filter(m => getMappedTeamName(m.home_team) === nation || getMappedTeamName(m.away_team) === nation);
                let sorted = validMatches.map(m => {
                    let diff = Math.abs(m.score.home_total - m.score.away_total);
                    let winner = m.score.home_total > m.score.away_total ? m.home_team : m.away_team;
                    return { ...m, diff: diff, winnerMapped: getMappedTeamName(winner) };
                }).filter(m => m.diff > 0);
                if (nation !== 'all') sorted = sorted.filter(m => m.winnerMapped === nation);
                sorted.sort((a, b) => b.diff - a.diff || (b.score.home_total + b.score.away_total) - (a.score.home_total + a.score.away_total));
                sorted.slice(0, 50).forEach((m, i) => {
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openMatchModal('${m.id}')">
                        <td class="p-3 text-center font-bold text-slate-400">${i+1}</td>
                        <td class="p-3 font-medium text-slate-700">${m.home_team} - ${m.away_team} <span class="text-[10px] text-slate-400 block">${m.date} (${m.phase})</span></td>
                        <td class="p-3 text-center font-bold text-slate-800 bg-slate-50">${m.score.home_total}-${m.score.away_total}</td>
                        <td class="p-3 text-center font-black text-emerald-600">+${m.diff}</td></tr>`;
                });
            } 
            else if (type === 'high_score') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase">Match (Datum)</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Resultat</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Totalt Mål</th></tr></thead><tbody class="divide-y divide-slate-100">';
                let validMatches = matches;
                if (nation !== 'all') validMatches = matches.filter(m => getMappedTeamName(m.home_team) === nation || getMappedTeamName(m.away_team) === nation);
                let sorted = validMatches.map(m => {
                    let tot = m.score.home_total + m.score.away_total;
                    return { ...m, totGoals: tot };
                }).filter(m => m.totGoals > 0).sort((a, b) => b.totGoals - a.totGoals);
                sorted.slice(0, 50).forEach((m, i) => {
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openMatchModal('${m.id}')">
                        <td class="p-3 text-center font-bold text-slate-400">${i+1}</td>
                        <td class="p-3 font-medium text-slate-700">${m.home_team} - ${m.away_team} <span class="text-[10px] text-slate-400 block">${m.date} (${m.phase})</span></td>
                        <td class="p-3 text-center font-bold text-slate-800 bg-slate-50">${m.score.home_total}-${m.score.away_total}</td>
                        <td class="p-3 text-center font-black text-blue-600">${m.totGoals}</td></tr>`;
                });
            }
            else if (type === 'attendance') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase">Match (Datum)</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase">Arena</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Publik</th></tr></thead><tbody class="divide-y divide-slate-100">';
                let validMatches = matches;
                if (nation !== 'all') validMatches = matches.filter(m => getMappedTeamName(m.home_team) === nation || getMappedTeamName(m.away_team) === nation);
                let sorted = validMatches.filter(m => m.attendance !== null).sort((a, b) => b.attendance - a.attendance);
                sorted.slice(0, 50).forEach((m, i) => {
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openMatchModal('${m.id}')">
                        <td class="p-3 text-center font-bold text-slate-400">${i+1}</td>
                        <td class="p-3 font-medium text-slate-700">${m.home_team} - ${m.away_team} <span class="text-[10px] text-slate-400 block">${m.date}</span></td>
                        <td class="p-3 font-medium text-slate-600">${m.arena}, ${m.city}</td>
                        <td class="p-3 text-right font-black text-slate-800">${m.attendance.toLocaleString('sv-SE')}</td></tr>`;
                });
            }
            else if (type === 'medals') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase">Nation</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center bg-yellow-50 text-yellow-700">🥇 Guld</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center bg-slate-100 text-slate-600">🥈 Silver</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center bg-orange-50 text-orange-800">🥉 Brons</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Totalt</th></tr></thead><tbody class="divide-y divide-slate-100">';
                let medals = {};
                Object.values(db.tournaments).forEach(t => {
                    if (year !== 'all' && str(t.year) !== year) return;
                    if(t.winner && t.winner !== 'Okänd') {
                        let mapped = getMappedTeamName(t.winner);
                        if(!medals[mapped]) medals[mapped] = {G:0, S:0, B:0, Tot:0};
                        medals[mapped].G++; medals[mapped].Tot++;
                    }
                });
                matches.forEach(m => {
                    if(!m.advancement) return;
                    let hMap = getMappedTeamName(m.home_team), aMap = getMappedTeamName(m.away_team);
                    if (m.advancement.is_final) {
                        let loser = m.advancement.advancing_team === m.home_team ? aMap : hMap;
                        if(m.advancement.advancing_team === null) {
                            if(m.score.home_total > m.score.away_total) loser = aMap;
                            else if(m.score.away_total > m.score.home_total) loser = hMap;
                        }
                        if(loser) {
                            if(!medals[loser]) medals[loser] = {G:0, S:0, B:0, Tot:0};
                            medals[loser].S++; medals[loser].Tot++;
                        }
                    }
                    if (m.advancement.is_bronze) {
                        let winner = m.advancement.advancing_team === m.home_team ? hMap : aMap;
                        if(m.advancement.advancing_team === null) {
                            if(m.score.home_total > m.score.away_total) winner = hMap;
                            else if(m.score.away_total > m.score.home_total) winner = aMap;
                        }
                        if(winner) {
                            if(!medals[winner]) medals[winner] = {G:0, S:0, B:0, Tot:0};
                            medals[winner].B++; medals[winner].Tot++;
                        }
                    }
                });
                let sorted = Object.entries(medals).map(([k, v]) => ({name: k, ...v})).sort((a,b) => {
                    if(b.G !== a.G) return b.G - a.G; if(b.S !== a.S) return b.S - a.S;
                    if(b.B !== a.B) return b.B - a.B; return b.Tot - a.Tot;
                }).filter(t => t.Tot > 0);
                if (nation !== 'all') sorted = sorted.filter(t => t.name === nation);
                sorted.forEach((t, i) => {
                    html += `<tr class="hover:bg-blue-50 transition">
                        <td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${t.name}</td>
                        <td class="p-3 text-center font-black text-yellow-600 bg-yellow-50/30">${t.G > 0 ? t.G : '-'}</td>
                        <td class="p-3 text-center font-black text-slate-500 bg-slate-50/50">${t.S > 0 ? t.S : '-'}</td>
                        <td class="p-3 text-center font-black text-orange-700 bg-orange-100/50">${t.B > 0 ? t.B : '-'}</td>
                        <td class="p-3 text-center font-bold text-blue-900">${t.Tot}</td></tr>`;
                });
                if (sorted.length === 0) html += `<tr><td colspan="6" class="p-6 text-center text-slate-500 italic">Inga medaljer funna med detta filter.</td></tr>`;
            }
            else if (type === 'h2h_most') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase">Möte (Lag A - Lag B)</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Antal Matcher</th></tr></thead><tbody class="divide-y divide-slate-100">';
                
                let pairs = {};
                matches.forEach(m => {
                    let t1 = getMappedTeamName(m.home_team);
                    let t2 = getMappedTeamName(m.away_team);
                    let pairArr = [t1, t2].sort();
                    let pKey = pairArr[0] + " - " + pairArr[1];
                    if (!pairs[pKey]) pairs[pKey] = { name: pKey, count: 0, t1: pairArr[0], t2: pairArr[1] };
                    pairs[pKey].count++;
                });
                
                let sortedPairs = Object.values(pairs).sort((a,b) => b.count - a.count);
                if (nation !== 'all') {
                    sortedPairs = sortedPairs.filter(p => p.t1 === nation || p.t2 === nation);
                }
                
                sortedPairs.slice(0, 50).forEach((p, i) => {
                    html += `<tr class="hover:bg-blue-50 transition cursor-pointer" onclick="openH2HFromToplist('${p.t1.replace(/'/g, "\\'")}', '${p.t2.replace(/'/g, "\\'")}')">
                        <td class="p-3 text-center font-bold text-slate-400">${i+1}</td>
                        <td class="p-3 font-bold text-slate-700">${p.name} <span class="text-[10px] text-slate-400 ml-2">Klicka för H2H-analys &rarr;</span></td>
                        <td class="p-3 text-center font-black text-blue-600">${p.count}</td></tr>`;
                });
            }

            html += '</tbody></table>';
            container.innerHTML = html;
        }

        function renderTeamStreaks(matches, filterNation, filterYear) {
            matches.sort((a, b) => new Date(a.date) - new Date(b.date));
            let teamData = {};
            getAllTeams().forEach(t => {
                teamData[t] = {
                    W: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    U: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    L: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    winless: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    CS: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    drought: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    scoring: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null },
                    conceding: { cur: 0, max: 0, curStart: null, maxStart: null, maxEnd: null }
                };
            });

            function updateS(td, type, active, date) {
                if (active) {
                    if (td[type].cur === 0) td[type].curStart = date;
                    td[type].cur++;
                    if (td[type].cur > td[type].max) {
                        td[type].max = td[type].cur; td[type].maxStart = td[type].curStart; td[type].maxEnd = date;
                    }
                } else { td[type].cur = 0; td[type].curStart = null; }
            }

            matches.forEach(m => {
                let hTeam = getMappedTeamName(m.home_team), aTeam = getMappedTeamName(m.away_team);
                let hG = m.score.home_total, aG = m.score.away_total, date = m.date;
                if (teamData[hTeam]) {
                    let d = teamData[hTeam];
                    updateS(d, 'W', hG > aG, date); updateS(d, 'U', hG >= aG, date); updateS(d, 'L', hG < aG, date);
                    updateS(d, 'winless', hG <= aG, date); updateS(d, 'CS', aG === 0, date); updateS(d, 'drought', hG === 0, date);
                    updateS(d, 'scoring', hG > 0, date); updateS(d, 'conceding', aG > 0, date);
                }
                if (teamData[aTeam]) {
                    let d = teamData[aTeam];
                    updateS(d, 'W', aG > hG, date); updateS(d, 'U', aG >= hG, date); updateS(d, 'L', aG < hG, date);
                    updateS(d, 'winless', aG <= hG, date); updateS(d, 'CS', hG === 0, date); updateS(d, 'drought', aG === 0, date);
                    updateS(d, 'scoring', aG > 0, date); updateS(d, 'conceding', hG > 0, date);
                }
            });

            let validTeams = Object.keys(teamData);
            if (filterNation !== 'all') validTeams = [filterNation];

            const categories = [
                { id: 'W', title: 'Segrar (Spel)', color: 'emerald-600', bg: 'emerald-50' },
                { id: 'U', title: 'Obesegrade', color: 'emerald-600', bg: 'emerald-50' },
                { id: 'L', title: 'Förluster (Spel)', color: 'rose-600', bg: 'rose-50' },
                { id: 'winless', title: 'Utan Seger', color: 'orange-500', bg: 'orange-50' },
                { id: 'CS', title: 'Hållna Nollor', color: 'blue-500', bg: 'blue-50' },
                { id: 'drought', title: 'Måltorka', color: 'slate-500', bg: 'slate-50' },
                { id: 'scoring', title: 'Målsvit', color: 'indigo-500', bg: 'indigo-50' },
                { id: 'conceding', title: 'Insläppta (Svit)', color: 'red-500', bg: 'red-50' }
            ];

            let cardsHtml = '';
            categories.forEach(cat => {
                let maxRec = 0, maxTeam = '-';
                validTeams.forEach(t => { if (teamData[t] && teamData[t][cat.id].max > maxRec) { maxRec = teamData[t][cat.id].max; maxTeam = t; } });
                cardsHtml += `<div class="bg-white border border-${cat.bg.split('-')[0]}-200 p-4 rounded-xl text-center shadow-sm"><div class="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1">${cat.title}</div><div class="text-3xl font-black text-${cat.color}">${maxRec}</div><div class="text-xs font-bold text-slate-700 mt-1 truncate">${maxTeam}</div></div>`;
            });
            document.getElementById('streak-summary-cards').innerHTML = cardsHtml;

            const type = document.getElementById('team-streak-type').value;
            let listData = [];
            validTeams.forEach(t => {
                if (teamData[t] && teamData[t][type].max > 0) {
                    listData.push({ team: t, val: teamData[t][type].max, start: teamData[t][type].maxStart, end: teamData[t][type].maxEnd });
                }
            });
            listData.sort((a, b) => b.val - a.val);

            let html = '<table class="w-full text-left border-collapse"><thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10"><tr><th class="p-3 text-xs font-semibold text-slate-500 uppercase w-12 text-center">#</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase">Lag</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Antal Matcher</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Från (Datum)</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Till (Datum)</th></tr></thead><tbody class="divide-y divide-slate-100">';
            listData.slice(0, 50).forEach((item, i) => {
                let startY = item.start ? item.start.substring(0,4) : '', endY = item.end ? item.end.substring(0,4) : '';
                let yearSpan = startY === endY ? `<span class="bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded text-[9px] ml-1">${startY}</span>` : `<span class="bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded text-[9px] ml-1">${startY}/${endY.substring(2)}</span>`;
                html += `<tr class="hover:bg-amber-50 transition cursor-pointer group" onclick="openStreakModal('${item.team}', '${type}', '${item.start}', '${item.end}', ${item.val})">
                    <td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${item.team} <span class="text-[10px] text-slate-400 ml-2 group-hover:text-amber-600 transition">Visa matcher &rarr;</span></td>
                    <td class="p-3 text-center font-black text-blue-900 text-lg">${item.val}</td>
                    <td class="p-3 text-center text-xs text-slate-500">${item.start || '-'}</td><td class="p-3 text-center text-xs text-slate-500">${item.end || '-'}${yearSpan}</td>
                </tr>`;
            });
            if (listData.length === 0) html += `<tr><td colspan="5" class="p-6 text-center text-slate-500 italic">Inga sviter hittades för denna filtrering.</td></tr>`;
            html += '</tbody></table>';
            document.getElementById('team-streak-results').innerHTML = html;
        }

        // =========================================================
        // 👤 SPELARE & STATISTIK 
        // =========================================================
        window.playerSearchCurrentPage = 0;

        function switchPlayerSubTab(subViewId) {
            document.querySelectorAll('.player-sub-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(subViewId).classList.remove('hidden');
            const tabs = [ {id: 'player-view-search', btn: 'player-sub-btn-search'}, {id: 'player-view-top', btn: 'player-sub-btn-top'} ];
            tabs.forEach(t => {
                const btn = document.getElementById(t.btn);
                if (t.id === subViewId) btn.className = "px-4 py-2 font-bold text-sm text-blue-900 border-b-2 border-blue-900 bg-white rounded-t-lg shadow-sm";
                else btn.className = "px-4 py-2 font-bold text-sm text-slate-500 hover:text-blue-900 border-b-2 border-transparent transition";
            });
            if (subViewId === 'player-view-search') document.getElementById('player-search-input').focus();
            if (subViewId === 'player-view-top') { populateTopNations(); renderTopList(); }
        }

        function populatePlayerNations() {
            const select = document.getElementById('player-nation-filter');
            if (select.options.length > 1) return; 
            let nations = new Set();
            Object.values(db.players).forEach(p => { if(p.nations) p.nations.forEach(n => nations.add(n)); });
            Array.from(nations).sort().forEach(n => { select.add(new Option(n, n)); });
        }

        function searchPlayersLive(pageIndex = 0) {
            if (typeof pageIndex !== 'number') pageIndex = 0; // Fallback for event objects
            window.playerSearchCurrentPage = pageIndex;

            const query = document.getElementById('player-search-input').value.toLowerCase().trim();
            const nationFilter = document.getElementById('player-nation-filter').value;
            const resultsContainer = document.getElementById('player-search-results');
            document.getElementById('player-profile-container').classList.add('hidden');
            
            if (query.length < 2 && nationFilter === 'all') {
                resultsContainer.innerHTML = '<div class="col-span-3 text-center text-slate-400 p-4 text-sm">Skriv minst 2 bokstäver eller välj en nation för att söka bland VM-spelare...</div>';
                return;
            }
            let matches = Object.values(db.players).filter(p => {
                let nameMatch = formatName(p.name).toLowerCase().includes(query);
                let natMatch = nationFilter === 'all' || p.nations.includes(nationFilter);
                return nameMatch && natMatch;
            });
            if (matches.length === 0) {
                resultsContainer.innerHTML = '<div class="col-span-3 text-center text-red-400 p-4 text-sm font-medium">Ingen spelare hittades med nuvarande sökfilter.</div>';
                return;
            }
            matches.sort((a, b) => {
                if (b.matches_played !== a.matches_played) return b.matches_played - a.matches_played;
                return formatName(a.name).localeCompare(formatName(b.name));
            });
            
            const PAGE_SIZE = 50;
            const totalMatches = matches.length;
            const totalPages = Math.ceil(totalMatches / PAGE_SIZE);
            const startIdx = pageIndex * PAGE_SIZE;
            const endIdx = startIdx + PAGE_SIZE;
            const currentMatches = matches.slice(startIdx, endIdx);

            let html = '';
            
            if (nationFilter !== 'all' && query.length === 0) {
                let totalSquad = matches.length;
                let totalPlayed = matches.filter(p => p.matches_played > 0).length;
                html += `
                    <div class="col-span-1 md:col-span-2 lg:col-span-3 bg-blue-50 border border-blue-200 p-4 rounded-xl text-blue-900 flex justify-between items-center mb-2 shadow-sm">
                        <div class="font-bold text-lg">${nationFilter}</div>
                        <div class="text-sm font-medium text-right">
                            <span class="block sm:inline"><b>${totalSquad}</b> spelare totalt i trupperna.</span>
                            <span class="block sm:inline sm:ml-1">Varav <b>${totalPlayed}</b> har spelat match.</span>
                        </div>
                    </div>`;
            }

            currentMatches.forEach(p => {
                let formattedName = formatName(p.name);
                let gkStr = p.is_gk ? ' <span class="text-[10px] text-slate-400 font-normal">(mv)</span>' : '';
                let nations = p.nations.join(", ");
                let goalIcon = p.goals > 0 ? `<span class="ml-2 text-emerald-600 font-bold text-xs" title="Har gjort mål i VM">⚽ ${p.goals}</span>` : '';
                
                let matchesText = p.matches_played > 0 
                    ? `<div class="text-xs font-bold text-slate-500">${p.matches_played} m</div>` 
                    : `<div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Endast trupp</div>`;

                html += `
                    <div onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')" class="bg-white border border-slate-200 p-3 rounded-lg shadow-sm hover:border-blue-500 hover:shadow-md cursor-pointer transition flex justify-between items-center group">
                        <div class="overflow-hidden pr-2">
                            <div class="font-bold text-slate-800 group-hover:text-blue-600 truncate">${formattedName}${gkStr}</div>
                            <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 truncate">${nations}</div>
                        </div>
                        <div class="text-right whitespace-nowrap flex flex-col items-end">
                            ${matchesText}
                            ${goalIcon}
                        </div>
                    </div>`;
            });

            if (totalPages > 1) {
                html += `
                <div class="col-span-1 md:col-span-2 lg:col-span-3 flex justify-between items-center bg-slate-50 p-3 rounded-lg border border-slate-200 mt-2 shadow-sm">
                    <button onclick="searchPlayersLive(${pageIndex - 1})" ${pageIndex === 0 ? 'disabled class="text-slate-300 cursor-not-allowed"' : 'class="text-blue-600 hover:text-blue-800 font-bold transition"'}><span class="text-lg leading-none mr-1">&larr;</span> Föregående</button>
                    <span class="text-xs text-slate-500 font-bold uppercase tracking-wider">Sida ${pageIndex + 1} av ${totalPages} <span class="font-normal normal-case">(${totalMatches} träffar)</span></span>
                    <button onclick="searchPlayersLive(${pageIndex + 1})" ${pageIndex === totalPages - 1 ? 'disabled class="text-slate-300 cursor-not-allowed"' : 'class="text-blue-600 hover:text-blue-800 font-bold transition"'}>Nästa <span class="text-lg leading-none ml-1">&rarr;</span></button>
                </div>`;
            }
            resultsContainer.innerHTML = html;
        }

        function openPlayerProfile(rawName) {
            const p = db.players[rawName];
            if (!p) return;
            switchPlayerSubTab('player-view-search');
            let gkStr = p.is_gk ? ' <span class="text-blue-300 text-base font-normal ml-2" title="Målvakt">(mv)</span>' : '';
            let birthYearStr = p.birth_date ? ` <span class="text-blue-300 text-lg font-medium ml-2">(född ${p.birth_date.substring(0,4)})</span>` : (p.birth_year ? ` <span class="text-blue-300 text-lg font-medium ml-2">(född ${p.birth_year})</span>` : "");
            
            document.getElementById('profile-name').innerHTML = formatName(p.name) + gkStr + birthYearStr;
            document.getElementById('profile-nations').innerText = p.nations.join(" & ");
            let tourHtml = ''; p.tournaments.sort().forEach(y => { tourHtml += `<span class="bg-blue-800 text-blue-100 border border-blue-700 px-2 py-1 rounded text-sm shadow-inner">${y}</span>`; });
            document.getElementById('profile-tournaments').innerHTML = tourHtml;
            document.getElementById('profile-stat-matches').innerText = p.matches_played;
            document.getElementById('profile-stat-goals').innerText = p.goals;
            document.getElementById('profile-stat-minutes').innerText = p.minutes_played + "'";
            document.getElementById('profile-stat-yc').innerText = p.yellow_cards;
            document.getElementById('profile-stat-rc').innerText = p.red_cards;
            const listContainer = document.getElementById('profile-matches-list');
            let mHtml = '';
            let pMatches = p.match_list.map(mId => db.matches[mId]).filter(m => m);
            pMatches.sort((a,b) => new Date(a.date) - new Date(b.date));
            pMatches.forEach(m => {
                const scoreClass = m.score.home_total !== null ? "font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200" : "text-slate-400 text-xs";
                let t_phases = p.nations; let isHome = false;
                t_phases.forEach(nat => { if(getMappedTeamName(m.home_team) === nat) isHome = true; });
                mHtml += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100"><div class="text-[10px] uppercase font-bold text-blue-900">${m.date.substring(0,4)}</div><div class="text-xs text-slate-500">${m.phase}</div></td>
                        <td class="p-3 border-t border-slate-100"><div class="text-xs text-slate-500">${m.date}</div></td>
                        <td class="p-3 border-t border-slate-100 text-right ${isHome ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="${scoreClass}">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 ${!isHome ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.away_team}</td>
                    </tr>`;
            });
            listContainer.innerHTML = mHtml;
            document.getElementById('player-profile-container').classList.remove('hidden');
            setTimeout(() => { window.scrollTo({ top: document.getElementById('player-profile-container').offsetTop - 100, behavior: 'smooth' }); }, 50);
        }

        function closePlayerProfile() {
            document.getElementById('player-profile-container').classList.add('hidden');
            searchPlayersLive(window.playerSearchCurrentPage); 
        }

        // --- TOPPLISTOR ---
        function populateTopNations() {
            const select = document.getElementById('top-nation-filter');
            if (select.options.length > 1) return; 
            let nations = new Set();
            Object.values(db.players).forEach(p => { if(p.nations) p.nations.forEach(n => nations.add(n)); });
            Array.from(nations).sort().forEach(n => { select.add(new Option(n, n)); });
        }

        function renderTopList() {
            const type = document.getElementById('top-type-filter').value;
            const nation = document.getElementById('top-nation-filter').value;
            const container = document.getElementById('top-list-results');
            let players = Object.values(db.players);
            if (nation !== 'all') players = players.filter(p => p.nations.includes(nation));

            let html = '<table class="w-full text-left border-collapse"><thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10"><tr>';
            html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase w-12 text-center">#</th><th class="p-3 text-xs font-semibold text-slate-500 uppercase">Spelare</th>';
            let sorted = [];

            if (type === 'matches') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Matcher</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => b.matches_played - a.matches_played).filter(p => p.matches_played > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let yearsArr = [...p.tournaments].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-blue-900">${p.matches_played}</td></tr>`;
                });
            }
            else if (type === 'goals') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Mål</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => b.goals - a.goals).filter(p => p.goals > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let yearsArr = [...p.tournaments].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-emerald-600">${p.goals}</td></tr>`;
                });
            }
            else if (type === 'tournaments') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Spelade Turneringar</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => b.tournaments.length - a.tournaments.length).filter(p => p.tournaments.length > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let yearsArr = [...p.tournaments].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-purple-600">${p.tournaments.length} <span class="text-xs font-normal text-slate-400 block">(${p.tournaments.join(', ')})</span></td></tr>`;
                });
            }
            else if (type === 'tournaments_squad') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Trupputtagningar</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => {
                    let aLen = a.squad_tournaments ? a.squad_tournaments.length : a.tournaments.length;
                    let bLen = b.squad_tournaments ? b.squad_tournaments.length : b.tournaments.length;
                    return bLen - aLen;
                }).filter(p => (p.squad_tournaments ? p.squad_tournaments.length : p.tournaments.length) > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let tList = p.squad_tournaments || p.tournaments;
                    let yearsArr = [...tList].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    let matchesBadge = p.matches_played === 0 ? `<span class="text-[9px] uppercase bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded ml-2 border border-slate-200">Endast trupp</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay}${matchesBadge} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-purple-600">${tList.length} <span class="text-xs font-normal text-slate-400 block">(${tList.join(', ')})</span></td></tr>`;
                });
            }
            else if (type === 'yellow') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Gula Kort</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => b.yellow_cards - a.yellow_cards).filter(p => p.yellow_cards > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let yearsArr = [...p.tournaments].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-amber-500">${p.yellow_cards}</td></tr>`;
                });
            }
            else if (type === 'red') {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Röda Kort</th></tr></thead><tbody class="divide-y divide-slate-100">';
                sorted = players.sort((a, b) => b.red_cards - a.red_cards).filter(p => p.red_cards > 0);
                sorted.slice(0, 50).forEach((p, i) => {
                    let yearsArr = [...p.tournaments].sort();
                    let yearStr = yearsArr.length > 1 ? `${yearsArr[0]}-${yearsArr[yearsArr.length-1]}` : (yearsArr.length === 1 ? yearsArr[0] : '');
                    let yearsDisplay = yearStr ? ` <span class="text-xs font-normal text-slate-400 ml-1">(${yearStr})</span>` : '';
                    html += `<tr class="hover:bg-blue-50 cursor-pointer" onclick="openPlayerProfile('${p.name.replace(/'/g, "\\'")}')"><td class="p-3 text-center font-bold text-slate-400">${i+1}</td><td class="p-3 font-bold text-slate-700">${formatName(p.name)}${p.is_gk ? ' <span class="text-[10px] text-slate-400">(mv)</span>' : ''}${yearsDisplay} <span class="text-xs font-normal text-slate-400 block sm:inline sm:ml-2">${p.nations.join(', ')}</span></td><td class="p-3 text-center font-black text-red-600">${p.red_cards}</td></tr>`;
                });
            }
            else if (type.includes('oldest') || type.includes('youngest')) {
                html += '<th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Ålder</th></tr></thead><tbody class="divide-y divide-slate-100">';
                html += `<tr><td colspan="3" class="p-8 text-center text-slate-500 italic font-medium">Vi kommer att aktivera åldersberäkningen snart! Datan finns inläst och väntar på de avancerade beräkningsfunktionerna.</td></tr>`;
            }

            html += '</tbody></table>';
            container.innerHTML = html;
        }

        // =========================================================
        // MODALER FÖR DELDETALJER (TURNERING/LAG/SVIT)
        // =========================================================
        function openTournamentModal(year) {
            let t = db.tournaments[year];
            if (!t) return;
            
            document.getElementById('tm-year').innerText = year;
            document.getElementById('tm-host').innerText = t.host;
            document.getElementById('tm-winner').innerText = t.winner && t.winner !== 'Okänd' ? t.winner : 'Ej korad';
            
            let s = t.stats;
            document.getElementById('tm-coach').innerText = s.champion_coach && s.champion_coach !== "Okänd" ? formatName(s.champion_coach) : 'Saknas';
            document.getElementById('tm-captain').innerText = s.champion_captain ? formatName(s.champion_captain) : 'Saknas i databas';
            
            document.getElementById('tm-matches').innerText = s.matches_played;
            document.getElementById('tm-goals').innerText = s.total_goals;
            document.getElementById('tm-avg-goals').innerText = s.matches_played > 0 ? (s.total_goals / s.matches_played).toFixed(2) : "0.00";
            document.getElementById('tm-avg-att').innerText = s.matches_played > 0 && s.total_attendance > 0 ? Math.round(s.total_attendance / s.matches_played).toLocaleString('sv-SE') : "0";
            
            document.getElementById('tm-g-h1').innerText = s.goals_h1;
            document.getElementById('tm-g-h2').innerText = s.goals_h2;
            document.getElementById('tm-g-et').innerText = `${s.goals_et} (${s.matches_et} m)`;
            document.getElementById('tm-g-pen').innerText = `${s.goals_pen} (${s.matches_pen} m)`;
            
            document.getElementById('tm-p-used').innerText = s.players_used;
            document.getElementById('tm-p-debut').innerText = s.debutants;
            document.getElementById('tm-p-scorers').innerText = s.goalscorers;
            
            if (s.top_scorers && s.top_scorers.length > 0) {
                let tsStr = s.top_scorers.map(x => `${formatName(x.name)} (${x.goals})`).join(', ');
                document.getElementById('tm-p-top').innerText = tsStr;
            } else {
                document.getElementById('tm-p-top').innerText = '-';
            }
            
            document.getElementById('tm-btn-matches').onclick = () => {
                closeTournamentModal();
                document.getElementById('filter-year').value = year;
                document.getElementById('search-input').value = '';
                document.getElementById('clear-search-btn').classList.add('hidden');
                window.lastSubTabBeforeSearch = null;
                switchTab('tab-matcher');
                switchSubTab('sub-view-list');
                onYearFilterChange();
            };
            
            document.getElementById('tournament-modal').classList.remove('hidden');
        }

        function closeTournamentModal() {
            document.getElementById('tournament-modal').classList.add('hidden');
        }

        function openTeamModal(mappedName) {
            document.getElementById('team-modal-name').innerText = mappedName;
            
            let teamMatches = Object.values(db.matches).filter(m => 
                m.score.home_total !== null && (getMappedTeamName(m.home_team) === mappedName || getMappedTeamName(m.away_team) === mappedName)
            );
            teamMatches.sort((a,b) => new Date(a.date) - new Date(b.date));
            
            let origNames = new Set();
            teamMatches.forEach(m => {
                if (getMappedTeamName(m.home_team) === mappedName) origNames.add(m.home_team);
                if (getMappedTeamName(m.away_team) === mappedName) origNames.add(m.away_team);
            });
            
            let subtotalHtml = '';
            let isMerged = origNames.size > 1;
            
            if (isMerged) {
                Array.from(origNames).sort().forEach(oName => {
                    let s = 0, v = 0, o = 0, f = 0, gm = 0, im = 0, p = 0;
                    teamMatches.forEach(m => {
                        let isH = m.home_team === oName, isA = m.away_team === oName;
                        if (!isH && !isA) return;
                        s++;
                        let hg = m.score.home_total, ag = m.score.away_total;
                        gm += isH ? hg : ag; im += isH ? ag : hg;
                        if (hg > ag) { if(isH) {v++; p+=3;} else {f++;} }
                        else if (ag > hg) { if(isA) {v++; p+=3;} else {f++;} }
                        else { o++; p++; }
                    });
                    subtotalHtml += `<div class="bg-white p-2 rounded border border-slate-200 shadow-sm text-xs"><div class="font-bold text-slate-700">${oName}</div><div class="text-slate-500 mt-1">${s} Matcher | ${v} V | ${o} O | ${f} F | ${gm}-${im} | <span class="font-bold text-blue-800">${p} P</span></div></div>`;
                });
                document.getElementById('team-modal-subtotals').innerHTML = subtotalHtml;
                document.getElementById('team-modal-subtotals').classList.remove('hidden');
            } else {
                document.getElementById('team-modal-subtotals').classList.add('hidden');
            }
            
            let ts=0, tv=0, to=0, tf=0, tgm=0, tim=0, tp=0;
            let listHtml = '';
            teamMatches.forEach(m => {
                let isH = getMappedTeamName(m.home_team) === mappedName;
                ts++;
                let hg = m.score.home_total, ag = m.score.away_total;
                tgm += isH ? hg : ag; tim += isH ? ag : hg;
                if (hg > ag) { if(isH) {tv++; tp+=3;} else {tf++;} }
                else if (ag > hg) { if(!isH) {tv++; tp+=3;} else {tf++;} }
                else { to++; tp++; }
                
                const scClass = "font-bold text-slate-800 bg-slate-100 px-2 py-1 rounded border border-slate-200";
                listHtml += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100"><div class="text-[10px] uppercase font-bold text-blue-900">${m.date.substring(0,4)}</div><div class="text-xs text-slate-500">${m.phase}</div></td>
                        <td class="p-3 border-t border-slate-100"><div class="text-xs text-slate-500">${m.date}</div></td>
                        <td class="p-3 border-t border-slate-100 text-right ${isH ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="${scClass}">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 ${!isH ? 'font-black text-blue-900' : 'font-medium text-slate-500'}">${m.away_team}</td>
                    </tr>`;
            });
            
            document.getElementById('team-modal-summary').innerHTML = `<div class="bg-blue-50 p-3 rounded-lg border border-blue-200 text-sm flex justify-between items-center"><span class="font-bold text-blue-900">Total VM-Historik</span><span class="font-medium text-blue-800">${ts} M | ${tv} V | ${to} O | ${tf} F | ${tgm}-${tim} | <span class="font-black">${tp} P</span></span></div>`;
            document.getElementById('team-modal-matches-list').innerHTML = listHtml;
            document.getElementById('team-modal').classList.remove('hidden');
        }

        function closeTeamModal() { document.getElementById('team-modal').classList.add('hidden'); }

        function openStreakModal(team, type, start, end, val) {
            let titles = {
                'W': 'Segersvit', 'U': 'Obesegrade', 'L': 'Förlustsvit', 'winless': 'Utan Seger',
                'CS': 'Hållna Nollor i rad', 'drought': 'Måltorka i rad', 'scoring': 'Matcher med Mål i rad', 'conceding': 'Insläppta mål i rad'
            };
            document.getElementById('streak-modal-title').innerText = `${team}: ${val} matcher`;
            document.getElementById('streak-modal-subtitle').innerText = `${titles[type]} (${start} - ${end})`;
            
            let sMatches = Object.values(db.matches).filter(m => 
                m.score.home_total !== null && 
                (getMappedTeamName(m.home_team) === team || getMappedTeamName(m.away_team) === team) &&
                m.date >= start && m.date <= end
            );
            sMatches.sort((a,b) => new Date(a.date) - new Date(b.date));
            
            let html = '';
            sMatches.forEach(m => {
                let isH = getMappedTeamName(m.home_team) === team;
                const scClass = "font-bold text-slate-800 bg-slate-100 px-2 py-1 rounded border border-slate-200";
                html += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-amber-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100"><div class="text-[10px] uppercase font-bold text-amber-900">${m.date.substring(0,4)}</div><div class="text-xs text-slate-500">${m.phase}</div></td>
                        <td class="p-3 border-t border-slate-100"><div class="text-xs text-slate-500">${m.date}</div></td>
                        <td class="p-3 border-t border-slate-100 text-right ${isH ? 'font-black text-amber-900' : 'font-medium text-slate-500'}">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center"><span class="${scClass}">${formatScore(m)}</span></td>
                        <td class="p-3 border-t border-slate-100 ${!isH ? 'font-black text-amber-900' : 'font-medium text-slate-500'}">${m.away_team}</td>
                    </tr>`;
            });
            document.getElementById('streak-modal-matches-list').innerHTML = html;
            document.getElementById('streak-modal').classList.remove('hidden');
        }

        function closeStreakModal() { document.getElementById('streak-modal').classList.add('hidden'); }

        // =========================================================
        // HUVUD-MATCHMODALEN (DEN DETALJERADE)
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
            if (m.score.home_ft !== null && m.score.away_ft !== null) {
                if (m.score.home_et !== null || m.score.home_total !== m.score.home_ft || m.score.away_total !== m.score.away_ft) {
                     detailsHtml += ` &bull; Efter full tid: ${m.score.home_ft}-${m.score.away_ft}`;
                }
            } else if (m.score.home_et !== null) {
                detailsHtml += ` &bull; Efter full tid: ${m.score.home_et}-${m.score.away_et}`;
            }
            if (m.score.home_pen !== null) detailsHtml += ` &bull; Straffar: ${m.score.home_pen}-${m.score.away_pen}`;
            document.getElementById('modal-score-details').innerHTML = detailsHtml;

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
            m.events.cards.forEach(c => { eventsArray.push({min: parseInt(c.minute) || 999, raw_min: c.minute, text: `<span class="card-red"></span> ${formatName(c.player)}`, team: m.home_team}); });
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
            } else eventsContainer.innerHTML = '<p class="text-center text-slate-400 text-sm italic">Inga specifika mål- eller kortuppgifter registrerade.</p>';

            const penContainerBox = document.getElementById('modal-penalties-container'), penContainer = document.getElementById('modal-penalties');
            if (m.events.penalties && m.events.penalties.length > 0) {
                penContainerBox.classList.remove('hidden');
                let homePens = m.events.penalties.filter(p => p.team === m.home_team).sort((a, b) => a.penalty_nr - b.penalty_nr);
                let awayPens = m.events.penalties.filter(p => p.team === m.away_team).sort((a, b) => a.penalty_nr - b.penalty_nr);
                const buildPens = (pens, isHome) => {
                    let p_html = `<div class="${isHome ? '' : 'text-right'}"><ul class="space-y-1">`;
                    pens.forEach(p => {
                        let outcomeText = p.outcome ? String(p.outcome).trim() : ''; let outcomeLower = outcomeText.toLowerCase();
                        let isGoal = !outcomeLower.includes('miss') && outcomeText !== ''; 
                        let icon = isGoal ? '<span class="pen-goal text-lg leading-none align-middle">✓</span>' : '<span class="pen-miss text-lg leading-none align-middle">✗</span>';
                        let outcomeDisplay = '';
                        if (outcomeLower !== 'mål' && outcomeLower !== 'miss' && outcomeLower !== 'ja' && outcomeLower !== '1' && outcomeText !== '') { outcomeDisplay = ` <span class="text-xs font-bold text-slate-500">${outcomeText}</span>`; }
                        let nrVal = p.penalty_nr; let hasNr = nrVal !== null && nrVal !== undefined && nrVal !== "" && String(nrVal) !== "null";
                        let leftText = isHome ? (hasNr ? `${nrVal}. ` : '') + icon + outcomeDisplay : formatName(p.player);
                        let rightText = isHome ? formatName(p.player) : outcomeDisplay + ' ' + icon + (hasNr ? ` <span class="text-xs text-slate-400">(${nrVal})</span>` : '');
                        p_html += `<li class="border-b border-slate-100 pb-1 last:border-0">${leftText} ${rightText}</li>`;
                    });
                    return p_html + '</ul></div>';
                };
                penContainer.innerHTML = buildPens(homePens, true) + buildPens(awayPens, false);
            } else penContainerBox.classList.add('hidden');

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
                    
                    let rcMinStr = p.red_card_minute ? `<span class="text-[10px] text-red-600 font-bold ml-0.5">${p.red_card_minute}'</span>` : '';
                    let goalStr = p.goals > 0 ? `<span class="ml-1.5 tracking-tighter text-[11px]">${'⚽'.repeat(p.goals)}</span>` : '';
                    
                    if (cardStr.includes('v') && cardStr.includes('utv')) cardIcon = `<span class="card-yellow"></span><span class="card-red"></span>${rcMinStr}`;
                    else if (cardStr.includes('utv')) cardIcon = `<span class="card-red"></span>${rcMinStr}`;
                    else if (cardStr.includes('v')) cardIcon = `<span class="card-yellow"></span>`;
                    
                    if (subStr) eventMin = `<span class="text-xs text-slate-400 ml-1">(${subStr})</span>`;
                    const nrText = p.shirt_nr && p.shirt_nr !== 'null' ? `<span class="inline-block w-6 font-bold text-slate-400 text-xs">${p.shirt_nr}.</span>` : `<span class="inline-block w-6 text-slate-300">-</span>`;
                    
                    lHtml += `<li class="py-1 border-b border-slate-50 last:border-0 flex items-center">${nrText} <span class="${subStr.includes('in') ? 'text-slate-600' : 'font-medium'}">${formatName(p.name)}</span>${goalStr}${capIcon}${subIcon}${cardIcon} ${eventMin}</li>`;
                });
                el.innerHTML = lHtml;
            };
            document.getElementById('modal-lineup-home-title').innerText = m.home_team; document.getElementById('modal-lineup-away-title').innerText = m.away_team;
            renderLineup(m.events.lineups.home, 'modal-lineup-home'); renderLineup(m.events.lineups.away, 'modal-lineup-away');
            document.getElementById('modal-coach-home').innerText = formatName(safeText(m.coaches.home)); document.getElementById('modal-coach-away').innerText = formatName(safeText(m.coaches.away));
            document.getElementById('match-modal').classList.remove('hidden');
        }

        function closeModal() { document.getElementById('match-modal').classList.add('hidden'); }
        
        function renderAdminWarnings() {
            const container = document.getElementById('admin-list-container'); const badge = document.getElementById('admin-badge');
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

        window.onload = () => { populateYearFilter(); renderTournaments(); renderMatches(); renderAdminWarnings(); };
    </script>
</body>
</html>
"""

    final_html = html_template.replace("__JSON_DATA_PLACEHOLDER__", json_str)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    print(f"✅ Dashboard framgångsrikt uppgraderad till version med Turneringsvyer och Matrix!")

if __name__ == "__main__":
    build_dashboard()