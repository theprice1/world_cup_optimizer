import streamlit as st
import pandas as pd
from single_game.optimizer import LineupOptimizer

st.set_page_config(page_title="FanTeam 5-Man Showdown Optimizer", layout="wide")

st.title("⚽ FanTeam 5-Man Showdown Optimizer")
st.write("Generates optimal 5-a-side lineups with a 1.5x Captain multiplier.")

# --- SIDEBAR DYNAMIC CONTROLS ---
st.sidebar.header("Optimizer Settings")

# 1. Adjustable Budget Slider (Tuned for 5-Man)
budget = st.sidebar.slider("Salary Cap Budget", min_value=35.0, max_value=75.0, value=50.0, step=0.5)

# 2. Maximum Players Allowed per Team Slider
max_players = st.sidebar.slider("Maximum Players per Club", min_value=1, max_value=4, value=3, step=1)

# 3. Match Status Filters
status_mode = st.sidebar.radio("Player Availability Filter", ["All", "Expected", "Starting"])

# 4. Smart Anti-Correlation Toggle
anti_corr = st.sidebar.checkbox("Apply Goalkeeper Anti-Correlation", value=True)

# --- DATA SESSION HANDLING ---
if "player_projections" in st.session_state and st.session_state["player_projections"] is not None:
    df_pool = st.session_state["player_projections"]
    
    st.subheader(f"Available Player Pool ({len(df_pool)} players)")
    
    if st.button("🚀 Calculate 5-Man Optimal Lineup", type="primary"):
        optimizer_engine = LineupOptimizer()
        
        optimized_lineup, logs_msg = optimizer_engine.optimize(
            df=df_pool,
            salary_cap=budget,
            max_per_team=max_players,
            roster_status_filter=status_mode,
            use_correlation=anti_corr
        )
        
        if optimized_lineup is not None:
            st.success(logs_msg)
            
            total_cost = optimized_lineup["Salary"].sum()
            total_pts = optimized_lineup["Projected_xPts"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Projected Lineup Points", f"{total_pts:.2f} xPts")
            col2.metric("Total Lineup Cost", f"{total_cost:.2f}M / {budget:.2f}M")
            col3.metric("Roster Composition", f"{len(optimized_lineup)} / 5 Players")
            
            st.subheader("📋 Your Optimized Lineup")
            # Added Roster_Slot so you can clearly see who the solver picked as Captain
            st.dataframe(optimized_lineup[["Roster_Slot", "Player", "Position", "Team", "Salary", "Projected_xPts"]], use_container_width=True)
        else:
            st.error(logs_msg)
else:
    st.info("💡 Please run the live data injection pipeline first on the home panel.")