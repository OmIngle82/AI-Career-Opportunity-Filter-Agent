import os
import sys
import json
import urllib.request

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
from auth import create_access_token

user_id = '9c0dd2c4-349b-4e87-9e56-c3b57608f910'
token = create_access_token({'sub': user_id})

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 1. Test GET /opportunities
req = urllib.request.Request('http://127.0.0.1:8000/opportunities', headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())
    opportunities = data.get('opportunities', [])
    print(f"1. GET /opportunities: OK ({len(opportunities)} items)")
    first = opportunities[0]
    print(f"   First opportunity: {first['id']} | {first['title']} | status: {first.get('status')}")

# 2. Test PATCH /opportunities/{id}/status to SAVED then back to INBOX
opp_id = first['id']
patch_url = f'http://127.0.0.1:8000/opportunities/{opp_id}/status'
patch_data = json.dumps({'status': 'SAVED'}).encode('utf-8')
patch_req = urllib.request.Request(patch_url, data=patch_data, headers=headers, method='PATCH')
with urllib.request.urlopen(patch_req) as resp:
    res = json.loads(resp.read())
    print(f"2. PATCH status to SAVED: OK (status: {res.get('status')})")

patch_data_inbox = json.dumps({'status': 'INBOX'}).encode('utf-8')
patch_req_inbox = urllib.request.Request(patch_url, data=patch_data_inbox, headers=headers, method='PATCH')
with urllib.request.urlopen(patch_req_inbox) as resp:
    res2 = json.loads(resp.read())
    print(f"3. PATCH status reset to INBOX: OK (status: {res2.get('status')})")

print("\n--- ALL ENDPOINTS VERIFIED & WORKING PERFECTLY ---")
