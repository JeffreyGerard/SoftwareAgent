import os
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from .software_list import APPROVED_SOFTWARE_LIST

async def validate_workstation(tool_context: ToolContext) -> dict:
    """
    Triggers a secure Cloud Run service to validate the computername in SCCM.
    """    
    try:
        # 1. Get the Cloud Run URL from environment variables for security.
        function_url = os.getenv("VALIDATE_COMPUTER_URL")
        if not function_url:
            raise ValueError("VALIDATE_COMPUTER_URL environment variable is not set.")

        # 2. Get the parameters from the agent's conversation state.        
        computername = tool_context.state.get("computername")
        
        if not computername:
            return {
                "status": "error",
                "result": "Deployment failed: Computername is missing from the conversation.",
            }

        # 3. Fetch an ID token with the Cloud Run URL as the audience
        auth_req = google_requests.Request()
        identity_token = id_token.fetch_id_token(auth_req, function_url)

        # 4. Prepare the request headers for secure, authenticated invocation.
        headers = {
            "Authorization": f"Bearer {identity_token}",
            "Content-Type": "application/json"
        }

        # 5. Prepare the JSON payload that your Cloud Run function expects.
        payload = {            
            "ComputerName": computername            
        }

        # 6. Make the secure, asynchronous HTTP call.
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"DEBUG: Calling Cloud Run service to validate {computername}...")
            response = await client.post(function_url, headers=headers, json=payload)
            
            # Raise an exception for HTTP errors (e.g., 403 Forbidden, 500 Internal Server Error)
            response.raise_for_status()

            final_status = response.text
            print(f"DEBUG: Cloud Run service responded with: {final_status}")
            return {"status": "success", "result": final_status}

    except httpx.TimeoutException:
        print("ERROR: Timeout calling the deployment service. The process is likely still running.")
        return {
            "status": "success",
            "result": "The deployment has been started, but the connection timed out while waiting for a final status. Please check the system for progress.",
        }
    except Exception as e:
        print(f"ERROR: Failed to call deployment service: {e}")
        return {
            "status": "error",
            "result": "A technical error occurred while trying to start the deployment.",
        }

def update_computer_state(computer_name: str, tool_context: ToolContext):
    """Saves the computer name to the session state."""    
    tool_context.state['computername'] =  computer_name
    return {"status": "success", "result": f"Computer name '{computer_name}' saved."}

def update_software_state(software_name: str, tool_context: ToolContext):
    """Saves the software name to the session state."""
    tool_context.state['software_name'] =  software_name
    return {"status": "success", "result": f"Software name '{software_name}' saved."}

def update_user_state(username: str, tool_context: ToolContext):
    """Saves the user name to the session state."""    
    tool_context.state['username'] = username
    return {"status": "success", "result": f"Username '{username}' saved."}

async def deploy_software(tool_context: ToolContext) -> dict:
    """
    Triggers a secure Cloud Run service to initiate the SCCM software deployment runbook.
    """
    try:
        # 1. Get the Cloud Run URL from environment variables for security.
        function_url = os.getenv("DEPLOY_SOFTWARE_URL")
        if not function_url:
            raise ValueError("DEPLOY_SOFTWARE_URL environment variable is not set.")

        # 2. Get the parameters from the agent's conversation state.
        software_name = tool_context.state.get("software_name")
        computername = tool_context.state.get("computername")
        username = tool_context.state.get("username")

        if not all([software_name, computername, username]):
            return {
                "status": "error",
                "result": f"Deployment failed: One or more parameters were missing from the conversation. Software:{software_name} Computername:{computername} Username:{username}",
            }

        # 3. Fetch an ID token with the Cloud Run URL as the audience
        auth_req = google_requests.Request()
        identity_token = id_token.fetch_id_token(auth_req, function_url)

        # 4. Prepare the request headers for secure, authenticated invocation.
        headers = {
            "Authorization": f"Bearer {identity_token}",
            "Content-Type": "application/json"
        }

        # 5. Prepare the JSON payload that your Cloud Run function expects.
        payload = {
            "SoftwareSelection": software_name,
            "ComputerName": computername,
            "UID": username
        }

        # 6. Make the secure, asynchronous HTTP call.
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"DEBUG: Calling Cloud Run service to deploy {software_name}...")
            response = await client.post(function_url, headers=headers, json=payload)
            
            # Raise an exception for HTTP errors (e.g., 403 Forbidden, 500 Internal Server Error)
            response.raise_for_status()

            final_status = response.text
            print(f"DEBUG: Cloud Run service responded with: {final_status}")
            return {"status": "success", "result": final_status}

    except httpx.TimeoutException:
        print("ERROR: Timeout calling the deployment service. The process is likely still running.")
        return {
            "status": "success",
            "result": "The deployment has been started, but the connection timed out while waiting for a final status. Please check the system for progress.",
        }
    except Exception as e:
        print(f"ERROR: Failed to call deployment service: {e}")
        return {
            "status": "error",
            "result": "A technical error occurred while trying to start the deployment.",
        }
