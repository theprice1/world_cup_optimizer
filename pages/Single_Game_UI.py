import streamlit as st
from single_game.optimizer import LineupOptimizer

st.set_page_config(page_title="Single Game Optimizer", layout="wide")

st.title("⚡ Single-Game Lineup Solver")
st.write("Constructs the mathematically perfect showdown roster based on live market odds calculations.")

# Check if data exists from the main page pipeline execution
if 'player_pool' not in st.session_state:
    st.warning("⚠️ No active player pool data found. Please run the pipeline on the main Homepage app first to fetch live odds.")
else:
    player_df = st.session_state['player_pool']

    # Layout configuration columns
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Optimizer Tuning")
        budget_input = st.slider("Salary Budget Cap (M)", 30.0, 100.0, 50.0, step=0.5)
        max_team_input = st.slider("Max Players per Team", 1, 4, 3, step=1)
        roster_size_input = st.slider("Roster Size", 4, 11, 5, step=1)
        
        run_optimization = st.button("Calculate Optimal Lineup", type="primary")

    with col2:
        if run_optimization:
            st.subheader("🏆 Optimal Lineup Output")
            
            # Run our Linear Programming solver class
            opt = LineupOptimizer(player_df)
            optimal_roster = opt.solve_optimal_lineup(
                budget=budget_input, 
                max_per_team=max_team_input, 
                roster_size=roster_size_input
            )
            
            if optimal_roster is not None:
                # Display the team
                st.dataframe(optimal_roster, use_container_width=True)
                
                # Dynamic summary metrics calculations
                total_cost = optimal_roster['Salary'].sum()
                total_xpts = optimal_roster['Projected_xPts'].sum()
                
                metric_col1, metric_col2 = st.columns(2)
                metric_col1.metric("Total Lineup Cost", f"{total_cost:.1f}M / {budget_input:.1f}M")
                metric_col2.metric("Total Expected Points (w/ Captain)", f"{total_xpts:.2f} xPts")
            else:
                st.error("No valid lineup can be formed with the current criteria constraints. Try increasing the budget cap or lowering roster size.")
        else:
            st.info("Adjust the parameter tuning settings on the left sidebar and click calculate to generate your mathematical lineup.")