// ==========================================
// Kalkylator Motor 2035 - Kärnlogik & Databearbetning
// ==========================================

// --- GLOBALT FELHANTERINGSSYSTEM ---
window.addEventListener('error', function(event) {
    const ds = document.getElementById('dataStatus');
    if (ds) {
        ds.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <b>Systemkrasch:</b> ${event.message} (Rad ${event.lineno})`;
        ds.className = "p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-bold";
    }
    console.error("Globalt fel:", event.error);
});

window.addEventListener('unhandledrejection', function(event) {
    const ds = document.getElementById('dataStatus');
    if (ds) {
        ds.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <b>Laddningsfel:</b> ${event.reason}`;
        ds.className = "p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-bold";
    }
    console.error("Promise-fel:", event.reason);
});

// --- LÄNKA HUVUDREGLAGE TILL ÅLDERSREGLAGE ---
document.addEventListener('input', function(e) {
    if (e.target && e.target.id === 'syssGradSlider') {
        const val = parseFloat(e.target.value) || 0;
        const valEl = document.getElementById('syssGradVal');
        if (valEl) valEl.innerText = (val > 0 ? '+' : '') + val + '%-enh';
        
        document.querySelectorAll('input[id^="syssAge"]').forEach(sl => {
            sl.value = val;
            const slVal = document.getElementById('val_' + sl.id);
            if (slVal) slVal.innerText = (val > 0 ? '+' : '') + val;
        });
        
        if (typeof window.runSimulation === 'function') window.runSimulation();
    }
});

// --- GLOBALA VARIABLER ---
window.PROGNOS_SLUTAR = 2035;
window.syssBasdata = {};
window.syssConfig = {};
window.popData = []; 
window.customPopData = null; 
window.useCustomPop = false; 

window.histDataStore = {}; 
window.progDataStore = {}; 
window.savedProjectedData = null; 
window.currentNaringSkala = 1.0; 

window.trendChartInstance = null;
window.globalChartVisibility = {}; 
window.allYears = [];
window.histYearsGlobal = [];
window.baseYear = 0; 

window.avgAnnualStudents = 3500; 
window.annualStudentsMap = {}; 
window.avgAnnualCivIng = 0;
window.annualCivIngMap = {};
window.useSpecificCivIng = false;

window.globalMigrantEmploymentRate = 0.50; 
window.takEffektMaxSyss = 100; 

window.takEffekter = {
    maxSyssGrad: 85.0, minArbetsloshet: 3.5, karnaLangtidsarbetslosa: 3.0, maxInpendlingsandel: 25.0, maxSyssGradAldre: 25.0, kapacitetstakInfrastruktur: 30000, studentAbsorptionsTak: 50
};

window.scenarioSettings = {
    base: { jobGrowth: 5, syssGrad: 0.5, student: 2, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10, naringSkala: 1.0 },
    high: { jobGrowth: 15, syssGrad: 2.0, student: 10, inpendling: 10, utpendling: 5, distans: 10, region: 15, migrantSyss: 15, naringSkala: 1.5 },
    low: { jobGrowth: -5, syssGrad: -1.0, student: -2, inpendling: -5, utpendling: -2, distans: 0, region: 0, migrantSyss: 5, naringSkala: 0.5 },
    stagnant: { jobGrowth: 0, syssGrad: 0, student: 0, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10, naringSkala: 0.0 }
};

window.SHOW_Y_GRACE_UI = true; 
window.DEFAULT_Y_GRACE = '20%';

window.infoTexts = {
    'pop_source': { 
        title: '1. Källa (Befolkningskopplingar)', 
        content: `<p>Här väljer du vilken befolkningsframskrivning som ska ligga till grund för det lokala utbudet av arbetskraft.</p>
                  <ul class="list-disc pl-5 space-y-2">
                  <li><b>Fryst (Statisk befolkning):</b> Låser den arbetsföra befolkningen vid basårets nivå. Används för att isolera effekten av enbart jobbtillväxt.</li>
                  <li><b>Officiell (Styrfil):</b> Läser in kommunens officiella prognos. <strong>Här används ett 10-årigt viktat historiskt genomsnitt</strong> som utgångspunkt för sysselsättningsgraderna för att säkerställa ett stabilt och trendjusterat startläge. Sysselsättningsgraden viktas även mot faktiska åldersgrupper.</li>
                  <li><b>Anpassad (Prognoskalkylatorn):</b> Om du har skapat ett eget demografiskt scenario i "Prognoskalkylatorn" och klickat på "Skicka", dyker det upp här.</li></ul>` 
    },
    'sim_mode': { 
        title: '2. Läge (Geografisk Avgränsning)', 
        content: `<p>Välj huruvida Linköping ska betraktas som en sluten eller öppen arbetsmarknadsregion.</p>
                  <ul class="list-disc pl-5 space-y-2">
                  <li><b>Fullständig:</b> Inkluderar all pendling. Detta är det mest realistiska läget.</li>
                  <li><b>Endast Lokal:</b> Kapar bort pendlingsnettot helt från beräkningen. Perfekt om du vill se hur robust den "egna" invånarpoolen är.</li></ul>` 
    },
    'kausalitet': { 
        title: '3. Kausalitet (Jämviktsmodell)', 
        content: `<p>Hur ska kalkylatorn hantera lokala obalanser mellan utbud och efterfrågan?</p>
                  <ul class="list-disc pl-5 space-y-2">
                  <li><b>Analytisk:</b> Modellen låter gapet mellan jobb och invånare stå öppet (visas som rött i diagrammen). Det är upp till dig att stänga det via reglagen.</li>
                  <li><b>Dynamisk Jämvikt:</b> Modellen fyller gapet automatiskt! Om företagen växer räknar motorn omedelbart ut hur mycket "inducerad befolkning" som måste flytta in, och lägger till dessa i grafer och tabeller.</li></ul>` 
    },
    'scenarios': { 
        title: 'Snabbscenarier', 
        content: `<p>Dessa knappar laddar in en "förinställd korg" av värden för alla reglage, till exempel vad som definieras som Hög eller Låg tillväxt.</p><p>Själva värdena bakom knapparna styr du i Excel-filens flik <em>Scenarier</em>. Om du i fliken <em>Tillväxt</em> har specificerat värden för enskilda åldersklasser laddas även de in automatiskt.</p>` 
    },
    'demografi': { 
        title: 'Lokal Tillväxt & Utbud', 
        content: `<p>Här skapar du dynamiken i arbetsmarknaden.</p>
                  <ul class="list-disc pl-5 space-y-2">
                  <li><b>Lokal Jobbtillväxt:</b> Företagens rekryteringsbehov över hela perioden (0-100%). Driver Efterfrågan uppåt.</li>
                  <li><b>Sysselsättningsgrad:</b> Hur stor andel av Linköpingsborna som arbetar. En ökning här fyller lokala jobb med lokal kompetens (ökar Utbudet). Kalkylatorn tillämpar en "Catch-up effekt" där underrepresenterade grupper (kvinnor och utrikes födda) växer snabbare än snittet.</li>
                  <li><b>Kvarstannandegrad LiU:</b> Att simulera ett tillskott av nya akademiker som väljer att stanna i kommunen efter examen.</li></ul>` 
    },
    'inflyttare': { 
        title: 'Inflyttares Sysselsättningsgrad', 
        content: `<p>Detta reglage påverkar inte arbetsmarknadsdiagrammen, utan korrigerar endast nyckeltalet <b>Befolkning (Ny)</b>.</p><p>SCB mäter sysselsättning året <i>innan</i> flytt. Genom att dra upp detta reglage (+10%) korrigerar du för mörkertalet av inflyttare som flyttar in specifikt för att börja ett jobb. Ju högre andel som jobbar, desto färre bostäder behöver byggas för att stänga ett kompetensgap.</p>` 
    },
    'geografi': { 
        title: 'Pendling & Geografi', 
        content: `<p>Här kan du påverka det externa arbetskraftsutbudet.</p>
                  <ul class="list-disc pl-5 space-y-2">
                  <li><b>Typ av förändring:</b> Välj mellan % eller absoluta tal (antal personer) för pendlingsreglagen.</li>
                  <li><b>Regionförstoring:</b> En tyngdkraftsmodell. Genom att dra ner restiden (ex. Ostlänken) räknar modellen ut hur många tusen kransinvånare som plötsligt hamnar inom pendlingströskeln för ett jobb i Linköping.</li></ul>` 
    },
    'shocker': { 
        title: 'Näringslivsjustering & Branschglidning', 
        content: `<p>Näringslivets strukturomvandling styrs via fliken <em>Näringslivsjustering</em> i Excel, och skalanivån (hur stor genomslaget är) styrs via parametern <em>Näringslivsjustering_skala</em> i scenariefliken.</p><p><b>Branschglidning:</b> Systemet är förberett för att tillämpa "kannibalisering" mellan branscher. Om en bransch växer snabbt kan den framöver dra till sig utbud (personal) från andra definierade branscher enligt styrfilen.</p>` 
    },
    'diagram': { 
        title: 'Utvecklingsdiagram & Analys', 
        content: `<p>I rullistan kan du djupdyka i arbetsmarknaden (Utbildningsnivå, Kön, Ursprung, Bransch). Använd kryssrutorna för att få grafen att utgå från 0 (mer visuell korrekthet) eller för att dela y-axeln på vänster/höger sida för lättare jämförelse mellan stora och små volymer.</p>` 
    },
    'befolkning': { 
        title: 'Demografisk Effekt (Befolkningsbehov)', 
        content: `<p>Visar hur mycket befolkning (vuxna och barn) som behöver flytta in för att täcka det omatchade rekryteringsgapet.</p>` 
    }
};

// --- HJÄLPFUNKTIONER ---
window.formatNumber = function(num, decimals = 0) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    return Number(num).toLocaleString('sv-SE', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
};

window.extractYear = function(row) {
    if (row['År'] !== undefined) return parseInt(row['År']);
    if (row['år'] !== undefined) return parseInt(row['år']);
    if (row['ÅR'] !== undefined) return parseInt(row['ÅR']);
    return null;
};

window.getKon = function(r) {
    for (let k in r) {
        if (k.toLowerCase().trim() === 'kön') return String(r[k]).trim().toLowerCase();
    }
    return null;
};

window.getRowTotal = function(r) {
    if (r['Totalt 16-74 år'] != null) return parseFloat(r['Totalt 16-74 år']);
    if (r['Totalt 16-74'] != null) return parseFloat(r['Totalt 16-74']);
    if (r['Totalt'] != null) return parseFloat(r['Totalt']);
    if (r['Samtliga'] != null) return parseFloat(r['Samtliga']);
    let sum = 0;
    Object.keys(r).forEach(k => {
        if (k.match(/\d+/) && !k.toLowerCase().includes('totalt') && !['år','kön','sektor','utbildningsnivå','bransch'].includes(k.toLowerCase())) {
            sum += parseFloat(r[k]) || 0;
        }
    });
    return sum;
};

window.showInfo = function(topicKey) {
    const data = window.infoTexts[topicKey];
    if(data) {
        document.getElementById('infoModalTitle').innerText = data.title;
        document.getElementById('infoModalContent').innerHTML = data.content;
        document.getElementById('infoModal').classList.remove('hidden');
    }
};

window.closeInfoModal = function() { 
    document.getElementById('infoModal').classList.add('hidden'); 
};

window.checkSharedScenario = function() {
    const popSelect = document.getElementById('popSource');
    let hasOfficial = false;
    if (window.syssConfig['Officiell_befolkningsprognos'] && window.syssConfig['Officiell_befolkningsprognos'].length > 0) {
        popSelect.add(new Option("Officiell (Styrfil)", "officiell"));
        hasOfficial = true;
    }
    try {
        const shared = localStorage.getItem('linkoping_shared_pop_scenario');
        if (shared) {
            window.customPopData = JSON.parse(shared);
            popSelect.add(new Option("Anpassad (Prognoskalkylatorn)", "custom"));
            popSelect.value = "custom";
            const btn = document.getElementById('clearCustomBtn');
            if (btn) btn.classList.remove('hidden');
            window.useCustomPop = true;
        } else if (hasOfficial) {
            popSelect.value = "officiell";
        }
    } catch(e) { console.error("Kunde inte läsa in anpassat scenario", e); }
    window.updatePopSourceDesc();
};

window.updatePopSourceDesc = function() {
    const val = document.getElementById('popSource').value;
    window.useCustomPop = (val === 'custom');
};

