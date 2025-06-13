def wait_for_backend(timeout=60, interval=3):
    """
    Pings the backend service until it responds successfully or a timeout is reached.
    Uses a more generous timeout and interval for free-tier cold starts.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to hit a lightweight backend endpoint (e.g., the root '/')
            response = requests.get(API_URL, timeout=5) # Small timeout for each ping attempt
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