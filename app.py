# app.py

import streamlit as st
from autogen import ConversableAgent
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
    is_termination_msg=lambda msg: "terminate" in msg.get("content").lower(),
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

# Create a sender object for the user
class Sender:
    def __init__(self, name):
        self.name = name

    # Ensure the object is hashable
    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Sender) and self.name == other.name

user_sender = Sender("user")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "last_agent" not in st.session_state:
    st.session_state["last_agent"] = "onboarding_agent"

# Chat Interface
st.header("Chat with Healthbite Assistant")

# Display conversation history
for msg in st.session_state["messages"]:
    if msg["sender"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**{msg['sender']}:** {msg['content']}")

# User input
user_input = st.text_input("Type your message:", key="user_input")

if st.button("Send"):
    if user_input:
        # Add user message to conversation
        st.session_state["messages"].append({"sender": "user", "content": user_input})

        # Determine which agent to interact with
        last_agent = st.session_state.get("last_agent", "onboarding_agent")

        if last_agent == "onboarding_agent":
            # Interact with onboarding_agent
            onboarding_agent.receive(
                sender=user_sender,
                message={"role": "user", "content": user_input}
            )

            # Get the agent's response
            response = onboarding_agent.message_history.get_new_messages()[-1]
            st.session_state["messages"].append({
                "sender": "Healthbite Assistant",
                "content": response["content"]
            })

            # Check for termination
            if onboarding_agent.is_terminated():
                st.session_state["last_agent"] = "engagement_agent"
                st.success("Onboarding complete! Proceeding to meal plan generation.")
            else:
                st.session_state["last_agent"] = "onboarding_agent"

        elif last_agent == "engagement_agent":
            # Interact with engagement_agent
            engagement_agent.receive(
                sender=user_sender,
                message={"role": "user", "content": user_input}
            )

            # Get the agent's response
            response = engagement_agent.message_history.get_new_messages()[-1]
            st.session_state["messages"].append({
                "sender": "Healthbite Assistant",
                "content": response["content"]
            })

            # Check for termination
            if engagement_agent.is_terminated():
                st.session_state["last_agent"] = "finished"
            else:
                st.session_state["last_agent"] = "engagement_agent"

        # Clear user input
        st.session_state["user_input"] = ""
    else:
        st.error("Please enter a message.")

# When conversation is finished
if st.session_state.get("last_agent") == "finished":
    # Extract meal plan from engagement_agent
    messages = engagement_agent.message_history.get_all_messages()
    if messages:
        # Find the last assistant message
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]
        if assistant_messages:
            meal_plan_content = assistant_messages[-1]["content"]
            st.header("Your Personalized Meal Plan")
            st.markdown(meal_plan_content)

            # Parse JSON data
            json_match = re.search(r"<json>(.*?)</json>", meal_plan_content, re.DOTALL)
            if json_match:
                json_data = json_match.group(1).strip()
                try:
                    data_list = json.loads(json_data)
                    df = pd.DataFrame(data_list)
                    st.subheader("Nutritional Information Data Frame")
                    st.dataframe(df)

                    # Generate plot
                    st.subheader("Nutritional Information Plot")
                    fig, ax = plt.subplots()
                    sns.barplot(data=df, x="Meal", y="Calorie Intake", ax=ax)
                    st.pyplot(fig)
                except json.JSONDecodeError:
                    st.error("Failed to parse JSON data from the assistant's response.")
            else:
                st.warning("No nutritional data found in the assistant's response.")
        else:
            st.error("No assistant messages found from the engagement agent.")
    else:
        st.error("No messages found from the engagement agent.")

    # Reset conversation
    if st.button("Start New Conversation"):
        st.session_state["messages"] = []
        onboarding_agent.reset()
        engagement_agent.reset()
        st.session_state["last_agent"] = "onboarding_agent"

# Footer
st.write("---")
st.write("Developed with ❤️ using OpenAI, Autogen, and Streamlit")
