import pytest
from pydantic import ValidationError
from src.schemas import OrderEvent


def test_valid_order():
    order = OrderEvent(event_id="e1", customer_id="c1", amount=10, currency="USD", status="paid")
    assert order.amount == 10


def test_negative_amount_rejected():
    with pytest.raises(ValidationError):
        OrderEvent(event_id="e1", customer_id="c1", amount=-10, currency="USD", status="paid")
