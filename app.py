import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Must be the very first Streamlit command
st.set_page_config(page_title="Personal Finance Tracker", page_icon="💰", layout="wide")

# --- Profile Setup ---
st.sidebar.header("👤 Account Profile")
st.sidebar.markdown("Type a different name below to switch accounts and get a fresh database.")
username = st.sidebar.text_input("Username:", "MyAccount")

# Make a safe filename based on the username
safe_username = "".join([c for c in username if c.isalnum()]) or "Default"

# -----------------------------------------------------------------------------
# Configuration & Cloud Database Setup (Firebase)
# -----------------------------------------------------------------------------

# 1. Connect to Firebase (Only initialize once)
if not firebase_admin._apps:
    try:
        # Read the raw JSON string from secrets and parse it
        key_dict = json.loads(st.secrets["firebase_json"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error("⚠️ Could not connect to Firebase! Make sure you have added your Firebase Key to the Streamlit Secrets.")
        st.stop()

# 2. Access the Firestore database
db = firestore.client()

def add_transaction(date, amount, category, trans_type, payment_method, description):
    """Insert a new transaction into Firebase Cloud."""
    doc_ref = db.collection('users').document(safe_username).collection('transactions').document()
    doc_ref.set({
        'date': date.strftime("%Y-%m-%d"),
        'amount': float(amount),
        'category': category,
        'type': trans_type,
        'payment_method': payment_method, # NEW: Bank or Cash
        'description': description,
        'created_at': firestore.SERVER_TIMESTAMP
    })

def delete_transaction(transaction_id):
    """Delete a transaction from Firebase Cloud by its ID."""
    db.collection('users').document(safe_username).collection('transactions').document(transaction_id).delete()

def load_data():
    """Load all transactions from Firebase into a pandas DataFrame."""
    docs = db.collection('users').document(safe_username).collection('transactions').stream()
    
    data = []
    for doc in docs:
        item = doc.to_dict()
        item['id'] = doc.id
        data.append(item)
        
    if data:
        df = pd.DataFrame(data)
        # Handle older data that didn't have 'payment_method'
        if 'payment_method' not in df.columns:
            df['payment_method'] = 'Bank'
        else:
            df['payment_method'] = df['payment_method'].fillna('Bank')
        return df
    else:
        # Return empty DataFrame with the correct columns if no data exists yet
        return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'type', 'payment_method', 'description', 'created_at'])

# -----------------------------------------------------------------------------
# Streamlit App Layout & UI
# -----------------------------------------------------------------------------

# Custom CSS to force specific colors for positive/negative metrics
st.markdown("""
    <style>
    .income-text { color: #2e7d32; font-weight: bold; font-size: 1.2rem;}
    .expense-text { color: #c62828; font-weight: bold; font-size: 1.2rem;}
    .balance-text { color: #1565c0; font-weight: bold; font-size: 1.2rem;}
    .small-text { font-size: 0.85rem; color: #555; }
    </style>
""", unsafe_allow_html=True)

st.title("💸 Personal Finance Dashboard")
st.markdown("© 2026 Sagor Hossen")
st.markdown("Track your income, expenses, and account balances.")

# --- Sidebar: Input Interface & Settings ---
st.sidebar.header("⚙️ Settings")
savings_goal = st.sidebar.number_input("Set Savings Goal (৳)", min_value=0.0, value=5000.0, step=100.0)

st.sidebar.divider()

st.sidebar.header("➕ Add New Transaction")

# Define categories based on type
INCOME_CATEGORIES = [
    "Salary", 
    "Commission", 
    "Bonus", 
    "Investments", 
    "Interest/Dividends",
    "Rental Income",
    "Refunds/Reimbursements",
    "Freelance/Side Hustle", 
    "Gifts", 
    "General Income", 
    "Other Income"
]
EXPENSE_CATEGORIES = [
    "Food & Dining", 
    "Fitness/Wellness", 
    "Travel/Leisure", 
    "Entertainment", 
    "Savings/Investments", 
    "Housing/Rent", 
    "Utilities", 
    "Transportation",
    "Other Expenses"
]

# Transaction Type MUST be outside the form to change categories dynamically
t_type = st.sidebar.radio("Transaction Type", ["Expense", "Income"], horizontal=True)

with st.sidebar.form("transaction_form", clear_on_submit=True):
    t_date = st.date_input("Date", datetime.today())
    
    # NEW: Payment Method selection
    t_method = st.radio("Account", ["Bank", "Cash", "bKash"], horizontal=True)
    
    if t_type == "Income":
        t_category = st.selectbox("Category", INCOME_CATEGORIES)
    else:
        t_category = st.selectbox("Category", EXPENSE_CATEGORIES)
        
    t_amount = st.number_input("Amount (৳)", min_value=0.01, format="%.2f")
    t_desc = st.text_input("Description (Optional)")
    
    submitted = st.form_submit_button("Save Transaction")
    if submitted:
        add_transaction(t_date, t_amount, t_category, t_type, t_method, t_desc)
        st.success("Transaction added successfully!")
        st.rerun()

# --- Main Dashboard: Data Processing ---
df = load_data()

# Initialize KPIs
total_income = 0.0
total_expense = 0.0
bank_income, bank_expense = 0.0, 0.0
cash_income, cash_expense = 0.0, 0.0
bkash_income, bkash_expense = 0.0, 0.0

