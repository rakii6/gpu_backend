from firebase_admin import firestore
class UserProfileService:
    def __init__(self, db_client):
        self.db = db_client
        

    async def initialize_user(self, user_id, email, name=None):
        user_doc={
            "profile":{
                "email":email,
                "name":name if name else "",
                "user_id":user_id,
                "created_at":"",
                "status":"active"


            },
            "user_history":{
                
            },
            "billing":{

            },
            "usage":{
                "total_gpu_hours": 0,
                "monthly_usage": {},
                "last_session": None
            },
            "created_at":firestore.SERVER_TIMESTAMP,
        }
        batch = self.db.batch()

        batch.set(self.db.collection('users').document(user_id), user_doc)

        batch.set(self.db.collection('users').document(user_id).collection('containers').document('_info'), {"count":0})
        batch.set(self.db.collection('users').document(user_id).collection('datasets').document('_info'), {"count":0})
        batch.set(self.db.collection('users').document(user_id).collection('models').document('_info'), {"count":0})
        batch.commit()
        return {"status":"Success in the user enviroment initialize", "user_id":user_id}
    
    async def get_user_profile(self, user_id):
        try:
            user_doc= self.db.collection('users').document(user_id).get()

            if not user_doc.exists:
                return{"status":"error",
                       "message":"User profile not found"}
            profile_data = user_doc.to_dict()
            return{"status":"success","profile":profile_data}
        except Exception as e:
            return{"status":"error from the get user profile except block",
                   "message":str(e)
                   }
            



      
