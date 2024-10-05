# app.py

import streamlit as st
from autogen import ConversableAgent, initiate_chats
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import json

st.title("Healthbite Meal Plan Generator")

# Set up the OpenAI API key from Streamlit secrets
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

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
    code_execution_config=False,  # Disable code execution
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
        "- **Provide nutritional data** for each meal in a JSON format with the following keys: Date, Meal (breakfast/lunch/dinner), Fat%, Calorie Intake, and Sugar. Enclose this data within <json></json> tags.\n"
        "- **Do not attempt to execute code or generate plots**; instead, provide the data we can use to generate these ourselves.\n\n"
        "**Customization Guidelines:**\n\n"
        "- Tailor the meal plan based on the customer's chronic disease.\n"
        "- Incorporate the customer's preferred cuisine styles.\n"
        "- Exclude any ingredients the customer wishes to avoid.\n\n"
        "**Additional Instructions:**\n\n"
        "- Make your responses engaging, fun, and enjoyable to read.\n"
        "- Conclude by returning 'TERMINATE' when you have provided all the information."
    ),
    llm_config={"config_list": config_list},
    code_execution_config=False,  # Disable code execution
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
if "meal_plan" not in st.session_state:
    st.session_state["meal_plan"] = ""
if "data_frame" not in st.session_state:
    st.session_state["data_frame"] = pd.DataFrame()

# Collect customer information
st.header("Patient Onboarding")
if "customer_info_completed" not in st.session_state:
    st.session_state["customer_info_completed"] = False

if not st.session_state["customer_info_completed"]:
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
        if not name or not zip_code:
            st.error("Please provide both your name and zip code.")
        else:
            st.session_state["customer_info"] = {
                "name": name.strip(),
                "zip_code": zip_code.strip(),
                "disease": disease,
                "cuisine": cuisine,
                "avoid_ingredients": [
                    ingredient.strip() for ingredient in avoid_ingredients.split(",") if ingredient.strip()
                ],
            }
            st.session_state["customer_info_completed"] = True
            st.success("Thank you! Your information has been recorded.")
else:
    st.write(f"Welcome, **{st.session_state['customer_info']['name']}**!")

# Proceed to meal plan generation if customer info is completed
if st.session_state.get("customer_info_completed"):
    if "meal_plan_generated" not in st.session_state:
        st.session_state["meal_plan_generated"] = False

    if not st.session_state["meal_plan_generated"]:
        if st.button("Generate Meal Plan"):
            st.header("Generating Your Personalized Meal Plan...")
            with st.spinner("Please wait while we generate your meal plan..."):

                # Prepare customer message
                customer_info = st.session_state["customer_info"]
                customer_message = (
                    f"My name is {customer_info['name']}. "
                    f"I have {customer_info['disease']} and prefer {', '.join(customer_info['cuisine'])} cuisine. "
                )
                if customer_info['avoid_ingredients']:
                    customer_message += f"I wish to avoid {', '.join(customer_info['avoid_ingredients'])}."

                # Simulate the conversation
                chats = [
                    {
                        "sender": onboarding_agent,
                        "recipient": customer_proxy_agent,
                        "message": "Hello! I'm here to help you get started with Healthbite.",
                        "max_turns": 2,
                        "clear_history": True,
                    },
                    {
                        "sender": customer_proxy_agent,
                        "recipient": engagement_agent,
                        "message": customer_message,
                        "max_turns": 1,
                        "summary_method": "reflection_with_llm",
                    },
                ]

                chat_results = initiate_chats(chats)

                # Extract the meal plan from the engagement agent's response
                conversation_key = f"{customer_proxy_agent.name}_{engagement_agent.name}"
                meal_plan_response = chat_results.get(conversation_key, {}).get("messages", [])

                if meal_plan_response:
                    # Get the last message from the engagement agent
                    meal_plan_content = meal_plan_response[-1]["content"]
                    st.session_state["meal_plan"] = meal_plan_content

                    # Parse JSON data
                    json_match = re.search(r"<json>(.*?)</json>", meal_plan_content, re.DOTALL)
                    if json_match:
                        json_data = json_match.group(1).strip()
                        try:
                            data_list = json.loads(json_data)
                            df = pd.DataFrame(data_list)
                            st.session_state["data_frame"] = df
                        except json.JSONDecodeError:
                            st.error("Failed to parse JSON data from the assistant's response.")
                    else:
                        st.warning("No nutritional data found in the assistant's response.")

                    st.session_state["meal_plan_generated"] = True

                else:
                    st.session_state["meal_plan"] = "No meal plan generated."
                    st.session_state["meal_plan_generated"] = True

            st.success("Your meal plan is ready!")

    # Display the meal plan if generated
    if st.session_state.get("meal_plan_generated") and st.session_state.get("meal_plan"):
        st.header("Your Personalized Meal Plan")
        st.markdown(st.session_state["meal_plan"])

        # Display data frame if available
        if not st.session_state["data_frame"].empty:
            st.subheader("Nutritional Information Data Frame")
            st.dataframe(st.session_state["data_frame"])

            # Generate plot
            st.subheader("Nutritional Information Plot")
            fig, ax = plt.subplots()
            sns.barplot(data=st.session_state["data_frame"], x="Meal", y="Calorie Intake", ax=ax)
            st.pyplot(fig)

# Footer
st.write("---")
st.write("Developed with ❤️ using OpenAI, Autogen, and Streamlit")
