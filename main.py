from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import auth, users, posts, communities, events, jobs, messages, admin, profiles

# Create all tables
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Element API",
    description="Professional networking platform — LinkedIn + Reddit + Events",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(profiles.router)
app.include_router(communities.router)
app.include_router(events.router)
app.include_router(jobs.router)
app.include_router(messages.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "Element API is running 🚀", "version": "2.0.0", "docs": "/docs"}
