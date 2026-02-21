from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from ..database import get_session
from ..models import User, Role, Status, Student
from ..auth import verify_password, create_access_token, create_refresh_token
from ..audit import log_action
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    usn: str
    name: str
    personal_email: EmailStr
    semester: int
    department: str
    branch: str
    bot_check: str # Simple answer to "What is 2+2?" or similar

@router.post("/login")
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    session: Session = Depends(get_session)
):
    statement = select(User).where(User.email == login_data.email)
    account = session.exec(statement).first()

    if not account:
        log_action(session, action="LOGIN_FAILED", actor_email=login_data.email,
                   detail="Invalid email", request=request)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if account.lockout_until and account.lockout_until > datetime.utcnow():
        retry_in = int((account.lockout_until - datetime.utcnow()).total_seconds() / 60) + 1
        raise HTTPException(status_code=403, detail=f"Account locked due to multiple failed attempts. Please retry in {retry_in} minutes.")

    if not verify_password(login_data.password, account.password_hash):
        account.failed_attempts += 1
        msg = f"Invalid email or password. Attempt {account.failed_attempts}/4"
        
        if account.failed_attempts >= 4:
            from datetime import timedelta
            account.lockout_until = datetime.utcnow() + timedelta(minutes=10)
            account.failed_attempts = 0 # Reset for next cycle after lockout
            msg = "Too many failed attempts. Account locked for 10 minutes."
        
        session.add(account)
        session.commit()
        
        log_action(session, action="LOGIN_FAILED", actor=account, detail=msg, request=request)
        raise HTTPException(status_code=401, detail=msg)

    # Success
    account.failed_attempts = 0
    account.lockout_until = None
    session.add(account)
    session.commit()

    if account.status == Status.PENDING:
        raise HTTPException(status_code=403, detail="Account pending admin approval.")
    if account.status == Status.SUSPENDED:
        raise HTTPException(status_code=403, detail="Account suspended.")

    access_token = create_access_token(data={
        "sub": str(account.id),
        "email": account.email,
        "role": account.role,
        "status": account.status
    })
    refresh_token_str = create_refresh_token(data={"sub": str(account.id)})

    days_30 = 30 * 24 * 60 * 60
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        max_age=days_30,
        expires=days_30,
        samesite="lax",
        path="/"
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token_str, 
        httponly=True, 
        max_age=days_30,
        expires=days_30,
        samesite="lax",
        path="/"
    )

    log_action(session, action="LOGIN", actor=account,
               detail=f"Successful login as {account.role}", request=request)

    return {
        "success": True,
        "message": "Login successful",
        "data": {
            "user": {
                "id": account.id,
                "email": account.email,
                "role": account.role,
                "status": account.status
            }
        }
    }

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session)
):
    log_action(session, action="LOGOUT", detail="User logged out", request=request)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/") # Changed to root path for simplicity
    return {"success": True, "message": "Logged out successfully"}

@router.post("/register")
async def register_student(
    request: Request,
    data: RegisterRequest,
    session: Session = Depends(get_session)
):
    # 1. Anti-bot check
    if data.bot_check != "4":
        raise HTTPException(status_code=400, detail="Anti-bot check failed. (Hint: 2+2=4)")

    # 2. Check USN uniqueness
    existing_student = session.exec(select(Student).where(Student.usn == data.usn.upper())).first()
    if existing_student:
        raise HTTPException(status_code=400, detail="A student with this USN already exists.")

    # 3. Create University Credentials
    uni_email = f"{data.usn.lower()}@university.edu"
    import secrets
    import string
    raw_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
    
    # Check if university email already exists in User table
    existing_user = session.exec(select(User).where(User.email == uni_email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="This university email is already taken. Please contact admin.")

    # 4. Create User Record
    from ..auth import get_password_hash
    new_user = User(
        email=uni_email,
        password_hash=get_password_hash(raw_password),
        role=Role.STUDENT,
        status=Status.PENDING # Needs admin approval or can be ACTIVE based on policy
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # 5. Create Student Profile
    new_student = Student(
        usn=data.usn.upper(),
        name=data.name,
        semester=data.semester,
        department=data.department,
        branch=data.branch,
        personal_email=data.personal_email,
        user_id=new_user.id
    )
    session.add(new_student)
    session.commit()

    # 6. Simulate Email Sending
    print(f"--- EMAIL SIMULATION ---")
    print(f"TO: {data.personal_email}")
    print(f"SUBJECT: Your University Portal Credentials")
    print(f"Welcome {data.name}! Your university account has been created.")
    print(f"University Email: {uni_email}")
    print(f"Temporary Password: {raw_password}")
    print(f"-------------------------")

    log_action(session, action="STUDENT_REGISTER", actor=new_user,
               detail=f"Student {data.name} ({data.usn}) registered with personal email {data.personal_email}",
               request=request)

    return {
        "success": True, 
        "message": "Registration successful! Your university credentials have been sent to your personal email.",
        "data": {
            "university_email": uni_email,
            "usn": data.usn.upper()
        }
    }
