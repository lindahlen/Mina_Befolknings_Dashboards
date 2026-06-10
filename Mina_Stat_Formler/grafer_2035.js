// ==========================================
// Grafer & UI 2035 - Visuell representation
// ==========================================

// --- FUNKTIONER FÖR FAST SKALA ---
window.savedScaleMin = null;
window.savedScaleMax = null;

window.toggleFixedScale = function() {
    const isChecked = document.getElementById('useFixedScale') ? document.getElementById('useFixedScale').checked : false;
    
    if (isChecked && window.trendChartInstance) {
        // Läs av den just nu aktiva grafens skala och spara den
        let currentAxis = window.trendChartInstance.options.indexAxis === 'y' ? 'x' : 'y';
        window.savedScaleMin = window.trendChartInstance.scales[currentAxis].min;
        window.savedScaleMax = window.trendChartInstance.scales[currentAxis].max;
    } else {
        // Återställ auto-skalning
        window.savedScaleMin = null;
        window.savedScaleMax = null;
    }
    
    // Uppdatera grafen omedelbart med/utan den låsta skalan
    if (typeof window.updateDashboard === 'function') window.updateDashboard(false); 
};
// ---------------------------------

// --- SAKNADE HJÄLPFUNKTIONER (Befolkningsgruppering & Export) ---

window.getGroupDefinitions = function(popGroupVal) {
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
};

// NY SMART FUNKTION: Hämtar befolkning från ny Excel-flik ELLER skalar SCB-data
window.getPopForGroupGlobal = function(yStr, group, causalityMode) {
    let pop = 0;
    let numericY = parseInt(yStr);
    let isProg = yStr.includes('Prognos');
    const currentPopData = (window.useCustomPop && window.customPopData) ? window.customPopData : window.popData;

    // 1. Kolla om året finns i Excel-fliken "Befutv" eller "Befolkning_historik" (Kollar oavsett om det är prognosår eller ej)
    let histSheetKey = Object.keys(window.syssBasdata || {}).find(k => k.toLowerCase().includes('befutv') || k.toLowerCase().includes('befolkning_historik'));
    
    if (histSheetKey && window.syssBasdata[histSheetKey]) {
        let row = window.syssBasdata[histSheetKey].find(r => {
            let y = r['År'] !== undefined ? r['År'] : (r['år'] !== undefined ? r['år'] : r['ÅR']);
            return parseInt(y) === numericY;
        });
        
        if (row) {
            Object.keys(row).forEach(k => {
                if (k.toLowerCase() === 'år') return;
                let m = String(k).match(/(\d+)\s*-\s*(\d+)/);
                if (m) {
                    let cMin = parseInt(m[1]), cMax = parseInt(m[2]);
                    // Om kolumnen ryms inom den efterfrågade gruppen
                    if (cMin >= group.min && cMax <= group.max) {
                        pop += parseFloat(row[k]) || 0;
                    }
                }
            });
            if (pop > 0) return pop; 
        }
    }

    // 2. Annars, Fallback till SCB 1-årsdata med skalning
    let records = currentPopData.filter(r => String(r.tid).trim() === yStr);
    if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === yStr.replace(' (Prognos)', ''));
    if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === String(window.baseYear)); 
    if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === `${window.baseYear} (Prognos)`);
    if (records.length === 0 && currentPopData.length > 0) {
        let allTid = [...new Set(currentPopData.map(r => String(r.tid)))];
        records = currentPopData.filter(r => String(r.tid) === allTid[allTid.length - 1]);
    }
    
    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
    let rawGroupPop = 0; let rawTotal16_74 = 0;
    
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
                
                if (age >= minAge && age <= maxAge) rawGroupPop += (r.Befolkning || 0);
                if (age >= 16 && age <= 74) rawTotal16_74 += (r.Befolkning || 0);
            }
        }
    });

    let targetTotalPop = 0;
    if (!isNaN(numericY)) {
        if (isProg && window.progDataStore && window.progDataStore[numericY]) {
            targetTotalPop = window.progDataStore[numericY].pop - (causalityMode === 'dynamic' ? (window.progDataStore[numericY].inducedPop || 0) : 0);
        } else if (!isProg && window.histDataStore && window.histDataStore[numericY]) {
            targetTotalPop = window.histDataStore[numericY].pop;
        }
    }

    if (targetTotalPop > 0 && rawTotal16_74 > 0) {
        pop = rawGroupPop * (targetTotalPop / rawTotal16_74);
    } else {
        pop = rawGroupPop;
    }

    return pop;
};

