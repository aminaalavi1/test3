# app.py

import streamlit as st
from autogen import ConversableAgent, initiate_chats
import os

st.title("Healthbite Meal Plan Generator")

# Set up the OpenAI API key
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# Configuration for the language model
config_list = [{"model": "gpt-3.5-turbo", "api_key": OPENAI_API_KEY}]

# Define agents
onboarding_agent = ConversableAgent(
    name="onboarding_agent",
    system_message=(
        "You are a helpful patient onboarding agent. "
        "Your job is to gather the patient's name, chronic disease, zip code, and meal cuisine preference. "
        "When they provide this information, ask them about any ingredients they wish to avoid. "
        "Do not ask for other information. Return 'TERMINATE' when you have gathered all the information."
    ),
    llm_config={"config_list": config_list},
    code_execution_config=False,
    human_input_mode="NEVER",
)

engagement_agent = ConversableAgent(
    name="engagement_agent",
    system_message=(
        "You are a friendly and engaging patient service agent. Your task is to provide the customer with a personalized meal plan for the day. "
        "Tailor the meal plan based on the customer's chronic disease. The meal plan should include:\n\n"
        "- **Recipes for each meal**, detailing the exact ingredients needed and their precise amounts and how to cook the meal.\n"
        "- **A separate grocery list** compiling all the ingredients required for the day.\n"
        "- **Serving sizes and calorie counts** for each meal.\n"
        "- **Nutritional information**, specifying the servings of greens, fruits, vegetables, fiber, proteins, etc., in each meal.\n\n"
        "**Additional Tasks:**\n\n"
        "- **Generate a data frame** that has five columns: Date, Meal (like breakfast/lunch/dinner), Fat%, calorie intake, and sugar.\n"
        "- **Create a plot** (e.g., a bar chart) visualizing this nutritional information.\n"
        "- **Include the data frame and the plot** in your response.\n\n"
        "**Customization Guidelines:**\n\n"
        "- Tailor the meal plan based on the customer's chronic disease.\n"
        "- Incorporate the customer's preferred cuisine styles.\n"
        "- Exclude any ingredients the customer wishes to avoid.\n\n"
        "**Additional Instructions:**\n\n"
        "- Make your responses engaging, fun, and enjoyable to read.\n"
        "- Conclude by returning 'TERMINATE' when you have provided all the information."
    ),
    llm_config={"config_list": config_list},
    code_execution_config={
        "allowed_imports": ["pandas", "matplotlib", "seaborn"],
        "execution_timeout": 60,  # in seconds
    },
    human_input_mode="NEVER",
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower(),
)

customer_proxy_agent = ConversableAgent(
    name="customer_proxy_agent",
    llm_config=False,
    code_execution_config=False,
    human_input_mode="ALWAYS",
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower(),
)

# Initialize session state
if "customer_info" not in st.session_state:
    st.session_state["customer_info"] = {}
if "conversation_history" not in st.session_state:
    st.session_state["conversation_history"] = []

# Collect customer information
st.header("Patient Onboarding")
if not st.session_state["customer_info"].get("completed"):
    with st.form(key="onboarding_form"):
        name = st.text_input("Enter your name:")
        zip_code = st.text_input("Enter your zip code:")
        disease = st.selectbox(
            "Select your chronic disease:",
            ["Diabetes", "Hypertension", "Heart Disease", "Other"]
        )
        cuisine = st.multiselect(
            "Select your preferred cuisines:",
            ["Italian", "Mexican", "Chinese", "Indian", "Mediterranean", "Other"]
        )
        avoid_ingredients = st.text_input("List any ingredients you wish to avoid (comma-separated):")
        submit_button = st.form_submit_button(label="Submit")

    if submit_button:
        st.session_state["customer_info"] = {
            "name": name.strip(),
            "zip_code": zip_code.strip(),
            "disease": disease,
            "cuisine": cuisine,
            "avoid_ingredients": [ingredient.strip() for ingredient in avoid_ingredients.split(",") if ingredient.strip()],
            "completed": True,
        }
        st.success("Thank you! Your information has been recorded.")
        st.experimental_rerun()
else:
    st.write(f"Welcome, **{st.session_state['customer_info']['name']}**!")

# Generate meal plan
if st.session_state["customer_info"].get("completed"):
    if st.button("Generate Meal Plan"):
        st.header("Generating Your Personalized Meal Plan...")
        with st.spinner("Please wait while we generate your meal plan..."):

            # Prepare the chat sequence
            chats = [
                {
                    "sender": onboarding_agent,
                    "recipient": customer_proxy_agent,
                    "message": (
                        "Hello! I'm here to help you get started with Healthbite."
                    ),
                    "max_turns": 2,
                    "clear_history": True,
                },
                {
                    "sender": customer_proxy_agent,
                    "recipient": engagement_agent,
                    "message": "Let's get your meal plan ready!",
                    "max_turns": 1,
                    "summary_method": "reflection_with_llm",
                },
            ]

            # Inject customer info into the conversation
            customer_info = st.session_state["customer_info"]
            customer_message = (
                f"My name is {customer_info['name']}. "
                f"I have {customer_info['disease']} and prefer {', '.join(customer_info['cuisine'])} cuisine. "
                f"I wish to avoid {', '.join(customer_info['avoid_ingredients'])}."
            )

            # Simulate the conversation
            customer_proxy_agent.human_input_mode = "NEVER"
            customer_proxy_agent.receive_message({"content": customer_message, "sender": "user"})
            chat_results = initiate_chats(chats)

            # Extract the meal plan from the engagement agent's response
            meal_plan_response = chat_results.get("customer_proxy_agent_engagement_agent", {}).get("messages", [])
            if meal_plan_response:
                # Get the last message from the engagement agent
                meal_plan_content = meal_plan_response[-1]["content"]
                st.session_state["meal_plan"] = meal_plan_content
            else:
                st.session_state["meal_plan"] = "No meal plan generated."

        st.success("Your meal plan is ready!")
        st.experimental_rerun()

# Display the meal plan
if st.session_state.get("meal_plan"):
    st.header("Your Personalized Meal Plan")
    st.markdown(st.session_state["meal_plan"])
