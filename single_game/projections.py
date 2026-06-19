import pandas as pd
import math
import re

class ProjectionEngine:
    def __init__(self, fanteam_scoring_rules=None):
        if fanteam_scoring_rules:
            self.scoring = fanteam_scoring_rules
        else:
            # Fully mapped rules from the single-game point matrix
            self.scoring = {
                'appearance': 1.0,
                'mins_60_bonus': 1.0,
                'full_match_bonus': {'FWD': 1.0, 'MID': 1.0, 'DEF': 0.0, 'GK': 0.0},
                'goals': {'FWD': 4.0, 'MID': 5.0, 'DEF': 6.0, 'GK': 8.0},
                'assists': 3.0,
                'shots_on_target': {'FWD': 0.4, 'MID': 0.4, 'DEF': 0.6, 'GK': 1.0},
                'clean_sheet': {'GK': 4.0, 'DEF': 4.0, 'MID': 1.0, 'FWD': 0.0},
                'save': 0.5,
                'yellow_card': -1.0,
                'red_card': -3.0,
                'impact_positive': 0.3,
                'impact_negative': -0.3
            }

    def odds_to_probability(self, decimal_odds):
        if not decimal_odds or decimal_odds <= 1.0:
            return 0.0
        return 1.0 / decimal_odds

    def calculate_poisson_probability(self, lam, k):
        """Calculates exact probability of k events occurring given mean lambda."""
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (math.pow(lam, k) * math.exp(-lam)) / math.factorial(k)

    def calculate_expected_conceded_penalty(self, xGA):
        """
        Computes the exact mathematical expectation for the non-linear goal penalty.
        Deduction triggers strictly per 2 goals scored against (-1 for 2-3, -2 for 4-5, etc).
        """
        if xGA <= 0:
            return 0.0
            
        prob_0 = self.calculate_poisson_probability(xGA, 0)
        prob_1 = self.calculate_poisson_probability(xGA, 1)
        prob_2 = self.calculate_poisson_probability(xGA, 2)
        prob_3 = self.calculate_poisson_probability(xGA, 3)
        prob_4 = self.calculate_poisson_probability(xGA, 4)
        prob_5 = self.calculate_poisson_probability(xGA, 5)
        prob_6 = self.calculate_poisson_probability(xGA, 6)
        prob_7 = self.calculate_poisson_probability(xGA, 7)
        
        # Probability of conceding 8 or more goals (residual)
        prob_8_plus = max(0.0, 1.0 - (prob_0 + prob_1 + prob_2 + prob_3 + prob_4 + prob_5 + prob_6 + prob_7))
        
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
            fanteam_full_name = f"{first_name} {last_name}"
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
            
            # --- EXTRACT LIVE ODDS AND ATTACH TEAM ENVIRONMENT CONTEXT ---
            sot_odds = prop_data.get('sot_over_odds', None)
            sot_line = prop_data.get('sot_line', 1.5)
            goal_odds = prop_data.get('goal_odds', None)
            
            # Extract the embedded team metrics from the updated pipeline mapping
            home_metrics = prop_data.get('home_metrics', {})
            away_metrics = prop_data.get('away_metrics', {})
            
            # Match the player's FanTeam club string to determine home or away orientation
            norm_team = team.lower()
            is_home = False
            if prop_data.get('home_team') and norm_team in prop_data.get('home_team').lower():
                is_home = True
                
            match_context = home_metrics if is_home else away_metrics
            
            # Pull metrics with solid structural fallbacks if mapping returns empty
            team_xG = match_context.get('expected_goals_for', 1.35)
            team_xGA = match_context.get('expected_goals_against', 1.35)
            team_cs_prob = match_context.get('clean_sheet_prob', 0.25)

            # Retrieve historical base variables
            profile = baselines.get(last_name, baselines.get(fanteam_full_name, {}))
            projected_minutes = profile.get('Expected_Minutes', 82.0 if position in ['GK', 'DEF'] else 72.0)
            save_pct = profile.get('Save_Pct', 0.70)
            assist_share = profile.get('Assist_Share', 0.12 if position == 'MID' else (0.08 if position == 'FWD' else 0.02))
            cards_per_90 = profile.get('Cards_Per_90', 0.15)
            net_impact_per_90 = profile.get('Net_Impact_Per_90', 1.5 if position in ['MID', 'FWD'] else 0.8)

            # Initialize Projection Breakdown
            xPts = 0.0
            
            # 1. DURABILITY & APPEARANCE METRICS
            # Probability models for critical minute thresholds
            prob_start = 1.0 if projected_minutes > 45 else 0.1
            prob_60_mins = 0.92 if projected_minutes >= 70 else (0.15 if projected_minutes > 20 else 0.0)
            prob_full_match = 0.85 if projected_minutes >= 90 else (0.10 if projected_minutes > 75 else 0.0)
            
            xPts += prob_start * self.scoring['appearance']
            xPts += prob_60_mins * self.scoring['mins_60_bonus']
            xPts += prob_full_match * self.scoring['full_match_bonus'].get(position, 0.0)

            # 2. ATTACKING OUTPUT (GOALS & ASSISTS)
            if goal_odds:
                prob_anytime_goal = self.odds_to_probability(goal_odds)
                # Convert anytime probability to an unbounded volume target using Poisson logic
                exp_goals = -math.log(1.0 - min(0.99, prob_anytime_goal))
            else:
                # Scaled baseline share of team's market-implied xG
                goal_share = 0.28 if position == 'FWD' else (0.14 if position == 'MID' else 0.03)
                exp_goals = team_xG * goal_share * (projected_minutes / 90.0)

            xPts += exp_goals * self.scoring['goals'].get(position, 4.0)
            
            # Expected Assists calculation derived from team expected goal generation
            exp_assists = team_xG * assist_share * (projected_minutes / 90.0)
            xPts += exp_assists * self.scoring['assists']

            # 3. SHOTS ON TARGET
            sot_multiplier = self.scoring['shots_on_target'].get(position, 0.4)
            if sot_odds:
                prob_over_sot = self.odds_to_probability(sot_odds)
                # Maps standard over/under line to a continuous linear expectation volume
                estimated_sot = sot_line * prob_over_sot * 1.18
            else:
                positional_sot_base = {'FWD': 1.15, 'MID': 0.75, 'DEF': 0.22, 'GK': 0.02}
                estimated_sot = positional_sot_base.get(position, 0.2) * (projected_minutes / 90.0)
                
            xPts += estimated_sot * sot_multiplier

            # 4. DEFENSIVE STABILITY & GOAL DEDUCTIONS
            # Clean sheets require cross-dependency of the team hitting a clean sheet AND player lasting 60 mins
            xPts += (team_cs_prob * prob_60_mins) * self.scoring['clean_sheet'].get(position, 0.0)
            
            # Apply distribution calculation for non-linear goal concession point hits
            if position in ['GK', 'DEF']:
                expected_gc_penalty = self.calculate_expected_conceded_penalty(team_xGA)
                xPts += expected_gc_penalty  # Penalty value is natively calculated as negative

            # Goalkeeper Save Metric Volume Projection
            if position == 'GK':
                # Map expected opposition shots target volume via baseline team defensive metrics
                opp_shots_on_target = team_xGA * 3.2
                expected_saves = opp_shots_on_target * save_pct * (projected_minutes / 90.0)
                xPts += expected_saves * self.scoring['save']

            # 5. DISCIPLINARY & PERIPHERAL IMPACTS
            # Cards risk exposure model scaled to game time
            expected_cards = cards_per_90 * (projected_minutes / 90.0)
            # Allocation weight: 90% yellow probability, 10% direct red probability
            xPts += (expected_cards * 0.90) * self.scoring['yellow_card']
            xPts += (expected_cards * 0.10) * self.scoring['red_card']

            # Micro-scoring peripheral balance execution (+0.3 / -0.3 stats combined)
            total_projected_impact_actions = net_impact_per_90 * (projected_minutes / 90.0)
            # Assuming a net positive return framework for standard active players
            xPts += (total_projected_impact_actions * 0.60) * self.scoring['impact_positive']
            xPts += (total_projected_impact_actions * 0.40) * self.scoring['impact_negative']

            rows.append({
                'Player': fanteam_full_name,
                'Team': team,
                'Position': position,
                'Salary': salary,
                'Projected_xPts': round(xPts, 2),
                'Live_Market_Mapped': 'Yes' if (goal_odds or sot_odds) else 'No',
                'Exp_Goals': round(exp_goals, 3),
                'Exp_SOT': round(estimated_sot, 2),
                'Team_xG': round(team_xG, 2),
                'Team_xGA': round(team_xGA, 2)
            })
            
        return pd.DataFrame(rows)
