import os
# --- ANTI-FRYS LÅS (Måste ligga före Scikit-Learn!) ---
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass

print("\n🔍 Startar fristående Faktoranalys (PCA)...")

# 1. LÄS IN DEN FÄRDIGTVÄTTADE DATABASEN
parent_folder = os.path.dirname(current_folder)
input_file = os.path.join(parent_folder, "segregation_base.csv") 
print(f"   Läser in data från: {input_file}")
df = pd.read_csv(input_file, encoding='utf-8')

# 2. IDENTIFIERA OCH EXKLUDERA DET SISTA ÅRET
years = sorted(df['tid'].dropna().unique(), reverse=True)
latest_year = years[0]
df_pca = df[df['tid'] < latest_year].copy()
print(f"   Exkluderar {latest_year} (ofullständig data). Analyserar {years[1]} till {years[-1]}.")

# ==========================================
# 3. IDENTIFIERA DE 22 STABILA VARIABLERNA
# ==========================================
core_keywords = [
    "långvarigt ekonomiskt bistånd", "inskrivna arbetslösa", "ej självförsörjande", 
    "ekonomiskt bistånd totalt", "trångbodda hushåll", "ohälsotal 50-64", 
    "låg ekonomisk standard", "uvas", "hyresrätt", "små bostäder", "kvm per person", "bilinnehav", 
    "förgymnasial utbildning", "kvarboende minst tre", "lång eftergymnasial utbildning", 
    "utrikes födda", "ensamstående", "nettoinkomst",
    "barnfattigdom", "sysselsättningsgrad", "6-15", "80+"
]

# --- FELSÖKNING: LÅSTA INDIKATORER ---
locked_keywords = []

pca_columns = []
for keyword in core_keywords:
    if keyword in locked_keywords:
        continue
        
    for col in df_pca.columns:
        col_lower = col.lower()
        if keyword.lower() in col_lower:
            if any(excl in col_lower for excl in ['index:', ' män', 'kvinnor', 'antal']): continue
            if keyword == "hyresrätt" and "rätter" in col_lower: continue
            if keyword == "ensamstående" and col_lower.startswith("hushåll ensam"): continue
            if keyword == "nettoinkomst" and ('%' in col_lower or 'andel' in col_lower): continue
            
            if col not in pca_columns: 
                pca_columns.append(col)

print(f"   Hittade exakt {len(pca_columns)} variabler för PCA. Dessa är:")
for c in pca_columns:
    print(f"      - {c}")

# ==========================================
# 4. FILTRERA UT BASOMRÅDEN (MED SPECIAL-INKLUDERING)
# ==========================================
mask = (df_pca['basområde'] != 'Hela kommunen')

if 'Inkluderad' in df_pca.columns:
    mask = mask & (pd.to_numeric(df_pca['Inkluderad'], errors='coerce') == 1)

# Lista på områden som SKA vara med, oavsett om de är märkta som Student/Verksamhetsområde
force_include = ['alsätter västra', 'universitetsområdet', 'stångebro östra']

if 'Områdestyp' in df_pca.columns:
    basomrade_lower = df_pca['basområde'].astype(str).str.strip().str.lower()
    
    # 1. Kolla vilka som INTE är student/verksamhet
    not_student_verk = ~df_pca['Områdestyp'].isin(['Studentområde', 'Verksamhetsområde'])
    
    # 2. Kolla vilka som ligger i vår speciallista
    is_force_included = basomrade_lower.isin(force_include)
    
    # 3. Behåll om de uppfyller villkor 1 ELLER villkor 2
    mask = mask & (not_student_verk | is_force_included)
    
df_calc = df_pca[mask].copy()
pca_results = pd.DataFrame()

# ==========================================
# 5. KÖR PCA ÅR FÖR ÅR (MED EXTREM DIAGNOSTIK)
# ==========================================
for year in sorted(df_calc['tid'].unique(), reverse=True):
    print(f"\n   [DIAGNOSTIK] ---> STARTAR ÅR {year} <---")
    
    df_year = df_calc[df_calc['tid'] == year].copy()
    print(f"      [DIAGNOSTIK] Filtrerat ut data: {len(df_year)} rader.")
    
    if len(df_year) < 5: 
        print(f"      [DIAGNOSTIK] För lite data för år {year}, hoppar över.")
        continue
    
    print(f"      [DIAGNOSTIK] Konverterar kolumner till numeriska värden...")
    X = df_year[pca_columns].apply(pd.to_numeric, errors='coerce').fillna(0)
    
    print(f"      [DIAGNOSTIK] Beräknar medelvärde och standardavvikelse...")
    X_mean = np.mean(X.values, axis=0)
    X_std = np.std(X.values, axis=0)
    X_std[X_std == 0] = 1.0 
    
    print(f"      [DIAGNOSTIK] Utför skalning...")
    X_scaled = (X.values - X_mean) / X_std
    
    print(f"      [DIAGNOSTIK] Startar matematikmotorn (Kovarians & Egenvärden)...")
    try:
        print(f"      [DIAGNOSTIK] 1. Skapar kovariansmatris (np.cov)...")
        cov_matrix = np.cov(X_scaled, rowvar=False)
        print(f"      [DIAGNOSTIK] -> Kovariansmatris skapad! (NaNs: {np.isnan(cov_matrix).any()})")
        
        print(f"      [DIAGNOSTIK] 2. Beräknar egenvärden (np.linalg.eigh)...")
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        print(f"      [DIAGNOSTIK] -> Egenvärden klara!")
        
        # 3. eigh sorterar i stigande ordning, vi vänder på det så största kommer först
        sorted_indices = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_indices]
        eigenvectors = eigenvectors[:, sorted_indices]
        
        # 4. Projicera Linköpingsdatan på de 3 viktigaste faktorerna
        U_pca = eigenvectors[:, :3]
        X_pca = np.dot(X_scaled, U_pca)
        
        print(f"      [DIAGNOSTIK] Matematikmotorn SLUTFÖRD framgångsrikt!")
    except Exception as e:
        print(f"      [DIAGNOSTIK] ETT FEL INTRÄFFADE: {e}")
        break
    
    print(f"      [DIAGNOSTIK] Beräknar faktorpoäng...")
    df_year['PCA_Faktor_1'] = np.round(X_pca[:, 0], 3)
    df_year['PCA_Faktor_2'] = np.round(X_pca[:, 1], 3)
    df_year['PCA_Faktor_3'] = np.round(X_pca[:, 2], 3)
    
    print(f"      [DIAGNOSTIK] Sparar resultat i internminnet...")
    cols_to_keep = ['basområde', 'tid', 'PCA_Faktor_1', 'PCA_Faktor_2', 'PCA_Faktor_3']
    pca_results = pd.concat([pca_results, df_year[cols_to_keep]], ignore_index=True)
    
    # Matematisk beräkning av förklaringsgraden
    total_var = np.sum(eigenvalues)
    explained_variance_ratio = eigenvalues / total_var
    print(f"   [DIAGNOSTIK] ---> ÅR {year} HELT KLAR (Förklaringsgrad Topp 3: {sum(explained_variance_ratio[:3])*100:.1f}%) <---")

# ==========================================
# 6. SPARA FRISTÅENDE DATABAS I MAPPEN OVANFÖR
# ==========================================
output_file = os.path.join(parent_folder, "pca_faktorer_linkoping.csv")
pca_results.to_csv(output_file, index=False, encoding='utf-8')

print(f"💾 KLART! Ny databas med faktorer sparad som: {output_file}")