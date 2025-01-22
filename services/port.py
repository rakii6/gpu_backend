from datetime import datetime
class PortManager:
    def __init__(self):
        self.ports = {}
        self.start_range = 8800
        self.end_range = 8900

        self.total_ports = self.end_range-self.start_range 
        self.ports_in_use = 0
        for port in range(self.start_range, self.end_range):
            self.ports[port]={
                'in_use':False,
                'container_id':None,
                'assigned_at':None,
                'user_id':None 
            }
    
    async def get_port_status(self):
        used_ports = 0
        for port in self.ports.values():
            if port['in_use']:
                used_ports+=1
        return{
            "Total ports":self.total_ports,
            "Used ports":used_ports,
            "Available ports":self.total_ports - used_ports
        }
    
    async def assign_ports(self, user_id:str):
        for port_num, port_info in self.ports.items():
            if not port_info['in_use']:
                self.ports[port_num]={
                     'in_use':True,'assigned_at':datetime.now(),'user_id':user_id

                }
                return port_num
        
        raise Exception("No ports available")
    
    def release_port(self, port_number:int):

        if port_number in self.ports:
            self.ports[port_number]={
                'in_use':False,'container_id':None,'assigned_at':None,'user_id':None
            }
            return{True}
        return{False}

        

            

    
    def check_capacity(self):

        remaining_ports = self.total_ports - self.ports_in_use

        if remaining_ports ==0:
            return {
                "status":"Full",
                "message":"Ports are full"
            }
        elif remaining_ports < 10:
            return{
                "status":"Warning",
                "message":"Nearing Full Capacity"
            }
        return{
            "status":"Healthy",
            "message":remaining_ports
        }       
    
    def update_container_id(self, port: int, container_id: str) -> bool:
        """Update container ID for a port after container creation"""
        if port in self.ports:
            self.ports[port]['container_id'] = container_id
            return True
        return False


    def is_port_in_use(self, port):
        pass

    # def assign_port(self):

    #     capacity  = self.check_capacity
    #     if capacity["status"] == "Full":

    #         raise Exception("no ports are available at the moment")
            

    # def release_port(self, port):
    #     pass

    

    


# ports = {
#     8800:{
#         'in_use':False,
#         'container_id':None,
#         'assigned_at':None,  
#     },
#     8801:{
#         'in_use':False,
#         'container_id':None,
#         'assigned_at':None,       
#     },
#     8802:{
#         'in_use':False,
#         'container_id':None,
#         'assigned_at':None,
        
#     },
# }


# we have to implement these too 

# Implement a waiting queue for users
# Send notifications when ports become available
# Implement a timeout system to free up inactive ports
# Auto-scale your port range (though this needs careful management)