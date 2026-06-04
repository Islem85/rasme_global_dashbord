import pandas as pd
import sys

CSV = r"C:\Users\ISLEM AYARI\OneDrive - AFDB\Documents\RASME\RASME_Projects\Global dashbord\kobo_04052026.csv"

# No header in the CSV; load and inspect
df = pd.read_csv(CSV, header=None, on_bad_lines='skip', engine='python')
print("SHAPE:", df.shape)
print()
print("FIRST ROW (col index -> value sample, type, n_unique, %null):")
for i in range(df.shape[1]):
    col = df.iloc[:, i]
    sample = col.dropna().head(2).tolist()
    nun = col.nunique(dropna=True)
    pnull = round(col.isna().mean() * 100, 1)
    s = ", ".join(str(x)[:35] for x in sample)
    print(f"  c{i:>2}: nunique={nun:<6} %null={pnull:<5}  sample=[{s}]")
