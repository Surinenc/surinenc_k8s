import os
import json
import time
import random
import threading  # 🔹 Para ejecutar hilos reales
import concurrent.futures  # 🔹 Para ejecutar en paralelo
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

# 📌 Función para debug con Thread ID
def debug_log(message):
    thread_id = threading.get_ident()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Thread-{thread_id}] {message}")

# 📌 Crear espacio de memoria separado por hilo
thread_local = threading.local()

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
    """Simula respuestas de API con un timeout de 30 segundos."""
    delay = random.uniform(3, 40)  # ⏳ Simula una latencia aleatoria entre 3 y 40s
    debug_log(f"⌛ Llamando a {endpoint} con delay de {delay:.2f}s para alerta: {alert['type']}")

    time.sleep(min(delay, 30))  # ⏳ Simula el delay con timeout máximo de 30s
    
    # 🔹 Modificaciones aplicadas: LogicMonitor con 80% de "down"
    mock_responses = {
        "logicmonitor": {"status": "down" if random.random() > 0.2 else "ok"},
        "servicenow_incidents": {"similar_case": f"Resolved: {alert['type']} issue on {fake.date()}" if random.random() > 0.5 else None},
        "confluence_kb": {"suggestion": f"Check {alert['type']} troubleshooting guide" if random.random() > 0.5 else None},
        "runbook": {"solution": f"Run script to fix {alert['type']}" if random.random() > 0.8 else None},
        "automation": {"success": random.random() > 0.2},  # 🔹 80% de éxito
        "servicenow_tickets": {"ticket_id": fake.uuid4()}
    }
    
    return mock_responses.get(endpoint, {})

# 📌 Estado del Incidente (Cada Hilo Tiene su Propia Instancia)
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
    debug_log(f"🟢 Ejecutando monitoring_agent para alerta: {state.alert['type']}")
    state.alert['status'] = mock_api_response("logicmonitor", state.alert)
    return state

def diagnosis_agent(state):
    debug_log(f"🟢 Ejecutando diagnosis_agent para alerta: {state.alert['type']}")
    model = get_azure_chat_model()
    response = model.invoke([HumanMessage(content=f"Diagnose this alert: {state.alert}, history: {state.history_match}, knowledge base: {state.kb_suggestion}, runbook: {state.runbook_solution}")])
    state.root_cause = response.content
    return state

def incident_history_agent(state):
    debug_log(f"🟢 Ejecutando incident_history_agent para alerta: {state.alert['type']}")
    state.history_match = mock_api_response("servicenow_incidents", state.alert)
    return state

def knowledge_base_agent(state):
    debug_log(f"🟢 Ejecutando knowledge_base_agent para alerta: {state.alert['type']}")
    state.kb_suggestion = mock_api_response("confluence_kb", state.alert)
    return state

def runbook_agent(state):
    debug_log(f"🟢 Ejecutando runbook_agent para alerta: {state.alert['type']}")
    solution = mock_api_response("runbook", state.alert)
    if solution:
        state.runbook_solution.append(solution)
    return state

def remediation_agent(state):
    debug_log(f"🟢 Ejecutando remediation_agent para alerta: {state.alert['type']}")
    state.remediation_success = random.random() > 0.2  # 🔹 80% de éxito
    return state

def ticketing_agent(state):
    debug_log(f"🟢 Creando ticket en ServiceNow para alerta: {state.alert['type']}")
    state.ticket_id = mock_api_response("servicenow_tickets", state.alert)
    return state

# 📌 Supervisor con ejecución en paralelo
def supervisor_agent(state):
    debug_log(f"🕵️‍♂️ Supervisor procesando alerta: {state.alert['type']}")

    monitoring_agent(state)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_agents = {
            executor.submit(incident_history_agent, state): "history",
            executor.submit(knowledge_base_agent, state): "kb",
            executor.submit(runbook_agent, state): "runbook",
        }

        for future in concurrent.futures.as_completed(future_agents, timeout=30):
            try:
                future.result()
            except concurrent.futures.TimeoutError:
                debug_log(f"⚠️ Timeout alcanzado para {future_agents[future]}.")

    diagnosis_agent(state)
    ticketing_agent(state)
    remediation_agent(state)
    ticketing_agent(state)

    return state

# 📌 Crear Workflow de LangGraph y Compilarlo
workflow = StateGraph(IncidentState)
workflow.add_node("supervisor", supervisor_agent)
workflow.set_entry_point("supervisor")
incident_workflow = workflow.compile()

# 📌 Procesar una Alerta en un Hilo Separado
def process_alert(alert):
    thread_local.state = IncidentState(alert)
    return incident_workflow.invoke(thread_local.state)

# 📌 Ejecutar Simulación con ThreadPoolExecutor (5 en Paralelo)
def run_simulation():
    mock_alerts = generate_mock_alerts(100)
    debug_log("\n🚀 Ejecutando 100 simulaciones con Supervisor...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_alert, alert): alert for alert in mock_alerts}
        concurrent.futures.wait(futures)

    debug_log("\n✅ Simulación completada.")

# 📌 Iniciar la simulación
run_simulation()
