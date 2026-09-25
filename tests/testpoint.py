def test_chat_endpoint(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    assert "Demo response" in response.json()["reply"]