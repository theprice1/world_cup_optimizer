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

    def build_projections_dataframe(self, fanteam_df, baselines, live_props_map):
        """
        Merges uploaded CSV data, baseline stats, and real-time market data vectors.
        """
        from single_game.data_pipeline import LiveDataPipeline
        pipeline_utils = LiveDataPipeline()
        
        rows = []
        
        # Loop through the actual players in your uploaded FanTeam CSV
        for index, row in fanteam_df.iterrows():
            # Extract standard FanTeam CSV fields
            raw_name = row.get('name', row.get('Player', 'Unknown'))
            position = row.get('position', row.get('Position', 'MID'))
            salary = row.get('price', row.get('Price', 8.0))
            team = row.get('team', row.get('Team', 'Unknown'))
            
            norm_name = pipeline_utils.normalize_name(raw_name)
            
            # See if we have live odds or historical baselines for this player
            prop_data = live_props_map.get(norm_name, {})
            profile = baselines.get(raw_name, {'Starts': 5, 'Save_Pct': 0.65})
            
            sot_odds = prop_data.get('sot_over_odds', None)
            sot_line = prop_data.get('sot_line', 1.5)
            
            xPts = self.scoring['appearance']
            
            if sot_odds:
                prob_over_sot = self.odds_to_probability(sot_odds)
                estimated_sot = sot_line * prob_over_sot * 1.2 
                xPts += estimated_sot * self.scoring['shots_on_target']
            else:
                estimated_sot = 1.1 if position in ['FWD', 'MID'] else 0.2
                xPts += estimated_sot * self.scoring['shots_on_target']
                
            if position == 'GK':
                xPts += (profile.get('Starts', 0) * profile.get('Save_Pct', 0) * 0.3) * self.scoring['save']
                xPts += 0.30 * self.scoring['clean_sheet']
            elif position == 'DEF':
                xPts += 0.30 * self.scoring['clean_sheet']

            rows.append({
                'Player': raw_name,
                'Team': team,
                'Position': position,
                'Salary': float(salary),
                'Projected_xPts': round(xPts, 2),
                'Live_Market_Mapped': 'Yes' if sot_odds else 'No'
            })
            
        return pd.DataFrame(rows)