import streamlit as st
import pandas as pd
from single_game.projections import calculate_projections

# 1. Page Global Configurations
st.set_page_config(
    page_title="World Cup Optimizer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚽ World Cup Slate & Showdown Optimizer")

# 2. Sidebar Configuration Layout & Data Pipelines
st.sidebar.header("Advanced Projection Inputs")
user_api_key = st.sidebar.text_input("The Odds API Secret Key (Optional)", type="password", help="Enter your key from the-odds-api.com to unlock live prop data ingestion.")

st.sidebar.subheader("Match Odds Configuration")
team_a = st.sidebar.text_input("Team A Code", "SUI").upper().strip()
team_a_xG = st.sidebar.slider(f"{team_a} Expected Goals (xG)", 0.2, 4.0, 1.8, 0.1)
team_a_sot = st.sidebar.slider(f"{team_a} Expected Shots on Target", 1.0, 12.0, 5.5, 0.5)
team_a_cs = st.sidebar.slider(f"{team_a} Clean Sheet Probability", 0.05, 0.95, 0.35, 0.05)

st.sidebar.subheader("Opponent Configuration")
team_b = st.sidebar.text_input("Team B Code", "QAT").upper().strip()
team_b_xG = st.sidebar.slider(f"{team_b} Expected Goals (xG)", 0.2, 4.0, 0.9, 0.1)
team_b_sot = st.sidebar.slider(f"{team_b} Expected Shots on Target", 1.0, 12.0, 3.0, 0.5)
team_b_cs = st.sidebar.slider(f"{team_b} Clean Sheet Probability", 0.05, 0.95, 0.15, 0.05)

# Pack odds into a structured dictionary matching the projections engine blueprint
match_odds_package = {
    team_a: {'xG': team_a_xG, 'Team_xSoT': team_a_sot, 'CS_odds': team_a_cs},
    team_b: {'xG': team_b_xG, 'Team_xSoT': team_b_sot, 'CS_odds': team_b_cs}
}

# 3. Landing Dashboard Information Layout
st.markdown("""
Welcome to the production environment for the World Cup Lineup Optimizer. Navigate using the sidebar to adjust live match parameters, manage tracking profiles, and optimize arrays.
""")

st.write("---")

# 4. Centralized Projection Processing Core
st.subheader("1. Ingest Slate & Generate Projections")
uploaded_file = st.file_uploader("Upload FanTeam Player Pool CSV File", type=["csv"], help="Upload your raw player slate CSV exported directly from the FanTeam contest portal.")

if uploaded_file is not None:
    # Read uploaded slate file
    raw_df = pd.read_csv(uploaded_file)
    
    st.info(f"Loaded {len(raw_df)} players from pool file. Generating projections via stochastic engines...")
    
    with st.spinner("Executing Survival Analysis, Poisson Thinning, and Skellam Distributions..."):
        # Fire calculations across the projections script
        processed_projections = calculate_projections(raw_df, match_odds_package, api_key=user_api_key)
        
    # Render outputs directly on the primary dashboard frame
    st.success("Stochastic Projections Successfully Calculated!")
    
    # Check what columns exist to construct an elegant visual overview
    display_cols = ['Name', 'Position', 'Price', 'xPts']
    team_col = 'Club' if 'Club' in processed_projections.columns else ('Team' if 'Team' in processed_projections.columns else None)
    if team_col:
        display_cols.insert(1, team_col)
        
    st.dataframe(
        processed_projections[[c for c in display_cols if c in processed_projections.columns]],
        use_container_width=True,
        hide_index=True
    )
    
    # Store projections globally within Streamlit session state to make them visible to solvers
    st.session_state['current_projections'] = processed_projections

else:
    st.warning("Please upload a player pool CSV file in the selector widget above to activate the calculation pipeline.")

st.write("---")

# 5. Core Operational Descriptions
st.subheader("Optimization Framework Modules")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    #### 🎯 Single Game (Showdown Mode)
    * Adjust fine-tuned match parameters and weights.
    * Manipulate dynamic expected scores on the fly.
    * Generate localized lineup variations with custom stacking configurations.
    """)

with col2:
    st.markdown("""
    #### 📊 Multi-Game (Slate Mass-Entry)
    * Maximize point outputs using Mixed-Integer Linear Programming (MILP).
    * Restrict risk utilizing defensive pairing stacking penalties.
    * Enforce exposure controls to prevent single point-of-failure vulnerabilities.
    """)