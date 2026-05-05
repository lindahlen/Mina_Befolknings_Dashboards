import os
import pandas as pd
import json
import re

def extract_minutes(val):
    """Hjälpfunktion för att konvertera text som '1 h 10 min' eller '45 min' till rena minuter (int)"""
    if pd.isna(val): 
        return None
    val_str = str(val).lower()
    h = 0; m = 0
    h_match = re.search(r'(\d+)\s*h', val_str)
    m_match = re.search(r'(\d+)\s*m', val_str)
    if h_match: h = int(h_match.group(1))
    if m_match: m = int(m_match.group(1))
    if h == 0 and m == 0:
        nums = re.findall(r'\d+', val_str)
        if nums: return int(nums[0])
        return None
    return (h * 60) + m

def main():
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    ut_mapp = os.path.abspath(os.path.join(os.getcwd(), '..'))

    hist_path_sub1 = os.path.join('excel_filer', 'sysselsättningsprognos_historisk_data.xlsx')
    hist_path_sub2 = os.path.join('excel-filer', 'sysselsättningsprognos_historisk_data.xlsx')
    hist_path_root = 'sysselsättningsprognos_historisk_data.xlsx'
    
    if os.path.exists(hist_path_sub1): hist_path = hist_path_sub1
    elif os.path.exists(hist_path_sub2): hist_path = hist_path_sub2
    elif os.path.exists(hist_path_root): hist_path = hist_path_root
    else: hist_path = hist_path_sub1

    config_path = 'styrfil_syss_kalkylator.xlsx'

    # === LÄS IN HISTORISK DATA ===
    basdata = {}
    if os.path.exists(hist_path):
        try:
            xls_hist = pd.ExcelFile(hist_path)
            for sheet_name in xls_hist.sheet_names:
                df = pd.read_excel(xls_hist, sheet_name=sheet_name)
                df = df.replace(['-', '..', '.', ' ', '', '#SAKNAS!'], pd.NA)
                df = df.where(pd.notnull(df), None)
                basdata[sheet_name] = df.to_dict(orient='records')
            
            # NYTT FILNAMN HÄR: _2035.json
            output_basdata = os.path.join(ut_mapp, "syss_basdata_2035.json")
            with open(output_basdata, 'w', encoding='utf-8') as f:
                json.dump(basdata, f, ensure_ascii=False, indent=2)
            print(f" -> Sparade '{output_basdata}'")
        except Exception as e: print(f"FEL: {e}")

    # === LÄS IN STYRFIL ===
    configdata = {}
    if os.path.exists(config_path):
        try:
            xls_config = pd.ExcelFile(config_path)
            for sheet_name in xls_config.sheet_names:
                df = pd.read_excel(xls_config, sheet_name=sheet_name)
                if 'Stöd_manuell' in df.columns: df = df.drop(columns=['Stöd_manuell'])
                
                if sheet_name == 'Inom_en_timme':
                    if 'Bil_Tid' in df.columns: df['Bil_minuter'] = df['Bil_Tid'].apply(extract_minutes)
                    if 'Kollektivt_tid' in df.columns: df['Kollektivt_minuter'] = df['Kollektivt_tid'].apply(extract_minutes)
                
                df = df.replace(['-', '..', '.', ' ', '', '#SAKNAS!'], pd.NA)
                df = df.where(pd.notnull(df), None)
                configdata[sheet_name] = df.to_dict(orient='records')
            
            # NYTT FILNAMN HÄR: _2035.json
            output_config = os.path.join(ut_mapp, "syss_config_2035.json")
            with open(output_config, 'w', encoding='utf-8') as f:
                json.dump(configdata, f, ensure_ascii=False, indent=2)
            print(f" -> Sparade '{output_config}'")
        except Exception as e: print(f"FEL: {e}")

    print("\nKlart! Databaserna är sparade och redo för 2035-kalkylatorn.")

if __name__ == "__main__":
    main()