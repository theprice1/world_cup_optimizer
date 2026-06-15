import pulp
import pandas as pd

class MultiGameOptimizer:
    def __init__(self, player_df):
        """
        Initializes the optimizer with the full slate player pool DataFrame.
        """
        self.df = player_df.copy()
        self.df['Salary'] = self.df['Salary'].astype(float)
        self.df['Projected_xPts'] = self.df['Projected_xPts'].astype(float)

    def solve_slate(self, budget=100.0, max_per_team=3):
        """
        Optimizes an 11-player lineup using standard full-slate formation rules:
        - Exactly 1 Goalkeeper (GK)
        - 3 to 5 Defenders (DEF)
        - 3 to 5 Midfielders (MID)
        - 1 to 3 Forwards (FWD)
        - Total exactly 11 players
        """
        if self.df.empty:
            return None

        prob = pulp.LpProblem("FanTeam_Multi_Game_Optimization", pulp.LpMaximize)
        player_vars = pulp.LpVariable.dicts("Player", self.df.index, cat=pulp.LpBinary)

        # Objective: Maximize total expected points
        prob += pulp.lpSum(self.df.loc[i, 'Projected_xPts'] * player_vars[i] for i in self.df.index)

        # Roster Size Constraint
        prob += pulp.lpSum(player_vars[i] for i in self.df.index) == 11

        # Budget Constraint
        prob += pulp.lpSum(self.df.loc[i, 'Salary'] * player_vars[i] for i in self.df.index) <= budget

        # Team Cap Constraint
        for team in self.df['Team'].unique():
            prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Team'] == team) <= max_per_team

        # Positional Constraints
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'GK') == 1
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'DEF') >= 3
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'DEF') <= 5
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'MID') >= 3
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'MID') <= 5
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'FWD') >= 1
        prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Position'] == 'FWD') <= 3

        # Solve
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        if pulp.LpStatus[prob.status] != "Optimal":
            return None

        selected_indices = [i for i in self.df.index if player_vars[i].varValue == 1]
        lineup_df = self.df.loc[selected_indices].copy()
        
        # Sort logically by position for clean user presentation
        pos_order = {'GK': 0, 'DEF': 1, 'MID': 2, 'FWD': 3}
        lineup_df['pos_rank'] = lineup_df['Position'].map(pos_order)
        lineup_df = lineup_df.sort_values(by='pos_rank').drop(columns=['pos_rank']).reset_index(drop=True)
        
        return lineup_df