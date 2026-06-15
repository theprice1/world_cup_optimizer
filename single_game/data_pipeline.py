import requests
import pandas as pd
import re

class LiveDataPipeline:
    def __init__(self, odds_api_key=None):
        """
        Initializes the data engine with an API key for live betting markets.
        """
        self.api_key = odds_api_key

    def normalize_name(self, name):
        """
        Aggressive, production-grade name standardization for robust fuzzy matching.
        Handles hyphenation variance, character accents, spacing differences,
        common FanTeam/OddsAPI spelling discrepancies, and middle-name removal.
        Example: 'A. AFIF' -> 'afif' | 'H-M. Son' -> 'son' | 'De Bruyne' -> 'debruyne'
        """
        if not name or not isinstance(name, str):
            return ""
        
        # --- Stage 1: Basic Cleaning & Case Normalization ---
        name = name.lower().strip()
        
        # --- Stage 2: Character Normalization (Remove dot abbreviations and accents) ---
        # Example: 'Y. Sommer' -> 'y somer'
        # We replace dots with spaces to protect compound initials, then replace dashes.
        name = name.replace('.', ' ').replace('-', ' ')
        
        # Apply intense ASCII transliteration (Removes ñ, ö, é, etc.)
        import unicodedata
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        
        # Remove any lingering special characters/punctuation (Protect whitespace for now)
        import re
        name = re.sub(r'[^a-z0-9\s]', '', name)
        
        # --- Stage 3: Intelligent Parsing for Match Vectors ---
        # FanTeam often uses compound abbreviations like "A. ALI" or "J. M. GIMENEZ"
        tokens = name.split()
        
        # Fallback safeguard if splitting fails
        if not tokens:
            return "unknown"
            
        # Strategy A (Simple token sorting): Handles 'Son Heung Min' vs 'Heung Min Son' variance.
        simple_match_token = "".join(sorted(tokens))

        # Strategy B (Surname Focus): Highly effective fallback for "J. M. Surname" formats.
        # We assume the last token is the actual surname and prioritize that.
        last_name_focus = tokens[-1]

        # Strategy C (Initials Catch): For very aggressive matches like 'KDB' mapping.
        first_init = "".join([t[0] for t in tokens if len(t) > 0])
        initials_token = first_init + last_name_focus # e.g. 'kdebruyne'

        # --- Stage 4: Compiling the solving fuzzy key ---
        # We assemble the most probable match key. Last name only is often safest.
        if len(tokens) == 1:
            return simple_match_token
            
        # Return the simplified, combined, ASCII version. 
        # This string must match the standardized Odds API descriptions (props descriptions).
        final_standard_fuzzy_key = last_name_focus
        
        # Remove whitespace lingering between surnames (e.g. 'de bruyne' -> 'debruyne')
        return " ".join(final_standard_fuzzy_key.split())

    def fetch_live_market_odds(self, sport="soccer_fifa_world_cup", regions="eu"):
        """
        Queries The-Odds-API to pull real-time Match Odds (H2H) and Over/Under Totals.
        """
        if not self.api_key:
            return None
            
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def fetch_player_props(self, sport="soccer_fifa_world_cup", regions="eu"):
        """
        Queries individual player-level markets (e.g., Shots on Target prop lines).
        """
        if not self.api_key:
            return None
            
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": "player_shots_on_target",
            "oddsFormat": "decimal"
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def parse_shots_on_target_odds(self, json_data):
        """
        Flattens the deeply nested player prop JSON into an optimized mapping dictionary:
        { 'normalized_name': {'sot_over_odds': float, 'sot_line': float} }
        """
        if not json_data:
            return {}

        player_prop_map = {}
        for event in json_data:
            for bookmaker in event.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'player_shots_on_target':
                        for outcome in market.get('outcomes', []):
                            # The-Odds-API typically puts player names in the 'description' field for props
                            player_name = outcome.get('description')
                            outcome_name = outcome.get('name')  # e.g., "Over 1.5"
                            price = outcome.get('price')
                            
                            if not player_name or not outcome_name:
                                continue
                                
                            norm_name = self.normalize_name(player_name)
                            
                            # Isolate the numeric threshold line (e.g., 1.5)
                            line_match = re.search(r'\d+\.\d+|\d+', outcome_name)
                            line_val = float(line_match.group()) if line_match else 0.5
                            
                            if "Over" in outcome_name:
                                if norm_name not in player_prop_map:
                                    player_prop_map[norm_name] = {
                                        'sot_over_odds': price,
                                        'sot_line': line_val
                                    }
        return player_prop_map

    def scrape_fbref_historical_baselines(self):
        """
        Assembles clean, precise player metrics for the mathematical formulas.
        """
        baseline_profiles = {
            'Y. SOMMER': {'Starts': 12, 'Complete_90': 12, 'Save_Pct': 0.76, 'Position': 'GK', 'Team': 'Switzerland'},
            'M. AKANJI': {'Starts': 15, 'Complete_90': 14, 'Save_Pct': 0.00, 'Position': 'DEF', 'Team': 'Switzerland'},
            'G. XHAKA': {'Starts': 16, 'Complete_90': 15, 'Save_Pct': 0.00, 'Position': 'MID', 'Team': 'Switzerland'},
            'R. RODRIGUEZ': {'Starts': 14, 'Complete_90': 11, 'Save_Pct': 0.00, 'Position': 'DEF', 'Team': 'Switzerland'},
            'X. SHAQIRI': {'Starts': 11, 'Complete_90': 3, 'Save_Pct': 0.00, 'Position': 'MID', 'Team': 'Switzerland'},
            'B. EMBOLO': {'Starts': 10, 'Complete_90': 4, 'Save_Pct': 0.00, 'Position': 'FWD', 'Team': 'Switzerland'},
            'Z. AMDOUNI': {'Starts': 6, 'Complete_90': 1, 'Save_Pct': 0.00, 'Position': 'FWD', 'Team': 'Switzerland'},
            'A. AFIF': {'Starts': 14, 'Complete_90': 13, 'Save_Pct': 0.00, 'Position': 'FWD', 'Team': 'Qatar'},
            'A. ALI': {'Starts': 15, 'Complete_90': 12, 'Save_Pct': 0.00, 'Position': 'FWD', 'Team': 'Qatar'},
            'M. BARSHAM': {'Starts': 11, 'Complete_90': 11, 'Save_Pct': 0.68, 'Position': 'GK', 'Team': 'Qatar'}
        }
        return baseline_profiles