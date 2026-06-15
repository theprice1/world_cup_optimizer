import streamlit as st
from single_game.data_pipeline import LiveDataPipeline
from single_game.projections.py import ProjectionEngine  # Correct relative path reference

def run_pipeline_orchestration():
    """
    Retrieves safe credentials, executes api tasks, and returns 
    a finalized DataFrame formatted cleanly for the Linear Programming Solver.
    """
    # Pull safe environment variables from the .streamlit runtime context safely
    api_key = st.secrets.get("ODDS_API_KEY", None)
    
    pipeline = LiveDataPipeline(odds_api_key=api_key)
    engine = ProjectionEngine()
    
    # Ingestion steps
    baselines = pipeline.scrape_fbref_historical_baselines()
    
    # Extract market props
    raw_prop_json = pipeline.fetch_player_props()
    props_map = pipeline.parse_shots_on_target_odds(raw_prop_json)
    
    # Compile projections
    final_pool_df = engine.build_projections_dataframe(baselines, props_map)
    return final_pool_df

if __name__ == "__main__":
    # Test suite run execution verification
    print("Executing standalone pipeline test run...")
    import mock
    # Provide a placeholder structure for local non-streamlit testing frameworks if executed directly
    if not hasattr(st, "secrets"):
        st.secrets = {"ODDS_API_KEY": "MOCK_KEY"}
    df = run_pipeline_orchestration()
    print(df.to_string())