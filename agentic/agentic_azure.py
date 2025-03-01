import os
import json
import time
import random
import threading  # 🔹 Para ejecutar hilos reales
import concurrent.futures  # 🔹 Para ejecutar en hilos separados
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
    return {"response": f"Datos de {endpoint} para {alert['type']}"}

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

# 📌 Agentes (Cada Hilo Usa su Propia Instancia de `IncidentState`)
def monitoring_agent(state):
    debug_log(f"🟢 Ejecutando monitoring_agent para alerta: {state.alert['type']}")
    state.alert['status'] = mock_api_response("logicmonitor", state.alert)
    return state

def diagnosis_agent(state):
    debug_log(f"🟢 Ejecutando diagnosis_agent para alerta: {state.alert['type']}")
    model = get_azure_chat_model()
    response = model.invoke([HumanMessage(content=f"Diagnose this alert: {state.alert}")])
    state.root_cause = response.content
    return state

# 📌 Supervisor ahora recibe `state`
def supervisor_agent(state):
    """Cada hilo tiene su propio `IncidentState`, evitando memoria compartida."""
    debug_log(f"🕵️‍♂️ Supervisor procesando alerta: {state.alert['type']}")

    monitoring_agent(state)
    diagnosis_agent(state)

    return state

# 📌 Crear Workflow de LangGraph y Compilarlo
workflow = StateGraph(IncidentState)
workflow.add_node("supervisor", supervisor_agent)  # ✅ LangGraph pasará `state` automáticamente
workflow.set_entry_point("supervisor")
incident_workflow = workflow.compile()

# 📌 Ejecutar Simulación con ThreadPoolExecutor (5 en Paralelo)
def run_simulation():
    mock_alerts = generate_mock_alerts(100)
    debug_log("\n🚀 Ejecutando 100 simulaciones con Supervisor (5 en paralelo, Threads Reales con Espacio de Memoria Individual)...\n")

    metrics_results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_alert, alert): alert for alert in mock_alerts}
        for future in concurrent.futures.as_completed(futures):
            metrics_results.append(future.result())

    with open("azure_performance_metrics.json", "w") as f:
        json.dump(metrics_results, f, indent=4)

    debug_log("\n✅ Simulación completada. Métricas guardadas en 'azure_performance_metrics.json'.")

# 📌 Procesar una Alerta en un Hilo Separado (Cada Hilo Usa su Propio `IncidentState`)
def process_alert(alert):
    thread_local.state = IncidentState(alert)  # ✅ Cada hilo tiene su propia instancia
    final_state = incident_workflow.invoke(thread_local.state)  # ✅ Ahora `supervisor_agent` recibe `state`
    return final_state

# 📌 Iniciar la simulación
run_simulation()
