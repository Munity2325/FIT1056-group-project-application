import os
import datetime
import streamlit as st
import pandas as pd


def show_report_page(manager, user):
    st.header("Reports")
    st.caption("Reports are grouped and never show client names, contacts or references.")
    col1, col2 = st.columns(2)
    start = col1.date_input("From", datetime.date.today() - datetime.timedelta(days=30))
    end = col2.date_input("To", datetime.date.today())
    if start > end:
        st.warning("The start date must be before the end date.")
        return
    kind = st.radio("Report", ["Demand", "Fairness"], horizontal=True)

    rows = manager.demand_report(start, end) if kind == "Demand" else manager.fairness_report(start, end)
    if not rows:
        st.info("No orders in this period.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    # csv export (FR-27), saved in reports/ and offered as a download
    if st.button("Export CSV"):
        os.makedirs("reports", exist_ok=True)
        path = f"reports/{kind.lower()}_{start}_{end}.csv"
        manager.export_report(rows, path)
        with open(path, "r") as f:
            st.download_button("Download CSV", f.read(), file_name=os.path.basename(path), mime="text/csv")
