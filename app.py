import streamlit as st
from single_game.main import run_pipeline_orchestration

st.set_page_config(page_title="World Cup Lineup Optimizer", layout="wide")

st.title("🏆 World Cup FanTeam Lineup Optimizer")
st.write("Integrating real-time statistics pipelines and consensus bookmaker odds into mathematical projections.")

st.sidebar.header("Configuration Panel")
market_mode = st.sidebar.radio("Data Engine Mode", ["Live Betting Odds Market", "Historical Baselines Only"])

if st.sidebar.button("Run Real-Time Data Pipeline"):
    with st.spinner("Connecting to The-Odds-API endpoints and recalculating structural projections..."):
        try:
            player_pool_df = run_pipeline_orchestration()
            
            st.subheader("📊 Consolidated Player Pool Projection Output")
            st.dataframe(player_pool_df.sort_values(by="Projected_xPts", ascending=False), width="stretch")
            
            # Informational status metrics
            total_players = len(player_pool_df)
            mapped_live = player_pool_df[player_pool_df['Live_Market_Mapped'] == 'Yes'].shape[0]
            st.success(f"Successfully processed {total_players} total player vectors. Live lines mapped for {mapped_live} profiles.")
            
            # Session state caching placeholder to allow pass-through access into optimizer.py files
            st.session_state['player_pool'] = player_pool_df
            
        except Exception as e:
            st.error(f"Error executing optimization data ingest paths: {e}")
            st.info("Check that your `.streamlit/secrets.toml` file contains a valid 'ODDS_API_KEY'.")
else:
    st.info("Click 'Run Real-Time Data Pipeline' in the sidebar options panel to execute live API fetches.")