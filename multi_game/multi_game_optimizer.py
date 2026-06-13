import random
import pandas as pd
import pulp

class SixASideOptimizer:
    def __init__(self, df, budget=57.0, min_budget=52.0, max_per_team=4, roster_size=6):
        self.df = df.copy()
        self.budget = budget
        self.min_budget = min_budget
        self.max_per_team = max_per_team
        self.roster_size = roster_size

    def load_and_preprocess(self):
        for col in ['Position', 'Lineup', 'Club', 'Name']:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip().str.lower()

        self.df = self.df[self.df['Lineup'] != 'unexpected'].copy()

        if 'Points' not in self.df.columns:
            self.df['Points'] = self.df['Price'] * 1.2
            
        self.df = self.df.reset_index(drop=True)

    def build_and_solve(self, num_lineups=10, max_overlap=4, max_exposure_pct=0.6, variance_pct=0.08, cs_probability=0.35):
        lineups = []
        previous_lineups = []
        player_exposure = {i: 0 for i in self.df.index}
        max_appearances = int(num_lineups * max_exposure_pct)

        for n in range(num_lineups):
            prob = pulp.LpProblem(f"Six_A_Side_Lineup_{n+1}", pulp.LpMaximize)
            
            player_vars = {
                i: pulp.LpVariable(f"player_{self.df.loc[i, 'PlayerID'] if 'PlayerID' in self.df.columns else i}", cat=pulp.LpBinary)
                for i in self.df.index
            }

            # Constraints
            prob += pulp.lpSum(player_vars[i] for i in self.df.index) == self.roster_size
            total_salary = pulp.lpSum(self.df.loc[i, 'Price'] * player_vars[i] for i in self.df.index)
            prob += total_salary <= self.budget
            prob += total_salary >= self.min_budget

            countries = self.df['Club'].unique()
            penalty_expressions = []

            for country in countries:
                team_players = [i for i in self.df.index if self.df.loc[i, 'Club'] == country]
                def_players = [i for i in team_players if self.df.loc[i, 'Position'] in ['goalkeeper', 'defender']]
                
                prob += pulp.lpSum(player_vars[i] for i in team_players) <= self.max_per_team
                
                y1 = pulp.LpVariable(f"def_1_{country}_{n}", cat=pulp.LpBinary)
                y2 = pulp.LpVariable(f"def_2_{country}_{n}", cat=pulp.LpBinary)
                y3 = pulp.LpVariable(f"def_3_{country}_{n}", cat=pulp.LpBinary)
                y4 = pulp.LpVariable(f"def_4_{country}_{n}", cat=pulp.LpBinary)

                prob += pulp.lpSum(player_vars[i] for i in def_players) == (y1 + y2 + y3 + y4)
                prob += y1 >= y2
                prob += y2 >= y3
                prob += y3 >= y4

                penalty_expressions.append((1 * y2) + (2 * y3) + (3 * y4))

            base_points = pulp.lpSum(
                (self.df.loc[i, 'Points'] * random.uniform(1 - variance_pct, 1 + variance_pct)) * player_vars[i] 
                for i in self.df.index
            )
            total_expected_penalty = pulp.lpSum(penalty_expressions) * cs_probability
            prob += (base_points - total_expected_penalty)

            # Global Diversity Rules
            for past_lineup in previous_lineups:
                prob += pulp.lpSum(player_vars[i] for i in past_lineup) <= max_overlap

            for i in self.df.index:
                if player_exposure[i] >= max_appearances:
                    prob += player_vars[i] == 0

            # Set a 30 second limit per iteration loop to avoid cloud timeouts
            status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
            
            if status == pulp.LpStatusOptimal:
                selected_indices = [i for i in self.df.index if player_vars[i].varValue == 1]
                for i in selected_indices:
                    player_exposure[i] += 1
                    
                lineups.append(self.df.loc[selected_indices].copy())
                previous_lineups.append(selected_indices)
            else:
                break
            
            del prob # Clear memory manually

        return lineups