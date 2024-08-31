import os

from authlib.jose import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse


# Load environment variables from .env file
load_dotenv()

app = FastAPI()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],  # Your Vue.js app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware setup
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise ValueError("No SESSION_SECRET_KEY set for SessionMiddleware")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# OAuth setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid https://www.googleapis.com/auth/userinfo.email'
    }
)

# JWT setup
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("No JWT_SECRET_KEY set")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Helper functions
def create_jwt_token(data: dict):
    return jwt.encode(data, JWT_SECRET_KEY, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Routes
@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for('auth_google')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google")
async def auth_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)

    # Create a JWT token
    jwt_token = create_jwt_token({"sub": user.get("email")})

    # Redirect back to the Vue app with the token
    frontend_url = FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}/auth?token={jwt_token}")


@app.get("/protected")
async def protected_route(current_user: str = Depends(get_current_user)):
    return {"message": "This is a protected route", "user": current_user}


# Startup event
@app.on_event("startup")
async def startup():
    await oauth.google.load_server_metadata()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)