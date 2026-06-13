import pandas as pd
import numpy as np
import math

def clean_position(pos_val):
    p = str(pos_val).upper().strip()
    if p in ['GK', 'GOALKEEPER', 'G']: return 'GK'
    if p in ['DEF', 'DF', 'DEFENDER', 'D']: return 'DEF'
    if p in ['MID', 'MD', 'MIDFIELDER', 'M']: return 'MID'
    if p in ['FWD', 'FW', 'FORWARD', 'ATTACKER', 'STRIKER', 'F']: return 'FWD'
    return p

def clean_tactical_role(role_val):
    r = str(role_val).upper().strip()
    if r in ['NAILED', 'STARTER', '90', 'FULL']: return 'NAILED'
    if r in ['VOLATILE', 'RISK', 'SUB_RISK', '60']: return 'VOLATILE'
    if r in ['SUB', 'IMPACT', 'BENCH', '25']: return 'IMPACT'
    return 'NAILED'  # Default safely to Nailed if column doesn't exist

def calculate_poisson_clean_sheet_decay(expected_conceded):
    """
    Uses a Poisson distribution to calculate exact probabilities for goals conceded
    to accurately score format-specific clean sheets and defensive penalties.
    """
    lam = max(0.05, expected_conceded)
    
    p0 = math.exp(-lam)                  # Concede 0 (Clean Sheet)
    p1 = (lam ** 1) * math.exp(-lam) / 1  # Concede 1
    p2 = (lam ** 2) * math.exp(-lam) / 2  # Concede 2
    p3 = (lam ** 3) * math.exp(-lam) / 6  # Concede 3
    p4_plus = max(0.0, 1.0 - (p0 + p1 + p2 + p3)) # Concede 4+
    
    # Expected FanTeam scoring impact: +4 for clean sheet, -1 for every 2 goals conceded after the first
    # Concede 0 = +4.0 pts
    # Concede 1 = 0.0 pts
    # Concede 2 = -1.0 pts
    # Concede 3 = -1.0 pts
    # Concede 4+ = -2.0 pts (approx baseline)
    expected_defensive_scoring = (p0 * 4.0) + (p1 * 0.0) + (p2 * -1.0) + (p3 * -1.0) + (p4_plus * -2.0)
    
    return p0, expected_defensive_scoring

