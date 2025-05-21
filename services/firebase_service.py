from dotenv import load_dotenv
import os, arrow
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict,  Optional, Any
load_dotenv()
cred_path=os.getenv("FIREBASE_CREDENTIAL_PATH")

class FirebaseService:
    is_initialized = False
    
    def __init__(self):

        if not FirebaseService.is_initialized:
            try:
                #we are setting core firebase conncetion once
                cred= credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                FirebaseService.is_initialized = True
            except Exception as e:
                return{
                    "status":"firebase init failed",
                    "message":str(e)
                }
        self.db = firestore.client()



        
        

    async def store_container_info(self, container_id:str, container_data:Dict):
        """Create a new container record"""

        try:
            required_fields = ['user_id', 'container_id','type','subdomain']
            for field in required_fields:
                if field not in container_data:
                    return{
                        "status":"error",
                        "Message":"Bruh missing fields"
                    }
            if 'created_at' not in container_data:
                container_data['created_at']= arrow.utcnow()
            


            user_id = container_data['user_id']
            container_ref = self.db.collection('users').document(user_id)
            container_ref.collection('containers').document(container_id).set(container_data)
            info_doc_ref = container_ref.collection('containers').document('_info')
            info_doc_ref.update({ 
            "total_count":firestore.Increment(1)
            })
            return{
                "status":'success',
                "message":"Container created Successfully",
                "container_id":container_id
            }
        except Exception as e:
            return{
                "status":"error",
                "message":f"Failed to create and store the container in fireDB {str(e)}"
            }


      


    async def get_user_container(self, user_id:str):
        """Get all containers for a user"""
        docs = self.db.collection('containers').where('user__id','==',user_id).stream()
        return [doc.to_dict() for doc in docs]


    async def update_container_status(self, container_id:str, status:str, user_id:str):

        """Update container Status"""
        try:
            print("looking for contianaer to pause")
            container_ref = self.db.collection('users').document(user_id).collection('containers').document(container_id)
            container = container_ref.get()
            print(f'continaer found {container}')

            if not container.exists:
                return{
                    'status':"error",
                    "message":f"container with {container_id} id not found in the db"
                }
            update_data = {
                'status':status,
                'last_active':firestore.SERVER_TIMESTAMP
            }
            # if additional_data:
            #     update_data.update(additional_data) #method to add another entry in dict
           
            container_ref.update(update_data)
            updated_doc = container_ref.get().to_dict()
            print(f"Document in firebase after update: {updated_doc}")
            return{
                'status':'success',
                'message':f'container status updated to {container_id} id'
            }
        except Exception as e:
            return{
                'status':'error',
                'message':f'Failed to update the container with {container_id}'
            }

       

    async def get_users_containers(self, user_id:str)->Dict:
        """Get all the containers assocaited with that 
        particular user, using their user_id as a param,
        and searching it in the containers collection in firebase"""

        
        try:
            containers_ref = self.db.collection('users').document(user_id).collection('containers')
            # container_list = [{"id":doc.id, **doc.to_dict()} for doc in containers]
            all_containers = containers_ref.stream()
            container_data = {}
            for container in all_containers:
                container_data[container.id]=container.to_dict()

           

            return{
                "status":"success",
                "data":container_data,
                "count":len(container_data)
            }
        except Exception as e:
            return{
                "status":"Error",
                "message":f"Failed to get user containers {str(e)}"
            }



    # async def get_container_by_subdomain(self,subdomain):
        



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
        
    


        
        

       

        
