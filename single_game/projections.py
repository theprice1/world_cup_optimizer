import pandas as pd
import numpy as np
import math
from scipy.stats import poisson, skellam
from single_game.data_pipeline import LiveDataPipeline

def clean_position(pos_val):
    p = str(pos_val).upper().strip()
    if p in ['GK', 'GOALKEEPER', 'G']: return 'GK'
    if p in ['DEF', 'DF', 'DEFENDER', 'D']: return 'DEF'
    if p in ['MID', 'MD', 'MIDFIELDER', 'M']: return 'MID'
    if p in ['FWD', 'FW', 'FORWARD', 'ATTACKER', 'STRIKER', 'F']: return 'FWD'
    return p

def solve_implied_poisson_sot(decimal_odds):
    """
    MODEL 3: IMPLIED POISSON RATES FOR SHOTS ON TARGET
    Solves for the implied Poisson rate (lambda) given standard market decimal odds.
    If odds are invalid or missing, it gracefully provides a neutral default rate.
    """
    if pd.isna(decimal_odds) or decimal_odds <= 1.0:
        return 0.85 # Balanced default expected shots on target value
        
    implied_prob = 1.0 / decimal_odds
    
    # Numerical solver to find lambda for the cumulative distribution function P(X >= 1)
    # 1 - e^(-lambda) = implied_prob
    # e^(-lambda) = 1 - implied_prob -> lambda = -ln(1 - implied_prob)
    try:
        val = max(0.01, min(0.99, implied_prob))
        calculated_lambda = -math.log(1.0 - val)
        return calculated_lambda
    except Exception:
        return 0.85