def calculate_projections(df, match_odds):
    """
    Advanced Tier-4 Projection Engine featuring:
    - xMin Runtime Modeling
    - Anytime Market Decoupling
    - Poisson Conceded Goal Penalties
    - Positional Tactical Scaling
    """
    df = df.copy()
    df['Position'] = df['Position'].apply(clean_position)
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(4.5)
    
    team_col = 'Club' if 'Club' in df.columns else 'Team'
    df['Normalized_Team'] = df[team_col].astype(str).str.strip().str.upper()
    
    # Safely look for advanced columns, use intelligent statistical defaults if missing
    if 'Tactical_Role' not in df.columns:
        df['Tactical_Role'] = 'NAILED'
    df['Tactical_Role'] = df['Tactical_Role'].apply(clean_tactical_role)
    
    if 'Attacking_Tier' not in df.columns:
        # Default Fullbacks/Wingers higher, Center Backs lower if info missing
        df['Attacking_Tier'] = 2
    df['Attacking_Tier'] = pd.to_numeric(df['Attacking_Tier'], errors='coerce').fillna(2).astype(int)

    # Calculate Market Override values if provided
    df['Market_Scorer_Prob'] = 0.0
    if 'Anytime_Scorer_Odds' in df.columns:
        # Converts e.g., 2.50 decimal odds to 0.40 probability. Assumes decimals.
        df['Market_Scorer_Prob'] = 1.0 / pd.to_numeric(df['Anytime_Scorer_Odds'], errors='coerce').fillna(float('inf'))
        df['Market_Scorer_Prob'] = df['Market_Scorer_Prob'].fillna(0.0)

    # Step 1: Pre-calculate positional price pools to allocate unassigned xG/xA
    group_salaries = df.groupby(['Normalized_Team', 'Position'])['Price'].sum().to_dict()

    projected_data = []

    for index, row in df.iterrows():
        team = row['Normalized_Team']
        pos = row['Position']
        price = row['Price']
        role = row['Tactical_Role']
        tier = row['Attacking_Tier']
        market_xg = row['Market_Scorer_Prob']

        if team not in match_odds:
            row_dict = row.to_dict()
            row_dict['xPts'] = 0.0
            projected_data.append(row_dict)
            continue

        odds = match_odds[team]
        opp_team = [t for t in match_odds.keys() if t != team]
        opp_xG = match_odds[opp_team[0]]['xG'] if opp_team else 1.0

        # --- 1. EXPECTED MINUTES MODELING ---
        xMin = {'NAILED': 90.0, 'VOLATILE': 62.0, 'IMPACT': 25.0}.get(role, 90.0)
        min_factor = xMin / 90.0
        
        # Base Appearance Points
        base_pts = 0.0
        if xMin >= 60.0:
            base_pts += 2.0  # Played 60+ mins
        elif xMin > 0.0:
            base_pts += 1.0  # Played under 60 mins

        # Clean Sheet Eligibility Modifier
        cs_eligibility = 1.0 if xMin >= 60.0 else 0.0

        # --- 2. POISSON CLEAN SHEET DECAY ---
        # Find true defensive equity using actual probability distributions
        true_cs_prob, net_defensive_points = calculate_poisson_clean_sheet_decay(opp_xG)
        
        if pos in ['GK', 'DEF'] and cs_eligibility > 0:
            base_pts += net_defensive_points
        elif pos == 'MID' and cs_eligibility > 0:
            base_pts += (true_cs_prob * 1.0) # Midfielders get 1 pt for clean sheets, no negative scaling

        # --- 3. MARKET SCORER AND ATTACKING TIER INTELLIGENCE ---
        # Calculate individual shares
        total_pos_salary = group_salaries.get((team, pos), price)
        price_weight = (price / total_pos_salary) if total_pos_salary > 0 else 1.0
        
        # Modify price weight by tactical attacking tier profile
        # Tier 1 = Heavy attacking wingback/creative engine, Tier 3 = Defensive anchor
        tier_multiplier = {1: 1.5, 2: 1.0, 3: 0.5}.get(tier, 1.0)
        effective_weight = price_weight * tier_multiplier

        # Distribute Team xG
        if market_xg > 0:
            # Absolute override using raw bookmaker intelligence
            player_xG = market_xg * min_factor
        else:
            # Proportional modeling using modified tactical price distributions
            pos_xG_share = {'FWD': 0.45, 'MID': 0.35, 'DEF': 0.18, 'GK': 0.02}.get(pos, 0)
            player_xG = odds['xG'] * pos_xG_share * effective_weight * 2.0 * min_factor

        player_xA = player_xG * 0.75 * tier_multiplier # Scaled by creative profile

        # Apply scoring framework metrics
        goal_pts = {'FWD': 4, 'MID': 5, 'DEF': 6, 'GK': 10}.get(pos, 0)
        base_pts += (player_xG * goal_pts)
        base_pts += (player_xA * 3.0)

        # --- 4. ADVANCED SHOTS ON TARGET & SAVES ---
        pos_sot_share = {'FWD': 0.50, 'MID': 0.35, 'DEF': 0.15, 'GK': 0.0}.get(pos, 0)
        player_xSoT = odds['Team_xSoT'] * pos_sot_share * effective_weight * 2.0 * min_factor
        sot_multiplier = {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6, 'GK': 0.0}.get(pos, 0)
        base_pts += (player_xSoT * sot_multiplier)

        # Goalkeeper Saves Math (Calculates save volume from opponent raw shots on target)
        if pos == 'GK':
            xSaves = max(0.0, odds['Opp_xSoT'] - opp_xG) * min_factor
            base_pts += (xSaves * 0.5)

        # Team Impact bonus points (Winner/Loser bonuses scaled by game length)
        base_pts += (((odds['Win_prob'] * 0.3) - (odds['Loss_prob'] * 0.3)) * min_factor)
        
        row_dict = row.to_dict()
        row_dict['xPts'] = round(max(0.0, base_pts), 2)
        projected_data.append(row_dict)

    projected_df = pd.DataFrame(projected_data)
    if 'Normalized_Team' in projected_df.columns:
        projected_df = projected_df.drop(columns=['Normalized_Team'])
        
    if 'xPts' in projected_df.columns:
        projected_df = projected_df.sort_values(by='xPts', ascending=False)
        
    return projected_df