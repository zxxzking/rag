from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash

from app.schemas import Token, TokenData, User, UserCreate, UserInDB, UserUpdate
from core.userManager import UserManager
from config.settings import Settings as AppSettings

SECRET_KEY = AppSettings.JWT_SECRET_KEY
ALGORITHM = AppSettings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = AppSettings.ACCESS_TOKEN_EXPIRE_MINUTES

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")
router = APIRouter()
user_manager = UserManager()
if AppSettings.ENABLE_DEFAULT_ADMIN:
    user_manager.ensure_default_user(
        username=AppSettings.DEFAULT_ADMIN_USERNAME,
        hashed_password=password_hash.hash(AppSettings.DEFAULT_ADMIN_PASSWORD),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def get_user(username: str) -> Optional[UserInDB]:
    user_dict = user_manager.get_user(username)
    if not user_dict:
        return None
    return UserInDB(**user_dict)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception

    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(
        current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )
    return current_user


@router.post("/token", response_model=Token, summary="User login")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )
    return Token(
        message="login success",
        access_token=access_token,
        token_type="bearer",
        username=user.username,
    )


@router.post("/register", response_model=User, summary="User register")
async def register_user(user: UserCreate) -> User:
    if user_manager.get_user(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    created = user_manager.create_user(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        email=user.email,
        full_name=user.full_name,
    )
    return User(**created)


@router.post("/logout", summary="User logout")
async def logout(
        current_user: Annotated[User, Depends(get_current_active_user)]
) -> dict:
    return {
        "message": "logout success",
        "username": current_user.username,
        "logout_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/me", response_model=User, summary="Get current user")
async def read_users_me(
        current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    return current_user


@router.put("/me", response_model=User, summary="Update current user")
async def update_user_me(
        user_update: UserUpdate,
        current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    updated_user = user_manager.update_user(
        username=current_user.username,
        email=user_update.email,
        full_name=user_update.full_name,
    )
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return User(**updated_user)


@router.get("/protected", summary="Protected route example")
async def protected_route(
        current_user: Annotated[User, Depends(get_current_active_user)]
) -> dict:
    return {
        "message": f"Hello {current_user.username}, this is a protected route!",
        "user_info": {
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
        },
        "access_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/all", summary="List users")
async def get_all_users(
        current_user: Annotated[User, Depends(get_current_admin_user)]
) -> dict:
    users = [
        User(**{k: v for k, v in user.items() if k != "hashed_password"})
        for user in user_manager.list_users()
    ]
    return {
        "users": users,
        "total": len(users),
        "requested_by": current_user.username,
    }


@router.delete("/me", summary="Delete current user")
async def delete_user_account(
        current_user: Annotated[User, Depends(get_current_active_user)]
) -> dict:
    deleted = user_manager.delete_user(current_user.username)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {
        "message": "User account deleted successfully",
        "deleted_user": current_user.username,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
