from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
import GPUtil
import asyncio
router = APIRouter()

@router.get('/')
async def root():
    try:
        return{"Message":"Hello World :D",
               "Description 1":"Thanks for landing here, just a student, trying to build and design something for everyone to use."}
    except Exception as e:
        print(f"error in root endpoint: {str(e)}")
        return{"statut":"error",
               "message":str(e)}

# @router.get('/{item}')
# async def item_name(item:str):
#     return {"Message":item}
@router.get('/get-container-of-user/{user_id}')
async def get_user_containers(user_id, request:Request):
    firebase_service=request.app.state.firebase
    return await firebase_service.get_users_containers(user_id)
@router.websocket('/ws/gpu-simple')
async def websocket_gpu_simple(websocket:WebSocket):
    await websocket.accept()

    try:
        while True:
            all_gpus = GPUtil.getGPUs()
            gpu_list = []

            for gpu in all_gpus:
                gpu_states = {
                    "id": gpu.id,  # GPU index (e.g., 0, 1, ...)
                    "uuid": gpu.uuid,
                    "memory_free": gpu.memoryFree,
                    "memory_total": gpu.memoryTotal,
                    "memory_used": gpu.memoryUsed,
                    "load": gpu.load,
                    "temperature": gpu.temperature
                }
                gpu_list.append(gpu_states)
            await websocket.send_json({"gpu_states":gpu_list})
            await asyncio.sleep(4)
    except WebSocketDisconnect:
        print("web socket disconnect Brother.")    
    except Exception as e:
        print(f"Error in Websocket:{str(e)}")
        


@router.get('/send_status')
async def get_stats(request:Request):
    system_metrics = request.app.state.system_metrics
    print("hitting the status api")
    return await system_metrics.send_stats()
    
