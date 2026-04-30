// ==========================================
// Kalkylator Motor 2035 - Kärnlogik & Databearbetning
// ==========================================

const appData = { historik: {}, config: {}, pop: [] };

let historiskData = {};
let prognos2035 = {};
let allYearsSet = new Set();

const baseYear = 2024;
const endYear = 2035;

async function fetchWithErr(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Filen ${url} saknas eller kunde inte läsas.`);
    let text = await res.text();
    text = text.replace(/:\s*NaN/g, ': null'); // Städar bort NaN
    return JSON.parse(text);
}

async function initEngine() {
    const statusEl = document.getElementById('dataStatus');
    try {
        const cb = '?v=' + new Date().getTime(); 
        
        const [syssBas, configBas, popBas] = await Promise.all([
            fetchWithErr('syss_basdata_2035.json' + cb),
            fetchWithErr('syss_config_2035.json' + cb),
            fetchWithErr('kalkylator_basdata_2035.json' + cb).catch(() => []) 
        ]);

        appData.historik = syssBas || {};
        appData.config = configBas || {};
        appData.pop = popBas || [];

        // Bygger BARA historiken
        byggHistoriskBaslinje();

        if(statusEl) {
            statusEl.innerHTML = '<i class="fa-solid fa-check"></i> 2035-Motorn Redo';
            statusEl.className = "p-1.5 px-3 bg-green-50 rounded border border-green-200 text-xs font-medium text-green-700";
        }
        
        // --- NYTT: Kör INTE prognosen direkt! Rita bara upp startläget (2024) ---
        byggaDropdown(baseYear);
        if (typeof renderDashboard === "function") renderDashboard();

    } catch (error) {
        if(statusEl) {
            statusEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Krasch: ${error.message}`;
            statusEl.className = "p-1.5 px-3 bg-red-50 rounded border border-red-200 text-xs font-medium text-red-700";
        }
        console.error("Fel i motorn:", error);
    }
}

function extractYear(row) {
    if (row['År'] !== undefined) return parseInt(row['År']);
    if (row['år'] !== undefined) return parseInt(row['år']);
    if (row['ÅR'] !== undefined) return parseInt(row['ÅR']);
    return null;
}

function getKon(r) {
    for (let k in r) { if (k.toLowerCase().trim() === 'kön') return String(r[k]).trim().toLowerCase(); }
    return null;
}

function getPopForYear(dataset, year) {
    let pop = 0;
    let searchStrProg = `${year} (Prognos)`;
    let searchStrHist = `${year}`;
    let records = dataset.filter(r => String(r.tid).trim() === searchStrProg);
    if (records.length === 0) records = dataset.filter(r => String(r.tid).trim() === searchStrHist);
    
    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');

    records.forEach(r => {
        if (!String(r.ålder).toLowerCase().includes('totalt')) {
            if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
            const match = String(r.ålder).match(/\d+/);
            if (match) {
                const age = parseInt(match[0]);
                if (age >= 16 && age <= 74) pop += (parseFloat(r.Befolkning) || 0);
            }
        }
    });
    return pop;
}

