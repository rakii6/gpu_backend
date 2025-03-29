from fastapi import APIRouter, Response, Request, BackgroundTasks, Depends, HTTPException
from security.authorization_service import AuthorizationService
from typing import Dict
from schemas.docker import ContainerRequest
import GPUtil
from datetime import datetime
import pytz

router = APIRouter(prefix="/docker")
# firebase_service = FirebaseService()
# docker_service = DockerService(firebase_service)
# port_manage= PortManager()
# gpu_monitor = GPUManager()
# redis_manager = RedisManager()

@router.get('/test')
async def test_endpoint():
    print("Test endpoint hit!")
    return {"message": "Test successful"}

@router.get('/check')
async def check_docker(request: Request):
    docker_service = request.app.state.docker
    return await docker_service.check_docker()

@router.post('/run')
async def run_container(request: Request):
    docker_service = request.app.state.docker
    return await docker_service.run_container()

@router.get('/user/{user_id}/containers')
async def get_user_containers(user_id: str,request:Request):
    firebase_service = request.app.state.firebase
    return await firebase_service.get_user_container(user_id)


@router.post('/environment/create')
async def creation_of_environment(request:Request,container_request: ContainerRequest,  background_tasks: BackgroundTasks ): #remember the subdomain we are creating it ourselves, 
    docker_service = request.app.state.docker
    # session_manager = request.app.state.session
    return await docker_service.create_user_environment(container_request, background_tasks)
@router.post('sessions/{container_id}/status')
async def get_container_session_status(container_id:str, request:Request):
    session_manager = request.app.state.session_service
    return await session_manager.get_session_status(container_id)



#dependency for Authorization, this like checks before a route gets executed
def get_auth_service(request : Request) -> AuthorizationService:
    firebase_service = request.app.state.firebase
    return AuthorizationService(firebase_service)


async def require_container_access(container_id:str, user_id:str, auth_service: AuthorizationService = Depends(get_auth_service)):
    if not await auth_service.can_access_container(user_id, container_id):
        raise HTTPException(status_code=403, detail="Access Denied")
    return True



    

@router.post('/stop_container/{container_id}/{user_id}')
async def cleanup_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    docker_service = request.app.state.docker
    return await docker_service.cleanup_container(container_id, user_id)

@router.post('/pause_container/{container_id}/{user_id}')
async def pause_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    docker_service = request.app.state.docker
    return await docker_service.pause_container(container_id, user_id)
@router.post('/restart_container/{container_id}/{user_id}')
async def restart_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    docker_service = request.app.state.docker
    return await docker_service.restart_container(container_id, user_id)

@router.get('/lookup/{user_id}/{subdomain}')
async def lookup_port(subdomain:str, user_id:str, request:Request):
    try:
        firebase_service = request.app.state.firebase
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






@router.get('/sessions/active')
async def get_active_sessions(request: Request):
    """Get all active sessions"""
    session_manager = request.app.state.session_service
    active_sessions = []
    
    for key in session_manager.redis.scan_iter("session:*:*"):
        session_key = key.decode('utf-8')
        # Parse out user_id and container_id from the key
        parts = session_key.split(':')
        if len(parts) == 3:  # Format is "session:user_id:container_id"
            user_id = parts[1]
            container_id = parts[2]
            
            session_data = session_manager.redis.hgetall(key)
            if session_data:
                session_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in session_data.items()}
                
                # Calculate if session is still active
                try:
                    end_time = datetime.fromisoformat(session_data.get('end_time', ''))
                    ist = pytz.timezone('Asia/Kolkata')
                    current_time = datetime.now(ist)
                    is_active = current_time < end_time
                    
                    if is_active:
                        active_sessions.append({
                            "container_id": container_id,
                            "user_id": user_id,
                            "start_time": session_data.get('start_time'),
                            "end_time": session_data.get('end_time'),
                            "duration_hours": session_data.get('duration_hours'),
                            "status": "active"
                        })
                except Exception as e:
                    print(f"Error processing session {session_key}: {str(e)}")
    
    return {"active_sessions": active_sessions}





@router.post('/session/{container_id}/cleanup')
async def cleanup_session(container_id: str, request: Request):
    session_manager = request.app.state.session_service
    return await session_manager.cleanup_expired_session(container_id)

@router.get('/database')
async def get_database(request:Request):
    try:
        firebase_service = request.app.state.firebase
        doc_info = await firebase_service.get_database()
        return doc_info
    except Exception as e:
        return{
            "status":"failed",
            "Message":str(e)
        }
@router.get('/gpu/status')
async def get_gpu_status(request: Request):
    """Get current GPU allocation status"""
    gpu_manager = request.app.state.gpu
    all_gpus = GPUtil.getGPUs()
    gpu_states = []

    for gpu in all_gpus:
        state = await gpu_manager._get_gpu_state(gpu.uuid)
        gpu_states.append({
            "uuid": gpu.uuid,
            "status": state.get('status', 'available'),
            "container_id": state.get('container_id'),
            "user_id": state.get('user_id'),
            "allocated_at": state.get('allocated_at'),
            "memory_total": gpu.memoryTotal,
            "memory_free": gpu.memoryFree
        })

    return {
        "total_gpus": len(all_gpus),
        "gpu_states": gpu_states
    }
        
@router.get('/test-redis')
async def test_redis_connection(request:Request):
    redis_manager= request.app.state.redis
    return await redis_manager.test_connection()



@router.get('/lookup/{subdomain}')
async def lookup_port(subdomain: str, response: Response, request: Request):
    print(f"Received lookup request for subdomain: {subdomain}")
    print(f"Request headers: {dict(request.headers)}")
    try:
        firebase_service = request.app.state.firebase
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
  
@router.post('/test/create-user')
async def create_test_user(request:Request):
    """Create a test user and return their ID"""
    firebase_service = request.app.state.firebase
    return await firebase_service.create_test_user()
# Add this to your docker_router.py file

@router.get('/containers/resources')
async def get_container_resources(request: Request):
    """Get resource usage stats for all running containers"""
    docker_service = request.app.state.docker
    stats = await docker_service.monitor_container_resources()
    
    # Calculate system-wide usage
    total_containers = len(stats)
    if total_containers > 0:
        total_mem_used = sum(s['memory_usage_gb'] for s in stats)
        total_mem_limit = sum(s['memory_limit_gb'] for s in stats)
        avg_cpu_percent = sum(s['cpu_usage_percent'] for s in stats) / total_containers
        
        system_stats = {
            "total_containers": total_containers,
            "total_memory_used_gb": round(total_mem_used, 2),
            "total_memory_allocated_gb": round(total_mem_limit, 2),
            "memory_utilization_percent": round((total_mem_used / total_mem_limit * 100) if total_mem_limit > 0 else 0, 2),
            "avg_cpu_utilization_percent": round(avg_cpu_percent, 2)
        }
    else:
        system_stats = {
            "total_containers": 0,
            "total_memory_used_gb": 0,
            "total_memory_allocated_gb": 0,
            "memory_utilization_percent": 0,
            "avg_cpu_utilization_percent": 0
        }
    
    return {
        "status": "success",
        "system_stats": system_stats,
        "container_stats": stats
    }
