import requests
import pandas as pd
import re
import unicodedata
import math

class LiveDataPipeline:
    def __init__(self, odds_api_key=None):
        self.api_key = odds_api_key

    def normalize_name(self, name):
        """Cleans accents, punctuation, and extra spaces for raw token matching."""
        if not name or not isinstance(name, str):
            return ""
        name = name.lower().strip()
        name = name.replace('.', ' ').replace('-', ' ')
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        name = re.sub(r'[^a-z0-9\s]', '', name)
        return " ".join(name.split())

    def fetch_player_props(self, sport="soccer_fifa_world_cup", regions="eu"):
        """Two-step fetch required by The Odds API for player props and team baselines."""
        if not self.api_key:
            return None
            
        # STEP 1: Query the main endpoint for team markets (h2h, totals, btts)
        events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        events_params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": "h2h,totals,btts",
            "oddsFormat": "decimal"
        }
        
        try:
            events_response = requests.get(events_url, params=events_params, timeout=10)
            if events_response.status_code != 200:
                return None
            events_data = events_response.json()
        except Exception:
            return None

        # Build a team matrix lookup from Step 1 data
        team_market_map = self.parse_team_markets(events_data)
        all_props = []

        # STEP 2: Loop through Event IDs to fetch player-specific props
        for event in events_data:
            event_id = event.get('id')
            home_team = event.get('home_team')
            away_team = event.get('away_team')
            if not event_id:
                continue
                
            props_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds"
            props_params = {
                "apiKey": self.api_key,
                "regions": regions,
                "markets": "player_shots_on_target,player_goal_scorer_anytime",
                "oddsFormat": "decimal"
            }
            
            try:
                props_response = requests.get(props_url, params=props_params, timeout=15)
                if props_response.status_code == 200:
                    event_props_data = props_response.json()
                    
                    # Inject calculated team-level data into the event props object
                    event_props_data['team_metrics'] = {
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_metrics': team_market_map.get(home_team, {}),
                        'away_metrics': team_market_map.get(away_team, {})}
                    
                    all_props.append(event_props_data)
            except Exception:
                continue
                
        return all_props if len(all_props) > 0 else None

    def parse_team_markets(self, events_data):
        """Calculates expected goals (xG) and clean sheet probabilities for each team."""
        team_map = {}
        for event in events_data:
            home = event.get('home_team')
            away = event.get('away_team')
            
            # Default fallbacks
            total_goals_line = 2.5
            prob_over = 0.50
            prob_btts_yes = 0.55
            
            # Extract markets from the primary bookmaker (usually the first one returned)
            bookmakers = event.get('bookmakers', [])
            if not bookmakers:
                continue
            
            markets = bookmakers[0].get('markets', [])
            for market in markets:
                if market['key'] == 'totals':
                    outcome = market['outcomes'][0]
                    total_goals_line = outcome.get('point', 2.5)
                    price = outcome.get('price', 2.0)
                    if outcome.get('name') == 'Over':
                        prob_over = 1.0 / price
                    else:
                        prob_over = 1.0 - (1.0 / price)
                elif market['key'] == 'btts':
                    for outcome in market['outcomes']:
                        if outcome['name'] == 'Yes':
                            prob_btts_yes = 1.0 / outcome['price']

            # --- Implied Total Goals Calculation (Using basic Gallagher/Poisson relation) ---
            # Approximating expected total game goals based on the 2.5 line projection
            implied_total_game_goals = total_goals_line * (prob_over / 0.5) * 0.95
            
            # Clean sheet approximation derived via Both Teams To Score (BTTS) probability
            # P(Clean Sheet) is highly correlated with 1 - P(BTTS) weighted by match favoritism
            prob_home_cs = max(0.05, 1.0 - prob_btts_yes) * 1.1
            prob_away_cs = max(0.05, 1.0 - prob_btts_yes) * 0.85
            
            # Allocate total match goals to individual teams
            # Normalizing to avoid split extremes
            home_xG = implied_total_game_goals * 0.55
            away_xG = implied_total_game_goals * 0.45

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
        if not json_data:
            return {}

        player_prop_map = {}
        for event in json_data:
            # Extract team metrics metadata injected during the fetch phase
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
                            
                            if not player_name:
                                continue
                                
                            norm_name = self.normalize_name(player_name)
                            
                            # Tie the player back to their specific team context
                            # The Odds API properties don't explicitly list player team inside outcomes, 
                            # so we initialize with a default blank template to be resolved during string match
                            if norm_name not in player_prop_map:
                                player_prop_map[norm_name] = {
                                    'sot_over_odds': None, 
                                    'sot_line': 1.5, 
                                    'goal_odds': None,
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'home_metrics': home_stats,
                                    'away_metrics': away_stats
                                }
                            
                            if market['key'] == 'player_shots_on_target' and "Over" in outcome_name:
                                line_match = re.search(r'\d+\.\d+|\d+', outcome_name)
                                line_val = float(line_match.group()) if line_match else 0.5
                                player_prop_map[norm_name]['sot_over_odds'] = price
                                player_prop_map[norm_name]['sot_line'] = line_val
                                
                            elif market['key'] == 'player_goal_scorer_anytime':
                                player_prop_map[norm_name]['goal_odds'] = price
                                        
        return player_prop_map

    def scrape_fbref_historical_baselines(self):
        return {}
