# app.py

import streamlit as st
import asyncio
from autogen import AssistantAgent, UserProxyAgent
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re
import json

# Set up the OpenAI API key from Streamlit secrets
st.set_page_config(page_title="Healthbite Meal Plan Generator", page_icon="🥗", layout="wide")
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

st.title("Healthbite Meal Plan Generator")

st.markdown(
    """
    This is a demo of AutoGen chat agents. You can chat with the Healthbite Assistant to get a personalized meal plan.
    """
)

# Define a custom AssistantAgent that tracks messages
class TrackableAssistantAgent(AssistantAgent):
    def _process_received_message(self, message, sender, silent):
        # Display the assistant's messages in Streamlit chat
        with st.chat_message("Healthbite Assistant"):
            st.markdown(message)
        return super()._process_received_message(message, sender, silent)

# Define a custom UserProxyAgent that tracks messages
class TrackableUserProxyAgent(UserProxyAgent):
    def _process_received_message(self, message, sender, silent):
        # Display the user's messages in Streamlit chat
        with st.chat_message("You"):
            st.markdown(message)
        return super()._process_received_message(message, sender, silent)

# Set up the assistant's system message
assistant_system_message = (
    "You are a helpful patient onboarding and meal plan assistant. "
    "Your job is to gather the patient's name, chronic disease, zip code, and meal cuisine preference. "
    "When they provide this information, ask them about any ingredients they wish to avoid. "
    "Once you have gathered all the information, provide a personalized meal plan for the day. "
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
)

# Set up OpenAI LLM configuration
llm_config = {
    "request_timeout": 600,
    "config_list": [
        {"model": "gpt-3.5-turbo", "api_key": OPENAI_API_KEY},
    ],
    "temperature": 0,  # temperature of 0 means deterministic output
}

# Create the assistant agent
assistant = TrackableAssistantAgent(
    name="Healthbite Assistant",
    system_message=assistant_system_message,
    llm_config=llm_config,
    code_execution_config=False,
    is_termination_msg=lambda x: "terminate" in x.get("content", "").lower(),
    human_input_mode="NEVER",
)

# Create the user proxy agent
user_proxy = TrackableUserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    llm_config=llm_config,
    is_termination_msg=lambda x: "terminate" in x.get("content", "").lower(),
)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_initiated" not in st.session_state:
    st.session_state.chat_initiated = False
if "conversation_finished" not in st.session_state:
    st.session_state.conversation_finished = False

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["sender"]):
        st.markdown(message["content"])

# User input
if not st.session_state.conversation_finished:
    user_input = st.text_input("Type your message:", key="user_input")
    if st.button("Send"):
        if not user_input:
            st.warning("Please enter a message")
            st.stop()

        # Add user message to chat history
        st.session_state.chat_history.append({"sender": "You", "content": user_input})

        # Start or continue the conversation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def chat():
            if not st.session_state.chat_initiated:
                await user_proxy.a_initiate_chat(
                    assistant,
                    message=user_input,
                    max_consecutive_auto_reply=5,
                    is_termination_msg=lambda x: "terminate" in x.get("content", "").lower(),
                )
                st.session_state.chat_initiated = True
            else:
                await user_proxy.a_receive(
                    sender=assistant,
                    message={"role": "assistant", "content": user_input},
                    is_termination_msg=lambda x: "terminate" in x.get("content", "").lower(),
                )

        loop.run_until_complete(chat())
        loop.close()

        # Display assistant's response
        assistant_response = assistant.message_history.get_new_messages()[-1]
        st.session_state.chat_history.append({"sender": "Healthbite Assistant", "content": assistant_response["content"]})

        # Check if conversation is terminated
        if assistant.is_terminated():
            st.session_state.conversation_finished = True

        # Clear user input
        st.session_state["user_input"] = ""

        # Rerun the app to display updated chat history
        st.experimental_rerun()

# When conversation is finished
if st.session_state.conversation_finished:
    st.header("Your Personalized Meal Plan")

    # Display the final assistant messages
    for message in st.session_state.chat_history:
        if message["sender"] == "Healthbite Assistant":
            with st.chat_message("Healthbite Assistant"):
                st.markdown(message["content"])

    # Extract meal plan from assistant's messages
    final_messages = [msg for msg in assistant.message_history.get_all_messages() if msg["role"] == "assistant"]
    if final_messages:
        meal_plan_content = final_messages[-1]["content"]

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
        st.error("No messages found from the assistant.")

    # Reset the conversation
    if st.button("Start New Conversation"):
        st.session_state.chat_history = []
        st.session_state.chat_initiated = False
        st.session_state.conversation_finished = False
        assistant.reset()
        user_proxy.reset()
        st.experimental_rerun()

# Footer
st.write("---")
st.write("Developed with ❤️ using OpenAI, Autogen, and Streamlit")
