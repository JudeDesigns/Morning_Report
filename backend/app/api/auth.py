from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.auth import get_current_user, require_roles
from app.config import settings
from app.store import users as user_store

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_ROLES = {"admin", "accounting", "office", "management", "viewer"}


class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "office"

    @field_validator("email")
    @classmethod
    def norm_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool


def _to_resp(u: dict) -> UserResponse:
    return UserResponse(**{k: u[k] for k in ["id", "email", "name", "role", "is_active"]})


# Only admins can create new users — prevents open registration
@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserCreate,
    _: dict = Depends(require_roles("admin")),
):
    try:
        user = user_store.create_user(
            email=data.email,
            name=data.name.strip(),
            hashed_password=get_password_hash(data.password),
            role=data.role,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _to_resp(user)


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Constant-time comparison via passlib; generic error prevents user enumeration
    user = user_store.get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.get("is_active"):
        raise HTTPException(400, "Account is inactive — contact an administrator")

    token = create_access_token(
        data={"sub": user["id"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer", "user": _to_resp(user)}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return _to_resp(current_user)
