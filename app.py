# app.py - SmartDoc AI Admin Dashboard

import streamlit as st
import requests
import os
import time
from datetime import datetime
from dotenv import load_dotenv # Used for loading environment variables locally
import pandas as pd # Import pandas for data manipulation
import plotly.express as px # Import plotly for beautiful graphs

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Configuration ---
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") # Added default for robustness

# Import the utility function to wait for the backend
from app_utils import wait_for_backend 

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Admin Dashboard - SmartDoc AI", layout="wide")
st.title("🛠 Admin Dashboard - SmartDoc AI")

# --- Initialize Session State Variables (Important for Reruns) ---
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'user_filter' not in st.session_state:
    st.session_state.user_filter = ""
if 'doc_page' not in st.session_state:
    st.session_state.doc_page = 1
if 'user_page' not in st.session_state:
    st.session_state.user_page = 1
if 'sort_order_docs' not in st.session_state:
    st.session_state.sort_order_docs = 'desc'  # Default: latest first
if 'sort_order_users' not in st.session_state:
    st.session_state.sort_order_users = 'desc' # Default: latest first
if 'backend_reachable' not in st.session_state: # Initialize backend reachable status
    st.session_state.backend_reachable = False


# --- Function to get authorization header for API requests ---
def get_auth_header():
    if not st.session_state.access_token:
        return None
    return {"Authorization": f"Bearer {st.session_state.access_token}"}

# --- Function to verify if the logged-in user has admin access ---
def verify_admin_access():
    headers = get_auth_header()
    if not headers:
        st.session_state.is_admin = False
        return False
    try:
        response = requests.get(f"{BACKEND_API_URL}/admin/users", headers=headers)
        if response.status_code == 200:
            st.session_state.is_admin = True
            return True
        elif response.status_code == 403:
            st.error(f"Access denied: {response.json().get('detail', 'Not an admin')}")
            st.session_state.is_admin = False
            return False
        elif response.status_code == 401:
             st.error("Authentication failed. Please log in again.")
             st.session_state.access_token = None
             st.session_state.is_admin = False
             return False
        else:
            st.error(f"Error verifying admin access: {response.status_code} - {response.json().get('detail', 'Unknown error')}")
            st.session_state.is_admin = False
            return False
    except requests.exceptions.ConnectionError:
        st.error("Network error: Could not connect to the backend API during admin verification. Please ensure the backend is running.")
        st.session_state.is_admin = False
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred during admin verification: {e}")
        st.session_state.is_admin = False
        return False

# --- Backend Connection Check with Spinner and Disappearing Message (moved to top-level conditional) ---
# This block runs only once per full app load or if backend_reachable is reset (e.g., on logout)
if not st.session_state.backend_reachable:
    connection_status_placeholder = st.empty() # Placeholder for connection messages
    with st.spinner("Attempting to connect to the backend API..."):
        if wait_for_backend():
            success_message_placeholder = st.empty()
            success_message_placeholder.success("Successfully connected to the backend API!")
            time.sleep(1)
            success_message_placeholder.empty()
            st.session_state.backend_reachable = True # Mark backend as reachable
        else:
            st.error("Failed to connect to the backend API. Please ensure the backend is running.")
            st.stop() # Stop the Streamlit app if backend is not reachable


