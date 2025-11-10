from firebase_admin import firestore
from google.cloud import firestore
from typing import Optional

class CreditsManager:
     def __init__(self, db):
          self.db = db


     async def initialize_user_credits(self, user_id: str, initial_amount: float = 0.0):
          """Initialize credit account for new user"""

          try:
                    balance_ref = self.db.collection('users').document(user_id).collection('credits').document('balance')
                    
                    # Check if already exists (prevent duplicate initialization)
                    if balance_ref.get().exists:
                         return {
                              "status": "exists",
                              "message": "Credit account already initialized"
                         }
                    
                    # Create the balance document
                    balance_ref.set({
                         'balance': initial_amount,
                         'currency': 'USD',
                         'created_at': firestore.SERVER_TIMESTAMP,
                         'last_updated': firestore.SERVER_TIMESTAMP,
                         'total_spent': 0.0
                    })
                    
                    print(f"Initialized credit account for user {user_id}")
                    
                    return {
                         "status": "success",
                         "message": "Credit account initialized",
                         "initial_balance": initial_amount
                    }
               
          except Exception as e:
                    print(f"Error initializing credits: {str(e)}")
                    return {"status": "error", "message": str(e)}      

     

    
    
     async def credit_balance_get(self, user_id: str):
          """users/{user_id}/credits/
                                └── balance (document)
                                    ├── balance: 0.0
                                    ├── currency: "USD"
                                    ├── created_at: timestamp
                                    ├── last_updated: timestamp
                                    └── total_spent: 0.0"""
          credit_ref = self.db.collection('users').document(user_id).collection('credits').document('balance')
          credit_doc =  credit_ref.get()

          if not credit_doc.exists:
               return{
                    "status":"not_found",
                    "balance":0.0
               }
          return{
               "status":"success",
               "balance":credit_doc.to_dict().get('balance',0.0),
               "currency":credit_doc.to_dict().get('currency','$')
          }
     
     async def check_sufficient_credits(self, user_id:str, required_amount:str):
          
          
          """Purpose: Verify user has enough credits before starting container
            Logic:

                Get current balance using get_credit_balance()
                Compare: balance >= required_amount
                Return boolean + details            
          """
          credit_data =  await self.credit_balance_get(user_id)

          if credit_data["status"]!= "success":
               return{
                    "status":"error",
                    "message":"User document not found",
                    "can_proceed":False
               }
          balance = credit_data["balance"]

          if required_amount>balance:
               return{
                    "status":"insufficent funds",
                    "message":f"You have less funds in your balance : ${balance}",
                    "can_proceed":False
               }
          else :
               return{
                    "status": "ok",
                    "message": f"Sufficient balance ({balance}) for request of {required_amount}.",
                    "can_proceed": True
               }
          

     async def deduct_credits(self,user_id: str, amount: float,  metadata:dict):
          """Purpose: Deduct credits when container is created successfully
                Logic:

                Use Firestore Transaction (CRITICAL for preventing race conditions)
                Read current balance
                Check if balance >= amount
                If yes: Decrement balance, log transaction
                If no: Rollback, return error"""
          try:
          
               balance_ref = self.db.collection('users').document(user_id).collection('credits').document('balance')
               transaction_ref = self.db.collection('users').document(user_id).collection('credits').document('balance').collection('transactions').document()


               transaction = self.db.transaction()

               @firestore.transactional
               def deduction_operation(transaction,balance_ref,amount,transaction_ref):
                    snapshot = balance_ref.get(transaction=transaction)

                    if not snapshot.exists:
                         raise ValueError("Balance Document not found")
                    data = snapshot.to_dict()
                    current_balance = data.get("balance",0.0)
                    total_spent = data.get('total_spent', 0.0)

                    if current_balance < amount:
                         raise ValueError("insuffcient Balance, please Pay")
                    new_balance=current_balance-amount
                    new_total_spent = total_spent+amount



                    transaction.update(balance_ref,{
                         "balance":new_balance,
                         "total_spent":new_total_spent,
                         "last_updated":firestore.SERVER_TIMESTAMP
                    })
                    # txn_ref = transaction_doc.document() 
                    transaction.set(transaction_ref,{
                         "type": "deduction",
                         "amount": amount,
                         "timestamp": firestore.SERVER_TIMESTAMP,
                         "metadata":metadata

                    })

                    return new_balance
               
               new_balance = deduction_operation(transaction,balance_ref, amount, transaction_ref)

              
               return{
                    "status":"success",
                    "amount_deducted":amount,
                    "balance":new_balance
               }
               
          except ValueError as e:
               return{
                     "status": "error",
               "message": str(e)
               }
          except Exception as e:
              print(f"Error deducting credits: {str(e)}")
              return {
            "status": "error",
            "message": f"Failed to deduct credits: {str(e)}"
        }
               

      
     async def add_credits(self,user_id: str, amount: float, source: str, metadata: dict = None):
          """Purpose: Add credits to user account (from payment, referral, admin grant)
               Logic:

               Use Firestore transaction (same reason as deduct)
               Increment balance by amount
               Log transaction with source

               Sources:

               "razorpay_payment" - User bought credits
               "free_trial" - Initial signup bonus
               "referral" - Friend referral bonus
               "admin_grant" - Manual credit by you
               "refund" - Container failure refund
               users/{user_id}/credits/transactions/{transaction_id}
                                                       ├── type: "addition"
                                                       ├── amount: 10.00
                                                       ├── source: "razorpay_payment"
                                                       ├── timestamp: timestamp
                                                       ├── metadata: {
                                                       │     razorpay_payment_id: "pay_xyz",
                                                       │     razorpay_order_id: "order_abc"
                                                       │   }"""
          try:
               # Validate source
               valid_sources = ['razorpay_payment', 'free_trial', 'referral', 'refund', 'admin_grant']
               if source not in valid_sources:
                    return {
                         "status": "error",
                         "message": f"Invalid source. Must be one of: {valid_sources}"
                    }
               
               # Reference to balance document
               balance_ref = self.db.collection('users').document(user_id).collection('credits').document('balance')
               transaction_ref = self.db.collection('users').document(user_id).collection('credits').document('balance').collection('transactions').document()
               transaction_data = {
                    'type': 'addition',
                    'amount': amount,
                    'source': source,
                    'timestamp': firestore.SERVER_TIMESTAMP
               }
               
               # Add source-specific metadata
               if source == 'razorpay_payment':
                    transaction_data['metadata'] = {
                         'razorpay_payment_id': metadata.get('razorpay_payment_id'),
                         'razorpay_order_id': metadata.get('razorpay_order_id'),
                         'payment_method': metadata.get('payment_method', 'card')
                    }
               
               elif source == 'free_trial':
                    transaction_data['metadata'] = {
                         'reason': 'New user signup bonus',
                         'expires_at': metadata.get('expires_at') if metadata else None  # Optional: credit expiry
                    }
               
               elif source == 'referral':
                    transaction_data['metadata'] = {
                         'referred_by': metadata.get('referred_by'),  # User ID who referred
                         'referral_code': metadata.get('referral_code'),
                         'reason': metadata.get('reason', 'Referral bonus')
                    }
               
               elif source == 'refund':
                    transaction_data['metadata'] = {
                         'original_container_id': metadata.get('container_id'),
                         'reason': metadata.get('reason', 'Container failure'),
                         'original_transaction_id': metadata.get('original_transaction_id')
                    }
               
               elif source == 'admin_grant':
                    transaction_data['metadata'] = {
                         'admin_id': metadata.get('admin_id'),
                         'reason': metadata.get('reason', 'Manual credit grant'),
                         'notes': metadata.get('notes')
                    }

               
               # Create transaction
               transaction = self.db.transaction()
               
               @firestore.transactional
               def add_in_transaction(transaction, balance_ref, amount, transaction_ref,transaction_data):
                    # Read current balance
                    snapshot = balance_ref.get(transaction=transaction)
                    
                    if snapshot.exists:
                         # Update existing balance
                         current_balance = snapshot.to_dict().get('balance', 0.0)
                         new_balance = current_balance + amount
                         
                         transaction.update(balance_ref, {
                              'balance': new_balance,
                              'last_updated': firestore.SERVER_TIMESTAMP,
                              
                         })
                    else:
                         # Create new balance document (shouldn't happen if initialize_user_credits ran)
                         new_balance = amount
                         transaction.set(balance_ref, {
                              'balance': new_balance,
                              'currency': 'USD',
                              'created_at': firestore.SERVER_TIMESTAMP,
                              'last_updated': firestore.SERVER_TIMESTAMP,
                              'total_spent': 0.0
                         })
                    
                    transaction_data['balance_after']=new_balance
                    transaction.set(transaction_ref, transaction_data)
                    return new_balance
               
               # Execute transaction
               new_balance = add_in_transaction(transaction, balance_ref, amount,transaction_ref, transaction_data)
               
               # Build transaction log based on source
               
               
               
               print(f"✅ Added ${amount:.2f} credits to user {user_id} via {source}")
               
               return {
                    "status": "success",
                    "amount_added": amount,
                    "source": source,
                    "new_balance": new_balance
               }
               
          except Exception as e:
               print(f"❌ Error adding credits: {str(e)}")
               return {
                    "status": "error",
                    "message": f"Failed to add credits: {str(e)}"
               }
     

          

     async def get_transaction_history(self, user_id:str, limit:int=50):
          """Purpose: Show user their credit usage history
               Logic:

               Query users/{user_id}/credits/transactions
               Order by timestamp descending
               Limit results
               Return formatted list"""
          try:
          
               transactions_ref = self.db.collection('users').document(user_id).collection('credits').collection('transactions')
               query = transactions_ref.order_by('timestamp').limit_to_last(limit)
               results = query.stream()
               print(f"dude here are the results of the query {results}")

               history = []
               for doc in results:
                    data = doc.to_dict()

                    history.append({
                         'id':doc.id,
                         'type':data.get('type'),
                         "amount":data.get('amount'),
                         "source":data.get('source'),
                         "timestamp":data.get('timestamp'),
                         "metadata":data.get('metadata')
                    })

               return{
                    "status":"success",
                    "count":len(history),
                    "message":"Users transaction history"
               }
          except Exception as e:
               print(f"errror in fetching the users transaction history{str(e)}")
               import traceback
               str_trace=traceback.print_exc()
               print(str_trace)
               return{
                    "status": "error",
                    "message": f"Failed to fetch transactions: {str(e)}"
               }
     
     async def admin_add_credits(self,secret_key:str,user_id:str,credits:float,source='admin_grant'):
          try:
               if secret_key =='IloveYou':
                    result=await self.add_credits(user_id=user_id, amount=credits, source= source)
                    if result['status'] == 'success':
                         return {
                              "status": "success",
                              "message": f"${credits} added to user {user_id}",
                              "new_balance": result['new_balance']
                         }
                    else:
                         return result
               else:
                    return{
                         "status":"error",
                         "message":"YOU ARE NOT THE ADMIN BRUH!!"
                    }
               
          except Exception as e:
               print(f"error in admin grant {str(e)}")
               import traceback
               traceback.print_exc()
               return{
                    "status":"error",
                    "message":f"error in admin grant {str(e)}"
               }




     def calculate_cost(self, container_request) -> float:
          """Calculate cost based on GPU count and duration"""
    
          # pricing table
          hourly_rates = {
               1: 0.20,
               2: 0.19,   # Per GPU rate (slight discount)
               4: 0.18,
               6: 0.175,
               8: 0.17
          }
          
          gpu_count = container_request.gpu_count
          duration = container_request.duration
          
          # Get rate per GPU (default to $0.20 if not in table)
          rate_per_gpu = hourly_rates.get(gpu_count, 0.20)
          
          # Total = rate_per_gpu × number_of_gpus × hours
          total_cost = rate_per_gpu * gpu_count * duration
          
          # Round to 2 decimal places
          return round(total_cost, 2)