window.clearCustomPop = function() {
    localStorage.removeItem('linkoping_shared_pop_scenario');
    window.customPopData = null; window.useCustomPop = false;
    const btn = document.getElementById('clearCustomBtn');
    if (btn) btn.classList.add('hidden');
    const popSelect = document.getElementById('popSource');
    for (let i=0; i<popSelect.options.length; i++) { if (popSelect.options[i].value === 'custom') { popSelect.remove(i); break; } }
    popSelect.value = (window.syssConfig['Officiell_befolkningsprognos']) ? "officiell" : "fryst";
    window.updatePopSourceDesc(); window.runSimulation();
};

window.calculateMigrantEmploymentRate = function() {
    let totalInf = 0; let workingInf = 0;
    const migrantData = window.syssConfig['Andel_förvarb_inflytt_över_län'];
    let rateCol = null;
    if (migrantData && migrantData.length > 0) {
        const keys = Object.keys(migrantData[0]);
        rateCol = keys.find(k => k.includes('Förvärvsarbetande_Totalt_In_Snitt')) || keys.find(k => k.includes('Förvärvsarbetande_Totalt_In_2024')) || keys.find(k => k.includes('Förvärvsarbetande'));
    }
    if (window.popData && window.popData.length > 0 && rateCol) {
        let bYearData = window.popData.filter(r => String(r.tid).trim() === String(window.baseYear) && !String(r.ålder).includes('Totalt'));
        if (bYearData.length === 0) {
             const aYears = [...new Set(window.popData.map(r => parseInt(String(r.tid).substring(0,4))))].filter(y => !isNaN(y)).sort();
             if(aYears.length > 0) bYearData = window.popData.filter(r => String(r.tid).trim() === String(aYears[aYears.length - 1]) && !String(r.ålder).includes('Totalt'));
        }
        for (let age = 0; age <= 100; age++) {
            let inflyttThisAge = 0;
            bYearData.forEach(r => { 
                const ageMatch = String(r.ålder).match(/\d+/); 
                if (ageMatch && parseInt(ageMatch[0]) === age) { inflyttThisAge += (r.Inflyttade || 0); } 
            });
            let rate = 0;
            const mRow = migrantData.find(r => { 
                const mMatch = String(r['Ålder']).match(/\d+/); 
                return mMatch && parseInt(mMatch[0]) === age; 
            });
            if (mRow && mRow[rateCol]) rate = parseFloat(mRow[rateCol]) / 100;
            totalInf += inflyttThisAge; workingInf += inflyttThisAge * rate;
        }
    }
    window.globalMigrantEmploymentRate = (totalInf > 0 && workingInf > 0) ? workingInf / totalInf : 0.50; 
};

window.getPopForYear = function(dataset, year) {
    let pop = 0;
    let records = dataset.filter(r => String(r.tid).trim() === `${year} (Prognos)`);
    if (records.length === 0) records = dataset.filter(r => String(r.tid).trim() === String(year));
    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
    records.forEach(r => {
        if (!String(r.ålder).toLowerCase().includes('totalt')) {
            if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
            const ageMatch = String(r.ålder).match(/\d+/);
            if (ageMatch) { const age = parseInt(ageMatch[0]); if (age >= 16 && age <= 74) { pop += (r.Befolkning || 0); } }
        }
    });
    return pop;
};

window.getScbVal = function(row, searchTerms, excludeTerms=[]) {
    if (!row) return null;
    for(let key of Object.keys(row)) {
        let k = key.toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
        if (searchTerms.some(term => k.includes(term)) && !excludeTerms.some(term => k.includes(term))) {
            let v = parseFloat(row[key]);
            if(!isNaN(v)) return v;
        }
    }
    return null;
};

window.extractOriginPop = function(datasetPartialName, targetYear) {
    let inr = 0, utr = 0, found = false;
    let dsKey = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes(datasetPartialName.toLowerCase()));
    const ds = dsKey ? window.syssBasdata[dsKey] : [];
    const records = ds.filter(r => window.extractYear(r) == targetYear);
    if (records.length === 0) return null;
    let hasTotalRow = records.some(r => window.getKon(r) === 'totalt' || window.getKon(r) === 'samtliga');
    records.forEach(r => {
        let kon = window.getKon(r);
        if (kon && hasTotalRow && kon !== 'totalt' && kon !== 'samtliga') return; 
        let isUtr = false, isInr = false;
        for (let k in r) {
            if (typeof r[k] === 'string') {
                let valStr = r[k].toLowerCase();
                if (valStr.includes('utrikes') && !valStr.includes('inrikes')) isUtr = true;
                if (valStr.includes('inrikes') || valStr.includes('sverige')) isInr = true;
            }
        }
        if (isUtr || isInr) {
            found = true; let rowTot = window.getRowTotal(r);
            if (isUtr) utr += rowTot; if (isInr) inr += rowTot;
        } else {
            for (let k in r) {
                let kl = k.toLowerCase().replace(/_/g, ' ');
                if (kl.includes('utrikes')) { utr += parseFloat(r[k]) || 0; found = true; }
                if (kl.includes('inrikes') || kl.includes('sverige')) { inr += parseFloat(r[k]) || 0; found = true; }
            }
        }
    });
    return found ? { inr, utr } : null;
};

window.toggleSimMode = function() {
    const mode = document.getElementById('simMode').value;
    const geoPanel = document.getElementById('geoPanel');
    if (mode === 'local') { geoPanel.classList.add('opacity-40', 'pointer-events-none'); } 
    else { geoPanel.classList.remove('opacity-40', 'pointer-events-none'); }
    if(typeof window.updateDashboard === 'function') window.updateDashboard(true); 
};

// --- BORTTAGET: toggleShocks() ---
// Eftersom vi inte längre använder Etableringschocker-UI:t raderas den funktionen här.

window.updatePendlingUI = function() {
    const type = document.getElementById('pendlingType').value;
    const inSlider = document.getElementById('inpendlingSlider');
    const utSlider = document.getElementById('utpendlingSlider');
    if (type === 'pct') {
        inSlider.min = -50; inSlider.max = 50; inSlider.step = 1;
        utSlider.min = -50; utSlider.max = 50; utSlider.step = 1;
    } else {
        inSlider.min = -5000; inSlider.max = 5000; inSlider.step = 50;
        utSlider.min = -5000; utSlider.max = 5000; utSlider.step = 50;
    }
    window.updatePendlingValue('inpendlingSlider', 'inpendlingVal');
    window.updatePendlingValue('utpendlingSlider', 'utpendlingVal');
};

window.updatePendlingValue = function(sliderId, textId) {
    const val = document.getElementById(sliderId).value;
    const type = document.getElementById('pendlingType').value;
    const prefix = val > 0 ? '+' : '';
    const suffix = type === 'pct' ? '%' : ' pers';
    document.getElementById(textId).innerText = prefix + val + suffix;
};

window.toggleCivIng = function() {
    const container = document.getElementById('civIngContainer');
    const icon = document.getElementById('civIngToggleIcon');
    window.useSpecificCivIng = !window.useSpecificCivIng;
    if (window.useSpecificCivIng) {
        container.classList.remove('hidden');
        icon.classList.replace('fa-circle-plus', 'fa-circle-minus');
        icon.classList.replace('text-sky-600', 'text-red-500');
    } else {
        container.classList.add('hidden');
        icon.classList.replace('fa-circle-minus', 'fa-circle-plus');
        icon.classList.replace('text-red-500', 'text-sky-600');
        document.getElementById('civIngSlider').value = 0;
        document.getElementById('civIngVal').innerText = 'Baslinje';
    }
    if (typeof window.runSimulation === 'function') window.runSimulation();
};

window.toggleSaveScenario = function() {
    const saveBtn = document.getElementById('saveBtn');
    const startYearSelect = document.getElementById('startYearSelect');
    if (!window.savedProjectedData) {
        if (Object.keys(window.progDataStore).length === 0) { alert("Du måste köra en simulering först."); return; }
        window.savedProjectedData = JSON.parse(JSON.stringify(window.progDataStore));
        saveBtn.innerHTML = '<i class="fa-solid fa-times mr-1"></i> Rensa jämförelse';
        saveBtn.classList.replace('bg-indigo-100', 'bg-red-100');
        saveBtn.classList.replace('text-indigo-800', 'text-red-800');
        saveBtn.classList.replace('hover:bg-indigo-200', 'hover:bg-red-200');
        startYearSelect.classList.add('hidden'); 
    } else {
        window.savedProjectedData = null;
        saveBtn.innerHTML = '<i class="fa-solid fa-code-compare mr-1"></i> Jämför';
        saveBtn.classList.replace('bg-red-100', 'bg-indigo-100');
        saveBtn.classList.replace('text-red-800', 'text-indigo-800');
        saveBtn.classList.replace('hover:bg-red-200', 'hover:bg-indigo-200');
        startYearSelect.classList.remove('hidden'); 
    }
    if(typeof window.updateDashboard === 'function') window.updateDashboard(false);
};

window.setScenario = function(type) {
    const s = window.scenarioSettings[type];
    document.getElementById('jobGrowthSlider').value = s.jobGrowth || 0;
    document.getElementById('jobGrowthVal').innerText = (s.jobGrowth > 0 ? '+' : '') + (s.jobGrowth || 0) + '%';
    
    const syssGradSlider = document.getElementById('syssGradSlider');
    if (syssGradSlider) {
        syssGradSlider.value = s.syssGrad || 0;
        const event = new Event('input', { bubbles: true });
        syssGradSlider.dispatchEvent(event);
    }
    
    const ageLabelsArr = ['16-19','20-24','25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65-69','70-74'];
    ageLabelsArr.forEach(a => {
        let id = 'syssAge' + a.replace('-', '_');
        let el = document.getElementById(id);
        if (el) {
            let specVal = s[`syssAge_${a.replace('-','_')}`];
            el.value = (specVal !== undefined) ? specVal : (s.syssGrad || 0);
            let valEl = document.getElementById('val_' + id);
            if (valEl) valEl.innerText = (el.value > 0 ? '+' : '') + el.value;
        }
    });
    
    window.currentNaringSkala = s.naringSkala !== undefined ? s.naringSkala : 1.0;

    document.getElementById('studentSlider').value = s.student || 0;
    document.getElementById('studentVal').innerText = (s.student > 0 ? '+' : '') + (s.student || 0) + '%-enh';
    if(document.getElementById('migrantSyssSlider')) { document.getElementById('migrantSyssSlider').value = s.migrantSyss !== undefined ? s.migrantSyss : 10; document.getElementById('migrantSyssVal').innerText = (s.migrantSyss > 0 ? '+' : '') + (s.migrantSyss !== undefined ? s.migrantSyss : 10) + '%-enh'; }
    if(document.getElementById('civIngSlider')) { document.getElementById('civIngSlider').value = 0; document.getElementById('civIngVal').innerText = 'Baslinje'; }
    
    document.getElementById('pendlingType').value = 'pct';
    window.updatePendlingUI();
    document.getElementById('inpendlingSlider').value = s.inpendling || 0;
    window.updatePendlingValue('inpendlingSlider', 'inpendlingVal');
    document.getElementById('utpendlingSlider').value = s.utpendling || 0;
    window.updatePendlingValue('utpendlingSlider', 'utpendlingVal');
    document.getElementById('distansSlider').value = s.distans || 0;
    document.getElementById('distansVal').innerText = (s.distans > 0 ? '+' : '') + (s.distans || 0) + '%';
    document.getElementById('regionSlider').value = s.region || 0;
    document.getElementById('regionVal').innerText = (s.region == 0 || !s.region) ? 'Dagens nivå' : '+' + s.region + ' min';
    
    // Inga Etableringschocker att bocka ur!
    
    if (typeof window.runSimulation === 'function') window.runSimulation();
};

