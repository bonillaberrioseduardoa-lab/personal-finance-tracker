

code = """import streamlit as st
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

TRANSACTION_HEADERS = [
    "ID", "Date", "Type", "Category", "Amount", "Description",
    "Payment Method", "Month", "Year", "Month Label", "Submitted At"
]

FIXED_HEADERS = [
    "ID", "Name", "Category", "Amount", "Due Day", "Active",
    "Notes", "Submitted At"
]

CATEGORY_HEADERS = ["Category", "Type"]

BUDGET_HEADERS = [
    "ID", "Month Label", "Category", "Budget Amount", "Submitted At"
]

GOAL_HEADERS = [
    "ID", "Goal Name", "Target Amount", "Current Amount",
    "Deadline", "Notes", "Submitted At"
]


@st.cache_resource
def connect_to_google_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)


def get_or_create_worksheet(spreadsheet, name, headers):
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers) + 5)
        ws.append_row(headers)
        return ws

    values = ws.get_all_values()
    if not values:
        ws.append_row(headers)

    return ws


sheet = connect_to_google_sheet()

transactions_ws = get_or_create_worksheet(sheet, "Transactions", TRANSACTION_HEADERS)
fixed_ws = get_or_create_worksheet(sheet, "Fixed Expenses", FIXED_HEADERS)
categories_ws = get_or_create_worksheet(sheet, "Categories", CATEGORY_HEADERS)
budgets_ws = get_or_create_worksheet(sheet, "Budgets", BUDGET_HEADERS)
goals_ws = get_or_create_worksheet(sheet, "Savings Goals", GOAL_HEADERS)


@st.cache_data(ttl=60)
def load_data_by_sheet(sheet_name):
    ws = sheet.worksheet(sheet_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)


def append_row(ws, row):
    ws.append_row(row)
    st.cache_data.clear()


def format_money(value):
    return f"${value:,.2f}"


def prepare_transactions(df):
    if df.empty:
        return df

    expected_cols = TRANSACTION_HEADERS

    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    df["Month Label"] = df["Date"].dt.strftime("%Y-%m")
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month

    return df


def prepare_money_column(df, column):
    if df.empty or column not in df.columns:
        return df
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return df


def safe_categories(df, transaction_type):
    if df.empty or "Type" not in df.columns or "Category" not in df.columns:
        return ["Other"]

    cats = df[df["Type"] == transaction_type]["Category"].dropna().tolist()
    return cats if cats else ["Other"]


transactions_df = prepare_transactions(load_data_by_sheet("Transactions"))
fixed_df = prepare_money_column(load_data_by_sheet("Fixed Expenses"), "Amount")
categories_df = load_data_by_sheet("Categories")
budgets_df = prepare_money_column(load_data_by_sheet("Budgets"), "Budget Amount")
goals_df = load_data_by_sheet("Savings Goals")

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

if menu == "Dashboard":
    st.title("📊 Executive Financial Dashboard")

    if transactions_df.empty:
        st.info("No transactions registered yet.")
    else:
        available_months = sorted(
            transactions_df["Month Label"].dropna().unique(),
            reverse=True
        )

        selected_month = st.selectbox("Select Month", available_months)

        month_df = transactions_df[
            transactions_df["Month Label"] == selected_month
        ]

        income = month_df[month_df["Type"] == "Income"]["Amount"].sum()
        expenses = month_df[month_df["Type"] == "Expense"]["Amount"].sum()
        balance = income - expenses
        savings_rate = (balance / income * 100) if income > 0 else 0

        fixed_total = 0
        if not fixed_df.empty and "Active" in fixed_df.columns:
            fixed_total = fixed_df[fixed_df["Active"] == "Yes"]["Amount"].sum()

        variable_expenses = max(expenses - fixed_total, 0)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Income", format_money(income))
        col2.metric("Expenses", format_money(expenses))
        col3.metric("Balance", format_money(balance))
        col4.metric("Savings Rate", f"{savings_rate:.1f}%")
        col5.metric("Fixed Expenses", format_money(fixed_total))

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
                st.subheader("Expenses by Category")
                fig = px.bar(
                    category_summary,
                    x="Category",
                    y="Amount",
                    text_auto=".2s",
                    title="Monthly Expenses by Category"
                )
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                st.subheader("Expense Distribution")
                fig_pie = px.pie(
                    category_summary,
                    names="Category",
                    values="Amount",
                    title="Expense Breakdown"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            st.subheader("Fixed vs Variable Expenses")
            fv_df = pd.DataFrame({
                "Type": ["Fixed Expenses", "Variable Expenses"],
                "Amount": [fixed_total, variable_expenses]
            })
            fig_fv = px.pie(fv_df, names="Type", values="Amount", title="Fixed vs Variable")
            st.plotly_chart(fig_fv, use_container_width=True)

        st.subheader("Daily Cash Flow")

        daily_summary = (
            month_df.groupby(["Date", "Type"])["Amount"]
            .sum()
            .reset_index()
        )

        if not daily_summary.empty:
            fig_daily = px.line(
                daily_summary,
                x="Date",
                y="Amount",
                color="Type",
                markers=True,
                title="Daily Income vs Expenses"
            )
            st.plotly_chart(fig_daily, use_container_width=True)

        st.subheader("Monthly Transactions")
        st.dataframe(
            month_df.sort_values("Date", ascending=False),
            use_container_width=True
        )

elif menu == "Add Transaction":
    st.title("➕ Add Income or Expense")

    with st.form("transaction_form"):
        trans_date = st.date_input("Date", date.today())
        trans_type = st.selectbox("Type", ["Expense", "Income"])

        category = st.selectbox(
            "Category",
            safe_categories(categories_df, trans_type)
        )

        amount = st.number_input(
            "Amount",
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )

        description = st.text_input("Description")

        payment_method = st.selectbox(
            "Payment Method",
            [
                "Cash",
                "Debit Card",
                "Credit Card",
                "ATH Móvil",
                "Bank Transfer",
                "Other"
            ]
        )

        submitted = st.form_submit_button("Save Transaction")

        if submitted:
            transaction_id = str(uuid.uuid4())[:8]
            month = trans_date.month
            year = trans_date.year
            month_label = trans_date.strftime("%Y-%m")
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            new_transaction = [
                transaction_id,
                str(trans_date),
                trans_type,
                category,
                float(amount),
                description,
                payment_method,
                month,
                year,
                month_label,
                submitted_at
            ]

            append_row(transactions_ws, new_transaction)
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

        amount = st.number_input(
            "Monthly Amount",
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )

        due_day = st.number_input("Due Day", min_value=1, max_value=31, step=1)
        active = st.selectbox("Active", ["Yes", "No"])
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Fixed Expense")

        if submitted:
            fixed_id = str(uuid.uuid4())[:8]
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            append_row(
                fixed_ws,
                [
                    fixed_id,
                    name,
                    category,
                    float(amount),
                    int(due_day),
                    active,
                    notes,
                    submitted_at
                ]
            )

            st.success("Fixed expense saved successfully!")
            st.rerun()

    st.divider()
    st.subheader("Current Fixed Expenses")

    fixed_current_df = load_data_by_sheet("Fixed Expenses")

    if fixed_current_df.empty:
        st.info("No fixed expenses registered yet.")
    else:
        st.dataframe(fixed_current_df, use_container_width=True)

elif menu == "Budgets":
    st.title("🎯 Monthly Budgets")

    current_month = datetime.now().strftime("%Y-%m")

    with st.form("budget_form"):
        month_label = st.text_input("Month", value=current_month)
        category = st.selectbox(
            "Category",
            safe_categories(categories_df, "Expense")
        )

        budget_amount = st.number_input(
            "Budget Amount",
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )

        submitted = st.form_submit_button("Save Budget")

        if submitted:
            budget_id = str(uuid.uuid4())[:8]
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            append_row(
                budgets_ws,
                [
                    budget_id,
                    month_label,
                    category,
                    float(budget_amount),
                    submitted_at
                ]
            )

            st.success("Budget saved successfully!")
            st.rerun()

    st.divider()
    st.subheader("Budget Performance")

    budgets_current_df = prepare_money_column(load_data_by_sheet("Budgets"), "Budget Amount")

    if budgets_current_df.empty or transactions_df.empty:
        st.info("No budget comparison available yet.")
    else:
        selected_budget_month = st.selectbox(
            "Select Budget Month",
            sorted(budgets_current_df["Month Label"].dropna().unique(), reverse=True)
        )

        budget_month_df = budgets_current_df[
            budgets_current_df["Month Label"] == selected_budget_month
        ]

        spent_df = transactions_df[
            (transactions_df["Month Label"] == selected_budget_month) &
            (transactions_df["Type"] == "Expense")
        ]

        spent_summary = (
            spent_df.groupby("Category")["Amount"]
            .sum()
            .reset_index()
            .rename(columns={"Amount": "Spent"})
        )

        budget_compare = budget_month_df.merge(
            spent_summary,
            on="Category",
            how="left"
        )

        budget_compare["Spent"] = budget_compare["Spent"].fillna(0)
        budget_compare["Remaining"] = (
            budget_compare["Budget Amount"] - budget_compare["Spent"]
        )
        budget_compare["Used %"] = (
            budget_compare["Spent"] / budget_compare["Budget Amount"] * 100
        ).round(1)

        st.dataframe(budget_compare, use_container_width=True)

        fig_budget = px.bar(
            budget_compare,
            x="Category",
            y=["Budget Amount", "Spent"],
            barmode="group",
            title="Budget vs Actual Spending"
        )

        st.plotly_chart(fig_budget, use_container_width=True)

elif menu == "Savings Goals":
    st.title("🏦 Savings Goals")

    with st.form("goal_form"):
        goal_name = st.text_input("Goal Name", placeholder="Example: Emergency Fund")
        target_amount = st.number_input(
            "Target Amount",
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )
        current_amount = st.number_input(
            "Current Amount",
            min_value=0.00,
            step=0.01,
            format="%.2f"
        )
        deadline = st.date_input("Deadline", date.today())
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Goal")

        if submitted:
            goal_id = str(uuid.uuid4())[:8]
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            append_row(
                goals_ws,
                [
                    goal_id,
                    goal_name,
                    float(target_amount),
                    float(current_amount),
                    str(deadline),
                    notes,
                    submitted_at
                ]
            )

            st.success("Savings goal saved successfully!")
            st.rerun()

    st.divider()

    goals_current_df = load_data_by_sheet("Savings Goals")

    if goals_current_df.empty:
        st.info("No savings goals registered yet.")
    else:
        goals_current_df["Target Amount"] = pd.to_numeric(
            goals_current_df["Target Amount"],
            errors="coerce"
        ).fillna(0)

        goals_current_df["Current Amount"] = pd.to_numeric(
            goals_current_df["Current Amount"],
            errors="coerce"
        ).fillna(0)

        goals_current_df["Progress %"] = (
            goals_current_df["Current Amount"] / goals_current_df["Target Amount"] * 100
        ).round(1)

        st.dataframe(goals_current_df, use_container_width=True)

        for _, row in goals_current_df.iterrows():
            st.subheader(row["Goal Name"])
            progress = min(row["Progress %"] / 100, 1.0) if row["Target Amount"] > 0 else 0
            st.progress(progress)
            st.write(
                f"{format_money(row['Current Amount'])} of "
                f"{format_money(row['Target Amount'])} "
                f"({row['Progress %']}%)"
            )

elif menu == "Analytics":
    st.title("📈 Financial Analytics")

    if transactions_df.empty:
        st.info("No data available yet.")
    else:
        monthly_summary = (
            transactions_df.groupby(["Month Label", "Type"])["Amount"]
            .sum()
            .reset_index()
        )

        pivot_summary = monthly_summary.pivot(
            index="Month Label",
            columns="Type",
            values="Amount"
        ).fillna(0)

        if "Income" not in pivot_summary.columns:
            pivot_summary["Income"] = 0

        if "Expense" not in pivot_summary.columns:
            pivot_summary["Expense"] = 0

        pivot_summary["Balance"] = pivot_summary["Income"] - pivot_summary["Expense"]
        pivot_summary["Savings Rate %"] = (
            pivot_summary["Balance"] / pivot_summary["Income"].replace(0, pd.NA) * 100
        ).fillna(0).round(1)

        pivot_summary = pivot_summary.reset_index()

        st.subheader("Monthly Income, Expenses, and Balance")

        fig_monthly = go.Figure()

        fig_monthly.add_trace(go.Bar(
            x=pivot_summary["Month Label"],
            y=pivot_summary["Income"],
            name="Income"
        ))

        fig_monthly.add_trace(go.Bar(
            x=pivot_summary["Month Label"],
            y=pivot_summary["Expense"],
            name="Expense"
        ))

        fig_monthly.add_trace(go.Scatter(
            x=pivot_summary["Month Label"],
            y=pivot_summary["Balance"],
            name="Balance",
            mode="lines+markers"
        ))

        fig_monthly.update_layout(
            barmode="group",
            title="Monthly Financial Performance"
        )

        st.plotly_chart(fig_monthly, use_container_width=True)

        st.subheader("Full Monthly Summary")
        st.dataframe(pivot_summary, use_container_width=True)

        st.subheader("Top Spending Categories All-Time")

        top_categories = (
            transactions_df[transactions_df["Type"] == "Expense"]
            .groupby("Category")["Amount"]
            .sum()
            .reset_index()
            .sort_values("Amount", ascending=False)
        )

        fig_top = px.bar(
            top_categories,
            x="Category",
            y="Amount",
            title="All-Time Spending by Category"
        )

        st.plotly_chart(fig_top, use_container_width=True)

elif menu == "History":
    st.title("📚 Transaction History")

    transactions_current_df = prepare_transactions(load_data_by_sheet("Transactions"))

    if transactions_current_df.empty:
        st.info("No transactions registered yet.")
    else:
        c1, c2, c3 = st.columns(3)

        type_filter = c1.selectbox("Type", ["All", "Income", "Expense"])

        month_filter = c2.selectbox(
            "Month",
            ["All"] + sorted(
                transactions_current_df["Month Label"].dropna().unique(),
                reverse=True
            )
        )

        category_filter = c3.selectbox(
            "Category",
            ["All"] + sorted(
                transactions_current_df["Category"].dropna().unique()
            )
        )

        filtered_df = transactions_current_df.copy()

        if type_filter != "All":
            filtered_df = filtered_df[filtered_df["Type"] == type_filter]

        if month_filter != "All":
            filtered_df = filtered_df[filtered_df["Month Label"] == month_filter]

        if category_filter != "All":
            filtered_df = filtered_df[filtered_df["Category"] == category_filter]

        st.dataframe(
            filtered_df.sort_values("Date", ascending=False),
            use_container_width=True
        )

        csv = filtered_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="personal_finance_transactions.csv",
            mime="text/csv"
        )
"""


