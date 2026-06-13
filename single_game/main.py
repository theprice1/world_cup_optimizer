import os
import glob
import sys
import pandas as pd
from projections import load_and_clean_data, calculate_projections
from optimizer import run_optimization

def get_latest_csv():
    """Finds and returns the most recently modified player CSV file in the current folder."""
    csv_files = glob.glob("*.csv")
    
    # Filter out our own optimizer output files so it doesn't read them by mistake
    csv_files = [f for f in csv_files if "optimal_lineup" not in f and "optimal_10_lineups" not in f]
    
    if not csv_files:
        raise FileNotFoundError("No input CSV files found in the directory.")
        
    # Get the file with the most recent creation/modification time
    latest_file = max(csv_files, key=os.path.getctime)
    return latest_file

def main():
    # -----------------------------------------------------------------
    # 1. FILE SELECTION
    # -----------------------------------------------------------------
    if len(sys.argv) > 1:
        # If a file was passed in the terminal (e.g., python main.py old_game.csv)
        target_csv = sys.argv[1]
    else:
        # If no file was passed, automatically grab the newest one
        print("No filename provided in terminal. Auto-detecting the newest CSV...")
        try:
            target_csv = get_latest_csv()
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    print(f"Loading data from {target_csv}...")
    
    # -----------------------------------------------------------------
    # 2. LOAD & CLEAN DATA
    # -----------------------------------------------------------------
    raw_df = load_and_clean_data(target_csv)
    
    # -----------------------------------------------------------------
    # 3. GENERATE FANTEAM-SPECIFIC PROJECTIONS
    # -----------------------------------------------------------------
    print("Calculating player projections (including 90-min, SoT, Save, and Impact rules)...")
    projected_df = calculate_projections(raw_df)
    
    # -----------------------------------------------------------------
    # 4. DEFINE LINEUP CONFIGURATIONS & STACKS
    # -----------------------------------------------------------------
    # Change total lineups here (e.g., 20, 50, 150)
    TOTAL_LINEUPS = 5 
    
    # Maximum allowed identical players between any two lineups (Max 4 out of 5)
    # Set to 3 for much more diversified lineups, leave at 4 to build around a tight "core"
    MAX_OVERLAP = 4 
    
    # STACKING RULE OPTIONS:
    # Option A: Let the mathematical projections build the absolute highest-upside builds
    #           (Defaults to FanTeam's built-in cap of max 3 players per team)
    my_stack_rule = None
    
    # Option B: Force a specific game script (e.g., Exactly 3 South Korea, 2 Czech Republic)
    # To use this, uncomment the line below:
    my_stack_rule = {'MEX': 4, 'ZAF': 1}
    
    # -----------------------------------------------------------------
    # 5. RUN LINEUP OPTIMIZATION LOOP
    # -----------------------------------------------------------------
    print(f"Running linear programming optimizer to generate {TOTAL_LINEUPS} unique lineups...")
    optimal_squads = run_optimization(
        projected_df, 
        budget=59.0, 
        num_lineups=TOTAL_LINEUPS, 
        max_overlap=MAX_OVERLAP, 
        stack_rule=my_stack_rule
    )
    
    if optimal_squads.empty:
        print("❌ Critical Error: Optimizer could not build any valid lineups with current constraints.")
        sys.exit(1)
        
    # -----------------------------------------------------------------
    # 6. FORMAT & CALCULATE CAPTAINCY METRICS
    # -----------------------------------------------------------------
    display_df = optimal_squads[['Lineup_Num', 'Name', 'Club', 'Position', 'Price', 'xPts', 'Is_Captain']].copy()
    
    # Apply FanTeam's 1.5x Captain Multiplier
    display_df['Final_xPts'] = display_df.apply(
        lambda r: r['xPts'] * 1.5 if r['Is_Captain'] else r['xPts'], axis=1
    )
    
    # -----------------------------------------------------------------
    # 7. PRINT TERMINAL DISPLAY SUMMARY
    # -----------------------------------------------------------------
    print("\n" + "="*60)
    print("🎯 MULTI-LINEUP GENERATION SUMMARY")
    print("="*60)
    
    # Loop through and print a clean breakdown of each generated lineup
    for lu_num in range(1, display_df['Lineup_Num'].max() + 1):
        lu_filter = display_df[display_df['Lineup_Num'] == lu_num]
        
        total_price = lu_filter['Price'].sum()
        total_xpts = lu_filter['Final_xPts'].sum()
        
        print(f"\n▶️ LINEUP #{lu_num} | Projected Points: {total_xpts:.2f} xPts | Budget: {total_price:.1f}M / 59.0M")
        print("-" * 60)
        print(lu_filter[['Name', 'Club', 'Position', 'Price', 'Final_xPts', 'Is_Captain']].to_string(index=False))
        print("-" * 60)
        
    # -----------------------------------------------------------------
    # 8. SAVE PORTFOLIO TO CSV
    # -----------------------------------------------------------------
    # Automatically extracts the distinct unique prefix from your input CSV
    file_id = target_csv.split('_')[0]
    output_filename = f"optimal_{TOTAL_LINEUPS}_lineups_{file_id}.csv"
    
    display_df.to_csv(output_filename, index=False)
    print(f"\n✅ Success! All {TOTAL_LINEUPS} optimized lineups saved to '{output_filename}'")

if __name__ == "__main__":
    main()