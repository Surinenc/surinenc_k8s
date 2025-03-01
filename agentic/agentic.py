import random
import json
import time
from tqdm import tqdm
from faker import Faker
import requests
import datetime
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
import langgraph
from langgraph.graph import StateGraph

from dotenv import load_dotenv
import os

load_dotenv()

# 📌 Generar datos falsos para 100 alertas
fake = Faker()
def generate_mock_alerts(n=100):
    alert_types = ["CPU High", "Memory Leak", "Disk Full", "Network Latency", "Service Down"]
    severities = ["Critical", "High", "Medium", "Low"]
    
    alerts = []
    for _ in range(n):
        alerts.append({
            "id": fake.uuid4(),
            "type": random.choice(alert_types),
            "severity": random.choice(severities),
            "timestamp": fake.date_time_this_year().isoformat()
        })
    
    return alerts

# 📌 Simular APIs con respuestas mock
def mock_api_response(endpoint, alert):
    mock_responses = {
        "logicmonitor": {"status": "ok" if random.random() > 0.2 else "down"},
        "servicenow_incidents": {"similar_case": f"Resolved: {alert['type']} issue on {fake.date()}" if random.random() > 0.5 else None},
        "confluence_kb": {"suggestion": f"Check {alert['type']} troubleshooting guide" if random.random() > 0.5 else None},
        "runbook": {"solution": f"Run script to fix {alert['type']}" if random.random() > 0.6 else None},
        "automation": {"success": random.random() > 0.7},
        "servicenow_tickets": {"ticket_id": fake.uuid4()}
    }
    return mock_responses.get(endpoint, {})

# 📌 Clase de estado con métricas
class IncidentState:
    def __init__(self, alert=None):
        self.alert = alert
        self.root_cause = None
        self.history_match = None
        self.kb_suggestion = None
        self.runbook_solution = None
        self.remediation_success = None
        self.ticket_id = None
        self.start_time = time.time()  # 📊 Iniciar tiempo de respuesta

# 📌 Agentes especializados
def monitoring_agent(state):
    state.alert['status'] = mock_api_response("logicmonitor", state.alert).get("status")
    return state

def diagnosis_agent(state):
    model = ChatOpenAI(model="gpt-3.5-turbo")
    response = model([HumanMessage(content=f"Diagnose this alert: {state.alert}")])
    state.root_cause = response.content
    return state

def incident_history_agent(state):
    state.history_match = mock_api_response("servicenow_incidents", state.alert).get("similar_case")
    return state

def knowledge_base_agent(state):
    state.kb_suggestion = mock_api_response("confluence_kb", state.alert).get("suggestion")
    return state

def runbook_agent(state):
    state.runbook_solution = mock_api_response("runbook", state.alert).get("solution")
    return state

def human_interaction_agent(state):
    """Permite la intervención humana si no hay runbook"""
    if not state.runbook_solution:
        print(f"\n🛑 ALERTA: {state.alert['type']} no tiene un runbook asociado.")
        user_input = input("👨‍💻 ¿Puedes sugerir una acción manualmente? (o presiona Enter para omitir): ")
        if user_input.strip():
            state.runbook_solution = user_input.strip()
    return state

def remediation_agent(state):
    if state.runbook_solution or state.history_match:
        state.remediation_success = mock_api_response("automation", state.alert).get("success")
    return state

def escalation_agent(state):
    if not state.remediation_success:
        state.ticket_id = mock_api_response("servicenow_tickets", state.alert).get("ticket_id")
    return state

def ticketing_agent(state):
    state.ticket_id = mock_api_response("servicenow_tickets", state.alert).get("ticket_id")
    return state

def self_improvement_agent(state):
    if not state.remediation_success:
        print(f"📈 Mejorando el sistema basado en fallo: {state.alert['type']}")
    return state

def calculate_metrics(state):
    """Calcula métricas de rendimiento y las guarda"""
    resolution_time = round(time.time() - state.start_time, 2)
    metrics = {
        "alert_id": state.alert["id"],
        "type": state.alert["type"],
        "severity": state.alert["severity"],
        "resolution_time": resolution_time,
        "remediation_success": state.remediation_success,
        "human_intervention": state.runbook_solution is not None and isinstance(state.runbook_solution, str)
    }
    return metrics

# 📌 Crear flujo en LangGraph
workflow = StateGraph(IncidentState)
workflow.add_node("monitoring", monitoring_agent)
workflow.add_node("diagnosis", diagnosis_agent)
workflow.add_node("incident_history", incident_history_agent)
workflow.add_node("knowledge_base", knowledge_base_agent)
workflow.add_node("runbook", runbook_agent)
workflow.add_node("human_interaction", human_interaction_agent)
workflow.add_node("remediation", remediation_agent)
workflow.add_node("escalation", escalation_agent)
workflow.add_node("ticketing", ticketing_agent)
workflow.add_node("self_improvement", self_improvement_agent)

workflow.add_edge("monitoring", "diagnosis")
workflow.add_edge("diagnosis", "incident_history")
workflow.add_edge("incident_history", "knowledge_base")
workflow.add_edge("knowledge_base", "runbook")
workflow.add_edge("runbook", "human_interaction")
workflow.add_edge("human_interaction", "remediation")
workflow.add_edge("remediation", "ticketing")
workflow.add_edge("remediation", "escalation")
workflow.add_edge("ticketing", "self_improvement")

workflow.set_entry_point("monitoring")
incident_workflow = workflow.compile()

# 📌 Ejecutar simulación con 100 alertas y registrar métricas
mock_alerts = generate_mock_alerts(100)

print("\n🚀 Ejecutando 100 simulaciones con métricas y soporte humano...\n")
metrics_results = []

for alert in tqdm(mock_alerts):
    state = IncidentState(alert=alert)
    final_state = incident_workflow.invoke(state)
    metrics = calculate_metrics(final_state)
    metrics_results.append(metrics)
    time.sleep(0.1)  # Simulación de latencia

# 📌 Guardar métricas en JSON
with open("performance_metrics.json", "w") as f:
    json.dump(metrics_results, f, indent=4)

print("\n✅ Simulación completada. Métricas guardadas en 'performance_metrics.json'.")
