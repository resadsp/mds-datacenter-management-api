"""Auth endpointi: login, current user i administracija korisnika."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.audit import log_action
from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    require_roles,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])


def _normalize_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def purge_refresh_tokens(db: Session) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(models.RefreshToken)
        .filter(
            (models.RefreshToken.expires_at < now)
            | (
                models.RefreshToken.revoked_at.is_not(None)
                & (models.RefreshToken.revoked_at < now - timedelta(days=30))
            )
        )
        .delete(synchronize_session=False)
    )
    return rows


def _issue_tokens_for_credentials(
    db: Session,
    username: str,
    password: str,
) -> schemas.Token:
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )
    refresh_token, jti, refresh_expires_at = create_refresh_token(user.username, user.role)
    purge_refresh_tokens(db)
    db.add(
        models.RefreshToken(
            jti=jti,
            username=user.username,
            expires_at=_normalize_utc_naive(refresh_expires_at),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    return schemas.Token(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


@router.post(
    "/token",
    response_model=schemas.Token,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    return _issue_tokens_for_credentials(db, form_data.username, form_data.password)


@router.post(
    "/login",
    response_model=schemas.Token,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
async def login(
    request: Request,
    payload: object | None = Body(default=None),
    db: Session = Depends(get_db),
):
    resolved_username = None
    resolved_password = None

    if isinstance(payload, dict):
        resolved_username = payload.get("username")
        resolved_password = payload.get("password")
    elif isinstance(payload, (bytes, bytearray)):
        try:
            parsed = parse_qs(payload.decode("utf-8"))
            resolved_username = parsed.get("username", [None])[0]
            resolved_password = parsed.get("password", [None])[0]
        except Exception:
            pass

    if not resolved_username or not resolved_password:
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                raw = await request.json()
                resolved_username = resolved_username or raw.get("username")
                resolved_password = resolved_password or raw.get("password")
            elif "application/x-www-form-urlencoded" in content_type:
                form_raw = (await request.body()).decode("utf-8")
                parsed = parse_qs(form_raw)
                resolved_username = resolved_username or (parsed.get("username", [None])[0])
                resolved_password = resolved_password or (parsed.get("password", [None])[0])
        except Exception:
            pass

    if not resolved_username or not resolved_password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    return _issue_tokens_for_credentials(db, resolved_username, resolved_password)


@router.post(
    "/refresh",
    response_model=schemas.Token,
    responses={401: {"model": schemas.ErrorResponse}},
)
def refresh_tokens(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    purge_refresh_tokens(db)
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")

    username = claims.get("sub")
    jti = claims.get("jti")
    if not username or not jti:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_row = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.jti == jti, models.RefreshToken.username == username)
        .first()
    )
    now = datetime.utcnow()
    if (
        token_row is None
        or token_row.revoked_at is not None
        or _normalize_utc_naive(token_row.expires_at) < now
    ):
        raise HTTPException(status_code=401, detail="Refresh token is expired or revoked")

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_row.revoked_at = now
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(user.username, user.role)
    db.add(
        models.RefreshToken(
            jti=new_jti,
            username=user.username,
            expires_at=_normalize_utc_naive(new_expires_at),
            created_at=now,
        )
    )

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    db.commit()

    return schemas.Token(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=new_refresh_token,
        refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


@router.post(
    "/logout",
    response_model=schemas.MessageResponse,
    responses={401: {"model": schemas.ErrorResponse}},
)
def logout(payload: schemas.LogoutRequest, db: Session = Depends(get_db)):
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")

    username = claims.get("sub")
    jti = claims.get("jti")
    if not username or not jti:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_row = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.jti == jti, models.RefreshToken.username == username)
        .first()
    )
    if token_row and token_row.revoked_at is None:
        token_row.revoked_at = datetime.utcnow()
        db.commit()

    return {"message": "Logged out successfully"}


@router.post(
    "/logout-all",
    response_model=schemas.MessageResponse,
    responses={401: {"model": schemas.ErrorResponse}},
)
def logout_all(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    now = datetime.utcnow()
    (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.username == current_user.username,
            models.RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"message": "All sessions logged out"}


@router.post(
    "/tokens/cleanup",
    response_model=schemas.MessageResponse,
    responses={403: {"model": schemas.ErrorResponse}},
)
def cleanup_tokens(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin")),
):
    removed = purge_refresh_tokens(db)
    log_action(
        db,
        actor_username=current_user.username,
        action="token.cleanup",
        entity_type="refresh_token",
        after_data={"removed": removed},
    )
    db.commit()
    return {"message": f"Cleanup completed. Removed: {removed}"}


@router.get(
    "/me",
    response_model=schemas.UserOut,
    responses={401: {"model": schemas.ErrorResponse}},
)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post(
    "/users",
    response_model=schemas.UserOut,
    responses={
        400: {"model": schemas.ErrorResponse},
        401: {"model": schemas.ErrorResponse},
        403: {"model": schemas.ErrorResponse},
    },
)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin")),
):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    db_user = models.User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    log_action(
        db,
        actor_username=current_user.username,
        action="user.create",
        entity_type="user",
        entity_id=db_user.id,
        after_data={
            "id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "is_active": db_user.is_active,
        },
    )
    db.commit()
    return db_user
