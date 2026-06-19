import pandas as pd
import numpy as np

class ProjectionEngine:
    def __init__(self):
        # FanTeam Single-Game Point Scoring Rules
        self.appearance_points = 2.0
        self.sot_points = 0.6
        self.goal_weights = {"GK": 8.0, "DEF": 6.0, "MID": 5.0, "FWD": 4.0}
        self.clean_sheet_weights = {"GK": 4.0, "DEF": 4.0, "MID": 1.0, "FWD": 0.0}

    def build_projections_dataframe(self, fanteam_df, baselines=None, parsed_props=None):
        """
        Builds a clean projection pool. Automatically steps in with robust 
        positional allocation math if live bookmaker player props are None.
        """
        df = fanteam_df.copy()
        
        # Hardcoded team implied totals parsed from your data pool
        team_implied_goals = {"USA": 1.65, "AUS": 1.20}
        team_clean_sheet_prob = {"USA": 0.32, "AUS": 0.22} 

        projected_points = []

        for idx, row in df.iterrows():
            player = row['Player']
            pos = row['Position']
            team = row['Team']
            
            # Get team context, default to a balanced baseline
            imp_goals = team_implied_goals.get(team, 1.30)
            cs_prob = team_clean_sheet_prob.get(team, 0.25)
            
            # Initialize empty baseline expectations
            exp_goals = 0.0
            exp_sot = 0.0
            
            # 1. ATTEMPT LIVE API COUPLING
            has_live_props = False
            if parsed_props and player in parsed_props:
                props = parsed_props[player]
                if props.get('anytime_goal_prob') is not None:
                    exp_goals = props['anytime_goal_prob']
                    exp_sot = props.get('expected_sot', 0.0)
                    has_live_props = True

            # 2. EMERGENCY FALLBACK MATH
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

            # 3. APPLY FANTEAM SCORING MATRIX
            xPts = self.appearance_points
            
            # Goal Scoring expected returns
            xPts += exp_goals * self.goal_weights.get(pos, 4.0)
            
            # Shots on target returns
            xPts += exp_sot * self.sot_points
            
            # Clean Sheet expected returns
            xPts += cs_prob * self.clean_sheet_weights.get(pos, 0.0)
            
            # Goalkeeper Save Volume Estimates
            if pos == "GK":
                opp_goals = team_implied_goals.get("AUS" if team == "USA" else "USA", 1.30)
                xPts += (opp_goals * 3.0) * 0.5

            projected_points.append(round(xPts, 2))

        df["Projected_xPts"] = projected_points
        return df