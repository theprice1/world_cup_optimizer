import pandas as pd
import math
import re

class ProjectionEngine:
    def __init__(self):
        # FanTeam Official Single Game Scoring Matrix
        self.scoring = {
            'appearance': 1.0,
            'mins_60_bonus': 1.0,
            'full_match_bonus': {'FWD': 1.0, 'MID': 1.0, 'DEF': 0.0, 'GK': 0.0},
            'goals': {'FWD': 4.0, 'MID': 5.0, 'DEF': 6.0, 'GK': 8.0},
            'assists': 3.0,
            'shots_on_target': {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6, 'GK': 1.0},
            'clean_sheet': {'GK': 4.0, 'DEF': 4.0, 'MID': 1.0, 'FWD': 0.0},
            'save': 0.5,
            'goals_conceded_penalty': -1.0, # Deducted strictly per 2 goals
            'yellow_card': -1.0,
            'red_card': -3.0,
            'impact_positive': 0.3,
            'impact_negative': -0.3,
            'caused_penalty': -2.0,
            'penalty_miss': -2.0,
            'own_goal': -2.0
        }

    def odds_to_probability(self, decimal_odds):
        return (1.0 / decimal_odds) if decimal_odds and decimal_odds > 1.0 else 0.0

    def calculate_poisson_probability(self, lam, k):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)

    def calculate_expected_conceded_penalty(self, xGA):
        if xGA <= 0: return 0.0
        
        prob_0 = self.calculate_poisson_probability(xGA, 0)
        prob_1 = self.calculate_poisson_probability(xGA, 1)
        prob_2 = self.calculate_poisson_probability(xGA, 2)
        prob_3 = self.calculate_poisson_probability(xGA, 3)
        prob_4 = self.calculate_poisson_probability(xGA, 4)
        prob_5 = self.calculate_poisson_probability(xGA, 5)
        prob_6 = self.calculate_poisson_probability(xGA, 6)
        prob_7 = self.calculate_poisson_probability(xGA, 7)
        prob_8_plus = max(0.0, 1.0 - sum([prob_0, prob_1, prob_2, prob_3, prob_4, prob_5, prob_6, prob_7]))
        
        # Exact FanTeam penalty thresholds
        expected_penalty = (
            (-1.0 * (prob_2 + prob_3)) +
            (-2.0 * (prob_4 + prob_5)) +
            (-3.0 * (prob_6 + prob_7)) +
            (-4.0 * prob_8_plus)
        )
        return expected_penalty

    def build_projections_dataframe(self, fanteam_df, baselines, live_props_map):
        from single_game.data_pipeline import LiveDataPipeline
        pipeline_utils = LiveDataPipeline()
        rows = []
        
        is_live_data_active = len(live_props_map) > 0
        
        for index, row in fanteam_df.iterrows():
            last_name = str(row.get('Name', '')).strip()
            first_name = str(row.get('FName', '')).strip()
            team = str(row.get('Club', '')).strip()
            salary_val = row.get('Price', 0)
            raw_pos_str = str(row.get('Position', '')).strip().lower()

            salary = float(re.sub(r'[^\d.]', '', str(salary_val))) if isinstance(salary_val, str) else float(salary_val)

            if 'goal' in raw_pos_str or raw_pos_str == 'gk': position = 'GK'
            elif 'def' in raw_pos_str: position = 'DEF'
            elif 'mid' in raw_pos_str: position = 'MID'
            else: position = 'FWD'

            fanteam_full_name = f"{first_name} {last_name}".strip()
            norm_fanteam_name = pipeline_utils.normalize_name(fanteam_full_name)
            fanteam_tokens = set(norm_fanteam_name.split())
            
            best_match_data = {}
            best_match_score = 0
            
            for api_name, data in live_props_map.items():
                api_tokens = set(api_name.split())
                intersection = fanteam_tokens.intersection(api_tokens)
                score = len(intersection)
                
                norm_last_name = pipeline_utils.normalize_name(last_name)
                if norm_last_name in api_tokens and len(norm_last_name) > 2:
                    score += 2
                    
                if score > best_match_score:
                    best_match_score = score
                    best_match_data = data
            
            prop_data = best_match_data if best_match_score > 0 else {}
            
            # --- Match Environment Integration ---
            if is_live_data_active and prop_data:
                home_metrics = prop_data.get('home_metrics', {})
                away_metrics = prop_data.get('away_metrics', {})
                is_home = (team.lower() in str(prop_data.get('home_team', '')).lower())
                match_context = home_metrics if is_home else away_metrics
                
                team_xG = match_context.get('expected_goals_for', 1.35)
                team_xGA = match_context.get('expected_goals_against', 1.35)
                team_cs_prob = match_context.get('clean_sheet_prob', 0.25)
            else:
                team_baseline = baselines.get('TEAMS', {}).get(team, {'xG_per_game': 1.35, 'xGA_per_game': 1.35, 'CS_rate': 0.25})
                team_xG = team_baseline.get('xG_per_game', 1.35)
                team_xGA = team_baseline.get('xGA_per_game', 1.35)
                team_cs_prob = team_baseline.get('CS_rate', 0.25)

            # Player Profile Base Metrics
            profile = baselines.get('PLAYERS', {}).get(last_name, baselines.get('PLAYERS', {}).get(fanteam_full_name, {}))
            projected_minutes = profile.get('Expected_Minutes', 85.0 if position in ['GK', 'DEF'] else 75.0)
            
            xPts = 0.0
            
            # 1. Durability
            prob_start = 1.0 if projected_minutes > 45 else 0.1
            prob_60_mins = 0.92 if projected_minutes >= 70 else 0.0
            prob_full_match = 0.85 if projected_minutes >= 90 else 0.10
            
            xPts += prob_start * self.scoring['appearance']
            xPts += prob_60_mins * self.scoring['mins_60_bonus']
            xPts += prob_full_match * self.scoring['full_match_bonus'].get(position, 0.0)

            # 2. Attacking
            goal_odds = prop_data.get('goal_odds')
            if goal_odds:
                prob_goal = self.odds_to_probability(goal_odds)
                exp_goals = -math.log(1.0 - min(0.99, prob_goal))
            else:
                historical_xg = profile.get('xG_per_90')
                goal_share = 0.35 if position == 'FWD' else (0.15 if position == 'MID' else 0.04)
                exp_goals = historical_xg * (projected_minutes/90) if historical_xg else team_xG * goal_share * (projected_minutes/90)

            xPts += exp_goals * self.scoring['goals'].get(position, 4.0)
            
            # Assists
            assist_share = profile.get('Assist_Share', 0.15 if position == 'MID' else 0.08)
            exp_assists = team_xG * assist_share * (projected_minutes / 90.0)
            xPts += exp_assists * self.scoring['assists']

            # 3. SOT
            sot_odds = prop_data.get('sot_over_odds')
            sot_line = prop_data.get('sot_line', 0.5)
            sot_multiplier = self.scoring['shots_on_target'].get(position, 0.4)
            
            if sot_odds:
                prob_over_sot = self.odds_to_probability(sot_odds)
                estimated_sot = sot_line * prob_over_sot * 1.5 if sot_line == 0.5 else sot_line * prob_over_sot * 1.18 
            else:
                sot_base = {'FWD': 1.15, 'MID': 0.75, 'DEF': 0.22, 'GK': 0.02}
                estimated_sot = sot_base.get(position, 0.2) * (projected_minutes / 90.0)
                
            xPts += estimated_sot * sot_multiplier

            # 4. Defense
            xPts += (team_cs_prob * prob_60_mins) * self.scoring['clean_sheet'].get(position, 0.0)
            
            if position in ['GK', 'DEF']:
                xPts += self.calculate_expected_conceded_penalty(team_xGA)

            if position == 'GK':
                opp_shots = team_xGA * 3.2
                exp_saves = opp_shots * profile.get('Save_Pct', 0.70) * (projected_minutes / 90.0)
                xPts += exp_saves * self.scoring['save']

            # 5. Negative Variance (Cards & Errors)
            exp_cards = profile.get('Cards_Per_90', 0.15) * (projected_minutes / 90.0)
            xPts += (exp_cards * 0.90) * self.scoring['yellow_card']
            xPts += (exp_cards * 0.10) * self.scoring['red_card']
            
            xPts += 0.02 * self.scoring['own_goal']
            xPts += 0.02 * self.scoring['caused_penalty']
            if profile.get('Is_Penalty_Taker', False):
                xPts += (exp_goals * 0.15) * self.scoring['penalty_miss']

            # 6. Micro Impact
            net_impact = profile.get('Net_Impact_Per_90', 2.0) * (projected_minutes / 90.0)
            xPts += (net_impact * 0.55) * self.scoring['impact_positive']
            xPts += (net_impact * 0.45) * self.scoring['impact_negative']

            rows.append({
                'Player': fanteam_full_name,
                'Position': position,
                'Team': team,
                'Salary': salary,
                'Goal_Odds': goal_odds,
                'SOT_Odds': sot_odds,
                'Team_xG': round(team_xG, 2),
                'Team_xGA': round(team_xGA, 2),
                'Projected_xPts': round(xPts, 2)
            })
            
        return pd.DataFrame(rows)
