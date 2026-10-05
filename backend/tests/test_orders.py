from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@patch("app.api.orders.get_redis_client")
def test_create_and_get_order(mock_redis):
    mock_redis.return_value = None

    order_payload = {
        "customer_email": "ops-lead@company.com",
        "item_name": "Cloud Compute Node",
        "quantity": 3,
        "total_amount": 299.99,
    }

    create_res = client.post("/api/v1/orders", json=order_payload)

    assert create_res.status_code == 201

    created_data = create_res.json()

    assert created_data["id"] is not None
    assert created_data["customer_email"] == "ops-lead@company.com"
    assert created_data["status"] == "CONFIRMED"

    order_id = created_data["id"]

    get_res = client.get(f"/api/v1/orders/{order_id}")

    assert get_res.status_code == 200
    assert get_res.json()["id"] == order_id


def test_get_nonexistent_order():
    res = client.get("/api/v1/orders/999999")

    assert res.status_code == 404