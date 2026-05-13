// ==========================================
// Grafer & UI 2035 - Visuell representation
// ==========================================

// --- INJEKTION AV PENDLINGSDIAGRAMMET ---
function injectPendlingOption() {
    const chartTypeSelect = document.getElementById('chartType');
    if (chartTypeSelect && !chartTypeSelect.querySelector('option[value="pendling_detalj"]')) {
        const optGroup = document.createElement('optgroup');
        optGroup.label = "── Pendling ──";
        optGroup.appendChild(new Option("In- och utpendling (Kommungräns)", "pendling_detalj"));
        
        const matchGroup = Array.from(chartTypeSelect.children).find(el => el.label && el.label.includes('Matchning'));
        if (matchGroup) {
            chartTypeSelect.insertBefore(optGroup, matchGroup);
        } else {
            chartTypeSelect.add(optGroup);
        }
    }
}
// Kör direkt för att garantera att det fastnar i listan
injectPendlingOption();
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectPendlingOption);
}
setTimeout(injectPendlingOption, 500);


// --- HJÄLPFUNKTIONER OCH INFO-MODALER ---
window.formatNumber = function(num, decimals = 0) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    return Number(num).toLocaleString('sv-SE', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
};

const infoTexts = {
    'pop_source': { title: 'Om Källa (Befolkningskopplingar)', content: `<p>Här väljer du vilken befolkning som ska ligga till grund för utbudet av arbetskraft i de olika diagrammen.</p><ul class="list-disc pl-5 space-y-2"><li><b>Fryst (Statisk befolkning):</b> Låser den arbetsföra befolkningen vid basårets nivå. Extremt användbart för att se effekten enbart av en snabb företagsexpansion.</li><li><b>Officiell (Styrfil):</b> Läser in kommunens/SCB:s framskrivna antaganden om framtiden. Sysselsättningsmodellen viktar då automatiskt om utbudet baserat på demografins åldrande.</li><li><b>Anpassad:</b> Ett egenskapskapat scenario (från Prognoskalkylatorn). Låter dig testa vad som händer om vi ökar invandring eller bostadsbyggande radikalt.</li></ul>` },
    'sim_mode': { title: 'Om Läge (Geografisk Avgränsning)', content: `<p>Här väljer du huruvida Linköping ska betraktas som en sluten eller öppen arbetsmarknad i din analys.</p><ul class="list-disc pl-5 space-y-2"><li><b>Fullständig (Pendling):</b> Inkluderar all in- och utpendling över kommungränsen, samt eventuellt virtuellt utbud från pendlingsregionen (distansarbete). Ger den verkligaste bilden.</li><li><b>Endast Lokal (Fryst):</b> Kapar all pendlingstillväxt och fokuserar 100 % på invånarna innanför gränsen. Detta avslöjar snabbt en underliggande lokal kompetensbrist innan den dolts av inpendlare.</li></ul>` },
    'kausalitet': { title: 'Om Kausalitet (Jämviktsmodell)', content: `<p>Avgör hur motorn skall hantera lokala obalanser när du kör din simulering.</p><ul class="list-disc pl-5 space-y-2"><li><b>Analytisk:</b> Modellen låter gapet mellan de gröna (jobb) och blåa (utbud) linjerna stå öppet, så att du själv kan "stänga" gapet manuellt via reglagen.</li><li><b>Dynamisk Jämvikt:</b> Modellen tvingar utbudet att matcha efterfrågan. Kalkylatorn räknar omedelbart ut exakt hur mycket nettoinflyttning som krävs för att fylla gapet, och pumpar in dessa personer i befolkningen.</li></ul>` },
    'shocker': { title: 'Om Specifika Etableringar & Chocker', content: `<p>Gör det möjligt att direkt applicera kända, stora företagsetableringar (eller nedläggningar) i prognosen, utöver den allmänna lokala tillväxten.</p><p>Kalkylatorn hanterar sedan eventuell <b>Branschglidning</b> automatiskt: Om försvaret expanderar drar det direkt till sig kompetens (tar utbud) från besläktade industribranscher inom kommunen, vilket sänker deras tillgängliga utbud i matchningsdiagrammen.</p>` },
    'scenarios': { title: 'Om Snabbscenarier', content: `<p>Dessa knappar laddar snabbt in förinställda värden för alla reglage från Excel-filens flik <em>Scenarier</em>.</p>` },
    'demografi': { title: 'Lokal Tillväxt & Utbud', content: `<p>Reglage som dikterar den organiska utvecklingen på arbetsmarknaden.</p><ul class="list-disc pl-5 space-y-2"><li><b>Lokal Jobbtillväxt:</b> Företagens generella tillväxt. <i>Observera att den procentuella förändringen du anger här summeras och fördelas jämnt över hela prognosperioden.</i></li><li><b>Sysselsättningsgrad:</b> Simulera att vi minskar utanförskapet (förändringen fördelas över perioden). Detta aktiverar en "Catch-up effekt" i bakgrunden där utrikes födda och kvinnor närmar sig inrikes födda män i en allt snabbare takt.</li><li><b>Kvarstannandegrad LiU:</b> Ett kraftfullt verktyg för att simulera att vi lyckas behålla fler tekniska och akademiska talanger i staden.</li></ul>` },
    'inflyttare': { title: 'Inflyttares sysselsättningsgrad', content: `<p>Detta reglage ritar inte om några linjer, utan korrigerar endast nyckeltalet <b>Befolkning (Ny)</b>.</p><p>SCB mäter ofta sysselsättning hos flyttare ett år i efterhand. Eftersom nyanlända arbetskraftsinvandrare ofta flyttar in <i>specifikt</i> för att börja ett jobb, måste deras "Faktiska Sysselsättningsgrad" justeras uppåt i beräkningarna. Detta minskar det totala bostadsbehovet väsentligt i scenarierna.</p>` },
    'geografi': { title: 'Pendling & Geografi', content: `<p>Modellerar arbetsmarknadsregionen och Linköpings pendlingsutbyte.</p><ul class="list-disc pl-5 space-y-2"><li><b>Bosättningskvot:</b> <i>Den valda Bosättningskvoten i styrfilen styr automatiskt hur stor andel av ny efterfrågan i specifika branscher som går till inpendlare!</i></li><li><b>In- och Utpendling:</b> Reglagen drar upp/ned de historiska basvolymerna ytterligare.</li><li><b>Distansarbete:</b> Dämpar behovet av inflyttning genom att skapa ett virtuellt pendlingsutbud via nätet.</li><li><b>Regionförstoring:</b> Bygger på en tyngdkraftsmodell. Minskar vi restiderna räknar kalkylatorn in tusentals nya potentiella pendlande från angränsande kommuner.</li></ul>` },
    'diagram': { title: 'Om Utvecklingsdiagrammen', content: `<p>Välj önskad graf att analysera. Diagrammen använder <b>"Intelligent X-axel"</b>, vilket innebär att grafer som mäter specifik historik (ex. Arbetslöshet) ritar ut data tills det är helt tomt, medan de grafer som kräver full sysselsättningsdata kapar axeln vid basåret om ingen prognos är körd.</p><p><i>TIPS: För matchningsdiagrammen dyker det upp en rullista där du kan filtrera fram specifika "Egna Kluster" definierade i Excel-styrfilen!</i></p>` },
    'befolkning': { title: 'Demografisk Effekt (Befolkningsbehov)', content: `<p>Det slutgiltiga kvittot på om kommunens infrastruktur och bostadsbyggande håller måttet.</p><ul class="list-disc pl-5 space-y-2"><li>Visar exakt hur många ytterligare invånare som måste inrymmas i Linköping för att täcka det omatchade rekryteringsgapet. Modellen bygger på den faktiska åldersstrukturen och sysselsättningsnivån hos inrikes och utrikes inflyttare till länet.</li></ul>` }
};