window.resetSimulation = function() {
    document.getElementById('simMode').value = 'full'; window.toggleSimMode();
    document.getElementById('jobGrowthSlider').value = 0; document.getElementById('jobGrowthVal').innerText = '+0%';
    
    const syssGradSlider = document.getElementById('syssGradSlider');
    if (syssGradSlider) {
        syssGradSlider.value = 0;
        const event = new Event('input', { bubbles: true });
        syssGradSlider.dispatchEvent(event);
    }
    
    window.currentNaringSkala = 1.0;

    document.getElementById('studentSlider').value = 0; document.getElementById('studentVal').innerText = 'Baslinje';
    if (window.useSpecificCivIng) window.toggleCivIng(); 
    document.getElementById('pendlingType').value = 'pct'; window.updatePendlingUI();
    document.getElementById('inpendlingSlider').value = 0; document.getElementById('inpendlingVal').innerText = '+0%';
    document.getElementById('utpendlingSlider').value = 0; document.getElementById('utpendlingVal').innerText = '+0%';
    document.getElementById('distansSlider').value = 0; document.getElementById('distansVal').innerText = 'Baslinje';
    document.getElementById('regionSlider').value = 0; document.getElementById('regionVal').innerText = 'Dagens nivå';
    
    window.progDataStore = {}; 
    window.savedProjectedData = null;
    
    const saveBtn = document.getElementById('saveBtn');
    if (saveBtn) {
        saveBtn.innerHTML = '<i class="fa-solid fa-code-compare mr-1"></i> Jämför';
        saveBtn.classList.remove('bg-red-100', 'text-red-800', 'hover:bg-red-200');
        saveBtn.classList.add('bg-indigo-100', 'text-indigo-800', 'hover:bg-indigo-200');
    }
    const startYearSelect = document.getElementById('startYearSelect');
    if(startYearSelect) startYearSelect.classList.remove('hidden');

    if(typeof window.buildDropdowns === 'function') window.buildDropdowns();
    if(typeof window.updateDashboard === 'function') window.updateDashboard(false);
};

