import pandas as pd

# The file you referenced verbatim
filename = "1121390_players_20260615101833.csv"

try:
    df = pd.read_csv(filename)
    print("\n--- FANTEAM CSV HEADERS FOUND ---")
    print(df.columns.tolist())
    print("---------------------------------\n")
except FileNotFoundError:
    print(f"Error: Could not find the file {filename} in this folder.")
except Exception as e:
    print(f"Error reading the CSV: {e}")