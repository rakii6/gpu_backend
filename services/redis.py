from dotenv import load_dotenv
import os
import redis
from datetime import datetime
import asyncio
import time
import json
import GPUtil
import threading
import traceback
from services.system_metrics import System_Metrics
load_dotenv()
redis_love=os.getenv("REDIS_LOVER")



class RedisManager:

    is_connected =False
    redis_client =None
    database_connections = {}

    def __init__(self, system_metrics :System_Metrics ):
        if not RedisManager.is_connected:
            print("RedisManager initialization called from:", traceback.format_stack()[-2])
            try:
                print("Connecting to Redis for the first time...")
                RedisManager.redis_client= redis.Redis(
                host='localhost',
                port=6379,
                password=redis_love
                )
                RedisManager.database_connections[0]=RedisManager.redis_client #storage of db conncetion, the 0 db
                RedisManager.redis_client.config_set('notify-keyspace-events', 'Ex')
                print("Key space notification enabled")

                RedisManager.is_connected = True
                print("Redis connection established")
                
            except Exception as e:
                # return{
                # "status":"error from Redis Init seciton",
                # "message":str(e)}
                print(f"Failed to connect to Redis: {e}")
                raise
        self.redis = RedisManager.redis_client
        self.gpu_lock = threading.Lock()
        self.system_metrics = system_metrics

        
    
    def redis_overlord(self):# Function to update/note/check GPU status in Redis daily
            try:
                print("starting detections ...........")

                time.sleep(1)
                system_data = self.system_metrics.send_stats()
                print(f"System data received: {type(system_data)}")
                print(f"System data keys: {system_data.keys() if isinstance(system_data, dict) else 'Not a dict'}")


                import subprocess
                try:
                    subprocess.run(['nvidia-smi'], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"nvidia-smi failed: {e}")
                    return

                try:

                    GPUS=GPUtil.getGPUs()
                    if not GPUS:
                        print("no Gpus detected, retrying.......")
                        time.sleep(2)
                        GPUS=GPUtil.getGPUs()
                except Exception as e:
                    print(f"Error getting GPUS: {str(e)}")
                    return
                
                for key in self.redis.scan_iter("gpu:*"):
                    self.redis.delete(key)
                stored_count = 0


                
                system_data =   self.system_metrics.send_stats()
                print("system data recieved")
                gpu_details_by_index ={}
                for gpu in system_data["gpu_details"]:
                    device_index = gpu["device_index"]
                    gpu_details_by_index[device_index]=gpu

              

                for i,gpu in enumerate(GPUS):
                    try:

                            if not hasattr(gpu, 'uuid'):
                                continue
                            
                            gpu_detail = gpu_details_by_index.get(i)
                            if not gpu_detail:
                                print(f"Warning: No matching system metric data for GPU {i}")
                                continue
                            print(f"setting gpu status for {i}")
                            gpu_status ={
                                "index":gpu.id,
                                "id":gpu.uuid,
                                "cuda_cores":gpu_detail["performance"]["cuda_cores_count"],
                                "tflops_fp32":gpu_detail["performance"]["tflops_fp32"],
                                "clock_speed_mhz":gpu_detail["performance"]["clock_speed_mhz"],
                                "memory_clock_mhz":gpu_detail["performance"]["memory_clock_mhz"],
                                "pcie_generation":gpu_detail["pcie"]["generation"],
                                "pcie_lanes":gpu_detail["pcie"]["lanes"],
                                "pcie_rx_mbs":gpu_detail["pcie"]["rx_mbs"],
                                "pcie_tx_mbs":gpu_detail["pcie"]["tx_mbs"],
                                "memoryFree": str(gpu.memoryFree),
                                "memoryTotal": str(gpu.memoryTotal),
                                "memoryUsed": str(gpu.memoryUsed),
                                "bandwidth_gbs":gpu_detail["memory"]["bandwidth_gbs"],
                                "bus_width_bit":gpu_detail["memory"]["bus_width_bit"],
                                "status": "available" if gpu.memoryFree > 1000 else "in_use",
                                "container_id": "",     # Empty string for no container
                                "user_id": "",          # Empty string for no user
                                "allocated_at": ""  # Simple rule
                            }
                            # for field, value in gpu_status.items():
                            #     self.redis.hset(f"gpu:{gpu_id}", field, value)
                            self.redis.hset(f"gpu:{gpu.uuid}",mapping=gpu_status)
                            self.redis.expire(f"gpu:{gpu.uuid}",86400)
                            stored_count += 1

                            
                    except Exception as e:
                        print(f"Error processing GPU {getattr(gpu, 'id', 'unknown')}: {e}")
                        continue


                        

                print(f"Stored {stored_count} out of {len(GPUS)} GPUs")
                return True

            except Exception as e:
                print(f"Error in redis_overlord: {str(e)}")
              

    
    def run_periodic_update(self):#function to run redis overlord very 10mins
        while True:
            self.redis_overlord()
            time.sleep(2000)
    def start_gpu_status_update(self):# Background thread to start the periodic update
        # task = asyncio.create_task(self.run_periodic_update())
        status_update_thread = threading.Thread(target= self.run_periodic_update)   
        status_update_thread.daemon = True #background
        status_update_thread.start()  
        return status_update_thread
        # return task
                
    def get_database(self, index):
        if index<0 or index >15:
            raise ValueError("redis has pre made databases from 0 to 15")
        # Use lock to prevent race conditions       
        with self.gpu_lock:
            if index in RedisManager.database_connections:
                return RedisManager.database_connections[index]
        new_connection = redis.Redis(
                host='localhost',
                port=6379,
                password=redis_love,
                db=index
            )
        new_connection.config_set('notify-keyspace-events', 'Ex') #remember if you are using keyspace event point them to right  db in any process,
        #please remember that in the pubsub the keyevent must be pointing to the correct db number
        RedisManager.database_connections[index]=new_connection
        return new_connection

    async def test_connection(self):
        try:
            self.redis.set('test_key', 'hello GPU monitoring')
            value = self.redis.get('test_key')
            return{
                "status":"success",
                "message":value.decode('utf-8')
            }
        except redis.ConnectionError as e:
            return{
                "status":"error redis from redis.connection block",
                "message":str(e)
                
            }
        except Exception as e:
            return{
                "status":"error from the test connection method block",
                "message":str(e)
            }
   

    async def mark_extracted_gpu(self, gpu_uid:str, container_id:str, user_id:str, ttl:int=3600): 
        """ttl needs to be as per user input, please remember""" 
        try:
            key = f"gpu:{gpu_uid}"
            data = {
                'status':"in_use",
                'allocated_at': datetime.now().isoformat(),
                'docker_container_id':container_id,
                'user_id':user_id,
            }
            data_str = json.dumps(data)
            
            self.redis.hset(key, mapping=data)
            self.redis.expire(key, ttl)

            return{
                "status":"success",
                "message":"data updated in redis db",
                "ttl":f"self destrcuct in {ttl} seconds"
            }
        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }




    async def store_gpu_metrics(self, gpu_uid:str, metrics:dict, ttl:int= 3600):
        
        """Here we will get the status of the gpu allocation"""
       
        try:
            redis_key = f"entry:{gpu_uid}"
            metric_key = f"metrics:{gpu_uid}"

            self.redis.hset(redis_key, mapping=metrics)

            if ttl>0:
                self.redis.expire(redis_key, ttl)
            
            self.redis.hincrby(metric_key, "update count", 1)

            return{
                "status":"success",
                "message":f"metrics for {gpu_uid} has  been stored.",
                "ttl":f"time to destruct in {ttl}seconds"
            }
        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }

    # async def allocate_gpu(self, gpu_id:int, container_id:str):
    #     """here we will check if a gpu is allocated to a 
    #     container or not, but we need to get the id
    #     of container when being created to allocate here in the """
        
    #     try:

    

    