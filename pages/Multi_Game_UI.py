import streamlit as st
from multi_game.multi_game_optimizer import MultiGameOptimizer

st.set_page_config(page_title="Multi Game Optimizer", layout="wide")

st.title("⚽ Multi-Game Full Slate Solver")
st.write("Generates an optimal 11-player squad across multiple World Cup fixtures using integrated market lines.")

if 'player_pool' not in st.session_state:
    st.warning("⚠️ No active player pool data found. Please run the pipeline on the main Homepage app first to fetch live odds.")
else:
    player_df = st.session_state['player_pool']

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Slate Settings")
        budget_input = st.slider("Roster Budget Cap (M)", 80.0, 120.0, 100.0, step=0.5)
        max_team_input = st.slider("Max Players per Country", 2, 5, 3, step=1)
        
        run_optimization = st.button("Build Optimal 11-Man Squad", type="primary")

    with col2:
        if run_optimization:
            st.subheader("🏆 Optimal 11-Player Lineup")
            
            optimizer = MultiGameOptimizer(player_df)
            optimal_roster = optimizer.solve_slate(budget=budget_input, max_per_team=max_team_input)
            
            if optimal_roster is not None:
                st.dataframe(optimal_roster, use_container_width=True)
                
                total_cost = optimal_roster['Salary'].sum()
                total_xpts = optimal_roster['Projected_xPts'].sum()
                
                m1, m2 = st.columns(2)
                m1.metric("Total Roster Cost", f"{total_cost:.1f}M / {budget_input:.1f}M")
                m2.metric("Squad Projected Points", f"{total_xpts:.2f} xPts")
            else:
                st.error("Linear solver failed to find a valid combination. Roster constraints might be too tight for the given budget.")
        else:
            st.info("Click the build button to optimize across the full match slate.")