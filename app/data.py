"""Fausses données métier (remplacez par vos vraies APIs / BDD)."""

CUSTOMERS = {
    "C-1001": {"id": "C-1001", "name": "Jane Martin", "email": "jane.martin@example.com", "tier": "gold"},
    "C-1002": {"id": "C-1002", "name": "Karim Ben Salah", "email": "karim.bensalah@example.com", "tier": "silver"},
    "C-1003": {"id": "C-1003", "name": "Sofia Rossi", "email": "sofia.rossi@example.com", "tier": "bronze"},
}

ORDERS = {
    4521: {"order_id": 4521, "customer_id": "C-1001", "status": "shipped", "carrier": "DHL",
           "tracking": "DHL-77821345", "eta": "2026-10-14", "total": 129.90,
           "items": [{"sku": "KB-100", "name": "Mechanical keyboard", "qty": 1}]},
    4522: {"order_id": 4522, "customer_id": "C-1002", "status": "processing", "carrier": None,
           "tracking": None, "eta": "2026-10-18", "total": 54.00,
           "items": [{"sku": "MS-220", "name": "Wireless mouse", "qty": 2}]},
    4523: {"order_id": 4523, "customer_id": "C-1003", "status": "delivered", "carrier": "UPS",
           "tracking": "UPS-99120044", "eta": "2026-10-05", "total": 310.00,
           "items": [{"sku": "MN-27", "name": "27in monitor", "qty": 1}]},
    4524: {"order_id": 4524, "customer_id": "C-1001", "status": "cancelled", "carrier": None,
           "tracking": None, "eta": None, "total": 19.99,
           "items": [{"sku": "CB-USB", "name": "USB-C cable", "qty": 1}]},
}
