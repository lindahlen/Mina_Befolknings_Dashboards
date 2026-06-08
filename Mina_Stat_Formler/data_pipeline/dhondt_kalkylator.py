# -*- coding: utf-8 -*-
"""
Modul för d'Hondts mandatfördelning med Excel-integration
Designad för Prognosmakarens gis-env (Master Config v2.0)
Author: Jimmy Lindahl, Analys & Utredning, Linköpings kommun
"""

import os
import sys
import pandas as pd

# ==========================================
# 1. MILJÖ OCH SÖKVÄGAR ENLIGT MASTER CONFIG
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass 

# ==========================================
# 2. STANDARDKOD FÖR TEXTFIX (UTF-8 / ANSI)
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

# ==========================================
# 3. KÄRNALGORITM: d'HONDTS METOD
# ==========================================
def calculate_dhondt(votes_dict, total_seats):
    """
    Fördelar mandat enligt d'Hondts metod (divisorer: 1, 2, 3...)
    :param votes_dict: Dictionary med { 'Gruppering': Antal röster/KF-mandat }
    :param total_seats: Antal platser i nämnden
    :return: (Dictionary med utdelade platser, Pandas DataFrame med beräkningslogg)
    """
    seats = {party: 0 for party in votes_dict.keys()}
    log_data = []

    for seat_num in range(1, total_seats + 1):
        max_quotient = -1.0
        winner = None
        ties = []

        for party, votes in votes_dict.items():
            if votes == 0 or pd.isna(votes):
                continue
            
            # d'Hondt divisor: (seats + 1)
            quotient = float(votes) / (seats[party] + 1)
            
            # Hantera avrundning/lika tal
            if abs(quotient - max_quotient) < 1e-6:
                ties.append(party)
            elif quotient > max_quotient:
                max_quotient = quotient
                winner = party
                ties = [party]

        # Avbrott om inga mandat finns att fördela
        if winner is None:
            break

        # Vid lika jämförelsetal ska formellt lottning ske.
        is_tie = len(ties) > 1
        actual_winner = ties[0]
        
        seats[actual_winner] += 1
        
        log_data.append({
            'Plats_nr': seat_num,
            'Tilldelas': actual_winner,
            'Jämförelsetal': max_quotient,
            'Lottning_krävs': is_tie,
            'Inblandade_vid_lika': ", ".join(ties) if is_tie else ""
        })

    return seats, pd.DataFrame(log_data)

# ==========================================
# 4. EXCEL-HANTERING OCH KÖRNING
# ==========================================
def create_excel_template(filepath):
    """ Skapar en Excel-mall om ingen fil finns """
    print(f"Hittade ingen datafil. Skapar en mall: {filepath}")
    data = {
        'Parti/Kartell': [
            'Tillsammans för Linköping (S+M)', 
            'Sverigedemokraterna', 
            'Centerpartiet', 
            'Vänsterpartiet', 
            'Miljöpartiet', 
            'Kristdemokraterna', 
            'Liberalerna', 
            'Linköpingslistan'
        ],
        '2018': [40, 8, 8, 5, 5, 6, 7, 0],
        '2022': [38, 10, 6, 5, 5, 4, 4, 7],
        '2026': [0, 0, 0, 0, 0, 0, 0, 0],
        '2030': [0, 0, 0, 0, 0, 0, 0, 0]
    }
    df = pd.DataFrame(data)
    df.to_excel(filepath, index=False)
    print("Mall skapad! Fyll i dina egna siffror och kör skriptet igen.")

if __name__ == "__main__":
    print("--- Startar Mandatberäkning (Analys & Utredning) ---")
    
    excel_file = "mandat_data.xlsx"
    target_year = "2026" # Kan ändras till '2022' eller '2030'
    nämndstorlek = 11
    
    # 1. Kolla om Excel-filen finns, annars skapa den
    if not os.path.exists(excel_file):
        create_excel_template(excel_file)
        # Vi kör på standarddata om mallen precis skapades
        target_year = "2022" 
    
    # 2. Läs in data från Excel
    print(f"\nLäser in data för år {target_year} från {excel_file}...")
    try:
        df = pd.read_excel(excel_file)
        # Bygg dictionary: {'Partinamn': röster_för_valt_år}
        if target_year in df.columns:
            votes_dict = dict(zip(df['Parti/Kartell'], df[target_year]))
        else:
            print(f"VARNING: År {target_year} saknas i Excel-filen. Avbryter.")
            sys.exit()
    except Exception as e:
        print(f"Fel vid inläsning av Excel: {e}")
        sys.exit()

    # 3. Kör d'Hondts metod
    slutresultat, log_df = calculate_dhondt(votes_dict, nämndstorlek)
    
    # 4. Visa resultat i terminalen
    print(f"\nSlutgiltig fördelning för nämnd med {nämndstorlek} platser ({target_year}):")
    total_utdelade = 0
    for kartell, mandat in sorted(slutresultat.items(), key=lambda x: x[1], reverse=True):
        if mandat > 0:
            print(f" - {fix_text(str(kartell))}: {mandat} mandat")
            total_utdelade += mandat
            
    print(f"\nTotalt utdelade mandat: {total_utdelade} av {nämndstorlek}")
    
    # 5. Spara eventuellt ut loggen
    # log_df.to_excel(f"dhondt_logg_{target_year}.xlsx", index=False)
    print("\nBeräkning klar! Tips: Du kan föra in dessa siffror direkt i HTML-verktyget för presentation.")