// ==========================================
// SCB-HISTORIK & DATATVÄTT
// ==========================================
window.extractHistoricalData = function() {
    const dfTillagg = window.syssBasdata['Syss_tillägg'] || window.syssBasdata['Syss_tillagg'] || [];
    const dfSyssGrad = window.syssBasdata['Syssgrad'] || [];
    const dfBRP = window.syssBasdata['BRP'] || [];
    const dfPendling = window.syssBasdata['Pendling'] || [];
    const syssAlderData = window.syssBasdata['Syss_ålder'] || window.syssBasdata['Syss_alder'] || [];
    const nattAlderData = window.syssBasdata['Natt_ålder'] || window.syssBasdata['Natt_alder'] || [];
    
    const dsUtrKeySyssGrad = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes('syssgrad_utrikes') || k.toLowerCase().includes('syssgrad_bakgrund'));
    const lData = window.syssBasdata['Långtidsarbetslöshet'] || window.syssBasdata['Langtidsarbetsloshet'];
    const dsUtrKeyNatt = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes('natt_utrikes') || k.toLowerCase().includes('natt_bakgrund'));
    const dsUtrKeySyss = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes('syss_utrikes') || k.toLowerCase().includes('syss_bakgrund'));

    let years = new Set();
    dfTillagg.forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    dfSyssGrad.forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    dfBRP.forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    
    if(window.syssBasdata['Arbetslöshet']) window.syssBasdata['Arbetslöshet'].forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    if(lData) lData.forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    if(dsUtrKeyNatt) window.syssBasdata[dsUtrKeyNatt].forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    if(dsUtrKeySyss) window.syssBasdata[dsUtrKeySyss].forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    if(dsUtrKeySyssGrad) window.syssBasdata[dsUtrKeySyssGrad].forEach(r => { let y = window.extractYear(r); if(y) years.add(y); });
    
    const sortedYears = Array.from(years).filter(y => !isNaN(y)).sort((a,b)=>a-b);
    if (sortedYears.length === 0) return;

    window.histDataStore = {};
    let brpHistory = []; 
    let lastKnownBRP = null; 
    let lastKnownBRPYear = null;
    
    sortedYears.forEach(y => {
        let dagTotalt = null, nattTotalt = null, inpendlingTot = 0, utpendlingTot = 0, hasPendlingData = false;
        
        let d_man = null, d_kvinna = null;
        let dagRowM = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && window.getKon(r) === 'män');
        let dagRowK = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && window.getKon(r) === 'kvinnor');
        if (dagRowM) d_man = parseFloat(dagRowM['Totalt'] || dagRowM['Samtliga'] || 0);
        if (dagRowK) d_kvinna = parseFloat(dagRowK['Totalt'] || dagRowK['Samtliga'] || 0);

        let n_man = null, n_kvinna = null;
        let nattRowM = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && window.getKon(r) === 'män');
        let nattRowK = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && window.getKon(r) === 'kvinnor');
        if (nattRowM) n_man = parseFloat(nattRowM['Totalt'] || nattRowM['Samtliga'] || 0);
        if (nattRowK) n_kvinna = parseFloat(nattRowK['Totalt'] || nattRowK['Samtliga'] || 0);

        if (d_man == null || d_kvinna == null) {
            let m = 0, k = 0, found = false;
            syssAlderData.filter(r => window.extractYear(r) == y).forEach(r => {
                let kon = window.getKon(r);
                if (kon === 'män') { m += window.getRowTotal(r); found = true; }
                if (kon === 'kvinnor') { k += window.getRowTotal(r); found = true; }
            });
            if (found) { d_man = m; d_kvinna = k; }
        }
        if (n_man == null || n_kvinna == null) {
            let m = 0, k = 0, found = false;
            nattAlderData.filter(r => window.extractYear(r) == y).forEach(r => {
                let kon = window.getKon(r);
                if (kon === 'män') { m += window.getRowTotal(r); found = true; }
                if (kon === 'kvinnor') { k += window.getRowTotal(r); found = true; }
            });
            if (found) { n_man = m; n_kvinna = k; }
        }

        let dagRow = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && (window.getKon(r) === 'totalt' || window.getKon(r) === null));
        if (dagRow && dagRow['Totalt'] != null) dagTotalt = parseFloat(dagRow['Totalt']);
        else if (d_man != null && d_kvinna != null) dagTotalt = d_man + d_kvinna; 
        
        if (dagRow && dagRow['Pendling'] != null) {
            inpendlingTot = parseFloat(dagRow['Pendling']);
            hasPendlingData = true;
        }

        let nattRow = dfTillagg.find(r => window.extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && (window.getKon(r) === 'totalt' || window.getKon(r) === null));
        if (nattRow && nattRow['Totalt'] != null) nattTotalt = parseFloat(nattRow['Totalt']);
        else if (n_man != null && n_kvinna != null) nattTotalt = n_man + n_kvinna; 

        if (nattRow && nattRow['Pendling'] != null) {
            utpendlingTot = parseFloat(nattRow['Pendling']);
            hasPendlingData = true;
        }

        if (!hasPendlingData && dfPendling.length > 0) {
            let inRow = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && (window.getKon(r) === 'totalt' || window.getKon(r) === null));
            if (inRow && inRow['Totalt'] != null) { inpendlingTot = parseFloat(inRow['Totalt']); hasPendlingData = true; }
            else {
                let inM = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && window.getKon(r) === 'män');
                let inK = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && window.getKon(r) === 'kvinnor');
                if (inM || inK) { inpendlingTot = (inM ? parseFloat(inM['Totalt']) : 0) + (inK ? parseFloat(inK['Totalt']) : 0); hasPendlingData = true; }
            }

            let utRow = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && (window.getKon(r) === 'totalt' || window.getKon(r) === null));
            if (utRow && utRow['Totalt'] != null) { utpendlingTot = parseFloat(utRow['Totalt']); hasPendlingData = true; }
            else {
                let utM = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && window.getKon(r) === 'män');
                let utK = dfPendling.find(r => window.extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && window.getKon(r) === 'kvinnor');
                if (utM || utK) { utpendlingTot = (utM ? parseFloat(utM['Totalt']) : 0) + (utK ? parseFloat(utK['Totalt']) : 0); hasPendlingData = true; }
            }
        }

        let faktiskRate = null;
        let syssGradRow = dfSyssGrad.find(r => window.extractYear(r) == y && (window.getKon(r) === 'totalt' || window.getKon(r) === null));
        if (syssGradRow && syssGradRow['Totalt 20-64 år'] != null) faktiskRate = parseFloat(syssGradRow['Totalt 20-64 år']);
        
        let syssGradTotObj = dfSyssGrad.find(r => window.extractYear(r) == y && (!window.getKon(r) || window.getKon(r) === 'totalt'));
        let syssGradMObj = dfSyssGrad.find(r => window.extractYear(r) == y && window.getKon(r) === 'män');
        let syssGradKObj = dfSyssGrad.find(r => window.extractYear(r) == y && window.getKon(r) === 'kvinnor');

        let syss_in_tot = null, syss_ut_tot = null;
        if(dsUtrKeySyssGrad && window.syssBasdata[dsUtrKeySyssGrad]) {
            let suRow = window.syssBasdata[dsUtrKeySyssGrad].find(r => window.extractYear(r) == y);
            if (suRow) {
                syss_in_tot = window.getScbVal(suRow, ['inrikes född 20-64 år totalt', 'inrikes födda', 'inrikes', 'inrikes född'], ['män', 'kvinnor']);
                syss_ut_tot = window.getScbVal(suRow, ['utrikes född 20-64 år totalt', 'utrikes födda', 'utrikes', 'utrikes född'], ['män', 'kvinnor']);
            }
        }

        let brpPerSyss = null;
        let brpRow = dfBRP.find(r => window.extractYear(r) == y);
        if (brpRow && brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)'] != null) {
            brpPerSyss = parseFloat(brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)']);
            lastKnownBRP = brpPerSyss; lastKnownBRPYear = y; brpHistory.push({year: y, val: brpPerSyss});
        }

        let arbetsloshetPct = null, arb_inrikes = null, arb_utrikes = null, arb_man = null, arb_kvinna = null;
        let arb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null };
        
        if(window.syssBasdata['Arbetslöshet']) {
            let arbRow = window.syssBasdata['Arbetslöshet'].find(r => window.extractYear(r) == y);
            if(arbRow) {
                let pctKeysArb = Object.keys(arbRow).filter(k => String(k).toLowerCase().includes('%') || String(k).toLowerCase().includes('andel'));
                if(pctKeysArb.length > 0) arbetsloshetPct = parseFloat(arbRow[pctKeysArb[0]]);
                
                let inKeyArb = pctKeysArb.find(k => k.toLowerCase().includes('inrikes'));
                let utKeyArb = pctKeysArb.find(k => k.toLowerCase().includes('utrikes'));
                if(inKeyArb) arb_inrikes = parseFloat(arbRow[inKeyArb]);
                if(utKeyArb) arb_utrikes = parseFloat(arbRow[utKeyArb]);

                let mKeyArb = pctKeysArb.find(k => { const kl = k.toLowerCase(); return (kl.includes('män') || kl.includes('man')) && !kl.includes('kvinna'); });
                let kKeyArb = pctKeysArb.find(k => k.toLowerCase().includes('kvinnor') || k.toLowerCase().includes('kvinna'));
                if(mKeyArb) arb_man = parseFloat(arbRow[mKeyArb]);
                if(kKeyArb) arb_kvinna = parseFloat(arbRow[kKeyArb]);
                
                arb.tot_pct = window.getScbVal(arbRow, ['totalt andel av arbetskraften', 'andel av arbetskraften totalt', 'totalt %', '%'], ['inskrivna']);
                arb.m_pct = window.getScbVal(arbRow, ['män andel av arbetskraften', 'män andel', 'män %'], ['inskrivna']);
                arb.k_pct = window.getScbVal(arbRow, ['kvinnor andel av arbetskraften', 'kvinnor andel', 'kvinnor %'], ['inskrivna']);
                arb.in_pct = window.getScbVal(arbRow, ['inrikes födda andel av arbetskraften', 'inrikes andel', 'inrikes %', 'inrikes födda %'], ['inskrivna']);
                arb.ut_pct = window.getScbVal(arbRow, ['utrikes födda andel av arbetskraften', 'utrikes andel', 'utrikes %', 'utrikes födda %'], ['inskrivna']);
                if (arb.m_pct == null) {
                    let rM = window.syssBasdata['Arbetslöshet'].find(r => window.extractYear(r) == y && window.getKon(r) === 'män');
                    arb.m_pct = window.getScbVal(rM, ['totalt andel', '%', 'andel'], ['inskrivna']);
                }
                if (arb.k_pct == null) {
                    let rK = window.syssBasdata['Arbetslöshet'].find(r => window.extractYear(r) == y && window.getKon(r) === 'kvinnor');
                    arb.k_pct = window.getScbVal(rK, ['totalt andel', '%', 'andel'], ['inskrivna']);
                }
                arb.tot_num = window.getScbVal(arbRow, ['totalt', 'samtliga', 'antal', 'värde'], ['andel', '%', 'inrikes', 'utrikes', 'män', 'kvinnor']);
                arb.m_num = window.getScbVal(arbRow, ['män', 'man'], ['andel', '%']);
                arb.k_num = window.getScbVal(arbRow, ['kvinnor', 'kvinna'], ['andel', '%']);
                arb.in_num = window.getScbVal(arbRow, ['inrikes', 'inrikes född'], ['andel', '%']);
                arb.ut_num = window.getScbVal(arbRow, ['utrikes', 'utrikes född'], ['andel', '%']);
            }
        }

        let langtidsPct = null, larb_inrikes = null, larb_utrikes = null, larb_man = null, larb_kvinna = null;
        let larb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null, tot_insk:null, m_insk:null, k_insk:null, in_insk:null, ut_insk:null };
        
        if (lData) {
            let lRow = lData.find(r => window.extractYear(r) == y);
            if(lRow) {
                let pctKeysLarb = Object.keys(lRow).filter(k => String(k).toLowerCase().includes('%') || String(k).toLowerCase().includes('andel'));
                if(pctKeysLarb.length > 0) langtidsPct = parseFloat(lRow[pctKeysLarb[0]]);
                
                let inKeyLarb = pctKeysLarb.find(k => k.toLowerCase().includes('inrikes'));
                let utKeyLarb = pctKeysLarb.find(k => k.toLowerCase().includes('utrikes'));
                if(inKeyLarb) larb_inrikes = parseFloat(lRow[inKeyLarb]);
                if(utKeyLarb) larb_utrikes = parseFloat(lRow[utKeyLarb]);

                let mKeyLarb = pctKeysLarb.find(k => { const kl = k.toLowerCase(); return (kl.includes('män') || kl.includes('man')) && !kl.includes('kvinna'); });
                let kKeyLarb = pctKeysLarb.find(k => k.toLowerCase().includes('kvinnor') || k.toLowerCase().includes('kvinna'));
                if(mKeyLarb) larb_man = parseFloat(lRow[mKeyLarb]);
                if(kKeyLarb) larb_kvinna = parseFloat(lRow[kKeyLarb]);
                
                larb.tot_pct = window.getScbVal(lRow, ['totalt 16-65 år andel av arbetskraften', 'andel av arbetskraften totalt', 'totalt andel']);
                larb.m_pct = window.getScbVal(lRow, ['män 16-65 år andel av arbetskraften', 'män andel av arbetskraften']);
                larb.k_pct = window.getScbVal(lRow, ['kvinnor 16-65 år andel av arbetskraften', 'kvinnor andel av arbetskraften', 'kvinnor 16-65 år andel av arbetskraften']);
                larb.in_pct = window.getScbVal(lRow, ['inrikes födda 16-65 år andel av arbetskraften', 'inrikes födda 16-65 år andel av arbetskraften']);
                larb.ut_pct = window.getScbVal(lRow, ['utrikes födda 16-65 år andel av arbetskraften', 'utrikes födda 16-65 år andel av arbetskraften']);

                larb.tot_insk = window.getScbVal(lRow, ['totalt 16-65 år andel av inskrivna', 'andel av inskrivna totalt']);
                larb.m_insk = window.getScbVal(lRow, ['män 16-65 år andel av inskrivna', 'män andel av inskrivna']);
                larb.k_insk = window.getScbVal(lRow, ['kvinnor 16-65 år andel av inskrivna', 'kvinnor andel av inskrivna', 'kvinnor 16-65 år andel av inskrivna']);
                larb.in_insk = window.getScbVal(lRow, ['inrikes födda 16-65 år andel av inskrivna', 'inrikes födda 16-65 år andel av inskrivna']);
                larb.ut_insk = window.getScbVal(lRow, ['utrikes födda 16-65 år andel av inskrivna', 'utrikes födda 16-65 år andel av inskrivna']);
                
                if (larb.m_pct == null || larb.m_insk == null) {
                    let rM = lData.find(r => window.extractYear(r) == y && window.getKon(r) === 'män');
                    larb.m_pct = window.getScbVal(rM, ['andel av arbetskraften', 'totalt andel']);
                    larb.m_insk = window.getScbVal(rM, ['andel av inskrivna']);
                }
                if (larb.k_pct == null || larb.k_insk == null) {
                    let rK = lData.find(r => window.extractYear(r) == y && window.getKon(r) === 'kvinnor');
                    larb.k_pct = window.getScbVal(rK, ['andel av arbetskraften', 'totalt andel']);
                    larb.k_insk = window.getScbVal(rK, ['andel av inskrivna']);
                }

                larb.tot_num = window.getScbVal(lRow, ['totalt', 'samtliga', 'antal', 'värde'], ['andel', '%', 'inrikes', 'utrikes', 'män', 'kvinnor']);
                larb.m_num = window.getScbVal(lRow, ['män', 'man'], ['andel', '%']);
                larb.k_num = window.getScbVal(lRow, ['kvinnor', 'kvinna'], ['andel', '%']);
                larb.in_num = window.getScbVal(lRow, ['inrikes', 'inrikes född'], ['andel', '%']);
                larb.ut_num = window.getScbVal(lRow, ['utrikes', 'utrikes född'], ['andel', '%']);
            }
        }

        let n_inrikes = null, n_utrikes = null, d_inrikes = null, d_utrikes = null;
        let n_orig = window.extractOriginPop(dsUtrKeyNatt || '', y);
        if(n_orig) { n_inrikes = n_orig.inr; n_utrikes = n_orig.utr; }
        let d_orig = window.extractOriginPop(dsUtrKeySyss || '', y);
        if(d_orig) { d_inrikes = d_orig.inr; d_utrikes = d_orig.utr; }

        let pop16_74 = window.getPopForYear(window.popData, y);
        if(pop16_74 === 0 && nattTotalt > 0) pop16_74 = nattTotalt / 0.70; 
        let motorRate = null;
        if (pop16_74 > 0 && nattTotalt > 0) motorRate = (nattTotalt / pop16_74) * 100;

        let ageRates = null;
        let nattAlderRowsForYear = nattAlderData.filter(r => window.extractYear(r) == y);
        let nattAlderRow = null;
        if (nattAlderRowsForYear.length > 0) {
            let totRow = nattAlderRowsForYear.find(r => window.getKon(r) === 'totalt');
            if (totRow) {
                nattAlderRow = totRow;
            } else {
                nattAlderRow = {};
                nattAlderRowsForYear.forEach(r => {
                    let kon = window.getKon(r);
                    if (kon === 'män' || kon === 'kvinnor') {
                        Object.keys(r).forEach(k => {
                            if (typeof r[k] === 'number' || (!isNaN(parseFloat(r[k])) && String(r[k]).trim() !== '')) {
                                nattAlderRow[k] = (nattAlderRow[k] || 0) + parseFloat(r[k]);
                            } else if (k === 'År' || k === 'år' || k === 'ÅR') {
                                nattAlderRow[k] = r[k];
                            }
                        });
                    }
                });
            }
        }
        
        if (nattAlderRow && window.popData.length > 0) {
            ageRates = {};
            let recordsForYear = window.popData.filter(r => String(r.tid).replace('(Prognos)','').trim() === String(y));
            let useGenderForYear = recordsForYear.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');

            Object.keys(nattAlderRow).forEach(key => {
                if (String(key).toLowerCase().includes('totalt')) return;
                const rangeMatch = String(key).match(/(\d+)\s*-\s*(\d+)/);
                if (rangeMatch) {
                    const minAge = parseInt(rangeMatch[1]);
                    const maxAge = parseInt(rangeMatch[2]);
                    if ((maxAge - minAge) > 5) return;

                    const workers = parseFloat(nattAlderRow[key]) || 0;
                    let groupPop = 0;
                    
                    recordsForYear.forEach(r => {
                        if (!String(r.ålder).toLowerCase().includes('totalt')) {
                            if (useGenderForYear && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
                            const ageMatch = String(r.ålder).match(/\d+/);
                            if (ageMatch) {
                                const a = parseInt(ageMatch[0]);
                                if (a >= minAge && a <= maxAge) groupPop += (r.Befolkning || 0);
                            }
                        }
                    });
                    if (groupPop > 0) ageRates[key] = { min: minAge, max: maxAge, rate: workers / groupPop };
                }
            });
        }

        let baseNetCommute = hasPendlingData ? (inpendlingTot - utpendlingTot) : 0;
        if (d_man != null && d_kvinna != null && dagTotalt == null) dagTotalt = d_man + d_kvinna;
        if (n_man != null && n_kvinna != null && nattTotalt == null) nattTotalt = n_man + n_kvinna;

        let d_man_age = {}, d_kvinna_age = {}, n_man_age = {}, n_kvinna_age = {};
        const ageLabels = ['16-19', '20-24', '25-34', '35-44', '45-54', '55-59', '60-64', '65-74'];
        ageLabels.forEach(l => { d_man_age[l] = 0; d_kvinna_age[l] = 0; n_man_age[l] = 0; n_kvinna_age[l] = 0; });
        
        let mapToTargetGroupFn = function(ageStr) {
            let s = ageStr.replace(' år', '').trim();
            if (s === '16-19') return '16-19';
            if (s === '20-24') return '20-24';
            if (s === '25-29' || s === '30-34' || s === '25-34') return '25-34';
            if (s === '35-39' || s === '40-44' || s === '35-44') return '35-44';
            if (s === '45-49' || s === '50-54' || s === '45-54') return '45-54';
            if (s === '55-59') return '55-59';
            if (s === '60-64') return '60-64';
            if (s === '65-69' || s === '70-74' || s === '65-74') return '65-74';
            return null;
        };

        syssAlderData.filter(r => window.extractYear(r) == y).forEach(r => {
            let kon = window.getKon(r);
            if (kon === 'män' || kon === 'kvinnor') {
                Object.keys(r).forEach(k => {
                    let mappedGroup = mapToTargetGroupFn(k);
                    if (mappedGroup) {
                        if (kon === 'män') d_man_age[mappedGroup] += parseFloat(r[k]) || 0;
                        if (kon === 'kvinnor') d_kvinna_age[mappedGroup] += parseFloat(r[k]) || 0;
                    }
                });
            }
        });

        nattAlderData.filter(r => window.extractYear(r) == y).forEach(r => {
            let kon = window.getKon(r);
            if (kon === 'män' || kon === 'kvinnor') {
                Object.keys(r).forEach(k => {
                    let mappedGroup = mapToTargetGroupFn(k);
                    if (mappedGroup) {
                        if (kon === 'män') n_man_age[mappedGroup] += parseFloat(r[k]) || 0;
                        if (kon === 'kvinnor') n_kvinna_age[mappedGroup] += parseFloat(r[k]) || 0;
                    }
                });
            }
        });

        window.histDataStore[y] = { 
            demand: dagTotalt, 
            supply: nattTotalt, 
            inpendling: hasPendlingData ? inpendlingTot : null,
            utpendling: hasPendlingData ? utpendlingTot : null,
            netCommuting: hasPendlingData ? baseNetCommute : null,
            totalSupply: (nattTotalt != null && hasPendlingData) ? (nattTotalt + baseNetCommute) : null,
            pop: pop16_74 > 0 ? pop16_74 : null,
            rate: motorRate,
            displayRate: faktiskRate !== null ? faktiskRate : null,
            syssGradTot: syssGradTotObj,
            syssGradM: syssGradMObj,
            syssGradK: syssGradKObj,
            syss_in_tot: syss_in_tot,
            syss_ut_tot: syss_ut_tot,
            brp: brpPerSyss,
            extrapolatedBrp: null,
            arb: arb, 
            larb: larb,
            arbetsloshetPct: arbetsloshetPct, 
            langtidsPct: langtidsPct, 
            n_inrikes: n_inrikes,
            n_utrikes: n_utrikes,
            d_inrikes: d_inrikes,
            d_utrikes: d_utrikes,
            d_man: d_man,
            d_kvinna: d_kvinna,
            n_man: n_man,
            n_kvinna: n_kvinna,
            arb_inrikes: arb_inrikes,
            arb_utrikes: arb_utrikes,
            larb_inrikes: larb_inrikes,
            larb_utrikes: larb_utrikes,
            arb_man: arb_man,
            arb_kvinna: arb_kvinna,
            larb_man: larb_man,
            larb_kvinna: larb_kvinna,
            d_man_age: d_man_age,
            d_kvinna_age: d_kvinna_age,
            n_man_age: n_man_age,
            n_kvinna_age: n_kvinna_age,
            ageRates: Object.keys(ageRates || {}).length > 0 ? ageRates : null
        };
    });

    let brpCAGR = 0.015; 
    if (brpHistory.length >= 2) {
        let first = brpHistory[Math.max(0, brpHistory.length - 11)];
        let last = brpHistory[brpHistory.length - 1];
        let yearsDiff = last.year - first.year;
        if (yearsDiff > 0 && first.val > 0) { brpCAGR = Math.pow(last.val / first.val, 1 / yearsDiff) - 1; }
    }

    let lastKnown = {};
    sortedYears.forEach(y => {
        let d = window.histDataStore[y];
        if (!d) return;
        ['displayRate','syss_in_tot','syss_ut_tot','n_inrikes','n_utrikes','d_inrikes','d_utrikes','n_man','n_kvinna','d_man','d_kvinna','ageRates'].forEach(k => {
            if (d[k] != null) lastKnown[k] = (typeof d[k] === 'object') ? JSON.parse(JSON.stringify(d[k])) : d[k];
            else if (lastKnown[k] != null) d[k] = (typeof lastKnown[k] === 'object') ? JSON.parse(JSON.stringify(lastKnown[k])) : lastKnown[k];
        });
        
        if(d.arb.tot_pct == null && lastKnown.arb_tot_pct != null) { d.arb.tot_pct = lastKnown.arb_tot_pct; d.arbetsloshetPct = lastKnown.arb_tot_pct; }
        else if (d.arb.tot_pct != null) lastKnown.arb_tot_pct = d.arb.tot_pct;
        
        if(d.larb.tot_pct == null && lastKnown.larb_tot_pct != null) { d.larb.tot_pct = lastKnown.larb_tot_pct; d.langtidsPct = lastKnown.larb_tot_pct; }
        else if (d.larb.tot_pct != null) lastKnown.larb_tot_pct = d.larb.tot_pct;

        if (d.brp === null && lastKnownBRP !== null && y > lastKnownBRPYear) {
            let yearsAhead = y - lastKnownBRPYear;
            d.extrapolatedBrp = lastKnownBRP * Math.pow(1 + brpCAGR, yearsAhead);
        } else {
            d.extrapolatedBrp = d.brp;
        }
    });

    window.histDataStore['brpCAGR'] = brpCAGR;
    window.histDataStore['lastKnownBRP'] = lastKnownBRP;

    window.baseYear = sortedYears[0];
    for (let i = sortedYears.length - 1; i >= 0; i--) {
        let y = sortedYears[i];
        if (window.histDataStore[y].demand != null && window.histDataStore[y].supply != null && window.histDataStore[y].displayRate != null) {
            window.baseYear = y; break;
        }
    }
    
    if (!window.baseYear || window.baseYear < sortedYears[0]) {
        for (let i = sortedYears.length - 1; i >= 0; i--) {
            let y = sortedYears[i];
            if (window.histDataStore[y].demand != null && window.histDataStore[y].supply != null) {
                window.baseYear = y; break;
            }
        }
    }

    window.histYearsGlobal = sortedYears.filter(y => y <= window.baseYear); 
    for (let y in window.histDataStore) {
        const numericY = parseInt(y);
        if (!isNaN(numericY) && numericY > window.baseYear && y !== 'brpCAGR' && y !== 'lastKnownBRP') {
            delete window.histDataStore[y];
        }
    }

    // VIKTAT GENOMSNITT 10 ÅR FÖR ATT SLIPPA DIPP
    const avgYears = window.histYearsGlobal.filter(y => y <= window.baseYear && y > window.baseYear - 10).sort((a,b)=>a-b);
    let totalWeight = 0;
    let sumRate = 0, sumDisplayRate = 0, sumIn = 0, sumUt = 0;
    let sumM = {}, sumK = {}, sumAge = {};
    
    avgYears.forEach((y, i) => {
        let w = i + 1; 
        totalWeight += w;

        let d = window.histDataStore[y];
        if (d.rate) sumRate += d.rate * w;
        if (d.displayRate) sumDisplayRate += d.displayRate * w;
        if (d.syss_in_tot) sumIn += d.syss_in_tot * w;
        if (d.syss_ut_tot) sumUt += d.syss_ut_tot * w;
        
        if (d.syssGradM) Object.keys(d.syssGradM).forEach(k => { if (!['år','tid','kön'].includes(k.toLowerCase())) sumM[k] = (sumM[k] || 0) + parseFloat(d.syssGradM[k]||0) * w; });
        if (d.syssGradK) Object.keys(d.syssGradK).forEach(k => { if (!['år','tid','kön'].includes(k.toLowerCase())) sumK[k] = (sumK[k] || 0) + parseFloat(d.syssGradK[k]||0) * w; });
        if (d.ageRates) Object.keys(d.ageRates).forEach(k => { sumAge[k] = (sumAge[k] || 0) + parseFloat(d.ageRates[k].rate||0) * w; });
    });
    
    if (totalWeight === 0) totalWeight = 1;
    let avgM = {}, avgK = {}, avgAge = null;
    Object.keys(sumM).forEach(k => avgM[k] = sumM[k] / totalWeight);
    Object.keys(sumK).forEach(k => avgK[k] = sumK[k] / totalWeight);
    
    if (window.histDataStore[window.baseYear] && window.histDataStore[window.baseYear].ageRates) {
        avgAge = JSON.parse(JSON.stringify(window.histDataStore[window.baseYear].ageRates));
        Object.keys(avgAge).forEach(k => { if (sumAge[k]) avgAge[k].rate = sumAge[k] / totalWeight; });
    }

    if (window.histDataStore[window.baseYear]) {
        window.histDataStore[window.baseYear].avg10_rate = sumRate / totalWeight;
        window.histDataStore[window.baseYear].avg10_displayRate = sumDisplayRate / totalWeight;
        window.histDataStore[window.baseYear].avg10_syss_in_tot = sumIn / totalWeight;
        window.histDataStore[window.baseYear].avg10_syss_ut_tot = sumUt / totalWeight;
        window.histDataStore[window.baseYear].avg10_syssGradM = avgM;
        window.histDataStore[window.baseYear].avg10_syssGradK = avgK;
        window.histDataStore[window.baseYear].avg10_ageRates = avgAge;
    }
};

