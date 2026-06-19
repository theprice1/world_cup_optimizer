import pandas as pd

class ProjectionEngine:
    def __init__(self):
        self.appearance_points = 2.0
        self.sot_points = 0.6
        self.goal_weights = {"GK": 8.0, "DEF": 6.0, "MID": 5.0, "FWD": 4.0}
        self.clean_sheet_weights = {"GK": 4.0, "DEF": 4.0, "MID": 1.0, "FWD": 0.0}

    def build_projections_dataframe(self, fanteam_df, baselines=None, parsed_props=None):
        df = fanteam_df.copy()
        
        # Robust column mapping
        col_mapping = {}
        for col in df.columns:
            c_low = col.lower().strip()
            if c_low in ['player', 'name', 'player name', 'player_name']: col_mapping[col] = 'Player'
            elif c_low in ['position', 'pos', 'role']: col_mapping[col] = 'Position'
            elif c_low in ['team', 'club', 'side']: col_mapping[col] = 'Team'
            elif c_low in ['salary', 'price', 'cost', 'credits']: col_mapping[col] = 'Salary'
                
        df = df.rename(columns=col_mapping)
        
        if 'Player' not in df.columns: raise KeyError("Missing Player column.")
        if 'Position' not in df.columns: df['Position'] = 'MID'
        if 'Team' not in df.columns: raise KeyError("Missing Team column.")
        if 'Salary' not in df.columns: df['Salary'] = 10.0

        team_implied_goals = {"USA": 1.65, "AUS": 1.20}
        team_clean_sheet_prob = {"USA": 0.32, "AUS": 0.22} 

        projected_points = []

        for idx, row in df.iterrows():
            player = row['Player']
            pos = str(row['Position']).upper().strip()
            team = str(row['Team']).upper().strip()
            
            if 'GK' in pos or 'GOAL' in pos: pos = 'GK'
            elif 'DEF' in pos or 'BACK' in pos: pos = 'DEF'
            elif 'MID' in pos or 'CENT' in pos: pos = 'MID'
            elif 'FWD' in pos or 'STR' in pos or 'ATT' in pos: pos = 'FWD'
            
            clean_team = "USA" if "USA" in team or "UNITED STATES" in team else "AUS"
            
            imp_goals = team_implied_goals.get(clean_team, 1.30)
            cs_prob = team_clean_sheet_prob.get(clean_team, 0.25)
            
            exp_goals = 0.0
            exp_sot = 0.0
            
            has_live_props = False
            if parsed_props and player in parsed_props:
                props = parsed_props[player]
                if props.get('anytime_goal_prob') is not None:
                    exp_goals = props['anytime_goal_prob']
                    exp_sot = props.get('expected_sot', 0.0)
                    has_live_props = True

            if not has_live_props:
                if pos == "FWD":
                    exp_goals = imp_goals * 0.38  
                    exp_sot = 1.6 * (imp_goals / 1.3)
                elif pos == "MID":
                    exp_goals = imp_goals * 0.18
                    exp_sot = 0.9 * (imp_goals / 1.3)
                elif pos == "DEF":
                    exp_goals = imp_goals * 0.06
                    exp_sot = 0.3
                elif pos == "GK":
                    exp_goals = 0.0
                    exp_sot = 0.0

            xPts = self.appearance_points
            xPts += exp_goals * self.goal_weights.get(pos, 4.0)
            xPts += exp_sot * self.sot_points
            xPts += cs_prob * self.clean_sheet_weights.get(pos, 0.0)
            
            if pos == "GK":
                opp_goals = team_implied_goals.get("AUS" if clean_team == "USA" else "USA", 1.30)
                xPts += (opp_goals * 3.0) * 0.5

            projected_points.append(round(xPts, 2))

        df["Position"] = [row['Position'] for idx, row in df.iterrows()]
        df["Projected_xPts"] = projected_points
        return df