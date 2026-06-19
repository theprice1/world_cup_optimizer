import streamlit as st
import pandas as pd
from single_game.data_pipeline import LiveDataPipeline
from single_game.projections import ProjectionEngine

st.set_page_config(page_title="FanTeam DFS Control Center", layout="wide")

st.title("⚙️ Data Injection Control Center")
st.write("Upload your FanTeam pricing CSV and fetch live Vegas odds to build the projection pool.")

# --- INPUT BLOCK ---
col1, col2 = st.columns(2)

with col1:
    api_key = st.text_input("The Odds API Key", type="password", help="Enter your live API key here.")
    
with col2:
    uploaded_file = st.file_uploader("Upload FanTeam Salary CSV", type=["csv"])

# --- PIPELINE EXECUTION ---
if st.button("🚀 Run Live Data Pipeline", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Please enter your API key to fetch live odds.")
    elif not uploaded_file:
        st.error("⚠️ Please upload the FanTeam pricing CSV.")
    else:
        with st.status("Initializing Data Pipeline...", expanded=True) as status:
            try:
                # 1. Fetch Odds
                st.write("📡 Connecting to The Odds API...")
                pipeline = LiveDataPipeline(odds_api_key=api_key)
                live_data = pipeline.fetch_player_props()
                
                # 2. Parse Data
                st.write("🧩 Parsing shots on target and goalscorer probabilities...")
                parsed_props = pipeline.parse_shots_on_target_odds(live_data)
                
                # 3. Get Baselines
                st.write("📚 Loading historical baselines...")
                baselines = pipeline.scrape_fbref_historical_baselines()
                
                # 4. Load CSV & Build Projections
                st.write("🧮 Calculating Expected Fantasy Points (xPts)...")
                fanteam_df = pd.read_csv(uploaded_file)
                engine = ProjectionEngine()
                projections_df = engine.build_projections_dataframe(fanteam_df, baselines, parsed_props)
                
                # 5. Save to Session State! (This is what the Optimizer page is looking for)
                st.session_state["player_projections"] = projections_df
                
                status.update(label="Pipeline Complete!", state="complete", expanded=False)
                
                st.success("✅ Projections successfully loaded into memory! You can now navigate to the 'Single Game UI' page on the left sidebar.")
                
                # Show a preview
                st.subheader("📊 Projection Preview")
                st.dataframe(projections_df.sort_values(by="Projected_xPts", ascending=False).head(15), use_container_width=True)

            except Exception as e:
                status.update(label="Pipeline Failed", state="error")
                st.error(f"Execution Error: {e}")
