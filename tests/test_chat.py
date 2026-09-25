def test_chat_route_echoes_message(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "You said: Hello",
    }