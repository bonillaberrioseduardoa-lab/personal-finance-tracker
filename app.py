from pathlib import Path

code = r'''import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
import uuid

st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💰",
    layout="wide"
)

SHEET_NAME = "Personal Finance Tracker"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

HEADERS = {
    "Transactions": [
        "ID", "Date", "Type", "Category", "Amount", "Description",
        "Payment Method", "Month", "Year", "Month Label", "Submitted At"
    ],
    "Fixed Expenses": [
        "ID", "Name", "Category", "Amount", "Due Day", "Active",
        "Notes", "Submitted At"
    ],
    "Categories": ["Category", "Type"],
    "Budgets": [
        "ID", "Month Label", "Category", "Budget Amount", "Submitted At"
    ],
    "Savings Goals": [
        "ID", "Goal Name", "Target Amount", "Current Amount",
        "Deadline", "Notes", "Submitted At"
    ]
}


@st.cache_resource
def connect_to_google_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)


def get_ws(name):
    spreadsheet = connect_to_google_sheet()
    try:
        return spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        ws.append_row(HEADERS[name])
        return ws


@st.cache_data(ttl=120, show_spinner=False)
def load_sheet(name):
    ws = get_ws(name)
    records = ws.get_all_records()
    return pd.DataFrame(records)


def save_row(sheet_name, row):
    ws = get_ws(sheet_name)
    ws.append_row(row)
    st.cache_data.clear()


def money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"


def prepare_transactions(df):
    if df.empty:
        return df

    for col in HEADERS["Transactions"]:
        if col not in df.columns:
            df[col] = ""

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    df["Month Label"] = df["Date"].dt.strftime("%Y-%m")
    df["Month"] = df["Date"].dt.month
    df["Year"] = df["Date"].dt.year
    return df


def categories_for(transaction_type):
    try:
        cats = load_sheet("Categories")
        if cats.empty:
            return ["Other"]
        if "Type" not in cats.columns or "Category" not in cats.columns:
            return ["Other"]
        values = cats[cats["Type"] == transaction_type]["Category"].dropna().tolist()
        return values if values else ["Other"]
    except Exception:
        return ["Other"]


st.sidebar.title("💰 Finance Tracker Pro")
menu = st.sidebar.radio(
    "Menu",
    [
        "Dashboard",
        "Add Transaction",
        "Fixed Expenses",
        "Budgets",
        "Savings Goals",
        "Analytics",
        "History"
    ]
)

# This message proves the app loaded before Google Sheets reads.
st.sidebar.caption("App loaded successfully.")

if menu == "Dashboard":
    st.title("📊 Executive Financial Dashboard")

    with st.spinner("Loading dashboard..."):
        transactions_df = prepare_transactions(load_sheet("Transactions"))
        fixed_df = load_sheet("Fixed Expenses")

    if transactions_df.empty:
        st.info("No transactions registered yet.")
    else:
        months = sorted(transactions_df["Month Label"].dropna().unique(), reverse=True)
        selected_month = st.selectbox("Select Month", months)

        month_df = transactions_df[transactions_df["Month Label"] == selected_month]

        income = month_df[month_df["Type"] == "Income"]["Amount"].sum()
        expenses = month_df[month_df["Type"] == "Expense"]["Amount"].sum()
        balance = income - expenses
        savings_rate = (balance / income * 100) if income > 0 else 0

        fixed_total = 0
        if not fixed_df.empty:
            if "Amount" in fixed_df.columns:
                fixed_df["Amount"] = pd.to_numeric(fixed_df["Amount"], errors="coerce").fillna(0)
            if "Active" in fixed_df.columns:
                fixed_total = fixed_df[fixed_df["Active"] == "Yes"]["Amount"].sum()

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Income", money(income))
        col2.metric("Expenses", money(expenses))
        col3.metric("Balance", money(balance))
        col4.metric("Savings Rate", f"{savings_rate:.1f}%")
        col5.metric("Fixed Expenses", money(fixed_total))

        st.divider()

        expense_df = month_df[month_df["Type"] == "Expense"]

        if not expense_df.empty:
            category_summary = (
                expense_df.groupby("Category")["Amount"]
                .sum()
                .reset_index()
                .sort_values("Amount", ascending=False)
            )

            c1, c2 = st.columns(2)

            with c1:
                fig = px.bar(
                    category_summary,
                    x="Category",
                    y="Amount",
                    text_auto=".2s",
                    title="Monthly Expenses by Category"
                )
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                fig_pie = px.pie(
                    category_summary,
                    names="Category",
                    values="Amount",
                    title="Expense Distribution"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        daily_summary = month_df.groupby(["Date", "Type"])["Amount"].sum().reset_index()
        if not daily_summary.empty:
            fig_daily = px.line(
                daily_summary,
                x="Date",
                y="Amount",
                color="Type",
                markers=True,
                title="Daily Cash Flow"
            )
            st.plotly_chart(fig_daily, use_container_width=True)

        st.subheader("Monthly Transactions")
        st.dataframe(month_df.sort_values("Date", ascending=False), use_container_width=True)

elif menu == "Add Transaction":
    st.title("➕ Add Income or Expense")

    with st.form("transaction_form"):
        trans_date = st.date_input("Date", date.today())
        trans_type = st.selectbox("Type", ["Expense", "Income"])
        category = st.selectbox("Category", categories_for(trans_type))
        amount = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
        description = st.text_input("Description")
        payment_method = st.selectbox(
            "Payment Method",
            ["Cash", "Debit Card", "Credit Card", "ATH Móvil", "Bank Transfer", "Other"]
        )

        submitted = st.form_submit_button("Save Transaction")

        if submitted:
            transaction_id = str(uuid.uuid4())[:8]
            month_label = trans_date.strftime("%Y-%m")
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            row = [
                transaction_id,
                str(trans_date),
                trans_type,
                category,
                float(amount),
                description,
                payment_method,
                trans_date.month,
                trans_date.year,
                month_label,
                submitted_at
            ]

            save_row("Transactions", row)
            st.success("Transaction saved successfully!")
            st.rerun()

elif menu == "Fixed Expenses":
    st.title("📌 Fixed Monthly Expenses")

    with st.form("fixed_expense_form"):
        name = st.text_input("Expense Name")
        category = st.selectbox(
            "Category",
            ["Rent", "Car", "Insurance", "Phone", "Internet", "Subscription",
             "Credit Card", "Loan", "Other"]
        )
        amount = st.number_input("Monthly Amount", min_value=0.01, step=0.01, format="%.2f")
        due_day = st.number_input("Due Day", min_value=1, max_value=31, step=1)
        active = st.selectbox("Active", ["Yes", "No"])
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Fixed Expense")

        if submitted:
            row = [
                str(uuid.uuid4())[:8],
                name,
                category,
                float(amount),
                int(due_day),
                active,
                notes,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]

            save_row("Fixed Expenses", row)
            st.success("Fixed expense saved successfully!")
            st.rerun()

    st.divider()
    st.subheader("Current Fixed Expenses")
    fixed_df = load_sheet("Fixed Expenses")
    if fixed_df.empty:
        st.info("No fixed expenses registered yet.")
    else:
        st.dataframe(fixed_df, use_container_width=True)

elif menu == "Budgets":
    st.title("🎯 Monthly Budgets")

    current_month = datetime.now().strftime("%Y-%m")

    with st.form("budget_form"):
        month_label = st.text_input("Month", value=current_month)
        category = st.selectbox("Category", categories_for("Expense"))
        budget_amount = st.number_input("Budget Amount", min_value=0.01, step=0.01, format="%.2f")
        submitted = st.form_submit_button("Save Budget")

        if submitted:
            row = [
                str(uuid.uuid4())[:8],
                month_label,
                category,
                float(budget_amount),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            save_row("Budgets", row)
            st.success("Budget saved successfully!")
            st.rerun()

    st.divider()
    st.subheader("Budget Performance")

    budgets_df = load_sheet("Budgets")
    transactions_df = prepare_transactions(load_sheet("Transactions"))

    if budgets_df.empty or transactions_df.empty:
        st.info("No budget comparison available yet.")
    else:
        budgets_df["Budget Amount"] = pd.to_numeric(budgets_df["Budget Amount"], errors="coerce").fillna(0)
        selected_month = st.selectbox("Select Budget Month", sorted(budgets_df["Month Label"].dropna().unique(), reverse=True))

        budget_month_df = budgets_df[budgets_df["Month Label"] == selected_month]
        spent_df = transactions_df[
            (transactions_df["Month Label"] == selected_month) &
            (transactions_df["Type"] == "Expense")
        ]

        spent_summary = spent_df.groupby("Category")["Amount"].sum().reset_index().rename(columns={"Amount": "Spent"})

        budget_compare = budget_month_df.merge(spent_summary, on="Category", how="left")
        budget_compare["Spent"] = budget_compare["Spent"].fillna(0)
        budget_compare["Remaining"] = budget_compare["Budget Amount"] - budget_compare["Spent"]
        budget_compare["Used %"] = (budget_compare["Spent"] / budget_compare["Budget Amount"] * 100).round(1)

        st.dataframe(budget_compare, use_container_width=True)

        fig = px.bar(
            budget_compare,
            x="Category",
            y=["Budget Amount", "Spent"],
            barmode="group",
            title="Budget vs Actual Spending"
        )
        st.plotly_chart(fig, use_container_width=True)

elif menu == "Savings Goals":
    st.title("🏦 Savings Goals")

    with st.form("goal_form"):
        goal_name = st.text_input("Goal Name", placeholder="Example: Emergency Fund")
        target_amount = st.number_input("Target Amount", min_value=0.01, step=0.01, format="%.2f")
        current_amount = st.number_input("Current Amount", min_value=0.00, step=0.01, format="%.2f")
        deadline = st.date_input("Deadline", date.today())
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Goal")

        if submitted:
            row = [
                str(uuid.uuid4())[:8],
                goal_name,
                float(target_amount),
                float(current_amount),
                str(deadline),
                notes,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            save_row("Savings Goals", row)
            st.success("Savings goal saved successfully!")
            st.rerun()

    st.divider()
    goals_df = load_sheet("Savings Goals")

    if goals_df.empty:
        st.info("No savings goals registered yet.")
    else:
        goals_df["Target Amount"] = pd.to_numeric(goals_df["Target Amount"], errors="coerce").fillna(0)
        goals_df["Current Amount"] = pd.to_numeric(goals_df["Current Amount"], errors="coerce").fillna(0)
        goals_df["Progress %"] = (goals_df["Current Amount"] / goals_df["Target Amount"] * 100).round(1)
        st.dataframe(goals_df, use_container_width=True)

        for _, row in goals_df.iterrows():
            st.subheader(row["Goal Name"])
            progress = min(row["Progress %"] / 100, 1.0) if row["Target Amount"] > 0 else 0
            st.progress(progress)
            st.write(f"{money(row['Current Amount'])} of {money(row['Target Amount'])} ({row['Progress %']}%)")

elif menu == "Analytics":
    st.title("📈 Financial Analytics")

    transactions_df = prepare_transactions(load_sheet("Transactions"))

    if transactions_df.empty:
        st.info("No data available yet.")
    else:
        monthly_summary = transactions_df.groupby(["Month Label", "Type"])["Amount"].sum().reset_index()
        pivot_summary = monthly_summary.pivot(index="Month Label", columns="Type", values="Amount").fillna(0)

        if "Income" not in pivot_summary.columns:
            pivot_summary["Income"] = 0

        if "Expense" not in pivot_summary.columns:
            pivot_summary["Expense"] = 0

        pivot_summary["Balance"] = pivot_summary["Income"] - pivot_summary["Expense"]
        pivot_summary["Savings Rate %"] = (
            pivot_summary["Balance"] / pivot_summary["Income"].replace(0, pd.NA) * 100
        ).fillna(0).round(1)
        pivot_summary = pivot_summary.reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(x=pivot_summary["Month Label"], y=pivot_summary["Income"], name="Income"))
        fig.add_trace(go.Bar(x=pivot_summary["Month Label"], y=pivot_summary["Expense"], name="Expense"))
        fig.add_trace(go.Scatter(x=pivot_summary["Month Label"], y=pivot_summary["Balance"], name="Balance", mode="lines+markers"))
        fig.update_layout(barmode="group", title="Monthly Financial Performance")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Full Monthly Summary")
        st.dataframe(pivot_summary, use_container_width=True)

        top_categories = (
            transactions_df[transactions_df["Type"] == "Expense"]
            .groupby("Category")["Amount"]
            .sum()
            .reset_index()
            .sort_values("Amount", ascending=False)
        )

        fig_top = px.bar(top_categories, x="Category", y="Amount", title="All-Time Spending by Category")
        st.plotly_chart(fig_top, use_container_width=True)

elif menu == "History":
    st.title("📚 Transaction History")

    transactions_df = prepare_transactions(load_sheet("Transactions"))

    if transactions_df.empty:
        st.info("No transactions registered yet.")
    else:
        c1, c2, c3 = st.columns(3)

        type_filter = c1.selectbox("Type", ["All", "Income", "Expense"])
        month_filter = c2.selectbox("Month", ["All"] + sorted(transactions_df["Month Label"].dropna().unique(), reverse=True))
        category_filter = c3.selectbox("Category", ["All"] + sorted(transactions_df["Category"].dropna().unique()))

        filtered_df = transactions_df.copy()

        if type_filter != "All":
            filtered_df = filtered_df[filtered_df["Type"] == type_filter]

        if month_filter != "All":
            filtered_df = filtered_df[filtered_df["Month Label"] == month_filter]

        if category_filter != "All":
            filtered_df = filtered_df[filtered_df["Category"] == category_filter]

        st.dataframe(filtered_df.sort_values("Date", ascending=False), use_container_width=True)

        csv = filtered_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="personal_finance_transactions.csv",
            mime="text/csv"
        )
'''

path = Path("/mnt/data/app_streamlit_stable.py")
path.write_text(code, encoding="utf-8")
print(path)
