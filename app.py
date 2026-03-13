import streamlit as st
import requests
import re
import time

# --- 1. UNIVERSAL SECURITY LAYER ---
def get_device_fingerprint():
    """Identifies the browser/OS combo without cookies or DB."""
    return hash(st.context.headers.get('User-Agent', 'unknown'))

def enforce_security():
    # Initialize session states
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "device_bindings" not in st.session_state:
        # This keeps track of which key belongs to which device for the current uptime
        st.session_state.device_bindings = {}

    if not st.session_state.authenticated:
        st.title("🛡️ Secure Access")
        st.info("This is a private tool. Please enter your personal access code.")
        
        # Pull keys directly from Streamlit Secrets
        try:
            valid_keys = st.secrets["access_keys"]
        except:
            st.error("Security Error: Access keys not configured in Secrets.")
            st.stop()

        input_code = st.text_input("Personal Access Code", type="password")
        
        if st.button("Unlock Application"):
            if input_code in valid_keys:
                current_fingerprint = get_device_fingerprint()
                
                # Check if this code is already bound to a different device
                if input_code in st.session_state.device_bindings:
                    bound_device = st.session_state.device_bindings[input_code]
                    if current_fingerprint == bound_device:
                        st.session_state.authenticated = True
                        st.session_state.username = valid_keys[input_code]
                        st.rerun()
                    else:
                        st.error("🚫 Access Denied: This code is already in use on another device.")
                else:
                    # First use! Bind the code to this device
                    st.session_state.device_bindings[input_code] = current_fingerprint
                    st.session_state.authenticated = True
                    st.session_state.username = valid_keys[input_code]
                    st.success(f"Verified: Welcome {st.session_state.username}")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ Invalid Code.")
        st.stop()
    return True

# --- 2. START SECURITY CHECK ---
if enforce_security():
    
    # --- API Helper Class ---
    class ReverbManager:
        def __init__(self, token):
            self.headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/hal+json",
                "Accept": "application/hal+json",
                "Accept-Version": "3.0"
            }
            self.base_url = "https://api.reverb.com/api"

        def get_listing_id(self, url):
            match = re.search(r'item/(\d+)', url)
            return match.group(1) if match else None

        def fetch_source(self, listing_id):
            res = requests.get(f"{self.base_url}/listings/{listing_id}", headers=self.headers)
            return res.json() if res.status_code == 200 else None

        def create_draft(self, src, ship_id, custom_description):
            try:
                price_str = str(src.get("price", {}).get("amount", "0")).replace(",", "")
                new_price = f"{(float(price_str) * 0.4):.2f}"
            except: 
                new_price = "0.00"

            payload = {
                "make": src.get("make"), "model": src.get("model"), "title": src.get("title"),
                "description": custom_description, "shipping_profile_id": int(ship_id),
                "price": {"amount": new_price, "currency": "USD"}
            }
            # Simplified photo mapping for bulk use
            photo_urls = [p.get("_links", {}).get("full", {}).get("href") for p in src.get("photos", []) if p]
            payload["photos"] = photo_urls

            return requests.post(f"{self.base_url}/listings", headers=self.headers, json=payload)

    # --- 3. MAIN INTERFACE ---
    st.set_page_config(page_title="Reverb Bulk Manager", layout="wide")

    # Reverb API Token Section
    if "reverb_token" not in st.session_state:
        st.title(f"🎸 Hello, {st.session_state.username}")
        st.caption("Please connect your Reverb account to continue.")
        token_input = st.text_input("Reverb API Token", type="password")
        if st.button("Connect Account"):
            if token_input:
                st.session_state.reverb_token = token_input
                st.rerun()
        st.stop()

    api = ReverbManager(st.session_state.reverb_token)

    # --- UI Layout ---
    st.title("🎸 Reverb Bulk Tool")
    st.sidebar.info(f"User: {st.session_state.username}")
    if st.sidebar.button("Log Out / Lock App"):
        st.session_state.authenticated = False
        st.rerun()

    tab1, tab2 = st.tabs(["🆕 Bulk Clone", "📋 Manage Drafts"])

    with tab1:
        st.header("Bulk Clone at 60% Off")
        col_l, col_r = st.columns(2)
        with col_l:
            urls_input = st.text_area("Paste URLs (one per line)", height=200)
            ship_id = st.text_input("Shipping Profile ID")
        with col_r:
            custom_desc = st.text_area("Custom Description (Applied to all)", height=200)

        if st.button("🚀 Start Bulk Process"):
            if not urls_input or not ship_id:
                st.warning("URLs and Shipping ID are required.")
            else:
                urls = [u.strip() for u in urls_input.replace("\n", ",").split(",") if u.strip()]
                progress = st.progress(0)
                
                for i, url in enumerate(urls):
                    l_id = api.get_listing_id(url)
                    if l_id:
                        src = api.fetch_source(l_id)
                        if src:
                            res = api.create_draft(src, ship_id, custom_desc)
                            if res.status_code in [201, 202]:
                                st.toast(f"Done: {src.get('title')[:30]}...")
                            else:
                                st.error(f"Error {res.status_code} on {url}")
                    
                    time.sleep(1) # API friendly delay
                    progress.progress((i + 1) / len(urls))
                st.success("Batch finished!")
