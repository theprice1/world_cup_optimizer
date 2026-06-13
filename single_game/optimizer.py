import pulp
import pandas as pd

def run_optimization(df, budget=59.0, num_lineups=10, max_overlap=4, stack_rule=None):
    all_lineups = []
    previous_lineups = [] 
    players = df.index.tolist()
    team_col = 'Club' if 'Club' in df.columns else 'Team'
    
    for lineup_num in range(1, num_lineups + 1):
        prob = pulp.LpProblem(f"Lineup_{lineup_num}", pulp.LpMaximize)
        
        roster_vars = pulp.LpVariable.dicts("roster", players, 0, 1, pulp.LpBinary)
        captain_vars = pulp.LpVariable.dicts("captain", players, 0, 1, pulp.LpBinary)
        
        # Objective Function
        prob += pulp.lpSum(
            (df.loc[i, 'xPts'] * roster_vars[i]) + 
            (df.loc[i, 'xPts'] * 0.5 * captain_vars[i]) 
            for i in players
        )
        
        # Base Lineup Composition
        prob += pulp.lpSum(roster_vars[i] for i in players) == 5
        prob += pulp.lpSum(captain_vars[i] for i in players) == 1
        
        for i in players:
            prob += captain_vars[i] <= roster_vars[i]
            
        prob += pulp.lpSum(df.loc[i, 'Price'] * roster_vars[i] for i in players) <= budget
        
        gk_indices = df[df['Position'] == 'GK'].index.tolist()
        prob += pulp.lpSum(roster_vars[i] for i in gk_indices) <= 1

        # Stacking Rules
        if stack_rule:
            for team, required_count in stack_rule.items():
                team_indices = df[df[team_col].str.upper() == team.upper()].index.tolist()
                prob += pulp.lpSum(roster_vars[i] for i in team_indices) == required_count
        else:
            teams = df[team_col].unique()
            for team in teams:
                team_indices = df[df[team_col] == team].index.tolist()
                prob += pulp.lpSum(roster_vars[i] for i in team_indices) <= 3

        # Lineup Diversity Constraints
        for past_lineup in previous_lineups:
            prob += pulp.lpSum(roster_vars[i] for i in past_lineup) <= max_overlap

        # Safe Solver Invocation with Cloud Deadlock timeouts
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
        
        if pulp.LpStatus[prob.status] != 'Optimal':
            break
            
        current_roster_indices = [i for i in players if roster_vars[i].varValue == 1]
        previous_lineups.append(current_roster_indices)
        
        lineup_data = df.loc[current_roster_indices].copy()
        lineup_data['Is_Captain'] = [captain_vars[i].varValue == 1 for i in current_roster_indices]
        lineup_data['Lineup_Num'] = lineup_num
        
        all_lineups.append(lineup_data)
        del prob # Memory cleanup

    if all_lineups:
        return pd.concat(all_lineups, ignore_index=True)
    return pd.DataFrame()