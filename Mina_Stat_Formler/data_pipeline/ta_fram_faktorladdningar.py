import os
import sys
import pandas as pd
import numpy as np

print("🚀 STARTAR SKRIPTET: Hämtar receptet (faktorladdningarna) för Linköpings PCA...")

# --- 1. SÄKERSTÄLL SÖKVÄG ---
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass

parent_folder = os.path.dirname(current_folder)
file_base = os.path.join(parent_folder, "segregation_base.csv")

# --- 2. LÄS IN GRUNDDATAN ---
print(f"   Läser in data från: {file_base}")
df_base = pd.read_csv(file_base, encoding='utf-8')
if len(df_base.columns) < 5:
    df_base = pd.read_csv(file_base, encoding='utf-8', sep=';')

senaste_aret = df_base['tid'].max()
df_year = df_base[df_base['tid'] == senaste_aret].copy()
# Gör alla kolumnnamn till gemener för enklare hantering
df_year.columns = df_year.columns.str.strip().str.lower()

# ==========================================
# 2.5 FILTRERA OMRÅDEN (Exakt kopia från huvudskriptet)
# ==========================================
print("   Filtrerar områden för att matcha den exakta PCA-rymden...")
mask = (df_year['basområde'].str.strip() != 'Hela kommunen')

if 'inkluderad' in df_year.columns:
    mask = mask & (pd.to_numeric(df_year['inkluderad'], errors='coerce') == 1)

# Lista på områden som SKA vara med
force_include = ['alsätter västra', 'universitetsområdet', 'stångebro östra']

if 'områdestyp' in df_year.columns:
    basomrade_lower = df_year['basområde'].astype(str).str.strip().str.lower()
    
    # Identifiera student/verksamhetsområden (ignorera skiftläge)
    typ_lower = df_year['områdestyp'].astype(str).str.strip().str.lower()
    not_student_verk = ~typ_lower.isin(['studentområde', 'verksamhetsområde'])
    
    # Tillämpa tvingande inkludering
    is_force_included = basomrade_lower.isin(force_include)
    
    mask = mask & (not_student_verk | is_force_included)

df_calc = df_year[mask].copy()
print(f"   Data filtrerad: Analyserar {len(df_calc)} områden (inklusive specialområden).")

# --- 3. DINA 22 VARIABLER (DYNAMISK SÖKNING) ---
core_keywords = [
    "långvarigt ekonomiskt bistånd", "inskrivna arbetslösa", "ej självförsörjande",
    "ekonomiskt bistånd totalt", "trångbodda hushåll", "ohälsotal 50-64",
    "låg ekonomisk standard", "uvas", "hyresrätt", "små bostäder", "kvm per person", "bilinnehav",
    "förgymnasial utbildning", "kvarboende minst tre", "lång eftergymnasial utbildning",
    "utrikes födda", "ensamstående", "nettoinkomst",
    # De fyra nya tilläggen:
    "barnfattigdom", "sysselsättningsgrad", "6-15", "80+"
]

pca_columns = []
for keyword in core_keywords:
    for col in df_calc.columns:
        col_lower = col.lower()
        if keyword.lower() in col_lower:
            # Samma filter som i huvudskriptet för att ta bort kön, antal och dubbletter
            if any(excl in col_lower for excl in ['index:', ' män', 'kvinnor', 'antal']): continue
            if keyword == "hyresrätt" and "rätter" in col_lower: continue
            if keyword == "ensamstående" and col_lower.startswith("hushåll ensam"): continue
            if keyword == "nettoinkomst" and ('%' in col_lower or 'andel' in col_lower): continue
            
            if col not in pca_columns: 
                pca_columns.append(col)

print(f"   Hittade exakt {len(pca_columns)} variabler för att skapa receptet. Rensar matrisen...")
X = df_calc[pca_columns].apply(pd.to_numeric, errors='coerce').fillna(0)

# --- 4. MATEMATIKEN ---
print("   Kör den matematiska motorn (PCA)...")
X_mean = np.mean(X.values, axis=0)
X_std = np.std(X.values, axis=0)
X_std[X_std == 0] = 1.0
X_scaled = (X.values - X_mean) / X_std

cov_matrix = np.cov(X_scaled, rowvar=False)
eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

sorted_indices = np.argsort(eigenvalues)[::-1]
eigenvectors = eigenvectors[:, sorted_indices]

# --- 5. RECEPTET ---
print("   Skapar recept-tabellen...")
loadings = eigenvectors[:, :3]
df_loadings = pd.DataFrame(loadings, columns=['Faktor_1', 'Faktor_2', 'Faktor_3'], index=pca_columns).round(3)

# ==========================================
# SKRIV UT RESULTATET DIREKT I TERMINALEN
# ==========================================
print("\n" + "="*50)
print(f"🏆 RECEPT FÖR FAKTOR 3 (År {senaste_aret})")
print("="*50)
print("\n🔹 DRAR UPPÅT (De starkaste positiva drivkrafterna):")
print(df_loadings['Faktor_3'].sort_values(ascending=False).head(4))

print("\n🔻 DRAR NEDÅT (De starkaste negativa drivkrafterna):")
print(df_loadings['Faktor_3'].sort_values(ascending=False).tail(4))
print("="*50 + "\n")

# Spara som CSV istället för Excel
output_file = os.path.join(parent_folder, f"PCA_Recept_{senaste_aret}.csv")
try:
    df_loadings.to_csv(output_file, sep=';', decimal=',')
    print(f"💾 Hela listan är sparad som CSV i: {output_file}")
except Exception as e:
    print(f"Kunde inte spara filen: {e}")