def calculate_projections(df, match_odds, api_key=None):
    """
    Advanced Stochastic Projection Engine executing the 4 core models:
    1. Survival Analysis (90-Minute Completion Bonus)
    2. Poisson Thinning (Goalkeeper Save Volumes)
    3. Implied Poisson Solving (Player-Specific Shots on Target Prop Lines)
    4. Skellam Distributions (Dynamic In-Match Period Impact Points)
    """
    df = df.copy()
    df['Position'] = df['Position'].apply(clean_position)
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(4.5)
    
    team_col = 'Club' if 'Club' in df.columns else 'Team'
    df['Normalized_Team'] = df[team_col].astype(str).str.strip().str.upper()

    # Step 1: Ingest Pipeline Profiles
    pipeline = LiveDataPipeline(odds_api_key=api_key)
    fbref_history = pipeline.scrape_fbref_historical_baselines()

    # Step 2: Establish Position Group Price Pools for fallback distributions
    group_salaries = df.groupby(['Normalized_Team', 'Position'])['Price'].sum().to_dict()

    projected_data = []

    for index, row in df.iterrows():
        name_upper = str(row['Name']).upper().strip()
        team = row['Normalized_Team']
        pos = row['Position']
        price = row['Price']

        if team not in match_odds:
            row_dict = row.to_dict()
            row_dict['xPts'] = 0.0
            projected_data.append(row_dict)
            continue

        odds = match_odds[team]
        opp_team = [t for t in match_odds.keys() if t != team][0]
        opp_odds = match_odds[opp_team]

        # Retrieve scraped metrics or construct smart fallbacks
        player_stats = fbref_history.get(name_upper, {})
        starts = player_stats.get('Starts', 10)
        completions = player_stats.get('Complete_90', 7)
        scraped_save_pct = player_stats.get('Save_Pct', 0.72 if pos == 'GK' else 0.0)

        # ─── MODEL 1: SURVIVAL ANALYSIS (90-MINUTE COMPLETION BONUS) ───
        # S(90) acts as the probability that a starter lasts the full game
        survival_prob = completions / max(1, starts)
        
        # Determine expected minutes based on historical survival curves
        if pos == 'GK':
            expected_mins = 90.0
            survival_prob = 1.0
        else:
            expected_mins = 90.0 if survival_prob > 0.8 else (65.0 if survival_prob > 0.4 else 25.0)
            
        time_fraction = expected_mins / 90.0

        # Calculate Appearance Base points
        base_pts = 0.0
        if expected_mins >= 60.0:
            base_pts += 2.0
            if pos in ['MID', 'FWD']:
                base_pts += (1.0 * survival_prob) # FanTeam full 90-minute completion bonus value
        elif expected_mins > 0.0:
            base_pts += 1.0

        # ─── MODEL 2: SKELLAM DISTRIBUTION (IMPACT POINTS) ───
        # Goal differences follow a Skellam distribution when scaled over the player's active minutes
        my_lambda = odds['xG'] * time_fraction
        opp_lambda = opp_odds['xG'] * time_fraction
        
        prob_win_period = 1.0 - skellam.cdf(0, my_lambda, opp_lambda)
        prob_loss_period = skellam.cdf(-1, my_lambda, opp_lambda)
        
        expected_impact_points = (prob_win_period * 0.3) - (prob_loss_period * 0.3)
        base_pts += expected_impact_points

        # ─── MODEL 3: GOALKEEPER SAVES (POISSON THINNING) ───
        if pos == 'GK':
            # Expected saves follow a thinned Poisson process driven by the opponent's total Shots on Target
            expected_saves = scraped_save_pct * opp_odds['Team_xSoT']
            base_pts += (expected_saves * 0.5) # FanTeam +0.5 points per save calculation

        # ─── MODEL 4: PLAYER SHOTS ON TARGET (IMPLIED POISSON) ───
        market_odds_col = 'Market_SoT_Odds' if 'Market_SoT_Odds' in df.columns else None
        if market_odds_col and not pd.isna(row[market_odds_col]):
            player_xSoT = solve_implied_poisson_sot(row[market_odds_col]) * time_fraction
        else:
            # Fallback allocation strategy using modified position price pools
            total_pos_salary = group_salaries.get((team, pos), price)
            price_weight = (price / total_pos_salary) if total_pos_salary > 0 else 1.0
            pos_sot_share = {'FWD': 0.50, 'MID': 0.35, 'DEF': 0.15, 'GK': 0.0}.get(pos, 0.0)
            player_xSoT = odds['Team_xSoT'] * pos_sot_share * price_weight * 2.0 * time_fraction

        sot_scoring_multiplier = {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6}.get(pos, 0.0)
        base_pts += (player_xSoT * sot_scoring_multiplier)

        # ─── ATTACKING & DEFENSIVE BASELINES ───
        # Clean Sheet modeling using Poisson distributions for goals conceded
        opp_xG_poisson_rate = opp_odds['xG']
        clean_sheet_prob = math.exp(-opp_xG_poisson_rate)
        
        if expected_mins >= 60.0:
            if pos in ['GK', 'DEF']:
                # Calculate defensive decay (penalties for multiple goals conceded)
                prob_concede_2 = (opp_xG_poisson_rate**2 * math.exp(-opp_xG_poisson_rate)) / 2.0
                prob_concede_3 = (opp_xG_poisson_rate**3 * math.exp(-opp_xG_poisson_rate)) / 6.0
                base_pts += (clean_sheet_prob * 4.0) - (prob_concede_2 * 1.0) - (prob_concede_3 * 1.0)
            elif pos == 'MID':
                base_pts += (clean_sheet_prob * 1.0)

        # Goals and Assists Distribution
        total_pos_salary = group_salaries.get((team, pos), price)
        price_weight = (price / total_pos_salary) if total_pos_salary > 0 else 1.0
        pos_xg_share = {'FWD': 0.45, 'MID': 0.35, 'DEF': 0.18, 'GK': 0.02}.get(pos, 0.0)
        
        allocated_xG = odds['xG'] * pos_xg_share * price_weight * 2.0 * time_fraction
        allocated_xA = allocated_xG * 0.75

        goal_value = {'FWD': 4, 'MID': 5, 'DEF': 6, 'GK': 10}.get(pos, 4)
        base_pts += (allocated_xG * goal_value)
        base_pts += (allocated_xA * 3.0)

        # Append calculated row to dataset
        row_dict = row.to_dict()
        row_dict['xPts'] = round(max(0.0, base_pts), 2)
        projected_data.append(row_dict)

    projected_df = pd.DataFrame(projected_data)
    if 'Normalized_Team' in projected_df.columns:
        projected_df = projected_df.drop(columns=['Normalized_Team'])
        
    if 'xPts' in projected_df.columns:
        projected_df = projected_df.sort_values(by='xPts', ascending=False)
        
    return projected_df