// ==========================================
// SIMULERING OCH DYNAMISK JÄMVIKT
// ==========================================
window.runSimulation = function() {
    const forecastYears = window.PROGNOS_SLUTAR - window.baseYear;
    if (forecastYears <= 0) return;

    const btn = document.getElementById('simBtn');
    if (btn) {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Beräknar...';
        btn.classList.add('opacity-75', 'cursor-not-allowed');
    }

    setTimeout(() => {
        try {
            const simMode = document.getElementById('simMode') ? document.getElementById('simMode').value : 'full';
            const popSource = document.getElementById('popSource') ? document.getElementById('popSource').value : 'officiell';
            const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
            const pendlingType = document.getElementById('pendlingType') ? document.getElementById('pendlingType').value : 'pct';

            const jobGrowthPct = parseFloat(document.getElementById('jobGrowthSlider')?.value) || 0; 
            const syssGradChangeOverall = parseFloat(document.getElementById('syssGradSlider')?.value) || 0;
            const studentChange = parseFloat(document.getElementById('studentSlider')?.value) || 0;
            const civIngChange = parseFloat(document.getElementById('civIngSlider')?.value) || 0;
            
            let inpendlingChange = 0, utpendlingChange = 0, distansChange = 0, regionChangeMin = 0;
            
            if (simMode === 'full') {
                inpendlingChange = parseFloat(document.getElementById('inpendlingSlider')?.value) || 0;
                utpendlingChange = parseFloat(document.getElementById('utpendlingSlider')?.value) || 0;
                distansChange = parseFloat(document.getElementById('distansSlider')?.value) || 0;
                regionChangeMin = parseFloat(document.getElementById('regionSlider')?.value) || 0;
            }

            const base = window.histDataStore[window.baseYear];
            window.progDataStore = {};
            
            let cumulativeExtraStudents = 0;
            let extraRegionSupplyTotal = 0;
            let beraknadeKommuner = 0;
            
            if (regionChangeMin > 0 && window.syssConfig['Inom_en_timme']) {
                window.syssConfig['Inom_en_timme'].forEach(row => {
                    let inpendling = parseFloat(row['Inpendling_2024']) || 0;
                    let bilMin = parseFloat(row['Bil_minuter']);
                    let kollMin = parseFloat(row['Kollektivt_minuter']);
                    let basTid = isNaN(bilMin) ? kollMin : bilMin; 
                    
                    if (inpendling > 0 && !isNaN(basTid) && basTid > 0) {
                        let nyTid = Math.max(10, basTid - regionChangeMin); 
                        let okning = inpendling * (Math.pow(basTid / nyTid, 1.5) - 1);
                        extraRegionSupplyTotal += okning;
                        beraknadeKommuner++;
                    }
                });
            }

            const baselineDemand = base.demand != null ? Number(base.demand) : 0;
            const baselineSupply = base.supply != null ? Number(base.supply) : 0;
            const baselineGap = Math.max(0, baselineDemand - baselineSupply);
            const distansBoostTotal = baselineGap * (distansChange / 100);
            
            const targetVirtualSupply = extraRegionSupplyTotal + distansBoostTotal;
            const brpCAGR = window.histDataStore['brpCAGR'] || 0.015;
            const baseExtrapolatedBRP = window.histDataStore[window.baseYear].extrapolatedBrp;
            
            const useAvg = (popSource === 'officiell' || popSource === 'custom');
            const baseOverallRate = useAvg && base.avg10_rate != null ? base.avg10_rate : (base.rate || 0);
            const baseDisplayRate = useAvg && base.avg10_displayRate != null ? base.avg10_displayRate : (base.displayRate != null ? Number(base.displayRate) : 0);
            let ageRates = useAvg && base.avg10_ageRates ? base.avg10_ageRates : base.ageRates;
            
            const base_syss_in_tot = useAvg && base.avg10_syss_in_tot != null ? base.avg10_syss_in_tot : base.syss_in_tot;
            const base_syss_ut_tot = useAvg && base.avg10_syss_ut_tot != null ? base.avg10_syss_ut_tot : base.syss_ut_tot;
            const base_syssGradM = useAvg && base.avg10_syssGradM ? base.avg10_syssGradM : base.syssGradM;
            const base_syssGradK = useAvg && base.avg10_syssGradK ? base.avg10_syssGradK : base.syssGradK;

            const syssGradDemandBoostTotal = (base.pop != null ? base.pop : 0) * (syssGradChangeOverall / 100);

            const base_n_ut = base.n_utrikes || 0;
            const base_n_in = base.n_inrikes || 0;
            const base_d_ut = base.d_utrikes || 0;
            const base_d_in = base.d_inrikes || 0;
            const share_n_ut = (base_n_ut + base_n_in > 0) ? (base_n_ut / (base_n_ut + base_n_in)) : 0.25;
            const share_d_ut = (base_d_ut + base_d_in > 0) ? (base_d_ut / (base_d_ut + base_d_in)) : 0.25;

            const base_d_man = base.d_man || 0;
            const base_d_kvinna = base.d_kvinna || 0;
            const share_d_man = (base_d_man + base_d_kvinna > 0) ? (base_d_man / (base_d_man + base_d_kvinna)) : 0.5;

            const base_n_man = base.n_man || 0;
            const base_n_kvinna = base.n_kvinna || 0;
            const share_n_man = (base_n_man + base_n_kvinna > 0) ? (base_n_man / (base_n_man + base_n_kvinna)) : 0.5;

            let dynPopAccumulated = 0;
            let futureInpendlingBase = base.inpendling != null ? Number(base.inpendling) : 0;
            let futureUtpendlingBase = base.utpendling != null ? Number(base.utpendling) : 0;

            // --- CATCH-UP EFFEKT ---
            let inrikesSyssKorr = syssGradChangeOverall;
            let utrikesSyssKorr = syssGradChangeOverall;
            let mKorr = syssGradChangeOverall;
            let kKorr = syssGradChangeOverall;

            if (syssGradChangeOverall > 0) {
                inrikesSyssKorr = syssGradChangeOverall * 0.4;  
                utrikesSyssKorr = syssGradChangeOverall * 2.8;  
                mKorr = syssGradChangeOverall * 0.8;
                kKorr = syssGradChangeOverall * 1.2;
            } else if (syssGradChangeOverall < 0) {
                inrikesSyssKorr = syssGradChangeOverall * 0.4;
                utrikesSyssKorr = syssGradChangeOverall * 2.8;
                mKorr = syssGradChangeOverall * 0.8;
                kKorr = syssGradChangeOverall * 1.2;
            }

            // Hämta skalan för näringslivsjustering
            let naringSkala = window.currentNaringSkala !== undefined ? window.currentNaringSkala : 1.0;
            let totalNaringDemandExtra = 0;
            let totalNaringDemandExtraM = 0;
            let totalNaringDemandExtraK = 0;

            for (let i = 1; i <= forecastYears; i++) {
                const forecastYear = window.baseYear + i;
                
                // Hantera Näringslivsjustering 
                let naringDemandThisYear = 0;
                let naringDemandThisYearM = 0;
                let naringDemandThisYearK = 0;

                if (window.syssConfig['Näringslivsjustering']) {
                    window.syssConfig['Näringslivsjustering'].forEach(row => {
                        let ar = parseInt(row['År']);
                        if (ar && ar === forecastYear) {
                            let val = (parseFloat(row['Antal_Jobb'] || row['Sysselsatta'] || row['Förändring'] || 0) * naringSkala);
                            naringDemandThisYear += val;
                            naringDemandThisYearM += val * share_d_man;
                            naringDemandThisYearK += val * (1 - share_d_man);
                        }
                    });
                }
                
                totalNaringDemandExtra += naringDemandThisYear;
                totalNaringDemandExtraM += naringDemandThisYearM;
                totalNaringDemandExtraK += naringDemandThisYearK;

                const demandGrowthFactor = 1 + ((jobGrowthPct / 100) * (i / forecastYears));
                const futureDemand = (baselineDemand * demandGrowthFactor) + (syssGradDemandBoostTotal * (i / forecastYears)) + totalNaringDemandExtra;

                let activePopData = popSource === 'fryst' ? [] : (window.useCustomPop && window.customPopData ? window.customPopData : window.popData);
                let futurePop = 0;
                let hasPopDataForYear = false; 
                
                if (popSource === 'fryst' || activePopData.length === 0) {
                    futurePop = base.pop != null ? Number(base.pop) : 0;
                } else {
                    futurePop = window.getPopForYear(activePopData, forecastYear);
                    if (futurePop > 0) { hasPopDataForYear = true; } 
                    else { futurePop = base.pop != null ? Number(base.pop) : 0; }
                }

                const baseTotalStudents = window.annualStudentsMap[forecastYear] !== undefined ? window.annualStudentsMap[forecastYear] : window.avgAnnualStudents;
                let extraStudentsThisYear = 0;
                if (window.useSpecificCivIng) {
                    const baseCivIng = window.annualCivIngMap[forecastYear] !== undefined ? window.annualCivIngMap[forecastYear] : window.avgAnnualCivIng;
                    const otherStudents = Math.max(0, baseTotalStudents - baseCivIng);
                    extraStudentsThisYear = (otherStudents * (studentChange / 100)) + (baseCivIng * (civIngChange / 100));
                } else {
                    extraStudentsThisYear = baseTotalStudents * (studentChange / 100);
                }
                
                cumulativeExtraStudents += extraStudentsThisYear;

                let futureSupply = 0, futureSupplyM = 0, futureSupplyK = 0, futureRate = 0;
                let isAgeWeighted = false;
                
                if (ageRates && popSource !== 'fryst' && activePopData.length > 0 && hasPopDataForYear) {
                    isAgeWeighted = true;
                    Object.values(ageRates).forEach(group => {
                        let groupFuturePop = 0, groupFuturePopM = 0, groupFuturePopK = 0;

                        let records = activePopData.filter(r => String(r.tid).trim() === `${forecastYear} (Prognos)`);
                        if (records.length === 0) records = activePopData.filter(r => String(r.tid).trim() === String(forecastYear));
                        
                        let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                        records.forEach(r => {
                            if (!String(r.ålder).toLowerCase().includes('totalt')) {
                                if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
                                const ageMatch = String(r.ålder).match(/\d+/);
                                if (ageMatch) {
                                    const a = parseInt(ageMatch[0]);
                                    if (a >= group.min && a <= group.max) {
                                        groupFuturePop += (r.Befolkning || 0);
                                        if (String(r.kön).trim().toLowerCase() === 'män') groupFuturePopM += (r.Befolkning || 0);
                                        else if (String(r.kön).trim().toLowerCase() === 'kvinnor') groupFuturePopK += (r.Befolkning || 0);
                                        else { 
                                            groupFuturePopM += (r.Befolkning || 0) * share_n_man; 
                                            groupFuturePopK += (r.Befolkning || 0) * (1 - share_n_man); 
                                        }
                                    }
                                }
                            }
                        });
                        
                        let sliderOffset = syssGradChangeOverall;
                        let sliderEl = document.getElementById(`syssAge${group.min}_${group.max}`);
                        if (sliderEl) sliderOffset = parseFloat(sliderEl.value) || 0;

                        const specificTargetRate = group.rate + (sliderOffset / 100); 
                        const currentSpecificRate = group.rate + ((specificTargetRate - group.rate) * (i / forecastYears));
                        futureSupply += (groupFuturePop * currentSpecificRate);
                        futureSupplyM += (groupFuturePopM * currentSpecificRate);
                        futureSupplyK += (groupFuturePopK * currentSpecificRate);
                    });
                    futureSupply += cumulativeExtraStudents;
                    futureSupplyM += cumulativeExtraStudents * share_n_man;
                    futureSupplyK += cumulativeExtraStudents * (1 - share_n_man);
                } else {
                    const targetRate = baseOverallRate + syssGradChangeOverall;
                    futureRate = baseOverallRate + (((targetRate) - baseOverallRate) * (i / forecastYears));
                    futureSupply = (futurePop * (futureRate / 100)) + cumulativeExtraStudents;
                    futureSupplyM = futureSupply * share_n_man;
                    futureSupplyK = futureSupply * (1 - share_n_man);
                }
                
                let futureInpendling = futureInpendlingBase;
                let futureUtpendling = futureUtpendlingBase;

                if (simMode === 'full') {
                    if (pendlingType === 'pct') {
                        futureInpendling = futureInpendlingBase * (1 + ((inpendlingChange/100) * (i/forecastYears)));
                        futureUtpendling = futureUtpendlingBase * (1 + ((utpendlingChange/100) * (i/forecastYears)));
                    } else {
                        futureInpendling = Math.max(0, futureInpendlingBase + (inpendlingChange * (i/forecastYears)));
                        futureUtpendling = Math.max(0, futureUtpendlingBase + (utpendlingChange * (i/forecastYears)));
                    }
                }

                const explicitNetCommuting = futureInpendling - futureUtpendling;
                const virtualSupply = targetVirtualSupply * (i / forecastYears);
                let futureTotalSupply = futureSupply + explicitNetCommuting + virtualSupply;

                let inducedPopThisYear = 0, inducedLaborThisYear = 0, reqForeignLabor = 0, hypotheticalPopNeed = 0;
                
                const currentGap = futureDemand - futureTotalSupply;
                if (currentGap > 0) {
                    const migrantEl = document.getElementById('migrantSyssSlider');
                    const userSyssAdjustment = migrantEl ? parseFloat(migrantEl.value) / 100 : 0.10;
                    const empRate = Math.max(0.01, window.globalMigrantEmploymentRate + userSyssAdjustment);
                    hypotheticalPopNeed = currentGap / empRate;
                }

                if (causalityMode === 'dynamic') {
                    if (currentGap > 0) {
                        inducedLaborThisYear = currentGap;
                        inducedPopThisYear = hypotheticalPopNeed;
                        
                        futureSupply += inducedLaborThisYear;
                        futureTotalSupply += inducedLaborThisYear;
                        futurePop += inducedPopThisYear;
                        dynPopAccumulated += inducedPopThisYear;
                        
                        futureSupplyM += inducedLaborThisYear * share_n_man;
                        futureSupplyK += inducedLaborThisYear * (1 - share_n_man);
                        
                        const maxDomesticNetWorkers = 500; 
                        if (inducedLaborThisYear > maxDomesticNetWorkers) reqForeignLabor = inducedLaborThisYear - maxDomesticNetWorkers;
                    }
                }

                let medfoljande = {};
                let medfoljande_totalt = 0;
                let basePopForChildren = causalityMode === 'dynamic' ? inducedPopThisYear : hypotheticalPopNeed;
                
                // --- JUSTERING: Se till att medföljande ALLTID beräknas (även om 0) för att inte bryta diagrammen ---
                if (window.syssConfig && window.syssConfig['Medföljande']) {
                    window.syssConfig['Medföljande'].forEach(row => {
                        let kategori = row['Skolform_Ålder'];
                        let kvot = parseFloat(row['Kvot']) || 0;
                        if (kategori) {
                            let antal = basePopForChildren > 0 ? basePopForChildren * kvot : 0;
                            medfoljande[kategori] = antal;
                            medfoljande_totalt += antal;
                        }
                    });
                }

                const displayTarget = baseDisplayRate + syssGradChangeOverall;
                const futureDisplayRate = baseDisplayRate + ((displayTarget - baseDisplayRate) * (i / forecastYears));

                const futureBrpPerSyss = baseExtrapolatedBRP ? baseExtrapolatedBRP * Math.pow(1 + brpCAGR, i) : null;
                const futureTotalBrpMkr = (futureBrpPerSyss && futureDemand) ? (futureBrpPerSyss * futureDemand) / 1000 : null;

                let fSyssGradM = null, fSyssGradK = null;
                if (base_syssGradM) {
                    fSyssGradM = {};
                    for (let k in base_syssGradM) {
                        if (!isNaN(base_syssGradM[k])) fSyssGradM[k] = base_syssGradM[k] + mKorr * (i / forecastYears);
                    }
                }
                if (base_syssGradK) {
                    fSyssGradK = {};
                    for (let k in base_syssGradK) {
                        if (!isNaN(base_syssGradK[k])) fSyssGradK[k] = base_syssGradK[k] + kKorr * (i / forecastYears);
                    }
                }

                const ageLabels = ['16-19', '20-24', '25-34', '35-44', '45-54', '55-59', '60-64', '65-74'];
                let d_man_age = {}, d_kvinna_age = {}, n_man_age = {}, n_kvinna_age = {};
                if (base.d_man_age) {
                    ageLabels.forEach(l => {
                        if (base.d_man_age[l] != null) d_man_age[l] = base.d_man_age[l] * (base.d_man > 0 ? ((base_d_man * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * share_d_man) / base.d_man) : 1);
                        if (base.d_kvinna_age[l] != null) d_kvinna_age[l] = base.d_kvinna_age[l] * (base.d_kvinna > 0 ? ((base_d_kvinna * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * (1 - share_d_man)) / base.d_kvinna) : 1);
                        if (base.n_man_age[l] != null) n_man_age[l] = base.n_man_age[l] * (base.n_man > 0 ? (futureSupplyM / base.n_man) : 1);
                        if (base.n_kvinna_age[l] != null) n_kvinna_age[l] = base.n_kvinna_age[l] * (base.n_kvinna > 0 ? (futureSupplyK / base.n_kvinna) : 1);
                    });
                }

                let blankArb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null };
                let blankLarb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null, tot_insk:null, m_insk:null, k_insk:null, in_insk:null, ut_insk:null };

                // --- ÅTERSTÄLLD KOD FÖR CATCH-UP-EFFEKT (Löser Krasch: dyn_share_n_ut is not defined) ---
                let shiftMax = 0.05 * (syssGradChangeOverall / 5); 
                let dyn_share_n_ut = share_n_ut + (shiftMax * (i / forecastYears));
                let dyn_share_d_ut = share_d_ut + (shiftMax * (i / forecastYears));

                window.progDataStore[forecastYear] = {
                    demand: futureDemand,
                    supply: futureSupply,
                    inpendling: futureInpendling,
                    utpendling: futureUtpendling,
                    explicitNetCommuting: explicitNetCommuting,
                    virtualSupply: virtualSupply, 
                    totalSupply: futureTotalSupply,
                    antalKommunerBeraknade: beraknadeKommuner,
                    pop: futurePop,
                    rate: futureSupply > 0 && futurePop > 0 ? (futureSupply / futurePop)*100 : futureRate,
                    displayRate: futureDisplayRate,
                    brp: futureBrpPerSyss,
                    totalBrpMkr: futureTotalBrpMkr,
                    syss_in_tot: base.syss_in_tot != null ? base.syss_in_tot + inrikesSyssKorr * (i/forecastYears) : null,
                    syss_ut_tot: base.syss_ut_tot != null ? base.syss_ut_tot + utrikesSyssKorr * (i/forecastYears) : null,
                    syssGradM: fSyssGradM, 
                    syssGradK: fSyssGradK,
                    n_utrikes: futureSupply * dyn_share_n_ut,
                    n_inrikes: futureSupply * (1 - dyn_share_n_ut),
                    d_utrikes: futureDemand * dyn_share_d_ut,
                    d_inrikes: futureDemand * (1 - dyn_share_d_ut),
                    n_man: futureSupplyM,
                    n_kvinna: futureSupplyK,
                    d_man: base_d_man * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * share_d_man + totalNaringDemandExtraM,
                    d_kvinna: base_d_kvinna * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * (1 - share_d_man) + totalNaringDemandExtraK,
                    d_man_age: d_man_age,
                    d_kvinna_age: d_kvinna_age,
                    n_man_age: n_man_age,
                    n_kvinna_age: n_kvinna_age,
                    arbetsloshetPct: null,
                    langtidsPct: null,
                    isAgeWeighted: isAgeWeighted,
                    arb: blankArb,
                    larb: blankLarb,
                    inducedPop: inducedPopThisYear,
                    reqForeignLabor: reqForeignLabor,
                    medfoljande: medfoljande,
                    medfoljande_totalt: medfoljande_totalt
                };
            }

            if(typeof window.buildDropdowns === 'function') window.buildDropdowns(); 
            if(typeof window.updateDashboard === 'function') window.updateDashboard(false); 

            if (btn) {
                btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Klar!';
                btn.classList.replace('bg-slate-700', 'bg-green-600');
                setTimeout(() => {
                    btn.innerHTML = '<i class="fa-solid fa-gears mr-1"></i> Kör';
                    btn.classList.replace('bg-green-600', 'bg-slate-700');
                    btn.classList.remove('opacity-75', 'cursor-not-allowed');
                }, 2000);
            }

        } catch (err) {
            console.error("Krasch i simuleringen:", err);
            const ds = document.getElementById('dataStatus');
            if(ds) {
                ds.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <b>Krasch (Simulering):</b> ${err.message}`;
                ds.className = "p-2 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-bold";
            }
            if(btn) {
                btn.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1"></i> Krasch`;
                btn.classList.replace('bg-slate-700', 'bg-red-600');
                btn.classList.remove('opacity-75', 'cursor-not-allowed');
            }
        }
    }, 100);
};