function byggHistoriskBaslinje() {
    historiskData = {};
    allYearsSet = new Set();
    
    const dfTillagg = appData.historik['Syss_tillägg'] || appData.historik['Syss_tillagg'] || [];
    const dfSyssGrad = appData.historik['Syssgrad'] || [];
    const dfBRP = appData.historik['BRP'] || [];
    const dfArb = appData.historik['Arbetslöshet'] || [];
    
    let years = new Set();
    dfTillagg.forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    
    const sortedYears = Array.from(years).filter(y => !isNaN(y)).sort((a,b)=>a-b);
    let brpHistory = [], lastKnownBRP = null, lastKnownBRPYear = null;

    sortedYears.forEach(y => {
        let dag = null, natt = null, inP = 0, utP = 0, hasPend = false;
        let d_m = 0, d_k = 0, n_m = 0, n_k = 0;
        
        dfTillagg.filter(r => extractYear(r) === y).forEach(r => {
            let typ = String(r['Typ']).toLowerCase();
            let kon = getKon(r);
            let val = parseFloat(r['Totalt'] || r['Samtliga'] || 0);
            
            if (typ.includes('dag')) { 
                if (kon === 'män') d_m = val; else if (kon === 'kvinnor') d_k = val; else if (kon === 'totalt' || !kon) dag = val;
                if (r['Pendling'] != null) { inP = parseFloat(r['Pendling']); hasPend = true; }
            }
            if (typ.includes('natt')) { 
                if (kon === 'män') n_m = val; else if (kon === 'kvinnor') n_k = val; else if (kon === 'totalt' || !kon) natt = val;
                if (r['Pendling'] != null) { utP = parseFloat(r['Pendling']); hasPend = true; }
            }
        });

        if (dag === null && (d_m > 0 || d_k > 0)) dag = d_m + d_k;
        if (natt === null && (n_m > 0 || n_k > 0)) natt = n_m + n_k;

        let fRate = null; 
        dfSyssGrad.filter(r => extractYear(r) === y).forEach(r => { 
            let kon = getKon(r);
            if(kon === 'totalt' || !kon) { if(r['Totalt 20-64 år']) fRate = parseFloat(r['Totalt 20-64 år']); }
        });
        
        const syssGradM = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'män');
        const syssGradK = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'kvinnor');

        let syss_in_tot = null, syss_ut_tot = null;
        if(appData.historik['Syssgrad_utrikes']) {
            const suRow = appData.historik['Syssgrad_utrikes'].find(r => extractYear(r) == y);
            if (suRow) {
                if (suRow['Inrikes_född_20-64_år_Totalt'] != null) syss_in_tot = parseFloat(suRow['Inrikes_född_20-64_år_Totalt']);
                if (suRow['Utrikes_född_20-64_år_Totalt'] != null) syss_ut_tot = parseFloat(suRow['Utrikes_född_20-64_år_Totalt']);
            }
        }

        let brpPer = null; 
        dfBRP.filter(r => extractYear(r) === y).forEach(r => { 
            if(r['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)']) {
                brpPer = parseFloat(r['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)']); 
                lastKnownBRP = brpPer; lastKnownBRPYear = y; brpHistory.push({year: y, val: brpPer});
            }
        });

        let arb = null, arb_in = null, arb_ut = null, arb_m = null, arb_k = null;
        dfArb.filter(r => extractYear(r) === y).forEach(r => {
            let keys = Object.keys(r).filter(k => String(k).toLowerCase().includes('%') || String(k).toLowerCase().includes('andel')); 
            if(keys.length) arb = parseFloat(r[keys[0]]);
            const inKey = keys.find(k => k.toLowerCase().includes('inrikes'));
            const utKey = keys.find(k => k.toLowerCase().includes('utrikes'));
            if(inKey) arb_in = parseFloat(r[inKey]); if(utKey) arb_ut = parseFloat(r[utKey]);
            const mKeyArb = keys.find(k => { const kl = k.toLowerCase(); return (kl.includes('män') || kl.includes('man')) && !kl.includes('kvinna'); });
            const kKeyArb = keys.find(k => k.toLowerCase().includes('kvinnor') || k.toLowerCase().includes('kvinna'));
            if(mKeyArb) arb_m = parseFloat(r[mKeyArb]); if(kKeyArb) arb_k = parseFloat(r[kKeyArb]);
        });

        let pop16_74 = getPopForYear(appData.pop, y);
        if(pop16_74 === 0 && natt > 0) pop16_74 = natt / 0.70; 

        if (y <= baseYear && dag != null && natt != null) {
            historiskData[y] = { 
                demand: dag, supply: natt, inpendling: hasPend ? inP : null, utpendling: hasPend ? utP : null,
                netCommuting: hasPend ? (inP - utP) : null, totalSupply: hasPend ? (natt + inP - utP) : natt,
                displayRate: fRate, brp: brpPer, extrapolatedBrp: brpPer, pop: pop16_74,
                syssGradM: syssGradM, syssGradK: syssGradK, syss_in_tot: syss_in_tot, syss_ut_tot: syss_ut_tot,
                arbetsloshetPct: arb, arb_inrikes: arb_in, arb_utrikes: arb_ut,
                n_man: n_m, n_kvinna: n_k, d_man: d_m, d_kvinna: d_k, arb_man: arb_m, arb_kvinna: arb_k
            };
            allYearsSet.add(y);
        }
    });

    let brpCAGR = 0.015; 
    if (brpHistory.length >= 2) {
        let first = brpHistory[Math.max(0, brpHistory.length - 11)]; let last = brpHistory[brpHistory.length - 1];
        let yDiff = last.year - first.year;
        if (yDiff > 0 && first.val > 0) brpCAGR = Math.pow(last.val / first.val, 1 / yDiff) - 1; 
    }
    sortedYears.forEach(y => {
        if (historiskData[y] && historiskData[y].brp === null && lastKnownBRP !== null && y > lastKnownBRPYear) {
            historiskData[y].extrapolatedBrp = lastKnownBRP * Math.pow(1 + brpCAGR, y - lastKnownBRPYear);
        }
    });
}

