from fastapi import APIRouter, Response, Request
from services.docker_service import DockerService
from services.firebase_service import FirebaseService
from services.port import PortManager
from services.gpu_manager import GPUManager
from services.redis import RedisManager
from typing import Dict
from schemas.docker import ContainerRequest, ContainerResponse

router = APIRouter(prefix="/docker")
firebase_service = FirebaseService()
docker_service = DockerService(firebase_service)
port_manage= PortManager()
gpu_monitor = GPUManager()
redis_manager = RedisManager()


@router.get('/check')
async def check_docker():
    return await docker_service.check_docker()
@router.post('/run')
async def run_container():
    return await docker_service.run_container()
@router.get('/user/{user_id}/containers')
async def get_user_containers(user_id: str):
    return await firebase_service.get_user_container(user_id)

@router.get('/test/port-status')
async def port_status():
    try:
        status= await port_manage.get_port_status()
        print(f"Port status: {status}")
        return status
    except Exception as e:
        print(f"Error getting port status: {str(e)}")
        return {"status": "error", "message": str(e)}
        
    
        
   

@router.post('/environment/create')
async def creation_of_environment(request: ContainerRequest): #remember the subdomain we are creating it ourselves, 
    return await docker_service.create_user_environment(request) #need to work on subdomin

@router.get('/lookup/{user_id}/{subdomain}')
async def lookup_port(subdomain:str, user_id:str):
    try:
        container_info= await firebase_service.get_container_by_subdomain(subdomain,user_id)
        if container_info:
            return{
                "status":"success",
                "message":container_info
                }
        else:
            return{
                "status":"Failed",
                "message":"Subdomain not found"
                 }
    except Exception as e:
        return{
            "status":"Error",
            "message":str(e)
        }
@router.get('/database')
async def get_database():
    try:
        doc_info = await firebase_service.get_database()
        return doc_info
    except Exception as e:
        return{
            "status":"failed",
            "Message":str(e)
        }
@router.get('/gpu-stats')
async def get_gpu_status():
    try:
        stats =  gpu_monitor.get_gpu_stats()
        if isinstance(stats, list):
            return{
                "status":"success",
                "gpu_count":len(stats),
                "gpus":stats
            }
        else:
            return{
                "status":"error",
                "Message":stats.get('message','unknown errror'),
                "error":stats.get('error')
            }

    except Exception as e:
        return{
            "status":"error",
            "mseeage":"failed to get the gpu Stats",
            "error":str(e)
        }
        
@router.get('/test-redis')
async def test_redis_connection():
    return await redis_manager.test_connection()
# @router.get('/lookup/{subdomain}')
# async def lookup_port(subdomain: str, response: Response):
    try:
        container_info = await firebase_service.get_container_by_subdomain(subdomain)
        print(f"lookup response for {subdomain}:", container_info)
        if container_info["status"] == "success":
            # Add required headers for nginx
             port = str(container_info["port"])
             print(f"Setting port header to: {port}")
             response.headers["X-Container-Port"] = port
           
             return container_info
            
        else:
            response.status_code = 404
            return container_info
    except Exception as e:
        print(f"Error in lookup: {str(e)}")
        response.status_code = 500
        return {"status": "error", "message": str(e)}


@router.get('/lookup/{subdomain}')
async def lookup_port(subdomain: str, response: Response, request: Request):
    print(f"Received lookup request for subdomain: {subdomain}")
    print(f"Request headers: {dict(request.headers)}")
    try:
        container_info = await firebase_service.get_container_by_subdomain(subdomain)
        print(f"Container info: {container_info}")
        if container_info["status"] == "success":
            port = str(container_info["port"])
            print(f"Setting port header to: {port}")
            response.headers["X-Container-Port"] = port
            return container_info
        else:
            response.status_code = 404
            return container_info
    except Exception as e:
        print(f"Error in lookup: {str(e)}")
        response.status_code = 500
        return {"status": "error", "message": str(e)}
    
        
            
            
        
    
        
            
            
       

        
    


#Test endpoints:

# @router.post('/test/jupyter')
# async def test_jupyter_container():
#     try:
#         container_data = await docker_service.create_user_environment(

#         )

@router.post('/test/create-user')
async def create_test_user():
    """Create a test user and return their ID"""
    return await firebase_service.create_test_user()
