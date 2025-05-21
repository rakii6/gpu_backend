from services.firebase_service import FirebaseService

class AuthorizationService:
    def __init__(self, firebase_service: FirebaseService ):
        self.firebase_service = firebase_service
        self.db = firebase_service.db

    # async def can_access_container(self, user_id: str, container_id: str) -> bool: #remember we are "RETURNING" True  and False
    #     """Check if user can access a specific container"""
    #     # Implementation similar to validate_container_ownership
    #     try:
    #         user_doc = self.db.collection('users').document(user_id).get()

    #         if not user_doc.exists():
    #             return False
    #         user_data = user_doc.to_dict()
    #         if 'containers' not in user_data:
    #             return False

    #         containers = user_data['containers']
    #         if not isinstance(containers, list):
    #             print("continaer is not a list for the user")
    #             return False

    #         for container in containers:
    #             if container.get('container_id')== container_id:
    #                 return True
    #         return False
    #     except Exception as e:
    #         print(f"error from the IDOR {str(e)} ")
    #         return False

    async def can_access_container(self, user_id: str, container_id: str) -> bool:
        """Check if user can access a specific container"""
        try:
            print(f"Checking authorization for user_id: {user_id}, container_id: {container_id}")
            container_doc = self.db.collection('users').document(user_id).collection('containers').document(container_id).get()

            if not container_doc.exists:
                print(f"container with {container_id} ID not found in Firebase")
                return False
                
            container_data = container_doc.to_dict()
            print(f"User data: {container_data.keys()}")
            
            if 'user_id' not in container_data:
                print(f"No containers associated with this {user_id} is in the Record.")
                return False
            elif container_data.get('status') == 'terminated':
                print(f"Container {container_id} is terminated and cannot be accessed")
                return False

            required_user = container_data['user_id']
            print(f"Found the require {required_user}")
            
            # if not isinstance(required_user, list):
            #     print("Container is not a list for the user")
            #     return False

            # for i, container in enumerate(containers):
            #     print(f"Checking container {i}: {container.get('container_id')}")
            #     if container.get('container_id') == container_id:
            #         print(f"Found matching container: {container_id}")
            #         return True
            if required_user == user_id:
                return True
            else:
                print(f"No matching container found for {container_id}")
                return False
                    
           
        except Exception as e:
            print(f"Error from the IDOR check: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        

        
    async def can_access_gpu(self, user_id: str, gpu_id: str) -> bool:
        """Check if user can access a specific GPU"""
        # Logic to check if this GPU is allocated to the user
        
    async def is_admin(self, user_id: str) -> bool:
        """Check if user has admin privileges"""
