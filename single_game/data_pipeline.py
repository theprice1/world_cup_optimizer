import requests
import pandas as pd
import re
import unicodedata
import math

class LiveDataPipeline:
    def __init__(self, odds_api_key=None):
        self.api_key = odds_api_key

    def normalize_name(self, name):
        if not name or not isinstance(name, str): return ""
        name = name.lower().strip()
        name = name.replace('.', ' ').replace('-', ' ')
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        name = re.sub(r'[^a-z0-9\s]', '', name)
        return " ".join(name.split())

    def fetch_player_props(self, sport="soccer_fifa_world_cup", regions="eu"):
        if not self.api_key:
            print("CRITICAL: API Key is missing.")
            return None
            
        # STEP 1: Strict h2h and totals ONLY to avoid INVALID_MARKET 400 error
        events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        events_params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        
        print(f"Fetching team match baselines...")
        events_response = requests.get(events_url, params=events_params, timeout=10)
        
        # Stop swallowing errors. Let's see exactly what the API server says.
        if events_response.status_code != 200:
            print(f"ERROR Step 1: {events_response.status_code} - {events_response.text}")
            return None
            
        events_data = events_response.json()
        team_market_map = self.parse_team_markets(events_data)
        all_props = []

        print(f"Found {len(events_data)} matches. Fetching player props...")
        # STEP 2: Player specific odds
        for event in events_data:
            event_id = event.get('id')
            home_team = event.get('home_team')
            away_team = event.get('away_team')
            
            props_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds"
            props_params = {
                "apiKey": self.api_key,
                "regions": regions,
                "markets": "player_shots_on_target,player_goal_scorer_anytime",
                "oddsFormat": "decimal"
            }
            
            props_response = requests.get(props_url, params=props_params, timeout=15)
            if props_response.status_code == 200:
                event_props_data = props_response.json()
                event_props_data['team_metrics'] = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_metrics': team_market_map.get(home_team, {}),
                    'away_metrics': team_market_map.get(away_team, {})
                }
                all_props.append(event_props_data)
            else:
                print(f"Failed to fetch props for {home_team} vs {away_team}: {props_response.status_code}")
                
        return all_props if len(all_props) > 0 else None

    def parse_team_markets(self, events_data):
        team_map = {}
        for event in events_data:
            home = event.get('home_team')
            away = event.get('away_team')
            
            total_goals_line = 2.5
            prob_over = 0.50
            prob_home_win = 0.33
            prob_away_win = 0.33
            
            bookmakers = event.get('bookmakers', [])
            if bookmakers:
                markets = bookmakers[0].get('markets', [])
                for market in markets:
                    if market['key'] == 'totals':
                        outcome = market['outcomes'][0]
                        total_goals_line = outcome.get('point', 2.5)
                        price = outcome.get('price', 2.0)
                        prob_over = 1.0 / price if outcome.get('name') == 'Over' else 1.0 - (1.0 / price)
                    elif market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if outcome['name'] == home:
                                prob_home_win = 1.0 / outcome['price']
                            elif outcome['name'] == away:
                                prob_away_win = 1.0 / outcome['price']

            implied_total_game_goals = total_goals_line * (prob_over / 0.5) * 0.95
            total_win_prob = prob_home_win + prob_away_win
            
            home_share = prob_home_win / total_win_prob if total_win_prob > 0 else 0.5
            away_share = prob_away_win / total_win_prob if total_win_prob > 0 else 0.5

            home_xG = implied_total_game_goals * home_share
            away_xG = implied_total_game_goals * away_share

            # Exact Poisson process model for Clean Sheets
            prob_home_cs = math.exp(-away_xG)
            prob_away_cs = math.exp(-home_xG)

            team_map[home] = {
                'expected_goals_for': round(home_xG, 2),
                'expected_goals_against': round(away_xG, 2),
                'clean_sheet_prob': round(min(0.85, prob_home_cs), 3)
            }
            team_map[away] = {
                'expected_goals_for': round(away_xG, 2),
                'expected_goals_against': round(home_xG, 2),
                'clean_sheet_prob': round(min(0.85, prob_away_cs), 3)
            }
        return team_map

    def parse_shots_on_target_odds(self, json_data):
        if not json_data: return {}

        player_prop_map = {}
        for event in json_data:
            metrics_meta = event.get('team_metrics', {})
            home_team = metrics_meta.get('home_team')
            away_team = metrics_meta.get('away_team')
            home_stats = metrics_meta.get('home_metrics', {})
            away_stats = metrics_meta.get('away_metrics', {})

            for bookmaker in event.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] in ['player_shots_on_target', 'player_goal_scorer_anytime']:
                        for outcome in market.get('outcomes', []):
                            player_name = outcome.get('description') or outcome.get('name')
                            outcome_name = outcome.get('name')
                            price = outcome.get('price')
                            
                            if not player_name: continue
                            norm_name = self.normalize_name(player_name)
                            
                            if norm_name not in player_prop_map:
                                player_prop_map[norm_name] = {
                                    'sot_over_odds': None, 'sot_line': 0.5, 'goal_odds': None,
                                    'home_team': home_team, 'away_team': away_team,
                                    'home_metrics': home_stats, 'away_metrics': away_stats
                                }
                            
                            # Standardize mapping to the Over 0.5 line for mathematical consistency
                            if market['key'] == 'player_shots_on_target' and outcome_name == 'Over':
                                point_line = outcome.get('point', 0.5)
                                if point_line == 0.5 or player_prop_map[norm_name]['sot_over_odds'] is None:
                                    player_prop_map[norm_name]['sot_over_odds'] = price
                                    player_prop_map[norm_name]['sot_line'] = point_line
                                
                            elif market['key'] == 'player_goal_scorer_anytime' and outcome_name == 'Yes':
                                # Map the lowest price (highest probability) to avoid stragglers
                                current_odds = player_prop_map[norm_name]['goal_odds']
                                if current_odds is None or price < current_odds:
                                    player_prop_map[norm_name]['goal_odds'] = price
                                        
        return player_prop_map