# --- Admin Login Function ---
def admin_login():
    # Display login form only if backend is reachable (confirmed by the above block)
    if st.session_state.get('backend_reachable', False):
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        login_response = requests.post(
                            f"{BACKEND_API_URL}/auth/token",
                            data={"username": email.lower(), "password": password} # Normalize email here too
                        )
                        
                        if login_response.status_code == 200:
                            token_data = login_response.json()
                            st.session_state.access_token = token_data.get("access_token")
                            st.session_state.token_type = token_data.get("token_type")
                            st.session_state.user_id = token_data.get("user_id")
                            st.session_state.username = token_data.get("username")

                            if verify_admin_access():
                                st.success("Admin login successful! Redirecting to dashboard...")
                                st.rerun() 
                            else:
                                st.error("Logged in, but this account does not have administrator privileges.")
                                st.session_state.access_token = None # Clear token if not admin
                                st.session_state.is_admin = False
                        elif login_response.status_code == 401:
                            error_detail = login_response.json().get("detail", "").lower()
                            if "gemini api key is missing" in error_detail:
                                st.error("Gemini API key is missing. Please update your profile with a valid key.")
                            elif "your gemini api key is invalid" in error_detail:
                                st.error("Your Gemini API key is invalid. Please update your key or contact support.")
                            elif "incorrect email or password" in error_detail:
                                st.error("Incorrect email or password.")
                            else:
                                st.error(f"Login failed: {login_response.json().get('detail', 'Unknown error')}")
                        else:
                            st.error(f"Login failed: {login_response.json().get('detail', 'Unknown error')}")
                    except requests.exceptions.ConnectionError:
                        st.error("Could not connect to the API. Please ensure the backend is running.")
                    except Exception as e:
                        st.error(f"An unexpected error occurred during login: {e}")
    st.stop() # Stop execution if we're in the login state


