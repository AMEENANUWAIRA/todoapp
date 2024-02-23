import sys

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

import models
from database import SessionLocal
from models import Users
from routers.auth import get_current_user

sys.path.append("..")

router = APIRouter(
    prefix='/users',
    tags=['users'],
    responses={404: {"description": "not found"}}
)

templates = Jinja2Templates(directory="templates")


class UserVerification(BaseModel):
    password: str
    new_password: str = Field(min_length=6)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Depends(get_db)
user_dependency = Depends(get_current_user)
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated="auto")


@router.get("/edit-password", response_class=HTMLResponse)
async def edit_user_view(request: Request):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("edit-user-password.html", {'request': request, 'user': user})


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(user_verification: UserVerification, user: dict = user_dependency,
                          db: Session = db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication failed')

    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    if not bcrypt_context.verify(user_verification.password, user_model.hashed_password):
        raise HTTPException(status_code=401, detail='Error changing password')
    else:
        user_model.hashed_password = bcrypt_context.hash(user_verification.new_password)

        db.add(user_model)
        db.commit()


@router.put("/phone_number/{phone_number}", status_code=status.HTTP_204_NO_CONTENT)
async def change_phone_number(phone_number: str, user: dict = user_dependency, db: Session = db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication failed')
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()

    user_model.phone_number = phone_number

    db.add(user_model)
    db.commit()


@router.post("/edit-password", response_class=HTMLResponse)
async def edit_user_password(request: Request,
                             username: str = Form(...),
                             password: str = Form(...),
                             password2: str = Form(...),
                             db: Session = db_dependency):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    user_data = db.query(models.Users).filter(models.Users.username == username).first()

    msg = 'Invalid username or password'

    if user_data is not None:
        if user_data.username == username and bcrypt_context.verify(password, user_data.hashed_password):
            user_data.hashed_password = bcrypt_context.hash(password2)
            db.add(user_data)
            db.commit()
            msg = 'Password updated'

    return templates.TemplateResponse("edit-user-password.html", {'request': request, 'user': user, 'msg': msg})
