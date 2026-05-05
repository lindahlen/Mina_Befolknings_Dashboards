// ==========================================
// Grafer & UI 2035 - Visuell representation
// ==========================================

// --- DYNAMISK INJICERING AV PENDLINGSDIAGRAMMET ---
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        try {
            const chartTypeSelect = document.getElementById('chartType');
            if (chartTypeSelect && !chartTypeSelect.querySelector('option[value="pendling_detalj"]')) {
                const optGroup = document.createElement('optgroup');
                optGroup.label = "── Pendling ──";
                const opt = new Option("In- och utpendling (Kommungräns)", "pendling_detalj");
                optGroup.appendChild(opt);
                
                let brpOpt = chartTypeSelect.querySelector('option[value="brp_totalt"]');
                if (brpOpt && brpOpt.nextSibling) {
                    chartTypeSelect.insertBefore(optGroup, brpOpt.nextSibling);
                } else {
                    chartTypeSelect.add(opt);
                }
            }
        } catch(e) { console.error("Kunde inte injicera Pendlingsdiagram", e); }
    }, 500); // Liten fördröjning för att säkra att DOM är redo
});

// --- RULLISTOR OCH NYCKELTAL ---
function buildDropdowns() {
    try {
        const ySel = document.getElementById('yearSelect');
        const sSel = document.getElementById('startYearSelect');
        if (!ySel || !sSel) return;
        
        const pY = ySel.value;
        const pS = sSel.value;
        
        const progYears = typeof progDataStore !== 'undefined' && progDataStore ? Object.keys(progDataStore).map(Number) : [];
        const histYears = typeof histYearsGlobal !== 'undefined' && histYearsGlobal ? histYearsGlobal : [];
        const bYear = typeof baseYear !== 'undefined' ? baseYear : 0;
        
        allYears = [...new Set([...histYears, ...progYears])].sort((a,b)=>a-b);
        
        ySel.innerHTML = ''; 
        sSel.innerHTML = '';
        
        // 1. Fyll "Granska År"
        if (allYears.length > 0) {
            [...allYears].reverse().forEach(y => { 
                let o = new Option(y > bYear ? y + " (Prognos)" : y, y); 
                if (y > bYear) o.className = "text-sky-700 font-bold bg-sky-50"; 
                ySel.add(o); 
            }); 
            let endYear = typeof PROGNOS_SLUTAR !== 'undefined' ? PROGNOS_SLUTAR : allYears[0];
            ySel.value = pY && allYears.includes(parseInt(pY)) ? pY : endYear; 
        } else {
            ySel.add(new Option("Data saknas", ""));
        }
        
        // 2. Fyll "Startår"
        if (histYears.length > 0) { 
            let requestedYears = new Set([1975, 1990, 2000, 2010, 2015, 2020]);
            let rolling10 = bYear > 10 ? bYear - 10 : null;
            if (rolling10) requestedYears.add(rolling10);

            let validStarts = Array.from(requestedYears).filter(y => histYears.includes(y)).sort((a,b) => b-a); 
            if (validStarts.length === 0) validStarts = [histYears[Math.max(0, histYears.length - 11)]];

            validStarts.forEach(y => sSel.add(new Option('Från ' + y, y))); 
            
            let defaultStart = rolling10 && validStarts.includes(rolling10) ? rolling10 : validStarts[0];
            sSel.value = pS && validStarts.includes(parseInt(pS)) ? pS : defaultStart; 
        } else {
            sSel.add(new Option("Data saknas", ""));
        }
    } catch(e) { console.error("Krasch i buildDropdowns:", e); }
}

function handleYearChange() {
    try {
        updateKPIs();
        const chartTypeElement = document.getElementById('chartType');
        if (!chartTypeElement) return;
        const chartType = chartTypeElement.value;
        
        // Uppdatera endast grafen om det är ett diagram som visar valt år (Matchning)
        if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
            updateDashboard(true);
        }
    } catch(e) { console.error("Krasch i handleYearChange:", e); }
}

