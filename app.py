import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px
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

@st.cache_resource
def connect_to_google_sheet():
    creds = Credentials.from_service_account_file(
    "able-yew-499012-q9-0b57020fb3fb.json",
    scopes=SCOPES
)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)
    return spreadsheet

creds = Credentials.from_service_account_file(
    "able-yew-499012-q9-0b57020fb3fb.json",
    scopes=SCOPES
)

def get_worksheet(sheet, name):
    return sheet.worksheet(name)

def load_data(ws):
    records = ws.get_all_records()
    return pd.DataFrame(records)

def append_transaction(ws, transaction):
    ws.append_row(transaction)

def append_fixed_expense(ws, expense):
    ws.append_row(expense)

sheet = connect_to_google_sheet()

transactions_ws = get_worksheet(sheet, "Transactions")
fixed_ws = get_worksheet(sheet, "Fixed Expenses")
categories_ws = get_worksheet(sheet, "Categories")

st.sidebar.title("💰 Finance Tracker")

menu = st.sidebar.radio(
    "Menu",
    [
        "Dashboard",
        "Add Transaction",
        "Fixed Expenses",
        "History"
    ]
)

# -------------------------------
# LOAD DATA
# -------------------------------

transactions_df = load_data(transactions_ws)
fixed_df = load_data(fixed_ws)
categories_df = load_data(categories_ws)

if not transactions_df.empty:
    transactions_df["Date"] = pd.to_datetime(transactions_df["Date"], errors="coerce")
    transactions_df["Amount"] = pd.to_numeric(transactions_df["Amount"], errors="coerce")

# -------------------------------
# DASHBOARD
# -------------------------------

if menu == "Dashboard":
    st.title("📊 Monthly Dashboard")

    if transactions_df.empty:
        st.info("No transactions registered yet.")
    else:
        available_months = sorted(
            transactions_df["Date"].dt.strftime("%Y-%m").dropna().unique(),
            reverse=True
        )

        selected_month = st.selectbox("Select Month", available_months)

        month_df = transactions_df[
            transactions_df["Date"].dt.strftime("%Y-%m") == selected_month
        ]

        income = month_df[month_df["Type"] == "Income"]["Amount"].sum()
        expenses = month_df[month_df["Type"] == "Expense"]["Amount"].sum()
        balance = income - expenses

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Income", f"${income:,.2f}")
        col2.metric("Total Expenses", f"${expenses:,.2f}")
        col3.metric("Balance", f"${balance:,.2f}")

        st.divider()

        expense_df = month_df[month_df["Type"] == "Expense"]

        if not expense_df.empty:
            category_summary = (
                expense_df.groupby("Category")["Amount"]
                .sum()
                .reset_index()
                .sort_values(by="Amount", ascending=False)
            )

            st.subheader("Expenses by Category")

            fig = px.bar(
                category_summary,
                x="Category",
                y="Amount",
                text="Amount",
                title="Monthly Expenses by Category"
            )

            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Category Breakdown")

            fig_pie = px.pie(
                category_summary,
                names="Category",
                values="Amount",
                title="Expense Distribution"
            )

            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Monthly Transactions")
        st.dataframe(month_df, use_container_width=True)

# -------------------------------
# ADD TRANSACTION
# -------------------------------

elif menu == "Add Transaction":
    st.title("➕ Add Income or Expense")

    if categories_df.empty:
        st.warning("Please add categories in the Google Sheet first.")
    else:
        with st.form("transaction_form"):
            trans_date = st.date_input("Date", date.today())

            trans_type = st.selectbox(
                "Type",
                ["Expense", "Income"]
            )

            filtered_categories = categories_df[
                categories_df["Type"] == trans_type
            ]["Category"].tolist()

            if not filtered_categories:
                filtered_categories = ["Other"]

            category = st.selectbox("Category", filtered_categories)

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
                    submitted_at
                ]

                append_transaction(transactions_ws, new_transaction)

                st.success("Transaction saved successfully!")

# -------------------------------
# FIXED EXPENSES
# -------------------------------

elif menu == "Fixed Expenses":
    st.title("📌 Fixed Monthly Expenses")

    with st.form("fixed_expense_form"):
        name = st.text_input("Expense Name")

        category = st.selectbox(
            "Category",
            [
                "Rent",
                "Car",
                "Insurance",
                "Phone",
                "Internet",
                "Subscription",
                "Credit Card",
                "Loan",
                "Other"
            ]
        )

        amount = st.number_input(
            "Monthly Amount",
            min_value=0.01,
            step=0.01,
            format="%.2f"
        )

        due_day = st.number_input(
            "Due Day",
            min_value=1,
            max_value=31,
            step=1
        )

        active = st.selectbox("Active", ["Yes", "No"])

        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Fixed Expense")

        if submitted:
            fixed_id = str(uuid.uuid4())[:8]
            submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            new_fixed_expense = [
                fixed_id,
                name,
                category,
                float(amount),
                int(due_day),
                active,
                notes,
                submitted_at
            ]

            append_fixed_expense(fixed_ws, new_fixed_expense)

            st.success("Fixed expense saved successfully!")

    st.divider()

    st.subheader("Current Fixed Expenses")

    fixed_df = load_data(fixed_ws)

    if fixed_df.empty:
        st.info("No fixed expenses registered yet.")
    else:
        st.dataframe(fixed_df, use_container_width=True)

# -------------------------------
# HISTORY
# -------------------------------

elif menu == "History":
    st.title("📚 Transaction History")

    transactions_df = load_data(transactions_ws)

    if transactions_df.empty:
        st.info("No transactions registered yet.")
    else:
        st.dataframe(transactions_df, use_container_width=True)

        csv = transactions_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="personal_finance_transactions.csv",
            mime="text/csv"
        )