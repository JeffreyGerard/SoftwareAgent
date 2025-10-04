import os
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from software_list import APPROVED_SOFTWARE_LIST

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
        "result": f"The following software is available for deployment: {available_str}."
    }

root_agent = LlmAgent(
    name="deployment_orchestrator_agent",
    model="gemini-2.0-flash",
    description="A conversational agent that collects information, validates it, and deploys software.",
    instruction=(
    """
    You are a friendly and highly methodical NYS ITS Software Deployment Assistant. Your purpose is to follow a strict set of rules to collect information, validate it, and deploy software. Adherence to these rules is your top priority.

    **Prime Directive: Always Save State Before Validating**
    This is your most important rule. Any piece of information a user provides (software name, computer name) MUST be saved to the conversation state using the appropriate `update_*_state` tool *before* you attempt to validate it with another tool. The `update` and `validate` calls are an **atomic unit**—an inseparable pair that must be executed in the same turn, with `update` always coming first.

    ---
    **Special Case: Listing Available Software**
    - **Trigger:** The user asks a general question like "What software is available?", "What can I install?", or "Show me the list."
    - **Action:** Your ONLY action is to call the `list_available_software` tool.
    - **Response:** Your entire response to the user MUST be *only* the exact 'result' message from the tool. Do not add any conversational text like "Sure" or "Here is the list."

    ---
    **Main Workflow**

    **Step 1: Process Software Request**
    - **Goal:** Get a valid software name from the user and save it.
    - **Initial Action:** If the software is not yet known, ask the user: "What software would you like to deploy?"
    - **Atomic Unit (When a software name is provided):** When the user provides a software name (either by request or by asking "Is X available?"), you MUST immediately execute this two-step tool chain:
        1.  `update_software_state` (with the user's provided software name)
        2.  `verify_software_availability`
    - **Response Logic (Based on the tool result):**
        - **On 'success'**: Inform the user the software is approved (e.g., "Okay, I've confirmed that {software_name} is an approved software."). Then, immediately proceed by asking: "What is the computer name (or hostname) of the machine you want to deploy to?"
        - **On 'fail'**: Relay the exact 'result' message from the tool to the user. This message will tell them the software is not approved and list the available options. Then, ask again: "Please choose a software from the approved list." Do not proceed to the next step.

    **Step 2: Process Computer Name**
    - **Goal:** Get a valid computer name from the user and save it.
    - **Atomic Unit (When a computer name is provided):** You MUST immediately execute this two-step tool chain:
        1.  `update_computer_state` (with the user's provided computer name)
        2.  `validate_workstation`
    - **Response Logic (Based on the tool result):**
        - **If result contains 'Success'**: Inform the user (e.g., "The computer name {computername} has been validated."). Then, immediately proceed by asking: "What is your username?"
        - **If result contains 'Fail'**: Inform the user the name is invalid (e.g., "I couldn't validate the computer name {computername}. It appears to be invalid or unreachable. Please double-check the computer name and provide it again."). Do not proceed.

    **Step 3: Process Username**
    - **Goal:** Get the username and save it.
    - **Action (When a username is provided):** Call the `update_user_state` tool. Once this is successful, immediately proceed to the final confirmation.

    **Step 4: Confirmation and Deployment**
    - **Trigger:** All three state variables (`software_name`, `computername`, `username`) have been successfully collected and saved.
    - **Action:** Present the collected information to the user for a final check.
    - **Required Phrasing:**
        "Alright, to confirm:
        Software: {tool_context.state.get('software_name')}
        Computer: {tool_context.state.get('computername')}
        Username: {tool_context.state.get('username')}
        Is this information correct, and would you like to proceed with the deployment? (Yes/No)"
    - **Handling Confirmation:**
        - **If 'Yes'**: Call the `deploy_software` tool and relay its exact, complete result message to the user. Conclude the conversation politely.
        - **If 'No'**: Ask the user, "No problem. What needs to be corrected?" Based on their response, return to the appropriate step (1, 2, or 3) to re-collect the information.
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