window.showInfo = function(topicKey) {
    const data = infoTexts[topicKey];
    if(data) {
        document.getElementById('infoModalTitle').innerText = data.title;
        document.getElementById('infoModalContent').innerHTML = data.content;
        document.getElementById('infoModal').classList.remove('hidden');
    }
};

window.closeInfoModal = function() { 
    document.getElementById('infoModal').classList.add('hidden'); 
};

window.addEventListener('click', (e) => { 
    if (e.target === document.getElementById('infoModal')) window.closeInfoModal(); 
});

// --- RULLISTOR OCH DATAKOPPLINGAR ---
window.checkSharedScenario = function() {
    const popSelect = document.getElementById('popSource');
    if (!popSelect) return;
    
    while (popSelect.options.length > 1) { popSelect.remove(1); }

    let hasOfficial = false;
    if (typeof syssConfig !== 'undefined' && (
        (syssConfig['Officiell_befolkningsprognos'] && syssConfig['Officiell_befolkningsprognos'].length > 0) || 
        (syssConfig['officiell_prognos'] && syssConfig['officiell_prognos'].length > 0)
    )) {
        popSelect.add(new Option("Officiell (Styrfil)", "officiell"));
        hasOfficial = true;
    }

    try {
        const shared = localStorage.getItem('linkoping_shared_pop_scenario');
        if (shared) {
            customPopData = JSON.parse(shared);
            popSelect.add(new Option("Anpassad (Prognoskalkylatorn)", "custom"));
            popSelect.value = "custom";
            const btn = document.getElementById('clearCustomBtn');
            if (btn) btn.classList.remove('hidden');
            if (typeof useCustomPop !== 'undefined') useCustomPop = true;
        } else if (hasOfficial) {
            popSelect.value = "officiell";
        } else {
            popSelect.value = "fryst";
        }
    } catch(e) { console.error("Kunde inte läsa in anpassat scenario", e); }
    
    if (typeof window.updatePopSourceDesc === 'function') window.updatePopSourceDesc();
};

window.updatePopSourceDesc = function() {
    const val = document.getElementById('popSource').value;
    const container = document.getElementById('popSourceContainer');
    if (container) {
        if (val === 'fryst') container.title = "Antar att befolkningen (16-74 år) stannar på utgångsårets nivå.";
        else if (val === 'officiell') container.title = "Använder kommunens officiella framskrivning av befolkningen.";
        else if (val === 'custom') container.title = "Använder ditt egna, importerade scenario från Prognoskalkylatorn.";
    }
    if (typeof useCustomPop !== 'undefined') useCustomPop = (val === 'custom');
};

window.clearCustomPop = function() {
    localStorage.removeItem('linkoping_shared_pop_scenario');
    if (typeof customPopData !== 'undefined') customPopData = null;
    if (typeof useCustomPop !== 'undefined') useCustomPop = false;
    const btn = document.getElementById('clearCustomBtn');
    if (btn) btn.classList.add('hidden');
    if (typeof window.checkSharedScenario === 'function') window.checkSharedScenario();
    if (typeof runSimulation === 'function') runSimulation();
};

window.buildDropdowns = function() {
    const progYears = typeof progDataStore !== 'undefined' ? Object.keys(progDataStore).map(Number) : [];
    allYears = [...new Set([...histYearsGlobal, ...progYears])].sort((a,b)=>a-b);

    const yearSelect = document.getElementById('yearSelect');
    if (!yearSelect) return;
    const prevYearVal = yearSelect.value;
    while (yearSelect.firstChild) { yearSelect.removeChild(yearSelect.firstChild); }
    
    if (allYears.length === 0) {
        yearSelect.add(new Option("Data saknas", ""));
    } else {
        [...allYears].reverse().forEach(y => {
            let text = y > baseYear ? y + " (Prognos)" : y.toString();
            let opt = new Option(text, y);
            if(y > baseYear) opt.className = "text-sky-700 font-bold bg-sky-50";
            yearSelect.add(opt);
        });
        
        if (prevYearVal && allYears.includes(parseInt(prevYearVal))) yearSelect.value = prevYearVal;
        else yearSelect.value = baseYear; 
    }

    const startYearSelect = document.getElementById('startYearSelect');
    if (!startYearSelect) return;
    const prevStartVal = startYearSelect.value;
    while (startYearSelect.firstChild) { startYearSelect.removeChild(startYearSelect.firstChild); }

    if (histYearsGlobal.length === 0) {
        startYearSelect.add(new Option("Data saknas", ""));
    } else {
        [...histYearsGlobal].reverse().forEach(y => startYearSelect.add(new Option('Från ' + y, y)));
        const defaultStart = histYearsGlobal[Math.max(0, histYearsGlobal.length - 11)];
        if (prevStartVal && histYearsGlobal.includes(parseInt(prevStartVal))) startYearSelect.value = prevStartVal;
        else startYearSelect.value = defaultStart; 
    }
};