// ==========================================
// BYGG DROPDOWNS & UPPDATERA UI
// ==========================================
window.buildDropdowns = function() {
    const progYears = Object.keys(window.progDataStore).map(Number);
    window.allYears = [...new Set([...window.histYearsGlobal, ...progYears])].sort((a,b)=>a-b);

    const yearSelect = document.getElementById('yearSelect');
    if(yearSelect) {
        const prevYearVal = yearSelect.value;
        while (yearSelect.firstChild) { yearSelect.removeChild(yearSelect.firstChild); }
        
        if (window.allYears.length === 0) {
            yearSelect.add(new Option("Data saknas", ""));
        } else {
            [...window.allYears].reverse().forEach(y => {
                let text = y > window.baseYear ? y + " (Prognos)" : y.toString();
                let opt = new Option(text, y);
                if(y > window.baseYear) opt.className = "text-sky-700 font-bold bg-sky-50";
                yearSelect.add(opt);
            });
            
            if (prevYearVal && window.allYears.includes(parseInt(prevYearVal))) yearSelect.value = prevYearVal;
            else yearSelect.value = window.baseYear; 
        }
    }

    const startYearSelect = document.getElementById('startYearSelect');
    if(startYearSelect) {
        const prevStartVal = startYearSelect.value;
        while (startYearSelect.firstChild) { startYearSelect.removeChild(startYearSelect.firstChild); }

        if (window.histYearsGlobal.length === 0) {
            startYearSelect.add(new Option("Data saknas", ""));
        } else {
            const specificYears = [1975, 1990, 2000, 2010, 2020, window.baseYear - 10, window.baseYear];
            const validYears = [...new Set(specificYears)].filter(y => window.histYearsGlobal.includes(y)).sort((a,b)=>a-b);
            
            validYears.reverse().forEach(y => startYearSelect.add(new Option('Från ' + y, y)));
            
            let defaultStart = window.baseYear - 10;
            if (!validYears.includes(defaultStart) && validYears.length > 0) defaultStart = validYears[validYears.length-1];
            
            if (prevStartVal && validYears.includes(parseInt(prevStartVal))) startYearSelect.value = prevStartVal;
            else startYearSelect.value = defaultStart; 
        }
    }
};

