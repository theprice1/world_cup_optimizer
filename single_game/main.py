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
    
    # 1. Fetch live player props from the API
    raw_prop_json = pipeline.fetch_player_props()
    props_map = pipeline.parse_shots_on_target_odds(raw_prop_json)
    
    # 2. Scrape historical baselines (for players without live odds)
    baselines = pipeline.scrape_fbref_historical_baselines()
    
    # 3. Compile final projections using the uploaded CSV
    final_pool_df = engine.build_projections_dataframe(fanteam_df, baselines, props_map)
    
    return final_pool_df