import requests

def call_n8n_workflow(payload: dict):
    url = "https://example.com/webhook/test"  # dummy for now

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}