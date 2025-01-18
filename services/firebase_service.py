from dotenv import load_dotenv
import os
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict
load_dotenv()
cred_path=os.getenv("FIREBASE_CREDENTIAL_PATH")

class FirebaseService:
    def __init__(self):
        
        cred= credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    async def store_container_info(self, user_id:str, container_data:Dict):
        """Store container information for a user"""


        try:
            #need to verify  if user exists or not
            user_ref =self.db.collection('users').document(user_id)
            user=user_ref.get()

            if not user.exists:
                return{"Status":"error", "message":"user not founnd,"}
            
            #then we need to store the info of that user
            #in the exisiting user documnet

            # container_ref = self.db.collection('containers').document(container_data['container_id'])
            # container_ref.set({
            #     'user_id':user_id,
            #     'container_id':container_data['container_id'],
            #     'created_at': firestore.SERVER_TIMESTAMP,
            #     'status':'active'
            # })
            

            #updating the user's containers list
            # user_ref.update({
            #     'containers':firestore.firestore.ArrayUnion([{
            #         'container_id':container_data['container_id'],
            #         'subdomain':container_data.get('subdomain'),
            #         'created_at': firestore.SERVER_TIMESTAMP,
            #         'status':'active',
            #         'resource_usage':{
            #             'gpu_allocated':True,
            #             'port':container_data.get('port')
            #         }
            #     }])
            # })
            
            if not user.get('containers'):
                user_ref.set({
                    'containers':[container_data]
                }, merge=True)
            else:
                user_ref.update({
                    'containers': firestore.ArrayUnion([container_data])
                })

            return{"status":"success","message":"Contaiiner info stoored"}
        except Exception as e:
            return{"status":"error","Message":str(e)}



        # doc_ref=self.db.collection('containers').document(user_id)
        
        # doc_ref.set({
        #     'container_id':container_data['container_id'],
        #     'subdomain':container_data['subdomain'],
        #     'created_at':firestore.SERVER.TIMESTAMP,
        #     'status':'active',
        #     'resource_usage':{
        #         'gpu_allocated':True,
        #         'port':container_data['port']
        #     }
        # }) this piece of code creates a new collection 

    async def get_user_container(self, user_id:str):
        """Get all containers for a user"""
        docs = self.db.collection('containers').where('user__id','==',user_id).stream()
        return [doc.to_dict() for doc in docs]


    async def update_container_status(self, user_id:str, container_id:str, status:str):
        """Update container Status"""

        doc_ref = self.db.collection('containers').document(user_id)
        doc_ref.update({
            'status':status,
            'last_updated':firestore.SERVER_TIMESTAMP
        })

    async def create_test_user(self):
        """This is just to create a test user"""
        try:
            user_data ={
                'email':'test@example.com',
                'name': 'Test User',
                'created_at':firestore.SERVER_TIMESTAMP,
                'containers':[]
            }

            #this here generates a doc with auto-ID

            doc_ref = self.db.collection('users').add(user_data)

            return{"status":"success","user_id":doc_ref[1].id}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        
    async def get_user(self, user_id:str):
        """Check, does user exists"""

        try:
            doc_ref= self.db.collection('users').document(user_id)
            doc = doc_ref.get()

            if doc.exists:
                return{"status":"success",
                       "user_data":doc.to_dict()}
            else:
                return{"status":"Error", "message":"user not foound"}
        except Exception as e:
            return{"status":"error", "message":str(e)}
        
    


        
        

       

        