window.handleYearChange = function() {
    if (typeof window.updateKPIs === 'function') window.updateKPIs();
    const chartTypeElement = document.getElementById('chartType');
    if (chartTypeElement) {
        const chartType = chartTypeElement.value;
        if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
            if (typeof window.updateDashboard === 'function') window.updateDashboard(true);
        }
    }
};

window.updateKPIs = function() {
    const yearSelect = document.getElementById('yearSelect');
    if (!yearSelect) return;
    const yearStr = yearSelect.value;
    if(!yearStr) return;
    const y = parseInt(yearStr);

    let d = y <= window.baseYear ? window.histDataStore[y] : (window.progDataStore[y] || window.histDataStore[y]);
    if (!d) return;

    const kpiEfterfragan = document.getElementById('kpiEfterfragan');
    if (kpiEfterfragan) kpiEfterfragan.innerText = d.demand != null ? window.formatNumber(d.demand, 0) : 'Data saknas';
    
    const kpiUtbud = document.getElementById('kpiUtbud');
    const kpiUtbudContainer = document.getElementById('kpiUtbudContainer');
    if (kpiUtbud && kpiUtbudContainer) {
        if (d.isAgeWeighted) {
            kpiUtbud.innerHTML = `${window.formatNumber(d.supply, 0)} <span class="text-xs text-sky-400" title="Åldersviktad beräkning aktiv">*</span>`;
            kpiUtbudContainer.title = "Lokalt arbetskraftsutbud (Åldersviktad beräkning)";
        } else {
            kpiUtbud.innerText = d.supply != null ? window.formatNumber(d.supply, 0) : 'Data saknas';
            kpiUtbudContainer.title = "Lokalt arbetskraftsutbud";
        }
    }
    
    const kpiBef = document.getElementById('kpiBefolkning');
    const kpiBefContainer = document.getElementById('kpiBefolkningContainer');
    const warningEl = document.getElementById('takWarning');
    const causalityModeEl = document.getElementById('causalityMode');
    const causalityMode = causalityModeEl ? causalityModeEl.value : 'analytic';
    
    const simModeEl = document.getElementById('simMode');
    const simMode = simModeEl ? simModeEl.value : 'full';
    const showCommuting = simMode === 'full';

    const warnings = [];
    const colorClasses = {
        'red': 'bg-red-100 text-red-800 border-red-300',
        'orange': 'bg-orange-100 text-orange-800 border-orange-300',
        'amber': 'bg-amber-100 text-amber-800 border-amber-300',
        'green': 'bg-green-100 text-green-800 border-green-300'
    };

    if (d.demand != null && d.supply != null) {
        let explNetto = d.netCommuting !== undefined ? d.netCommuting : (d.explicitNetCommuting || 0);
        let virtualExt = d.virtualSupply || 0;
        const totalPendling = showCommuting ? (explNetto + virtualExt) : 0;
        
        const kpiPendling = document.getElementById('kpiPendling');
        if(kpiPendling) {
            kpiPendling.innerText = (totalPendling > 0 ? '+' : '') + window.formatNumber(totalPendling, 0);
            kpiPendling.className = "text-base md:text-lg font-bold " + (totalPendling > 0 ? "text-indigo-600" : (showCommuting ? "text-emerald-600" : "text-gray-400"));
            
            if (!showCommuting) {
                kpiPendling.title = "Pendling inaktiverad i läget 'Endast Lokal'.";
                kpiPendling.innerText = '-';
            } else if (virtualExt > 0) {
                const komText = d.antalKommunerBeraknade ? ` för ${d.antalKommunerBeraknade} grannkommuner` : '';
                kpiPendling.title = `Faktisk pendling: ${window.formatNumber(explNetto, 0)}.\nVirtuellt Pendlingsutbud: ${window.formatNumber(virtualExt, 0)} ${komText}.`;
            } else {
                kpiPendling.title = "Totalt Pendlingsnetto";
            }
        }

        if (typeof window.takEffekter !== 'undefined') {
            let inpendlingAndel = (d.inpendling != null && d.demand > 0) ? (d.inpendling / d.demand) * 100 : 0;
            if (inpendlingAndel > window.takEffekter.maxInpendlingsandel) {
                warnings.push({icon: 'fa-car-side', color: 'amber', text: 'Hög inpendlingsandel', title: `Varning: Inpendlingsandel (${window.formatNumber(inpendlingAndel, 1)}%) överstiger ${window.takEffekter.maxInpendlingsandel}%.`});
            }
            
            let totalPendlingFysisk = (d.inpendling || 0) + (d.utpendling || 0);
            if (totalPendlingFysisk > window.takEffekter.kapacitetstakInfrastruktur) {
                warnings.push({icon: 'fa-train', color: 'red', text: 'Infrastruktur överbelastad', title: `Varning: Fysisk pendling (${window.formatNumber(totalPendlingFysisk, 0)} resor/dag) överstiger taket på ${window.formatNumber(window.takEffekter.kapacitetstakInfrastruktur, 0)}.`});
            }
        }

        if (causalityMode === 'dynamic' && d.inducedPop !== undefined) {
            if (d.inducedPop > 0) {
                if(kpiBef) {
                    let barnText = d.medfoljande_totalt ? ` <span class="text-[11px] font-normal text-emerald-800 block leading-tight">(+${window.formatNumber(d.medfoljande_totalt, 0)} barn)</span>` : '';
                    kpiBef.innerHTML = '+' + window.formatNumber(d.inducedPop, 0) + barnText;
                    kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                    if(kpiBefContainer) kpiBefContainer.title = `Dynamisk jämvikt:\n${window.formatNumber(d.inducedPop, 0)} nya vuxna har simulerats flytta in (samt uppskattningsvis ${window.formatNumber(d.medfoljande_totalt||0, 0)} medföljande barn).`;
                }
                if (d.reqForeignLabor > 0) {
                    warnings.push({icon: 'fa-globe', color: 'amber', text: 'Arbetskraftsinv. behövs', title: `Ca ${window.formatNumber(d.reqForeignLabor, 0)} arbetare måste rekryteras internationellt pga demografiska gränser.`});
                }
            } else {
                if(kpiBef) {
                    kpiBef.innerText = 'Balans';
                    kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                    if(kpiBefContainer) kpiBefContainer.title = "Dynamisk jämvikt: Utbud och pendling täcker behovet.";
                }
            }
        } else {
            const omatchatGap = d.demand - (d.supply + totalPendling);
            if (omatchatGap > 5) {
                const migrantSyssSlider = document.getElementById('migrantSyssSlider');
                const userSyssAdjustment = migrantSyssSlider ? parseFloat(migrantSyssSlider.value) / 100 : 0.10;
                const employmentRate = (typeof window.globalMigrantEmploymentRate !== 'undefined' ? window.globalMigrantEmploymentRate : 0.50) + userSyssAdjustment;
                let totalPopNeeded = omatchatGap / Math.max(0.01, employmentRate); 
                
                let totalBarnNeeded = 0;
                if (typeof window.syssConfig !== 'undefined' && window.syssConfig['Medföljande']) {
                    window.syssConfig['Medföljande'].forEach(row => {
                        totalBarnNeeded += totalPopNeeded * (parseFloat(row['Kvot']) || 0);
                    });
                }

                if(kpiBef) {
                    let barnText = totalBarnNeeded > 0 ? ` <span class="text-[11px] font-normal text-orange-800 block leading-tight">(+${window.formatNumber(totalBarnNeeded, 0)} barn)</span>` : '';
                    kpiBef.innerHTML = '+' + window.formatNumber(totalPopNeeded, 0) + barnText;
                    kpiBef.className = "text-base md:text-lg font-bold text-orange-600";
                    if(kpiBefContainer) kpiBefContainer.title = `Analys av gap:\nDet kvarstår ett gap på ${window.formatNumber(omatchatGap, 0)} jobb.\nFör att fylla detta krävs inflyttning av ca ${window.formatNumber(totalPopNeeded, 0)} nya vuxna (samt ${window.formatNumber(totalBarnNeeded, 0)} medföljande barn).`;
                }
            } else if (omatchatGap < -5) {
                if(kpiBef) {
                    kpiBef.innerText = 'Överskott';
                    kpiBef.className = "text-base md:text-lg font-bold text-sky-600";
                    if(kpiBefContainer) kpiBefContainer.title = `Lokalt utbud är ${window.formatNumber(Math.abs(omatchatGap), 0)} personer högre än tillgängliga jobb.`;
                }
                warnings.push({icon: 'fa-leaf', color: 'green', text: 'Arbetskraftsöverskott', title: `Lokalt utbud överstiger efterfrågan.`});
            } else {
                if(kpiBef) {
                    kpiBef.innerText = 'Balans';
                    kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                    if(kpiBefContainer) kpiBefContainer.title = "Perfekt matchning. Inget kvarstående rekryteringsgap.";
                }
                warnings.push({icon: 'fa-check', color: 'green', text: 'Arbetsmarknad i balans', title: `Utbud och Efterfrågan möts perfekt.`});
            }
        }
    } else {
        const kpiPendling = document.getElementById('kpiPendling');
        if(kpiPendling) {
            kpiPendling.innerText = 'Data saknas';
            kpiPendling.className = "text-base md:text-lg font-bold text-gray-400";
        }
        if(kpiBef) kpiBef.innerText = '-';
    }
    
    const kpiSyssGrad = document.getElementById('kpiSyssGrad');
    if (kpiSyssGrad) {
        if (d.displayRate != null) {
            kpiSyssGrad.innerText = window.formatNumber(d.displayRate, 1) + '%';
            if (typeof window.takEffekter !== 'undefined' && d.displayRate > window.takEffektMaxSyss) {
                kpiSyssGrad.className = "text-base md:text-lg font-bold text-red-600";
                warnings.push({icon: 'fa-triangle-exclamation', color: 'red', text: 'Arbetskraftsbrist', title: `Varning: Sysselsättningsgraden (${window.formatNumber(d.displayRate, 1)}%) överstiger taket på ${window.takEffektMaxSyss}%.`});
            } else if (causalityMode === 'analytic' && !(d.demand != null && d.supply != null && (d.demand - (d.supply + (d.netCommuting !== undefined ? d.netCommuting : (d.explicitNetCommuting || 0)) + (d.virtualSupply || 0))) <= -5) ) {
                kpiSyssGrad.className = "text-base md:text-lg font-bold text-gray-800";
            }
        } else {
            kpiSyssGrad.innerText = 'Data saknas';
        }
    }

    if (d.arbetsloshetPct != null && typeof window.takEffekter !== 'undefined' && d.arbetsloshetPct < window.takEffekter.minArbetsloshet) {
        warnings.push({icon: 'fa-fire', color: 'orange', text: 'Under friktionsgräns', title: `Varning: Arbetslösheten (${window.formatNumber(d.arbetsloshetPct, 1)}%) är lägre än friktionsgränsen på ${window.takEffekter.minArbetsloshet}%.`});
    }
    
    if (warningEl) {
        warningEl.innerHTML = '';
        if (warnings.length > 0) {
            warningEl.classList.remove('hidden');
            warningEl.classList.add('flex');
            warnings.forEach(w => {
                const el = document.createElement('span');
                el.className = `${colorClasses[w.color]} px-2 py-0.5 rounded text-[10px] md:text-xs font-bold border cursor-help shadow-sm`;
                el.title = w.title;
                el.innerHTML = `<i class="fa-solid ${w.icon} mr-1"></i> ${w.text}`;
                warningEl.appendChild(el);
            });
        } else {
            warningEl.classList.add('hidden');
            warningEl.classList.remove('flex');
        }
    }

    let displayBrp = d.brp || d.extrapolatedBrp;
    const kpiBox = document.getElementById('kpiBRPContainer');
    const kpiBRP = document.getElementById('kpiBRP');

    if (kpiBRP && kpiBox) {
        if (displayBrp != null) {
            let tkrText = window.formatNumber(displayBrp, 1) + ' tkr';
            let totalBrpMkr = d.totalBrpMkr;
            if (!totalBrpMkr && d.demand) totalBrpMkr = (displayBrp * d.demand) / 1000;

            if (d.brp === null && d.extrapolatedBrp != null && y <= window.baseYear) {
                kpiBRP.innerHTML = `<span class="text-slate-400 italic" title="Extrapolerat värde (SCB-data saknas ännu)">${tkrText}*</span>`;
            } else {
                kpiBRP.innerText = tkrText;
            }

            if (totalBrpMkr) {
                kpiBox.title = `Total Regional Ekonomi (BRP): ca ${window.formatNumber(totalBrpMkr, 0)} Mkr\n(Beräknat som BRP/syss × Dagbefolkning)`;
            } else {
                kpiBox.title = "Bruttoregionalprodukt per sysselsatt (tkr)";
            }
        } else {
            kpiBRP.innerText = 'Data saknas';
            kpiBox.title = "Bruttoregionalprodukt per sysselsatt (tkr)";
        }
    }
};

