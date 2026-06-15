import pandas as pd

class ProjectionEngine:
    def __init__(self, fanteam_scoring_rules=None):
        """
        Initializes the pricing and projections calculator using FanTeam criteria.
        """
        if fanteam_scoring_rules:
            self.scoring = fanteam_scoring_rules
        else:
            # Production FanTeam Scoring Defaults
            self.scoring = {
                'appearance': 1.0,
                'clean_sheet': 4.0,
                'save': 0.5,
                'shots_on_target': 0.4,
                'goals': {'FWD': 4.0, 'MID': 5.0, 'DEF': 6.0, 'GK': 8.0}
            }

    def odds_to_probability(self, decimal_odds):
        """Converts decimal market price into implied probability percentage."""
        if not decimal_odds or decimal_odds <= 1.0:
            return 0.0
        return 1.0 / decimal_odds

    def build_projections_dataframe(self, baselines, live_props_map):
        """
        Merges underlying baseline stats and real-time market data vectors,
        applying mathematical scoring equations to resolve optimized Expected Points (xPts).
        """
        from single_game.data_pipeline import LiveDataPipeline
        pipeline_utils = LiveDataPipeline()
        
        rows = []
        for raw_name, profile in baselines.items():
            norm_name = pipeline_utils.normalize_name(raw_name)
            position = profile.get('Position', 'MID')
            
            # Extract live betting props if available; fallback to baseline projections if empty
            prop_data = live_props_map.get(norm_name, {})
            sot_odds = prop_data.get('sot_over_odds', None)
            sot_line = prop_data.get('sot_line', 1.5)
            
            # --- Projections Mathematics ---
            xPts = 0.0
            
            # 1. Start / Appearance Points
            xPts += self.scoring['appearance']
            
            # 2. Shots on Target Evaluation via Implied Odds Probabilities
            if sot_odds:
                prob_over_sot = self.odds_to_probability(sot_odds)
                # Mathematical estimation: weighted average of clearing the prop line
                estimated_sot = sot_line * prob_over_sot * 1.2 
                xPts += estimated_sot * self.scoring['shots_on_target']
            else:
                # Historical baseline fallback
                estimated_sot = 1.1 if position in ['FWD', 'MID'] else 0.2
                xPts += estimated_sot * self.scoring['shots_on_target']
                
            # 3. Position-Based Bonus Metrics (Saves/Clean Sheets)
            if position == 'GK':
                # Simplified save calculation based on historical save percentage baseline
                xPts += (profile['Starts'] * profile['Save_Pct'] * 0.3) * self.scoring['save']
                # Default 30% baseline chance for a clean sheet if H2H endpoints are excluded
                xPts += 0.30 * self.scoring['clean_sheet']
            elif position == 'DEF':
                xPts += 0.30 * self.scoring['clean_sheet']

            # Assign fantasy pricing configuration (simulating platform salary metrics)
            mock_salaries = {'FWD': 11.5, 'MID': 9.5, 'DEF': 7.0, 'GK': 6.0}
            salary = mock_salaries.get(position, 8.0)

            rows.append({
                'Player': raw_name,
                'Team': profile.get('Team', 'Unknown'),
                'Position': position,
                'Salary': salary,
                'Projected_xPts': round(xPts, 2),
                'Live_Market_Mapped': 'Yes' if sot_odds else 'No'
            })
            
        return pd.DataFrame(rows)