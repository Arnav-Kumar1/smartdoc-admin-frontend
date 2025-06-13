# admin only dashboard
import streamlit as st
import requests
import os
import time

st.set_page_config(page_title="Admin Dashboard - SmartDoc AI", layout="wide")
st.title("🛠 Admin Dashboard - SmartDoc AI")

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["📄 Documents", "👤 Users"])

def get_auth_header():
    if 'access_token' not in st.session_state:
        st.error("Please login first")
        return None
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


# Add after imports

def verify_admin_access():
    headers = get_auth_header()
    if not headers:
        st.session_state.is_admin = False
        st.error("No authentication token found")
        return False
    try:
        response = requests.get(f"{API_URL}/admin/users", headers=headers)
        if response.status_code == 200:
            st.session_state.is_admin = True  # Store in session
            return True
        elif response.status_code == 403:
            st.error(f"Access denied: {response.json().get('detail', 'Not an admin')}")
        else:
            st.error(f"Error verifying admin status: {response.status_code}")
        st.session_state.is_admin = False  # Store in session
        return False
    except Exception as e:
        st.error(f"Error checking admin status: {str(e)}")
        st.session_state.is_admin = False  # Store in session
        return False

def admin_login():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            try:
                response = requests.post(
                    f"{API_URL}/auth/token",
                    data={"username": email, "password": password}
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.access_token = data["access_token"]
                    
                    # Verify admin access after login
                    if verify_admin_access():
                        st.success("Logged in as admin successfully!")
                        st.rerun()
                    else:
                        st.session_state.pop('access_token', None)
                else:
                    st.error(f"Invalid credentials: {response.json().get('detail', 'Unknown error')}")
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

# Add this check at the start of the app
if 'access_token' in st.session_state:
    if 'is_admin' not in st.session_state:
        verify_admin_access()  # Verify only once per session
    
    if not st.session_state.get('is_admin', False):
        st.error("Access denied: Admin privileges required")
        st.session_state.pop('access_token', None)
        st.stop()

# Modify fetch_documents
@st.cache_data(ttl=120)  # Cache for 1 minute
def fetch_documents():
    headers = get_auth_header()
    if not headers:
        return []
    try:
        response = requests.get(f"{API_URL}/admin/documents", headers=headers)  # Changed endpoint
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch documents")
            return []
    except Exception as e:
        st.error(f"Error: {e}")
        return []

# Modify fetch_users
@st.cache_data(ttl=120)  # Cache for 1 minute
def fetch_users():
    headers = get_auth_header()
    if not headers:
        return []
    try:
        response = requests.get(f"{API_URL}/admin/users", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch users")
            return []
    except Exception as e:
        st.error(f"Error: {e}")
        return []

# Add before the page check
if 'access_token' not in st.session_state:
    admin_login()
    st.stop()


# Add to session state initialization
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'user_filter' not in st.session_state:
    st.session_state.user_filter = ""

# Add this with other session state initializations at the start of the file
if 'doc_page' not in st.session_state:
    st.session_state.doc_page = 1
if 'user_page' not in st.session_state:
    st.session_state.user_page = 1

# Add to session state initialization
if 'sort_order_docs' not in st.session_state:
    st.session_state.sort_order_docs = 'desc'  # Default: ascending (oldest first)
if 'sort_order_users' not in st.session_state:
    st.session_state.sort_order_users = 'desc'

# In Documents section
if page == "📄 Documents":
    st.header("📁 All Uploaded Documents")
    
    # Get all unique user IDs from documents
    docs = fetch_documents()
    
    if 'unique_user_ids' not in st.session_state:
        st.session_state.unique_user_ids = sorted(list({str(doc['user_id']) for doc in docs}))
    user_ids = st.session_state.unique_user_ids
    
    # Search and filter controls
    search_col1, search_col2, sort_col = st.columns([1, 1, 1])
    with search_col1:
        # st.session_state.search_query = st.text_input("Search by filename", st.session_state.search_query)
        # Add debounce to search
        if 'last_typing_time' not in st.session_state:
            st.session_state.last_typing_time = 0

        new_query = st.text_input("Search by filename", st.session_state.search_query)

        # Only update if 1 second passed since last keystroke
        if new_query != st.session_state.search_query:
            current_time = time.time()
            if current_time - st.session_state.last_typing_time > 1.0:
                st.session_state.search_query = new_query
                st.session_state.doc_page = 1  # Reset to first page
                st.rerun()
            else:
                st.session_state.last_typing_time = current_time
    with search_col2:
        # Add 'All Users' option at beginning
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
    
    if docs:
        # Apply search filters
        filtered_docs = docs
        if st.session_state.search_query:
            filtered_docs = [doc for doc in filtered_docs 
                           if st.session_state.search_query.lower() in doc['filename'].lower()]
        if st.session_state.user_filter:
            filtered_docs = [doc for doc in filtered_docs 
                           if st.session_state.user_filter == str(doc['user_id'])]
        
        # Then apply sorting
        filtered_docs = sorted(filtered_docs, 
                              key=lambda x: x['upload_time'], 
                              reverse=(st.session_state.sort_order_docs == 'desc'))
        
        if not filtered_docs:
            st.info("No documents found matching your search criteria.")
            st.stop()
            
        PAGE_SIZE = 8
        total_pages = max(1, len(filtered_docs) // PAGE_SIZE + (1 if len(filtered_docs) % PAGE_SIZE > 0 else 0))
        
        # Reset page number if it exceeds the new total pages
        if st.session_state.doc_page > total_pages:
            st.session_state.doc_page = 1
        
        # Pagination controls in one line
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("◀ Prev", disabled=st.session_state.doc_page == 1):
                st.session_state.doc_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.doc_page}/{total_pages}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ▶", disabled=st.session_state.doc_page >= total_pages):
                st.session_state.doc_page += 1
                st.rerun()
        
        # Display current page
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
                
                # Add delete button
                if st.button(f"🗑️ Delete Document", key=f"del_doc_{doc['id']}"):
                    try:
                        response = requests.delete(
                            f"{API_URL}/admin/documents/{doc['id']}", 
                            headers=get_auth_header()
                        )
                        if response.status_code == 200:
                            fetch_documents.clear()
                            if 'unique_user_ids' in st.session_state:
                                del st.session_state.unique_user_ids
                            st.success("Document deleted successfully!")
                            st.session_state.doc_page = 1  # Reset to first page
                            st.rerun()
                        else:
                            st.error("Failed to delete document")
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.info("No documents found.")

# In Users section
elif page == "👤 Users":
    st.header("👥 Registered Users")
    
    # Add sort control
    sort_col1, sort_col2 = st.columns([1, 3])
    with sort_col1:
        if st.button("🔽 Sort Latest First" if st.session_state.sort_order_docs == 'asc' else "🔼 Sort Oldest First"):
            st.session_state.sort_order_users = 'desc' if st.session_state.sort_order_users == 'asc' else 'asc'
            st.rerun()
    
    users = fetch_users()
    
    if users:
        # Sort users by created_at
        if 'sorted_users' not in st.session_state:
            st.session_state.sorted_users = sorted(users, 
                                          key=lambda x: x['created_at'],
                                          reverse=(st.session_state.sort_order_users == 'desc'))
        users = st.session_state.sorted_users
        
        user_data = []
        
        PAGE_SIZE = 8
        total_pages = max(1, len(users) // PAGE_SIZE + (1 if len(users) % PAGE_SIZE > 0 else 0))
        
        # Pagination controls in one line
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("◀ Prev", disabled=st.session_state.user_page == 1):
                st.session_state.user_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.user_page}/{total_pages}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ▶", disabled=st.session_state.user_page >= total_pages):
                st.session_state.user_page += 1
                st.rerun()
        
        # Display current page
        start_idx = (st.session_state.user_page - 1) * PAGE_SIZE
        end_idx = min(st.session_state.user_page * PAGE_SIZE, len(users))
        
        for user in users[start_idx:end_idx]:
            user_data.append({
                "ID": user['id'],
                "Username": user['username'],
                "Email": user['email'],
                "Role": '👑 Admin' if bool(int(user.get('is_admin', 0))) else '👤 User',
                "Created": user.get('created_at'),
                "Status": '✅ Active' if bool(int(user.get('is_active', 0))) else '❌ Inactive',
            })
        
        st.dataframe(
            user_data,
            column_config={
                "ID": st.column_config.TextColumn("User ID"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Role": st.column_config.TextColumn("Role", width="small"),
                "Username": st.column_config.TextColumn("Username", width="medium"),
                "Email": st.column_config.TextColumn("Email", width="medium"),
                "Created": st.column_config.TextColumn("Created At", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Detailed view for selected user
        selected_email = st.selectbox("View user details", [""] + [user['email'] for user in users])
        if selected_email:
            user = next((u for u in users if u['email'] == selected_email), None)
            if user:
                is_admin = bool(int(user.get('is_admin', 0)))
                is_active = bool(int(user.get('is_active', 0)))
                
                # Create columns for better layout
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("User Information")
                    st.markdown(f"**User ID:** `{user['id']}`")
                    st.markdown(f"**Username:** `{user['username']}`")
                    st.markdown(f"**Email:** `{user['email']}`")
                
                with col2:
                    st.subheader("Account Status")
                    st.markdown(f"**Role:** {'👑 Admin' if is_admin else '👤 User'}")
                    st.markdown(f"**Account Created:** `{user.get('created_at')}`")
                    st.markdown(f"**Status:** {'✅ Active' if is_active else '❌ Inactive'}")
                
                # Only show delete option for non-admin users
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
                                        f"{API_URL}/admin/users/{user['id']}", 
                                        headers=get_auth_header()
                                    )
                                    if response.status_code == 200:
                                        fetch_documents.clear()
                                        fetch_users.clear()
                                        if 'unique_user_ids' in st.session_state:
                                            del st.session_state.unique_user_ids
                                        if 'sorted_users' in st.session_state:
                                            del st.session_state.sorted_users
                                        st.success("User and all associated documents deleted successfully!")
                                        st.session_state[delete_state_key] = False
                                        st.session_state.user_page = 1  # Reset to first page
                                        st.rerun()
                                    else:
                                        st.error(f"Failed to delete user: {response.json().get('detail', 'Unknown error')}")
                                except Exception as e:
                                    st.error(f"Error: {e}")
