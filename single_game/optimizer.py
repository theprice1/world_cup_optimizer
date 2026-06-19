import pulp
import pandas as pd

def run_optimization(df, salary_cap=100.0, max_per_team=5, roster_status_filter="All", use_correlation=True):
    """
    Executes linear programming optimization with strict positional constraints 
    and optional correlation logic.
    
    roster_status_filter: "All", "Expected", or "Starting"
    """
    # 1. PRE-OPTIMIZATION FILTERING
    # Ensure we operate on a clean copy and reset the index for PuLP mapping
    pool_df = df.copy()
    
    # Apply Starting/Expected filters if that column exists in your FanTeam CSV
    # (Adjust 'Status' to match your actual CSV column name if different)
    if roster_status_filter != "All" and 'Status' in pool_df.columns:
        pool_df = pool_df[pool_df['Status'].str.contains(roster_status_filter, case=False, na=False)]

    if pool_df.empty or len(pool_df) < 11:
        return None, f"Insufficient players after applying the '{roster_status_filter}' filter to form an 11-man roster."

    pool_df = pool_df.reset_index(drop=True)

    # 2. INITIALIZE THE PROBLEM
    prob = pulp.LpProblem("DFS_Optimization", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("Player", pool_df.index, cat="Binary")
    
    # Objective: Maximize total xPts
    prob += pulp.lpSum(pool_df.loc[i, "xPts"] * player_vars[i] for i in pool_df.index)
    
    # 3. GLOBAL CONSTRAINTS
    # Strict Total Players
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index) == 11
    
    # Strict Salary Cap
    prob += pulp.lpSum(pool_df.loc[i, "Salary"] * player_vars[i] for i in pool_df.index) <= salary_cap
    
    # 4. STRICT POSITIONAL CONSTRAINTS (Fixes the 3 GK issue)
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "GK") == 1
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "DEF") >= 3
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "DEF") <= 5
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "MID") >= 3
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "MID") <= 5
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "FWD") >= 1
    prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "FWD") <= 3

    # 5. DYNAMIC MAX PLAYERS PER TEAM
    teams = pool_df["Team"].unique()
    for team in teams:
        prob += pulp.lpSum(player_vars[i] for i in pool_df.index if pool_df.loc[i, "Team"] == team) <= max_per_team

    # 6. ADVANCED NEGATIVE CORRELATION (Optional)
    # Banish opposing forwards if you roster a team's Goalkeeper
    if use_correlation and 'Opponent' in pool_df.columns:
        for i in pool_df.index:
            if pool_df.loc[i, "Position"] == "GK":
                gk_team = pool_df.loc[i, "Team"]
                gk_opponent = pool_df.loc[i, "Opponent"]
                
                # Find all opposing forwards
                opposing_fwds = [j for j in pool_df.index if pool_df.loc[j, "Team"] == gk_opponent and pool_df.loc[j, "Position"] == "FWD"]
                
                for fwd_index in opposing_fwds:
                    # Logic: player_vars[GK] + player_vars[Opposing FWD] must be <= 1. 
                    # If GK is 1, FWD must be 0. If FWD is 1, GK must be 0.
                    prob += player_vars[i] + player_vars[fwd_index] <= 1

    # 7. EXECUTE THE SOLVER
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    if pulp.LpStatus[status] == "Optimal":
        selected_indices = [i for i in pool_df.index if player_vars[i].varValue == 1]
        optimized_df = pool_df.loc[selected_indices].copy()
        
        # Sort values nicely for the UI
        pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
        optimized_df["_sort"] = optimized_df["Position"].map(pos_order)
        optimized_df = optimized_df.sort_values(["_sort", "Salary"], ascending=[True, False]).drop(columns=["_sort"])
        
        return optimized_df, "Optimal Lineup Generated Successfully"
    
    return None, "Optimizer could not find a valid lineup under these constraints. Try increasing the salary cap or max players per team."