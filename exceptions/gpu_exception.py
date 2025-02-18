class GPUException(Exception):
    def __init__(self, message:str, gpu_uuid:str,):
        
        self.message = message
        self.gpu_uuid = gpu_uuid
        super().__init__(self.format_error())

    def format_error(self):
        if self.gpu_uuid is not None:
            return f"GPU error for {self.gpu_uuid}:{self.message}"
        return f"GPU Exception: {self.message}"
    def __str__(self):
        return self.format_error()
    
class GPUNotAvailable(GPUException):
    def __init__(self,  message: str = "GPU is not available for allocation", gpu_uuid: str=None):
        super().__init__(message, gpu_uuid)

class GPUAllocationError(GPUException):
    def __init__(self, message:str="Failed to allocate GPU", gpu_uuid:str=None):
        super().__init__(message, gpu_uuid)