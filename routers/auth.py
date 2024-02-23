from datetime import timedelta, timezone, datetime
from typing import Optional

from fastapi import HTTPException, Form
from starlette import status
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from passlib.context import CryptContext
from starlette.responses import RedirectResponse, Response

import models
from database import SessionLocal
from sqlalchemy.orm import Session
from models import Users
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated="auto")
oauth2bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

SECRET_KEY = 'd42ae102500dffac3aca9808c53a271085db201641bbc415390252666acd07fd'
ALGORITHM = 'HS256'

templates = Jinja2Templates(directory="templates")


class CreateUserRequest(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str
    password: str
    role: str
    phone_number: str


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginForm():
    def __init__(self, request: Request):
        self.request = request
        self.username = Optional[str]
        self.password = Optional[str]

    async def create_oauth_form(self):
        form = await self.request.form()
        self.username = form.get("email")
        self.password = form.get("password")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Depends(get_db)


def authenticate_user(username: str, password: str, db):
    """
    authenticate the user and return the status of authentication.

    :param username: username of the user.
    :param password: password of the user.
    :param db: database connection.
    :return: bool
    """

    user = db.query(Users).filter(username == Users.username).first()
    if not user:
        return False

    if not bcrypt_context.verify(password, user.hashed_password):
        return False

    return user


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    """
    create and return an access token 

    :param username: username of the user.
    :param user_id: id of the user.
    :param role: role of the user.
    :param expries_delta: timestamp of expiration.
    :return: jwt token
    """

    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.now(timezone.utc) + expires_delta

    encode.update({'exp': expires})

    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request):
    try:
        token = request.cookies.get("access_token")
        if token is None:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        user_id = payload.get('id')
        role = payload.get('role')

        if username is None or user_id is None:
            logout(request)
        return {'username': username, 'id': user_id, 'user_role': role}

    except JWTError:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail='Not found')


@router.get("/", response_class=HTMLResponse)
async def authentication_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request})


@router.post(path="/", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    form = LoginForm(request)
    try:
        await form.create_oauth_form()
        response = RedirectResponse(url="/todo", status_code=status.HTTP_302_FOUND)

        validate_user_cookie = await login_for_token_access(response=response, form_data=form, db=db)

        if not validate_user_cookie:
            msg = "Incorrect username or password"
            return templates.TemplateResponse("login.html", {"request": request, "msg": msg})

        return response

    except HTTPException:
        msg = "Unknown error"
        return templates.TemplateResponse("login.html", {"request": request, "msg": msg})


@router.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    msg = "Logout successful"
    response = templates.TemplateResponse("login.html", {'request': request, 'msg': msg})
    response.delete_cookie(key="access_token")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse('register.html', {'request': request})


@router.post("/register", response_class=HTMLResponse)
async def register(request: Request \
                   , email: str = Form(...) \
                   , username: str = Form(...) \
                   , firstname: str = Form(...) \
                   , lastname: str = Form(...) \
                   , password: str = Form(...) \
                   , password2: str = Form(...) \
                   , db: Session = Depends(get_db)):
    validation1 = db.query(models.Users).filter(models.Users.username == username).first()
    validation2 = db.query(models.Users).filter(models.Users.email == email).first()

    if password != password2 or validation1 is not None or validation2 is not None:
        msg = "Invalid registration request"
        return templates.TemplateResponse("register.html", {'request': request, 'msg': msg})

    user_model = models.Users()
    user_model.username = username
    user_model.email = email
    user_model.first_name = firstname
    user_model.last_name = lastname

    hash_password = bcrypt_context.hash(password)
    user_model.hashed_password = hash_password

    user_model.is_active = True

    db.add(user_model)
    db.commit()

    msg = "User successfully created"
    return templates.TemplateResponse("login.html", {'request': request, 'msg': msg})


@router.get("/user", status_code=status.HTTP_200_OK)
async def get_users(db: Session = db_dependency):
    return db.query(Users).all()


@router.post("/token", response_model=Token)
async def login_for_token_access(response: Response, form_data: OAuth2PasswordRequestForm = Depends(),
                                 db: Session = db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        return False

    token = create_access_token(user.username, user.id, user.role, timedelta(minutes=60))
    response.set_cookie(key="access_token", value=token, httponly=True)

    return True