function setScenario(type) {
    const sc = appData.config['Scenarier'];
    if (!sc) return;
    const getVal = (indikator) => {
        let row = sc.find(r => String(r.Indikator).trim() === indikator);
        if(row) {
            if (type === 'base') return parseFloat(row['Bas']);
            if (type === 'high') return parseFloat(row['Hög']);
            if (type === 'low') return parseFloat(row['Låg']);
            if (type === 'stagnant') return parseFloat(row['Stagnerande']);
        } return 0;
    };
    const setSlider = (id, val, suffix) => {
        const sliderEl = document.getElementById(id);
        if (sliderEl) { sliderEl.value = val || 0; const textEl = document.getElementById(id.replace('Slider', 'Val')); if (textEl) textEl.innerText = (val > 0 ? '+' : '') + val + suffix; }
    };
    setSlider('jobGrowthSlider', getVal('Jobbtillväxt'), '%');
    setSlider('syssGradSlider', getVal('Sysselsättningsgrad'), '%-enh');
    setSlider('studentSlider', getVal('Kvarstannandegrad'), '%-enh');
    const intVal = getVal('Justering inflyttares syss.grad');
    setSlider('migrantSyssSlider', intVal, '%-enh');
    setSlider('inpendlingSlider', getVal('Inpendling'), '%'); setSlider('utpendlingSlider', getVal('Utpendling'), '%');
    
    // När användaren aktivt väljer ett scenario, DÅ körs prognosen!
    runSimulation2035();
}

