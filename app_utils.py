import time
import requests
import streamlit as st
import os
BACKEND_API_URL = os.getenv("BACKEND_API_URL")




def wait_for_backend(timeout=60, interval=3):
    """
    Pings the backend service until it responds successfully or a timeout is reached.
    Uses a more generous timeout and interval for free-tier cold starts.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to hit a lightweight backend endpoint (e.g., the root '/')
            response = requests.get(BACKEND_API_URL, timeout=5) # Small timeout for each ping attempt
            if response.status_code == 200:
                return True # Backend is awake and responsive
        except requests.exceptions.ConnectionError:
            # Backend not awake yet, or connection refused; keep trying
            pass
        except requests.exceptions.Timeout:
            # Request timed out, backend might be slow to respond; keep trying
            pass
        except Exception as e:
            # Catch any other unexpected errors during ping
            print(f"Error during backend ping attempt: {type(e).__name__} - {e}")
            pass
        time.sleep(interval) # Wait before retrying
    return False # Timeout reached, backend did not become responsive

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


def fetch_users(token: str): # Accepts token as argument for caching key
    headers = {"Authorization": f"Bearer {token}"} if token else None
    if not headers:
        return []
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
