import pandas as pd

def calculate_projections(df, match_odds):
    """
    Takes a raw FanTeam dataframe and calculates individualized xPts 
    projections using real-time dynamic match odds passed from the UI.
    """
    projected_data = []

    for index, row in df.iterrows():
        team = row.get('Club', row.get('Team'))
        if isinstance(team, str):
            team = team.strip().upper()
            
        pos = str(row['Position']).upper().strip()
        name = row['Name']

        if team not in match_odds:
            row_dict = row.to_dict()
            row_dict['xPts'] = 0.0
            projected_data.append(row_dict)
            continue

        odds = match_odds[team]
        base_pts = 2.0 
        
        # Clean Sheet Calculations
        if pos in ['GK', 'DEF']:
            base_pts += (4.0 * odds['CS_odds'])
        elif pos == 'MID':
            base_pts += (1.0 * odds['CS_odds'])
            
        # xG & xA Share Distribution
        xG_share = {'FWD': 0.40, 'MID': 0.40, 'DEF': 0.15, 'GK': 0.0}.get(pos, 0)
        player_xG = odds['xG'] * xG_share
        player_xA = player_xG * 0.75 
        
        goal_pts = {'FWD': 4, 'MID': 5, 'DEF': 6, 'GK': 0}.get(pos, 0)
        base_pts += (player_xG * goal_pts)
        base_pts += (player_xA * 3.0)

        # 90-Minute Appearance Bonuses
        prob_90_mins = {'GK': 0.90, 'DEF': 0.90, 'MID': 0.60, 'FWD': 0.60}.get(pos, 0.5)
        if pos in ['MID', 'FWD']:
            base_pts += (1.0 * prob_90_mins)

        # Shots on Target Distribution
        sot_share = {'FWD': 0.50, 'MID': 0.35, 'DEF': 0.15, 'GK': 0.0}.get(pos, 0)
        player_xSoT = odds['Team_xSoT'] * sot_share
        sot_multiplier = {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6, 'GK': 0.0}.get(pos, 0)
        base_pts += (player_xSoT * sot_multiplier)

        # Goalkeeper Saves Math
        if pos == 'GK':
            opp_team = [t for t in match_odds.keys() if t != team]
            opp_xG = match_odds[opp_team[0]]['xG'] if opp_team else 1.0
            xSaves = max(0, odds['Opp_xSoT'] - opp_xG) 
            base_pts += (xSaves * 0.5)

        # Impact Points
        base_pts += ((odds['Win_prob'] * 0.3) - (odds['Loss_prob'] * 0.3))
        
        row_dict = row.to_dict()
        row_dict['xPts'] = round(base_pts, 2)
        projected_data.append(row_dict)

    projected_df = pd.DataFrame(projected_data)
    if 'xPts' in projected_df.columns:
        projected_df = projected_df.sort_values(by='xPts', ascending=False)
    return projected_df