import streamlit as st
import pandas as pd
from single_game.main import run_pipeline_orchestration

st.set_page_config(page_title="World Cup Lineup Optimizer", layout="wide")

st.title("🏆 World Cup FanTeam Lineup Optimizer")
st.write("Upload your FanTeam player pool CSV and integrate real-time market odds.")

st.sidebar.header("1. Upload Slate Data")
# The file uploader widget
uploaded_csv = st.sidebar.file_uploader("Upload FanTeam Player Pool (CSV)", type=['csv'])

st.sidebar.header("2. Run Engine")
if st.sidebar.button("Run Real-Time Data Pipeline"):
    if uploaded_csv is None:
        st.error("Please upload a FanTeam CSV file first!")
    else:
        with st.spinner("Processing CSV and fetching live odds from the API..."):
            try:
                # Read the uploaded CSV into a Pandas DataFrame
                fanteam_df = pd.read_csv(uploaded_csv)
                
                # Pass the CSV data into our orchestration pipeline
                player_pool_df = run_pipeline_orchestration(fanteam_df)
                
                st.subheader("📊 Consolidated Player Pool Projection Output")
                st.dataframe(player_pool_df.sort_values(by="Projected_xPts", ascending=False), width="stretch")
                
                st.success("Pipeline complete! Head to the Single Game or Multi Game tabs to build your lineups.")
                
                # Save to session state so the optimizers can access it
                st.session_state['player_pool'] = player_pool_df
                
            except Exception as e:
                st.error(f"Pipeline error: {e}")