// ==========================================
// EXPORT-FUNKTIONER FÖR CSV
// ==========================================
window.exportPopDynamicCSV = function() {
    const popGroupSelect = document.getElementById('subGroupSelect');
    const popGroupVal = popGroupSelect ? popGroupSelect.value : 'total';
    const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
    const currentPopData = (window.useCustomPop && window.customPopData) ? window.customPopData : window.popData;
    
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; 
    csvContent += "År;Källa;Grupp;Basbefolkning;Tillskott (Dynamisk Jämvikt);Total Befolkning\n";
    
    if (popGroupVal === 'total') {
        window.allYears.forEach(y => {
            let numericY = Number(y);
            let isProg = numericY > window.baseYear;
            let source = isProg ? 'Prognos' : 'Historik';
            
            if (!isProg && window.histDataStore[numericY]) {
                csvContent += `"${numericY}";"${source}";"Totalt 16-74 år";${Math.round(window.histDataStore[numericY].pop)};0;${Math.round(window.histDataStore[numericY].pop)}\n`;
            } else if (isProg && window.progDataStore[numericY]) {
                let d = window.progDataStore[numericY];
                let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                let base = d.pop - induced;
                csvContent += `"${numericY}";"${source}";"Totalt 16-74 år";${Math.round(base)};${Math.round(induced)};${Math.round(d.pop)}\n`;
            }
        });
    } else {
        const groups = window.getGroupDefinitions(popGroupVal);
        const getPopForGroup = (yStr, group) => {
            let pop = 0;
            let records = currentPopData.filter(r => String(r.tid).trim() === yStr);
            if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === yStr.replace(' (Prognos)', ''));
            if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === String(window.baseYear)); 
            
            let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
            records.forEach(r => {
                if (!String(r.ålder).toLowerCase().includes('totalt')) {
                    let konStr = String(r.kön).trim().toLowerCase();
                    if (useGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                    if (group.sex && konStr !== group.sex) return;

                    const ageMatch = String(r.ålder).match(/\d+/);
                    if (ageMatch) {
                        const age = parseInt(ageMatch[0]);
                        let minAge = group.min !== undefined ? group.min : 0;
                        let maxAge = group.max !== undefined ? group.max : 999;
                        if (age >= minAge && age <= maxAge) {
                            pop += (r.Befolkning || 0);
                        }
                    }
                }
            });

            if (pop === 0 && yStr.includes('Prognos')) {
                let fallbackRecords = currentPopData.filter(r => String(r.tid).trim() === String(window.baseYear));
                let fallbackUseGender = fallbackRecords.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                fallbackRecords.forEach(r => {
                    if (!String(r.ålder).toLowerCase().includes('totalt')) {
                        let konStr = String(r.kön).trim().toLowerCase();
                        if (fallbackUseGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                        if (group.sex && konStr !== group.sex) return;
                        const ageMatch = String(r.ålder).match(/\d+/);
                        if (ageMatch) {
                            const age = parseInt(ageMatch[0]);
                            let minAge = group.min !== undefined ? group.min : 0;
                            let maxAge = group.max !== undefined ? group.max : 999;
                            if (age >= minAge && age <= maxAge) pop += (r.Befolkning || 0);
                        }
                    }
                });
            }
            return pop;
        };

        window.allYears.forEach(y => {
            let numericY = Number(y);
            let isProg = numericY > window.baseYear;
            let source = isProg ? 'Prognos' : 'Historik';
            let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
            
            let totalBase16_74 = getPopForGroup(searchStr, { min: 16, max: 74 });
            
            groups.forEach(g => {
                let groupBase = getPopForGroup(searchStr, g);
                let induced = 0;
                
                if (isProg && window.progDataStore[numericY] && causalityMode === 'dynamic') {
                    let totalInduced = window.progDataStore[numericY].inducedPop || 0;
                    induced = totalBase16_74 > 0 ? totalInduced * (groupBase / totalBase16_74) : 0;
                }
                
                let totalPop = groupBase + induced;
                
                if (!isProg && window.histDataStore[numericY]) {
                    csvContent += `"${numericY}";"${source}";"${g.label}";${Math.round(groupBase)};0;${Math.round(groupBase)}\n`;
                } else if (isProg && window.progDataStore[numericY]) {
                    csvContent += `"${numericY}";"${source}";"${g.label}";${Math.round(groupBase)};${Math.round(induced)};${Math.round(totalPop)}\n`;
                }
            });
        });
    }

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "Dynamisk_Befolkningsutveckling.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

window.exportSyssToCSV = function() {
    if (Object.keys(window.progDataStore).length === 0 && Object.keys(window.histDataStore).length === 0) {
        alert("Ingen data finns att exportera.");
        return;
    }
    
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; 
    csvContent += "År;Källa;Efterfrågan (Jobb);Lokalt Utbud (Nattbef.);Inpendling;Utpendling;Pendlingsnetto;Virtuellt Utbud;Totalt Utbud (Inkl. Pendling);Omatchat Gap;Befolkningsbehov;Sysselsättningsgrad (%);BRP per sysselsatt (tkr);Total BRP (Mkr);Arbetslöshet (%);Långtidsarbetslöshet (%)\n";
    
    const userSyssAdjustment = parseFloat(document.getElementById('migrantSyssSlider').value) / 100;
    const baseEmploymentRate = window.globalMigrantEmploymentRate || 0.50;
    const employmentRate = baseEmploymentRate + userSyssAdjustment;
    const simMode = document.getElementById('simMode').value;
    const showCommuting = simMode === 'full';

    const addRow = (y, d, isProg) => {
        if (!d) return;
        const source = isProg ? "Prognos" : "Historik";
        const dem = d.demand != null ? Number(d.demand) : 0;
        const sup = d.supply != null ? Number(d.supply) : 0;
        const inP = d.inpendling != null ? Number(d.inpendling) : 0;
        const utP = d.utpendling != null ? Number(d.utpendling) : 0;
        const explicitNet = d.explicitNetCommuting != null ? Number(d.explicitNetCommuting) : 0;
        const netP = d.netCommuting != null ? Number(d.netCommuting) : explicitNet;
        const vSup = d.virtualSupply != null ? Number(d.virtualSupply) : 0;
        const totPend = showCommuting ? (netP + vSup) : 0;
        const totSup = sup + totPend;
        const gap = dem - totSup;
        
        let befBehov = 0;
        if (gap > 5) befBehov = gap / Math.max(0.01, employmentRate);
        else if (gap < -5) befBehov = -Math.abs(gap); 
        
        const syssGrad = d.displayRate || 0;
        const brp = d.brp || d.extrapolatedBrp || 0;
        let totBrp = d.totalBrpMkr || 0;
        if (!totBrp && dem) totBrp = (brp * dem) / 1000;
        const arb = d.arbetsloshetPct !== null && d.arbetsloshetPct !== undefined ? d.arbetsloshetPct : "";
        const larb = d.langtidsPct !== null && d.langtidsPct !== undefined ? d.langtidsPct : "";

        csvContent += `"${y}";"${source}";${Math.round(dem)};${Math.round(sup)};${Math.round(inP)};${Math.round(utP)};${Math.round(netP)};${Math.round(vSup)};${Math.round(totSup)};${Math.round(gap)};${Math.round(befBehov)};${syssGrad.toFixed(2).replace('.', ',')};${brp.toFixed(1).replace('.', ',')};${Math.round(totBrp)};${arb !== "" ? arb.toFixed(2).replace('.', ',') : ""};${larb !== "" ? larb.toFixed(2).replace('.', ',') : ""}\n`;
    };

    const progYears = Object.keys(window.progDataStore).map(Number).sort((a,b)=>a-b);
    let histYears = Object.keys(window.histDataStore).map(Number).sort((a,b)=>a-b);
    
    if (progYears.length > 0) {
        histYears = histYears.slice(-5);
    }

    histYears.forEach(y => addRow(y, window.histDataStore[y], false));
    progYears.forEach(y => addRow(y, window.progDataStore[y], true));

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "Sysselsattningsprognos_Linkoping.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};