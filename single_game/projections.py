import pandas as pd

class ProjectionEngine:
    def __init__(self, fanteam_scoring_rules=None):
        if fanteam_scoring_rules:
            self.scoring = fanteam_scoring_rules
        else:
            self.scoring = {
                'appearance': 1.0,
                'clean_sheet': 4.0,
                'save': 0.5,
                'shots_on_target': 0.4,
                'goals': {'FWD': 4.0, 'MID': 5.0, 'DEF': 6.0, 'GK': 8.0}
            }

    def odds_to_probability(self, decimal_odds):
        if not decimal_odds or decimal_odds <= 1.0:
            return 0.0
        return 1.0 / decimal_odds

    def build_projections_dataframe(self, fanteam_df, baselines, live_props_map):
        from single_game.data_pipeline import LiveDataPipeline
        pipeline_utils = LiveDataPipeline()
        
        rows = []
        
        for index, row in fanteam_df.iterrows():
            try:
                last_name = str(row['Name']).strip()
                first_name = str(row['FName']).strip()
                team = str(row['Club']).strip()
                salary_val = row['Price']
                raw_pos_str = str(row['Position']).strip()
            except KeyError as e:
                raise KeyError(f"CRITICAL DATA MAP ERROR: Could not find required column {e} in FanTeam CSV.")

            if isinstance(salary_val, str):
                import re
                numeric_val_str = re.sub(r'[^\d.]', '', salary_val)
                salary = float(numeric_val_str) if numeric_val_str else 0.0
            else:
                salary = float(salary_val)

            raw_pos = raw_pos_str.lower()
            if 'goal' in raw_pos or raw_pos == 'gk':
                position = 'GK'
            elif 'def' in raw_pos:
                position = 'DEF'
            elif 'mid' in raw_pos:
                position = 'MID'
            else:
                position = 'FWD'

            # --- BULLETPROOF TOKEN MATCHING ---
            # 1. Combine First and Last name from CSV!
            fanteam_full_name = f"{first_name} {last_name}"
            norm_fanteam_name = pipeline_utils.normalize_name(fanteam_full_name)
            fanteam_tokens = set(norm_fanteam_name.split())
            
            best_match_data = {}
            best_match_score = 0
            
            # 2. Compare against every API player name
            for api_name, data in live_props_map.items():
                api_tokens = set(api_name.split())
                
                # Count how many words match exactly (e.g. "kevin" and "debruyne")
                intersection = fanteam_tokens.intersection(api_tokens)
                score = len(intersection)
                
                # Boost the score if the Last Name is an exact match
                norm_last_name = pipeline_utils.normalize_name(last_name)
                if norm_last_name in api_tokens and len(norm_last_name) > 2:
                    score += 2
                    
                if score > best_match_score:
                    best_match_score = score
                    best_match_data = data
            
            # If we found at least a 1-token match, assign the data
            prop_data = best_match_data if best_match_score > 0 else {}
            
            sot_odds = prop_data.get('sot_over_odds', None)
            sot_line = prop_data.get('sot_line', 1.5)
            goal_odds = prop_data.get('goal_odds', None)
            
            profile = baselines.get(last_name, {'Starts': 5, 'Save_Pct': 0.65})
            
            xPts = self.scoring['appearance']
            mapped = False
            
            # SOT Logic
            if sot_odds:
                prob_over_sot = self.odds_to_probability(sot_odds)
                estimated_sot = sot_line * prob_over_sot * 1.2 
                xPts += estimated_sot * self.scoring['shots_on_target']
                mapped = True
            else:
                estimated_sot = 1.1 if position in ['FWD', 'MID'] else 0.2
                xPts += estimated_sot * self.scoring['shots_on_target']
                
            # Goalscorer Logic
            if goal_odds:
                prob_goal = self.odds_to_probability(goal_odds)
                xPts += prob_goal * self.scoring['goals'].get(position, 4.0)
                mapped = True
                
            # Defense Logic
            if position == 'GK':
                xPts += (profile.get('Starts', 0) * profile.get('Save_Pct', 0.65) * 0.3) * self.scoring['save']
                xPts += 0.30 * self.scoring['clean_sheet']
            elif position == 'DEF':
                xPts += 0.30 * self.scoring['clean_sheet']

            rows.append({
                'Player': fanteam_full_name,
                'Team': team,
                'Position': position,
                'Salary': salary,
                'Projected_xPts': round(xPts, 2),
                'Live_Market_Mapped': 'Yes' if mapped else 'No'
            })
            
        return pd.DataFrame(rows)