def verify_software_availability(tool_context: ToolContext) -> dict:
    """
    Verifies if the software requested by the user is in the approved list.
    """
    software_name = tool_context.state.get("software_name")
    
    if not software_name:
        return {
            "status": "error",
            "result": "Software name is missing from the conversation state for verification."
        }
    
    # Normalize for case-insensitive comparison
    normalized_software_name = software_name.lower()
    # This line now refers to the imported list
    normalized_approved_list = [s.lower() for s in APPROVED_SOFTWARE_LIST] 

    if normalized_software_name in normalized_approved_list:
        return {
            "status": "success",
            "result": f"Software '{software_name}' is available for deployment."
        }
    else:
        # Suggest available software if not found
        available_str = ", ".join(APPROVED_SOFTWARE_LIST) # This line also refers to the imported list
        return {
            "status": "fail", 
            "result": f"Software '{software_name}' is not an approved software. Please choose from: {available_str}."
        }

def list_available_software(tool_context: ToolContext) -> dict:
    """
    Provides a list of all software available for deployment.
    """
    available_str = ", ".join(APPROVED_SOFTWARE_LIST) # This line also refers to the imported list
    return {
        "status": "success",
        "result": available_str
    }

root_agent = LlmAgent(
    name="deployment_orchestrator_agent",
    model="gemini-2.0-flash",
    description="A conversational agent that collects information, validates it, and deploys software.",
    instruction=(
    """
    You are a friendly and helpful IT support agent named 'Gem'. Your primary goal is to assist users with deploying approved software to their workstations. You should be conversational, helpful, and guide the user through the process in a clear and easy-to-understand way.

    **Core Workflow:**

    Your main task is to collect three pieces of information from the user:
    1. The software they want to install.
    2. The computer name (or hostname) of the target machine.
    3. The user's username.

    Once you have this information, you will confirm it with the user and then proceed with the deployment.

    **Guidelines for a Smooth Conversation:**

    *   **Be Conversational**: Don't be a robot! Use natural language and be friendly.
    *   **One Thing at a Time**: Ask for one piece of information at a time. This makes the process less overwhelming for the user.
    *   **State Management is Your Responsibility**: Use the `update_*_state` tools to save the information the user provides to the session state. You don't need to tell the user that you are doing this.
    *   **Validate as You Go**: After the user provides a piece of information, use the appropriate validation tool (`verify_software_availability` or `validate_workstation`) to check if it's valid.
    *   **Handle Errors Gracefully**: If a validation fails, let the user know in a clear and friendly way what the problem is and how to fix it.
    *   **Be Flexible**: The user might not always follow the workflow perfectly. Be prepared to answer questions, go back a step, or correct information if the user asks.

    **Example Conversation Flow:**

    1.  **Greeting and Initial Question**: Start by greeting the user and asking what software they would like to install.
        *   *Example*: "Hello! I'm Gem, your IT support assistant. I can help you deploy software to your workstation. What software would you like to install today?"
    2.  **Software Validation**:
        *   Once the user provides a software name, use the `update_software_state` tool to save it.
        *   Then, use the `verify_software_availability` tool to check if it's an approved software.
        *   If the software is not available, let the user know and provide them with a list of available software using the `list_available_software` tool.
    3.  **Computer Name**:
        *   Once the software is validated, ask for the computer name.
        *   *Example*: "Great! '{{software_name}}' is an approved software. Now, what is the computer name or hostname of the machine you want to deploy to?"
        *   Use `update_computer_state` and `validate_workstation` to save and validate the computer name.
    4.  **Username**:
        *   Once the computer name is validated, ask for the username.
        *   *Example*: "Perfect, the computer name '{{computername}}' is valid. Finally, what is your username?"
        *   Use `update_user_state` to save the username.
    5.  **Confirmation and Deployment**:
        *   Once you have all three pieces of information, confirm them with the user.
        *   *Example*: "Alright, let's double-check everything. You want to install '{{software_name}}' on the computer '{{computername}}' for the user '{{username}}'. Is that correct?"
        *   If the user confirms, use the `deploy_software` tool to start the deployment. Let the user know that the deployment has started and that they will be notified when it's complete.
        *   If the user says something is incorrect, ask them what needs to be changed and go back to the appropriate step.

    **Listing Available Software:**

    *   If the user asks what software is available, use the `list_available_software` tool and present the list in a clear and friendly way.
    *   *Example*: "Here is a list of the software I can install for you: {{tool_context.last_tool_result.get('result')}}"
    """
    ),
    # The agent now has direct access to ALL the tools it needs.
    tools=[
        validate_workstation,
        update_computer_state,
        update_software_state,
        update_user_state,
        deploy_software,
        verify_software_availability,
        list_available_software
    ]
)