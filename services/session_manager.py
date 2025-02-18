from .firebase_service import FirebaseService
from .redis import RedisManager
from .docker_service import DockerService
from .gpu_manager import GPUManager
from typing import Dict, List
from datetime import datetime, timedelta
import asyncio

class SessionManager:

    def __init__(self, redis_manager:RedisManager, firebase_service:FirebaseService, docker_service:DockerService, gpu_manager: GPUManager ):
        
        self.redis = redis_manager.redis
        self.firebase = firebase_service
        self.docker = docker_service
        self.gpu_manager = gpu_manager





    async def start_session(self, user_id: str, container_id: str, duration_hours: int, payment_status: bool = False) -> Dict:
        """Start a new container session with specified duration
        Store session info in Redis with expiry
            Set up monitoring
                Return session details"""
        try:
                session_key = f"session:{container_id}" #this is important

                if self.redis.exists(session_key):
                    return{
                        "status":"error",
                        "message":"session  already exsists for this container"
                    }
                
                current_time = datetime.now()
                end_time = current_time + timedelta(hours=duration_hours) #time delta is a python class to add or sub time from the present time.

                
                session_data = {
                    "container_id":container_id,
                    "payment_status": "paid" if payment_status else "unpaid", #this is important
                    "user_id":user_id,
                    "start_time":current_time.isoformat(),
                    "end_time":end_time.isoformat(),
                    "duration_hours":str(duration_hours),
                    "status":"active"


                }
                self.redis.hmset(session_key, session_data)
                self.redis.expire(session_key, duration_hours * 3600)



                try:
                    await self.firebase.update_container_status(
                        user_id,
                        container_id,
                        "active",                   #this block is to store to firebase 
                        {"session_end":end_time.isoformat()}
                    )
                except Exception as firebase_error:
                    return{
                        "message":f"firebase update failed{str(firebase_error)}"
                    }
                

                return {
                "status": "success",
                "message": "Session started successfully",
                "session_details": {
                "container_id": container_id,
                "start_time": current_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": duration_hours,
                "remaining_time": duration_hours * 3600
                }}
        
        except Exception as e:
                return{
                    "status":"error",
                    "message":f"Failed to start session {str(e)}"
                }
          
    async def get_session_status(self, container_id: str) -> Dict:
        """Get remaining time and status for a container session"""
        try:
            session_key = f"session:{container_id}"

            if not self.redis.exists(session_key):
                 return{
                      "status":"error",
                      "message":f"No active session for the container {container_id}"
                 }


            session_data= self.redis.hgetall(session_key)
            session_data = {k.decode():v.decode() for k,v in session_data.items()}
            end_time = datetime.isoformat(session_data['end_time'])
            current_time =datetime.now()
            time_remaining = (end_time-current_time).total_seconds()

            session_status = "active" if time_remaining > 0 else "expired"
                
            
            
            return {
            "status": "success",
            "session_info": {
                "container_id": container_id,
                "user_id": session_data['user_id'],
                "start_time": session_data['start_time'],
                "end_time": session_data['end_time'],
                "duration_hours": session_data['duration_hours'],
                "status": session_status
            },
            "time_remaining_seconds": max(0, time_remaining),
            "time_remaining_hours": max(0, time_remaining / 3600)
            }
        
        except Exception as e:
             return{
                  "status":"error",
                  "message":f"Error getting session status: {str(e)}"
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
             for session_key in self.redis.scan_iter("session:*"): #here we scan  the entire the list of keys startring  with "session:" using for loop
                  session_data = self.redis.hgetall(session_key)

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

                            self.redis.delete(session_key)
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
            try:
                container = self.docker.containers.get(container_id)
                container_info = container.attrs
            except self.docker.errors.NotFound:
                 return{
                      "status":"error",
                      "message":f"error & warningContainer {container_id} not found, might already be removed"
                        
                 }
            device_requests = container_info["HostConfig"].get("DeviceRequests", [])
            gpu_ids =[]
            for devices in device_requests:
                 if devices.get("Driver") =="nvidia":
                      gpu_ids = devices.get('DeviceIDs',[])
                      for gpu_id in gpu_ids:
                           try:
                                await self.gpu_manager.release_gpu(gpu_id)
                            
                           except Exception as gpu_error:
                                return{
                                     "message": f"Error releasing GPU {gpu_id}: {str(gpu_error)}"
                                }
            try:
                container.stop(timeout=10)
                container.remove(force=True)
                 
            except Exception as container_error:
                return{
                    
                    "Message":f"Error stopping container: {str(container_error)}"
                }
            

            session_key = f"session:{container_id}"
            if self.redis.exists(session_key):
                 self.redis.delete(session_key)
            
            return{
                 "status": "success",
                "message": "Session cleanup completed",
                "released_gpus": gpu_ids
            }
        except Exception as e:
            
            return {
                "status": "Critical error in cleanup_expired_session:",
                "message": f"Cleanup failed: {str(e)}"
            }

                                
                        
                 

             
        
        


                      

            


