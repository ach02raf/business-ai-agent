"""Les 3 tools métier + registre.

Chaque tool valide ses arguments avec Pydantic (défense en profondeur :
la validation a lieu côté agent ET côté tool/serveur MCP).
"""
import json
import os
import threading
from dataclasses import dataclass
from typing import Callable, Literal, Type

from pydantic import BaseModel, Field

from .config import get_settings
from .data import CUSTOMERS, ORDERS

_lock = threading.Lock()


# ----------------------------- Schémas d'entrée -----------------------------
class SearchCustomerInput(BaseModel):
    query: str = Field(min_length=2, max_length=100,
                       description="Nom, email ou ID client (ex: 'Jane', 'jane.martin@example.com', 'C-1001')")


class GetOrderInput(BaseModel):
    order_id: int = Field(ge=1, le=9_999_999, description="Numéro de commande, ex: 4521")


class CreateTicketInput(BaseModel):
    customer_id: str = Field(pattern=r"^C-\d{4}$", description="ID client, format C-1234")
    subject: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    priority: Literal["low", "medium", "high"] = "medium"


# --------------------------------- Helpers ---------------------------------
def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _load_tickets() -> list[dict]:
    path = get_settings().tickets_file
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_tickets(tickets: list[dict]) -> None:
    path = get_settings().tickets_file
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2, ensure_ascii=False)


def list_tickets() -> list[dict]:
    with _lock:
        return _load_tickets()


# ---------------------------------- Tools ----------------------------------
def search_customer(query: str) -> dict:
    """Recherche un client par nom, email ou ID. Les emails sont masqués (PII)."""
    q = SearchCustomerInput(query=query).query.lower()
    matches = [
        {**c, "email": _mask_email(c["email"])}
        for c in CUSTOMERS.values()
        if q in c["name"].lower() or q in c["email"].lower() or q == c["id"].lower()
    ]
    return {"count": len(matches), "customers": matches}


def get_order(order_id: int) -> dict:
    """Retourne le statut et le détail d'une commande."""
    oid = GetOrderInput(order_id=order_id).order_id
    order = ORDERS.get(oid)
    if not order:
        return {"error": "not_found", "detail": f"Order #{oid} not found"}
    return order


def create_ticket(customer_id: str, subject: str, description: str, priority: str = "medium") -> dict:
    """Crée un ticket support (action d'ÉCRITURE : validation humaine requise)."""
    data = CreateTicketInput(customer_id=customer_id, subject=subject,
                             description=description, priority=priority)
    if data.customer_id not in CUSTOMERS:
        return {"error": "not_found", "detail": f"Customer {data.customer_id} not found"}
    with _lock:
        tickets = _load_tickets()
        ticket = {"ticket_id": f"T-{len(tickets) + 1:04d}", "status": "open", **data.model_dump()}
        tickets.append(ticket)
        _save_tickets(tickets)
    return ticket


# --------------------------------- Registre ---------------------------------
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: Type[BaseModel]
    func: Callable[..., dict]


TOOLS: dict[str, ToolSpec] = {
    "search_customer": ToolSpec("search_customer", "Search a customer by name, email or customer ID.",
                                SearchCustomerInput, search_customer),
    "get_order": ToolSpec("get_order", "Get the status and details of an order by its order number.",
                          GetOrderInput, get_order),
    "create_ticket": ToolSpec("create_ticket", "Create a support ticket for a customer. Write action.",
                              CreateTicketInput, create_ticket),
}
