import os
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from .. import schemas, models, database

router = APIRouter(
    tags=["Auth"]
)

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM")


# Generates has values for the given password
def generate_hash(password):
    return password_context.hash(password)


# Verifies the current password with hased password
def verify_password(hashed_pass, plain_text):
    return password_context.verify(plain_text, hash=hashed_pass)


# Creating the access token (JWT)
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Decoding the JWT to get user
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = {
        "username": username,
        "id": payload.get("id"),
        "role" : payload.get("role")
    }
    if user is None:
        raise credentials_exception
    return user


user_dep = Annotated[dict, Depends(get_current_user)]


@router.post('/token', response_model=schemas.Token, status_code=200)
async def login_token(
        request: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: database.db_dependency
):
    
    """
    Endpoint to generate access token for user login.

    Parameters:
    - request: OAuth2PasswordRequestForm, Form containing username and password.
    - db: Session, Database session dependency.

    Returns:
    - dict: Access token and token type.
    """

    user = db.query(models.Users).filter(models.Users.username == request.username).first()
    if user and verify_password(user.passwordHash, request.password):
        token = create_access_token({"username": user.username, "id": user.id, "role": user.role})
        return {"access_token": token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")


@router.post('/signup', status_code=200, response_model=schemas.createUserResponse)
def create_user(request: schemas.CreateUser, db: database.db_dependency):

    """
    Endpoint to create a new user.

    Parameters:
    - request: CreateUser, Request body containing user information.
    - db: Session, Database session dependency.

    Returns:
    - Users: Newly created user.
    """

    if request.password == request.confirmation:
        hash_pass = generate_hash(request.password)
        db_user = models.Users(username=request.username, passwordHash=hash_pass, role=request.role)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password Don't Match")

    
