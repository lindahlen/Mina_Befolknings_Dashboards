import os
import sys
import pandas as pd

# ==========================================
# 1. Gyllene Regel: Sätt arbetskatalog
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    print(f"Arbetskatalog satt till: {current_folder}")
except NameError:
    print("Körs interaktivt, säkerställ att VS Code har mappen öppen.")
    current_folder = os.getcwd()

# ==========================================
# 2. Sökvägar & Mappstruktur
# ==========================================
parent_folder = os.path.abspath(os.path.join(current_folder, ".."))
file_name = "underlag för analys av divisionsvandringar.xlsx"
file_path = os.path.join(parent_folder, "excel_filer", file_name)

export_folder = os.path.join(parent_folder, "utdata_export")
export_csv_path = os.path.join(export_folder, "rensad_laglista.csv")
html_overview_path = os.path.join(parent_folder, "divisionsvandringar_oversikt.html")

# ==========================================
# 3. Konfiguration för Analys & QA (Data Quality)
# ==========================================
# Fyll i dessa när du har bestämt vilka kolumner som ska användas!
# Tills dessa är ifyllda kommer koden köras i "Basic"-läge.
ANALYS_KOLUMNER = {
    'lag': None,          # Byt ut None mot t.ex. 'Lag'
    'sasong': None,       # Byt ut None mot t.ex. 'Säsong' (Bör vara årtal, t.ex. 2023)
    'niva': None,         # Byt ut None mot t.ex. 'Divisionsnivå' (Numerisk: 1=Högst, 5=Lägst)
    'pagar': None,        # Byt ut None mot t.ex. 'Pågående_säsong' (Boolean eller specifik sträng)
    'lagsta_nivan': 5     # Ange vad som är den lägsta divisionen (för att ignorera drop-outs därifrån)
}

# Textfix-funktion (enligt Master Config v2.0)
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
# 4. Analys-funktioner (Ramverk för framtiden)
# ==========================================
def kor_qa_analyser(df):
    """
    Körs endast när kolumnerna i ANALYS_KOLUMNER har definierats.
    Returnerar HTML-kodsblock med resultaten för QA-översikten.
    """
    qa_html = "<h2>Analys & Logikkontroller (QA)</h2>"
    
    # Kolla om användaren har matat in kolumnnamn
    if not all([ANALYS_KOLUMNER['lag'], ANALYS_KOLUMNER['sasong'], ANALYS_KOLUMNER['niva']]):
        qa_html += "<p><em>Väntar på att kolumnnamn ska definieras i koden (ANALYS_KOLUMNER) för att köra logikkontroller (ologiska hopp, försvunna lag etc.).</em></p>"
        return qa_html
        
    # Här kommer logiken ligga när kolumnerna är satta. Exempel på struktur:
    lag_col = ANALYS_KOLUMNER['lag']
    sasong_col = ANALYS_KOLUMNER['sasong']
    niva_col = ANALYS_KOLUMNER['niva']
    
    qa_html += f"<p>Kör QA-analys på kolumnerna: <strong>{lag_col}</strong>, <strong>{sasong_col}</strong>, <strong>{niva_col}</strong>.</p>"
    
    # TODO 1: Ologiska hopp (t.ex. hoppar över en division)
    qa_html += "<h3>⚠️ Ologiska divisionshopp (Mer än 1 nivå/år)</h3>"
    qa_html += "<p><em>Funktion förberedd: Beräknar |Nivå(år N) - Nivå(år N+1)| > 1</em></p>"
    
    # TODO 2: Försvunna lag (exklusive nedflyttning från lägsta serien)
    qa_html += "<h3>👻 Lag som oförklarligt försvunnit</h3>"
    qa_html += f"<p><em>Funktion förberedd: Letar efter lag som spelade år N, men saknas år N+1 (och var inte i Div {ANALYS_KOLUMNER['lagsta_nivan']} år N).</em></p>"

    # TODO 3: Återkomster
    qa_html += "<h3>🔄 Lag som försvunnit och återuppstått</h3>"
    qa_html += "<p><em>Funktion förberedd: Identifierar glapp i säsonger för samma lag.</em></p>"
    
    # TODO 4: Prognos inför nästa år (Sista fullständiga året)
    qa_html += "<h3>📈 Prognos: Lag som 'borde' finnas kvar nästa säsong</h3>"
    qa_html += "<p><em>Funktion förberedd: Utgår från sista kompletta året och räknar fram förväntat deltagande exkl. nedflyttning från lägsta nivån.</em></p>"

    return qa_html

# ==========================================
# 5. Huvudprocess
# ==========================================
def main():
    if not os.path.exists(file_path):
        print(f"FEL: Kunde fortfarande inte hitta filen på sökvägen:\n{os.path.abspath(file_path)}")
        return

    try:
        print(f"Hittade filen! Läser in {file_name}...")
        df = pd.read_excel(file_path, sheet_name="Laglista") 
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(fix_text)

        if not os.path.exists(export_folder):
            os.makedirs(export_folder)
            
        df.to_csv(export_csv_path, index=False, encoding='utf-8-sig')
        
        # Kör logikkontroller (returnerar platshållare tills kolumner är valda)
        qa_sektion_html = kor_qa_analyser(df)
        
        # Skapa HTML-översikt
        html_content = f"""
        <!DOCTYPE html>
        <html lang="sv">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Översikt: Divisionsvandringar</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #2980b9; margin-top: 30px; }}
                h3 {{ color: #e67e22; margin-bottom: 5px; }}
                .summary {{ background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .qa-box {{ background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 40px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; font-size: 14px; }}
                th {{ background-color: #3498db; color: white; position: sticky; top: 0; }}
                tr:hover {{ background-color: #f1f1f1; }}
            </style>
        </head>
        <body>
            <h1>Datasammanställning: Divisionsvandringar</h1>
            
            <div class="summary">
                <p><strong>Totalt antal rader (lag/säsonger):</strong> {len(df)}</p>
                <p><strong>Antal kolumner:</strong> {len(df.columns)}</p>
                <p><strong>Tillgängliga kolumner:</strong> {', '.join(df.columns)}</p>
            </div>
            
            <div class="qa-box">
                {qa_sektion_html}
            </div>

            <h2>Förhandsgranskning av data (första 100 raderna)</h2>
            {df.head(100).to_html(index=False, classes='data-table', border=0)}
        </body>
        </html>
        """
        
        with open(html_overview_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"Bearbetning klar! Öppna: {html_overview_path} för att se din nya layout.")

    except Exception as e:
        print(f"ETT FEL UPPSTOD VID BEARBETNINGEN: {e}")

if __name__ == "__main__":
    main()