from typing import Dict, Optional
from datetime import datetime

class Log_manager:
    is_initialized= False
    operation_logs = {}


    def __init__(self):
        if not Log_manager.is_initialized:
            Log_manager.operation_logs={}
            Log_manager.is_initialized = True


        


    async def create_operation(self,
                               operation_id:str,
                               operation_type:str,
                               user_id:str,
                               details:Dict=None) -> Dict:
        operation ={
            "operation_id":operation_id,
            "type":operation_type,
            "user_id":user_id,
            "status":"started",
            "started_at":datetime.now().isoformat,
            "details":details or {},
            "progress":[],
            "completed_at":None

        }
        Log_manager.operation_logs[operation_id]=operation
        return operation
    
    async def add_progress(self,operation_id:str, message:str, status :str="in progress"):
        """progress for an operation"""

        if operation_id in Log_manager.operation_logs:
            Log_manager.operation_logs[operation_id]["progress"].append({
                "time":datetime.now().isoformat(),
                "message":message,
                "status":status
            })
        Log_manager.operation_logs[operation_id]["status"]=status

    async def complete_operation(self, operation_id:str, status:str = "completed"):
        """Mark an operation as completet"""

        if operation_id in Log_manager.operation_logs:
            Log_manager.operation_logs[operation_id]["status"]=status
            Log_manager.operation_logs[operation_id]["completed_at"]=datetime.now().isoformat()


    async def get_operation_status(self, opertaion_id:str)->Optional[Dict]:
        """get the current status of an opertaion"""
        return Log_manager.operation_logs.get(opertaion_id)





