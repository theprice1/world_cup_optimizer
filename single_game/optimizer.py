import pulp
import pandas as pd

class LineupOptimizer:
    def __init__(self, player_df):
        """
        Initializes the optimizer with the parsed player pool DataFrame.
        """
        self.df = player_df.copy()
        # Ensure data types are correct for the mathematical solver
        self.df['Salary'] = self.df['Salary'].astype(float)
        self.df['Projected_xPts'] = self.df['Projected_xPts'].astype(float)

    def solve_optimal_lineup(self, budget=50.0, max_per_team=3, roster_size=5):
        """
        Solves a Mixed-Integer Linear Programming (MILP) problem to find 
        the optimal combination of players maximizing Projected_xPts.
        """
        if self.df.empty:
            return None

        # 1. Define the Problem
        prob = pulp.LpProblem("FanTeam_Single_Game_Optimization", pulp.LpMaximize)

        # 2. Define Decision Variables (1 if player is picked, 0 otherwise)
        player_vars = pulp.LpVariable.dicts(
            "Player", 
            self.df.index, 
            cat=pulp.LpBinary
        )

        # 3. Objective Function: Maximize Expected Points
        prob += pulp.lpSum(self.df.loc[i, 'Projected_xPts'] * player_vars[i] for i in self.df.index)

        # 4. Constraint 1: Total Roster Size
        prob += pulp.lpSum(player_vars[i] for i in self.df.index) == roster_size

        # 5. Constraint 2: Budget Cap
        prob += pulp.lpSum(self.df.loc[i, 'Salary'] * player_vars[i] for i in self.df.index) <= budget

        # 6. Constraint 3: Max Players per Team (to prevent locking into just one country)
        teams = self.df['Team'].unique()
        for team in teams:
            prob += pulp.lpSum(player_vars[i] for i in self.df.index if self.df.loc[i, 'Team'] == team) <= max_per_team

        # 7. Solve the system quietly
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        # Check if an optimal solution was found
        if pulp.LpStatus[prob.status] != "Optimal":
            return None

        # 8. Extract Selected Lineup
        selected_indices = [i for i in self.df.index if player_vars[i].varValue == 1]
        lineup_df = self.df.loc[selected_indices].copy()

        # 9. Designate Captain (Highest projected player gets 1.5x multiplier)
        lineup_df = lineup_df.sort_values(by="Projected_xPts", ascending=False).reset_index(drop=True)
        lineup_df['Role'] = ['Captain (1.5x)'] + ['Flexible'] * (len(lineup_df) - 1)
        
        # Adjust captain's points in the final display array
        lineup_df.loc[0, 'Projected_xPts'] = round(lineup_df.loc[0, 'Projected_xPts'] * 1.5, 2)

        return lineup_df