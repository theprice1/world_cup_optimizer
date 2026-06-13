import pandas as pd

def clean_position(pos_val):
    p = str(pos_val).upper().strip()
    if p in ['GK', 'GOALKEEPER', 'G']: return 'GK'
    if p in ['DEF', 'DF', 'DEFENDER', 'D']: return 'DEF'
    if p in ['MID', 'MD', 'MIDFIELDER', 'M']: return 'MID'
    if p in ['FWD', 'FW', 'FORWARD', 'ATTACKER', 'STRIKER', 'F']: return 'FWD'
    return p

def calculate_projections(df, match_odds):
    """
    Calculates dynamic player projections by distributing team-level odds 
    proportionally based on individual player price weights within their position.
    """
    df = df.copy()
    df['Position'] = df['Position'].apply(clean_position)
    
    # Ensure Price is numeric
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(4.5)
    
    # Create normalized team matching strings
    team_col = 'Club' if 'Club' in df.columns else 'Team'
    df['Normalized_Team'] = df[team_col].astype(str).str.strip().str.upper()
    
    # Step 1: Calculate total price weight for each position per team
    # This prevents division-by-zero and allows us to scale shares relative to cost
    group_salaries = df.groupby(['Normalized_Team', 'Position'])['Price'].sum().to_dict()

    projected_data = []

    for index, row in df.iterrows():
        team = row['Normalized_Team']
        pos = row['Position']
        price = row['Price']

        if team not in match_odds:
            row_dict = row.to_dict()
            row_dict['xPts'] = 0.0
            projected_data.append(row_dict)
            continue

        odds = match_odds[team]
        base_pts = 2.0 
        
        # Calculate individual weight within this team's positional group
        total_pos_salary = group_salaries.get((team, pos), price)
        # Fallback if group salary calculation encounters single-player edge cases
        price_weight = (price / total_pos_salary) if total_pos_salary > 0 else 1.0
        
        # 1. Clean Sheet Calculations (Flat per position group)
        if pos in ['GK', 'DEF']:
            base_pts += (4.0 * odds['CS_odds'])
        elif pos == 'MID':
            base_pts += (1.0 * odds['CS_odds'])
            
        # 2. Price-Weighted xG & xA Share Distribution
        pos_xG_share = {'FWD': 0.45, 'MID': 0.35, 'DEF': 0.18, 'GK': 0.02}.get(pos, 0)
        
        # Player gets a fraction of the position's share based on their price weight
        player_xG = odds['xG'] * pos_xG_share * price_weight * 2.0 # Scaled for typical squad depth
        player_xA = player_xG * 0.75 
        
        goal_pts = {'FWD': 4, 'MID': 5, 'DEF': 6, 'GK': 10}.get(pos, 0)
        base_pts += (player_xG * goal_pts)
        base_pts += (player_xA * 3.0)

        # 3. 90-Minute Appearance Probabilities (Slightly boosted for premium priced assets)
        base_prob = {'GK': 0.95, 'DEF': 0.90, 'MID': 0.65, 'FWD': 0.60}.get(pos, 0.5)
        prob_90_mins = min(0.95, base_prob * (1.0 + (price_weight * 0.1)))
        if pos in ['MID', 'FWD']:
            base_pts += (1.0 * prob_90_mins)

        # 4. Price-Weighted Shots on Target
        pos_sot_share = {'FWD': 0.50, 'MID': 0.35, 'DEF': 0.15, 'GK': 0.0}.get(pos, 0)
        player_xSoT = odds['Team_xSoT'] * pos_sot_share * price_weight * 2.0
        sot_multiplier = {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6, 'GK': 0.0}.get(pos, 0)
        base_pts += (player_xSoT * sot_multiplier)

        # 5. Goalkeeper Saves Math (Remains specific to GK position)
        if pos == 'GK':
            opp_team = [t for t in match_odds.keys() if t != team]
            opp_xG = match_odds[opp_team[0]]['xG'] if opp_team else 1.0
            xSaves = max(0, odds['Opp_xSoT'] - opp_xG) 
            base_pts += (xSaves * 0.5)

        # 6. Team Match Impact Points
        base_pts += ((odds['Win_prob'] * 0.3) - (odds['Loss_prob'] * 0.3))
        
        row_dict = row.to_dict()
        row_dict['xPts'] = round(base_pts, 2)
        projected_data.append(row_dict)

    projected_df = pd.DataFrame(projected_data)
    
    # Drop the temporary column before outputting
    if 'Normalized_Team' in projected_df.columns:
        projected_df = projected_df.drop(columns=['Normalized_Team'])
        
    if 'xPts' in projected_df.columns:
        projected_df = projected_df.sort_values(by='xPts', ascending=False)
        
    return projected_df