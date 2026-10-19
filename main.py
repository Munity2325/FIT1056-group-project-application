import streamlit as st
from gui.main_dashboard import launch
from app.admin_utils import init_logger, backup_data

if __name__ == "__main__":
    # streamlit reruns this on every click so only set up logging and backup once
    if "backup_done" not in st.session_state:
        init_logger()
        backup_data()
        st.session_state.backup_done = True

    launch()
