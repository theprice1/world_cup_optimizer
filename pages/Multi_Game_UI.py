import streamlit as st
import pandas as pd
from multi_game.multi_game_optimizer import SixASideOptimizer

st.set_page_config(page_title="Multi-Game", page_icon="🏆", layout="wide")
st.title("🏆 Multi-Game Slate Optimizer")

if "multi_optimizing" not in st.session_state:
    st.session_state.multi_optimizing = False

# Setup inputs
num_lineups = st.sidebar.number_input("Lineup Count", min_value=1, max_value=100, value=10)
max_overlap = st.sidebar.slider("Max Overlap Rule", 1, 5, 4)
budget = st.sidebar.number_input("Budget Ceiling", value=57.0, step=0.5)
min_budget = st.sidebar.number_input("Budget Floor", value=52.0, step=0.5)
max_exposure = st.sidebar.slider("Max Exposure Cap (%)", 10, 100, 60)
variance = st.sidebar.slider("Applied Projection Variance (%)", 0, 20, 5)
cs_prob = st.sidebar.slider("Global CS Expectation (EV Penalty)", 0.0, 1.0, 0.35)

uploaded_file = st.file_uploader("Upload Multi-Game Slate CSV", type="csv")

if uploaded_file is not None:
    slate_df = pd.read_csv(uploaded_file)
    st.info("CSV loaded completely into system memory.")
    
    if st.button("Generate Mass Lineups", type="primary", disabled=st.session_state.multi_optimizing):
        st.session_state.multi_optimizing = True
        st.rerun()

if st.session_state.multi_optimizing:
    with st.spinner("Processing Linear Optimization Matrix..."):
        try:
            opt = SixASideOptimizer(slate_df, budget, min_budget, max_per_team=4, roster_size=6)
            opt.load_and_preprocess()
            lineups = opt.build_and_solve(num_lineups, max_overlap, max_exposure / 100.0, variance / 100.0, cs_prob)
            
            if not lineups:
                st.error("Infeasible constraints. Relax the parameters and try again.")
            else:
                st.success(f"Generated {len(lineups)} unique lineups.")
                
                # --- EXPOSURE ACCOUNTING & CHARTING ---
                all_players = []
                for l in lineups:
                    all_players.extend(l['Name'].str.title().tolist())
                
                exp_df = pd.DataFrame(all_players, columns=['Player']).value_counts().reset_index(name='Count')
                exp_df['Exposure %'] = round((exp_df['Count'] / len(lineups)) * 100, 1)
                
                st.subheader("🎯 Player Exposure Summary")
                st.bar_chart(exp_df, x='Player', y='Exposure %')
                st.dataframe(exp_df, use_container_width=True, hide_index=True)
                
                st.subheader("📋 Lineup Output Profiles")
                tabs = st.tabs([f"Lineup {i+1}" for i in range(len(lineups))])
                for i, tab in enumerate(tabs):
                    with tab:
                        ldf = lineups[i].copy()
                        st.dataframe(ldf[['Name', 'Club', 'Position', 'Price', 'Points']], use_container_width=True, hide_index=True)
        finally:
            st.session_state.multi_optimizing = False