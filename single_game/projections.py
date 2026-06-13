import pandas as pd
import numpy as np
import requests
import math

# ==========================================
# PHASE 1: LIVE API ODDS INGESTION
# ==========================================
def fetch_live_market_odds(api_key, sport="soccer_fifa_world_cup", regions="eu"):
    """
    Dynamically pulls live moneyline and over/under odds from The-Odds-API.
    Falls back to safe default tournament projections if the API limits are hit.
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None # Pipeline will handle None by reverting to default UI state safely


# ==========================================
# PHASE 2 & 3: HISTORICAL SHARES & BOTTLENECK ADJUSTMENTS
# ==========================================
def clean_position(pos_val):
    p = str(pos_val).upper().strip()
    if p in ['GK', 'GOALKEEPER', 'G']: return 'GK'
    if p in ['DEF', 'DF', 'DEFENDER', 'D']: return 'DEF'
    if p in ['MID', 'MD', 'MIDFIELDER', 'M']: return 'MID'
    if p in ['FWD', 'FW', 'FORWARD', 'ATTACKER', 'STRIKER', 'F']: return 'FWD'
    return p

def compile_base_probabilities(df, match_odds):
    """
    Combines historical rolling player xG/xA per 90 with opponent 
    positional defensive vulnerabilities.
    """
    df = df.copy()
    df['Position'] = df['Position'].apply(clean_position)
    
    # Use real historical statistics if present; otherwise fallback gracefully to scaled prices
    if 'Hist_xG_per90' not in df.columns: df['Hist_xG_per90'] = pd.to_numeric(df['Price'], errors='coerce').fillna(4.5) * 0.02
    if 'Hist_xA_per90' not in df.columns: df['Hist_xA_per90'] = pd.to_numeric(df['Price'], errors='coerce').fillna(4.5) * 0.015
    if 'Hist_xMin' not in df.columns: df['Hist_xMin'] = 75.0

    team_col = 'Club' if 'Club' in df.columns else 'Team'
    df['Normalized_Team'] = df[team_col].astype(str).str.strip().str.upper()

    # Opponent defensive bottleneck vectors (e.g., Team X concedes heavily down the flanks)
    # Default = 1.0 (neutral). A value of 1.25 means the opponent allows 25% more production to that position.
    opp_vulnerability = {
        'QAT': {'DEF': 1.25, 'MID': 1.10, 'FWD': 1.05, 'GK': 1.0},
        'SUI': {'DEF': 0.85, 'MID': 0.90, 'FWD': 0.80, 'GK': 0.95}
    }

    # Calculate squad-level aggregate historical expected stats to build market distribution weights
    team_totals = df.groupby('Normalized_Team')[['Hist_xG_per90', 'Hist_xA_per90']].sum().to_dict('index')

    player_profiles = []

    for index, row in df.iterrows():
        team = row['Normalized_Team']
        pos = row['Position']
        
        if team not in match_odds:
            continue
            
        opp = [t for t in match_odds.keys() if t != team][0]
        vuln_factor = opp_vulnerability.get(opp, {}).get(pos, 1.0)
        
        # Calculate raw team share weights based on historical baseline records
        t_totals = team_totals.get(team, {'Hist_xG_per90': 1.0, 'Hist_xA_per90': 1.0})
        xg_share = (row['Hist_xG_per90'] / max(0.01, t_totals['Hist_xG_per90'])) * vuln_factor
        xa_share = (row['Hist_xA_per90'] / max(0.01, t_totals['Hist_xA_per90'])) * vuln_factor
        
        player_profiles.append({
            'Name': row['Name'],
            'Team': team,
            'Position': pos,
            'Price': row['Price'],
            'xMin': float(row['Hist_xMin']),
            'Base_xG_Share': xg_share,
            'Base_xA_Share': xa_share
        })
        
    return player_profiles


# ==========================================
# PHASE 4: MONTE CARLO SIMULATION ENGINE
# ==========================================
def run_monte_carlo_simulation(player_profiles, match_odds, simulations=10000, target_percentile=90):
    """
    Simulates the entire match script 10,000 times using paired Poisson distributions.
    Extracts the elite 'ceiling' outcome profiles to build tournament winning lineups.
    """
    teams = list(match_odds.keys())
    team_a, team_b = teams[0], teams[1]
    
    # Arrays to collect simulation outputs across all runs
    sim_results = {p['Name']: np.zeros(simulations) for p in player_profiles}
    
    for sim in range(simulations):
        # 1. Generate random true game script goal tallies via Poisson distributions
        goals_a = np.random.poisson(match_odds[team_a]['xG'])
        goals_b = np.random.poisson(match_odds[team_b]['xG'])
        
        # Determine match state outcome
        cs_a = (goals_b == 0)
        cs_b = (goals_a == 0)
        
        # 2. Iterate through players and score individual match events dynamically
        for p in player_profiles:
            pts = 0.0
            xMin_factor = p['xMin'] / 90.0
            
            # Appearance allocation logic
            if p['xMin'] >= 60: pts += 2.0
            elif p['xMin'] > 0: pts += 1.0
            else: continue
            
            # Team specific context matching
            is_team_a = (p['Team'] == team_a)
            my_team_goals = goals_a if is_team_a else goals_b
            opp_team_goals = goals_b if is_team_a else goals_a
            has_cs = cs_a if is_team_a else cs_b
            
            # Match outcome bonus vectors
            if my_team_goals > opp_team_goals: pts += (0.3 * xMin_factor)
            elif my_team_goals < opp_team_goals: pts -= (0.3 * xMin_factor)
            
            # Clean Sheet scoring maps
            if has_cs and p['xMin'] >= 60:
                if p['Position'] in ['GK', 'DEF']: pts += 4.0
                elif p['Position'] == 'MID': pts += 1.0
            elif p['Position'] in ['GK', 'DEF'] and p['xMin'] >= 60:
                # Goal conceding penalties (-1 for every 2 goals conceded after the first)
                if opp_team_goals >= 2:
                    pts -= math.floor(opp_team_goals / 2)

            # 3. Simulate Event Multipliers (Goals and Assists)
            if my_team_goals > 0:
                # Probability scaling factor for individual distribution assignments
                sim_goals = np.random.binomial(my_team_goals, min(1.0, p['Base_xG_Share'] * xMin_factor))
                sim_assists = np.random.binomial(max(0, my_team_goals - sim_goals), min(1.0, p['Base_xA_Share'] * xMin_factor))
                
                goal_value = {'FWD': 4, 'MID': 5, 'DEF': 6, 'GK': 10}.get(p['Position'], 4)
                pts += (sim_goals * goal_value)
                pts += (sim_assists * 3.0)
                
            # Peripheral volume projections (Shots on Target / Saves)
            team_sot = match_odds[p['Team']]['Team_xSoT']
            sim_sot = np.random.binomial(np.random.poisson(team_sot), min(0.3, 0.05 * xMin_factor))
            sot_val = {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6}.get(p['Position'], 0.0)
            pts += (sim_sot * sot_val)
            
            if p['Position'] == 'GK':
                opp_sot = match_odds[team_b if is_team_a else team_a]['Team_xSoT']
                sim_saves = max(0, np.random.poisson(opp_sot) - my_team_goals)
                pts += (sim_saves * 0.5)

            sim_results[p['Name']][sim] = max(0.0, pts)
            
    # 4. Collapse all 10,000 array iterations down into the specified percentile projection
    compiled_projections = []
    for p in player_profiles:
        percentile_score = np.percentile(sim_results[p['Name']], target_percentile)
        compiled_projections.append({
            'Name': p['Name'],
            'Team': p['Team'],
            'Position': p['Position'],
            'Price': p['Price'],
            'xPts': round(percentile_score, 2)
        })
        
    return pd.DataFrame(compiled_projections).sort_values(by='xPts', ascending=False)

# ==========================================
# MASTER RUNTIME INTEGRATION ENTRY POINT
# ==========================================
def calculate_projections(df, match_odds):
    """
    Main pipeline handler mapping clean historical frameworks 
    and feeding the Monte Carlo simulation logic.
    """
    # 1. Build and clean historical profiles
    profiles = compile_base_probabilities(df, match_odds)
    
    # 2. Run simulation tracking elite 90th-percentile tournament upside floors
    final_projections_df = run_monte_carlo_simulation(profiles, match_odds, simulations=10000, target_percentile=90)
    
    return final_projections_df