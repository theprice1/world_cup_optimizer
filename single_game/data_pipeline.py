import requests
import pandas as pd
import re
import unicodedata

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
        """Two-step fetch required by The Odds API for player props."""
        if not self.api_key:
            return None
            
        # STEP 1: Query the main endpoint to get the specific Event IDs for active matches
        events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        events_params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": "h2h" # Lightweight query just to get the match list and IDs
        }
        
        try:
            events_response = requests.get(events_url, params=events_params, timeout=10)
            if events_response.status_code != 200:
                return None
            events_data = events_response.json()
        except Exception:
            return None

        all_props = []

        # STEP 2: Loop through the Event IDs and query the Event-Specific endpoint
        for event in events_data:
            event_id = event.get('id')
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
                # We increase timeout slightly as event endpoints can be heavier
                props_response = requests.get(props_url, params=props_params, timeout=15)
                if props_response.status_code == 200:
                    event_props_data = props_response.json()
                    all_props.append(event_props_data)
            except Exception:
                continue
                
        # Return the combined master list of all player props across all games
        return all_props if len(all_props) > 0 else None

    def parse_shots_on_target_odds(self, json_data):
        if not json_data:
            return {}

        player_prop_map = {}
        for event in json_data:
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
                            
                            if norm_name not in player_prop_map:
                                player_prop_map[norm_name] = {'sot_over_odds': None, 'sot_line': 1.5, 'goal_odds': None}
                            
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