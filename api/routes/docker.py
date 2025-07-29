from fastapi import APIRouter, Response, Request, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
import json
from security.authorization_service import AuthorizationService
from typing import Dict
from schemas.docker import ContainerRequest, PaymentRequest, SupportRequest
import GPUtil
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os, httpx

load_dotenv()
TELEGRAM_BOT_TKN = os.getenv("TELEGRAM_BOT_TKN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


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

@router.get('/test-persistence/{user_id}')
async def test_persistence(user_id: str, request: Request):
    docker_service = request.app.state.docker
    return await docker_service.test_persistence(user_id)




@router.post('/payments/create_order')
async def create_order(request: Request, order_creation: dict):
    try:
        print("=== CREATE ORDER DEBUG START ===")
        user_id = request.state.user_id
        print(f"User ID from middleware: {user_id}")
        print(f"Raw order_creation: {order_creation}")
        
        # Check if we can create the objects
        container_request = ContainerRequest(**order_creation['container_request'])
        print(f"Container request created: {container_request}")
        
        payment_request_data = order_creation['payment_request'] 
        print(f"Payment request data: {payment_request_data}")
        
        # Create PaymentRequest object properly
        payment_request = PaymentRequest(**payment_request_data)
        print(f"Payment request created: {payment_request}")
        
        payment_manager = request.app.state.payment_manager
        print(f"Payment manager: {payment_manager}")
        
        result = await payment_manager.create_order(payment_request, container_request)
        print(f"here is the result from the create order :{result}")
        return result
        
    except Exception as e:
        print(f"ERROR in create_order endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    


@router.post('/payments/clear/{order_id}')
async def clear_order_id(request:Request, order_id:str):
    try:
        user_id = request.state.user_id
        payment_manager = request.app.state.payment_manager
        result = await payment_manager.clear_order(order_id,user_id)
        print(f"Here are the results for the payment clear 😉😉{result}")
        return result
    except Exception as e: 
        print(f"Error in the clear trash endpoint {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))





    
@router.post('/environment/create')
async def creation_of_environment(request:Request, creation_data: dict, background_tasks: BackgroundTasks ): #remember the subdomain we are creating it ourselves, 
     try:

        user_id = request.state.user_id #get the user_id from the middleware
        print(f"userId from middleware{user_id}")
        print(f"this is the request {request}")
        print(f"this is the creation data {creation_data}")

        container_request = ContainerRequest(**creation_data['container_request']) #a wrapper
        print(f"this is the the container request for environment create {container_request}")
        
        print("trying to initaliase the payment data and all,...")
        payment_data = creation_data['payment_data']
        print(f"this is the payment data after payment {payment_data}")

        docker_service = request.app.state.docker
        print(f"docker service manager is :{docker_service}")

        gpu_manager = request.app.state.gpu
        print(f"gpu manager is :{gpu_manager}")

        payment_manager = request.app.state.payment_manager
        print(f"payment_manger is: {payment_manager}")

        payment_confirmation = payment_manager.verify_razorpay_signature(payment_data)
        print(f"payment is confirmed {payment_confirmation}")
        # if not payment_confirmation:
        #     payment_manager.payment_failure(payment_data["razorpay_order_id"],"payment failed")
        #     return{
        #         "message":"Payment Failure"
        #     }



        payment_details = await payment_manager.fetch_payment_details(payment_data["razorpay_payment_id"])
        print(f"payment details are :{payment_details}")

        if not payment_confirmation:
            await gpu_manager.unlock_gpus(user_id)
            return{
                "status":"error",
                "message":"Payment Unsuccessfull"
            }
        
        container_request.user_id = user_id
        print("🚀 About to call docker_service.create_user_environment...")
        
        # session_manager = request.app.state.session
        result =await docker_service.create_user_environment(container_request, background_tasks)

        if result["status"] == "success":
            await payment_manager.process_successful_payment(payment_data, result["container_id"],user_id, payment_details )

        
        print(f"✅ Environment creation result: {result}")
            
        return result
     
     except Exception as e:
        print(f"❌ ERROR in creation_of_environment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/sessions/{container_id}/status')
async def get_container_session_status(container_id:str, request:Request):
    session_manager = request.app.state.session_service
    print(f"Handler triggered for container_id: {container_id}")
    return await session_manager.get_session_status(container_id)

@router.post('/support')
async def submit_support_request(support_request: SupportRequest, request: Request):
    """Submit a support request and notify via Telegram"""
    try:
        # Get environment variables
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return {
                "success": False,
                "message": "Telegram notification not configured"
            }

        # Format message for Telegram
        message = (
            f"*New Support Request*\n\n"
            f"*User:* `{support_request.user_id}`\n"
            f"*Support Code:* `{support_request.support_code}`\n"
            f"*Issue Type:* {support_request.issue_type}\n"
        )
        
        if support_request.user_email:
            message += f"📧 *Email:* {support_request.user_email}\n"
            
        message += f"\n📝 *Issue Description:*\n{support_request.issue}"
        
        # Send to Telegram
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(telegram_url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
            
            if response.status_code != 200:
                print(f"Telegram API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": "Failed to send notification"
                }
        
        return {
            "success": True,
            "message": "Support request submitted successfully!",
            "ticketId": support_request.support_code
        }
        
    except Exception as e:
        print(f"Support request error: {str(e)}")
        return {
            "success": False,
            "message": "Failed to submit support request"
        }



#dependency for Authorization, this like checks before a route gets executed
def get_auth_service(request : Request) -> AuthorizationService:
    firebase_service = request.app.state.firebase
    return AuthorizationService(firebase_service)


async def require_container_access(container_id:str, user_id:str, auth_service: AuthorizationService = Depends(get_auth_service)):


    access_result = await auth_service.can_access_container(user_id, container_id)
   

        
    if not access_result["allowed"]:

        if not access_result["reason"]=="container_terminated":
                raise HTTPException(
                        status_code=409, 
                        detail={
                            "status": "error",
                            "reason": "container_terminated",
                            "message": access_result["message"]
                        }
                    )
        elif access_result["reason"]=="container_not_found":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status":"error",
                        "reason":"not_found",
                        "message":access_result["message"]
                    }
                )
        else:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "status":"error",
                        "reason":access_result["reason"],
                        "message":access_result["message"]
                    }
                )
    return True

        

    

@router.post('/stop_container/{container_id}/{user_id}') #be careful using this, its kill the container
async def cleanup_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    try:
        print(f"this is the request {request} from stoppage")
        print(f" this is the contianer{container_id} and user id{user_id}")
        docker_service = request.app.state.docker
        print(f"Docker service retireved : {docker_service is not None}")
        if not docker_service:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Docker service not available"
                }
            )
    
        result = await docker_service.cleanup_container(container_id, user_id)
        print(f"this is the result from the docker stop {result}")
        

    except Exception as stoppage_error:
        import traceback
        error_trace = traceback.format_exc()
        print(f"EXCEPTION in cleanup_container: {str(stoppage_error)}")
        print(f"Traceback: {error_trace}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Container cleanup failed: {str(stoppage_error)}",
                "details": error_trace
            }
        )

