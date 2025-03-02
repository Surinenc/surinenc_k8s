import os
import json
import time
import random
import threading
import concurrent.futures
from tqdm import tqdm
from faker import Faker
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage
import langgraph
from langgraph.graph import StateGraph
from typing import List

# 🔹 Load environment variables
load_dotenv()

# 🔥 Parallelism Configuration
MAX_PARALLEL_ALERTS = 1 
TIMEOUT_SECONDS = 30  

# 📌 Print Execution Configuration
print(f"\n🚀 Execution Configuration: {MAX_PARALLEL_ALERTS} alerts in parallel, Timeout: {TIMEOUT_SECONDS}s\n")

# 📌 Debug Logging Function
def debug_log(message, color="\033[97m"):
    thread_id = threading.get_ident()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Thread-{thread_id}] {color}{message}\033[0m [{timestamp}]")

# 📌 Simulated Alerts Generator
fake = Faker()
def generate_mock_alerts(n=100):
    alert_types = ["CPU High", "Memory Leak", "Disk Full", "Network Latency", "Service Down"]
    severities = ["Critical", "High", "Medium", "Low"]
    
    return [
        {"id": fake.uuid4(), "type": random.choice(alert_types), "severity": random.choice(severities), "timestamp": fake.date_time_this_year().isoformat()}
        for _ in range(n)
    ]

# 📌 Simulated API with Timeout
def mock_api_response(endpoint, alert):
    delay = random.uniform(3, 40)
    debug_log(f"⌛ Calling {endpoint} with delay {delay:.2f}s for alert: {alert['type']}")
    
    if delay > TIMEOUT_SECONDS:
        debug_log(f"⚠️ Timeout on {endpoint}, assuming no response.")
        return None  
    
    time.sleep(delay)
    
    mock_responses = {
        "logicmonitor": {"status": "down" if random.random() > 0.2 else "ok"},
        "servicenow_incidents": {"similar_case": f"Resolved: {alert['type']} issue on {fake.date()}" if random.random() > 0.5 else None},
        "confluence_kb": {"suggestion": f"Check {alert['type']} troubleshooting guide" if random.random() > 0.5 else None},
        "runbook": {"solution": f"Run script to fix {alert['type']}" if random.random() > 0.8 else None},
        "automation": {"success": random.random() > 0.2},
        "servicenow_tickets": {"ticket_id": fake.uuid4()}
    }
    
    return mock_responses.get(endpoint, {})

# 📌 Incident State
class IncidentState:
    def __init__(self, alert=None):
        self.alert = alert
        self.root_cause = None
        self.history_match = None
        self.kb_suggestion = None
        self.runbook_solution: List[str] = []
        self.human_provided_solution: List[str] = []
        self.remediation_success = None
        self.ticket_id = None
        self.start_time = time.time()

# 📌 Agents
def monitoring_agent(state):
    debug_log(f"\033[94m🔵\033[0m Running monitoring_agent for alert: {state.alert['type']}")
    state.alert['status'] = mock_api_response("logicmonitor", state.alert)
    return state

def incident_history_agent(state):
    debug_log(f"\033[38;5;214m🟠\033[0m Running incident_history_agent for alert: {state.alert['type']}")
    state.history_match = mock_api_response("servicenow_incidents", state.alert)
    return state

def knowledge_base_agent(state):
    debug_log(f"\033[92m🟢\033[0m Running knowledge_base_agent for alert: {state.alert['type']}")
    state.kb_suggestion = mock_api_response("confluence_kb", state.alert)
    return state

def runbook_agent(state):
    debug_log(f"\033[95m🟣\033[0m Running runbook_agent for alert: {state.alert['type']}")
    solution = mock_api_response("runbook", state.alert)
    if solution:
        state.runbook_solution.append(solution)
    return state

# 📌 Mocked `diagnosis_agent`
def diagnosis_agent(state):
    debug_log(f"\033[91m🔴\033[0m Running diagnosis_agent for alert: {state.alert['type']}")
    
    # 🔥 Fixed Root Cause Analysis
    state.root_cause = "Root Cause: The issue is caused by a misconfiguration in the system settings. Recommended action: Apply the latest configuration update."
    
    return state

def ticketing_agent(state):
    debug_log(f"\033[97m⚪\033[0m Running ticketing_agent for alert: {state.alert['type']}")
    state.ticket_id = mock_api_response("servicenow_tickets", state.alert)["ticket_id"]
    return state

def remediation_agent(state):
    debug_log(f"\033[93m🟡\033[0m Running remediation_agent for alert: {state.alert['type']}")
    state.remediation_success = mock_api_response("automation", state.alert)["success"]
    return state

def escalation_agent(state):
    debug_log(f"\033[1;91m🔴\033[0m Running escalation_agent for alert: {state.alert['type']}")
    return state

def self_improvement_agent(state):
    debug_log(f"\033[96m🔷\033[0m Running self_improvement_agent for alert: {state.alert['type']}")
    with open("incident_history.json", "a") as f:
        json.dump(vars(state), f)
        f.write("\n")
    return state

# 📌 Supervisor Agent
def supervisor_agent(state):
    debug_log(f"🕵️‍♂️ Supervisor processing alert: {state.alert['type']}")

    monitoring_agent(state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(incident_history_agent, state),
            executor.submit(knowledge_base_agent, state),
            executor.submit(runbook_agent, state)
        ]
        concurrent.futures.wait(futures)  

    diagnosis_agent(state)  

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(ticketing_agent, state),
            executor.submit(remediation_agent, state)
        ]
        concurrent.futures.wait(futures)

    if not state.remediation_success:
        escalation_agent(state)

    ticketing_agent(state)  
    self_improvement_agent(state)

    debug_log(f"✅ **Execution completed for alert: {state.alert['type']}**")

# 📌 Running the simulation
if __name__ == "__main__":
    workflow = StateGraph(IncidentState)
    workflow.add_node("supervisor", supervisor_agent)
    workflow.set_entry_point("supervisor")
    incident_workflow = workflow.compile()

    def run_simulation():
        mock_alerts = generate_mock_alerts(100)
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_ALERTS) as executor:
            futures = [executor.submit(lambda: incident_workflow.invoke(IncidentState(alert))) for alert in mock_alerts]
            concurrent.futures.wait(futures)

    run_simulation()
