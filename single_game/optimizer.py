import pulp
import pandas as pd

class LineupOptimizer:
    def __init__(self):
        pass

    def optimize(self, df, salary_cap=100.0, max_per_team=5, roster_status_filter="All", use_correlation=True):
        """
        Executes linear programming optimization using PuLP.
        Enforces exact roster construction rules, flexible budgets, 
        and optional negative correlation.
        """
        # 1. PRE-OPTIMIZATION FILTERING
        pool_df = df.copy()
        
        # Apply Starting/Expected filters if the column exists in the data
        if roster_status_filter != "All" and 'Status' in pool_df.columns:
            pool_df = pool_df[pool_df['Status'].str.contains(roster_status_filter, case=False, na=False)]

        if pool_df.empty or len(pool_df) < 11:
            return None, f"Insufficient players ({len(pool_df)}) available after applying the '{roster_status_filter}' filter to form an 11-man lineup."

        pool_df = pool_df.reset_index(drop=True)

        # 2. INITIALIZE LP PROBLEM
        prob = pulp.LpProblem("FanTeam_Single_Game_Optimization", pulp.LpMaximize)
        player_vars = pulp.LpVariable.dicts("Player", pool_df.index, cat="Binary")
        
        # Objective: Maximize total Projected xPts
        prob += pulp.lpSum(pool_df.loc[i, "Projected_xPts"] * player_vars[i] for i in pool_df.index)
        
        # 3. GLOBAL CONSTRAINTS
        # Exact team size constraint
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index) == 11
        
        # Budget Limit Constraint
        prob += pulp.lpSum(pool_df.loc[i, "Salary"] * player_vars[i] for i in pool_df.index) <= salary_cap
        
        # 4. STRICT POSITIONAL ROSTER LIMITS
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "GK") == 1
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "DEF") >= 3
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "DEF") <= 5
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "MID") >= 3
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "MID") <= 5
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "FWD") >= 1
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "FWD") <= 3

        # 5. DYNAMIC MAX PLAYERS PER CLUB
        teams = pool_df["Team"].unique()
        for team in teams:
            prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Team"] == team) <= max_per_team

        # 6. ANTI-CORRELATION ADVANCED RULE
        # Blocks selecting an opposing forward if you roster that team's GK
        if use_correlation and 'Opponent' in pool_df.columns:
            for i in pool_df.index:
                if pool_df.loc[i, "Position"] == "GK":
                    gk_opponent = pool_df.loc[i, "Opponent"]
                    opposing_fwds = [j for j in pool_df.index if pool_df.loc[j, "Team"] == gk_opponent and pool_df.loc[j, "Position"] == "FWD"]
                    
                    for fwd_index in opposing_fwds:
                        prob += player_vars[i] + player_vars[fwd_index] <= 1

        # 7. RUN SOLVER
        status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
        
        if pulp.LpStatus[status] == "Optimal":
            selected_indices = [i for i in pool_df.index if player_vars[i].varValue == 1]
            optimized_df = pool_df.loc[selected_indices].copy()
            
            # Sort order structure for visual clean presentation in Streamlit UI
            pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
            optimized_df["_sort"] = optimized_df["Position"].map(pos_order)
            optimized_df = optimized_df.sort_values(["_sort", "Salary"], ascending=[True, False]).drop(columns=["_sort"])
            
            return optimized_df, "Optimal Lineup Generated Successfully!"
        
        return None, "Infeasible Constraints: The solver could not form a legal squad under these settings. Try raising the budget or increasing maximum players per team."