if not df.empty:
    # Total calculations
    total_income = df[df['type'] == 'Income']['amount'].sum()
    total_expense = df[df['type'] == 'Expense']['amount'].sum()
    
    # Bank calculations
    bank_income = df[(df['type'] == 'Income') & (df['payment_method'] == 'Bank')]['amount'].sum()
    bank_expense = df[(df['type'] == 'Expense') & (df['payment_method'] == 'Bank')]['amount'].sum()
    
    # Cash calculations
    cash_income = df[(df['type'] == 'Income') & (df['payment_method'] == 'Cash')]['amount'].sum()
    cash_expense = df[(df['type'] == 'Expense') & (df['payment_method'] == 'Cash')]['amount'].sum()

    # bKash calculations
    bkash_income = df[(df['type'] == 'Income') & (df['payment_method'] == 'bKash')]['amount'].sum()
    bkash_expense = df[(df['type'] == 'Expense') & (df['payment_method'] == 'bKash')]['amount'].sum()

net_savings = total_income - total_expense
bank_balance = bank_income - bank_expense
cash_balance = cash_income - cash_expense
bkash_balance = bkash_income - bkash_expense

# --- Main Dashboard: KPI Row ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.container(border=True)
    st.markdown("### Total Income")
    st.markdown(f"<span class='income-text'>৳{total_income:,.2f}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='small-text'>Bank: ৳{bank_income:,.2f} | Cash: ৳{cash_income:,.2f} | bKash: ৳{bkash_income:,.2f}</span>", unsafe_allow_html=True)

with col2:
    st.container(border=True)
    st.markdown("### Total Expenses")
    st.markdown(f"<span class='expense-text'>৳{total_expense:,.2f}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='small-text'>Bank: ৳{bank_expense:,.2f} | Cash: ৳{cash_expense:,.2f} | bKash: ৳{bkash_expense:,.2f}</span>", unsafe_allow_html=True)

with col3:
    st.container(border=True)
    st.markdown("### 🏦 Bank Balance")
    b_color = "#2e7d32" if bank_balance >= 0 else "#c62828"
    st.markdown(f"<span style='color:{b_color}; font-weight:bold; font-size: 1.2rem;'>৳{bank_balance:,.2f}</span>", unsafe_allow_html=True)

with col4:
    st.container(border=True)
    st.markdown("### 💵 Cash Balance")
    c_color = "#2e7d32" if cash_balance >= 0 else "#c62828"
    st.markdown(f"<span style='color:{c_color}; font-weight:bold; font-size: 1.2rem;'>৳{cash_balance:,.2f}</span>", unsafe_allow_html=True)

with col5:
    st.container(border=True)
    st.markdown("### 📱 bKash")
    bk_color = "#2e7d32" if bkash_balance >= 0 else "#c62828"
    st.markdown(f"<span style='color:{bk_color}; font-weight:bold; font-size: 1.2rem;'>৳{bkash_balance:,.2f}</span>", unsafe_allow_html=True)

st.divider()

# --- Main Dashboard: Charts & Goals ---
col_chart, col_goal = st.columns([2, 1])

with col_chart:
    st.subheader("📊 Spending by Category")
    if not df.empty and total_expense > 0:
        expense_df = df[df['type'] == 'Expense']
        category_group = expense_df.groupby('category', as_index=False)['amount'].sum()
        category_group = category_group.sort_values(by='amount', ascending=False)
        
        fig = px.bar(
            category_group, 
            x='category', 
            y='amount', 
            color='category',
            text='amount',
            labels={'amount': 'Amount (৳)', 'category': 'Category'},
            template='plotly_white'
        )
        fig.update_traces(texttemplate='৳%{text:.2s}', textposition='outside')
        fig.update_layout(showlegend=False, margin=dict(t=10, l=10, r=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No expense data available yet. Add an expense to see the chart!")

with col_goal:
    st.subheader("🎯 Total Savings Progress")
    st.write(f"**Target:** ৳{savings_goal:,.2f}")
    
    if savings_goal > 0:
        current_progress = max(0.0, net_savings) 
        progress_pct = min(current_progress / savings_goal, 1.0)
        
        st.progress(progress_pct)
        st.write(f"**Current Total:** ৳{current_progress:,.2f} ({progress_pct*100:.1f}%)")
        
        if progress_pct >= 1.0:
            st.balloons()
            st.success("Congratulations! You've reached your savings goal!")
        elif current_progress == 0 and net_savings < 0:
             st.warning("You are currently operating at a deficit.")
    else:
        st.write("Please set a savings goal greater than $0.")

st.divider()

# --- Main Dashboard: Transaction History ---
st.subheader("📝 Recent Transactions")
if not df.empty:
    display_df = df.sort_values(by='date', ascending=False).drop(columns=['id'])
    
    # Hide the cloud timestamp column from the display if it exists
    if 'created_at' in display_df.columns:
        display_df = display_df.drop(columns=['created_at'])
        
    display_df['amount'] = display_df['amount'].apply(lambda x: f"৳{x:,.2f}")
    
    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "date": "Date",
            "type": "Type",
            "payment_method": "Account",
            "category": "Category",
            "amount": "Amount",
            "description": "Description"
        }
    )

    # --- NEW: Delete Feature ---
    st.write("")
    with st.expander("🗑️ Delete a Transaction"):
        # Create a formatted label for the dropdown so the user knows what they are deleting
        df['delete_label'] = df['date'].astype(str) + " | " + df['category'] + " | ৳" + df['amount'].apply(lambda x: f"{x:,.2f}") + " (" + df['type'] + ")"
        
        # Make a dictionary to map the formatted label back to the real database ID
        transaction_dict = dict(zip(df['delete_label'], df['id']))
        
        selected_label = st.selectbox("Select a transaction to permanently delete:", list(transaction_dict.keys()))
        
        if st.button("Delete Selected Transaction", type="primary"):
            target_id = transaction_dict[selected_label]
            delete_transaction(target_id)
            st.success("Transaction deleted successfully!")
            st.rerun() # Refresh the app instantly to show the updated numbers
            
else:
    st.info("No transactions recorded yet. Use the sidebar to add your first entry!")