function runSimulation2035() {
    const btn = document.getElementById('simBtn');
    if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Simulerar...';
    
    setTimeout(() => {
        prognos2035 = {};
        
        const jobGrowthMultiplier = parseFloat(document.getElementById('jobGrowthSlider') ? document.getElementById('jobGrowthSlider').value : 0) / 100;
        const syssGradBoost = parseFloat(document.getElementById('syssGradSlider') ? document.getElementById('syssGradSlider').value : 0);
        const studentChange = parseFloat(document.getElementById('studentSlider') ? document.getElementById('studentSlider').value : 0);
        const inpendlingBoostPct = parseFloat(document.getElementById('inpendlingSlider') ? document.getElementById('inpendlingSlider').value : 0) / 100;
        const utpendlingBoostPct = parseFloat(document.getElementById('utpendlingSlider') ? document.getElementById('utpendlingSlider').value : 0) / 100;
        const causality = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
        const simMode = document.getElementById('simMode') ? document.getElementById('simMode').value : 'full';
        const popSource = document.getElementById('popSource') ? document.getElementById('popSource').value : 'fryst';

        const bas = historiskData[baseYear] || { demand: 80000, supply: 75000, inpendling: 15000, utpendling: 10000, pop: 115000, displayRate: 80, arbetsloshetPct: 5 };
        
        let accDemand = bas.demand;
        let dynPopAccumulated = 0;   
        let dynLaborAccumulated = 0; 
        let cumulativeExtraStudents = 0; 
        let structuralInpendlingAccumulated = 0;

        let share_n_man = (bas.n_man + bas.n_kvinna > 0) ? (bas.n_man / (bas.n_man + bas.n_kvinna)) : 0.5;
        let share_d_man = (bas.d_man + bas.d_kvinna > 0) ? (bas.d_man / (bas.d_man + bas.d_kvinna)) : 0.5;
        let share_n_ut = (bas.n_utrikes + bas.n_inrikes > 0) ? (bas.n_utrikes / (bas.n_utrikes + bas.n_inrikes)) : 0.2;
        let share_d_ut = (bas.d_utrikes + bas.d_inrikes > 0) ? (bas.d_utrikes / (bas.d_utrikes + bas.d_inrikes)) : 0.2;

        for (let y = 2025; y <= endYear; y++) {
            
            // --- A. EFTERFRÅGAN OCH BOSÄTTNINGSKVOT ---
            let jobDeltaDettaAr = 0;
            let structuralInpendlingDettaAr = 0;

            if (appData.config['Näringslivsjustering']) {
                appData.config['Näringslivsjustering'].forEach(row => {
                    let bransch = row['SNIbokstav']; 
                    let valY = parseFloat(row[String(y)]) || 0;
                    let valPrev = parseFloat(row[String(y-1)]) || 0;
                    
                    let deltaTotal = (valY - valPrev) * (1 + jobGrowthMultiplier);
                    jobDeltaDettaAr += deltaTotal;

                    let bKvot = 0.60; 
                    if (appData.historik['Bosättningskvot_bransch']) {
                        let bRow = appData.historik['Bosättningskvot_bransch'].find(r => String(r['År']) === '2021');
                        if (bRow && bRow[bransch] !== undefined) {
                            bKvot = Math.max(0, Math.min(1, parseFloat(bRow[bransch]))); 
                        }
                    }
                    structuralInpendlingDettaAr += (deltaTotal * (1 - bKvot));
                });
            } else {
                jobDeltaDettaAr = bas.demand * (jobGrowthMultiplier / 10);
                structuralInpendlingDettaAr = jobDeltaDettaAr * 0.4; 
            }

            accDemand += jobDeltaDettaAr;
            structuralInpendlingAccumulated += structuralInpendlingDettaAr;

            // --- B. UTBUD ---
            let basePopForYear = bas.pop;
            if (popSource === 'officiell' && appData.pop && appData.pop.length > 0) {
                let p = getPopForYear(appData.pop, y);
                if (p > 0) basePopForYear = p;
            }
            
            let currentSyssGrad = (bas.displayRate || 80) + syssGradBoost * ((y - baseYear)/10);
            let currentBaseSupply = basePopForYear * (currentSyssGrad / 100);

            let extraStudentsThisYear = 3500 * (studentChange / 100);
            cumulativeExtraStudents += extraStudentsThisYear;
            currentBaseSupply += cumulativeExtraStudents;

            // --- C. PENDLING ---
            let inpendling = (bas.inpendling || 0) + structuralInpendlingAccumulated;
            inpendling = inpendling * (1 + (inpendlingBoostPct * ((y - baseYear)/10)));
            let utpendling = (bas.utpendling || 0) * (1 + (utpendlingBoostPct * ((y - baseYear)/10)));
            
            if (simMode === 'local') {
                inpendling = (bas.inpendling || 0);
                utpendling = (bas.utpendling || 0);
            }

            // --- D. GAP & DYNAMISK JÄMVIKT ---
            let totSupplyInklPendling = currentBaseSupply + dynLaborAccumulated + inpendling - utpendling;
            let gap = accDemand - totSupplyInklPendling;
            let induceradBefolkningDettaAr = 0;

            if (causality === 'dynamic' && gap > 0) {
                let sliderEl = document.getElementById('migrantSyssSlider');
                let syssGradInflyttare = Math.max(0.01, 0.50 + ((sliderEl ? parseFloat(sliderEl.value) : 10) / 100));
                
                induceradBefolkningDettaAr = gap / syssGradInflyttare;
                dynPopAccumulated += induceradBefolkningDettaAr;
                dynLaborAccumulated += gap;
                
                totSupplyInklPendling += gap;
            }

            let futureSupply = currentBaseSupply + dynLaborAccumulated;
            
            prognos2035[y] = {
                demand: accDemand, supply: futureSupply, inpendling: inpendling, utpendling: utpendling,
                netCommuting: inpendling - utpendling, totalSupply: totSupplyInklPendling,
                pop: basePopForYear + dynPopAccumulated, inducedPop: dynPopAccumulated, 
                displayRate: currentSyssGrad, brp: accDemand * 0.85, 
                arbetsloshetPct: (bas.arbetsloshetPct || 5) - syssGradBoost * ((y - baseYear)/10),
                
                syss_in_tot: bas.syss_in_tot != null ? bas.syss_in_tot + syssGradBoost * ((y - baseYear)/10) : null,
                syss_ut_tot: bas.syss_ut_tot != null ? bas.syss_ut_tot + syssGradBoost * ((y - baseYear)/10) : null,
                n_man: futureSupply * share_n_man, n_kvinna: futureSupply * (1 - share_n_man),
                d_man: accDemand * share_d_man, d_kvinna: accDemand * (1 - share_d_man),
                arb_inrikes: bas.arb_inrikes != null ? bas.arb_inrikes - syssGradBoost * ((y - baseYear)/10) : null,
                arb_utrikes: bas.arb_utrikes != null ? bas.arb_utrikes - syssGradBoost * ((y - baseYear)/10) : null,
                arb_man: bas.arb_man != null ? bas.arb_man - syssGradBoost * ((y - baseYear)/10) : null,
                arb_kvinna: bas.arb_kvinna != null ? bas.arb_kvinna - syssGradBoost * ((y - baseYear)/10) : null
            };
            allYearsSet.add(y);
        }

        // Tvinga rullistan att byta till 2035 när vi har kört klart
        byggaDropdown(endYear);
        if (typeof renderDashboard === "function") renderDashboard();

        if (btn) { btn.innerHTML = '<i class="fa-solid fa-check"></i> Klar'; setTimeout(() => btn.innerHTML = '<i class="fa-solid fa-gears"></i> Kör 2035-Prognos', 1500); }
    }, 50);
}

function byggaDropdown(forceYear = null) {
    const ySelect = document.getElementById('yearSelect');
    if (!ySelect) return;
    
    const pVal = ySelect.value;
    ySelect.innerHTML = '';
    
    let arr = Array.from(allYearsSet).sort((a,b)=>b-a);
    arr.forEach(y => {
        let text = y > baseYear ? y + " (Prognos)" : y;
        let opt = new Option(text, y);
        if (y > baseYear) opt.className = "text-sky-700 font-bold bg-sky-50";
        ySelect.add(opt);
    });
    
    if (forceYear !== null) {
        ySelect.value = forceYear;
    } else {
        ySelect.value = pVal && arr.includes(parseInt(pVal)) ? pVal : endYear;
    }
}

window.addEventListener('DOMContentLoaded', initEngine);