from threading import Lock
from pynvml import *
import speedtest 


class System_Metrics:

    def __init__(self):
      
        self.hw_info_cache = {}
        self.cache_expiry = 3600  # 1 hour
        self.last_update = 0

        
    async def form_available_packages(self):
        try:
            
            available_gpus = []
            for gpu_key in self.redis.scan_iter("gpu:*"):
                gpu_data =  self.redis.hgetall(gpu_key)

                if gpu_data:
                    status = gpu_data.get(b'status',b'').decode('utf-8')
                    if status == 'available':
                        available_gpus.append(gpu_data)
                
                length_gpus= len(available_gpus)

                return length_gpus
        except Exception as e:
            return{
                "error":str(e)
            }
        
    def send_stats(self):
        try:
            try:
                nvmlInit()
                # Version = nvmlSystemGetDriverVersion()
                deviceCount = nvmlDeviceGetCount()
                
                # RTX 4070 specs
                gpu_specs = {
                    "NVIDIA GeForce RTX 4070": {
                        "cuda_cores": 5888,
                        "boost_clock_mhz": 2475,
                        "fp32_factor": 2,
                        "memory_bandwidth_gbs": 504.2,  # GB/s
                        "memory_bus_width_bit": 192,    # bits
                        "pcie_gen": 4,                  # PCIe generation
                        "pcie_lanes": 16                # Number of PCIe lanes
                    }
                }
                
                GPU_devices = []
                for device_idx in range(deviceCount):
                    handle = nvmlDeviceGetHandleByIndex(device_idx)
                    
                    # Device name
                    device_name = nvmlDeviceGetName(handle)
                    
                    # Use specs for this device (or default to RTX 4070)
                    device_specs = gpu_specs.get(device_name, gpu_specs["NVIDIA GeForce RTX 4070"])
                    
                    # Clock speeds
                    sm_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_SM)
                    mem_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM)
                    clock_mhz = sm_clock if sm_clock > 0 else device_specs["boost_clock_mhz"]
                    
                    # Calculate TFLOPs
                    tflops = (device_specs["cuda_cores"] * (clock_mhz / 1000) * device_specs["fp32_factor"] * 2) / 1000
                    
                    # Utilization rates
                    util = nvmlDeviceGetUtilizationRates(handle)
                    
                    # PCIe throughput (convert to MB/s)
                    tx_bytes = nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_TX_BYTES) / 1024 / 1024
                    rx_bytes = nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_RX_BYTES) / 1024 / 1024
                    
                    # Memory info
                    memory = nvmlDeviceGetMemoryInfo(handle)
                    
                    # PCI info
                    pci_info = nvmlDeviceGetPciInfo(handle)
                    pci_gen = device_specs["pcie_gen"]  # This is not directly available from NVML
                    pci_width = device_specs["pcie_lanes"]  # This is not directly available from NVML
                    
                    gpu_info = {
                        "device_index": device_idx,
                        "name": device_name,
                        "performance": {
                            "cuda_cores_count": device_specs["cuda_cores"],
                            "tflops_fp32": round(tflops, 2),
                            "clock_speed_mhz": clock_mhz,
                            "memory_clock_mhz": mem_clock
                        },
                        "memory": {
                            "total_gb": round(memory.total / (1024**3), 2),
                            "used_gb": round(memory.used / (1024**3), 2),
                            "free_gb": round(memory.free / (1024**3), 2),
                            "bandwidth_gbs": device_specs["memory_bandwidth_gbs"],
                            "bus_width_bit": device_specs["memory_bus_width_bit"]
                        },
                        "utilization": {
                            "gpu_percent": util.gpu,
                            "memory_percent": util.memory
                        },
                        "pcie": {
                            "rx_mbs": round(rx_bytes, 2),
                            "tx_mbs": round(tx_bytes, 2),
                            "bus_id": pci_info.busId,
                            "generation": pci_gen,
                            "lanes": pci_width,
                            "bandwidth_gbs": pci_gen * pci_width  # Approximate PCIe bandwidth (GB/s)
                        }
                    }
                    GPU_devices.append(gpu_info)
                
                nvmlShutdown()
            except NVMLError as error:
                return {"error": str(error)}
            
            try:
                st = speedtest.Speedtest()
                download_speed =  st.download() / 1_000_000
                upload_speed =  st.upload() / 1_000_000
                st.get_servers([])
                ping_result =  st.results.ping

                net_stats={
                    "download_speed": f"{download_speed:.2f} Mbps",
                    "upload_speed":f"{upload_speed:.2f}Mbps",
                    "ping":ping_result
                }

                return {
                    "gpu_count": deviceCount,
                    # "driver_version": Version.decode('utf-8') if isinstance(Version, bytes) else Version,
                    # "net_stats":net_stats,
                    "gpu_details": GPU_devices
                }
            except Exception as e:
                
                return{
                    "error":str(e)
                }               

        except Exception as e:
            return{
                "status":"error",
                "message":str(e)
            }
        



# GPU metrics (implemented!)

# CPU metrics (usage, cores, temperature) PENDING!
# Memory metrics (usage, speed)
# Storage metrics (capacity, read/write speeds)
# Network metrics (bandwidth, latency)


# Resource Allocation Tracking PENDING!
# Track which users are consuming which resources
# Historical usage patterns
# Cost calculation based on resource consumption


# Performance Benchmarking PENDING!
# Run standard benchmarks to grade your hardware
# Compare performance across different container configs
# Generate performance scores for marketing


# Health Monitoring & Alerting PENDING!
# Monitor for overheating or performance degradation
# Detect anomalies in system metrics
# Trigger alerts when predefined thresholds are exceeded


# Reporting & Analytics PENDING!
# Generate usage reports for internal and customer-facing dashboards
# Analyze utilization patterns to optimize pricing
# Predict capacity needs based on growth trends    





                

            

            



        
   

           
 
       
       
        
        
        

        
            
        

        
        

        
       
       
       


       
        











    
   
