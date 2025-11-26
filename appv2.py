# app.py
import streamlit as st
import openai
import os
import sqlite3
from datetime import datetime
from gtts import gTTS
import tempfile
import traceback

# -----------------------------
#   CONFIG
# -----------------------------
# IMPORTANT: do NOT place your API key here in plaintext.
# Set environment variable: OPENAI_API_KEY or use Streamlit secrets.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

DB_PATH = "smart_trolley.db"

# -----------------------------
#   DATABASE SETUP
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_history (
            phone TEXT,
            product_name TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------
#   PRODUCT DATA (example)
# -----------------------------
product_data = {
    "RFID001": {"name": "Organic Apples", "quantity": 20, "mrp": 200, "discounted_rate": 180},
    "RFID002": {"name": "Whole Wheat Bread", "quantity": 50, "mrp": 40, "discounted_rate": 35},
    "RFID003": {"name": "Almond Milk", "quantity": 30, "mrp": 120, "discounted_rate": 100},
    "RFID004": {"name": "Olive Oil - 500ml", "quantity": 15, "mrp": 450, "discounted_rate": 400},
    "RFID005": {"name": "Basmati Rice - 1kg", "quantity": 25, "mrp": 150, "discounted_rate": 130},
}

# -----------------------------
#   HELPER FUNCTIONS
# -----------------------------
def get_product_details(rfid):
    return product_data.get(rfid)

def add_purchase_history(phone, product_name):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO purchase_history (phone, product_name, timestamp) VALUES (?, ?, ?)",
            (phone, product_name, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def get_user_history(phone):
    if not phone:
        return []
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT product_name, timestamp FROM purchase_history WHERE phone=? ORDER BY timestamp DESC", (phone,))
    rows = c.fetchall()
    conn.close()
    # return a list of product names (most recent first)
    return [row[0] for row in rows]

def safe_openai_chat(prompt, system=None, model="gpt-4"):
    """
    Wrapper with basic error handling. Returns string or an error message.
    """
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=800,
            temperature=0.8
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        # Log to Streamlit (could be replaced with proper logging)
        st.error("Error calling OpenAI API. See console for details.")
        print("OpenAI API call failed:", e)
        traceback.print_exc()
        return "Sorry — could not get a response from the recommendation engine at the moment."

def get_recommendations(product_name, history):
    # history is a list of purchased product names
    history_text = ", ".join(history) if history else "No prior purchases."
    prompt = (
        f"The user is interested in {product_name}.\n"
        f"User purchase history: {history_text}\n\n"
        "Suggest 4-6 personalized complementary items (short list), "
        "one useful tip (e.g., storage/cooking), one reminder (e.g., expiry or pairings), details about previous purchases - give suggestion like don't buy this product as it is recently bought or repeat this product its going to end in your kitchen based on the quantities and days "
        "and any current deal suggestions or coupon ideas (if applicable). Keep it concise and friendly."
    )
    return safe_openai_chat(prompt)

def get_product_answer(product_name, inquiry):
    prompt = f"The user asked about {product_name}: {inquiry}\nProvide a concise helpful answer (2-4 sentences) and one related tip."
    return safe_openai_chat(prompt)

def generate_final_bill(cart):
    total_amount = sum(item["discounted_rate"] for item in cart)
    bill_lines = []
    bill_lines.append("### 🧾 Final Bill")
    bill_lines.append("")
    bill_lines.append("| Item | Price (₹) |")
    bill_lines.append("|------|-----------|")
    for item in cart:
        bill_lines.append(f"| {item['name']} | {item['discounted_rate']} |")
    bill_lines.append("")
    bill_lines.append(f"### **Total: ₹{total_amount}**")
    return "\n".join(bill_lines)

def text_to_speech_savefile(text, lang="en"):
    """
    Saves TTS to a temporary mp3 file and returns the path.
    """
    if not text or text.strip() == "":
        return None
    try:
        tts = gTTS(text, lang=lang)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        tts.save(tmp_path)
        return tmp_path
    except Exception as e:
        print("TTS failed:", e)
        traceback.print_exc()
        return None

# -----------------------------
#   STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Smart Trolley", layout="wide")
st.title("🛒 SMART TROLLEY")

# Session state initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "phone" not in st.session_state:
    st.session_state.phone = None
if "cart" not in st.session_state:
    st.session_state.cart = []
if "checkout_stage" not in st.session_state:
    # None, "awaiting_phone", "confirm" etc.
    st.session_state.checkout_stage = None
if "checkout_phone" not in st.session_state:
    st.session_state.checkout_phone = ""

# -----------------------------
#   SIDEBAR: LOG IN / SIGN UP
# -----------------------------
with st.sidebar:
    st.header("🔐 Authentication")

    menu = st.radio("Select Option", ["Sign In", "Sign Up"])

    phone_input = st.text_input("Phone Number", key="sidebar_phone")
    password_input = st.text_input("Password", type="password", key="sidebar_password")

    if menu == "Sign Up":
        if st.button("Create Account"):
            if not phone_input or not password_input:
                st.error("Please enter a phone and password.")
            else:
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT phone FROM users WHERE phone=?", (phone_input,))
                if c.fetchone():
                    st.error("Phone number already registered.")
                else:
                    c.execute("INSERT INTO users (phone, password) VALUES (?, ?)", (phone_input, password_input))
                    conn.commit()
                    st.success("Account created successfully!")
                conn.close()

    if menu == "Sign In":
        if st.button("Login"):
            if not phone_input or not password_input:
                st.error("Please enter phone and password.")
            else:
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE phone=? AND password=?", (phone_input, password_input))
                if c.fetchone():
                    st.session_state.logged_in = True
                    st.session_state.phone = phone_input
                    st.success("Logged in successfully!")
                else:
                    st.error("Invalid login.")
                conn.close()

    if st.session_state.logged_in:
        st.info(f"Logged in as: {st.session_state.phone}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.phone = None
            st.session_state.cart = []
            st.session_state.checkout_stage = None
            st.session_state.checkout_phone = ""
            st.success("Logged out.")

# -----------------------------
#   MAIN PANEL
# -----------------------------
st.subheader("📘 Product Scanner")

rfid = st.text_input("Enter RFID Code", key="rfid_input")

if rfid:
    product = get_product_details(rfid.strip())
    if product:
        st.write(f"### **{product['name']}**")
        st.write(f"- Quantity: {product['quantity']}")
        st.write(f"- MRP: ₹{product['mrp']}")
        st.write(f"- Discounted: ₹{product['discounted_rate']}")

        add_opt = st.radio("Add to Cart?", ["No", "Yes"], key="add_opt")

        inquiry = st.text_input("Any questions about the product? (Type 'no' to skip)", key="inquiry_input")

        if st.button("Submit Product Action"):
            if add_opt == "Yes":
                st.session_state.cart.append(product.copy())  # copy to avoid aliasing
                if st.session_state.logged_in:
                    # Only mark purchase history on confirmed payment, not on add-to-cart.
                    pass
                st.success("Item added to cart (local session).")

                # Provide immediate recommendations based on DB-stored history + current cart (if logged in or if user provides phone)
                history = get_user_history(st.session_state.phone) if st.session_state.logged_in else []
                # include current cart items (session) as context but NOT saved as purchase history yet
                rec = get_recommendations(product["name"], history + [p["name"] for p in st.session_state.cart])
                st.write("### 🎯 Recommendations")
                st.write(rec)
                # TTS for recommendations
                audio_path = text_to_speech_savefile(rec)
                if audio_path:
                    st.audio(audio_path, format="audio/mp3")
            else:
                st.info("Item not added to cart.")

            if inquiry and inquiry.lower() != "no":
                ans = get_product_answer(product["name"], inquiry)
                st.write("### ❓ Answer")
                st.write(ans)
                audio_path = text_to_speech_savefile(ans)
                if audio_path:
                    st.audio(audio_path, format="audio/mp3")

    else:
        st.error("Invalid RFID.")

# -----------------------------
#   CART SECTION
# -----------------------------
st.subheader("🛍 Your Cart")

if st.session_state.cart:
    for i, item in enumerate(st.session_state.cart):
        st.write(f"{i+1}. **{item['name']}** — ₹{item['discounted_rate']}")

    remove_index = st.number_input("Remove item index", min_value=1, max_value=len(st.session_state.cart), key="remove_index")

    if st.button("Remove from Cart"):
        try:
            removed = st.session_state.cart.pop(remove_index-1)
            st.success(f"Removed {removed['name']}")
        except Exception:
            st.error("Invalid index.")

    # Payment Flow (always allow checkout; save history if phone provided or logged in)
    st.markdown("---")
    st.write("### Checkout")

    if st.session_state.logged_in:
        st.info(f"Purchases will be saved to account: {st.session_state.phone}")

    # If user not logged in, allow entering phone at checkout to save history across sessions
    if not st.session_state.logged_in:
        st.write("Not logged in? Enter a phone number below to save this purchase to that phone (optional).")
        st.session_state.checkout_phone = st.text_input("Phone for saving purchase (optional)", key="checkout_phone_input", value=st.session_state.checkout_phone)

    # Always allow payment (demo)
    if st.button("Proceed to Payment"):
        # simple demo payment accepted
        # Save to DB if we have a phone (either logged-in or provided at checkout)
        saving_phone = None
        if st.session_state.logged_in:
            saving_phone = st.session_state.phone
        elif st.session_state.checkout_phone and st.session_state.checkout_phone.strip():
            saving_phone = st.session_state.checkout_phone.strip()

        if saving_phone:
            for item in st.session_state.cart:
                add_purchase_history(saving_phone, item["name"])
            st.success("Payment successful! Purchases saved to purchase history.")
            st.write(generate_final_bill(st.session_state.cart))
            # play a brief TTS confirmation
            confirmation_text = f"Payment successful. You purchased {len(st.session_state.cart)} items. Thank you!"
            audio_path = text_to_speech_savefile(confirmation_text)
            if audio_path:
                st.audio(audio_path, format="audio/mp3")
            # clear cart
            st.session_state.cart = []
        else:
            # guest checkout without saving history
            st.success("Payment successful (guest checkout). Purchases were not saved to any account.")
            st.write(generate_final_bill(st.session_state.cart))
            confirmation_text = f"Payment successful. You purchased {len(st.session_state.cart)} items. Thank you!"
            audio_path = text_to_speech_savefile(confirmation_text)
            if audio_path:
                st.audio(audio_path, format="audio/mp3")
            st.session_state.cart = []

else:
    st.info("Cart is empty.")
