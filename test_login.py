# """Quick test to find valid credentials"""
# import requests
#
# BASE_URL = "http://127.0.0.1:8000"
#
# test_users = [
#     ("manager1@test.com", "password"),
#     ("manager1@test.com", "test123"),
#     ("manager1@test.com", "manager123"),
#     ("manager2@test.com", "password"),
#     ("testuser@example.com", "password"),
#     ("testuser@example.com", "test123"),
#     ("gelkomos@lightidea.org", "password"),
# ]
#
# for email, password in test_users:
#     try:
#         response = requests.post(
#             f"{BASE_URL}/auth/login/",
#             json={"email": email, "password": password},
#             timeout=5
#         )
#         if response.status_code == 200:
#             data = response.json()
#             print(f"✓ SUCCESS: {email} / {password}")
#             print(f"  Access Token: {data['tokens']['access'][:50]}...")
#             break
#         else:
#             print(f"✗ Failed: {email} / {password} - Status {response.status_code}")
#     except Exception as e:
#         print(f"✗ Error: {email} / {password} - {e}")
