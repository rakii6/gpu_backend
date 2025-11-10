from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from schemas.docker import OrderRequest, CreateContainer_Credit, ContainerRequest
from pydantic import BaseModel
from firebase_admin import firestore

router = APIRouter(prefix="/credits", tags=["Credits"])

@router.post('/add_credits_order')
async def addition_credit_order(request: Request):

    try:
        print(f"this is the credit order request {request}")
        data = await request.json()
        
        order_data = OrderRequest(**data["orderRequest"])
        print(f"this is the credit order request after json {data}")

        user_id=request.state.user_id
        credits_manager = request.app.state.credits_manager
        payment_manager = request.app.state.payment_manager

        payment_order_confirmation = await payment_manager.create_ordinary_order(order_data)
        # we have to see what the payemnet data strccutre is like in the payment_mangerfile
        print(f"this is the result of payment confirmation{payment_order_confirmation}")

        return payment_order_confirmation
      

        # credit_addition_result = await credits_manager.add_credits(user_id,amount,source)
        # print(f"this is the credit add resutl {credit_addition_result}")

        # if credit_addition_result["status"]=="success":
        #     return{
        #         "status":"success",
        #         "message":f"Your credit of ${amount} has been added successfully!"
        #     }
    except Exception as e:
        import traceback
        strace_bck_str = traceback.format_exc()
        print(strace_bck_str)
        return{
            "status":"Error",
            "message":str(e)

        }
    
@router.post('/add_credits')
async def add_credits(request:Request):
    print(f" this{request}")
    try:
      
        user_id = request.state.user_id
        data = await request.json()
        print(f"🔍 RAW DATA RECEIVED: {data}")
        print(f"🔍 DATA KEYS: {list(data.keys())}")

        paymentData=data.get("paymentData") 
        orderRequest = data.get("orderRequest")
        print(f"this is teh payment request {paymentData} and order request {orderRequest}")
        if not paymentData or not orderRequest:
            return {"status": "error", "message": "Missing paymentData or orderRequest"}
        
        print(f"recieved payment data {paymentData} & order request {orderRequest}")
        
        payment_mananger = request.app.state.payment_manager
        payment_confirmation = payment_mananger.verify_razorpay_signature(paymentData)

        print(f"this is the payment confirmation{payment_confirmation}")

        credits_manager = request.app.state.credits_manager


        credit_addition_result = await credits_manager.add_credits(user_id=user_id, amount=orderRequest['amount'],source=orderRequest['source'],  metadata={
        'razorpay_payment_id': paymentData['razorpay_payment_id'],
        'razorpay_order_id': paymentData['razorpay_order_id'],
        'payment_method': 'card'
    })
        print(f"this is the credit add resutl {credit_addition_result}")
        return credit_addition_result       
    except Exception as e:
        import traceback
        traceback_str = traceback.print_exc()
        print(traceback_str)
        return{
            "status":"error",
            "message":str(e)
        }


@router.post('/deduct_credits')
async def deduct_credits(data:CreateContainer_Credit,request:Request):
    print(f" this{request} request and this is the {data} data")
    try:
      
        user_id = request.state.user_id
        firebase = request.app.state.firebase
        docker = request.app.state.docker
        credits_manager = request.app.state.credits_manager
        gpu_manager = request.app.state.gpu
   
        sufficient_credits_result = await credits_manager.check_sufficient_credits(user_id,data.amount)
        
        if not sufficient_credits_result["status"]:
            return JSONResponse(
                status_code=402,
                content={
                    "error":"Insufficient credits",
                }
            )
        
           

        
        if isinstance(gpu_manager, tuple):
                print("ERROR: GPU Manager is still a tuple!")
                gpu_manager = gpu_manager[0]

       
        gpu_lock = await gpu_manager.lock_gpus_for_payment(user_id=user_id,
                gpu_count=data.gpu_count,
                ttl_minutes=10)
        if gpu_lock['status'] == 'error' or gpu_lock['status']!='success':
                return gpu_lock
        deduct_result = await credits_manager.deduct_credits(user_id, data.amount,data.model_dump())
        container_request = ContainerRequest(
              user_id=user_id,
            container_type= data.container_type,
            subdomain=data.subdomain,
            gpu_count=data.gpu_count,
            duration=data.duration
        )
        if deduct_result["status"] != "success":
        # Unlock GPUs if deduction failed
            await gpu_manager.unlock_gpus(user_id)
            return JSONResponse(
            status_code=500,
            content={"error": "Credit deduction failed"}
            )
        
        if deduct_result["status"]=="success":
            
            docker_container_creation = await docker.create_user_environment(container_request)
            print(f"✅ Environment creation result: {docker_container_creation}")
            
        return docker_container_creation

              
    except Exception as e:
        import traceback
        traceback_str = traceback.print_exc()
        print(traceback_str)
        await credits_manager.add_credits(user_id, data.amount, "refund")
        await gpu_manager.unlock_gpus(user_id)
        return{
            "status":"error",
            "message":str(e)
        }

    

#  const orderRequest = {
#       amount:amount,
#       currency:"USD",
#       user_id:user_id,
#       order_type:"Credit addition"
#     }
