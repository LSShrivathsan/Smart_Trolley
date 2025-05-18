import gradio as gr
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

product_data = {
    "RFID001": {
        "name": "Organic Apples",
        "quantity": 20,
        "mrp": 200,
        "discounted_rate": 180
    },
    "RFID002": {
        "name": "Whole Wheat Bread",
        "quantity": 50,
        "mrp": 40,
        "discounted_rate": 35
    },
    "RFID003": {
        "name": "Almond Milk",
        "quantity": 30,
        "mrp": 120,
        "discounted_rate": 100
    },
    "RFID004": {
        "name": "Olive Oil - 500ml",
        "quantity": 15,
        "mrp": 450,
        "discounted_rate": 400
    },
    "RFID005": {
        "name": "Basmati Rice - 1kg",
        "quantity": 25,
        "mrp": 150,
        "discounted_rate": 130
    }
}

cart = []

def get_product_details(rfid):
    """Fetch product details based on RFID."""
    return product_data.get(rfid, None)

def add_to_cart(product):
    """Add product to cart."""
    cart.append(product)

def remove_from_cart(index):
    """Remove a product from the cart by index."""
    try:
        removed_item = cart.pop(index)
        return f"Removed '{removed_item['name']}' from the cart."
    except IndexError:
        return f"Invalid index. Please enter a valid index."

def get_recommendations(product_name):
    """Generate product recommendations using GPT-4."""
    prompt = f"Suggest complementary and similar products for {product_name}."
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

def get_product_answer(product_name, inquiry):
    """Generate an answer to the product inquiry using GPT-4."""
    prompt = f"The user has a question about {product_name}: {inquiry}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

def generate_final_bill():
    """Generate the final bill in a tabular format."""
    bill_details = []
    total_amount = 0

    for index, item in enumerate(cart):
        amount = item['discounted_rate']
        total_amount += amount
        bill_details.append({
            "Index": index,
            "Product Name": item['name'],
            "Discounted Rate (₹)": item['discounted_rate'],
            "Amount (₹)": amount
        })

    bill_text = "Here is the final bill:\n\n"
    bill_text += "| Index | Product Name           | Discounted Rate (₹) | Amount (₹) |\n"
    bill_text += "|-------|------------------------|---------------------|------------|\n"
    for item in bill_details:
        bill_text += f"| {item['Index']:<5} | {item['Product Name']:<22} | {item['Discounted Rate (₹)']:<19} | {item['Amount (₹)']:<10} |\n"
    bill_text += "|-------|------------------------|---------------------|------------|\n"
    bill_text += f"| Total |                        |                     | ₹{total_amount:<10} |\n"

    return bill_text

def chatbot_interaction(rfid, user_input, inquiry, remove_index):
    """Handle chatbot interaction with the user."""
    response = ""

    # Remove from cart
    if remove_index is not None:
        try:
            remove_index = int(remove_index)
            response = remove_from_cart(remove_index)
        except ValueError:
            response = "-"

    product_details = ""
    final_bill = ""

    if rfid:
        product = get_product_details(rfid)
        if not product:
            return f"No product found for RFID {rfid}.", "", response

        product_details = (
            f"**Product:** {product['name']}\n"
            f"**Quantity Available:** {product['quantity']}\n"
            f"**MRP:** ₹{product['mrp']}\n"
            f"**Discounted Rate:** ₹{product['discounted_rate']}\n"
        )

        if user_input == "yes":
            add_to_cart(product)
            response += f"Added '{product['name']}' to your cart.\n"

            recommendations = get_recommendations(product['name'])
            response += f"**You may also like:** {recommendations}\n"
        elif user_input == "no":
            response += f"'{product['name']}' was not added to the cart."
        else:
            response += f"You can ask more about '{product['name']}' or decide to add it to the cart."

        if inquiry and inquiry.lower() != "no":
            try:
                answer = get_product_answer(product['name'], inquiry)
                response += f"\n**Answer:** {answer}\n"
            except Exception as e:
                response += f"Error with GPT-4 API call: {e}"

    final_bill = generate_final_bill() if cart else "Your cart is empty."
    return product_details, response, final_bill

def gradio_interface(rfid, user_input, inquiry, remove_index):
    product_details, interaction_response, final_bill_output = chatbot_interaction(rfid, user_input, inquiry, remove_index)
    return product_details, interaction_response, final_bill_output

iface = gr.Interface(
    fn=gradio_interface,
    inputs=[
        gr.Textbox(label="RFID Input"),
        gr.Radio(["yes", "no"], label="Add to Cart"),
        gr.Textbox(label="Any Questions about the Product? (type 'no' to skip)"),
        gr.Textbox(label="Enter Index to Remove from Cart (leave blank if not removing)"),
    ],
    outputs=[
        gr.Textbox(label="Product Details"),
        gr.Textbox(label="Interaction Response"),
        gr.Textbox(label="Final Bill"),
    ],
    title="SMART TROLLEY",
    description="Enter RFID codes to add items to the cart, inquire about products, remove items from the cart, and get recommendations.",
)

iface.launch(demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 8000))))
