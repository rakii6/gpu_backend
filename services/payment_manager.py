import razorpay
from fastapi import Request, HTTPException
import os
from firebase_admin import firestore
from dotenv import load_dotenv
from schemas.docker import PaymentRequest, ContainerRequest, OrderRequest
from services.gpu_manager import GPUManager
from services.firebase_service import FirebaseService
from services.credits_service import CreditsManager
import time
import hmac
import hashlib
import httpx

load_dotenv()



class PaymentManager:
    

    def __init__(self, gpu_manager:GPUManager, firebase_service:FirebaseService, credit_manager:CreditsManager ):
        self.gpu_manager = gpu_manager
        self.firebase_service = firebase_service
        self.credits_manager = credit_manager
        self.db = firebase_service.db
        self.key_id = os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        print(f"Razorpay Key ID: {self.key_id}")
        print(f"Razorpay Key Secret: {'*' * len(self.key_secret) if self.key_secret else 'None'}")
        self.razorpay_client = razorpay.Client(auth=(self.key_id, self.key_secret))

    
    async def create_order(self,request:PaymentRequest, container_request:ContainerRequest):

        
        gpu_lock = False
        
        try:
            # if request.type == 'card':
            #     try:
            #         balance_result =await self.credits_manager.check_sufficient_credits(user_id=request.user_id, required_amount=request.amount)

            #         if balance_result["status"]=="insufficent funds":
            #             print(f"insufficent credits")
            #             return{
            #                 "status":"error",
            #                 "message":"Please add credits"
            #             }
            #         elif balance_result["status"]=="ok":
            #             deduct_result = await self.credits_manager.deduct_credits(user_id=request.user_id ,amount=request.amount, container_id=container_request.container_type, service_details=container_request)
            #             print(f"Deduction happened")
            #             return{
            #                 "status":"success",
            #                 "message":"Creating container"
            #             }
            #     except Exception as e:
            #         import traceback
            #         print(traceback.format_exc())
            #         return{
            #             "status":"error",
            #             "message":str(e)
            #         }
                        

                    

            print(f"Using Razorpay credentials - Key ID: {self.key_id}")
        
        # Test the credentials first
            try:
                test_orders = self.razorpay_client.order.all()
                print("Razorpay auth test successful")
            except Exception as auth_error:
                print(f"Razorpay auth test failed: {auth_error}")


            print(f"GPU Manager type: {type(self.gpu_manager)}")
            print(f"GPU Manager: {self.gpu_manager}")
        
        # If it's still a tuple, fix it:
            if isinstance(self.gpu_manager, tuple):
                print("ERROR: GPU Manager is still a tuple!")
                self.gpu_manager = self.gpu_manager[0]  # Extract from tupl
                

            print(f"🔒 Locking {container_request.gpu_count} GPUs for user {container_request.user_id}")
            gpu_lock_result = await self.gpu_manager.lock_gpus_for_payment(
                user_id=container_request.user_id,
                gpu_count=container_request.gpu_count,
                ttl_minutes=10
            )
            print(f"this is the GPU lock result {gpu_lock_result}")
            if gpu_lock_result['status'] == 'error':
                return gpu_lock_result
            gpu_lock= True

            amount_without_decimals = int(float(request.amount * 100))

            order_data = {
            'amount': amount_without_decimals,
            'currency': request.currency,
            'receipt': f"ORD_{int(time.time())}",  # Your internal receipt ID
            'notes':{
                'user_id': request.user_id,
                'container_type': container_request.container_type,
                'subdomain': container_request.subdomain,
                'gpu_count': str(container_request.gpu_count),
                'duration': str(container_request.duration),
                'service_type': 'gpu_rental',
                'platform': 'indiegpu'
            }
           
        }
            razorpay_order = self.razorpay_client.order.create(data=order_data)
            print(f"Sending order response with amount: {int(request.amount * 100)}")

            await self.store_pending_payment(user_id = request.user_id,razorpay_order = razorpay_order, container_request = container_request, amount= request.amount)

            return {
            'id': razorpay_order['id'],
            'amount': int(request.amount * 100),
            'currency': request.currency,
            'key_id': self.key_id,  # Frontend needs this
            'name': 'IndieGPU',
            'description': f'{container_request.gpu_count} GPU(s) for {container_request.duration} hours',
            'user_id':container_request.user_id,
            
            'theme': {
                'color': '#00E5FF'  # Your neon cyan
            },
            'modal': {
                'ondismiss': 'function(){console.log("Payment cancelled")}'
            }
        }
        except Exception as e:
            print(f"❌ Failed to create Razorpay order: {str(e)}")
            return{
                "status":"error",
                "message":f"failed payment rzaor pay {str(e)}"
            }
        
    async def create_ordinary_order(self,request:OrderRequest):

        
        
        try:
            # if request.type == 'card':
            #     try:
            #         balance_result =await self.credits_manager.check_sufficient_credits(user_id=request.user_id, required_amount=request.amount)

            #         if balance_result["status"]=="insufficent funds":
            #             print(f"insufficent credits")
            #             return{
            #                 "status":"error",
            #                 "message":"Please add credits"
            #             }
            #         elif balance_result["status"]=="ok":
            #             deduct_result = await self.credits_manager.deduct_credits(user_id=request.user_id ,amount=request.amount, container_id=container_request.container_type, service_details=container_request)
            #             print(f"Deduction happened")
            #             return{
            #                 "status":"success",
            #                 "message":"Creating container"
            #             }
            #     except Exception as e:
            #         import traceback
            #         print(traceback.format_exc())
            #         return{
            #             "status":"error",
            #             "message":str(e)
            #         }
                        

                    
            print(f"this is the request hitting the fucntion defition of create ordinatry payment{request}")
            print(f"Using Razorpay credentials - Key ID: {self.key_id}")
        
        # Test the credentials first
            try:
                test_orders = self.razorpay_client.order.all()
                print("Razorpay auth test successful")
            except Exception as auth_error:
                print(f"Razorpay auth test failed: {auth_error}")


           
       
           
            amount_without_decimals = int(float(request.amount * 100))

            order_data = {
            'amount': amount_without_decimals,
            'currency': request.currency,
            'receipt': f"ORD_{int(time.time())}",  # Your internal receipt ID
            'notes':{
                'user_id': request.user_id,
                'order_type': request.order_type,
            }
           
        }
            razorpay_order = self.razorpay_client.order.create(data=order_data)
            print(f"Sending order response with amount: {int(request.amount * 100)}")

            await self.store_payment(user_id = request.user_id,razorpay_order = razorpay_order, order_type = request.order_type, amount= request.amount)
            # this is to stroe pending payment, for normal orders

            return {
            'id': razorpay_order['id'],
            'amount': int(request.amount * 100),
            'currency': request.currency,
            'key_id': self.key_id,  # Frontend needs this
            'name': 'IndieGPU',
            'description': f'creating order for {request.order_type}, for {request.user_id} user',
            'user_id':request.user_id,
            
            'theme': {
                'color': '#00E5FF'  #  neon cyan
            },
            'modal': {
                'ondismiss': 'function(){console.log("Payment cancelled")}'
            }
        }
        except Exception as e:
            print(f"❌ Failed to create Razorpay order: {str(e)}")
            return{
                "status":"error",
                "message":f"failed payment rzaor pay {str(e)}"
            }
        

    async def clear_order(self,razorpay_order_id, user_id):
        
        try:
                if razorpay_order_id:
                    payment_ref = self.db.collection('users').document(user_id).collection('payment_info').document(razorpay_order_id)
                    payment_snapshot = payment_ref.get()
                    if payment_snapshot.exists:
                        payment_ref.delete()
                        print(f"{payment_ref} which was pending and failed, deleted 👌👌")
                    else:
                        print(f"⚠️ Pending payment document not found: {razorpay_order_id}")

                try:
                    unlock_result = await self.gpu_manager.unlock_gpus(user_id)
                    print(f"Gpu unlocked results {unlock_result}")
                except Exception as gpu_error:
                    print(f"gpu unlocking error {gpu_error}")


                    
                return {"Pending payment deleted"}
                            
        except Exception as cleanup_error:
                print(f"❌ Failed to delete pending payment: {cleanup_error}")    
                return None
        
    async def clear_ordinary_order(self,razorpay_order_id, user_id):
        
        try:
                if razorpay_order_id:
                    payment_ref = self.db.collection('users').document(user_id).collection('payment_info').document(razorpay_order_id)
                    payment_snapshot = payment_ref.get()
                    if payment_snapshot.exists:
                        payment_ref.delete()
                        print(f"{payment_ref} which was pending and failed, deleted 👌👌")
                    else:
                        print(f"⚠️ Pending payment document not found: {razorpay_order_id}")
                    
                return {"Pending payment deleted"}
                            
        except Exception as cleanup_error:
                print(f"❌ Failed to delete pending payment: {cleanup_error}")    
                return None
            
        
    async def store_payment(self, user_id:str,razorpay_order:dict,order_type:str,amount:float):
        try:
                payment_data = {
                'razorpay_order_id':razorpay_order['id'],
                'amount':amount,
                'currency':razorpay_order['currency'],
                'status':'pending',
                'created_at':firestore.SERVER_TIMESTAMP,
                'order_details': order_type,
                'payment_method': None,  
                'razorpay_payment_id': None,  
            }
                payement_ref = self.db.collection('users').document(user_id).collection('payment_info').document(f"credit_order_{razorpay_order['id']}")
                payement_ref.set(payment_data)
                stored_doc = payement_ref.get()
                if stored_doc.exists:
                        print("stored doc exisist 👌")
                else:
                        print("stored doc does not exisist 😒")
        except Exception as e:
                print(f"❌ Failed to store pending payment: {str(e)}")
        
        
             
          
                  
    async def store_pending_payment(self,user_id:str,razorpay_order:dict, container_request: ContainerRequest, amount:float ):
        try:
            payment_data = {
                'razorpay_order_id':razorpay_order['id'],
                'amount':amount,
                'currency':razorpay_order['currency'],
                'status':'pending',
                'created_at':firestore.SERVER_TIMESTAMP,
                'service_details': {
                    'container_type': container_request.container_type,
                    'subdomain': container_request.subdomain,
                    'gpu_count': container_request.gpu_count,
                    'duration_hours': container_request.duration,
                },
                'payment_method': None,  
                'razorpay_payment_id': None,  
                'container_id': None,
                'receipt': None
            
            }
            
            payement_ref = self.db.collection('users').document(user_id).collection('payment_info').document(razorpay_order['id'])
            payement_ref.set(payment_data)
            print("Payment data store success 📄📄")

            stored_doc = payement_ref.get()
            if stored_doc.exists:
                print("stored doc exisist 👌")
            else:
                print("stored doc does not exisist 😒")
        except Exception as e:
            print(f"❌ Failed to store pending payment: {str(e)}")


    # async def process_successful_payment(self, payment_data:dict, container_id:str, user_id:str, payment_details:str):
    #     try:
            
        
    #         print(f"this is the container id from process success pay {container_id} and the payemnet data {payment_data} and payment details {payment_details}")
    #         payment_ref = self.db.collection('users').document(user_id).collection('payment_info').document(payment_data["razorpay_order_id"])
    #         info_doc_ref = self.db.collection('users').document(user_id).collection('payment_info').document("_info")
    #         order_id = payment_ref.get()
    #         payment_method = payment_details['method']
    #         payment_method_details = payment_details.get(payment_method)
    #         if order_id.exists:
    #             print(f"order id found: {order_id}")
    #             payment_ref.update({
    #                 'payment_method': payment_method,  
    #                  payment_method:payment_method_details,
    #                 'razorpay_payment_id': payment_details["razorpay_payment_id"],
    #                 'container_id': container_id,
    #                 'receipt': payment_details["receipt"],
    #                 'status':"paid"
    #             })
    #             print("update done")
    #             info_doc_ref.update({ 
    #             "total_count":firestore.Increment(1)
    #                 })
    #             print("increament done")
    #     except Exception as e:
    #         print(f"order id fetcthing failure")
    #         return{
    #             "message":f"{order_id} does not exsists",
    #             "status":str(e)
    #         }
            
    async def process_successful_payment(self, payment_data: dict, container_id: str, user_id: str, payment_details: dict):
        import traceback  # Add this import at the top of your file
        
        try:
            print(f"🔍 Starting payment processing...")
            print(f"📦 Container ID: {container_id}")
            print(f"👤 User ID: {user_id}")
            print(f"💳 Payment Data: {payment_data}")
            print(f"📋 Payment Details: {payment_details}")
            
            # Build document references
            payment_ref = self.db.collection('users').document(user_id).collection('payment_info').document(payment_data["razorpay_order_id"])
            info_doc_ref = self.db.collection('users').document(user_id).collection('payment_info').document("_info")
            
            print(f"📄 Checking if order document exists...")
            order_doc = payment_ref.get()
            
            if not order_doc.exists:
                print(f"❌ Order document does not exist for order_id: {payment_data['razorpay_order_id']}")
                return {
                    "status": "error",
                    "message": f"Order {payment_data['razorpay_order_id']} not found"
                }
            
            print(f"✅ Order document found: {payment_data['razorpay_order_id']}")
            
            # Extract payment method details
            payment_method = payment_details.get('method')
            if not payment_method:
                print(f"❌ No payment method found in payment_details")
                return {
                    "status": "error", 
                    "message": "Payment method not found"
                }
                
            payment_method_details = payment_details.get(payment_method, {})
            
            print(f"💳 Payment method: {payment_method}")
            print(f"🔧 Payment method details: {payment_method_details}")
            
            # Prepare update data
            update_data = {
                'status': 'paid',
                'payment_method': payment_method,
                 payment_method: payment_method_details,
                'razorpay_payment_id': payment_details.get("id"),  # Use .get() for safety
                'container_id': container_id,
                'receipt': payment_details.get("receipt"),
                'completed_at': firestore.SERVER_TIMESTAMP
            }
            
            print(f"📝 Update data prepared: {update_data}")
            
            # Perform the update
            print(f"🔄 Updating payment document...")
            payment_ref.update(update_data)
            print(f"✅ Payment document updated successfully")
            
            # Update the info counter
            print(f"📊 Updating payment counter...")
            info_doc_ref.update({
                "total_count": firestore.Increment(1)
            })
            print(f"✅ Payment counter updated successfully")
            
            return {
                "status": "success",
                "message": "Payment processed successfully",
                "order_id": payment_data["razorpay_order_id"]
            }
            
        except Exception as e:
            # This is the key part - full traceback!
            print(f"💥 EXCEPTION CAUGHT in process_successful_payment:")
            print(f"❌ Error type: {type(e).__name__}")
            print(f"❌ Error message: {str(e)}")
            print(f"📍 Full traceback:")
            traceback.print_exc()  # This prints the full stack trace
            
            return {
                "status": "error",
                "message": f"Payment processing failed: {str(e)}",
                "error_type": type(e).__name__
            }
    async def _find_user_by_order_id(self,order_id: str,user_id:str):
        user_ref = self.db.collection('users').document(user_id)
        payment_ref = self.db.collection('users').document(user_id).collection('payment_info').document(order_id)
            
        if user_ref.exists and payment_ref.exists:
                return True
        else:
                return False

        
            
    # async def handle_payment_failure(self,)



        


    def verify_razorpay_signature(self, payment_data: dict) -> bool:

        """Enhanced signature verification with detailed logging"""
    
      
      
        order_id = payment_data.get('razorpay_order_id')
        payment_id = payment_data.get('razorpay_payment_id') 
        received_signature = payment_data.get('razorpay_signature')

        signature_string = f"{order_id}|{payment_id}"
       
        
        expected_signature = hmac.new(
            self.key_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
       
        
        if len(received_signature) == len(expected_signature):
            for i, (r, e) in enumerate(zip(received_signature, expected_signature)):
                if r != e:
                    print(f"❌ Mismatch at position {i}: received='{r}' expected='{e}'")
                    break
            else:
                print("✅ All characters match!")
        else:
            print(f"❌ Length mismatch: received={len(received_signature)}, expected={len(expected_signature)}")
        
        # Final comparison
        is_valid = hmac.compare_digest(expected_signature, received_signature)
        # payment_details= await self.fetch_payment_details(payment_id)
        print(f"🔐 Signature verification result: {is_valid}")
        
        return is_valid


    
    
    async def fetch_payment_details(self, payment_id: str):
        url = f"https://api.razorpay.com/v1/payments/{payment_id}"
        auth = (self.key_id, self.key_secret)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=auth)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Payment not found")
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch payment details from Razorpay")
        
    # async def get_user_bill_details(self, user_id:str, ):
    #     try:
    #         payment_ref = self.db.collection('users').document(user_id).collection('payment_info')
    #         payment_docs = payment_ref.get()

    #         if not payment_docs.exists:
    #             return{"status":"error",
    #                    "message":"User profile not found"}
    #         payment_data = payment_docs.to_dict()
            
            
            
    #     except Exception as bill_error:


    



    #         return{"status":"success","profile":profile_data,
    #                "user_data":subcollection_data}
    #     except Exception as e:
    #         return{"status":"error from the get user profile except block",
    #                "message":str(e)
    #                }