function updateKPIs() {
    try {
        let ySelect = document.getElementById('yearSelect');
        if (!ySelect || !ySelect.value) return;
        
        let y = parseInt(ySelect.value);
        let d = y <= baseYear ? histDataStore[y] : (progDataStore[y] || histDataStore[y]);
        if (!d) return;

        document.getElementById('kpiEfterfragan').innerText = d.demand != null ? formatNumber(d.demand, 0) : 'Data saknas';
        
        if (d.isAgeWeighted) {
            document.getElementById('kpiUtbud').innerHTML = `${formatNumber(d.supply, 0)} <span class="text-xs text-sky-400" title="Åldersviktad beräkning aktiv">*</span>`;
            document.getElementById('kpiUtbudContainer').title = "Lokalt arbetskraftsutbud (Åldersviktad beräkning)";
        } else {
            document.getElementById('kpiUtbud').innerText = d.supply != null ? formatNumber(d.supply, 0) : 'Data saknas';
            document.getElementById('kpiUtbudContainer').title = "Lokalt arbetskraftsutbud";
        }
        
        const kpiBef = document.getElementById('kpiBefolkning');
        const kpiBefContainer = document.getElementById('kpiBefolkningContainer');
        const warningEl = document.getElementById('takWarning');
        const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
        
        const simModeEl = document.getElementById('simMode');
        const showCommuting = simModeEl && simModeEl.value === 'full';

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
            if (kpiPendling) {
                kpiPendling.innerText = (totalPendling > 0 ? '+' : '') + formatNumber(totalPendling, 0);
                kpiPendling.className = "text-base md:text-lg font-bold " + (totalPendling > 0 ? "text-indigo-600" : (showCommuting ? "text-emerald-600" : "text-gray-400"));
                
                if (!showCommuting) {
                    kpiPendling.title = "Pendling inaktiverad i läget 'Endast Lokal'.";
                    kpiPendling.innerText = '-';
                } else if (virtualExt > 0) {
                    const komText = d.antalKommunerBeraknade ? ` för ${d.antalKommunerBeraknade} grannkommuner` : '';
                    kpiPendling.title = `Faktisk pendling: ${formatNumber(explNetto, 0)}.\nVirtuellt Pendlingsutbud: ${formatNumber(virtualExt, 0)} ${komText}.`;
                } else {
                    kpiPendling.title = "Totalt Pendlingsnetto";
                }
            }

            let inpendlingAndel = (d.inpendling != null && d.demand > 0) ? (d.inpendling / d.demand) * 100 : 0;
            if (typeof takEffekter !== 'undefined' && inpendlingAndel > takEffekter.maxInpendlingsandel) {
                warnings.push({icon: 'fa-car-side', color: 'amber', text: 'Hög inpendlingsandel', title: `Varning: Inpendlingsandel (${formatNumber(inpendlingAndel, 1)}%) överstiger ${takEffekter.maxInpendlingsandel}%.`});
            }
            
            let totalPendlingFysisk = (d.inpendling || 0) + (d.utpendling || 0);
            if (typeof takEffekter !== 'undefined' && totalPendlingFysisk > takEffekter.kapacitetstakInfrastruktur) {
                warnings.push({icon: 'fa-train', color: 'red', text: 'Infrastruktur överbelastad', title: `Varning: Fysisk pendling (${formatNumber(totalPendlingFysisk, 0)} resor/dag) överstiger taket på ${formatNumber(takEffekter.kapacitetstakInfrastruktur, 0)}.`});
            }

            if (kpiBef && kpiBefContainer) {
                if (causalityMode === 'dynamic' && d.inducedPop !== undefined) {
                    if (d.inducedPop > 0) {
                        kpiBef.innerText = '+' + formatNumber(d.inducedPop, 0);
                        kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                        kpiBefContainer.title = `Dynamisk jämvikt:\n${formatNumber(d.inducedPop, 0)} nya invånare har simulerats flytta in.`;
                        
                        if (d.reqForeignLabor > 0) {
                            warnings.push({icon: 'fa-globe', color: 'amber', text: 'Arbetskraftsinv. behövs', title: `Ca ${formatNumber(d.reqForeignLabor, 0)} arbetare måste rekryteras internationellt pga demografiska gränser.`});
                        }
                    } else {
                        kpiBef.innerText = 'Balans';
                        kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                        kpiBefContainer.title = "Dynamisk jämvikt: Utbud och pendling täcker behovet.";
                    }
                } else {
                    const omatchatGap = d.demand - (d.supply + totalPendling);
                    if (omatchatGap > 5) {
                        const migrantSyssSlider = document.getElementById('migrantSyssSlider');
                        const userSyssAdjustment = (migrantSyssSlider ? parseFloat(migrantSyssSlider.value) : 10) / 100;
                        const employmentRate = (typeof globalMigrantEmploymentRate !== 'undefined' ? globalMigrantEmploymentRate : 0.50) + userSyssAdjustment;
                        let totalPopNeeded = omatchatGap / Math.max(0.01, employmentRate); 

                        kpiBef.innerText = '+' + formatNumber(totalPopNeeded, 0);
                        kpiBef.className = "text-base md:text-lg font-bold text-orange-600";
                        kpiBefContainer.title = `Analys av gap:\nDet kvarstår ett gap på ${formatNumber(omatchatGap, 0)} jobb.\nFör att fylla detta krävs inflyttning av ca ${formatNumber(totalPopNeeded, 0)} nya invånare.`;
                    } else if (omatchatGap < -5) {
                        kpiBef.innerText = 'Överskott';
                        kpiBef.className = "text-base md:text-lg font-bold text-sky-600";
                        kpiBefContainer.title = `Lokalt utbud är ${formatNumber(Math.abs(omatchatGap), 0)} personer högre än tillgängliga jobb.`;
                        warnings.push({icon: 'fa-leaf', color: 'green', text: 'Arbetskraftsöverskott', title: `Lokalt utbud överstiger efterfrågan.`});
                    } else {
                        kpiBef.innerText = 'Balans';
                        kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                        kpiBefContainer.title = "Perfekt matchning. Inget kvarstående rekryteringsgap.";
                        warnings.push({icon: 'fa-check', color: 'green', text: 'Arbetsmarknad i balans', title: `Utbud och Efterfrågan möts perfekt.`});
                    }
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
                kpiSyssGrad.innerText = formatNumber(d.displayRate, 1) + '%';
                if (typeof takEffektMaxSyss !== 'undefined' && d.displayRate > takEffektMaxSyss) {
                    kpiSyssGrad.className = "text-base md:text-lg font-bold text-red-600";
                    warnings.push({icon: 'fa-triangle-exclamation', color: 'red', text: 'Arbetskraftsbrist', title: `Varning: Sysselsättningsgraden (${formatNumber(d.displayRate, 1)}%) överstiger taket på ${takEffektMaxSyss}%.`});
                } else if (causalityMode === 'analytic' && !(d.demand != null && d.supply != null && (d.demand - (d.supply + (d.netCommuting !== undefined ? d.netCommuting : (d.explicitNetCommuting || 0)) + (d.virtualSupply || 0))) <= -5) ) {
                    kpiSyssGrad.className = "text-base md:text-lg font-bold text-gray-800";
                }
            } else {
                kpiSyssGrad.innerText = 'Data saknas';
            }
        }

        if (d.arbetsloshetPct != null && typeof takEffekter !== 'undefined' && d.arbetsloshetPct < takEffekter.minArbetsloshet) {
            warnings.push({icon: 'fa-fire', color: 'orange', text: 'Under friktionsgräns', title: `Varning: Arbetslösheten (${formatNumber(d.arbetsloshetPct, 1)}%) är lägre än friktionsgränsen på ${takEffekter.minArbetsloshet}%.`});
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
        const kpiBRPEl = document.getElementById('kpiBRP');

        if (kpiBRPEl && kpiBox) {
            if (displayBrp != null) {
                let tkrText = formatNumber(displayBrp, 1) + ' tkr';
                let totalBrpMkr = d.totalBrpMkr;
                if (!totalBrpMkr && d.demand) totalBrpMkr = (displayBrp * d.demand) / 1000;

                if (d.brp === null && d.extrapolatedBrp != null && y <= baseYear) {
                    kpiBRPEl.innerHTML = `<span class="text-slate-400 italic" title="Extrapolerat värde (SCB-data saknas ännu)">${tkrText}*</span>`;
                } else {
                    kpiBRPEl.innerText = tkrText;
                }

                if (totalBrpMkr) {
                    kpiBox.title = `Total Regional Ekonomi (BRP): ca ${formatNumber(totalBrpMkr, 0)} Mkr\n(Beräknat som BRP/syss × Dagbefolkning)`;
                } else {
                    kpiBox.title = "Bruttoregionalprodukt per sysselsatt (tkr)";
                }
            } else {
                kpiBRPEl.innerText = 'Data saknas';
                kpiBox.title = "Bruttoregionalprodukt per sysselsatt (tkr)";
            }
        }
    } catch (e) { console.error("Fel i updateKPIs:", e); }
}

// --- DATA EXPORT OCH MATCHNINGS-HJÄLPARE ---
function getGroupDefinitions(popGroupVal) {
    let groups = [];
    if (popGroupVal === 'func') {
        groups = [
            { label: '16-19 år', sex: null, min: 16, max: 19, color: '#0284c7' },
            { label: '20-24 år', sex: null, min: 20, max: 24, color: '#10b981' },
            { label: '25-64 år', sex: null, min: 25, max: 64, color: '#8b5cf6' },
            { label: '65-74 år', sex: null, min: 65, max: 74, color: '#f59e0b' }
        ];
    } else if (popGroupVal === '5yr') {
        const colors = ['#0284c7', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#14b8a6', '#f97316', '#84cc16', '#64748b', '#d946ef'];
        groups.push({ label: '16-19 år', sex: null, min: 16, max: 19, color: colors[0] });
        let colorIdx = 1;
        for (let i = 20; i <= 70; i += 5) {
            let end = (i === 70) ? 74 : i+4;
            groups.push({ label: `${i}-${end} år`, sex: null, min: i, max: end, color: colors[colorIdx % colors.length] });
            colorIdx++;
        }
    }
    return groups;
}

function exportPopDynamicCSV() {
    const popGroupSelect = document.getElementById('subGroupSelect');
    const popGroupVal = popGroupSelect ? popGroupSelect.value : 'total';
    const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
    const currentPopData = (typeof useCustomPop !== 'undefined' && useCustomPop && customPopData) ? customPopData : popData;
    
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; 
    csvContent += "År;Källa;Grupp;Basbefolkning;Tillskott (Dynamisk Jämvikt);Total Befolkning\n";
    
    if (popGroupVal === 'total') {
        allYears.forEach(y => {
            let numericY = Number(y);
            let isProg = numericY > baseYear;
            let source = isProg ? 'Prognos' : 'Historik';
            
            if (!isProg && histDataStore[numericY]) {
                csvContent += `"${numericY}";"${source}";"Totalt 16-74 år";${Math.round(histDataStore[numericY].pop)};0;${Math.round(histDataStore[numericY].pop)}\n`;
            } else if (isProg && progDataStore[numericY]) {
                let d = progDataStore[numericY];
                let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                let base = d.pop - induced;
                csvContent += `"${numericY}";"${source}";"Totalt 16-74 år";${Math.round(base)};${Math.round(induced)};${Math.round(d.pop)}\n`;
            }
        });
    } else {
        const groups = getGroupDefinitions(popGroupVal);
        const getPopForGroup = (yStr, group) => {
            let pop = 0;
            let records = currentPopData.filter(r => String(r.tid).trim() === yStr);
            if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === yStr.replace(' (Prognos)', ''));
            if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === String(baseYear)); 
            
            let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
            records.forEach(r => {
                if (!String(r.ålder).toLowerCase().includes('totalt')) {
                    let konStr = String(r.kön).trim().toLowerCase();
                    if (useGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                    if (group.sex && konStr !== group.sex) return;
                    const match = String(r.ålder).match(/\d+/);
                    if (match) {
                        const age = parseInt(match[0]);
                        let minAge = group.min !== undefined ? group.min : 0;
                        let maxAge = group.max !== undefined ? group.max : 999;
                        if (age >= minAge && age <= maxAge) pop += (r.Befolkning || 0);
                    }
                }
            });
            return pop;
        };

        allYears.forEach(y => {
            let numericY = Number(y);
            let isProg = numericY > baseYear;
            let source = isProg ? 'Prognos' : 'Historik';
            let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
            
            let totalBase16_74 = getPopForGroup(searchStr, { min: 16, max: 74 });
            
            groups.forEach(g => {
                let groupBase = getPopForGroup(searchStr, g);
                let induced = 0;
                
                if (isProg && progDataStore[numericY] && causalityMode === 'dynamic') {
                    let totalInduced = progDataStore[numericY].inducedPop || 0;
                    induced = totalBase16_74 > 0 ? totalInduced * (groupBase / totalBase16_74) : 0;
                }
                
                let totalPop = groupBase + induced;
                if (!isProg && histDataStore[numericY]) {
                    csvContent += `"${numericY}";"${source}";"${g.label}";${Math.round(groupBase)};0;${Math.round(groupBase)}\n`;
                } else if (isProg && progDataStore[numericY]) {
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
}

function exportSyssToCSV() {
    if (Object.keys(progDataStore).length === 0 && Object.keys(histDataStore).length === 0) {
        alert("Ingen data finns att exportera."); return;
    }
    
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; 
    csvContent += "År;Källa;Efterfrågan (Jobb);Lokalt Utbud (Nattbef.);Inpendling;Utpendling;Pendlingsnetto;Virtuellt Utbud;Totalt Utbud (Inkl. Pendling);Omatchat Gap;Befolkningsbehov;Sysselsättningsgrad (%);BRP per sysselsatt (tkr);Total BRP (Mkr);Arbetslöshet (%);Långtidsarbetslöshet (%)\n";
    
    const userSyssAdjustment = parseFloat(document.getElementById('migrantSyssSlider').value) / 100;
    const baseEmploymentRate = typeof globalMigrantEmploymentRate !== 'undefined' ? globalMigrantEmploymentRate : 0.50;
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

    const progYears = Object.keys(progDataStore).map(Number).sort((a,b)=>a-b);
    let histYears = Object.keys(histDataStore).map(Number).sort((a,b)=>a-b);
    if (progYears.length > 0) histYears = histYears.slice(-5);

    histYears.forEach(y => addRow(y, histDataStore[y], false));
    progYears.forEach(y => addRow(y, progDataStore[y], true));

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "Sysselsattningsprognos_Linkoping.csv");
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
}

function aggregateMatchData(dataset, refYear, labels, keyField, mapFn = null) {
    let result = { 'män': {}, 'kvinnor': {}, 'totalt': {} };
    labels.forEach(l => { result['män'][l] = 0; result['kvinnor'][l] = 0; result['totalt'][l] = 0; });
    
    let records = dataset.filter(r => {
        let rY = r['År'] !== undefined ? parseInt(r['År']) : (r['år'] !== undefined ? parseInt(r['år']) : null);
        return rY == refYear;
    });
    if (records.length === 0) return result;
    
    let hasKonCol = records.some(r => {
        for(let k in r) if(k.toLowerCase().trim() === 'kön') return r[k] !== null; return false;
    });
    let hasTotalRow = false;
    if (hasKonCol) {
        hasTotalRow = records.some(r => {
            for(let k in r) if(k.toLowerCase().trim() === 'kön') return String(r[k]).trim().toLowerCase() === 'totalt' || String(r[k]).trim() === ''; return false;
        });
    }
    
    records.forEach(r => {
        let kon = 'totalt';
        for(let k in r) if(k.toLowerCase().trim() === 'kön') kon = String(r[k]).trim().toLowerCase() || 'totalt';
        
        let isCountableTotal = false;
        if (!hasKonCol) isCountableTotal = true;
        else if (hasTotalRow) isCountableTotal = (kon === 'totalt');
        else isCountableTotal = (kon === 'män' || kon === 'kvinnor');
        
        if (keyField === 'Cols') {
            Object.keys(r).forEach(k => {
                let key = mapFn ? mapFn(k) : k;
                if (labels.includes(key)) {
                    let val = parseFloat(r[k]) || 0;
                    if (kon === 'män' || kon === 'kvinnor') result[kon][key] += val;
                    if (isCountableTotal) result['totalt'][key] += val;
                }
            });
        } else {
            let rawKey = String(r[keyField] || '').trim();
            let key = mapFn ? mapFn(rawKey) : rawKey;
            
            if (labels.includes(key)) {
                if (r['Män'] !== undefined || r['män'] !== undefined || r['Kvinnor'] !== undefined || r['kvinnor'] !== undefined) {
                    let mVal = parseFloat(r['Män'] || r['män'] || 0);
                    let kVal = parseFloat(r['Kvinnor'] || r['kvinnor'] || 0);
                    let tVal = parseFloat(r['Totalt'] || r['totalt'] || (mVal + kVal));
                    
                    result['män'][key] += mVal;
                    result['kvinnor'][key] += kVal;
                    if (isCountableTotal) result['totalt'][key] += tVal;
                } else {
                    let val = parseFloat(r['Totalt'] ?? r['Samtliga'] ?? r['Befolkning'] ?? r['Värde'] ?? r['Antal'] ?? 0);
                    if (isNaN(val)) val = 0;
                    if (kon === 'män' || kon === 'kvinnor') result[kon][key] += val;
                    if (isCountableTotal) result['totalt'][key] += val;
                }
            }
        }
    });
    return result;
}

function drawMatchChart(year, labels, dagData, nattData, splitGender, useZeroAxis, isHorizontal = false) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();
    
    let isProg = progDataStore[year] !== undefined;

    if (isProg && histDataStore[baseYear]) {
        const progD = progDataStore[year];
        const baseD = histDataStore[baseYear];
        const simMode = document.getElementById('simMode').value;
        const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
        const demandScale = progD.demand / baseD.demand;
        const supplyScale = simMode === 'full' ? (progD.totalSupply / baseD.totalSupply) : (progD.supply / baseD.supply);
        
        ['totalt', 'män', 'kvinnor'].forEach(kon => {
            labels.forEach(l => {
                if (dagData[kon] && dagData[kon][l] !== undefined) dagData[kon][l] *= demandScale;
                if (nattData[kon] && nattData[kon][l] !== undefined) nattData[kon][l] *= supplyScale;
            });
        });

        if (currentShocks.length > 0) {
            currentShocks.forEach(shock => {
                if (parseInt(shock['År']) <= year && shock['Bransch']) {
                    const bName = String(shock['Bransch']).trim();
                    const val = parseFloat(shock['Antal_Jobb']) || 0;
                    if (dagData['totalt'] && dagData['totalt'][bName] !== undefined) {
                        dagData['totalt'][bName] += val;
                        
                        let mShare = 0.5; 
                        if (shock['Andel_Män'] !== undefined && shock['Andel_Män'] !== null && String(shock['Andel_Män']).trim() !== '') {
                            let andelMStr = String(shock['Andel_Män']).trim();
                            let parsed = parseFloat(andelMStr.replace('%', '').replace(',', '.'));
                            if (!isNaN(parsed)) mShare = andelMStr.includes('%') || parsed > 1 ? parsed / 100 : parsed;
                        }
                        
                        if(dagData['män']) dagData['män'][bName] += val * mShare;
                        if(dagData['kvinnor']) dagData['kvinnor'][bName] += val * (1 - mShare);

                        if (causalityMode === 'dynamic') {
                            nattData['totalt'][bName] += val;
                            if(nattData['män']) nattData['män'][bName] += val * mShare;
                            if(nattData['kvinnor']) nattData['kvinnor'][bName] += val * (1 - mShare);
                        }
                    }
                }
            });
        }
    }

    let datasets = [];
    
    if (splitGender) {
        datasets = [
            { label: 'Efterfrågan (Män)', data: labels.map(l => dagData['män'][l]), backgroundColor: '#0284c7' },
            { label: 'Efterfrågan (Kvinnor)', data: labels.map(l => dagData['kvinnor'][l]), backgroundColor: '#be185d' },
            { label: 'Lokalt Utbud (Män)', data: labels.map(l => nattData['män'][l]), backgroundColor: '#0ea5e9' },
            { label: 'Lokalt Utbud (Kvinnor)', data: labels.map(l => nattData['kvinnor'][l]), backgroundColor: '#ec4899' }
        ];
    } else {
        let netData = {};
        labels.forEach(l => { netData[l] = (nattData['totalt'][l] || 0) - (dagData['totalt'][l] || 0); });
        
        const simMode = document.getElementById('simMode').value;
        const supplyLabel = simMode === 'full' ? 'Utbud (Inkl. all pendling)' : 'Lokalt Utbud (Nattbef.)';

        datasets = [
            { 
                type: isHorizontal ? 'bar' : 'line', 
                label: 'Rekryteringsgap (Lokal brist)', 
                data: labels.map(l => netData[l]), 
                borderColor: '#ef4444', 
                backgroundColor: isHorizontal ? 'rgba(239, 68, 68, 0.7)' : '#ef4444', 
                borderWidth: 2, 
                pointRadius: 4, 
                fill: false, 
                order: 1 
            },
            { type: 'bar', label: 'Efterfrågan/Jobb (Dag)', data: labels.map(l => dagData['totalt'][l]), backgroundColor: '#10b981', order: 2 },
            { type: 'bar', label: supplyLabel, data: labels.map(l => nattData['totalt'][l]), backgroundColor: '#0ea5e9', order: 3 }
        ];
    }

    const yGraceElement = document.getElementById('yGrace');
    const graceVal = yGraceElement ? yGraceElement.value : '20%';

    const scaleConfig = isHorizontal ? {
        x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
        y: { ticks: { font: { size: 10 } } }
    } : {
        x: { ticks: { font: { size: 10 } } },
        y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
    };

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            indexAxis: isHorizontal ? 'y' : 'x', 
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: scaleConfig,
            plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + formatNumber(ctx.raw, 0) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
        }
    });
}

function updateDashboard(calledFromDropdown = true) {
    try {
        const chartTypeElement = document.getElementById('chartType');
        const subGroupSelect = document.getElementById('subGroupSelect');
        if (!chartTypeElement) return;

        const chartType = chartTypeElement.value;
        
        const dualAxesContainer = document.getElementById('dualAxesContainer');
        const useDualAxesElement = document.getElementById('useDualAxes');
        let useDualAxes = useDualAxesElement ? useDualAxesElement.checked : false;
        const useZeroAxisElement = document.getElementById('useZeroAxis');
        const useZeroAxis = useZeroAxisElement ? useZeroAxisElement.checked : false;

        if (!(chartType.includes('arbetsloshet_utrikes') || chartType.includes('langtidsarb_utrikes') || chartType.includes('arbetsloshet_kon') || chartType.includes('langtidsarb_kon') || chartType === 'syssgrad_utrikes' || chartType === 'trend_utrikes')) {
            useDualAxes = false;
        }

        const exportPopBtn = document.getElementById('exportPopBtn');

        // Hantera synlighet för menyer beroende på diagram
        if (chartType === 'pop_dynamic') {
            if(exportPopBtn) exportPopBtn.classList.replace('hidden', 'flex');
            if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
            if (subGroupSelect && subGroupSelect.getAttribute('data-type') !== 'pop_dynamic') {
                subGroupSelect.innerHTML = '<option value="total">Totalt 16-74 år</option><option value="func">Funktionella grupper</option><option value="5yr">5-årsklasser</option>';
                subGroupSelect.setAttribute('data-type', 'pop_dynamic');
            }
            if(subGroupSelect) {
                subGroupSelect.classList.remove('hidden');
                chartTypeElement.classList.remove('rounded-r');
                subGroupSelect.classList.add('rounded-r');
            }
        } else if (chartType.includes('arbetsloshet_utrikes') || chartType.includes('langtidsarb_utrikes') || chartType.includes('arbetsloshet_kon') || chartType.includes('langtidsarb_kon') || chartType === 'syssgrad_utrikes' || chartType === 'trend_utrikes') {
            if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
            if(dualAxesContainer) { dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); }
            if(subGroupSelect) subGroupSelect.classList.add('hidden'); 
            chartTypeElement.classList.add('rounded-r');
        } else if (chartType === 'bransch_match') {
            if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
            if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
            if (subGroupSelect && subGroupSelect.getAttribute('data-type') !== 'bransch') {
                subGroupSelect.innerHTML = '<option value="all">Alla branscher (SNI)</option>';
                if (typeof syssConfig !== 'undefined' && syssConfig['SNIgrupper'] && syssConfig['SNIgrupper'].length > 0) {
                    const firstRow = syssConfig['SNIgrupper'][0];
                    const groupCols = Object.keys(firstRow).slice(1);
                    groupCols.forEach(col => subGroupSelect.add(new Option(col, col)));
                }
                subGroupSelect.setAttribute('data-type', 'bransch');
            }
            if(subGroupSelect) {
                subGroupSelect.classList.remove('hidden');
                chartTypeElement.classList.remove('rounded-r');
                subGroupSelect.classList.add('rounded-r');
            }
        } else if (chartType === 'syssgrad_kon') {
            if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
            if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
            if (subGroupSelect && subGroupSelect.getAttribute('data-type') !== 'syssgrad') {
                subGroupSelect.innerHTML = '';
                const sampleY = typeof histDataStore !== 'undefined' ? Object.keys(histDataStore).find(k => histDataStore[k].syssGradM) : null;
                if (sampleY) {
                    const keys = Object.keys(histDataStore[sampleY].syssGradM).filter(k => !['År', 'år', 'Kön', 'kön'].includes(k));
                    keys.forEach(k => subGroupSelect.add(new Option(k, k)));
                    let defaultOpt = Array.from(subGroupSelect.options).find(o => o.value.includes('20-64'));
                    if (!defaultOpt && subGroupSelect.options.length > 0) defaultOpt = subGroupSelect.options[0];
                    if (defaultOpt) subGroupSelect.value = defaultOpt.value;
                }
                subGroupSelect.setAttribute('data-type', 'syssgrad');
            }
            if(subGroupSelect) {
                subGroupSelect.classList.remove('hidden');
                chartTypeElement.classList.remove('rounded-r');
                subGroupSelect.classList.add('rounded-r');
            }
        } else {
            if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
            if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
            if(subGroupSelect) subGroupSelect.classList.add('hidden');
            chartTypeElement.classList.add('rounded-r');
        }

        const startYearSelect = document.getElementById('startYearSelect');
        const desc = document.getElementById('chartDescription');
        const title = document.getElementById('trendTitle');
        const yearSelectEl = document.getElementById('yearSelect');
        const selectedYearStr = yearSelectEl ? yearSelectEl.value : String(typeof PROGNOS_SLUTAR !== 'undefined' ? PROGNOS_SLUTAR : new Date().getFullYear());
        const ctxElement = document.getElementById('trendChart');
        if (!ctxElement) return;
        const ctx = ctxElement.getContext('2d');
        const wrapper = document.getElementById('chartWrapper');
        
        const isComparing = typeof savedProjectedData !== 'undefined' && savedProjectedData !== null;
        const simModeEl = document.getElementById('simMode');
        const simMode = simModeEl ? simModeEl.value : 'full';
        const showCommuting = simMode === 'full';
        const causalityModeEl = document.getElementById('causalityMode');
        const causalityMode = causalityModeEl ? causalityModeEl.value : 'analytic';
        
        const selYearInt = parseInt(selectedYearStr);
        const isProgYear = typeof progDataStore !== 'undefined' && progDataStore[selYearInt] !== undefined;
        const refYear = isProgYear ? (typeof baseYear !== 'undefined' ? baseYear : 0) : selYearInt;
        const currentPopData = (typeof useCustomPop !== 'undefined' && useCustomPop && customPopData) ? customPopData : (typeof popData !== 'undefined' ? popData : []);
        
        if (typeof trendChartInstance !== 'undefined' && trendChartInstance) {
            trendChartInstance.data.datasets.forEach((ds, i) => {
                const meta = trendChartInstance.getDatasetMeta(i);
                globalChartVisibility[ds.label] = meta.hidden === null ? ds.hidden : meta.hidden;
            });
            trendChartInstance.destroy();
        }

        if (wrapper) wrapper.style.minHeight = '300px';

        const yGraceElement = document.getElementById('yGrace');
        const graceVal = yGraceElement ? yGraceElement.value : '20%';

        let labels = [];
        let datasets = [];
        let isHorizontal = false;
        let isStacked = false;
        let isBarChart = false;
        let customScale = null;
        let isMultiLine = false;
        
        const bYear = typeof baseYear !== 'undefined' ? baseYear : 0;
        const graphStartYear = isComparing ? bYear : (parseInt(startYearSelect ? startYearSelect.value : 0) || (typeof allYears !== 'undefined' && allYears.length > 0 ? allYears[0] : 0));
        const activeYears = typeof allYears !== 'undefined' ? allYears.filter(y => y >= graphStartYear) : [];

        // AVBRYT HÄR OM DATAN SAKNAS FÖR ATT UNDVIKA KRASCH
        if (!histDataStore || Object.keys(histDataStore).length === 0) {
            if (title) title.innerText = "Ingen data inläst";
            if (desc) desc.innerText = "Kunde inte bygga grafen eftersom grunddatan saknas i historiken.";
            return;
        }

        // ==========================================
        // 1. MATCHNINGSDIAGRAM (Avbryter och ritar separat)
        // ==========================================
        if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
            if (startYearSelect) startYearSelect.style.display = 'none'; 
            isBarChart = true;
            let dagData = {}, nattData = {};
            let isGenderSplit = false;
            
            if (chartType === 'utb_match') {
                if (title) title.innerText = `Utbildningsmatchning (År ${selectedYearStr})`;
                if (desc) desc.innerHTML = `Staplarna visar kraven från företagen ställt mot vad invånarna har för utbildning. Den röda linjen visar <b>Kompetensgapet</b>.`;
                labels = ['Förgymnasial', 'Gymnasial', 'Eftergymnasial', 'Okänd'];
                const mapLevel = (l) => {
                    let t = String(l).toLowerCase();
                    if (t.includes('förgymnasial')) return 'Förgymnasial';
                    if (t.includes('eftergymnasial') || t.includes('forskar')) return 'Eftergymnasial';
                    if (t.includes('gymnasial')) return 'Gymnasial';
                    return 'Okänd';
                };
                dagData = aggregateMatchData(syssBasdata['Syss_utbnivå'] || syssBasdata['Syss_utbniva'] || [], refYear, labels, 'Utbildningsnivå', mapLevel);
                nattData = aggregateMatchData(syssBasdata['Natt_utbnivå'] || syssBasdata['Natt_utbniva'] || [], refYear, labels, 'Utbildningsnivå', mapLevel);
            
            } else if (chartType === 'sektor_match') {
                if (title) title.innerText = `Sektormatchning (År ${selectedYearStr})`;
                if (desc) desc.innerHTML = `Sektor för invånarna jämfört med sektor för jobben.`;
                labels = ['Privat sektor', 'Offentlig sektor'];
                dagData = aggregateMatchData(syssBasdata['Syss_sektor'] || [], refYear, labels, 'Sektor');
                nattData = aggregateMatchData(syssBasdata['Natt_sektor'] || [], refYear, labels, 'Sektor');
            
            } else if (chartType === 'sektor_match_kon') {
                if (title) title.innerText = `Sektormatchning: Män och Kvinnor (År ${selectedYearStr})`;
                if (desc) desc.innerHTML = `Sektor för invånarna jämfört med sektor för jobben, uppdelat på kön.`;
                labels = ['Privat sektor', 'Offentlig sektor'];
                isGenderSplit = true;
                
                let d_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
                let d_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
                let n_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
                let n_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };

                (syssBasdata['Syss_sektor'] || []).filter(r => extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) {
                        d_m[sec] += parseFloat(r['Män'] || r['män'] || 0);
                        d_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0);
                    }
                });
                (syssBasdata['Natt_sektor'] || []).filter(r => extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) {
                        n_m[sec] += parseFloat(r['Män'] || r['män'] || 0);
                        n_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0);
                    }
                });
                dagData = {'män': d_m, 'kvinnor': d_k};
                nattData = {'män': n_m, 'kvinnor': n_k};

            } else if (chartType === 'bransch_match') {
                if (title) title.innerText = `Branschmatchning (År ${selectedYearStr})`;
                if (desc) desc.innerHTML = `Detaljerad matchning per näringsgren/bransch. Röda markeringar (<0) visar lokalt underskott.`;
                isHorizontal = true;
                const dfDag = syssBasdata['Syss_bransch'] || [];
                const dfNatt = syssBasdata['Natt_bransch'] || [];
                
                if (dfDag.length > 0) {
                    const excludeCols = ['År', 'år', 'Samtliga', 'Totalt', 'Kön', 'kön', 'Okänd bransch'];
                    labels = Object.keys(dfDag[0]).filter(k => !excludeCols.includes(k));
                }
                
                dagData = aggregateMatchData(dfDag, refYear, labels, 'Cols');
                nattData = aggregateMatchData(dfNatt, refYear, labels, 'Cols');
                
                const subGroupVal = subGroupSelect ? subGroupSelect.value : 'all';
                if (subGroupVal && subGroupVal !== 'all' && syssConfig['SNIgrupper']) {
                    let groupedDag = { 'totalt': {} };
                    let groupedNatt = { 'totalt': {} };
                    const sniGrupper = syssConfig['SNIgrupper'];
                    const firstKey = Object.keys(sniGrupper[0])[0]; 

                    labels.forEach(l => {
                        let mappingRow = sniGrupper.find(r => String(r[firstKey]).trim() === String(l).trim());
                        let targetGroup = mappingRow ? mappingRow[subGroupVal] : null;

                        if (targetGroup && targetGroup !== null && String(targetGroup).trim() !== '') {
                            let groupName = String(targetGroup).trim();
                            if (!groupedDag['totalt'][groupName]) { groupedDag['totalt'][groupName] = 0; groupedNatt['totalt'][groupName] = 0; }
                            groupedDag['totalt'][groupName] += dagData['totalt'][l] || 0;
                            groupedNatt['totalt'][groupName] += nattData['totalt'][l] || 0;
                        }
                    });
                    labels = Object.keys(groupedDag['totalt']);
                    dagData = groupedDag;
                    nattData = groupedNatt;
                }

                if (labels.length > 15 && (!subGroupVal || subGroupVal === 'all')) {
                    if (wrapper) wrapper.style.minHeight = (labels.length * 20) + 'px';
                }
            }
            
            drawMatchChart(selYearInt, labels, dagData, nattData, isGenderSplit, useZeroAxis, isHorizontal);
            return; // RITAD OCH KLAR!
        }

        // ==========================================
        // 2. DYNAMISK BEFOLKNING
        // ==========================================
        if (chartType === 'pop_dynamic') {
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
            if (title) title.innerText = "Framtida Befolkning 16-74 år (Dynamisk)" + suffix;
            if (desc) desc.innerText = "Visar kommunens basbefolkning i åldern 16-74 år. Om du har den dynamiska modellen aktiverad visar grafen även det simulerade befolkningstillskottet för motsvarande åldrar.";

            const popGroupVal = subGroupSelect ? subGroupSelect.value : 'total';
            let hasProg = false;
            labels = activeYears;

            if (popGroupVal === 'total') {
                let h_pop=[], p_base=[], p_induced=[];
                labels.forEach(y => {
                    let numericY = Number(y);
                    if (y <= bYear && histDataStore[numericY]) h_pop.push(histDataStore[numericY].pop);
                    else h_pop.push(null);
                    
                    if (y > bYear && progDataStore[numericY]) {
                        let d = progDataStore[numericY];
                        let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                        let base = d.pop - induced;
                        p_base.push(base); p_induced.push(induced); hasProg = true;
                    } else if (y === bYear && histDataStore[numericY]) {
                        p_base.push(histDataStore[numericY].pop); p_induced.push(0);
                    } else {
                        p_base.push(null); p_induced.push(null);
                    }
                });

                datasets = [ { label: 'Historisk Befolkning', data: h_pop, borderColor: '#0284c7', backgroundColor: '#0ea5e920', borderWidth: 3, fill: true, pointStyle: 'circle', spanGaps: true, stack: 'hist' } ];
                if (hasProg && !isComparing) {
                    datasets.push({ label: 'Basbefolkning (Prognos)', data: p_base, borderColor: '#0ea5e9', backgroundColor: '#0ea5e920', borderWidth: 2, borderDash: [5,5], fill: true, pointStyle: 'circle', stack: 'prog' });
                    datasets.push({ label: 'Inflyttning från jobbtillväxt', data: p_induced, borderColor: '#10b981', backgroundColor: '#10b98180', borderWidth: 2, fill: true, pointStyle: 'rect', stack: 'prog' });
                }
                isStacked = hasProg;
            } else {
                isMultiLine = true;
                const getPopForGroup = (yStr, group) => {
                    let pop = 0;
                    let records = currentPopData.filter(r => String(r.tid).trim() === yStr);
                    if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === yStr.replace(' (Prognos)', ''));
                    if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === String(bYear)); 
                    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                    records.forEach(r => {
                        if (!String(r.ålder).toLowerCase().includes('totalt')) {
                            let konStr = String(r.kön).trim().toLowerCase();
                            if (useGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                            if (group.sex && konStr !== group.sex) return;
                            const match = String(r.ålder).match(/\d+/);
                            if (match) {
                                const age = parseInt(match[0]);
                                let minAge = group.min !== undefined ? group.min : 0;
                                let maxAge = group.max !== undefined ? group.max : 999;
                                if (age >= minAge && age <= maxAge) pop += (r.Befolkning || 0);
                            }
                        }
                    });
                    if (pop === 0 && yStr.includes('Prognos')) {
                        let fallbackRecords = currentPopData.filter(r => String(r.tid).trim() === String(bYear));
                        let fallbackUseGender = fallbackRecords.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                        fallbackRecords.forEach(r => {
                            if (!String(r.ålder).toLowerCase().includes('totalt')) {
                                let konStr = String(r.kön).trim().toLowerCase();
                                if (fallbackUseGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                                if (group.sex && konStr !== group.sex) return;
                                const match = String(r.ålder).match(/\d+/);
                                if (match) {
                                    const age = parseInt(match[0]);
                                    let minAge = group.min !== undefined ? group.min : 0;
                                    let maxAge = group.max !== undefined ? group.max : 999;
                                    if (age >= minAge && age <= maxAge) pop += (r.Befolkning || 0);
                                }
                            }
                        });
                    }
                    return pop;
                };

                let groups = getGroupDefinitions(popGroupVal);

                groups.forEach((g, idx) => {
                    let h_data = [], p_data = [];
                    labels.forEach((yStr) => {
                        let numericY = Number(yStr);
                        let isProg = numericY > bYear;
                        let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
                        let groupBase = getPopForGroup(searchStr, g);
                        let totalBase16_74 = getPopForGroup(searchStr, { min: 16, max: 74 });
                        let finalPop = groupBase;
                        
                        if (isProg && progDataStore[numericY] && causalityMode === 'dynamic') {
                            let induced = progDataStore[numericY].inducedPop || 0;
                            let groupInduced = totalBase16_74 > 0 ? induced * (groupBase / totalBase16_74) : 0;
                            finalPop += groupInduced;
                        }
                        
                        if (isProg) { h_data.push(null); p_data.push(finalPop); hasProg = true; } 
                        else { h_data.push(finalPop); p_data.push(null); }
                    });
                    
                    labels.forEach((yStr, idx2) => { if (Number(yStr) === bYear && idx2 < labels.length - 1) p_data[idx2] = h_data[idx2]; });
                    datasets.push({ label: g.label, data: h_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true });
                    if (p_data.some(v => v !== null)) datasets.push({ label: g.label + ' (Prognos)', data: p_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
                });
            }

        // ==========================================
        // 3. PENDLING (STAPLAR)
        // ==========================================
        } else if (chartType === 'pendling_detalj') {
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            if (title) title.innerText = "In- och utpendling (Kommungräns)";
            if (desc) desc.innerText = "Visar pendlingsflödena över kommungränsen i absoluta tal (antal personer) samt det resulterande pendlingsnettot.";
            isBarChart = true;

            let hIn = [], hUt = [], hNet = [];
            let pIn = [], pUt = [], pNet = [];
            labels = activeYears;
            
            labels.forEach(y => {
                let numY = Number(y);
                if (numY <= bYear && histDataStore[numY]) {
                    hIn.push(histDataStore[numY].inpendling);
                    hUt.push(histDataStore[numY].utpendling ? -histDataStore[numY].utpendling : null); 
                    hNet.push(histDataStore[numY].netCommuting);
                } else { hIn.push(null); hUt.push(null); hNet.push(null); }
                
                if (numY === bYear && histDataStore[numY]) {
                    pIn.push(histDataStore[numY].inpendling);
                    pUt.push(histDataStore[numY].utpendling ? -histDataStore[numY].utpendling : null);
                    pNet.push(histDataStore[numY].netCommuting);
                } else if (numY > bYear && progDataStore[numY]) {
                    pIn.push(progDataStore[numY].inpendling);
                    pUt.push(progDataStore[numY].utpendling ? -progDataStore[numY].utpendling : null);
                    pNet.push(progDataStore[numY].explicitNetCommuting);
                } else { pIn.push(null); pUt.push(null); pNet.push(null); }
            });

            datasets = [
                { type: 'bar', label: 'Inpendling', data: hIn, backgroundColor: '#0ea5e9' },
                { type: 'bar', label: 'Utpendling', data: hUt, backgroundColor: '#ef4444' },
                { type: 'line', label: 'Pendlingsnetto', data: hNet, borderColor: '#334155', borderWidth: 3, fill: false, pointStyle: 'rect' }
            ];
            
            const hasProg = pIn.some((v, idx) => v !== null && labels[idx] > bYear);
            if (hasProg && !isComparing) {
                datasets.push({ type: 'bar', label: 'Inpendling (Prognos)', data: pIn, backgroundColor: 'rgba(14, 165, 233, 0.4)' });
                datasets.push({ type: 'bar', label: 'Utpendling (Prognos)', data: pUt, backgroundColor: 'rgba(239, 68, 68, 0.4)' });
                datasets.push({ type: 'line', label: 'Pendlingsnetto (Prognos)', data: pNet, borderColor: '#94a3b8', borderWidth: 3, borderDash: [5,5], fill: false, pointStyle: 'rect' });
            }

        // ==========================================
        // 4. ÅRLIG FÖRÄNDRING (DELTAT)
        // ==========================================
        } else if (chartType === 'utbud_efterfragan_delta') {
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            if (title) title.innerText = "Årlig förändring (Nytt utbud/Efterfrågan)";
            if (desc) desc.innerText = "Visar hur många nya arbetstillfällen och invånare som tillkommer eller försvinner varje enskilt år jämfört med året innan.";
            isBarChart = true;

            let dDemand = [], dSupply = [];
            labels = activeYears;
            
            labels.forEach(y => {
                let numY = Number(y);
                let currD = null, currS = null;
                let prevD = null, prevS = null;

                if (numY <= bYear && histDataStore[numY]) {
                    currD = histDataStore[numY].demand; currS = histDataStore[numY].supply;
                } else if (numY > bYear && progDataStore[numY]) {
                    currD = progDataStore[numY].demand; currS = progDataStore[numY].supply;
                }

                if (numY - 1 <= bYear && histDataStore[numY - 1]) {
                    prevD = histDataStore[numY - 1].demand; prevS = histDataStore[numY - 1].supply;
                } else if (numY - 1 > bYear && progDataStore[numY - 1]) {
                    prevD = progDataStore[numY - 1].demand; prevS = progDataStore[numY - 1].supply;
                }

                if (currD != null && prevD != null) dDemand.push(currD - prevD); else dDemand.push(null);
                if (currS != null && prevS != null) dSupply.push(currS - prevS); else dSupply.push(null);
            });

            datasets = [
                { type: 'bar', label: 'Förändring Efterfrågan', data: dDemand, backgroundColor: '#10b981' },
                { type: 'bar', label: 'Förändring Lokalt Utbud', data: dSupply, backgroundColor: '#0ea5e9' }
            ];

        // ==========================================
        // 5. UTBUD VS EFTERFRÅGAN (TREND)
        // ==========================================
        } else if (chartType === 'utbud_efterfragan') {
            isMultiLine = true;
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
            if (title) title.innerText = "Utbud vs Efterfrågan" + suffix;
            if (desc) {
                if (causalityMode === 'dynamic') desc.innerHTML = "I <b>Dynamiskt läge</b> anpassar sig utbudet (den blå och lila linjen) automatiskt efter företagens efterfrågan. Grafen visar den slutgiltiga balansen.";
                else if (showCommuting) desc.innerText = "Grafen visar Efterfrågan på arbetskraft (Jobb/Grön), det lokala Utbudet (Bosatta/Blå), samt det Totala Utbudet inkl. in/ut-pendling (Streckad lila). När den lila linjen fångar in den gröna är arbetsmarknaden i balans!";
                else desc.innerText = "Grafen visar Efterfrågan på arbetskraft (Jobb/Grön) och det lokala Utbudet (Bosatta/Blå). Pendling visas ej i denna vy.";
            }

            labels = activeYears;
            let hDemand=[], hSupply=[], hTotalSupply=[], pDemand=[], pSupply=[], pTotalSupply=[], sDemand=[], sSupply=[], sTotalSupply=[];

            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= bYear && histDataStore[numericY]) { hDemand.push(histDataStore[numericY].demand); hSupply.push(histDataStore[numericY].supply); hTotalSupply.push(histDataStore[numericY].totalSupply); } 
                else { hDemand.push(null); hSupply.push(null); hTotalSupply.push(null); }
                
                if (y === bYear && histDataStore[numericY]) { pDemand.push(histDataStore[numericY].demand); pSupply.push(histDataStore[numericY].supply); pTotalSupply.push(histDataStore[numericY].totalSupply); } 
                else if (y > bYear && progDataStore[numericY]) { pDemand.push(progDataStore[numericY].demand); pSupply.push(progDataStore[numericY].supply); pTotalSupply.push(progDataStore[numericY].totalSupply); } 
                else { pDemand.push(null); pSupply.push(null); pTotalSupply.push(null); }
                
                if (isComparing) {
                    if (y <= bYear && histDataStore[numericY]) { sDemand.push(histDataStore[numericY].demand); sSupply.push(histDataStore[numericY].supply); sTotalSupply.push(histDataStore[numericY].totalSupply); } 
                    else if (y > bYear && savedProjectedData && savedProjectedData[numericY]) { sDemand.push(savedProjectedData[numericY].demand); sSupply.push(savedProjectedData[numericY].supply); sTotalSupply.push(savedProjectedData[numericY].totalSupply); } 
                    else { sDemand.push(null); sSupply.push(null); sTotalSupply.push(null); }
                }
            });
            
            const hasProg = pDemand.some((v, idx) => v !== null && labels[idx] > bYear);
            
            if (!isComparing) {
                datasets = [
                    { label: 'Efterfrågan (Dagbefolkning)', data: hDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect', spanGaps: true },
                    { label: 'Lokalt Utbud (Nattbefolkning)', data: hSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
                ];
                if (showCommuting) datasets.push({ label: 'Totalt Utbud (Inkl. Pendling)', data: hTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [2, 2], pointStyle: 'triangle', spanGaps: true });
                
                if (hasProg) {
                    datasets.push({ label: 'Efterfrågan (Prognos)', data: pDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect' });
                    datasets.push({ label: 'Lokalt Utbud (Prognos)', data: pSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'circle' });
                    if (showCommuting) datasets.push({ label: 'Totalt Utbud (Prognos)', data: pTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'triangle' });
                }
            } else {
                datasets = [
                    { label: 'Efterfrågan (Aktuell)', data: pDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect' },
                    { label: 'Efterfrågan (Sparad)', data: sDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' },
                    { label: 'Lokalt Utbud (Aktuell)', data: pSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle' },
                    { label: 'Lokalt Utbud (Sparad)', data: sSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' }
                ];
                if (showCommuting) {
                    datasets.push({ label: 'Totalt Utbud (Aktuell)', data: pTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'triangle' });
                    datasets.push({ label: 'Totalt Utbud (Sparad)', data: sTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' });
                }
            }

            let defaultHiddenLabels = ['Efterfrågan (Aktuell)', 'Efterfrågan (Sparad)', 'Totalt Utbud (Inkl. Pendling)', 'Totalt Utbud (Aktuell)', 'Totalt Utbud (Sparad)'];
            if (showCommuting) defaultHiddenLabels.push('Efterfrågan (Prognos)');
            
            datasets.forEach(ds => {
                if (globalChartVisibility[ds.label] !== undefined) ds.hidden = globalChartVisibility[ds.label];
                else if (defaultHiddenLabels.includes(ds.label)) ds.hidden = true;
            });

        // ==========================================
        // 6. INRIKES / UTRIKES OCH KÖN (TRENDER)
        // ==========================================
        } else if (chartType === 'trend_utrikes' || chartType === 'trend_kon') {
            isMultiLine = true;
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
            
            let key1_n, key2_n, key1_d, key2_d, lbl1_n, lbl2_n, lbl1_d, lbl2_d, col1, col2;
            if (chartType === 'trend_utrikes') {
                if (title) title.innerText = "Integration: Arbetsmarknad efter ursprung" + suffix;
                if (desc) desc.innerText = "Visar hur utbudet (nattbefolkning) och efterfrågan (dagbefolkning) fördelar sig mellan inrikes och utrikes födda.";
                key1_n = 'n_inrikes'; key2_n = 'n_utrikes'; key1_d = 'd_inrikes'; key2_d = 'd_utrikes';
                lbl1_n = 'Lokalt Utbud (Inrikes)'; lbl2_n = 'Lokalt Utbud (Utrikes)'; lbl1_d = 'Efterfrågan (Inrikes)'; lbl2_d = 'Efterfrågan (Utrikes)';
                col1 = '#0ea5e9'; col2 = '#f97316';
            } else {
                if (title) title.innerText = "Jämställdhet: Arbetsmarknad efter kön" + suffix;
                if (desc) desc.innerText = "Visar hur utbudet (nattbefolkning) och efterfrågan (dagbefolkning) fördelar sig mellan män och kvinnor.";
                key1_n = 'n_man'; key2_n = 'n_kvinna'; key1_d = 'd_man'; key2_d = 'd_kvinna';
                lbl1_n = 'Lokalt Utbud (Män)'; lbl2_n = 'Lokalt Utbud (Kvinnor)'; lbl1_d = 'Efterfrågan (Män)'; lbl2_d = 'Efterfrågan (Kvinnor)';
                col1 = '#0ea5e9'; col2 = '#ec4899';
            }

            labels = activeYears;
            let h_n1=[], h_n2=[], p_n1=[], p_n2=[], h_d1=[], h_d2=[], p_d1=[], p_d2=[];

            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= bYear && histDataStore[numericY]) {
                    h_n1.push(histDataStore[numericY][key1_n]); h_n2.push(histDataStore[numericY][key2_n]);
                    h_d1.push(histDataStore[numericY][key1_d]); h_d2.push(histDataStore[numericY][key2_d]);
                } else { h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null); }
                
                if (y === bYear && histDataStore[numericY]) {
                    p_n1.push(histDataStore[numericY][key1_n]); p_n2.push(histDataStore[numericY][key2_n]);
                    p_d1.push(histDataStore[numericY][key1_d]); p_d2.push(histDataStore[numericY][key2_d]);
                } else if (y > bYear && progDataStore[numericY]) {
                    p_n1.push(progDataStore[numericY][key1_n]); p_n2.push(progDataStore[numericY][key2_n]);
                    p_d1.push(progDataStore[numericY][key1_d]); p_d2.push(progDataStore[numericY][key2_d]);
                } else { p_n1.push(null); p_n2.push(null); p_d1.push(null); p_d2.push(null); }
            });

            datasets = [
                { label: lbl1_n, data: h_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                { label: lbl2_n, data: h_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                { label: lbl1_d, data: h_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true },
                { label: lbl2_d, data: h_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true }
            ];
            
            const hasProg = p_n1.some((v, idx) => v !== null && labels[idx] > bYear);
            if(hasProg && !isComparing) {
                datasets.push({ label: lbl1_n.replace('Lokalt ', '') + ' (Prog)', data: p_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
                datasets.push({ label: lbl2_n.replace('Lokalt ', '') + ' (Prog)', data: p_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
                datasets.push({ label: lbl1_d + ' (Prog)', data: p_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
                datasets.push({ label: lbl2_d + ' (Prog)', data: p_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
            }

            const defaultHidden = [lbl1_d, lbl2_d, lbl1_d + ' (Prog)', lbl2_d + ' (Prog)'];
            datasets.forEach(ds => {
                if (globalChartVisibility[ds.label] !== undefined) ds.hidden = globalChartVisibility[ds.label];
                else if (defaultHidden.includes(ds.label)) ds.hidden = true;
            });

            if (useDualAxes && chartType === 'trend_utrikes') {
                customScale = {
                    y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes', color: col1 }, ticks: { callback: val => formatNumber(val) } },
                    y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => formatNumber(val) } }
                };
                datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
            }

        // ==========================================
        // 7. SYSSELSÄTTNINGSGRAD (%-Linjer)
        // ==========================================
        } else if (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon') {
            isMultiLine = true;
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
            
            let key1, key2, lbl1, lbl2, col1, col2;
            if (chartType === 'syssgrad_utrikes') {
                if (title) title.innerText = "Sysselsättningsgrad: Inrikes och Utrikes födda" + suffix;
                if (desc) desc.innerText = "Visar hur stor andel av befolkningen (20-64 år) som är sysselsatt, uppdelat på bakgrund.";
                key1 = 'syss_in_tot'; key2 = 'syss_ut_tot'; lbl1 = 'Inrikes'; lbl2 = 'Utrikes'; col1 = '#0ea5e9'; col2 = '#f97316';
            } else {
                if (title) title.innerText = "Sysselsättningsgrad: Män och Kvinnor" + suffix;
                if (desc) desc.innerText = "Visar hur stor andel av befolkningen som är sysselsatt, uppdelat på kön och vald åldersgrupp.";
                key1 = 'syssGradM'; key2 = 'syssGradK'; lbl1 = 'Män'; lbl2 = 'Kvinnor'; col1 = '#0ea5e9'; col2 = '#ec4899';
            }

            const ageGroup = subGroupSelect ? subGroupSelect.value : 'Totalt 20-64 år';
            let h_1 = [], h_2 = [], h_tot = [], p_1 = [], p_2 = [], p_tot = [];
            labels = activeYears;
            
            labels.forEach(y => {
                let numericY = Number(y);
                if (numericY >= 1985) {
                    let v1 = null, v2 = null;
                    if (histDataStore[numericY]) {
                        if (chartType === 'syssgrad_utrikes') {
                            v1 = histDataStore[numericY][key1] != null ? parseFloat(histDataStore[numericY][key1]) : null;
                            v2 = histDataStore[numericY][key2] != null ? parseFloat(histDataStore[numericY][key2]) : null;
                        } else {
                            v1 = histDataStore[numericY][key1] && histDataStore[numericY][key1][ageGroup] != null ? parseFloat(histDataStore[numericY][key1][ageGroup]) : null;
                            v2 = histDataStore[numericY][key2] && histDataStore[numericY][key2][ageGroup] != null ? parseFloat(histDataStore[numericY][key2][ageGroup]) : null;
                        }
                    }

                    if (y <= bYear) { h_1.push(v1); h_2.push(v2); h_tot.push(histDataStore[numericY] ? histDataStore[numericY].displayRate : null); } 
                    else { h_1.push(null); h_2.push(null); h_tot.push(null); }
                    
                    if (y === bYear) { p_1.push(v1); p_2.push(v2); p_tot.push(histDataStore[numericY] ? histDataStore[numericY].displayRate : null); } 
                    else if (y > bYear && progDataStore[numericY]) {
                        let base_1 = null, base_2 = null;
                        if (histDataStore[bYear]) {
                            if (chartType === 'syssgrad_utrikes') {
                                base_1 = histDataStore[bYear][key1] != null ? parseFloat(histDataStore[bYear][key1]) : null;
                                base_2 = histDataStore[bYear][key2] != null ? parseFloat(histDataStore[bYear][key2]) : null;
                            } else {
                                base_1 = histDataStore[bYear][key1] && histDataStore[bYear][key1][ageGroup] != null ? parseFloat(histDataStore[bYear][key1][ageGroup]) : null;
                                base_2 = histDataStore[bYear][key2] && histDataStore[bYear][key2][ageGroup] != null ? parseFloat(histDataStore[bYear][key2][ageGroup]) : null;
                            }
                        }
                        let base_tot = histDataStore[bYear].displayRate != null ? parseFloat(histDataStore[bYear].displayRate) : null;
                        const syssGradEl = document.getElementById('syssGradSlider');
                        const sliderChange = syssGradEl ? parseFloat(syssGradEl.value) : 0;
                        const step = (numericY - bYear) / 10;
                        p_1.push(base_1 != null ? base_1 + sliderChange * step : null);
                        p_2.push(base_2 != null ? base_2 + sliderChange * step : null);
                        p_tot.push(base_tot != null ? base_tot + sliderChange * step : null);
                    } else { p_1.push(null); p_2.push(null); p_tot.push(null); }
                }
            });

            datasets = [
                { label: `Sysselsättningsgrad ${lbl1} %`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                { label: `Sysselsättningsgrad ${lbl2} %`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
            ];
            if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt %', data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });

            const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > bYear);
            if (hasProg) {
                datasets.push({ label: `${lbl1} % (Prognos)`, data: p_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                datasets.push({ label: `${lbl2} % (Prognos)`, data: p_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt % (Prognos)', data: p_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect', fill: false, hidden: true });
            }

            datasets.forEach(ds => {
                if (globalChartVisibility[ds.label] !== undefined) ds.hidden = globalChartVisibility[ds.label];
            });

            if (useDualAxes && chartType === 'syssgrad_utrikes') {
                customScale = {
                    y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes %', color: col1 }, ticks: { callback: val => formatNumber(val, 1) + '%' } },
                    y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => formatNumber(val, 1) + '%' } }
                };
                datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
            } else {
                customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 1) + '%' } } };
            }

        // ==========================================
        // 8. ARBETSLÖSHET & LÅNGTIDSARBETSLÖSHET
        // ==========================================
        } else if (chartType.includes('arbetsloshet') || chartType.includes('langtidsarb')) {
            isMultiLine = true;
            if (startYearSelect) startYearSelect.style.display = 'inline-block';
            let isLangtid = chartType.includes('langtidsarb');
            let groupStr = chartType.includes('_utrikes') ? 'utrikes' : (chartType.includes('_kon') ? 'kon' : 'totalt');
            
            if (title) {
                let baseT = isLangtid ? "Långtidsarbetslöshet" : "Arbetslöshet";
                if (groupStr === 'totalt') title.innerText = baseT + (isLangtid ? " (Kärnan)" : " & Arbetskraftsreserv");
                else if (groupStr === 'utrikes') title.innerText = baseT + ": Inrikes och Utrikes födda";
                else title.innerText = baseT + ": Män och Kvinnor";
            }
            
            if (desc) {
                if (groupStr === 'totalt') desc.innerText = isLangtid ? "Andel långtidsarbetslösa (Totalt). Denna grupp utgör ofta kärnan i den strukturella arbetslösheten." : "Historisk andel av arbetskraften som är inskriven arbetslös. Fungerar som referens.";
                else if (groupStr === 'utrikes') desc.innerText = isLangtid ? "Andel långtidsarbetslösa uppdelat på bakgrund." : "Visar hur andelen inskrivna arbetslösa skiljer sig mellan inrikes födda och utrikes födda historiskt.";
                else desc.innerText = (isLangtid ? "Andel långtidsarbetslösa" : "Visar hur andelen inskrivna arbetslösa skiljer sig") + " mellan könen.";
            }

            let h_1=[], h_2=[], p_1=[], p_2=[], h_tot=[], p_tot=[];
            labels = activeYears;
            labels.forEach(y => {
                let numericY = Number(y);
                if (numericY >= 1985) {
                    let d = histDataStore[numericY];
                    if (groupStr === 'totalt') {
                        let val = d ? (isLangtid ? d.langtidsPct : d.arbetsloshetPct) : null;
                        if (y <= bYear) h_1.push(val); else h_1.push(null);
                        if (y === bYear) p_1.push(val);
                        else if (y > bYear && progDataStore[numericY]) p_1.push(isLangtid ? progDataStore[numericY].langtidsPct : progDataStore[numericY].arbetsloshetPct);
                        else p_1.push(null);
                    } else {
                        let key1 = isLangtid ? (groupStr === 'utrikes' ? 'larb_inrikes' : 'larb_man') : (groupStr === 'utrikes' ? 'arb_inrikes' : 'arb_man');
                        let key2 = isLangtid ? (groupStr === 'utrikes' ? 'larb_utrikes' : 'larb_kvinna') : (groupStr === 'utrikes' ? 'arb_utrikes' : 'arb_kvinna');
                        let totKey = isLangtid ? 'langtidsPct' : 'arbetsloshetPct';
                        
                        if (y <= bYear && d) { h_1.push(d[key1]); h_2.push(d[key2]); h_tot.push(d[totKey]); } 
                        else { h_1.push(null); h_2.push(null); h_tot.push(null); }
                        
                        if (y === bYear && d) { p_1.push(d[key1]); p_2.push(d[key2]); p_tot.push(d[totKey]); } 
                        else if (y > bYear && progDataStore[numericY]) { p_1.push(progDataStore[numericY][key1]); p_2.push(progDataStore[numericY][key2]); p_tot.push(progDataStore[numericY][totKey]); } 
                        else { p_1.push(null); p_2.push(null); p_tot.push(null); }
                    }
                }
            });

            if (groupStr === 'totalt') {
                let lbl = isLangtid ? 'Långtidsarbetslösa' : 'Arbetslöshet';
                datasets = [
                    { label: lbl + ' % (Historik)', data: h_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: isLangtid ? 'rgba(249, 115, 22, 0.2)' : 'rgba(239, 68, 68, 0.2)', borderWidth: 3, pointStyle: 'circle', fill: true, spanGaps: true },
                    { label: 'Teoretisk ' + lbl + ' % (Prognos)', data: p_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'circle', fill: false }
                ];
            } else {
                let lbl1 = groupStr === 'utrikes' ? 'Inrikes' : 'Män';
                let lbl2 = groupStr === 'utrikes' ? 'Utrikes' : 'Kvinnor';
                let col1 = '#0ea5e9';
                let col2 = groupStr === 'utrikes' ? '#f97316' : '#ec4899';
                let baseL = isLangtid ? 'Långtidsarbetslösa' : 'Arbetslöshet';
                
                datasets = [
                    { label: `${baseL} ${lbl1} %`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                    { label: `${baseL} ${lbl2} %`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
                ];
                if (groupStr === 'kon') datasets.push({ label: 'Totalt %', data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });
                
                const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > bYear);
                if (hasProg) {
                    datasets.push({ label: `${lbl1} % (Prognos)`, data: p_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                    datasets.push({ label: `${lbl2} % (Prognos)`, data: p_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                    if (groupStr === 'kon') datasets.push({ label: 'Totalt % (Prognos)', data: p_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect', fill: false, hidden: true });
                }
            }
            
            if (useDualAxes && groupStr === 'utrikes') {
                let col1 = '#0ea5e9'; let col2 = '#f97316';
                customScale = {
                    y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes %', color: col1 }, ticks: { callback: val => formatNumber(val, 1) + '%' } },
                    y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => formatNumber(val, 1) + '%' } }
                };
                datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
            } else {
                customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 1) + '%' } } };
            }

        // ==========================================
        // 9. BRP (Ekonomisk tillväxt)
        // ==========================================
        } else if (chartType === 'brp_totalt') {
            if (startYearSelect) startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
            if (title) title.innerText = "Ekonomisk Tillväxt" + suffix;
            if (desc) desc.innerText = "Visar den totala storleken på Linköpings lokala ekonomi (Bruttoregionalprodukt).";

            let hBRP = [], pBRP = [], sBRP = [];
            labels = activeYears;
            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= bYear && histDataStore[numericY]) {
                    let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                    hBRP.push((brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null);
                } else { hBRP.push(null); }
                
                if (y === bYear && histDataStore[numericY]) {
                    let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                    pBRP.push((brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null);
                } else if (y > bYear && progDataStore[numericY]) {
                    pBRP.push(progDataStore[numericY].totalBrpMkr);
                } else { pBRP.push(null); }
                
                if (isComparing) {
                    if (y <= bYear && histDataStore[numericY]) {
                        let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                        sBRP.push((brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null);
                    } else if (y > bYear && savedProjectedData && savedProjectedData[numericY]) {
                        sBRP.push(savedProjectedData[numericY].totalBrpMkr);
                    } else { sBRP.push(null); }
                }
            });

            if (!isComparing) {
                datasets = [
                    { label: 'Total BRP (Mkr) - Historik', data: hBRP, borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.2)', borderWidth: 3, pointStyle: 'rect', fill: true, spanGaps: true },
                    { label: 'Total BRP (Mkr) - Prognos', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect', fill: false }
                ];
            } else {
                 datasets = [
                    { label: 'Total BRP (Mkr) - Aktuell', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect' },
                    { label: 'Total BRP (Mkr) - Sparad', data: sBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], opacity: 0.6, pointStyle: 'rectRot' }
                ];
            }
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 0) } } };
        }

        // ==========================================
        // RITA GRAFEN
        // ==========================================
        if (!isBarChart && datasets.length > 0) {
            datasets.forEach(ds => {
                if (globalChartVisibility[ds.label] !== undefined) ds.hidden = globalChartVisibility[ds.label];
            });

            let decimals = (chartType.includes('arbetsloshet') || chartType.includes('syssgrad')) ? 1 : 0;
            let suffix_text = (chartType.includes('arbetsloshet') || chartType.includes('syssgrad')) ? '%' : (chartType === 'brp_totalt' ? ' Mkr' : '');

            let finalOptions = {
                responsive: true, 
                maintainAspectRatio: false, 
                interaction: { mode: isMultiLine ? 'index' : 'nearest', intersect: false },
                scales: customScale || { y: { stacked: isStacked, beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, decimals) + suffix_text } } },
                plugins: { 
                    tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + formatNumber(ctx.raw, decimals) + suffix_text } }, 
                    legend: { 
                        labels: { boxWidth: 10, font: { size: 11 }, generateLabels: function(chart) { return Chart.defaults.plugins.legend.labels.generateLabels(chart).map(l => { l.color = l.hidden ? '#cbd5e1' : '#334155'; return l; }); } },
                        onClick: function(e, legendItem, legend) {
                            Chart.defaults.plugins.legend.onClick.call(this, e, legendItem, legend);
                            setTimeout(() => {
                                const hideBtn = document.getElementById('hideAllBtn');
                                if (hideBtn && !hideBtn.classList.contains('hidden')) {
                                    const anyVis = trendChartInstance.data.datasets.some((ds, i) => trendChartInstance.isDatasetVisible(i));
                                    hideBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
                                }
                            }, 50);
                        }
                    } 
                }
            };

            trendChartInstance = new Chart(ctx, {
                type: 'line',
                data: { labels: labels.map(l => String(l).replace(' (Prognos)', '')), datasets: datasets },
                options: finalOptions
            });
        } else if (isBarChart && datasets.length > 0) {
            
            let scaleConfig = isHorizontal ? {
                x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
                y: { ticks: { font: { size: 10 } } }
            } : {
                x: { ticks: { font: { size: 10 } } },
                y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
            };

            if(chartType === 'pendling_detalj') {
               scaleConfig = {
                  x: { ticks: { font: { size: 10 } } },
                  y: { beginAtZero: true, grace: graceVal, ticks: { callback: val => formatNumber(val, 0), font: { size: 10 } } }
               };
            }

            trendChartInstance = new Chart(ctx, {
                type: 'bar',
                data: { labels: labels.map(l => String(l).replace(' (Prognos)', '')), datasets: datasets },
                options: {
                    indexAxis: isHorizontal ? 'y' : 'x', 
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: customScale || scaleConfig,
                    plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + formatNumber(ctx.raw, 0) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
                }
            });
        }

        if (!calledFromDropdown && typeof updateKPIs === 'function') updateKPIs();
        
        const hideAllBtn = document.getElementById('hideAllBtn');
        if (hideAllBtn) {
            if (!isBarChart && chartType !== 'utbud_efterfragan_delta' && chartType !== 'pendling_detalj') {
                hideAllBtn.classList.remove('hidden'); hideAllBtn.classList.add('flex');
                if (trendChartInstance && trendChartInstance.data) {
                    const anyVis = trendChartInstance.data.datasets.some((ds, i) => trendChartInstance.isDatasetVisible(i));
                    hideAllBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
                }
            } else {
                hideAllBtn.classList.add('hidden'); hideAllBtn.classList.remove('flex');
            }
        }
    } catch(e) {
        console.error("Fel i updateDashboard:", e);
        const desc = document.getElementById('chartDescription');
        if(desc) desc.innerHTML = `<span class="text-red-600 font-bold">Krasch vid ritning av diagram:</span> ${e.message}`;
    }
}

function toggleAllSeries() {
    try {
        if(!trendChartInstance) return;
        const anyVisible = trendChartInstance.data.datasets.some((ds, i) => trendChartInstance.isDatasetVisible(i));
        trendChartInstance.data.datasets.forEach((ds, i) => {
            const meta = trendChartInstance.getDatasetMeta(i);
            meta.hidden = anyVisible;
            globalChartVisibility[ds.label] = anyVisible;
        });
        trendChartInstance.update();
        const btn = document.getElementById('hideAllBtn');
        if (btn) btn.innerHTML = anyVisible ? '<i class="fa-solid fa-eye mr-1"></i> Visa alla' : '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla';
    } catch(e) { console.error(e); }
}