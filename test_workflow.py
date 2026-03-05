import requests
import json
import time

url = "http://127.0.0.1:5000/process"
files = {'files': open('dummy.pdf', 'rb')}

data = {
    'model': 'gpt-4o',
    'hotel_code': 'STLMO',
    'api_key': 'dummy_key'
}

response = requests.post(url, files=files, data=data)
print("Process Response:")
print(response.status_code)
res_json = response.json()
print(res_json)

# Even though it fails because of the dummy key, we can test that the session handling works
session_id = res_json.get('session_id')
if session_id:
    print(f"Got session_id: {session_id}")
    finalize_url = "http://127.0.0.1:5000/finalize"
    finalize_data = {
        'session_id': session_id,
        'placements': {
            'dummy.pdf': 'top-right'
        }
    }
    fin_response = requests.post(finalize_url, json=finalize_data)
    print("Finalize Response:")
    print(fin_response.status_code)
    print(fin_response.json())
else:
    print("No session ID returned!")
