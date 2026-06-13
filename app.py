import streamlit as st

st.set_page_config(
    page_title="World Cup Optimizer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚽ World Cup Slate & Showdown Optimizer")

st.markdown("""
Welcome to the production environment for the World Cup Lineup Optimizer. Navigate using the sidebar to select your specific optimization module:

* **Single Game (Showdown):** Adjust match weights, manipulate individual projections on the fly, and build a localized set of unique lineups featuring custom stacking and captain structures.
* **Multi-Game (Slate mass-entry):** Optimize 6-a-side slates using deep Mixed-Integer Linear Programming (MILP) with integrated FanTeam Defensive Stacking Penalties and player exposure controls.

*Select a page from the left sidebar to begin.*
""")