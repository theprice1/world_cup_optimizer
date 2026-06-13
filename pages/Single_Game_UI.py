import streamlit as st
import pandas as pd
from single_game.projections import calculate_projections
from single_game.optimizer import run_optimization

st.set_page_config(page_title="Single Game", page_icon="⚽", layout="wide")
st.title("⚽ Single Game Showdown Module")

if "is_optimizing" not in st.session_state:
    st.session_state.is_optimizing = False

# Sidebar Configuration
st.sidebar.header("Match Weights")
t1 = st.sidebar.text_input("Team 1 Code", value="KOR").upper()
t1_xg = st.sidebar.number_input(f"{t1} xG", value=1.15, step=0.05)
t1_win = st.sidebar.slider(f"{t1} Win Probability", 0.0, 1.0, 0.45)
t1_cs = st.sidebar.slider(f"{t1} Clean Sheet Probability", 0.0, 1.0, 0.32)

t2 = st.sidebar.text_input("Team 2 Code", value="CZE").upper()
t2_xg = st.sidebar.number_input(f"{t2} xG", value=1.05, step=0.05)
t2_win = st.sidebar.slider(f"{t2} Win Probability", 0.0, 1.0, 0.25)
t2_cs = st.sidebar.slider(f"{t2} Clean Sheet Probability", 0.0, 1.0, 0.29)

live_odds = {
    t1: {'xG': t1_xg, 'CS_odds': t1_cs, 'Win_prob': t1_win, 'Loss_prob': t2_win, 'Team_xSoT': 4.5, 'Opp_xSoT': 3.5},
    t2: {'xG': t2_xg, 'CS_odds': t2_cs, 'Win_prob': t2_win, 'Loss_prob': t1_win, 'Team_xSoT': 3.5, 'Opp_xSoT': 4.5}
}

st.sidebar.header("Optimization Constraints")
budget = st.sidebar.number_input("Budget Cap", value=59.0, step=0.5)
num_lineups = st.sidebar.number_input("Lineup Count", min_value=1, max_value=50, value=10)
max_overlap = st.sidebar.slider("Max Player Overlap", 1, 4, 4)

uploaded_file = st.file_uploader("Upload Showdown CSV", type="csv")

if uploaded_file is not None:
    # Direct memory read instead of saving to disk
    raw_df = pd.read_csv(uploaded_file)
    raw_df.columns = raw_df.columns.str.strip()
    if 'Price' in raw_df.columns:
        raw_df['Price'] = raw_df['Price'].astype(float)
        
    projected_df = calculate_projections(raw_df, live_odds)
    
    st.subheader("Edit Pool Projections")
    edited_df = st.data_editor(projected_df, num_rows="dynamic", use_container_width=True, hide_index=True)

    if st.button("Run Optimizer Engine", type="primary", disabled=st.session_state.is_optimizing):
        st.session_state.is_optimizing = True
        st.rerun()

if st.session_state.is_optimizing:
    with st.spinner("Processing optimization matrices..."):
        try:
            results_df = run_optimization(edited_df, budget, num_lineups, max_overlap)
            if results_df.empty:
                st.error("No valid solutions found.")
            else:
                st.success("Lineups optimized successfully.")
                tabs = st.tabs([f"Lineup {i}" for i in range(1, num_lineups + 1)])
                for i, tab in enumerate(tabs):
                    with tab:
                        sub = results_df[results_df['Lineup_Num'] == (i + 1)]
                        st.dataframe(sub[['Name', 'Position', 'Price', 'xPts', 'Is_Captain']], use_container_width=True, hide_index=True)
        finally:
            st.session_state.is_optimizing = False