window.exportPopDynamicCSV = function() {
    const popGroupSelect = document.getElementById('subGroupSelect');
    const popGroupVal = popGroupSelect ? popGroupSelect.value : 'total';
    const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
    
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
        window.allYears.forEach(y => {
            let numericY = Number(y);
            let isProg = numericY > window.baseYear;
            let source = isProg ? 'Prognos' : 'Historik';
            let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
            
            let totalBase16_74 = window.getPopForGroupGlobal(searchStr, { min: 16, max: 74 }, causalityMode);
            
            groups.forEach(g => {
                let groupBase = window.getPopForGroupGlobal(searchStr, g, causalityMode);
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
    if (Object.keys(window.progDataStore || {}).length === 0 && Object.keys(window.histDataStore || {}).length === 0) {
        alert("Ingen data finns att exportera.");
        return;
    }
    
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF"; 
    csvContent += "År;Källa;Efterfrågan (Jobb);Lokalt Utbud (Nattbef.);Inpendling;Utpendling;Pendlingsnetto;Virtuellt Utbud;Totalt Utbud (Inkl. Pendling);Omatchat Gap;Befolkningsbehov;Sysselsättningsgrad (%);BRP per sysselsatt (tkr);Total BRP (Mkr);Arbetslöshet (%);Långtidsarbetslöshet (%)\n";
    
    const migrantSyssSlider = document.getElementById('migrantSyssSlider');
    const userSyssAdjustment = migrantSyssSlider ? parseFloat(migrantSyssSlider.value) / 100 : 0.10;
    const baseEmploymentRate = window.globalMigrantEmploymentRate || 0.50;
    const employmentRate = baseEmploymentRate + userSyssAdjustment;
    const simMode = document.getElementById('simMode') ? document.getElementById('simMode').value : 'full';
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

    const progYears = Object.keys(window.progDataStore || {}).map(Number).sort((a,b)=>a-b);
    let histYears = Object.keys(window.histDataStore || {}).map(Number).sort((a,b)=>a-b);
    
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
// ----------------------------------------------------------------

window.aggregateMatchData = function(dataset, refYear, labels, keyField, mapFn = null) {
    let result = { 'män': {}, 'kvinnor': {}, 'totalt': {} };
    labels.forEach(l => { result['män'][l] = 0; result['kvinnor'][l] = 0; result['totalt'][l] = 0; });
    
    let records = dataset.filter(r => window.extractYear(r) == refYear);
    if (records.length === 0) return result;
    
    let hasKonCol = records.some(r => window.getKon(r) !== null);
    let hasTotalRow = hasKonCol ? records.some(r => window.getKon(r) === 'totalt' || window.getKon(r) === '') : false;
    
    records.forEach(r => {
        let kon = window.getKon(r);
        if (!hasKonCol || kon === null || kon === '') kon = 'totalt'; 
        
        let isCountableTotal = false;
        if (!hasKonCol) {
            isCountableTotal = true;
        } else if (hasTotalRow) {
            isCountableTotal = (kon === 'totalt');
        } else {
            isCountableTotal = (kon === 'män' || kon === 'kvinnor');
        }
        
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
};

window.drawMatchChart = function(year, labels, dagData, nattData, splitGender, useZeroAxis, isHorizontal = false) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (window.trendChartInstance) {
        window.trendChartInstance.destroy();
        window.trendChartInstance = null;
    }
    
    let isProg = window.progDataStore && window.progDataStore[year] !== undefined;

    if (isProg && window.histDataStore && window.histDataStore[window.baseYear]) {
        const progD = window.progDataStore[year];
        const baseD = window.histDataStore[window.baseYear];
        const simModeEl = document.getElementById('simMode');
        const simMode = simModeEl ? simModeEl.value : 'full';
        const causalityModeEl = document.getElementById('causalityMode');
        const causalityMode = causalityModeEl ? causalityModeEl.value : 'analytic';
        
        const demandScale = (progD.demand && baseD.demand > 0) ? (progD.demand / baseD.demand) : 1;
        const supplyScale = simMode === 'full' 
            ? ((progD.totalSupply && baseD.totalSupply > 0) ? (progD.totalSupply / baseD.totalSupply) : 1) 
            : ((progD.supply && baseD.supply > 0) ? (progD.supply / baseD.supply) : 1);
        
        ['totalt', 'män', 'kvinnor'].forEach(kon => {
            labels.forEach(l => {
                if (dagData[kon] && dagData[kon][l] !== undefined) dagData[kon][l] *= demandScale;
                if (nattData[kon] && nattData[kon][l] !== undefined) nattData[kon][l] *= supplyScale;
            });
        });

        // --- UPPDATERA GRAF-DATA (ÅRTAL SOM KOLUMNER) ---
        // --- NY LOGIK FÖR GRAFEN (BÅDA EXCEL-FLIKARNA) ---
            let activeNaringTab = 'Näringslivsjustering';
            let naringSkala = window.currentNaringSkala !== undefined ? window.currentNaringSkala : 1.0;

            if (window.currentActiveScenario === 'high' && window.syssConfig['Näringslivsjustering_hög']) {
                activeNaringTab = 'Näringslivsjustering_hög';
                naringSkala = 1.0;
            }

            if (window.syssConfig[activeNaringTab]) {
                window.syssConfig[activeNaringTab].forEach(row => {
                    let branschCol = Object.keys(row).find(k => {
                        let kl = String(k).toLowerCase().replace(/\s/g, '');
                        return ['bransch', 'sninamn', 'näringsgren', 'sni', 'snibokstav'].includes(kl);
                    }) || Object.keys(row)[0];
                    
                    let bransch = String(row[branschCol] || '').trim();
                    if (bransch.toLowerCase() === 'totalt' || bransch.toLowerCase() === 'summa' || bransch === '') return;

                    let ackumuleratVal = 0;
                    for (let y = window.baseYear + 1; y <= year; y++) {
                         let valStr = row[String(y)] !== undefined ? row[String(y)] : (row[y] !== undefined ? row[y] : 0);
                         ackumuleratVal += (parseFloat(valStr) || 0);
                    }
                    
                    let val = ackumuleratVal * naringSkala;
                    
                    if (bransch && val !== 0 && dagData['totalt'] && dagData['totalt'][bransch] !== undefined) {
                        let mShare = 0.5; 
                        
                        dagData['totalt'][bransch] += val;
                        if(dagData['män']) dagData['män'][bransch] += val * mShare;
                        if(dagData['kvinnor']) dagData['kvinnor'][bransch] += val * (1 - mShare);

                        if (causalityMode === 'dynamic') {
                            nattData['totalt'][bransch] += val;
                            if(nattData['män']) nattData['män'][bransch] += val * mShare;
                            if(nattData['kvinnor']) nattData['kvinnor'][bransch] += val * (1 - mShare);
                        }
                        
                        // Applicera branschglidning i grafen
                        if (val > 0 && window.syssConfig['Branschglidning']) {
                            let glidningar = window.syssConfig['Branschglidning'].filter(g => String(g['Växande_Bransch'] || g['Växande bransch'] || g['Växande']).trim() === bransch);
                            glidningar.forEach(g => {
                                let drabbad = String(g['Drabbad_Bransch'] || g['Drabbad bransch'] || g['Drabbad']).trim();
                                let faktor = parseFloat(g['Överföringsfaktor'] || g['Kvot']) || 0;
                                let tapp = val * faktor;
                                
                                if (tapp > 0 && dagData['totalt'][drabbad] !== undefined) {
                                    dagData['totalt'][drabbad] -= tapp;
                                    if(dagData['män']) dagData['män'][drabbad] -= tapp * mShare;
                                    if(dagData['kvinnor']) dagData['kvinnor'][drabbad] -= tapp * (1 - mShare);

                                    if (causalityMode === 'dynamic') {
                                        nattData['totalt'][drabbad] -= tapp;
                                        if(nattData['män']) nattData['män'][drabbad] -= tapp * mShare;
                                        if(nattData['kvinnor']) nattData['kvinnor'][drabbad] -= tapp * (1 - mShare);
                                    }
                                }
                            });
                        }
                    }
                });
            }
            // --- SLUT PÅ DET NYA BLOCKET ---
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
        labels.forEach(l => { netData[l] = nattData['totalt'][l] - dagData['totalt'][l]; });
        
        const simModeEl = document.getElementById('simMode');
        const supplyLabel = (simModeEl && simModeEl.value === 'full') ? 'Utbud (Inkl. all pendling)' : 'Lokalt Utbud (Nattbef.)';

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
    const graceVal = yGraceElement && yGraceElement.style.display !== 'none' ? yGraceElement.value : '20%';
    
    const scaleConfig = isHorizontal ? {
        x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
        y: { ticks: { font: { size: 10 } } }
    } : {
        x: { ticks: { font: { size: 10 } } },
        y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
    };

    window.trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            indexAxis: isHorizontal ? 'y' : 'x', 
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: scaleConfig,
            plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, 0) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
        }
    });
};

window.updateDashboard = function(calledFromDropdown = true) {
    // --- LÄGG TILL DETTA HÄR: ---
        if (calledFromDropdown) {
            const fixedScaleCb = document.getElementById('useFixedScale');
            if (fixedScaleCb && fixedScaleCb.checked) {
                fixedScaleCb.checked = false;
                window.savedScaleMin = null;
                window.savedScaleMax = null;
            }
            
            // NYTT: Krasch-säker hantering av "Utgå från 0" (Rör bara DOM-elementet)
            const cType = document.getElementById('chartType') ? document.getElementById('chartType').value : null;
            const zeroCb = document.getElementById('useZeroAxis');
            if (zeroCb && cType) {
                if (window.lastSelectedChart !== cType) {
                    if (cType === 'bostadsbyggande_behov') {
                        zeroCb.checked = true;
                    } else {
                        zeroCb.checked = false;
                    }
                    window.lastSelectedChart = cType;
                }
            }
        }
        // ----------------------------
    const chartTypeElement = document.getElementById('chartType');
    const subGroupSelect = document.getElementById('subGroupSelect');
    if (!chartTypeElement || !subGroupSelect) return;

    const chartType = chartTypeElement.value;
    // --- NYTT: Dölj "Fast skala" dynamiskt för vissa grafer ---
            const fixedScaleContainer = document.getElementById('fixedScaleContainer');
            if (fixedScaleContainer) {
                if (chartType.includes('match') || chartType === 'pendling_detalj' || chartType === 'medfoljande_behov' || chartType === 'utbud_efterfragan_delta') {
                    fixedScaleContainer.style.display = 'none';
                } else {
                    fixedScaleContainer.style.display = 'flex';
                }
            }
            // ---------------------------------------------------------
    
    const dualAxesContainer = document.getElementById('dualAxesContainer');
    const useDualAxesElement = document.getElementById('useDualAxes');

    // --- NY LOGIK FÖR STANDARDVÄRDEN (DELADE AXLAR) ---
    // Denna känner av om vi bytt diagramtyp sedan senast. Om ja, sätter den rätt default-kryss!
    if (window.lastChartType !== chartType) {
        if (useDualAxesElement) {
            if (chartType.includes('_utrikes')) {
                useDualAxesElement.checked = true; // Alltid på för inrikes/utrikes
            } else if (chartType.includes('_kon')) {
                useDualAxesElement.checked = false; // Alltid av för män/kvinnor
            }
        }
        window.lastChartType = chartType;
    }
    
    let useDualAxes = useDualAxesElement ? useDualAxesElement.checked : false;
    const useZeroAxisElement = document.getElementById('useZeroAxis');
    const useZeroAxis = useZeroAxisElement ? useZeroAxisElement.checked : false;

    // Förenklad kontroll: Alla diagram med _utrikes eller _kon stödjer delade axlar
    if (!(chartType.includes('_utrikes') || chartType.includes('_kon'))) {
        useDualAxes = false;
    }

    const exportPopBtn = document.getElementById('exportPopBtn');

    // --- UI LOGIK FÖR RULLISTOR OCH KNAPPAR BEROENDE PÅ DIAGRAM ---
    if (chartType === 'pop_dynamic') {
        if(exportPopBtn) exportPopBtn.classList.replace('hidden', 'flex');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        if (subGroupSelect.getAttribute('data-type') !== 'pop_dynamic') {
            subGroupSelect.innerHTML = '<option value="total">Totalt 16-74 år</option><option value="func">Funktionella grupper</option><option value="5yr">5-årsklasser</option>';
            subGroupSelect.setAttribute('data-type', 'pop_dynamic');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType.includes('arbetsloshet') || chartType.includes('langtidsarb')) {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer && (chartType.includes('_utrikes') || chartType.includes('_kon'))) { 
            dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); 
        } else if (dualAxesContainer) { 
            dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); 
        }
        
        let dataTypeKey = chartType.includes('langtidsarb') ? 'larb_type' : 'arb_type';
        if (subGroupSelect.getAttribute('data-type') !== dataTypeKey) {
            subGroupSelect.innerHTML = '<option value="pct">Andel av arbetskraften (%)</option>';
            if (chartType.includes('langtidsarb')) {
                subGroupSelect.innerHTML += '<option value="insk">Andel av inskrivna arbetslösa (%)</option>';
            }
            subGroupSelect.innerHTML += '<option value="num">Antal personer</option>';
            subGroupSelect.setAttribute('data-type', dataTypeKey);
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'pendling_detalj') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        
        if (subGroupSelect.getAttribute('data-type') !== 'pendling_dir') {
            subGroupSelect.innerHTML = '<option value="neg">Utpendling visas som negativ (-)</option><option value="pos">Utpendling visas som positiv (+)</option>';
            subGroupSelect.setAttribute('data-type', 'pendling_dir');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'bransch_match') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        if (subGroupSelect.getAttribute('data-type') !== 'bransch') {
            subGroupSelect.innerHTML = '<option value="all">Alla branscher (SNI)</option>';
            if (window.syssConfig && window.syssConfig['SNIgrupper'] && window.syssConfig['SNIgrupper'].length > 0) {
                const firstRow = window.syssConfig['SNIgrupper'][0];
                const groupCols = Object.keys(firstRow).slice(1);
                groupCols.forEach(col => subGroupSelect.add(new Option(col, col)));
            }
            subGroupSelect.setAttribute('data-type', 'bransch');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'syssgrad_kon' || chartType === 'syssgrad_utrikes' || chartType === 'trend_kon' || chartType === 'trend_utrikes') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        
        if(dualAxesContainer) { dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); }
        
        if (chartType === 'syssgrad_kon') {
            if (subGroupSelect.getAttribute('data-type') !== 'syssgrad') {
                subGroupSelect.innerHTML = '';
                const sampleY = Object.keys(window.histDataStore).find(k => window.histDataStore[k].syssGradM);
                if (sampleY) {
                    const keys = Object.keys(window.histDataStore[sampleY].syssGradM).filter(k => !['År', 'år', 'Kön', 'kön'].includes(k));
                    keys.forEach(k => subGroupSelect.add(new Option(k, k)));
                    let defaultOpt = Array.from(subGroupSelect.options).find(o => o.value.includes('20-64'));
                    if (!defaultOpt && subGroupSelect.options.length > 0) defaultOpt = subGroupSelect.options[0];
                    if (defaultOpt) subGroupSelect.value = defaultOpt.value;
                }
                subGroupSelect.setAttribute('data-type', 'syssgrad');
            }
            subGroupSelect.classList.remove('hidden');
            chartTypeElement.classList.remove('rounded-r');
            subGroupSelect.classList.add('rounded-r');
        } else if (chartType === 'trend_kon') {
            if (subGroupSelect.getAttribute('data-type') !== 'trend_kon_age') {
                subGroupSelect.innerHTML = '<option value="totalt">Totalt</option>';
                const ageLabels = ['16-19', '20-24', '25-34', '35-44', '45-54', '55-59', '60-64', '65-74'];
                ageLabels.forEach(k => subGroupSelect.add(new Option(k + " år", k)));
                subGroupSelect.setAttribute('data-type', 'trend_kon_age');
            }
            subGroupSelect.classList.remove('hidden');
            chartTypeElement.classList.remove('rounded-r');
            subGroupSelect.classList.add('rounded-r');
        } else {
            subGroupSelect.classList.add('hidden');
            chartTypeElement.classList.add('rounded-r');
        }
        
    } else {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        subGroupSelect.classList.add('hidden');
        chartTypeElement.classList.add('rounded-r');
    }

    const startYearSelect = document.getElementById('startYearSelect');
    const desc = document.getElementById('chartDescription');
    if (desc) {
    desc.innerHTML = ''; // NYTT: Sudda alltid ut den gamla texten först!
    }
    const title = document.getElementById('trendTitle');
    const selectedYearStr = document.getElementById('yearSelect').value;
    const ctx = document.getElementById('trendChart').getContext('2d');
    const wrapper = document.getElementById('chartWrapper');
    
    const isComparing = window.savedProjectedData !== null;
    const simMode = document.getElementById('simMode').value;
    const showCommuting = simMode === 'full';
    const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
    
    const selYearInt = parseInt(selectedYearStr);
    const isProgYear = window.progDataStore && window.progDataStore[selYearInt] !== undefined;
    const refYear = isProgYear ? window.baseYear : selYearInt;
    const currentPopData = (window.useCustomPop && window.customPopData) ? window.customPopData : window.popData;
    
    if (window.trendChartInstance) {
        window.trendChartInstance.data.datasets.forEach((ds, i) => {
            const meta = window.trendChartInstance.getDatasetMeta(i);
            window.globalChartVisibility[ds.label] = meta.hidden === null ? ds.hidden : meta.hidden;
        });
        window.trendChartInstance.destroy();
        window.trendChartInstance = null;
    }

    wrapper.style.minHeight = '300px';
    const yGraceElement = document.getElementById('yGrace');
    const graceVal = (typeof window.SHOW_Y_GRACE_UI !== 'undefined' && window.SHOW_Y_GRACE_UI) && yGraceElement ? yGraceElement.value : (window.DEFAULT_Y_GRACE || '20%');

    let labels = []; let datasets = []; let isHorizontal = false; let isStacked = false; let isBarChart = false; let customScale = null; let isMultiLine = false;
    const graphStartYear = isComparing ? window.baseYear : (parseInt(startYearSelect.value) || (window.allYears && window.allYears.length > 0 ? window.allYears[0] : 0));
    const activeYears = window.allYears ? window.allYears.filter(y => y >= graphStartYear) : [];

    // ==================
    // RITLOGIK PER TYP
    // ==================
    if (chartType === 'pop_dynamic') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : " (Historik)");
        if (title) title.innerText = "Framtida Befolkning 16-74 år (Dynamisk)" + suffix;
        
        if (desc) {
            // Skapa texten baserat på vilket läge som är valt
            const infoText = causalityMode === 'dynamic' 
                ? "Visar kommunens basbefolkning (16–74 år) samt det simulerade befolkningstillskottet från den nya arbetskraftsinflyttningen."
                : "Visar kommunens basbefolkning (16–74 år). <span class='text-amber-700 font-medium'>Byt till Dynamiskt scenario och klicka på Kör för att simulera inflyttning från nya jobb.</span>";

            // Baka in texten tillsammans med i-knappen
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            <p class="mb-2"><strong>Arbetsför ålder:</strong> Diagrammet fokuserar på åldersspannet 16–74 år, vilket utgör kärnan i den lokala arbetskraften.</p>
                            <p class="mb-2"><strong>Exportera data:</strong> Klicka på CSV-knappen för att ladda ner den underliggande befolkningsdatan för egna analyser. Denna funktion är unik för just denna vy.</p>
                            <p><strong>Tips!</strong> Använd rullistan bredvid för att bryta ner staplarna i "Funktionella grupper" eller "5-årsklasser" för att se exakt åldersprofil.</p>
                            
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span>${infoText}</span>
                </div>
            `;
        }

        const popGroupVal = subGroupSelect.value;
        let hasProg = false;
        labels = activeYears;

        if (popGroupVal === 'total') {
            let h_pop=[], p_base=[], p_induced=[];
            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= window.baseYear && window.histDataStore[numericY]) h_pop.push(window.histDataStore[numericY].pop);
                else h_pop.push(null);
                
                if (y > window.baseYear && window.progDataStore[numericY]) {
                    let d = window.progDataStore[numericY];
                    let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                    let base = d.pop - induced;
                    p_base.push(base); p_induced.push(induced); hasProg = true;
                } else if (y === window.baseYear && window.histDataStore[numericY]) {
                    p_base.push(window.histDataStore[numericY].pop); p_induced.push(0);
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
                let groups = window.getGroupDefinitions(popGroupVal);
                
                groups.forEach((g, idx) => {
                    let h_data = [], p_data = [];
                    labels.forEach((yStr) => {
                        let numericY = Number(yStr);
                        let isProg = numericY > baseYear;
                        let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
                        
                        // ANVÄNDER NYA GLOBALA FUNKTIONEN FÖR RÄTT HISTORIK!
                        let groupBase = window.getPopForGroupGlobal(searchStr, g, causalityMode);
                        let totalBase16_74 = window.getPopForGroupGlobal(searchStr, { min: 16, max: 74 }, causalityMode);
                        
                        let finalPop = groupBase;
                        if (isProg && progDataStore[numericY] && causalityMode === 'dynamic') {
                            let induced = progDataStore[numericY].inducedPop || 0;
                            let groupInduced = totalBase16_74 > 0 ? induced * (groupBase / totalBase16_74) : 0;
                            finalPop += groupInduced;
                        }
                        
                        if (isProg) { 
                            h_data.push(null); 
                            p_data.push(finalPop); 
                            hasProg = true; 
                        } else { 
                            h_data.push(finalPop); 
                            p_data.push(null); 
                        }
                    });
                    
                    labels.forEach((yStr, idx2) => { 
                        if (Number(yStr) === baseYear && idx2 < labels.length - 1) p_data[idx2] = h_data[idx2]; 
                    });
                    
                    datasets.push({ label: g.label, data: h_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true });
                    if (p_data.some(v => v !== null)) {
                        datasets.push({ label: g.label + ' (Prognos)', data: p_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
                    }
                });
            }
            } else if (chartType === 'bostadsbyggande_behov') {
            startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
            let suffix = isComparing ? " (Jämförelse)" : (progDataStore[allYears[allYears.length-1]] ? " (Scenario)" : "");
            if (title) title.innerText = "Bostadsbyggande & Behov" + suffix;
            if (desc) {
                const infoText = causalityMode === 'dynamic' 
                    ? "Visar historiskt färdigställda bostäder jämfört med det årliga nya behovet (basprognos + simulerat nettotillskott inkl. familjer)." 
                    : "Visar historiskt färdigställda bostäder jämfört med det teoretiska nya behovet (basprognos + tillskott från rekryteringsgap inkl. familjer).";

                desc.innerHTML = `
                    <div class="flex items-center gap-2">
                        <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                            <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                            
                            <div class="absolute z-[100] hidden group-hover:block w-72 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                                <p class="mb-2"><strong>Flödesmodell:</strong> Kalkylen visar det faktiska nya behovet per enskilt år baserat på 2,1 boende per ny bostad.</p>
                                <p class="mb-2"><strong>Familjemultiplikator:</strong> Inflyttande arbetskraft från jobbtillväxt skalas upp med 33 % för att inkludera medföljande barn och äldre (baserat på att ca 75 % är i arbetsför ålder).</p>
                                <p><strong>Tips!</strong> Klicka på "10-årigt historiskt snitt" i teckenförklaringen för att tända/släcka jämförelselinjen.</p>
                                
                                <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                            </div>
                        </span>
                        <span>${infoText}</span>
                    </div>
                `;
            } 
            isBarChart = true;
            isStacked = true;
            labels = activeYears;

            let hBostader = [], pBehovBase = [], pBehovExtra = [], sBehovBase = [], sBehovExtra = [], maxKapacitet = [], rollingAvgData = [];
            let userSyssAdj = document.getElementById('migrantSyssSlider') ? parseFloat(document.getElementById('migrantSyssSlider').value) / 100 : 0.10;
            let empRate = Math.max(0.01, (window.globalMigrantEmploymentRate || 0.5) + userSyssAdj);
            
            let byggTak = (window.takEffekter && window.takEffekter.maxBostadsproduktion) ? window.takEffekter.maxBostadsproduktion : 1500;

            let sistaHistoriskaAr = baseYear;
            if (currentPopData && currentPopData.find(r => String(r.tid).replace(' (Prognos)', '').trim() === String(baseYear + 1) && r.Färdigställda_bostäder !== undefined && r.Färdigställda_bostäder !== null && r.Färdigställda_bostäder !== "")) {
                sistaHistoriskaAr = baseYear + 1;
            }

            let getPop0to100 = (yVal) => {
                let sum = 0;
                if (window.syssBasdata) {
                    let pSource = typeof popSource !== 'undefined' ? popSource : (window.popSource || null);
                    let sheetKeys = [];
                    
                    if (pSource && window.syssBasdata[pSource]) {
                        sheetKeys = [pSource];
                    } else {
                        sheetKeys = Object.keys(window.syssBasdata).filter(k => k.toLowerCase().includes('prognos'));
                    }
                    
                    for (let key of sheetKeys) {
                        let rows = window.syssBasdata[key].filter(r => parseInt(r['År'] || r['år'] || r['ÅR']) === parseInt(yVal));
                        if (rows.length > 0) {
                            rows.forEach(row => {
                                Object.keys(row).forEach(k => {
                                    if (/^\d+$/.test(String(k).trim())) {
                                        sum += parseFloat(row[k]) || 0;
                                    }
                                });
                            });
                            if (sum > 0) return sum;
                        }
                    }
                }
                
                let pData = typeof currentPopData !== 'undefined' ? currentPopData : (window.popData || []);
                let recs = pData.filter(r => String(r.tid).replace(' (Prognos)', '').trim() === String(yVal));
                if (recs.length > 0) {
                    recs.forEach(r => {
                        if (!String(r.ålder).toLowerCase().includes('totalt')) {
                            sum += parseFloat(r.Befolkning) || 0;
                        }
                    });
                }
                return sum;
            };

            labels.forEach((y, index) => {
                let numericY = Number(y);
                maxKapacitet.push(byggTak);

                // Hantera rullande 10-årssnitt
                let endYearForAvg = numericY > sistaHistoriskaAr ? sistaHistoriskaAr : numericY;
                let sumBostader = 0;
                let countBostader = 0;
                
                for (let i = 0; i < 10; i++) {
                    let lookbackYear = endYearForAvg - i;
                    let popRec10 = currentPopData ? currentPopData.find(r => String(r.tid).replace(' (Prognos)', '').trim() === String(lookbackYear) && r.Färdigställda_bostäder !== undefined && r.Färdigställda_bostäder !== null && String(r.Färdigställda_bostäder).trim() !== "") : null;
                    if (popRec10) {
                        sumBostader += parseFloat(popRec10.Färdigställda_bostäder);
                        countBostader++;
                    }
                }
                rollingAvgData.push(countBostader > 0 ? (sumBostader / countBostader) : null);

                let popRec = null;
                if (currentPopData && numericY <= sistaHistoriskaAr) {
                    popRec = currentPopData.find(r => String(r.tid).replace(' (Prognos)', '').trim() === String(numericY) && r.Färdigställda_bostäder !== undefined && r.Färdigställda_bostäder !== null && String(r.Färdigställda_bostäder).trim() !== "");
                }

                if (popRec) {
                    hBostader.push(parseFloat(popRec.Färdigställda_bostäder));
                    pBehovBase.push(null);
                    pBehovExtra.push(null);
                    sBehovBase.push(null);
                    sBehovExtra.push(null);
                } 
                else if (numericY > baseYear && progDataStore[numericY]) {
                    hBostader.push(null);
                    
                    let calcBehovBase = (ar) => {
                        let pCurr = getPop0to100(ar);
                        let pPrev = getPop0to100(ar - 1);
                        let popGrowthBase = 0;
                        
                        if (pCurr > 0 && pPrev > 0) {
                            popGrowthBase = Math.max(0, pCurr - pPrev);
                        }

                        if (popGrowthBase === 0 && ar <= baseYear + 2) {
                            let pNext = getPop0to100(ar + 1);
                            if (pNext > pCurr) {
                                popGrowthBase = pNext - pCurr;
                            }
                        }

                        return popGrowthBase > 0 ? popGrowthBase / 2.1 : 0;
                    };

                    let calcBehovExtra = (store, ar) => {
                        let dCurr = store[ar];
                        let dPrev = store[ar - 1];
                        if (!dCurr) return 0;

                        let extraPopNeededCurr = 0;
                        let extraPopNeededPrev = 0;

                        if (causalityMode === 'dynamic' && dCurr.inducedPop > 0) {
                            extraPopNeededCurr = dCurr.inducedPop;
                        } else if (causalityMode === 'analytic') {
                            const gapCurr = dCurr.demand - (dCurr.supply + (showCommuting ? ((dCurr.netCommuting !== undefined ? dCurr.netCommuting : (dCurr.explicitNetCommuting || 0)) + (dCurr.virtualSupply || 0)) : 0));
                            if (gapCurr > 5) extraPopNeededCurr = gapCurr / empRate;
                        }

                        if (dPrev) {
                            if (causalityMode === 'dynamic' && dPrev.inducedPop > 0) {
                                extraPopNeededPrev = dPrev.inducedPop;
                            } else if (causalityMode === 'analytic') {
                                const gapPrev = dPrev.demand - (dPrev.supply + (showCommuting ? ((dPrev.netCommuting !== undefined ? dPrev.netCommuting : (dPrev.explicitNetCommuting || 0)) + (dPrev.virtualSupply || 0)) : 0));
                                if (gapPrev > 5) extraPopNeededPrev = gapPrev / empRate;
                            }
                        }

                        // Det årliga flödet (endast arbetare)
                        let annualNetPop = Math.max(0, extraPopNeededCurr - extraPopNeededPrev);
                        
                        // SKALA UPP för medföljande familjemedlemmar (16-74 år -> 0-100 år)
                        let totalDemographicInflow = annualNetPop * 1.33;
                        
                        // Dela med 2.1 för att få fram antalet bostäder
                        return totalDemographicInflow > 0 ? totalDemographicInflow / 2.1 : 0; 
                    };

                    let baseNeed = calcBehovBase(numericY);
                    pBehovBase.push(baseNeed);
                    pBehovExtra.push(calcBehovExtra(progDataStore, numericY));

                    if (isComparing) {
                        sBehovBase.push(baseNeed);
                        sBehovExtra.push(savedProjectedData ? calcBehovExtra(savedProjectedData, numericY) : null);
                    }
                }
                else {
                    hBostader.push(null);
                    pBehovBase.push(null);
                    pBehovExtra.push(null);
                    sBehovBase.push(null);
                    sBehovExtra.push(null);
                }
            });

            datasets = [
                { type: 'bar', label: 'Färdigställda Bostäder (Historik)', data: hBostader, backgroundColor: '#0ea5e9', stack: 'Stack 1' },
                { type: 'bar', label: 'Behov från Basprognos (Scenario)', data: pBehovBase, backgroundColor: '#fcd34d', stack: 'Stack 1' },
                { type: 'bar', label: 'Extra behov från Jobb (Scenario)', data: pBehovExtra, backgroundColor: '#f59e0b', stack: 'Stack 1' }
            ];
            
            if (isComparing) {
                datasets.push({ type: 'bar', label: 'Behov från Basprognos (Sparad)', data: sBehovBase, backgroundColor: 'rgba(252, 211, 77, 0.4)', stack: 'Stack 2' });
                datasets.push({ type: 'bar', label: 'Extra behov från Jobb (Sparad)', data: sBehovExtra, backgroundColor: 'rgba(245, 158, 11, 0.4)', stack: 'Stack 2' });
            }

            datasets.push({ type: 'line', label: '10-årssnitt (Historisk Byggtakt)', data: rollingAvgData, borderColor: '#64748b', borderWidth: 2, pointStyle: false, fill: false, hidden: true });
            datasets.push({ type: 'line', label: 'Kapacitetstak (Byggproduktion)', data: maxKapacitet, borderColor: '#ef4444', borderWidth: 2, borderDash: [5,5], pointStyle: false, fill: false });

            customScale = { y: { stacked: true, beginAtZero: true, min: 0, ticks: { callback: val => typeof window.formatNumber === 'function' ? window.formatNumber(val, 0) : val } } };

    } else if (chartType === 'medfoljande_behov') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore && window.allYears && window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : "");
        if (title) title.innerText = "Välfärdsbehov (Medföljande barn)" + suffix;
        
        if (desc) {
            const infoText = causalityMode === 'dynamic' 
                ? "Visar uppskattat behov av nya förskole- och skolplatser som genereras av arbetskraftsinflyttningen varje år."
                : "<span class='text-amber-700 font-medium'>Denna vy visar inga data i Analytiskt läge. Byt till ett Dynamiskt scenario i panelen ovan och klicka på Kör.</span>";

            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        
                        <div class="absolute z-[100] hidden group-hover:block w-72 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            <p class="mb-2"><strong>Medföljande familjer:</strong> När du simulerar effekten av nya jobb beräknar kalkylatorn hur många barnfamiljer som flyttar in.</p>
                            <p class="mb-2"><strong>Flödesmodell:</strong> Diagrammet visar det årliga nettotillskottet (hur många *nya* platser som måste skapas). <br><br><em>Obs: De inledande prognosåren är dolda då de utgör övergångsår i beräkningsmotorn.</em></p>
                            
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span>${infoText}</span>
                </div>
            `;
        }
        
        isBarChart = true;
        isStacked = true;

        let categories = [];
        if (window.syssConfig && window.syssConfig['Medföljande'] && window.syssConfig['Medföljande'].length > 0) {
            categories = window.syssConfig['Medföljande'].map(r => r['Skolform_Ålder']).filter(c => c);
        } else {
            categories = ['Förskola (0-5 år)', 'Grundskola F-3 (6-9 år)', 'Grundskola 4-9 (10-15 år)', 'Gymnasium (16-18 år)']; 
        }

        // Hämta enbart prognosåren (efter baseYear)
        let forecastYears = activeYears.filter(y => y > window.baseYear); 
        if (forecastYears.length === 0) forecastYears = [(window.baseYear+1).toString()]; 
        
        // Identifiera de två första prognosåren (övergångsåren)
        let hiddenYears = [];
        if (forecastYears.length > 0) hiddenYears.push(forecastYears[0]);
        if (forecastYears.length > 1) hiddenYears.push(forecastYears[1]);

        // Bygg etiketterna för X-axeln. De två första åren får "(Redovisas ej)"
        labels = forecastYears.map((y, index) => {
            if (index === 0 || index === 1) return [y, '(Redovisas ej)'];
            return y;
        });
        
        const colors = ['#f59e0b', '#10b981', '#0ea5e9', '#8b5cf6', '#ec4899'];
        
        categories.forEach((cat, idx) => {
            let p_data = [];
            forecastYears.forEach(y => {
                let numericY = Number(y);
                let currentVal = 0;
                let prevVal = 0;

                // Hämta ackumulerat värde för aktuellt år
                if (window.progDataStore && window.progDataStore[numericY] && window.progDataStore[numericY].medfoljande) {
                    currentVal = window.progDataStore[numericY].medfoljande[cat] || 0;
                }

                // Hämta ackumulerat värde för föregående år
                if (window.progDataStore && window.progDataStore[numericY - 1] && window.progDataStore[numericY - 1].medfoljande) {
                    prevVal = window.progDataStore[numericY - 1].medfoljande[cat] || 0;
                }

                // Räkna ut årets nettoförändring
                let annualNet = Math.max(0, currentVal - prevVal);

                // Nolla stapeln om det är något av övergångsåren, annars tryck in det faktiska årliga behovet
                if (hiddenYears.includes(y)) {
                    p_data.push(null);
                } else {
                    p_data.push(annualNet);
                }
            });
            
            datasets.push({
                type: 'bar',
                label: cat,
                data: p_data,
                backgroundColor: colors[idx % colors.length]
            });
        });
        
        customScale = { 
            y: { 
                stacked: true, 
                beginAtZero: true,
                min: 0, 
                ticks: { callback: val => typeof window.formatNumber === 'function' ? window.formatNumber(val, 0) : val } 
            } 
        };

    } else if (chartType === 'utbud_efterfragan') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : " (Historik)");
        if (title) title.innerText = "Utbud vs Efterfrågan" + suffix;
        
        if (desc) {
            // Skapa texten baserat på vilka lägen och pendlingsval som är aktiverade
            let infoText = "";
            if (causalityMode === 'dynamic') {
                infoText = "I <b>Dynamiskt läge</b> anpassar sig utbudet (den blå och lila linjen) automatiskt efter företagens efterfrågan. Grafen visar den slutgiltiga balansen.";
            } else if (showCommuting) {
                infoText = "Visar Efterfrågan (Jobb/Grön), lokalt Utbud (Bosatta/Blå) samt Totalt Utbud inkl. pendling (Streckad lila). När den lila fångar den gröna är arbetsmarknaden i balans!";
            } else {
                infoText = "Visar Efterfrågan (Jobb/Grön) och lokalt Utbud (Bosatta/Blå). Pendling visas ej i denna vy.";
            }

            // Baka in texten tillsammans med i-knappen (Nu med MAGNET-effekt!)
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            <p class="mb-2"><strong>Arbetsmarknadens motor:</strong> Visar gapet mellan antalet jobb i kommunen (Efterfrågan) och storleken på den lokala arbetskraften (Utbud).</p>
                            <p class="mb-2"><strong>Pendling (Full / Endast Demografi):</strong> Byt simuleringstyp högst upp i panelen för att styra om in- och utpendling (den lila linjen) ska räknas med för att fylla gapet, eller om du enbart vill se kommunens egen arbetskraft.</p>
                            <p><strong>Tips!</strong> Använd årtals-rullistan ovanför diagrammet! När du byter år där uppdateras direkt alla nyckeltalsrutor med exakta siffror för just det året.</p>
                            
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}</span>
                </div>
            `;
        }

        labels = activeYears;
        let hDemand=[], hSupply=[], hTotalSupply=[], pDemand=[], pSupply=[], pTotalSupply=[], sDemand=[], sSupply=[], sTotalSupply=[];

        labels.forEach(y => {
            let numericY = Number(y);
            if (y <= window.baseYear && window.histDataStore[numericY]) { hDemand.push(window.histDataStore[numericY].demand); hSupply.push(window.histDataStore[numericY].supply); hTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
            else { hDemand.push(null); hSupply.push(null); hTotalSupply.push(null); }
            
            if (y === window.baseYear && window.histDataStore[numericY]) { pDemand.push(window.histDataStore[numericY].demand); pSupply.push(window.histDataStore[numericY].supply); pTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
            else if (y > window.baseYear && window.progDataStore[numericY]) { pDemand.push(window.progDataStore[numericY].demand); pSupply.push(window.progDataStore[numericY].supply); pTotalSupply.push(window.progDataStore[numericY].totalSupply); } 
            else { pDemand.push(null); pSupply.push(null); pTotalSupply.push(null); }
            
            if (isComparing) {
                if (y <= window.baseYear && window.histDataStore[numericY]) { sDemand.push(window.histDataStore[numericY].demand); sSupply.push(window.histDataStore[numericY].supply); sTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
                else if (y > window.baseYear && window.savedProjectedData && window.savedProjectedData[numericY]) { sDemand.push(window.savedProjectedData[numericY].demand); sSupply.push(window.savedProjectedData[numericY].supply); sTotalSupply.push(window.savedProjectedData[numericY].totalSupply); } 
                else { sDemand.push(null); sSupply.push(null); sTotalSupply.push(null); }
            }
        });
        
        const hasProg = pDemand.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        
        if (!isComparing) {
            datasets = [
                { label: 'Efterfrågan (Dagbefolkning)', data: hDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect', spanGaps: true },
                { label: 'Lokalt Utbud (Nattbefolkning)', data: hSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
            ];
            if (showCommuting) datasets.push({ label: 'Totalt Utbud (Inkl. Pendling)', data: hTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [2, 2], pointStyle: 'triangle', spanGaps: true });
            
            if (hasProg) {
                datasets.push({ label: 'Efterfrågan (Scenario)', data: pDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect' });
                datasets.push({ label: 'Lokalt Utbud (Scenario)', data: pSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'circle' });
                if (showCommuting) datasets.push({ label: 'Totalt Utbud (Scenario)', data: pTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'triangle' });
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
        datasets.forEach(ds => { if (defaultHiddenLabels.includes(ds.label)) ds.hidden = true; });

    } else if (chartType.includes('arbetsloshet') || chartType.includes('langtidsarb')) {
        isMultiLine = true;
        startYearSelect.style.display = 'inline-block';
        let isLangtid = chartType.includes('langtidsarb');
        let groupStr = chartType.includes('_utrikes') ? 'utrikes' : (chartType.includes('_kon') ? 'kon' : 'totalt');
        let typeVal = subGroupSelect ? subGroupSelect.value : 'pct'; 
        
        if (title) {
            let baseT = isLangtid ? "Långtidsarbetslöshet" : "Arbetslöshet";
            if (groupStr === 'totalt') title.innerText = baseT + (isLangtid ? " (Kärnan)" : " & Arbetskraftsreserv");
            else if (groupStr === 'utrikes') title.innerText = baseT + ": Inrikes och Utrikes födda";
            else title.innerText = baseT + ": Män och Kvinnor";
        }

        if (desc) {
            // Sätt en kort rubriktext för vyn samt info om november månad
            let infoText = isLangtid 
                ? "Visar historisk utveckling av långtidsarbetslösheten i kommunen. Uppgifterna avser november månad." 
                : "Visar historisk utveckling av den registrerade arbetslösheten. Uppgifterna avser november månad.";

            // Bygg ihop innehållet i i-knappen dynamiskt beroende på vilket diagram som visas
            let tooltipHTML = `<p class="mb-2 text-amber-300 font-medium">Observera: Denna vy redovisar enbart historisk data och påverkas inte av de framtidsscenarier du simulerar.</p>`;

            if (isLangtid) {
                tooltipHTML += `<p class="mb-2"><strong>Långtidsarbetslös:</strong> Definieras som en person som varit inskriven som arbetslös i minst 12 månader i sträck.</p>`;
                tooltipHTML += `<p class="mb-2"><strong>Byt mått (rullistan):</strong> Du kan växla mellan <em>Antal personer</em>, <em>Andel av arbetskraften (%)</em> eller <em>Andel av inskrivna arbetslösa (%)</em> för att se hur stor del av arbetslösheten som riskerar att bita sig fast.</p>`;
            } else {
                tooltipHTML += `<p class="mb-2"><strong>Byt mått (rullistan):</strong> Använd rullistan bredvid för att växla mellan <em>Andel av arbetskraften (%)</em> och <em>Antal personer</em>.</p>`;
            }

            // NYTT: Notis om delade axlar för inrikes/utrikes födda
            if (groupStr === 'utrikes') {
                tooltipHTML += `<p class="mb-2"><strong>Delade axlar:</strong> Eftersom grupperna kan skilja sig stort i storlek (volym) visas grafen som standard med delade Y-axlar (vänster/höger) för att göra det enklare att jämföra utvecklingstrenderna.</p>`;
            }

            if (groupStr === 'kon') {
                tooltipHTML += `<p><strong>Tips!</strong> Det finns möjlighet att aktivera kurvan för "Totalt" i diagrammet för att enkelt kunna jämföra könen mot det gemensamma snittet.</p>`;
            }

            // Baka in allt med magnet-effekten
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            ${tooltipHTML}
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}</span>
                </div>
            `;
        }
        
        let h_1=[], h_2=[], h_tot=[];
        
        // Filtrera axeln så att den slutar strikt vid basåret. Inga prognosår ritas ut för arbetslöshet.
        labels = activeYears.filter(y => y <= window.baseYear);
        
        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985 && window.histDataStore && window.histDataStore[numericY]) {
                let d = window.histDataStore[numericY];
                let obj = isLangtid ? d.larb : d.arb;
                
                if (obj) {
                    if (groupStr === 'totalt') {
                        let val = typeVal === 'num' ? obj.tot_num : (typeVal === 'insk' ? obj.tot_insk : obj.tot_pct);
                        h_1.push(val);
                    } else {
                        let v1 = null, v2 = null, vTot = null;
                        if (groupStr === 'utrikes') {
                            if (typeVal === 'num') { v1 = obj.in_num; v2 = obj.ut_num; }
                            else if (typeVal === 'insk') { v1 = obj.in_insk; v2 = obj.ut_insk; }
                            else { v1 = obj.in_pct; v2 = obj.ut_pct; }
                        } else {
                            if (typeVal === 'num') { v1 = obj.m_num; v2 = obj.k_num; vTot = obj.tot_num; }
                            else if (typeVal === 'insk') { v1 = obj.m_insk; v2 = obj.k_insk; vTot = obj.tot_insk; }
                            else { v1 = obj.m_pct; v2 = obj.k_pct; vTot = obj.tot_pct; }
                        }
                        h_1.push(v1); h_2.push(v2); h_tot.push(vTot);
                    }
                } else {
                    h_1.push(null); h_2.push(null); h_tot.push(null);
                }
            } else {
                h_1.push(null); h_2.push(null); h_tot.push(null);
            }
        });

        let lblSuffix = typeVal === 'num' ? ' (Antal)' : ' %';

        if (groupStr === 'totalt') {
            let lbl = isLangtid ? 'Långtidsarbetslösa' : 'Arbetslösa';
            datasets = [
                { label: lbl + lblSuffix, data: h_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: isLangtid ? 'rgba(249, 115, 22, 0.2)' : 'rgba(239, 68, 68, 0.2)', borderWidth: 3, pointStyle: 'circle', fill: true, spanGaps: true }
            ];
        } else {
            let lbl1 = groupStr === 'utrikes' ? 'Inrikes' : 'Män';
            let lbl2 = groupStr === 'utrikes' ? 'Utrikes' : 'Kvinnor';
            let col1 = '#0ea5e9';
            let col2 = groupStr === 'utrikes' ? '#f97316' : '#ec4899';
            let baseL = isLangtid ? 'Långtidsarb.' : 'Arbetslöshet';
            
            datasets = [
                { label: `${baseL} ${lbl1}${lblSuffix}`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                { label: `${baseL} ${lbl2}${lblSuffix}`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
            ];
            if (groupStr === 'kon') datasets.push({ label: 'Totalt' + lblSuffix, data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });
        }

        if (useDualAxes && (groupStr === 'utrikes' || groupStr === 'kon') && typeVal !== 'num') {
            let lbl1 = groupStr === 'utrikes' ? 'Inrikes' : 'Män';
            let lbl2 = groupStr === 'utrikes' ? 'Utrikes' : 'Kvinnor';
            let col1 = '#0ea5e9';
            let col2 = groupStr === 'utrikes' ? '#f97316' : '#ec4899';
            
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: lbl1 + ' %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: lbl2 + ' %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(lbl2) ? 'y1' : 'y'; });
        } else {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, typeVal === 'num' ? 0 : 1) + (typeVal === 'num' ? '' : '%') } } };
        }

    } else if (chartType === 'brp_totalt') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : " (Historik)");
        if (title) title.innerText = "Ekonomisk Tillväxt" + suffix;
        
        if (desc) {
            // Baka in texten och i-knappen med magnet-effekten!
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            <p class="mb-2"><strong>Bruttoregionprodukt (BRP):</strong> BRP är den regionala motsvarigheten till BNP och mäter det samlade värdet av allt som produceras i kommunen.</p>
                            <p class="mb-2"><strong>Hur beräknas framtiden?</strong> Kalkylatorn uppskattar den framtida tillväxten genom att kombinera det simulerade antalet arbetande personer (jobb) med en årlig produktivitetsökning. Vilken procentsats som används för produktiviteten (t.ex. 1,5%) styrs av det scenario (ex. <em>Bas</em>, <em>Hög</em> eller <em>Låg</em>) som har aktiverats i styrfilen.</p>
                            <p><strong>BRP i Nyckeltalsrutan:</strong> Observera att KPI-rutan högst upp på sidan visar BRP <em>per sysselsatt</em> (ett mått på hur produktiv varje medarbetare är), medan detta diagram visar den <em>totala</em> ekonomiska volymen för hela kommunen (Mkr).</p>
                            
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">Visar kommunens uppskattade Bruttoregionprodukt (BRP) i Miljoner kronor (Mkr) över tid.</span>
                </div>
            `;
        }

        let hBRP = [], pBRP = [], sBRP = [];
        labels = activeYears;
        labels.forEach(y => {
            let numericY = Number(y);
            if (y <= window.baseYear && window.histDataStore[numericY]) {
                let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                hBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
            } else { hBRP.push(null); }
            
            if (y === window.baseYear && window.histDataStore[numericY]) {
                let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                pBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
            } else if (y > window.baseYear && window.progDataStore[numericY]) {
                pBRP.push(window.progDataStore[numericY].totalBrpMkr);
            } else { pBRP.push(null); }
            
            if (isComparing) {
                if (y <= window.baseYear && window.histDataStore[numericY]) {
                    let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                    sBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
                } else if (y > window.baseYear && window.savedProjectedData && window.savedProjectedData[numericY]) {
                    sBRP.push(window.savedProjectedData[numericY].totalBrpMkr);
                } else { sBRP.push(null); }
            }
        });

        if (!isComparing) {
            datasets = [
                { label: 'Total BRP (Mkr) - Historik', data: hBRP, borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.2)', borderWidth: 3, pointStyle: 'rect', fill: true, spanGaps: true },
                { label: 'Total BRP (Mkr) - Scenario', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect', fill: false }
            ];
        } else {
             datasets = [
                { label: 'Total BRP (Mkr) - Aktuell', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect' },
                { label: 'Total BRP (Mkr) - Sparad', data: sBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], opacity: 0.6, pointStyle: 'rectRot' }
            ];
        }
        customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0) } } };

    } else if (chartType === 'utbud_efterfragan_delta') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "Årlig förändring (Nytt utbud/Efterfrågan)";
        
        if (desc) {
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            <p class="mb-2"><strong>Årlig nettoförändring:</strong> Visar förändringen från ett år till nästa. Hur många <em>nya</em> jobb skapas jämfört med hur mycket arbetskraften växer?</p>
                            <p><strong>Tolkning:</strong> Staplar under nollstrecket innebär en minskning. Simulerade jobbsatsningar i kalkylatorn syns ofta som skarpa uppåtgående toppar i den gröna stapeln.</p>
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">Visar den årliga nettoförändringen av antalet jobb och den lokala arbetskraften. Klicka på "Förändring Nettopendling" i teckenförklaringen för att lägga till detta flöde i staplarna.</span>
                </div>
            `;
        }

        isBarChart = true;

        let dDemand = [], dSupply = [], dPend = [];
        labels = activeYears;
        
        const simModeEl = document.getElementById('simMode');
        const showCommuting = simModeEl ? (simModeEl.value === 'full') : true;

        const getCalculatedValues = (year) => {
            let d = year <= window.baseYear ? window.histDataStore[year] : (window.progDataStore[year] || window.histDataStore[year]);
            if (!d) return { dem: null, sup: null, pend: null };
            
            let dem = d.demand != null ? Number(d.demand) : 0;
            let sup = d.supply != null ? Number(d.supply) : 0;
            
            let explicitNet = d.explicitNetCommuting != null ? Number(d.explicitNetCommuting) : 0;
            let netP = d.netCommuting != null ? Number(d.netCommuting) : explicitNet;
            let vSup = d.virtualSupply != null ? Number(d.virtualSupply) : 0;
            
            let totPend = showCommuting ? (netP + vSup) : 0;
            
            return { dem: dem, sup: sup, pend: totPend };
        };

        labels.forEach(y => {
            let numY = Number(y);
            
            let current = getCalculatedValues(numY);
            let previous = getCalculatedValues(numY - 1);

            if (current.dem != null && previous.dem != null) dDemand.push(current.dem - previous.dem); else dDemand.push(null);
            if (current.sup != null && previous.sup != null) dSupply.push(current.sup - previous.sup); else dSupply.push(null);
            if (current.pend != null && previous.pend != null) dPend.push(current.pend - previous.pend); else dPend.push(null);
        });

        datasets = [
            { type: 'bar', label: 'Förändring Efterfrågan', data: dDemand, backgroundColor: '#10b981', stack: 'Stack 1' },
            { type: 'bar', label: 'Förändring Lokalt Utbud', data: dSupply, backgroundColor: '#0ea5e9', stack: 'Stack 2' },
            { type: 'bar', label: 'Förändring Nettopendling', data: dPend, backgroundColor: '#f59e0b', stack: 'Stack 2', hidden: true }
        ];

    } else if (chartType === 'pendling_detalj') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "In- och utpendling (Kommungräns)";
        isBarChart = true;

        const mode = subGroupSelect ? subGroupSelect.value : 'neg';

        if (desc) {
            let modeSuffix = causalityMode === 'dynamic' ? " <strong>(Dynamisk jämvikt)</strong>" : " <strong>(Analytiskt läge)</strong>";
            let infoText = "Visar in- och utpendling över kommungränsen, samt pendlingsnetto över tid." + modeSuffix;
            
            let tooltipHTML = `
                <p class="mb-2"><strong>Rullistan:</strong> Välj om utpendling ska visas som positiva eller negativa staplar för att lättare jämföra volymer eller visuellt se nettot.</p>
                <p class="mb-2"><strong>Förväntad utveckling (Bas):</strong> Kalkylatorn beräknar en strukturell grundpendling baserad på jobbtillväxt, demografi och grannkommunernas arbetskraftsreserv.</p>
                <p class="mb-2"><strong>Analytiskt läge:</strong> Visar den strukturella pendlingen. Om denna inte räcker för att fylla kommunens jobb, varnar Nyckeltalet (KPI) högst upp med en orange parentes som visar hur extremt pendlingen skulle behöva öka för att lösa krisen.</p>
                <p><strong>Dynamiskt läge:</strong> Modellen löser rekryteringsgapet genom ökad inflyttning. Eftersom de nya invånarna bor lokalt och tar jobben, slipper pendlingen öka drastiskt och stannar därmed på sin naturliga, balanserade grundnivå i diagrammet.</p>
            `;

            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            ${tooltipHTML}
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}</span>
                </div>
            `;
        }

        let hIn = [], hUt = [], hNet = [], pIn = [], pUt = [], pNet = [];
        labels = activeYears;
        
        labels.forEach(y => {
            let numY = Number(y);
            
            // 1. Historiken (alltid oförändrad)
            if (numY <= window.baseYear && window.histDataStore[numY]) {
                hIn.push(window.histDataStore[numY].inpendling);
                let utVal = window.histDataStore[numY].utpendling;
                hUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null); 
                hNet.push(window.histDataStore[numY].netCommuting);
            } else { 
                hIn.push(null); hUt.push(null); hNet.push(null); 
            }
            
            // 2. Framtiden (Scenariot)
            if (numY === window.baseYear && window.histDataStore[numY]) {
                pIn.push(null); pUt.push(null);
                pNet.push(window.histDataStore[numY].netCommuting);
            } else if (numY > window.baseYear && window.progDataStore[numY]) {
                
                let d = window.progDataStore[numY];
                let currentIn = d.inpendling || 0;
                let currentUt = d.utpendling || 0;
                
                // EXAKT samma logik som i updateKPIs
                let explNetto = d.netCommuting !== undefined ? d.netCommuting : (d.explicitNetCommuting || 0);
                let virtualExt = d.virtualSupply || 0;
                let totalPendling = showCommuting ? (explNetto + virtualExt) : 0;
                
                let currentNet = totalPendling;

                // För att staplarna (In minus Ut) ska gå jämnt ut med det nya nettot, 
                // adderar vi det virtuella pendlingsutbudet på inpendlingen.
                currentIn += virtualExt;

                // --- DYNAMISK LOGIK (MATCHAR DYNAMISKT GAP I KPI-KORTET) ---
                if (causalityMode === 'dynamic' && showCommuting) {
                    let omatchatGap = (d.demand || 0) - ((d.supply || 0) + totalPendling);
                    
                    if (Math.abs(omatchatGap) > 5) {
                        currentNet = totalPendling + omatchatGap; // Nettot blir det som krävs för balans
                        
                        if (omatchatGap > 0) {
                            currentIn += omatchatGap; // Fler pendlar in för att ta jobben
                        } else {
                            currentUt += Math.abs(omatchatGap); // Överskott av lokal arbetskraft pendlar ut
                        }
                    }
                }
                
                pIn.push(currentIn);
                pUt.push(currentUt ? (mode === 'neg' ? -currentUt : currentUt) : null);
                pNet.push(currentNet);

            } else { 
                pIn.push(null); pUt.push(null); pNet.push(null); 
            }
        });

        datasets = [
            { type: 'bar', label: 'Inpendling', data: hIn, backgroundColor: '#0ea5e9', order: 2 },
            { type: 'bar', label: 'Utpendling', data: hUt, backgroundColor: '#ef4444', order: 3 },
            { type: 'line', label: 'Pendlingsnetto', data: hNet, borderColor: '#334155', borderWidth: 3, fill: false, pointStyle: 'rect', order: 1 }
        ];
        
        const hasProg = pIn.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if (hasProg && !isComparing) {
            datasets.push({ type: 'bar', label: 'Inpendling (Scenario)', data: pIn, backgroundColor: 'rgba(14, 165, 233, 0.4)', order: 2 });
            datasets.push({ type: 'bar', label: 'Utpendling (Scenario)', data: pUt, backgroundColor: 'rgba(239, 68, 68, 0.4)', order: 3 });
            datasets.push({ type: 'line', label: 'Pendlingsnetto (Scenario)', data: pNet, borderColor: '#94a3b8', borderWidth: 3, borderDash: [5,5], fill: false, pointStyle: 'rect', order: 1 });
        }

    } else if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
        startYearSelect.style.display = 'none'; 
        isBarChart = true;
        let dagData = {}, nattData = {};
        let isGenderSplit = false;
        
        const getDataset = (partialName) => {
            const key = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes(partialName.toLowerCase()));
            return key ? window.syssBasdata[key] : [];
        };

        const refYear = isProgYear ? window.baseYear : selYearInt;
        let suffix = isProgYear ? " (Scenario)" : "";
        
        let infoText = "";
        let chartSpecificTooltip = "";

        if (chartType === 'utb_match') {
            if (title) title.innerText = `Utbildningsmatchning (År ${selYearInt})${suffix}`;
            labels = ['Förgymnasial', 'Gymnasial', 'Kort eftergymnasial', 'Lång eftergymnasial'];
            const mapLevel = (l) => {
                let t = String(l).toLowerCase();
                if (t.includes('förgymnasial')) return 'Förgymnasial';
                if (t.includes('kort eftergymnasial') || (t.includes('eftergymnasial') && t.includes('kort'))) return 'Kort eftergymnasial';
                if (t.includes('lång eftergymnasial') || (t.includes('eftergymnasial') && t.includes('lång')) || t.includes('forskar')) return 'Lång eftergymnasial';
                if (t.includes('eftergymnasial')) return 'Lång eftergymnasial'; 
                if (t.includes('gymnasial')) return 'Gymnasial';
                return 'Okänd';
            };
            dagData = window.aggregateMatchData(getDataset('Syss_utb'), refYear, labels, 'Utbildningsnivå', mapLevel);
            nattData = window.aggregateMatchData(getDataset('Natt_utb'), refYear, labels, 'Utbildningsnivå', mapLevel);
            
            infoText = "Visar matchningen mellan lokalt utbud och företagens efterfrågan utifrån utbildningsnivå.";
            chartSpecificTooltip = `<p class="mb-2"><strong>Utbildning:</strong> Jämför den utbildningsnivå som företagen kräver med den utbildningsnivå som den bosatta arbetskraften har.</p>`;
        
        } else if (chartType === 'sektor_match' || chartType === 'sektor_match_kon') {
            if (chartType === 'sektor_match_kon') {
                if (title) title.innerText = `Sektormatchning: Män och Kvinnor (År ${selYearInt})${suffix}`;
                isGenderSplit = true;
            } else {
                if (title) title.innerText = `Sektormatchning (År ${selYearInt})${suffix}`;
            }
            labels = ['Privat sektor', 'Offentlig sektor'];
            
            if (chartType === 'sektor_match_kon') {
                let d_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 }, d_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
                let n_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 }, n_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };

                getDataset('Syss_sektor').filter(r => window.extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) { d_m[sec] += parseFloat(r['Män'] || r['män'] || 0); d_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
                });
                getDataset('Natt_sektor').filter(r => window.extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) { n_m[sec] += parseFloat(r['Män'] || r['män'] || 0); n_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
                });
                dagData = {'män': d_m, 'kvinnor': d_k};
                nattData = {'män': n_m, 'kvinnor': n_k};
            } else {
                dagData = window.aggregateMatchData(getDataset('Syss_sektor'), refYear, labels, 'Sektor');
                nattData = window.aggregateMatchData(getDataset('Natt_sektor'), refYear, labels, 'Sektor');
            }
            
            infoText = "Visar matchningen mellan lokalt utbud och efterfrågan inom privat respektive offentlig sektor.";
            chartSpecificTooltip = `<p class="mb-2"><strong>Sektor:</strong> Visar fördelningen av jobb och lokal arbetskraft mellan privat näringsliv och offentlig verksamhet.</p>`;
        
        } else if (chartType === 'bransch_match') {
            if (title) title.innerText = `Branschmatchning (År ${selYearInt})${suffix}`;
            isHorizontal = true;
            const dfDag = getDataset('Syss_bransch');
            const dfNatt = getDataset('Natt_bransch');
            
            let rawLabels = [];
            if (dfDag.length > 0) {
                // NY LOGIK: Vi plockar INTE bort 'Okänd bransch' här. Den måste finnas kvar ifall vi vill gruppera den!
                const excludeCols = ['År', 'år', 'Samtliga', 'Totalt', 'Kön', 'kön'];
                rawLabels = Object.keys(dfDag[0]).filter(k => !excludeCols.includes(k));
            }
            
            let dagDataRaw = window.aggregateMatchData(dfDag, refYear, rawLabels, 'Cols');
            let nattDataRaw = window.aggregateMatchData(dfNatt, refYear, rawLabels, 'Cols');
            
            const subGroupVal = subGroupSelect ? subGroupSelect.value : 'all';
            
            if (subGroupVal && subGroupVal !== 'all' && window.syssConfig['SNIgrupper']) {
                // ANVÄNDAREN HAR VALT EN GRUPPERING
                let groupedDag = { 'totalt': {} }, groupedNatt = { 'totalt': {} };
                const sniGrupper = window.syssConfig['SNIgrupper'];
                const firstKey = Object.keys(sniGrupper[0])[0]; 

                rawLabels.forEach(l => {
                    let mappingRow = sniGrupper.find(r => String(r[firstKey]).trim() === String(l).trim());
                    let targetGroup = mappingRow ? mappingRow[subGroupVal] : null;

                    if (targetGroup && String(targetGroup).trim() !== '') {
                        let groupName = String(targetGroup).trim();
                        if (!groupedDag['totalt'][groupName]) { groupedDag['totalt'][groupName] = 0; groupedNatt['totalt'][groupName] = 0; }
                        groupedDag['totalt'][groupName] += dagDataRaw['totalt'][l] || 0;
                        groupedNatt['totalt'][groupName] += nattDataRaw['totalt'][l] || 0;
                    }
                });
                labels = Object.keys(groupedDag['totalt']);
                dagData = groupedDag; nattData = groupedNatt;
            } else {
                // STANDARDLÄGE (Ingen gruppering)
                // NY LOGIK: Nu filtrerar vi bort 'Okänd bransch' så den inte stör standardvyn
                labels = rawLabels.filter(l => l !== 'Okänd bransch');
                dagData = dagDataRaw; 
                nattData = nattDataRaw;
            }

            if (labels.length > 15 && (!subGroupVal || subGroupVal === 'all')) {
                wrapper.style.minHeight = (labels.length * 20) + 'px';
            }
            
            infoText = "Visar matchningen mellan lokalt utbud och efterfrågan uppdelat på olika branscher.";
            chartSpecificTooltip = `
                <p class="mb-2"><strong>Bransch (SNI):</strong> Utgångspunkten för branschindelningen är SCB:s standard via så kallad "SNI-bokstav".</p>
                <p class="mb-2"><strong>Gruppera branscher:</strong> Använd rullistan bredvid för att slå ihop branscherna till större, anpassade grupper. <em>Här inkluderas även okända branscher om de är definierade i din styrfil.</em></p>
            `;
        }
        
        if (desc) {
            let commonTooltipHTML = "";
            
            if (chartType !== 'sektor_match_kon') {
                commonTooltipHTML += `
                    <p class="mb-2"><strong>Rekryteringsgap:</strong> Visar skillnaden mellan antalet jobb (Efterfrågan/Dagbefolkning) och bosatt arbetskraft (Utbud/Nattbefolkning). Om stapeln för jobb är högre uppstår ett gap. Gapet kan fyllas genom ökad inpendling eller ökad inflyttning.</p>
                    <p class="mb-2"><strong>Analytiskt vs Dynamiskt:</strong> I <em>Analytiskt</em> läge ser du det teoretiska gapet utifrån basprognosen. I <em>Dynamiskt</em> läge visas den nya jämvikten <em>efter</em> att de simulerade inflyttarna har tillsatt jobben.</p>
                `;
            } else {
                commonTooltipHTML += `
                    <p class="mb-2"><strong>Analytiskt vs Dynamiskt:</strong> I <em>Analytiskt</em> läge visas utbud och efterfrågan utifrån basprognosen. I <em>Dynamiskt</em> läge visas den nya jämvikten <em>efter</em> att den simulerade arbetskraftsinflyttningen skett.</p>
                `;
            }

            commonTooltipHTML += `
                <p><strong>Tips för framtiden!</strong> För scenarier framåt i tiden: Använd årtals-rullistan ovanför diagrammet för att titta på balansen under enskilda år.</p>
            `;

            let modeSuffix = causalityMode === 'dynamic' ? " <strong>(Dynamisk jämvikt)</strong>" : "";

            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            ${chartSpecificTooltip}
                            ${commonTooltipHTML}
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}${modeSuffix}</span>
                </div>
            `;
            // NYTT: Tvinga KPI:erna att uppdateras efter att diagrammet (och simuleringen) är helt klar
            if (typeof window.updateKPIs === 'function') {
            setTimeout(() => {
                window.updateKPIs();
            }, 50); // 50 millisekunders fördröjning räcker för att koden ska hinna andas
            }
        } // <-- Här slutar blocket för bransch_match
        
        window.drawMatchChart(selYearInt, labels, dagData, nattData, isGenderSplit, useZeroAxis, isHorizontal);
        return; 
    } else if (chartType === 'trend_utrikes' || chartType === 'trend_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : " (Historik)");
        
        let key1_n, key2_n, key1_d, key2_d, lbl1_n, lbl2_n, lbl1_d, lbl2_d, col1, col2;
        let infoText = "";
        let tooltipHTML = "";

        if (chartType === 'trend_utrikes') {
            if (title) title.innerText = "Integration: Arbetsmarknad efter ursprung" + suffix;
            key1_n = 'n_inrikes'; key2_n = 'n_utrikes'; key1_d = 'd_inrikes'; key2_d = 'd_utrikes';
            lbl1_n = 'Lokalt Utbud (Inrikes)'; lbl2_n = 'Lokalt Utbud (Utrikes)'; lbl1_d = 'Efterfrågan (Inrikes)'; lbl2_d = 'Efterfrågan (Utrikes)';
            col1 = '#0ea5e9'; col2 = '#f97316';
            
            // Text och i-knapp specifikt för Integration/Ursprung (Utan "endast historik"-varningen)
            infoText = "Visar arbetsmarknadens balans uppdelat på inrikes och utrikes födda.";
            tooltipHTML = `
                <p class="mb-2"><strong>Integration:</strong> Jämför hur utbudet (bosatta) och efterfrågan (jobb) utvecklas för inrikes respektive utrikes födda.</p>
                <p><strong>Delade axlar:</strong> Eftersom grupperna är olika stora visas grafen som standard med delade Y-axlar (vänster/höger). Detta gör det möjligt att jämföra <em>trenderna</em> oberoende av volym.</p>
            `;
            
        } else {
            if (title) title.innerText = "Jämställdhet: Arbetsmarknad efter kön" + suffix;
            key1_n = 'n_man'; key2_n = 'n_kvinna'; key1_d = 'd_man'; key2_d = 'd_kvinna';
            lbl1_n = 'Lokalt Utbud (Män)'; lbl2_n = 'Lokalt Utbud (Kvinnor)'; lbl1_d = 'Efterfrågan (Män)'; lbl2_d = 'Efterfrågan (Kvinnor)';
            col1 = '#0ea5e9'; col2 = '#ec4899';
            
            // Text och i-knapp specifikt för Jämställdhet/Kön
            infoText = "Visar arbetsmarknadens utveckling och balans uppdelat på män och kvinnor.";
            tooltipHTML = `
                <p class="mb-2"><strong>Jämställdhet:</strong> Visar gapet mellan det lokala utbudet (arbetskraft) och företagens efterfrågan (jobb) för kvinnor respektive män.</p>
                <p><strong>Tips om Delade axlar:</strong> Om du aktiverar "Delade axlar" ovanför diagrammet får män och kvinnor varsin Y-axel (vänster/höger). Detta gör det mycket lättare att jämföra formen på kurvorna om antalet skiljer sig stort.</p>
            `;
        }

        // Baka in texten och i-knappen med den smidiga magnet-effekten
        if (desc) {
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            ${tooltipHTML}
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}</span>
                </div>
            `;
        }

        labels = activeYears;
        let h_n1=[], h_n2=[], p_n1=[], p_n2=[], h_d1=[], h_d2=[], p_d1=[], p_d2=[];
        const ageGroup = chartType === 'trend_kon' ? subGroupSelect.value : 'totalt';

        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985) {
                if (y <= window.baseYear && window.histDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        h_n1.push(window.histDataStore[numericY][key1_n]); h_n2.push(window.histDataStore[numericY][key2_n]);
                        h_d1.push(window.histDataStore[numericY][key1_d]); h_d2.push(window.histDataStore[numericY][key2_d]);
                    } else {
                        h_n1.push(window.histDataStore[numericY].n_man_age && window.histDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_man_age[ageGroup] : null);
                        h_n2.push(window.histDataStore[numericY].n_kvinna_age && window.histDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        h_d1.push(window.histDataStore[numericY].d_man_age && window.histDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_man_age[ageGroup] : null);
                        h_d2.push(window.histDataStore[numericY].d_kvinna_age && window.histDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else { h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null); }
                
                if (y === window.baseYear && window.histDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        p_n1.push(window.histDataStore[numericY][key1_n]); p_n2.push(window.histDataStore[numericY][key2_n]);
                        p_d1.push(window.histDataStore[numericY][key1_d]); p_d2.push(window.histDataStore[numericY][key2_d]);
                    } else {
                        p_n1.push(window.histDataStore[numericY].n_man_age && window.histDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_man_age[ageGroup] : null);
                        p_n2.push(window.histDataStore[numericY].n_kvinna_age && window.histDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        p_d1.push(window.histDataStore[numericY].d_man_age && window.histDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_man_age[ageGroup] : null);
                        p_d2.push(window.histDataStore[numericY].d_kvinna_age && window.histDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else if (y > window.baseYear && window.progDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        p_n1.push(window.progDataStore[numericY][key1_n]); p_n2.push(window.progDataStore[numericY][key2_n]);
                        p_d1.push(window.progDataStore[numericY][key1_d]); p_d2.push(window.progDataStore[numericY][key2_d]);
                    } else {
                        p_n1.push(window.progDataStore[numericY].n_man_age && window.progDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.progDataStore[numericY].n_man_age[ageGroup] : null);
                        p_n2.push(window.progDataStore[numericY].n_kvinna_age && window.progDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.progDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        p_d1.push(window.progDataStore[numericY].d_man_age && window.progDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.progDataStore[numericY].d_man_age[ageGroup] : null);
                        p_d2.push(window.progDataStore[numericY].d_kvinna_age && window.progDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.progDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else { p_n1.push(null); p_n2.push(null); p_d1.push(null); p_d2.push(null); }
            } else {
                h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null);
                p_n1.push(null); p_n2.push(null); p_d1.push(null); p_d2.push(null);
            }
        });

        datasets = [
            { label: lbl1_n, data: h_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: lbl2_n, data: h_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: lbl1_d, data: h_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true },
            { label: lbl2_d, data: h_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true }
        ];
        
        const hasProg = p_n1.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if(hasProg && !isComparing) {
            datasets.push({ label: lbl1_n.replace('Lokalt ', '') + ' (Scen)', data: p_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            datasets.push({ label: lbl2_n.replace('Lokalt ', '') + ' (Scen)', data: p_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            datasets.push({ label: lbl1_d + ' (Scen)', data: p_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
            datasets.push({ label: lbl2_d + ' (Scen)', data: p_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
        }

        if (useDualAxes && (chartType === 'trend_utrikes' || chartType === 'trend_kon')) {
            let isUtr = chartType === 'trend_utrikes';
            let title1 = isUtr ? 'Inrikes' : 'Män';
            let title2 = isUtr ? 'Utrikes' : 'Kvinnor';
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: title1, color: col1 }, ticks: { callback: val => window.formatNumber(val) } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: title2, color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val) } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(title2) ? 'y1' : 'y'; });
        }

    } else if (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Scenario)" : " (Historik)");
        
        let key1, key2, lbl1, lbl2, col1, col2;
        let infoText = "";
        let tooltipHTML = "";

        if (chartType === 'syssgrad_utrikes') {
            if (title) title.innerText = "Sysselsättningsgrad: Inrikes och Utrikes födda" + suffix;
            key1 = 'syss_in_tot'; key2 = 'syss_ut_tot'; lbl1 = 'Inrikes'; lbl2 = 'Utrikes'; col1 = '#0ea5e9'; col2 = '#f97316';
            
            infoText = "Visar sysselsättningsgraden i procent, uppdelat på inrikes och utrikes födda.";
            tooltipHTML = `
                <p class="mb-2"><strong>Sysselsättningsgrad:</strong> Visar hur stor andel (%) av de bosatta i åldern 20-64 år som är sysselsatta (förvärvsarbetande).</p>
                <p class="mb-2"><strong>Delade axlar:</strong> Diagrammet visas som standard med delade Y-axlar (vänster/höger) för att göra det lättare att jämföra utvecklingstrender mellan grupperna.</p>
                <p><strong>Catch-up-effekt:</strong> I framtidsscenarier syns ofta en så kallad "catch-up-effekt", där sysselsättningsgraden för utrikes födda antas öka i en snabbare takt för att över tid närma sig den för inrikes födda.</p>
            `;
        } else {
            if (title) title.innerText = "Sysselsättningsgrad: Män och Kvinnor" + suffix;
            key1 = 'syssGradM'; key2 = 'syssGradK'; lbl1 = 'Män'; lbl2 = 'Kvinnor'; col1 = '#0ea5e9'; col2 = '#ec4899';
            
            infoText = "Visar sysselsättningsgraden i procent, uppdelat på män och kvinnor.";
            tooltipHTML = `
                <p class="mb-2"><strong>Sysselsättningsgrad:</strong> Visar hur stor andel (%) av de bosatta i vald åldersgrupp som är sysselsatta (förvärvsarbetande).</p>
                <p class="mb-2"><strong>Tips om Totalt & Ålder:</strong> Du kan aktivera kurvan för "Totalt" i teckenförklaringen för att se kommunens genomsnitt. Använd rullistan bredvid diagrammet för att ändra vilken åldersgrupp som visas.</p>
                <p><strong>Scenario-effekt:</strong> När du ändrar reglagen för sysselsättningsgrad i panelen och kör en simulering ser du direkt hur dessa kurvor höjs i framtiden.</p>
            `;
        }

        // Baka in texten och i-knappen med magnet-effekten
        if (desc) {
            desc.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="relative group cursor-help text-blue-500 hover:text-blue-700 mt-0.5 before:absolute before:-inset-3 before:content-['']">
                        <i class="fa-solid fa-circle-info text-base relative z-10"></i>
                        <div class="absolute z-[100] hidden group-hover:block w-80 p-3 mt-2 text-xs text-white font-normal normal-case bg-gray-800 rounded shadow-xl -left-2 top-full text-left pointer-events-none">
                            ${tooltipHTML}
                            <div class="absolute w-3 h-3 bg-gray-800 rotate-45 -top-1 left-2.5"></div>
                        </div>
                    </span>
                    <span class="text-sm">${infoText}</span>
                </div>
            `;
        }

        const ageGroup = subGroupSelect ? subGroupSelect.value : '20-64';
        let h_1 = [], h_2 = [], h_tot = [], p_1 = [], p_2 = [], p_tot = [];
        labels = activeYears;
        
        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985) {
                let v1 = null, v2 = null;
                if (window.histDataStore[numericY]) {
                    if (chartType === 'syssgrad_utrikes') {
                        v1 = window.histDataStore[numericY][key1] != null ? parseFloat(window.histDataStore[numericY][key1]) : null;
                        v2 = window.histDataStore[numericY][key2] != null ? parseFloat(window.histDataStore[numericY][key2]) : null;
                    } else {
                        v1 = window.histDataStore[numericY][key1] && window.histDataStore[numericY][key1][ageGroup] != null ? parseFloat(window.histDataStore[numericY][key1][ageGroup]) : null;
                        v2 = window.histDataStore[numericY][key2] && window.histDataStore[numericY][key2][ageGroup] != null ? parseFloat(window.histDataStore[numericY][key2][ageGroup]) : null;
                    }
                }

                // NY LOGIK FÖR HISTORIK: Räkna ut snittet av v1 och v2 om båda finns, annars använd displayRate (som fallback för utrikes)
                let totHistVal = null;
                if (chartType === 'syssgrad_kon' && v1 !== null && v2 !== null) {
                    totHistVal = (v1 + v2) / 2;
                } else {
                    totHistVal = window.histDataStore[numericY] ? window.histDataStore[numericY].displayRate : null;
                }

                if (y <= window.baseYear) { 
                    h_1.push(v1); h_2.push(v2); h_tot.push(totHistVal); 
                } else { 
                    h_1.push(null); h_2.push(null); h_tot.push(null); 
                }
                
                // NY LOGIK FÖR PROGNOS: Samma sak, hämta rätt värden och räkna ut snittet
                if (y === window.baseYear) { 
                    p_1.push(v1); p_2.push(v2); p_tot.push(totHistVal); 
                } 
                else if (y > window.baseYear && window.progDataStore[numericY]) {
                    let pv1 = null, pv2 = null, pvTot = null;
                    
                    if (chartType === 'syssgrad_utrikes') {
                        pv1 = window.progDataStore[numericY][key1] != null ? window.progDataStore[numericY][key1] : null;
                        pv2 = window.progDataStore[numericY][key2] != null ? window.progDataStore[numericY][key2] : null;
                        pvTot = window.progDataStore[numericY].displayRate != null ? window.progDataStore[numericY].displayRate : null;
                    } else {
                        pv1 = window.progDataStore[numericY][key1] && window.progDataStore[numericY][key1][ageGroup] != null ? window.progDataStore[numericY][key1][ageGroup] : null;
                        pv2 = window.progDataStore[numericY][key2] && window.progDataStore[numericY][key2][ageGroup] != null ? window.progDataStore[numericY][key2][ageGroup] : null;
                        // Räkna ut snittet för framtiden
                        if (pv1 !== null && pv2 !== null) {
                            pvTot = (pv1 + pv2) / 2;
                        } else {
                            pvTot = window.progDataStore[numericY].displayRate != null ? window.progDataStore[numericY].displayRate : null;
                        }
                    }
                    
                    p_1.push(pv1);
                    p_2.push(pv2);
                    p_tot.push(pvTot);
                } else { 
                    p_1.push(null); p_2.push(null); p_tot.push(null); 
                }
            }
        });

        datasets = [
            { label: `Sysselsättningsgrad ${lbl1} %`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: `Sysselsättningsgrad ${lbl2} %`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
        ];
        if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt %', data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });

        const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if (hasProg) {
            datasets.push({ label: `${lbl1} % (Scenario)`, data: p_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
            datasets.push({ label: `${lbl2} % (Scenario)`, data: p_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
            if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt % (Scenario)', data: p_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect', fill: false, hidden: true });
        }

        if (useDualAxes && (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon')) {
            let isUtr = chartType === 'syssgrad_utrikes';
            let title1 = isUtr ? 'Inrikes' : 'Män';
            let title2 = isUtr ? 'Utrikes' : 'Kvinnor';
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: title1 + ' %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: title2 + ' %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(title2) ? 'y1' : 'y'; });
        }

    }

    if (datasets.length > 0) {
        let maxValidIdx = -1;
        datasets.forEach(ds => {
            ds.data.forEach((val, idx) => {
                if (val !== null && val !== undefined && val !== '') {
                    if (idx > maxValidIdx) maxValidIdx = idx;
                }
            });
        });
        if (maxValidIdx >= 0 && maxValidIdx < labels.length - 1) {
            labels = labels.slice(0, maxValidIdx + 1);
            datasets.forEach(ds => {
                ds.data = ds.data.slice(0, maxValidIdx + 1);
            });
        }
    }

    datasets.forEach(ds => {
        if (window.globalChartVisibility[ds.label] !== undefined) ds.hidden = window.globalChartVisibility[ds.label];
    });

    if (!isBarChart) {
        let isPct = false;
        if (chartType.includes('arbetsloshet') || chartType.includes('syssgrad')) {
            let typeVal = subGroupSelect ? subGroupSelect.value : 'pct';
            isPct = typeVal !== 'num';
        }
        let decimals = isPct ? 1 : 0;
        let suffix_text = isPct ? '%' : (chartType === 'brp_totalt' ? ' Mkr' : '');

        let finalOptions = {
            responsive: true, 
            maintainAspectRatio: false, 
            interaction: { mode: isMultiLine ? 'index' : 'nearest', intersect: false },
            scales: customScale || { y: { stacked: isStacked, beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals) + suffix_text } } },
            plugins: { 
                tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, decimals) + suffix_text } }, 
                legend: { 
                    labels: { boxWidth: 10, font: { size: 11 }, generateLabels: function(chart) { return Chart.defaults.plugins.legend.labels.generateLabels(chart).map(l => { l.color = l.hidden ? '#cbd5e1' : '#334155'; return l; }); } },
                    onClick: function(e, legendItem, legend) {
                        Chart.defaults.plugins.legend.onClick.call(this, e, legendItem, legend);
                        setTimeout(() => {
                            const hideBtn = document.getElementById('hideAllBtn');
                            if (hideBtn && !hideBtn.classList.contains('hidden')) {
                                const anyVis = window.trendChartInstance.data.datasets.some((ds, i) => window.trendChartInstance.isDatasetVisible(i));
                                hideBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
                            }
                        }, 50);
                    }
                } 
            }
        };
        // --- LÄGG TILL DETTA FÖR FAST SKALA ---
            const useFixedScale = document.getElementById('useFixedScale') ? document.getElementById('useFixedScale').checked : false;
            if (useFixedScale && window.savedScaleMax !== null) {
                if (finalOptions.scales.y) {
                    finalOptions.scales.y.min = window.savedScaleMin;
                    finalOptions.scales.y.max = window.savedScaleMax;
                }
                if (finalOptions.scales.y1) {
                    finalOptions.scales.y1.min = window.savedScaleMin;
                    finalOptions.scales.y1.max = window.savedScaleMax;
                }
            }
            // --------------------------------------

        window.trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: labels.map(l => String(l).replace(' (Prognos)', '').replace(' (Scenario)', '')), datasets: datasets },
            options: finalOptions
        });
    } else if (isBarChart && datasets.length > 0) {
        
        let decimals = 0;
        let scaleConfig = isHorizontal ? {
            x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
            y: { ticks: { font: { size: 10 } } }
        } : {
            x: { ticks: { font: { size: 10 } } },
            y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
        };

        if (chartType === 'pendling_detalj') {
            scaleConfig = {
                x: { ticks: { font: { size: 10 } } },
                y: { beginAtZero: true, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } } }
            };
        }
        if (chartType === 'medfoljande_behov') {
            scaleConfig = {
                x: { ticks: { font: { size: 10 } } },
                y: { stacked: true, beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } } }
            };
        }
        // --- LÄGG TILL DETTA FÖR FAST SKALA ---
                const useFixedScaleBar = document.getElementById('useFixedScale') ? document.getElementById('useFixedScale').checked : false;
                if (useFixedScaleBar && window.savedScaleMax !== null) {
                    if (isHorizontal && scaleConfig.x) {
                        scaleConfig.x.min = window.savedScaleMin;
                        scaleConfig.x.max = window.savedScaleMax;
                    } else if (!isHorizontal && scaleConfig.y) {
                        scaleConfig.y.min = window.savedScaleMin;
                        scaleConfig.y.max = window.savedScaleMax;
                    }
                }
                // --------------------------------------

        window.trendChartInstance = new Chart(ctx, {
            type: 'bar',
            data: { labels: labels.map(l => String(l).replace(' (Prognos)', '').replace(' (Scenario)', '')), datasets: datasets },
            options: {
                indexAxis: isHorizontal ? 'y' : 'x', 
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: scaleConfig,
                plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, decimals) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
            }
        });
    }

    if (!calledFromDropdown) {
        if (typeof window.updateKPIs === 'function') window.updateKPIs();
    }
    
    const hideAllBtn = document.getElementById('hideAllBtn');
    if (hideAllBtn) {
        if (datasets.length > 1 && !chartType.includes('match') && chartType !== 'utbud_efterfragan_delta' && chartType !== 'pendling_detalj' && chartType !== 'medfoljande_behov') {
            hideAllBtn.classList.remove('hidden');
            hideAllBtn.classList.add('flex');
            
            const anyVis = datasets.some(ds => ds.hidden !== true);
            hideAllBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
        } else {
            hideAllBtn.classList.add('hidden');
            hideAllBtn.classList.remove('flex');
        }
    }
};

window.toggleAllSeries = function() {
    if(!window.trendChartInstance) return;
    const anyVisible = window.trendChartInstance.data.datasets.some((ds, i) => window.trendChartInstance.isDatasetVisible(i));
    window.trendChartInstance.data.datasets.forEach((ds, i) => {
        const meta = window.trendChartInstance.getDatasetMeta(i);
        meta.hidden = anyVisible;
        window.globalChartVisibility[ds.label] = anyVisible;
    });
    window.trendChartInstance.update();
    const btn = document.getElementById('hideAllBtn');
    if (btn) btn.innerHTML = anyVisible ? '<i class="fa-solid fa-eye mr-1"></i> Visa alla' : '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla';
};