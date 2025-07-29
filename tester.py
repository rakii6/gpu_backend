# Add these imports to your authentication_router.py
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Add this function to your authentication_router.py
async def send_reset_email(to_email: str, reset_link: str, user_name: str = "User"):
    """Send password reset email"""
    try:
        smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("EMAIL_PORT", "587"))
        email_user = os.getenv("EMAIL_USER")
        email_password = os.getenv("EMAIL_PASSWORD")
        
        if not email_user or not email_password:
            return {"status": "error", "message": "Email configuration missing"}
        
        message = MimeMultipart("alternative")
        message["Subject"] = "Reset Your IndieGPU Password"
        message["From"] = email_user
        message["To"] = to_email
        
        # Simple HTML email
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background: #110e20; color: #ffffff; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #1A142F; border-radius: 12px; padding: 30px;">
                    <h1 style="color: #00E5FF; text-align: center;">IndieGPU</h1>
                    <h2 style="color: #FFF176;">Reset Your Password</h2>
                    <p>Hi {user_name},</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href="{reset_link}" style="color: #00E5FF;">Reset Password</a></p>
                    <p style="color: #999; font-size: 12px;">This link expires in 1 hour.</p>
                </div>
            </body>
        </html>
        """
        
        message.attach(MimeText(html_content, "html"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_user, email_password)
            server.send_message(message)
        
        return {"status": "success", "message": "Email sent"}
        
    except Exception as e:
        print(f"Email error: {str(e)}")
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}

# Replace your existing reset-password endpoint with this:
@router.post("/reset-password", status_code=200)
async def reset_password(request: ResetPasswordRequest):
    try:
        # Check if user exists
        user = auth.get_user_by_email(request.email)
        
        # Generate reset link (Firebase handles this)
        reset_link = auth.generate_password_reset_link(
            request.email,
            action_code_settings={
                'url': 'https://indiegpu.com/reset-password',  # Your frontend URL
                'handleCodeInApp': False
            }
        )
        
        # Send the email
        email_result = await send_reset_email(
            to_email=request.email,
            reset_link=reset_link,
            user_name=user.display_name or "User"
        )
        
        if email_result["status"] == "success":
            return {
                "status": "success",
                "message": f"Password reset instructions sent to {request.email}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send reset email")
            
    except firebase_admin.exceptions.FirebaseError:
        # Don't reveal if email exists - security best practice
        return {
            "status": "success", 
            "message": f"If an account with {request.email} exists, reset instructions have been sent."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Something went wrong, try again later")

# Add this new Pydantic model
class UpdatePasswordRequest(BaseModel):
    oob_code: str  # The code from Firebase reset link
    new_password: str = Field(..., min_length=6)

# Add this new endpoint for actually updating the password
@router.post("/update-password")
async def update_password(request: UpdatePasswordRequest):
    try:
        # Verify the reset code and get the email
        email = auth.verify_password_reset_code(request.oob_code)
        
        # Update the password
        user = auth.get_user_by_email(email)
        auth.update_user(user.uid, password=request.new_password)
        
        # Optional: Revoke all existing sessions for security
        auth.revoke_refresh_tokens(user.uid)
        
        return {
            "status": "success",
            "message": "Password updated successfully. Please log in with your new password."
        }
        
    except firebase_admin.exceptions.InvalidArgumentError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update password")