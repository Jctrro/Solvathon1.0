import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from jose import JWTError, jwt, ExpiredSignatureError
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select
from .database import get_session
from .models import User, Role
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

SECRET_KEY = os.getenv("JWT_SECRET", "your-super-secret-access-key-min-32-chars")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Extreme priority fix: Set default to 30 days to avoid any expiry issues
        expire = datetime.now(timezone.utc) + timedelta(days=30)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        print("TOKEN ERROR: Token has expired")
        return None
    except JWTError as e:
        print(f"TOKEN ERROR: JWT error: {str(e)}")
        return None
    except Exception as e:
        print(f"TOKEN ERROR: Unexpected error: {str(e)}")
        return None

def get_current_user(request: Request, session: Session = Depends(get_session)):
    token = request.cookies.get("access_token")
    if not token:
        print(f"AUTH ERROR: No access_token found. Cookies available: {request.cookies.keys()}")
        # Log headers too for extreme debugging
        print(f"DEBUG HEADERS: {dict(request.headers)}")
        raise HTTPException(status_code=401, detail="Not authenticated - Missing Cookie")
    
    payload = decode_token(token)
    if not payload:
        print(f"AUTH ERROR: Token decoding failed for cookie: {token[:10]}...")
        raise HTTPException(status_code=401, detail="Session expired or invalid token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user

def check_role(allowed_roles: List[Role]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker
