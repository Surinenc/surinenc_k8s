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

# 🔹 Cargar variables de entorno
load_dotenv()

# 🔥 Configuración de paralelismo
MAX_PARALLEL_ALERTS = 5  
TIMEOUT_SECONDS = 30  # ⏳ Máximo tiempo de espera por agentes paralelos

# 📌 Imprimir configuración al inicio
print(f"\n🚀 Configuración de ejecución: {MAX_PARALLEL_ALERTS} alertas en paralelo, Timeout: {TIMEOUT_SECONDS}s\n")

# 📌 Función para debug con Thread ID al inicio y bolita de color
def debug_log(message, color="\033[97m"):
    thread_id = threading.get_ident()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Thread-{thread_id}] {color}{message}\033[0m [{timestamp}]")

# 📌 Generar Alertas Simuladas
fake = Faker()
def generate_mock_alerts(n=100):
    alert_types = ["CPU High", "Memory Leak", "Disk Full", "Network Latency", "Service Down"]
    severities = ["Critical", "High", "Medium", "Low"]
    
    return [
        {"id": fake.uuid4(), "type": random.choice(alert_types), "severity": random.choice(severities), "timestamp": fake.date_time_this_year().isoformat()}
        for _ in range(n)
    ]

# 📌 API Simulada con Timeout de 30s
def mock_api_response(endpoint, alert):
    delay = random.uniform(3, 40)
    debug_log(f"⌛ Llamando a {endpoint} con delay de {delay:.2f}s para alerta: {alert['type']}")
    
    if delay > TIMEOUT_SECONDS:
        debug_log(f"⚠️ Timeout en {endpoint}, asumiendo sin respuesta.")
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

# 📌 Estado del Incidente
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

# 📌 Modelo de OpenAI en Azure
def get_azure_chat_model():
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_API_BASE"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

# 📌 Agentes
def monitoring_agent(state):
    debug_log(f"\033[94m🔵\033[0m Ejecutando monitoring_agent para alerta: {state.alert['type']}")
    state.alert['status'] = mock_api_response("logicmonitor", state.alert)
    return state

def incident_history_agent(state):
    debug_log(f"\033[38;5;214m🟠\033[0m Ejecutando incident_history_agent para alerta: {state.alert['type']}")
    state.history_match = mock_api_response("servicenow_incidents", state.alert)
    return state

def knowledge_base_agent(state):
    debug_log(f"\033[92m🟢\033[0m Ejecutando knowledge_base_agent para alerta: {state.alert['type']}")
    state.kb_suggestion = mock_api_response("confluence_kb", state.alert)
    return state

def runbook_agent(state):
    debug_log(f"\033[95m🟣\033[0m Ejecutando runbook_agent para alerta: {state.alert['type']}")
    solution = mock_api_response("runbook", state.alert)
    if solution:
        state.runbook_solution.append(solution)
    return state

def diagnosis_agent(state):
    debug_log(f"\033[91m🔴\033[0m Ejecutando diagnosis_agent para alerta: {state.alert['type']}")
    model = get_azure_chat_model()
    response = model.invoke([HumanMessage(content=f"Diagnose this alert: {state.alert}, history: {state.history_match}, knowledge base: {state.kb_suggestion}, runbook: {state.runbook_solution}")])
    state.root_cause = response.content
    return state

def remediation_agent(state):
    debug_log(f"\033[93m🟡\033[0m Ejecutando remediation_agent para alerta: {state.alert['type']}")
    state.remediation_success = mock_api_response("automation", state.alert)["success"]
    return state

def ticketing_agent(state):
    debug_log(f"\033[97m⚪\033[0m Creando ticket en ServiceNow para alerta: {state.alert['type']}")
    state.ticket_id = mock_api_response("servicenow_tickets", state.alert)["ticket_id"]
    return state

def escalation_agent(state):
    debug_log(f"\033[1;91m🔴\033[0m Escalando incidente para alerta: {state.alert['type']}")
    return state

def self_improvement_agent(state):
    debug_log(f"\033[96m🔷\033[0m Aprendiendo del incidente para alerta: {state.alert['type']}")
    with open("incident_history.json", "a") as f:
        json.dump(vars(state), f)
        f.write("\n")
    return state

# 📌 Supervisor corregido con flujo completo y paralelismo
def supervisor_agent(state):
    debug_log(f"🕵️‍♂️ Supervisor procesando alerta: {state.alert['type']}")

    monitoring_agent(state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_agents = {
            executor.submit(incident_history_agent, state),
            executor.submit(knowledge_base_agent, state),
            executor.submit(runbook_agent, state),
        }

        concurrent.futures.wait(future_agents, timeout=TIMEOUT_SECONDS)

    diagnosis_agent(state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_agents = {
            executor.submit(ticketing_agent, state),
            executor.submit(remediation_agent, state),
        }
        concurrent.futures.wait(future_agents)

    if not state.remediation_success:
        escalation_agent(state)

    ticketing_agent(state)
    self_improvement_agent(state)

    return state

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