window.handleYearChange = function() {
    if (typeof window.updateKPIs === 'function') window.updateKPIs();
    const chartTypeElement = document.getElementById('chartType');
    if (!chartTypeElement) return;
    const chartType = chartTypeElement.value;
    if (chartType !== 'utbud_efterfragan' && chartType !== 'brp_totalt' && chartType !== 'pop_dynamic' && !chartType.includes('arbetsloshet') && !chartType.includes('langtidsarb') && !chartType.includes('trend_utrikes') && !chartType.includes('trend_kon') && chartType !== 'syssgrad_kon' && chartType !== 'syssgrad_utrikes') {
        if (typeof window.updateDashboard === 'function') window.updateDashboard(true);
    }
};

// --- KPI OCH NYCKELTAL ---
window.updateKPIs = function() {
    const yearSelect = document.getElementById('yearSelect');
    if(!yearSelect) return;
    const yearStr = yearSelect.value;
    if(!yearStr) return;
    const y = parseInt(yearStr);

    let d = y <= baseYear ? histDataStore[y] : (progDataStore[y] || histDataStore[y]);
    if (!d) return;

    const kpiEfterfragan = document.getElementById('kpiEfterfragan');
    if(kpiEfterfragan) kpiEfterfragan.innerText = d.demand != null ? window.formatNumber(d.demand, 0) : 'Data saknas';
    
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

        let inpendlingAndel = (d.inpendling != null && d.demand > 0) ? (d.inpendling / d.demand) * 100 : 0;
        if (typeof takEffekter !== 'undefined' && inpendlingAndel > takEffekter.maxInpendlingsandel) {
            warnings.push({icon: 'fa-car-side', color: 'amber', text: 'Hög inpendlingsandel', title: `Varning: Inpendlingsandel (${window.formatNumber(inpendlingAndel, 1)}%) överstiger ${takEffekter.maxInpendlingsandel}%.`});
        }
        
        let totalPendlingFysisk = (d.inpendling || 0) + (d.utpendling || 0);
        if (typeof takEffekter !== 'undefined' && totalPendlingFysisk > takEffekter.kapacitetstakInfrastruktur) {
            warnings.push({icon: 'fa-train', color: 'red', text: 'Infrastruktur överbelastad', title: `Varning: Fysisk pendling (${window.formatNumber(totalPendlingFysisk, 0)} resor/dag) överstiger taket på ${window.formatNumber(takEffekter.kapacitetstakInfrastruktur, 0)}.`});
        }

        if (causalityMode === 'dynamic' && d.inducedPop !== undefined) {
            if (d.inducedPop > 0) {
                if(kpiBef) {
                    kpiBef.innerText = '+' + window.formatNumber(d.inducedPop, 0);
                    kpiBef.className = "text-base md:text-lg font-bold text-emerald-600";
                    if(kpiBefContainer) kpiBefContainer.title = `Dynamisk jämvikt:\n${window.formatNumber(d.inducedPop, 0)} nya invånare har simulerats flytta in.`;
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
                const employmentRate = (typeof globalMigrantEmploymentRate !== 'undefined' ? globalMigrantEmploymentRate : 0.50) + userSyssAdjustment;
                let totalPopNeeded = omatchatGap / Math.max(0.01, employmentRate); 

                if(kpiBef) {
                    kpiBef.innerText = '+' + window.formatNumber(totalPopNeeded, 0);
                    kpiBef.className = "text-base md:text-lg font-bold text-orange-600";
                    if(kpiBefContainer) kpiBefContainer.title = `Analys av gap:\nDet kvarstår ett gap på ${window.formatNumber(omatchatGap, 0)} jobb.\nFör att fylla detta krävs inflyttning av ca ${window.formatNumber(totalPopNeeded, 0)} nya invånare.`;
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
            if (typeof takEffektMaxSyss !== 'undefined' && d.displayRate > takEffektMaxSyss) {
                kpiSyssGrad.className = "text-base md:text-lg font-bold text-red-600";
                warnings.push({icon: 'fa-triangle-exclamation', color: 'red', text: 'Arbetskraftsbrist', title: `Varning: Sysselsättningsgraden (${window.formatNumber(d.displayRate, 1)}%) överstiger taket på ${takEffektMaxSyss}%.`});
            } else if (causalityMode === 'analytic' && !(d.demand != null && d.supply != null && (d.demand - (d.supply + (d.netCommuting !== undefined ? d.netCommuting : (d.explicitNetCommuting || 0)) + (d.virtualSupply || 0))) <= -5) ) {
                kpiSyssGrad.className = "text-base md:text-lg font-bold text-gray-800";
            }
        } else {
            kpiSyssGrad.innerText = 'Data saknas';
        }
    }

    if (d.arbetsloshetPct != null && typeof takEffekter !== 'undefined' && d.arbetsloshetPct < takEffekter.minArbetsloshet) {
        warnings.push({icon: 'fa-fire', color: 'orange', text: 'Under friktionsgräns', title: `Varning: Arbetslösheten (${window.formatNumber(d.arbetsloshetPct, 1)}%) är lägre än friktionsgränsen på ${takEffekter.minArbetsloshet}%.`});
    }
    
    const warningEl = document.getElementById('takWarning');
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

            if (d.brp === null && d.extrapolatedBrp != null && y <= baseYear) {
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

// --- HUVUDFUNKTION FÖR ATT RITA DIAGRAMMEN ---
window.updateDashboard = function(calledFromDropdown = true) {
    const chartTypeElement = document.getElementById('chartType');
    const subGroupSelect = document.getElementById('subGroupSelect');
    if(!chartTypeElement || !subGroupSelect) return;
    
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

    // Menystyrning beroende på diagramtyp
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
        if(dualAxesContainer && chartType.includes('_utrikes')) { dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); }
        else if (dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        
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
            if (typeof syssConfig !== 'undefined' && syssConfig['SNIgrupper'] && syssConfig['SNIgrupper'].length > 0) {
                const firstRow = syssConfig['SNIgrupper'][0];
                const groupCols = Object.keys(firstRow).slice(1);
                groupCols.forEach(col => subGroupSelect.add(new Option(col, col)));
            }
            subGroupSelect.setAttribute('data-type', 'bransch');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
    } else if (chartType === 'syssgrad_kon') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        if (subGroupSelect.getAttribute('data-type') !== 'syssgrad') {
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
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
    } else if (chartType === 'trend_utrikes' || chartType === 'syssgrad_utrikes') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); }
        subGroupSelect.classList.add('hidden'); 
        chartTypeElement.classList.add('rounded-r');
    } else {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        subGroupSelect.classList.add('hidden');
        chartTypeElement.classList.add('rounded-r');
    }

    const startYearSelect = document.getElementById('startYearSelect');
    const desc = document.getElementById('chartDescription');
    const title = document.getElementById('trendTitle');
    const selectedYearStr = document.getElementById('yearSelect').value;
    const ctxElement = document.getElementById('trendChart');
    if(!ctxElement) return;
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
    const refYear = isProgYear ? baseYear : selYearInt;
    const currentPopData = (typeof useCustomPop !== 'undefined' && useCustomPop && customPopData) ? customPopData : popData;
    
    if (typeof trendChartInstance !== 'undefined' && trendChartInstance) {
        trendChartInstance.data.datasets.forEach((ds, i) => {
            const meta = trendChartInstance.getDatasetMeta(i);
            globalChartVisibility[ds.label] = meta.hidden === null ? ds.hidden : meta.hidden;
        });
        trendChartInstance.destroy();
    }

    wrapper.style.minHeight = '300px';
    const yGraceElement = document.getElementById('yGrace');
    const graceVal = yGraceElement ? yGraceElement.value : '20%';

    let labels = [];
    let datasets = [];
    let isHorizontal = false;
    let isStacked = false;
    let isBarChart = false;
    let customScale = null;
    let isMultiLine = false;
    
    const graphStartYear = isComparing ? baseYear : (parseInt(startYearSelect.value) || (allYears.length > 0 ? allYears[0] : 0));
    const activeYears = allYears.filter(y => y >= graphStartYear);

    // ==================
    // RITLOGIK PER TYP
    // ==================
    if (chartType === 'pop_dynamic') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (typeof progDataStore !== 'undefined' && progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
        if (title) title.innerText = "Framtida Befolkning 16-74 år (Dynamisk)" + suffix;
        if (desc) desc.innerText = "Visar kommunens basbefolkning i åldern 16-74 år. Om du har den dynamiska modellen aktiverad visar grafen även det simulerade befolkningstillskottet för motsvarande åldrar.";

        const popGroupVal = subGroupSelect.value;
        let hasProg = false;
        labels = activeYears;

        if (popGroupVal === 'total') {
            let h_pop=[], p_base=[], p_induced=[];
            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) h_pop.push(histDataStore[numericY].pop);
                else h_pop.push(null);
                
                if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) {
                    let d = progDataStore[numericY];
                    let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                    let base = d.pop - induced;
                    p_base.push(base); p_induced.push(induced); hasProg = true;
                } else if (y === baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
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

            let groups = [
                { label: '16-19 år', sex: null, min: 16, max: 19, color: '#0284c7' },
                { label: '20-24 år', sex: null, min: 20, max: 24, color: '#10b981' },
                { label: '25-64 år', sex: null, min: 25, max: 64, color: '#8b5cf6' },
                { label: '65-74 år', sex: null, min: 65, max: 74, color: '#f59e0b' }
            ];
            
            if (popGroupVal === '5yr') {
                groups = [];
                const colors = ['#0284c7', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#14b8a6', '#f97316', '#84cc16'];
                groups.push({ label: '16-19 år', sex: null, min: 16, max: 19, color: colors[0] });
                let colorIdx = 1;
                for (let i = 20; i <= 70; i += 5) {
                    let end = (i === 70) ? 74 : i+4;
                    groups.push({ label: `${i}-${end} år`, sex: null, min: i, max: end, color: colors[colorIdx % colors.length] });
                    colorIdx++;
                }
            }

            groups.forEach((g, idx) => {
                let h_data = [], p_data = [];
                labels.forEach((yStr) => {
                    let numericY = Number(yStr);
                    let isProg = numericY > baseYear;
                    let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
                    let groupBase = getPopForGroup(searchStr, g);
                    let totalBase16_74 = getPopForGroup(searchStr, { min: 16, max: 74 });
                    let finalPop = groupBase;
                    if (isProg && typeof progDataStore !== 'undefined' && progDataStore[numericY] && causalityMode === 'dynamic') {
                        let induced = progDataStore[numericY].inducedPop || 0;
                        let groupInduced = totalBase16_74 > 0 ? induced * (groupBase / totalBase16_74) : 0;
                        finalPop += groupInduced;
                    }
                    if (isProg) { h_data.push(null); p_data.push(finalPop); hasProg = true; } 
                    else { h_data.push(finalPop); p_data.push(null); }
                });
                labels.forEach((yStr, idx2) => { if (Number(yStr) === baseYear && idx2 < labels.length - 1) p_data[idx2] = h_data[idx2]; });
                datasets.push({ label: g.label, data: h_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true });
                if (p_data.some(v => v !== null)) datasets.push({ label: g.label + ' (Prognos)', data: p_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            });
        }

    } else if (chartType === 'utbud_efterfragan') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (typeof progDataStore !== 'undefined' && progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
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
            if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) { hDemand.push(histDataStore[numericY].demand); hSupply.push(histDataStore[numericY].supply); hTotalSupply.push(histDataStore[numericY].totalSupply); } 
            else { hDemand.push(null); hSupply.push(null); hTotalSupply.push(null); }
            
            if (y === baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) { pDemand.push(histDataStore[numericY].demand); pSupply.push(histDataStore[numericY].supply); pTotalSupply.push(histDataStore[numericY].totalSupply); } 
            else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) { pDemand.push(progDataStore[numericY].demand); pSupply.push(progDataStore[numericY].supply); pTotalSupply.push(progDataStore[numericY].totalSupply); } 
            else { pDemand.push(null); pSupply.push(null); pTotalSupply.push(null); }
            
            if (isComparing) {
                if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) { sDemand.push(histDataStore[numericY].demand); sSupply.push(histDataStore[numericY].supply); sTotalSupply.push(histDataStore[numericY].totalSupply); } 
                else if (y > baseYear && savedProjectedData && savedProjectedData[numericY]) { sDemand.push(savedProjectedData[numericY].demand); sSupply.push(savedProjectedData[numericY].supply); sTotalSupply.push(savedProjectedData[numericY].totalSupply); } 
                else { sDemand.push(null); sSupply.push(null); sTotalSupply.push(null); }
            }
        });
        
        const hasProg = pDemand.some((v, idx) => v !== null && labels[idx] > baseYear);
        
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
        datasets.forEach(ds => { if (defaultHiddenLabels.includes(ds.label)) ds.hidden = true; });

    } else if (chartType === 'utbud_efterfragan_delta') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "Årlig förändring (Nytt utbud/Efterfrågan)";
        if (desc) desc.innerText = "Visar hur många nya arbetstillfällen och invånare som tillkommer eller försvinner varje enskilt år jämfört med året innan.";
        isBarChart = true;

        let dDemand = [], dSupply = [];
        labels = activeYears;
        
        labels.forEach(y => {
            let numY = Number(y);
            let currD = null, currS = null;
            let prevD = null, prevS = null;

            if (numY <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numY]) {
                currD = histDataStore[numY].demand; currS = histDataStore[numY].supply;
            } else if (numY > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numY]) {
                currD = progDataStore[numY].demand; currS = progDataStore[numY].supply;
            }

            if (numY - 1 <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numY - 1]) {
                prevD = histDataStore[numY - 1].demand; prevS = histDataStore[numY - 1].supply;
            } else if (numY - 1 > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numY - 1]) {
                prevD = progDataStore[numY - 1].demand; prevS = progDataStore[numY - 1].supply;
            }

            if (currD != null && prevD != null) dDemand.push(currD - prevD); else dDemand.push(null);
            if (currS != null && prevS != null) dSupply.push(currS - prevS); else dSupply.push(null);
        });

        datasets = [
            { type: 'bar', label: 'Förändring Efterfrågan', data: dDemand, backgroundColor: '#10b981' },
            { type: 'bar', label: 'Förändring Lokalt Utbud', data: dSupply, backgroundColor: '#0ea5e9' }
        ];

    } else if (chartType === 'trend_utrikes' || chartType === 'trend_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (typeof progDataStore !== 'undefined' && progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
        
        let key1_n, key2_n, key1_d, key2_d, lbl1_n, lbl2_n, lbl1_d, lbl2_d, col1, col2;
        if (chartType === 'trend_utrikes') {
            if (title) title.innerText = "Integration: Arbetsmarknad efter ursprung" + suffix;
            if (desc) desc.innerText = "Visar hur utbudet (nattbefolkning) och efterfrågan (dagbefolkning) fördelar sig mellan inrikes och utrikes födda i absoluta tal.";
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
            if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                h_n1.push(histDataStore[numericY][key1_n]); h_n2.push(histDataStore[numericY][key2_n]);
                h_d1.push(histDataStore[numericY][key1_d]); h_d2.push(histDataStore[numericY][key2_d]);
            } else { h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null); }
            
            if (y === baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                p_n1.push(histDataStore[numericY][key1_n]); p_n2.push(histDataStore[numericY][key2_n]);
                p_d1.push(histDataStore[numericY][key1_d]); p_d2.push(histDataStore[numericY][key2_d]);
            } else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) {
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
        
        const hasProg = p_n1.some((v, idx) => v !== null && labels[idx] > baseYear);
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
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes (Antal)', color: col1 }, ticks: { callback: val => window.formatNumber(val) } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes (Antal)', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val) } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
        } else {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val) } } };
        }

    } else if (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (typeof progDataStore !== 'undefined' && progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
        
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

        const ageGroup = subGroupSelect.value;
        let h_1 = [], h_2 = [], h_tot = [], p_1 = [], p_2 = [], p_tot = [];
        labels = activeYears;
        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985) {
                let v1 = null, v2 = null;
                if (typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                    if (chartType === 'syssgrad_utrikes') {
                        v1 = histDataStore[numericY][key1] != null ? parseFloat(histDataStore[numericY][key1]) : null;
                        v2 = histDataStore[numericY][key2] != null ? parseFloat(histDataStore[numericY][key2]) : null;
                    } else {
                        v1 = histDataStore[numericY][key1] && histDataStore[numericY][key1][ageGroup] != null ? parseFloat(histDataStore[numericY][key1][ageGroup]) : null;
                        v2 = histDataStore[numericY][key2] && histDataStore[numericY][key2][ageGroup] != null ? parseFloat(histDataStore[numericY][key2][ageGroup]) : null;
                    }
                }

                if (y <= baseYear) { h_1.push(v1); h_2.push(v2); h_tot.push(typeof histDataStore !== 'undefined' && histDataStore[numericY] ? histDataStore[numericY].displayRate : null); } 
                else { h_1.push(null); h_2.push(null); h_tot.push(null); }
                
                if (y === baseYear) { p_1.push(v1); p_2.push(v2); p_tot.push(typeof histDataStore !== 'undefined' && histDataStore[numericY] ? histDataStore[numericY].displayRate : null); } 
                else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) {
                    let base_1 = null, base_2 = null;
                    if (typeof histDataStore !== 'undefined' && histDataStore[baseYear]) {
                        if (chartType === 'syssgrad_utrikes') {
                            base_1 = histDataStore[baseYear][key1] != null ? parseFloat(histDataStore[baseYear][key1]) : null;
                            base_2 = histDataStore[baseYear][key2] != null ? parseFloat(histDataStore[baseYear][key2]) : null;
                        } else {
                            base_1 = histDataStore[baseYear][key1] && histDataStore[baseYear][key1][ageGroup] != null ? parseFloat(histDataStore[baseYear][key1][ageGroup]) : null;
                            base_2 = histDataStore[baseYear][key2] && histDataStore[baseYear][key2][ageGroup] != null ? parseFloat(histDataStore[baseYear][key2][ageGroup]) : null;
                        }
                    }
                    let base_tot = typeof histDataStore !== 'undefined' && histDataStore[baseYear].displayRate != null ? parseFloat(histDataStore[baseYear].displayRate) : null;
                    
                    if (chartType === 'syssgrad_utrikes') {
                        p_1.push(progDataStore[numericY].syss_in_tot);
                        p_2.push(progDataStore[numericY].syss_ut_tot);
                    } else {
                        p_1.push(progDataStore[numericY].syssGradM && progDataStore[numericY].syssGradM[ageGroup] != null ? parseFloat(progDataStore[numericY].syssGradM[ageGroup]) : null);
                        p_2.push(progDataStore[numericY].syssGradK && progDataStore[numericY].syssGradK[ageGroup] != null ? parseFloat(progDataStore[numericY].syssGradK[ageGroup]) : null);
                    }
                    p_tot.push(progDataStore[numericY].displayRate);
                } else { p_1.push(null); p_2.push(null); p_tot.push(null); }
            }
        });

        datasets = [
            { label: `Sysselsättningsgrad ${lbl1} %`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: `Sysselsättningsgrad ${lbl2} %`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
        ];
        if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt %', data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });

        const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > baseYear);
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
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
        } else {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 1) + '%' } } };
        }

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
        
        let suffixTxt = typeVal === 'num' ? " i absoluta tal (Antal personer)." : (typeVal === 'insk' ? " som procent av inskrivna arbetslösa." : " som procent av arbetskraften.");
        if (desc) {
            if (groupStr === 'totalt') desc.innerText = isLangtid ? "Andel långtidsarbetslösa (Totalt). Denna grupp utgör ofta kärnan i den strukturella arbetslösheten." : "Historisk andel av arbetskraften som är inskriven arbetslös. Fungerar som referens.";
            else if (groupStr === 'utrikes') desc.innerText = isLangtid ? "Långtidsarbetslösa uppdelat på bakgrund." : "Visar hur andelen inskrivna arbetslösa skiljer sig mellan inrikes födda och utrikes födda historiskt.";
            else desc.innerText = (isLangtid ? "Långtidsarbetslösa" : "Visar hur andelen inskrivna arbetslösa skiljer sig") + " mellan könen" + suffixTxt;
        }

        let h_1=[], h_2=[], p_1=[], p_2=[], h_tot=[], p_tot=[];
        
        // Intelligent X-axel: Låt arbetslöshet sträcka sig till det verkliga slutet på dess data, men klipp prognos-åren
        const maxHistYear = (typeof histYearsGlobal !== 'undefined' && histYearsGlobal.length > 0) ? Math.max(...histYearsGlobal) : baseYear;
        labels = [];
        activeYears.forEach(y => {
            if (y <= maxHistYear) {
                let numericY = Number(y);
                if (numericY >= 1985) {
                    labels.push(y);
                    let d = typeof histDataStore !== 'undefined' ? histDataStore[numericY] : null;
                    
                    if (d) {
                        let objArb = d.arb || {
                            tot_num: null, m_num: null, k_num: null, in_num: null, ut_num: null,
                            tot_pct: d.arbetsloshetPct !== undefined ? d.arbetsloshetPct : null,
                            m_pct: d.arb_man !== undefined ? d.arb_man : null,
                            k_pct: d.arb_kvinna !== undefined ? d.arb_kvinna : null,
                            in_pct: d.arb_inrikes !== undefined ? d.arb_inrikes : null,
                            ut_pct: d.arb_utrikes !== undefined ? d.arb_utrikes : null
                        };
                        let objLarb = d.larb || {
                            tot_num: null, m_num: null, k_num: null, in_num: null, ut_num: null,
                            tot_pct: d.langtidsPct !== undefined ? d.langtidsPct : null,
                            m_pct: d.larb_man !== undefined ? d.larb_man : null,
                            k_pct: d.larb_kvinna !== undefined ? d.larb_kvinna : null,
                            in_pct: d.larb_inrikes !== undefined ? d.larb_inrikes : null,
                            ut_pct: d.larb_utrikes !== undefined ? d.larb_utrikes : null,
                            tot_insk: null, m_insk: null, k_insk: null, in_insk: null, ut_insk: null
                        };
                        
                        let obj = isLangtid ? objLarb : objArb;
                        
                        if (groupStr === 'totalt') {
                            let val = null;
                            if (typeVal === 'num') val = obj.tot_num;
                            else if (typeVal === 'insk') val = obj.tot_insk;
                            else val = obj.tot_pct;
                            
                            if (y <= baseYear) h_1.push(val); else h_1.push(null);
                            
                            if (y === baseYear) p_1.push(val);
                            else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) p_1.push(isLangtid ? progDataStore[numericY].langtidsPct : progDataStore[numericY].arbetsloshetPct);
                            else p_1.push(null);
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
                            
                            if (y <= baseYear) { h_1.push(v1); h_2.push(v2); h_tot.push(vTot); } 
                            else { h_1.push(null); h_2.push(null); h_tot.push(null); }
                            
                            if (y === baseYear) { p_1.push(v1); p_2.push(v2); p_tot.push(vTot); } 
                            else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) {
                                let key1 = isLangtid ? (groupStr === 'utrikes' ? 'larb_inrikes' : 'larb_man') : (groupStr === 'utrikes' ? 'arb_inrikes' : 'arb_man');
                                let key2 = isLangtid ? (groupStr === 'utrikes' ? 'larb_utrikes' : 'larb_kvinna') : (groupStr === 'utrikes' ? 'arb_utrikes' : 'arb_kvinna');
                                let totKey = isLangtid ? 'langtidsPct' : 'arbetsloshetPct';
                                p_1.push(progDataStore[numericY][key1] !== undefined ? progDataStore[numericY][key1] : null); 
                                p_2.push(progDataStore[numericY][key2] !== undefined ? progDataStore[numericY][key2] : null); 
                                p_tot.push(progDataStore[numericY][totKey] !== undefined ? progDataStore[numericY][totKey] : null);
                            } 
                            else { p_1.push(null); p_2.push(null); p_tot.push(null); }
                        }
                    } else {
                        h_1.push(null); h_2.push(null); h_tot.push(null);
                        p_1.push(null); p_2.push(null); p_tot.push(null);
                    }
                }
            }
        });

        let lblSuffix = typeVal === 'num' ? ' (Antal)' : ' %';

        if (groupStr === 'totalt') {
            let lbl = isLangtid ? 'Långtidsarbetslösa' : 'Arbetslösa';
            datasets = [
                { label: lbl + lblSuffix, data: h_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: isLangtid ? 'rgba(249, 115, 22, 0.2)' : 'rgba(239, 68, 68, 0.2)', borderWidth: 3, pointStyle: 'circle', fill: true, spanGaps: true }
            ];
            const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > baseYear);
            if (hasProg && typeVal !== 'num' && typeVal !== 'insk') {
                datasets.push({ label: 'Teoretisk ' + lbl + ' (Prognos)', data: p_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'circle', fill: false });
            }
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
            
            const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > baseYear);
            if (hasProg && typeVal !== 'num' && typeVal !== 'insk') {
                datasets.push({ label: `${lbl1} % (Prognos)`, data: p_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                datasets.push({ label: `${lbl2} % (Prognos)`, data: p_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
                if (groupStr === 'kon') datasets.push({ label: 'Totalt % (Prognos)', data: p_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect', fill: false, hidden: true });
            }
        }
        
        if (useDualAxes && groupStr === 'utrikes' && typeVal !== 'num') {
            let col1 = '#0ea5e9'; let col2 = '#f97316';
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: 'Inrikes %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: 'Utrikes %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes('Utrikes') ? 'y1' : 'y'; });
        } else if (typeVal === 'num') {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0) } } };
        } else {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 1) + '%' } } };
        }

    } else if (chartType === 'brp_totalt') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (typeof progDataStore !== 'undefined' && progDataStore[allYears[allYears.length-1]] ? " (Prognos)" : " (Historik)");
        if (title) title.innerText = "Ekonomisk Tillväxt" + suffix;
        if (desc) desc.innerText = "Visar den totala storleken på Linköpings lokala ekonomi (Bruttoregionalprodukt).";

        const graphStartYear = isComparing ? baseYear : (parseInt(startYearSelect.value) || (allYears.length > 0 ? allYears[0] : 0));
        labels = []; 
        let hBRP = [], pBRP = [], sBRP = [];

        allYears.forEach(y => {
            if (y >= graphStartYear) {
                labels.push(y);
                let numericY = Number(y);
                
                if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                    let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                    let tot = (brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null;
                    hBRP.push(tot);
                } else {
                    hBRP.push(null);
                }
                
                if (y === baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                    let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                    let tot = (brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null;
                    pBRP.push(tot);
                } else if (y > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numericY]) {
                    pBRP.push(progDataStore[numericY].totalBrpMkr);
                } else {
                    pBRP.push(null);
                }
                
                if (isComparing) {
                    if (y <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numericY]) {
                        let brpPer = histDataStore[numericY].brp || histDataStore[numericY].extrapolatedBrp;
                        let tot = (brpPer && histDataStore[numericY].demand) ? (brpPer * histDataStore[numericY].demand) / 1000 : null;
                        sBRP.push(tot);
                    } else if (y > baseYear && typeof savedProjectedData !== 'undefined' && savedProjectedData[numericY]) {
                        sBRP.push(savedProjectedData[numericY].totalBrpMkr);
                    } else {
                        sBRP.push(null);
                    }
                }
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
        customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0) } } };

    } else if (chartType === 'pendling_detalj') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "In- och utpendling (Kommungräns)";
        if (desc) desc.innerText = "Visar pendlingsflödena över kommungränsen i absoluta tal (antal personer) samt det resulterande pendlingsnettot.";
        isBarChart = true;

        const mode = subGroupSelect ? subGroupSelect.value : 'neg';
        let hIn = [], hUt = [], hNet = [];
        let pIn = [], pUt = [], pNet = [];
        const graphStartYear = isComparing ? baseYear : (parseInt(startYearSelect.value) || (allYears.length > 0 ? allYears[0] : 0));
        labels = activeYears.filter(y => y >= graphStartYear);
        
        labels.forEach(y => {
            let numY = Number(y);
            if (numY <= baseYear && typeof histDataStore !== 'undefined' && histDataStore[numY]) {
                hIn.push(histDataStore[numY].inpendling);
                let utVal = histDataStore[numY].utpendling;
                hUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null); 
                hNet.push(histDataStore[numY].netCommuting);
            } else { hIn.push(null); hUt.push(null); hNet.push(null); }
            
            if (numY === baseYear && typeof histDataStore !== 'undefined' && histDataStore[numY]) {
                pIn.push(histDataStore[numY].inpendling);
                let utVal = histDataStore[numY].utpendling;
                pUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null);
                pNet.push(histDataStore[numY].netCommuting);
            } else if (numY > baseYear && typeof progDataStore !== 'undefined' && progDataStore[numY]) {
                pIn.push(progDataStore[numY].inpendling);
                let utVal = progDataStore[numY].utpendling;
                pUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null);
                pNet.push(progDataStore[numY].explicitNetCommuting);
            } else { pIn.push(null); pUt.push(null); pNet.push(null); }
        });

        datasets = [
            { type: 'bar', label: 'Inpendling', data: hIn, backgroundColor: '#0ea5e9', order: 2 },
            { type: 'bar', label: 'Utpendling', data: hUt, backgroundColor: '#ef4444', order: 3 },
            { type: 'line', label: 'Pendlingsnetto', data: hNet, borderColor: '#334155', borderWidth: 3, fill: false, pointStyle: 'rect', order: 1 }
        ];
        
        const hasProg = pIn.some((v, idx) => v !== null && labels[idx] > baseYear);
        if (hasProg && !isComparing) {
            datasets.push({ type: 'bar', label: 'Inpendling (Prognos)', data: pIn, backgroundColor: 'rgba(14, 165, 233, 0.4)', order: 2 });
            datasets.push({ type: 'bar', label: 'Utpendling (Prognos)', data: pUt, backgroundColor: 'rgba(239, 68, 68, 0.4)', order: 3 });
            datasets.push({ type: 'line', label: 'Pendlingsnetto (Prognos)', data: pNet, borderColor: '#94a3b8', borderWidth: 3, borderDash: [5,5], fill: false, pointStyle: 'rect', order: 1 });
        }
    } else if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
        startYearSelect.style.display = 'none'; 
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
            dagData = aggregateMatchData(typeof syssBasdata !== 'undefined' ? (syssBasdata['Syss_utbnivå'] || syssBasdata['Syss_utbniva'] || []) : [], refYear, labels, 'Utbildningsnivå', mapLevel);
            nattData = aggregateMatchData(typeof syssBasdata !== 'undefined' ? (syssBasdata['Natt_utbnivå'] || syssBasdata['Natt_utbniva'] || []) : [], refYear, labels, 'Utbildningsnivå', mapLevel);
        
        } else if (chartType === 'sektor_match') {
            if (title) title.innerText = `Sektormatchning (År ${selectedYearStr})`;
            if (desc) desc.innerHTML = `Sektor för invånarna jämfört med sektor för jobben.`;
            labels = ['Privat sektor', 'Offentlig sektor'];
            dagData = aggregateMatchData(typeof syssBasdata !== 'undefined' ? (syssBasdata['Syss_sektor'] || []) : [], refYear, labels, 'Sektor');
            nattData = aggregateMatchData(typeof syssBasdata !== 'undefined' ? (syssBasdata['Natt_sektor'] || []) : [], refYear, labels, 'Sektor');
        
        } else if (chartType === 'sektor_match_kon') {
            if (title) title.innerText = `Sektormatchning: Män och Kvinnor (År ${selectedYearStr})`;
            if (desc) desc.innerHTML = `Sektor för invånarna jämfört med sektor för jobben, uppdelat på kön.`;
            labels = ['Privat sektor', 'Offentlig sektor'];
            isGenderSplit = true;
            
            let d_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
            let d_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
            let n_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
            let n_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };

            if (typeof syssBasdata !== 'undefined') {
                (syssBasdata['Syss_sektor'] || []).filter(r => extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) { d_m[sec] += parseFloat(r['Män'] || r['män'] || 0); d_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
                });
                (syssBasdata['Natt_sektor'] || []).filter(r => extractYear(r) == refYear).forEach(r => {
                    let sec = String(r['Sektor'] || '').trim();
                    if(labels.includes(sec)) { n_m[sec] += parseFloat(r['Män'] || r['män'] || 0); n_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
                });
            }
            dagData = {'män': d_m, 'kvinnor': d_k};
            nattData = {'män': n_m, 'kvinnor': n_k};

        } else if (chartType === 'bransch_match') {
            if (title) title.innerText = `Branschmatchning (År ${selectedYearStr})`;
            if (desc) desc.innerHTML = `Detaljerad matchning per näringsgren/bransch. Röda markeringar (<0) visar lokalt underskott.`;
            isHorizontal = true;
            const dfDag = typeof syssBasdata !== 'undefined' ? (syssBasdata['Syss_bransch'] || []) : [];
            const dfNatt = typeof syssBasdata !== 'undefined' ? (syssBasdata['Natt_bransch'] || []) : [];
            
            let rawLabels = [];
            if (dfDag.length > 0) {
                const excludeCols = ['År', 'år', 'Samtliga', 'Totalt', 'Kön', 'kön', 'Okänd bransch'];
                rawLabels = Object.keys(dfDag[0]).filter(k => !excludeCols.includes(k));
            }
            
            let dagDataRaw = aggregateMatchData(dfDag, refYear, rawLabels, 'Cols');
            let nattDataRaw = aggregateMatchData(dfNatt, refYear, rawLabels, 'Cols');
            
            const subGroupVal = subGroupSelect ? subGroupSelect.value : 'all';
            if (subGroupVal && subGroupVal !== 'all' && typeof syssConfig !== 'undefined' && syssConfig['SNIgrupper']) {
                let groupedDag = { 'totalt': {} }, groupedNatt = { 'totalt': {} };
                const sniGrupper = syssConfig['SNIgrupper'];
                const firstKey = Object.keys(sniGrupper[0])[0]; 

                rawLabels.forEach(l => {
                    let mappingRow = sniGrupper.find(r => String(r[firstKey]).trim() === String(l).trim());
                    let targetGroup = mappingRow ? mappingRow[subGroupVal] : null;

                    if (targetGroup && targetGroup !== null && String(targetGroup).trim() !== '') {
                        let groupName = String(targetGroup).trim();
                        if (!groupedDag['totalt'][groupName]) { groupedDag['totalt'][groupName] = 0; groupedNatt['totalt'][groupName] = 0; }
                        groupedDag['totalt'][groupName] += dagDataRaw['totalt'][l] || 0;
                        groupedNatt['totalt'][groupName] += nattDataRaw['totalt'][l] || 0;
                    }
                });
                labels = Object.keys(groupedDag['totalt']);
                dagData = groupedDag; nattData = groupedNatt;
            } else {
                labels = rawLabels;
                dagData = dagDataRaw;
                nattData = nattDataRaw;
            }

            if (labels.length > 15 && (!subGroupVal || subGroupVal === 'all')) {
                wrapper.style.minHeight = (labels.length * 20) + 'px';
            }
        }
        
        drawMatchChart(selYearInt, labels, dagData, nattData, isGenderSplit, useZeroAxis, isHorizontal);
        return; 
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
        if (globalChartVisibility[ds.label] !== undefined) ds.hidden = globalChartVisibility[ds.label];
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

        trendChartInstance = new Chart(ctx, {
            type: 'bar',
            data: { labels: labels.map(l => String(l).replace(' (Prognos)', '')), datasets: datasets },
            options: {
                indexAxis: isHorizontal ? 'y' : 'x', 
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: scaleConfig,
                plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, decimals) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
            }
        });
    }

    if (!calledFromDropdown) window.updateKPIs();
    
    const hideAllBtn = document.getElementById('hideAllBtn');
    if (hideAllBtn && !hideAllBtn.classList.contains('hidden')) {
        const anyVis = trendChartInstance.data.datasets.some((ds, i) => trendChartInstance.isDatasetVisible(i));
        hideAllBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
    }
};

window.toggleAllSeries = function() {
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
};