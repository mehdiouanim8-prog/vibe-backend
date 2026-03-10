from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect
from database import engine, Base
import auth, users, posts, communities, events, jobs, messages, admin, profiles

# ─── Safe DB Migration ───────────────────────────────────────
# Adds reaction_type column to likes table if it doesn't exist yet
try:
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        if "likes" in existing_tables:
            columns = [col["name"] for col in inspector.get_columns("likes")]
            if "reaction_type" not in columns:
                conn.execute(text("ALTER TABLE likes ADD COLUMN reaction_type VARCHAR DEFAULT 'like'"))
                conn.commit()
except Exception as e:
    print(f"Migration warning (non-fatal): {e}")

# ─── Create All Tables ───────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Element API",
    description="Professional networking platform — LinkedIn + Reddit + Events",
    version="2.0.0"
)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────
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
