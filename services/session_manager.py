from .firebase_service import FirebaseService
from .redis import RedisManager
from .service_types import DockerService
from .gpu_manager import GPUManager
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz
import asyncio

class SessionManager:

    def __init__(self, redis_manager:RedisManager, firebase_service:FirebaseService, gpu_manager: GPUManager, docker_service: Optional[DockerService] = None ):
        self.redis = redis_manager.redis
        self.session_db = redis_manager.get_database(1)
        self.firebase = firebase_service
        self.gpu_manager = gpu_manager
        self._docker = docker_service
        self.pubsub = self.redis.pubsub()

        asyncio.create_task(self._start_expiry_listener())
        # print(f"Session Manager initialized with docker: {docker_service is not None}")
        
    @property
    def docker(self):
         if self._docker is None:
               print("Warning: Docker service not set in SessionManager")
         return self._docker
    

    @docker.setter
    def docker(self, value):
         print(f"Setting docker service in SessionManager: {value is not None}")
         self._docker = value



    async def start_session(self, user_id: str, container_id: str, duration_hours: int, payment_status: bool = False) -> Dict:
        """Start a new container session with specified duration
        Store session info in Redis with expiry
            Set up monitoring
                Return session details"""
        # self.pubsub.subscribe('__keyevent@0__:expired')
        try:
                session_key = f"session:{container_id}" #this is important

                if self.session_db.exists(session_key):
                    return{
                        "status":"error",
                        "message":"session  already exsists for this container"
                    }
                ist = pytz.timezone('Asia/Kolkata')
                current_time = datetime.now(ist)
                end_time = current_time + timedelta(hours=duration_hours) #time delta is a python class to add or sub time from the present time.
                print(f"this is the {end_time}&{current_time}")
                
                
                
                session_data = {
                    "container_id":container_id,
                    "payment_status": "paid" if payment_status else "unpaid", #this is important
                    "user_id":user_id,
                    "start_time":current_time.isoformat(),
                    "end_time":end_time.isoformat(),
                    "duration_hours":str(duration_hours),
                    "status":"active"
                }
                print("session data created from session method")
                self.session_db.hset(session_key, mapping=session_data)
                
                self.session_db.expire(session_key, int(duration_hours*3600)) #pubsub key event notification, #remeber to change
              


               
                

                return {
                "status": "success",
                "message": "Session started successfully",
                "session_details": {
                "container_id": container_id,
                "start_time": current_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": duration_hours,
                "remaining_time": duration_hours * 3600}
                }
        
        except Exception as e:
                return{
                    "status":"error",
                    "message":f"Failed to start session {str(e)}"
                }
          
    # async def get_session_status(self, container_id: str) -> Dict:
    #     """Get remaining time and status for a container session"""
    #     try:
    #         session_key = None
    #         for key in self.session_db.scan_iter(f"session:{container_id}"):
    #             print("seesion keys found")
    #             session_key = key.decode('utf-8')
    #             break
    #         if not session_key:
    #              return{
    #                   "status":"error",
    #                   "message": f"No active session for the container ID with{container_id}"
    #              }
    #         session_data = self.session_db.hgetall(session_key)
    #         session_data = {k.decode():v.decode() for  k,v in session_data}

    #         end_time = datetime.fromisoformat(session_data['end_time'])
    #         ist = pytz.timezone('Asia/Kolkata')
    #         current_time = datetime.now(ist)
    #         time_remaining = (end_time - current_time).total_seconds()
    #         session_status = "active" if time_remaining > 0 else "expired"             
    #         return {
    #         "status": "success",
    #         "session_info": {
    #             "container_id": container_id,
    #             # "user_id": session_data['user_id'],
    #             "start_time": session_data['start_time'],
    #             "end_time": end_time,
    #             "duration_hours": session_data['duration_hours'],
    #             "status": session_status
    #         },
    #         "time_remaining_seconds": max(0, time_remaining),
    #         "time_remaining_hours": max(0, time_remaining / 3600)
    #         }
        
    #     except Exception as e:
    #          return{
    #               "status":"error",
    #               "message":f"Error getting session status: {str(e)}"
    #          }

    
    async def get_session_status(self, container_id: str) -> Dict:
        """get remaining time and all idc"""
         
        try:
            print(f"Looking for container ID: {container_id}")
            
            # Using the simplified key pattern
            session_key = f"session:{container_id}"
            
            # Check if this session exists
            if not self.session_db.exists(session_key):
                return {
                    "status": "error",
                    "message": f"No active session for container ID: {container_id}"
                }
            
            # Get all session data
            session_data = self.session_db.hgetall(session_key)
            if not session_data:
                return {
                    "status": "error",
                    "message": f"Session exists but has no data"
                }
                
            session_data = {k.decode(): v.decode() for k, v in session_data.items()}
            
            # Calculate remaining time
            end_time = datetime.fromisoformat(session_data['end_time']) 
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)
            time_remaining = (end_time - current_time).total_seconds()
            session_status = "active" if time_remaining > 0 else "expired"
            
            return {
                "status": "success",
                "session_info": {
                    "container_id": container_id,
                    "start_time": session_data['start_time'],
                    "end_time": session_data['end_time'],
                    "duration_hours": session_data['duration_hours'],
                    "status": session_status
                },
                "time_remaining_seconds": max(0, time_remaining),
                "time_remaining_hours": max(0, time_remaining / 3600)
            }
        
        except Exception as e:
            print(f"Error in get_session_status: {str(e)}")
            return {
                "status": "error",
                "message": f"Error getting session status: {str(e)}"
            }



    async def check_container_payment(self, container_id) -> Dict:
        """Check if user can create new containers based on their plan"""
        try:
             session_key = f"session:{container_id}"
             session_data = self.redis.hgetall(session_key)
             if session_data :
                    
                    session_data = {k.decode():v.decode() for k,v in session_data.items()}
                    if session_data.get('payment_status') == 'paid':
                         return{
                       "can_create":True,
                       "message":f"Payment Verified for container creation"
                        }
                    else:
                         return{
                              "can_create":False,
                              "message":"Payment needed for the creation of new container"
                         } 
             return{
                  "can_create": False,
                  "message": "No session found for this container"

             }
        except Exception as e:
            return {
            "status": "error",
            "message": f"Error checking payment: {str(e)}"
        }
                            


    async def _monitor_sessions(self):
        """Background task to monitor active sessions and cleanup expired ones"""

        try:
             for session_key in self.session_db.scan_iter("session:*"): #here we scan  the entire the list of keys startring  with "session:" using for loop
                  session_data = self.session_db.hgetall(session_key)

                  if session_data:
                       session_data = {k.decode():v.decode() for k,v in session_data.items()}

                       end_time = datetime.fromisoformat(session_data.get('end_time'))
                       current_time = datetime.now()

                       if current_time >= end_time:
                            
                            container_id = session_data.get('container_id')
                            user_id = session_data.get('user_id')

                            await self.cleanup_expired_session(container_id)

                            await self.firebase.update_container_status(
                                 user_id,
                                 container_id,
                                 "expired"
                            )

                            self.session_db.delete(session_key)
        except Exception as e:
             return{
                  "status":"error",
                  "message":str(e)
             }





        pass

    async def cleanup_expired_session(self, container_id: str) -> Dict:
        """ Clean up an expired session and its resources
    
    Steps:
    1. Get container info from Docker
    2. Stop and remove container
    3. Release GPU resources
    4. Update status in Firebase
    5. Clean up Redis entries"""
        try:
            session_key = f"session:{container_id}"
            print("session key is collected")
            if self.session_db.exists(session_key):
                 print(f"session is key being deleted")
                 self.session_db.delete(session_key)
                 print(f"session key  deleted{session_key}")
                 return{
                 "status": "success",
                "message": "Session cleanup completed",
                "cleaned_session":session_key
                }
            else:
                return{
                     "status": "warning",
                    "message": "No session data found"
                }
        
        except Exception as e:
            
            return {
                "status": "Critical error in cleanup_expired_session:",
                "message": f"Cleanup failed: {str(e)}"
            }

    async def _start_expiry_listener(self):
          """Background task to listen for Redis key expiration events 
          and then stop the docker container by  calling a method"""

          self.pubsub.subscribe('__keyevent@1__:expired')#please remember that in the pubsub the keyevent must be pointing to the correct db number
          try:
               while True:
                    message = self.pubsub.get_message(timeout=1.0)
                    if message and message['type'] == 'message':
                         expired_key = message['data'].decode('utf-8')
                         if expired_key.startswith('session:'):
                              parts = expired_key.split(':')#classic split technique and gettin continaer id
                              if len(parts) == 2:
                                   container_id= parts[1]
                                   print(f"Session expired for container {container_id}")
                                   if self.docker:
                                        await self._docker.cleanup_container(container_id)
                                   else:
                                        print("ERROR: Docker service not available!")
                                        

                              
                # Small sleep to prevent CPU spinning
                    await asyncio.sleep(0.1)
          except Exception as e:
                print("Yeah we failed to delete the session key automatically")
                asyncio.create_task(self._start_expiry_listener())
               
         
                                
                        
                 

             
        
        


                      

            


