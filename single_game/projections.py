import pulp
import pandas as pd

class LineupOptimizer:
    def __init__(self):
        pass

    def optimize(self, df, salary_cap=50.0, max_per_team=5, roster_status_filter="All", use_correlation=True):
        """
        Executes a 5-man Showdown linear programming optimization.
        Allocates exactly 1 Captain (1.5x points) and 4 Flex players.
        """
        pool_df = df.copy()
        
        # Apply Status Filters if column exists
        if roster_status_filter != "All" and 'Status' in pool_df.columns:
            pool_df = pool_df[pool_df['Status'].str.contains(roster_status_filter, case=False, na=False)]

        if pool_df.empty or len(pool_df) < 5:
            return None, f"Insufficient players ({len(pool_df)}) to form a 5-man lineup."

        pool_df = pool_df.reset_index(drop=True)

        # 1. INITIALIZE LP PROBLEM
        prob = pulp.LpProblem("FanTeam_5_Man_Optimization", pulp.LpMaximize)
        
        # Two binary decision variables per player: chosen as Flex or chosen as Captain
        flex_vars = pulp.LpVariable.dicts("Flex", pool_df.index, cat="Binary")
        capt_vars = pulp.LpVariable.dicts("Capt", pool_df.index, cat="Binary")
        
        # 2. OBJECTIVE: Maximize total xPts (Captain gets 1.5x points)
        prob += pulp.lpSum(
            (pool_df.loc[i, "Projected_xPts"] * flex_vars[i]) + 
            (pool_df.loc[i, "Projected_xPts"] * 1.5 * capt_vars[i]) 
            for i in pool_df.index
        )
        
        # 3. PLAYER MUTUALLY EXCLUSIVE RULE
        # A player cannot be both Captain and Flex simultaneously
        for i in pool_df.index:
            prob += flex_vars[i] + capt_vars[i] <= 1
            
        # 4. ROSTER SIZE CONSTRAINTS
        prob += pulp.lpSum(capt_vars[i] for i in pool_df.index) == 1  # Exactly 1 Captain
        prob += pulp.lpSum(flex_vars[i] for i in pool_df.index) == 4  # Exactly 4 Flex
        
        # 5. BUDGET LIMIT (Captain costs 1x normal salary)
        prob += pulp.lpSum(pool_df.loc[i, "Salary"] * (flex_vars[i] + capt_vars[i]) for i in pool_df.index) <= salary_cap
        
        # 6. POSITIONAL LIMITS
        prob += pulp.lpSum(flex_vars[i] + capt_vars[i] for i in pool_df.index if pool_df.loc[i, "Position"] == "GK") <= 1

        # 7. DYNAMIC MAX PLAYERS PER CLUB
        teams = pool_df["Team"].unique()
        for team in teams:
            prob += pulp.lpSum(flex_vars[i] + capt_vars[i] for i in pool_df.index if pool_df.loc[i, "Team"] == team) <= max_per_team

        # 8. ANTI-CORRELATION RULE
        if use_correlation and 'Opponent' in pool_df.columns:
            for i in pool_df.index:
                if pool_df.loc[i, "Position"] == "GK":
                    gk_opponent = pool_df.loc[i, "Opponent"]
                    opposing_fwds = [j for j in pool_df.index if pool_df.loc[j, "Team"] == gk_opponent and pool_df.loc[j, "Position"] == "FWD"]
                    
                    for fwd_index in opposing_fwds:
                        gk_drafted = flex_vars[i] + capt_vars[i]
                        fwd_drafted = flex_vars[fwd_index] + capt_vars[fwd_index]
                        prob += gk_drafted + fwd_drafted <= 1

        # 9. RUN SOLVER
        status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
        
        if pulp.LpStatus[status] == "Optimal":
            selected_records = []
            
            for i in pool_df.index:
                if capt_vars[i].varValue == 1:
                    record = pool_df.loc[i].copy()
                    record["Roster_Slot"] = "⭐ CAPTAIN"
                    record["Projected_xPts"] = round(record["Projected_xPts"] * 1.5, 2)
                    selected_records.append(record)
                elif flex_vars[i].varValue == 1:
                    record = pool_df.loc[i].copy()
                    record["Roster_Slot"] = "FLEX"
                    selected_records.append(record)
                    
            optimized_df = pd.DataFrame(selected_records)
            
            # Put Captain at the top of the interface
            slot_order = {"⭐ CAPTAIN": 0, "FLEX": 1}
            optimized_df["_sort"] = optimized_df["Roster_Slot"].map(slot_order)
            optimized_df = optimized_df.sort_values(["_sort", "Salary"], ascending=[True, False]).drop(columns=["_sort"])
            
            return optimized_df, "Optimal 5-Man Lineup Generated Successfully!"
        
        return None, "Infeasible Constraints: The solver could not form a legal 5-man squad. Try raising the budget or increasing maximum players per team."