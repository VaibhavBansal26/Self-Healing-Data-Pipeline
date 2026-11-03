from src.kafka_lag import get_consumer_lag


def test_kafka_lag_returns_structured_response_without_kafka():
    result = get_consumer_lag(topic="unlikely_missing_test_topic")
    assert "status" in result
    assert "partitions" in result
