import streamlit as st
from single_game.data_pipeline import LiveDataPipeline
from single_game.projections import ProjectionEngine

def run_pipeline_orchestration(fanteam_df):
    """
    Retrieves safe credentials, executes api tasks, and merges 
    the FanTeam CSV data with live API projections.
    """
    api_key = st.secrets.get("ODDS_API_KEY", None)
    
    pipeline = LiveDataPipeline(odds_api_key=api_key)
    engine = ProjectionEngine()
    
    # 1. Fetch live player props
    raw_prop_json = pipeline.fetch_player_props()
    
    # --- CRITICAL API VISIBILITY ---
    if not raw_prop_json:
        st.warning("⚠️ The Odds API returned NO DATA. Player props for this match have not been released by bookmakers yet (usually available 24 hours before kickoff). Using baseline math.")
        props_map = {}
    else:
        props_map = pipeline.parse_shots_on_target_odds(raw_prop_json)
        if len(props_map) == 0:
            st.warning("⚠️ Connected to API, but found 0 player prop odds. Bookmakers haven't opened these lines yet.")
        else:
            st.success(f"✅ Successfully downloaded live prop lines for {len(props_map)} players from The Odds API.")
    
    # 2. Scrape historical baselines
    baselines = pipeline.scrape_fbref_historical_baselines()
    
    # 3. Compile final projections using the uploaded CSV
    final_pool_df = engine.build_projections_dataframe(fanteam_df, baselines, props_map)
    
    return final_pool_df