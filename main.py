from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.database import engine, Base
from routers import auth, users, posts

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Social App API",
    description="A full-featured social media backend",
    version="1.0.0"
)

# CORS - allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "API is running 🚀", "docs": "/docs"}
