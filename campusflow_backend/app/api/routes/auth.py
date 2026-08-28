"""Authentication routes — login and current-user introspection."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_current_user, get_user_repo
from app.core.errors import NotAuthenticated, NotFound
from app.core.security import create_access_token, verify_password
from app.repositories.repositories import UserRepository
from app.schemas import CurrentUser, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, users: UserRepository = Depends(get_user_repo)):
    user = users.by_username(payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise NotAuthenticated("invalid username or password")
    if user.status != "Active":
        raise NotAuthenticated("account is not active")
    roles = users.roles_for(user.id)
    token = create_access_token(subject=str(user.id), roles=roles)
    return TokenResponse(access_token=token, roles=roles)


@router.get("/me", response_model=CurrentUser)
def me(auth: AuthContext = Depends(get_current_user),
       users: UserRepository = Depends(get_user_repo)):
    user = users.by_id(auth.user_id)
    if user is None:
        raise NotFound("user not found")
    return CurrentUser(
        id=user.id, username=user.username, email=user.email,
        first_name=user.first_name, last_name=user.last_name,
        roles=auth.roles,
    )
