# app/services/billing_service.py
# class BillingService:
#     def __init__(self, firebase_service):
#         self.firebase = firebase_service

#     async def start_session(self, user_id: str, container_id: str):
#         """Start billing session for container usage"""
#         self.db.collection('billing').add({
#             'user_id': user_id,
#             'container_id': container_id,
#             'start_time': firestore.SERVER_TIMESTAMP,
#             'status': 'active'
#         })

#     async def end_session(self, user_id: str, container_id: str):
#         """End billing session and calculate usage"""
#         # Calculate time used and update billing record
#         pass