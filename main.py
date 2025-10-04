import asyncio
import uuid
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from software_agent.agent import root_agent
from utils import call_agent_async

load_dotenv()

# ===== PART 1: Initialize Persistent Session Service =====
session_service = InMemorySessionService()

# ===== PART 2: Define Initial State =====
# This will only be used when creating a new session
initial_state = {
    "username": "jgerard12",
    "computername": None,
    "software_name": None,    
}

async def main_async():
    # Setup constants
    APP_NAME = "Software Agent"
    USER_ID = "jgerard12"
    SESSION_ID = str(uuid.uuid4())

    # Create a new session with initial state
    new_session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state=initial_state,
    )
    SESSION_ID = new_session.id
    print(f"Created new session: {SESSION_ID}")

    # ===== PART 4: Agent Runner Setup =====
    # Create a runner with the memory agent
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # ===== PART 5: Interactive Conversation Loop =====
    print("\nWelcome to Software Deployment Agent Chat!")    
    print("Type 'exit' or 'quit' to end the conversation.\n")

    while True:
        # Get user input
        user_input = input("You: ")

        # Check if user wants to exit
        if user_input.lower() in ["exit", "quit"]:
            print("Ending conversation. Your data has been saved to the database.")
            break

        # Process the user query through the agent
        await call_agent_async(runner, USER_ID, SESSION_ID, user_input)


if __name__ == "__main__":
    asyncio.run(main_async())