# --- Data Fetching Functions (Moved to top-level for consistent definition) ---
@st.cache_data(ttl=300) # Cache for 5 minutes
def fetch_documents():
    headers = get_auth_header()
    if not headers: return []
    try:
        response = requests.get(f"{BACKEND_API_URL}/admin/documents", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch documents: {response.status_code} - {response.json().get('detail', 'Unknown error')}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("Network error: Could not connect to backend to fetch documents.")
        return []
    except Exception as e:
        st.error(f"Error fetching documents: {e}")
        return []

@st.cache_data(ttl=300) # Cache for 5 minutes
def fetch_users():
    headers = get_auth_header()
    if not headers: return []
    try:
        response = requests.get(f"{BACKEND_API_URL}/admin/users", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch users: {response.status_code} - {response.json().get('detail', 'Unknown error')}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("Network error: Could not connect to backend to fetch users.")
        return []
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []


# --- Main Application Logic (Runs if authenticated as admin) ---
if not st.session_state.get('is_admin', False):
    admin_login() # Call login function if not authenticated
else: # User is authenticated as admin
    st.sidebar.header("Navigation")
    # Add Dashboard to the navigation panel
    page = st.sidebar.radio("Go to", ["📊 Dashboard", "📄 Documents", "👤 Users", "➡️ Logout"])

    # --- Logout Logic ---
    if page == "➡️ Logout":
        st.session_state.access_token = None
        st.session_state.is_admin = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.backend_reachable = False # Reset backend status so it pings again on next login attempt

        # Clear cached data and session state variables
        st.session_state.pop('unique_user_ids', None)
        st.session_state.pop('sorted_users', None)
        st.cache_data.clear() # Clear st.cache_data for functions like fetch_documents/fetch_users
        st.cache_resource.clear() # Clear st.cache_resource as well if used

        st.success("You have been logged out successfully.")
        time.sleep(1)
        st.rerun() # Force rerun to go back to login screen


    # --- Dashboard Page ---
    elif page == "📊 Dashboard":
        st.header("📊 Admin Dashboard Overview")
        
        # Fetch all data needed for the dashboard (cached from previous runs)
        all_documents = fetch_documents()
        all_users = fetch_users()

        st.subheader("Key Metrics")
        col1, col2 = st.columns(2) # Changed to 2 columns as one metric is removed
        with col1:
            st.metric(label="Total Users", value=len(all_users))
            st.metric(label="Total Documents", value=len(all_documents)) # Moved to first column
        
        # Calculate vectorized vs. non-vectorized documents
        vectorized_count = sum(1 for doc in all_documents if doc.get('is_vectorized'))
        non_vectorized_count = len(all_documents) - vectorized_count
        
        with col2: # Moved to second column
            st.metric(label="Vectorized Docs", value=vectorized_count)
            st.metric(label="Non-Vectorized Docs", value=non_vectorized_count)


        st.subheader("Document Status Distribution")
        if all_documents:
            doc_status_data = pd.DataFrame({
                'Status': ['Vectorized', 'Non-Vectorized'],
                'Count': [vectorized_count, non_vectorized_count]
            })
            fig_doc_status = px.pie(doc_status_data, values='Count', names='Status', 
                                    title='Document Vectorization Status',
                                    color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_doc_status, use_container_width=True)
        else:
            st.info("No document data to display status distribution.")

        st.subheader("Documents Uploaded Over Time")
        if all_documents:
            # Convert to DataFrame and ensure 'upload_time' is datetime
            docs_df = pd.DataFrame(all_documents)
            
            # --- DEBUGGING: Display the DataFrame to check parsed dates ---
            # st.write("DEBUG: Docs DataFrame (raw):")
            # st.dataframe(docs_df) # Show the DataFrame as received from API
            
            if 'upload_time' in docs_df.columns and not docs_df['upload_time'].empty:
                # Attempt to convert, handle errors by coercing invalid dates to NaT
                docs_df['upload_time_dt'] = pd.to_datetime(docs_df['upload_time'], errors='coerce')
                
                # Drop rows where upload_time_dt is NaT (failed conversions)
                docs_df = docs_df.dropna(subset=['upload_time_dt'])

                if not docs_df.empty:
                    # Decide on granularity: if data spans multiple days, group by date.
                    # If all data is on the same day, group by hour for better visibility.
                    min_date = docs_df['upload_time_dt'].min().date()
                    max_date = docs_df['upload_time_dt'].max().date()

                    if min_date == max_date:
                        # All data on the same day, group by hour
                        docs_df['upload_period'] = docs_df['upload_time_dt'].dt.floor('H') # Group by hour
                        x_axis_label = 'Hour of Day'
                        # tickformat = '%H:%M' # Removed tickformat for bar chart
                    else:
                        # Data spans multiple days, group by date
                        docs_df['upload_period'] = docs_df['upload_time_dt'].dt.date
                        x_axis_label = 'Date'
                        # tickformat = '%Y-%m-%d' # Removed tickformat for bar chart

                    # Group by period and count documents
                    docs_over_time = docs_df.groupby('upload_period').size().reset_index(name='count')
                    docs_over_time = docs_over_time.sort_values('upload_period')

                    # --- DEBUGGING: Display aggregated DataFrame for plotting ---
                    # st.write("DEBUG: Docs Aggregated Data for Plotting:")
                    # st.dataframe(docs_over_time)

                    # Changed from px.line to px.bar for better comprehension with sparse data
                    fig_docs_time = px.bar(docs_over_time, x='upload_period', y='count', 
                                            title='Documents Uploaded Over Time',
                                            labels={'upload_period': x_axis_label, 'count': 'Number of Documents'},
                                            text='count') # Show count directly on bars
                    fig_docs_time.update_traces(textposition='outside') # Position text outside bars
                    fig_docs_time.update_layout(uniformtext_minsize=8, uniformtext_mode='hide') # Text sizing
                    # fig_docs_time.update_xaxes(rangeslider_visible=True, tickformat=tickformat) # Removed rangeslider for bar chart
                    st.plotly_chart(fig_docs_time, use_container_width=True)
                else:
                    st.info("All document 'upload_time' values were invalid or no data after filtering for trend analysis.")
            else:
                st.info("Document data missing 'upload_time' or is empty for trend analysis.")
        else:
            st.info("No document data to display upload trends.")

        st.subheader("Users Registered Over Time")
        if all_users:
            # Convert to DataFrame and ensure 'created_at' is datetime
            users_df = pd.DataFrame(all_users)
            # --- DEBUGGING: Display the DataFrame to check parsed dates ---
            # st.write("DEBUG: Users DataFrame (raw):")
            # st.dataframe(users_df)

            if 'created_at' in users_df.columns and not users_df['created_at'].empty:
                # Attempt to convert, handle errors by coercing invalid dates to NaT
                users_df['created_at_dt'] = pd.to_datetime(users_df['created_at'], errors='coerce')
                
                # Drop rows where created_at_dt is NaT (failed conversions)
                users_df = users_df.dropna(subset=['created_at_dt'])

                if not users_df.empty:
                    # Decide on granularity: if data spans multiple days, group by date.
                    # If all data is on the same day, group by hour for better visibility.
                    min_date = users_df['created_at_dt'].min().date()
                    max_date = users_df['created_at_dt'].max().date()

                    if min_date == max_date:
                        # All data on the same day, group by hour
                        users_df['registration_period'] = users_df['created_at_dt'].dt.floor('H') # Group by hour
                        x_axis_label = 'Hour of Day'
                        # tickformat = '%H:%M' # Removed tickformat for bar chart
                    else:
                        # Data spans multiple days, group by date
                        users_df['registration_period'] = users_df['created_at_dt'].dt.date
                        x_axis_label = 'Date'
                        # tickformat = '%Y-%m-%d' # Removed tickformat for bar chart

                    # Group by period and count users
                    users_over_time = users_df.groupby('registration_period').size().reset_index(name='count')
                    users_over_time = users_over_time.sort_values('registration_period')

                    # --- DEBUGGING: Display aggregated DataFrame for plotting ---
                    # st.write("DEBUG: Users Aggregated Data for Plotting:")
                    # st.dataframe(users_over_time)

                    # Changed from px.line to px.bar for better comprehension with sparse data
                    fig_users_time = px.bar(users_over_time, x='registration_period', y='count', 
                                             title='Users Registered Over Time',
                                             labels={'registration_period': x_axis_label, 'count': 'Number of Users'},
                                             color_discrete_sequence=['purple'],
                                             text='count') # Show count directly on bars
                    fig_users_time.update_traces(textposition='outside') # Position text outside bars
                    fig_users_time.update_layout(uniformtext_minsize=8, uniformtext_mode='hide') # Text sizing
                    # fig_users_time.update_xaxes(rangeslider_visible=True, tickformat=tickformat) # Removed rangeslider for bar chart
                    st.plotly_chart(fig_users_time, use_container_width=True)
                else:
                    st.info("All user 'created_at' values were invalid or no data after filtering for trend analysis.")
            else:
                st.info("User data missing 'created_at' or is empty for trend analysis.")
        else:
            st.info("No user data to display registration trends.")


    # --- Documents Page ---
    elif page == "📄 Documents":
        st.header("📁 All Uploaded Documents")
        
        all_documents = fetch_documents() 
        
        if 'unique_user_ids' not in st.session_state:
            st.session_state.unique_user_ids = sorted(list({str(doc['user_id']) for doc in all_documents}))
        user_ids = st.session_state.unique_user_ids
        
        search_col1, search_col2, sort_col = st.columns([1, 1, 1])
        with search_col1:
            if 'last_typing_time' not in st.session_state:
                st.session_state.last_typing_time = 0

            new_query = st.text_input("Search by filename", st.session_state.search_query)

            if new_query != st.session_state.search_query:
                current_time = time.time()
                if current_time - st.session_state.last_typing_time > 1.0:
                    st.session_state.search_query = new_query
                    st.session_state.doc_page = 1
                    st.rerun()
                else:
                    st.session_state.last_typing_time = current_time
        with search_col2:
            user_options = ['All Users'] + user_ids
            selected_user = st.selectbox(
                "Filter by User ID", 
                user_options,
                index=0 if not st.session_state.user_filter else user_options.index(st.session_state.user_filter)
            )
            st.session_state.user_filter = selected_user if selected_user != 'All Users' else ""
        with sort_col:
           if st.button("🔽 Sort Latest First" if st.session_state.sort_order_docs == 'asc' else "🔼 Sort Oldest First"):
                st.session_state.sort_order_docs = 'desc' if st.session_state.sort_order_docs == 'asc' else 'asc'
                st.rerun()
        
        if all_documents:
            filtered_docs = all_documents
            if st.session_state.search_query:
                filtered_docs = [doc for doc in filtered_docs 
                               if st.session_state.search_query.lower() in doc['filename'].lower()]
            if st.session_state.user_filter:
                filtered_docs = [doc for doc in filtered_docs 
                               if st.session_state.user_filter == str(doc['user_id'])]
            
            filtered_docs = sorted(filtered_docs, 
                                  key=lambda x: x['upload_time'], 
                                  reverse=(st.session_state.sort_order_docs == 'desc'))
            
            if not filtered_docs:
                st.info("No documents found matching your search criteria.")
            else:
                PAGE_SIZE = 8
                total_pages = max(1, len(filtered_docs) // PAGE_SIZE + (1 if len(filtered_docs) % PAGE_SIZE > 0 else 0))
                
                if st.session_state.doc_page > total_pages:
                    st.session_state.doc_page = 1
                
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    if st.button("◀ Prev", disabled=st.session_state.doc_page == 1, key="doc_prev_btn"):
                        st.session_state.doc_page -= 1
                        st.rerun()
                with col2:
                    st.markdown(f"<div style='text-align: center'>Page {st.session_state.doc_page}/{total_pages}</div>", unsafe_allow_html=True)
                with col3:
                    if st.button("Next ▶", disabled=st.session_state.doc_page >= total_pages, key="doc_next_btn"):
                        st.session_state.doc_page += 1
                        st.rerun()
                
                start_idx = (st.session_state.doc_page - 1) * PAGE_SIZE
                end_idx = min(st.session_state.doc_page * PAGE_SIZE, len(filtered_docs))
                
                current_docs = filtered_docs[start_idx:end_idx]
                for doc in current_docs:
                    with st.expander(f"{doc['filename']} - {doc['user_id']}"):
                        st.markdown(f"**Document ID:** `{doc['id']}`")
                        st.markdown(f"**Filename:** `{doc['filename']}`")
                        st.markdown(f"**File Type:** `{doc['file_type']}`")
                        st.markdown(f"**Upload Time:** `{doc['upload_time']}`")
                        st.markdown(f"**Status:** {'✅ Vectorized' if doc.get('is_vectorized') else '❌ Not Vectorized'}")
                        st.markdown(f"**Path:** `{doc.get('path')}`")
                        st.markdown(f"**Uploaded by User ID:** `{doc.get('user_id')}`")
                        st.markdown(f"**Summary:** {doc.get('summary', 'No summary available')}")
                        
                        if st.button(f"🗑️ Delete Document", key=f"del_doc_{doc['id']}"):
                            try:
                                response = requests.delete(
                                    f"{BACKEND_API_URL}/admin/documents/{doc['id']}", 
                                    headers=get_auth_header()
                                )
                                if response.status_code == 200:
                                    fetch_documents.clear()
                                    if 'unique_user_ids' in st.session_state:
                                        del st.session_state.unique_user_ids
                                    st.success("Document deleted successfully!")
                                    st.session_state.doc_page = 1
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete document: {response.json().get('detail', 'Unknown error')}")
                            except Exception as e:
                                st.error(f"Error: {e}")
        else:
            st.info("No documents found.")

    # --- Users Page ---
    elif page == "👤 Users":
        st.header("👥 Registered Users")
        
        sort_col1, sort_col2 = st.columns([1, 3])
        with sort_col1:
            if st.button("🔽 Sort Latest First" if st.session_state.sort_order_users == 'asc' else "🔼 Sort Oldest First", key="user_sort_btn"): # Added key for uniqueness
                st.session_state.sort_order_users = 'desc' if st.session_state.sort_order_users == 'asc' else 'asc'
                st.rerun()
        
        users = fetch_users() # Call the now globally defined function
        
        if users:
            if 'sorted_users' not in st.session_state or st.session_state.sort_order_users != st.session_state.get('_prev_sort_order_users', None):
                st.session_state.sorted_users = sorted(users, 
                                              key=lambda x: x['created_at'],
                                              reverse=(st.session_state.sort_order_users == 'desc'))
                st.session_state._prev_sort_order_users = st.session_state.sort_order_users
            users = st.session_state.sorted_users
            
            PAGE_SIZE = 8
            total_pages = max(1, len(users) // PAGE_SIZE + (1 if len(users) % PAGE_SIZE > 0 else 0))
            
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if st.button("◀ Prev", disabled=st.session_state.user_page == 1, key="user_prev_btn"):
                    st.session_state.user_page -= 1
                    st.rerun()
            with col2:
                st.markdown(f"<div style='text-align: center'>Page {st.session_state.user_page}/{total_pages}</div>", unsafe_allow_html=True)
            with col3:
                if st.button("Next ▶", disabled=st.session_state.user_page >= total_pages, key="user_next_btn"):
                    st.session_state.user_page += 1
                    st.rerun()
            
            start_idx = (st.session_state.user_page - 1) * PAGE_SIZE
            end_idx = min(st.session_state.user_page * PAGE_SIZE, len(users))
            
            current_users = users[start_idx:end_idx]
            
            user_data_display = []
            for user in current_users:
                user_data_display.append({
                    "ID": str(user['id']), # Ensure UUID is converted to string for display
                    "Username": user['username'],
                    "Email": user['email'],
                    "Role": '👑 Admin' if bool(int(user.get('is_admin', 0))) else '👤 User',
                    "Created": datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M:%S") if 'created_at' in user else 'N/A',
                    "Status": '✅ Active' if bool(int(user.get('is_active', 0))) else '❌ Inactive',
                    "Gemini API Key Set": "Yes" if user.get('gemini_api_key') else "No"
                })
            
            st.dataframe(
                user_data_display,
                column_config={
                    "ID": st.column_config.TextColumn("User ID"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Role": st.column_config.TextColumn("Role", width="small"),
                    "Username": st.column_config.TextColumn("Username", width="medium"),
                    "Email": st.column_config.TextColumn("Email", width="medium"),
                    "Created": st.column_config.TextColumn("Created At", width="medium"),
                    "Gemini API Key Set": st.column_config.TextColumn("Gemini Key")
                },
                hide_index=True,
                use_container_width=True
            )
            
            selected_email = st.selectbox("View user details", [""] + [user['email'] for user in users], key="user_detail_select")
            if selected_email:
                user = next((u for u in users if u['email'] == selected_email), None)
                if user:
                    is_admin = bool(int(user.get('is_admin', 0)))
                    is_active = bool(int(user.get('is_active', 0)))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("User Information")
                        st.markdown(f"**User ID:** `{user['id']}`")
                        st.markdown(f"**Username:** `{user['username']}`")
                        st.markdown(f"**Email:** `{user['email']}`")
                    
                    with col2:
                        st.subheader("Account Status")
                        st.markdown(f"**Role:** {'👑 Admin' if is_admin else '👤 User'}")
                        st.markdown(f"**Account Created:** `{datetime.fromisoformat(user['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S') if 'created_at' in user else 'N/A'}`")
                        st.markdown(f"**Status:** {'✅ Active' if is_active else '❌ Inactive'}")
                        st.markdown(f"**Gemini API Key:** {'Yes' if user.get('gemini_api_key') else 'No (or not visible)'}")
                    
                    if not is_admin:
                        st.divider()
                        st.subheader("⚠️ Danger Zone")
                        delete_state_key = f"delete_state_{user['id']}"
                        
                        if delete_state_key not in st.session_state:
                            st.session_state[delete_state_key] = False
                        
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if st.button("🗑️ Delete User", key=f"del_user_{user['id']}", type="primary"):
                                st.session_state[delete_state_key] = True
                        
                        if st.session_state[delete_state_key]:
                            with col2:
                                st.warning("⚠️ WARNING: This will permanently delete all files uploaded by this user!")
                                if st.button("✔️ Confirm Delete", key=f"confirm_del_{user['id']}", type="primary"):
                                    try:
                                        response = requests.delete(
                                            f"{BACKEND_API_URL}/admin/users/{user['id']}", 
                                            headers=get_auth_header()
                                        )
                                        if response.status_code == 200:
                                            fetch_documents.clear()
                                            fetch_users.clear()
                                            st.session_state.pop('unique_user_ids', None)
                                            st.session_state.pop('sorted_users', None)
                                            st.success("User and all associated documents deleted successfully!")
                                            st.session_state[delete_state_key] = False
                                            st.session_state.user_page = 1
                                            st.rerun()
                                        else:
                                            st.error(f"Failed to delete user: {response.json().get('detail', 'Unknown error')}")
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                                if st.button("Cancel", key=f"cancel_del_{user['id']}"):
                                    st.session_state[delete_state_key] = False
                                    st.rerun()
        else:
            st.info("No users found.")
