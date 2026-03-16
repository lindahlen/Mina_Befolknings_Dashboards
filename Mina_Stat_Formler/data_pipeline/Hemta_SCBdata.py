import os
import sys
import requests
import pandas as pd

# ==========================================
# 1. GENERELL SETUP (Gyllene Regeln)
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass 

# ==========================================
# 2. DATAHANTERING & ENCODING FIX
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
# 3. HÄMTA DATA FRÅN SCB API (SJÄLVLÄKANDE OCH DYNAMISK)
# ==========================================
def fetch_scb_employment_linkoping():
    print("Steg 1: Hämtar metadata över sysselsatta i Linköping från SCB...")
    
    # UPPDATERAD URL: SCB har flyttat datan till AM0207Z (Ny tidsserie)
    url = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0207/AM0207Z/DagSektAldKN"
    
    # --- 1. LÄS METADATA FÖR ATT HITTA RÄTT KODER ---
    meta_response = requests.get(url)
    if meta_response.status_code != 200:
        print(f"Kunde inte hämta metadata. HTTP {meta_response.status_code}")
        print("SCB svarade:", meta_response.text)
        return None
        
    metadata = meta_response.json()
    query_params = []
    
    print("Steg 2: Bygger dynamisk API-fråga baserat på aktuell metadata...")
    # Skanna metadata för att dynamiskt välja de koder som fungerar idag
    for var in metadata.get('variables', []):
        code = var['code']
        
        if code == 'Region':
            query_params.append({"code": code, "selection": {"filter": "item", "values": ["0580"]}}) # 0580 = Linköping
            
        elif code == 'Alder':
            # Vi föredrar en stor klumpsumma för att undvika dubbelräkning
            vals = var['values']
            if '15-74' in vals:
                selected = ['15-74']
            elif '16-74' in vals:
                selected = ['16-74']
            elif 'tot' in [str(v).lower() for v in vals]:
                selected = [v for v in vals if 'tot' in str(v).lower()]
            else:
                selected = vals # Annars tar vi alla åldrar
            query_params.append({"code": code, "selection": {"filter": "item", "values": selected}})
            
        elif code == 'Kon':
            vals = var['values']
            if '1+2' in vals:
                selected = ['1+2']
            else:
                selected = vals
            query_params.append({"code": code, "selection": {"filter": "item", "values": selected}})
            
        elif code == 'Tid':
            # Om vi hoppar över 'Tid' i queryn returnerar SCB oftast alla tillgängliga år automatiskt,
            # men för att vara helt säkra skickar vi med alla år som finns.
            query_params.append({"code": code, "selection": {"filter": "item", "values": var['values']}})
            
        else:
            # För alla övriga filter (t.ex. 'ArbetsstSekt', 'ContentsCode' etc) som SCB kräver,
            # väljer vi helt enkelt ALLA tillgängliga alternativ så vi inte missar någon data.
            query_params.append({"code": code, "selection": {"filter": "item", "values": var['values']}})

    # --- 2. BYGG DYNAMISK JSON-QUERY ---
    query = {
      "query": query_params,
      "response": {
        "format": "json"
      }
    }

    # --- 3. SKICKA POST-BEGÄRAN ---
    print("Steg 3: Laddar ner historisk data från SCB...")
    response = requests.post(url, json=query)
    
    if response.status_code == 200:
        data = response.json()
        
        # Läs av kolumnnamnen dynamiskt från svaret
        columns = [col['code'] for col in data['columns']]
        
        records = []
        for item in data['data']:
            row_data = item['key'] + item['values']
            row_dict = dict(zip(columns, row_data))
            records.append(row_dict)
            
        df = pd.DataFrame(records)
        
        # Byt namn på tids- och värdekolumnerna till något logiskt
        if 'Tid' in df.columns:
            df.rename(columns={'Tid': 'År'}, inplace=True)
            
        # Hitta kolumnen som innehåller den faktiska datan (troligtvis slutar den på något kryptiskt som 'DagBef')
        value_cols = [c for c in df.columns if c not in ['Region', 'Alder', 'Kon', 'År', 'ArbetsstSekt']]
        if value_cols:
            df.rename(columns={value_cols[0]: 'Sysselsatta'}, inplace=True)
            
        # Städa datan: Hantera prickar (..) som 0 och gör till siffror
        if 'Sysselsatta' in df.columns:
            df['Sysselsatta'] = pd.to_numeric(df['Sysselsatta'].replace('..', '0'), errors='coerce').fillna(0).astype(int)
        df['År'] = pd.to_numeric(df['År'], errors='coerce')
        
        # Summera allt per år (summera alla åldrar, kön och sektorer till en totalsiffra för dagbefolkningen)
        df_total = df.groupby("År")["Sysselsatta"].sum().reset_index()
        
        # Sortera kronologiskt
        df_total = df_total.sort_values(by="År")
        
        print(f"\nData hämtad framgångsrikt! Antal unika år: {len(df_total)}")
        print("\nHistorisk utveckling i Linköping:")
        print(df_total.to_string(index=False))
        
        # Spara ner filen för visualisering och scenarier
        output_file = "sysselsatta_linkoping_historik.csv"
        df_total.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\nSparade data till: {output_file}")
        
        return df_total
    else:
        print(f"\nFel vid API-anrop: HTTP {response.status_code}")
        try:
            print("Detaljer från SCB:", response.text)
        except:
            print("Ett oväntat fel uppstod.")
        return None

if __name__ == "__main__":
    df = fetch_scb_employment_linkoping()