# @router.post('/stop_container/{container_id}/{user_id}')
# async def cleanup_container(request: Request, container_id: str, user_id: str, _: bool = Depends(require_container_access)):
#     import traceback
#     import time
    
#     start_time = time.time()
#     print(f"🔥 CLEANUP ENDPOINT HIT at {time.strftime('%Y-%m-%d %H:%M:%S')}")
#     print(f"📦 Container ID: {container_id}")
#     print(f"👤 User ID: {user_id}")
#     print(f"🔐 Authorization passed: {_}")
    
#     try:
#         # Check if docker service exists
#         if not hasattr(request.app.state, 'docker'):
#             print(f"❌ Docker service not found in app state!")
#             return {
#                 "status": "error",
#                 "message": "Docker service not available"
#             }
        
#         docker_service = request.app.state.docker
#         print(f"✅ Docker service found: {type(docker_service)}")
        
#         # Call the cleanup method with enhanced logging
#         print(f"🚀 Calling docker_service.cleanup_container({container_id}, {user_id})")
#         result = await docker_service.cleanup_container(container_id, user_id)
        
#         elapsed_time = time.time() - start_time
#         print(f"⏱️  Cleanup operation completed in {elapsed_time:.2f} seconds")
#         print(f"📋 Cleanup result: {result}")
        
#         # Verify the result structure
#         if not isinstance(result, dict):
#             print(f"⚠️  WARNING: Expected dict result, got {type(result)}")
        
#         if result.get('status') == 'error':
#             print(f"❌ Cleanup reported an error: {result.get('message')}")
#         elif result.get('status') == 'success':
#             print(f"✅ Cleanup reported success: {result.get('message')}")
#         else:
#             print(f"🤔 Unexpected status in result: {result.get('status')}")
        
#         return result
        
#     except Exception as e:
#         elapsed_time = time.time() - start_time
#         print(f"💥 EXCEPTION in cleanup_container endpoint after {elapsed_time:.2f}s:")
#         print(f"❌ Error type: {type(e).__name__}")
#         print(f"❌ Error message: {str(e)}")
#         print(f"📍 Full traceback:")
#         traceback.print_exc()
        
#         return {
#             "status": "error",
#             "message": f"Container cleanup failed: {str(e)}",
#             "error_type": type(e).__name__,
#             "container_id": container_id,
#             "user_id": user_id
#         }

@router.post('/pause_container/{container_id}/{user_id}')
async def pause_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    print(f"=== PAUSE ENDPOINT DEBUG ===")
    print(f"Container ID: {container_id}")
    print(f"User ID: {user_id}")
    print(f"Request user from middleware: {request.state.user_id}")
    docker_service = request.app.state.docker
    return await docker_service.pause_container(container_id, user_id)

@router.post('/restart_container/{container_id}/{user_id}')
async def restart_container(request:Request, container_id:str, user_id:str, _: bool = Depends(require_container_access)):
    docker_service = request.app.state.docker
    return await docker_service.restart_container(container_id, user_id)








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
