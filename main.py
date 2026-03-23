from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect
from database import engine, Base
import auth, users, posts, profiles, communities, events, jobs, messages, admin
from app.routers import ai
app.include_router(ai.router)

# ─── Safe DB Migrations ───────────────────────────────────────

def run_migrations():
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()

            if "likes" in existing_tables:
                cols = [c["name"] for c in inspector.get_columns("likes")]
                if "reaction_type" not in cols:
                    conn.execute(text("ALTER TABLE likes ADD COLUMN reaction_type VARCHAR DEFAULT 'like'"))
                    conn.commit()

            if "posts" in existing_tables:
                cols = [c["name"] for c in inspector.get_columns("posts")]
                for col, definition in [
                    ("tags",        "VARCHAR"),
                    ("feeling",     "VARCHAR"),
                    ("is_archived", "BOOLEAN DEFAULT FALSE"),
                    ("is_deleted",  "BOOLEAN DEFAULT FALSE"),
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE posts ADD COLUMN {col} {definition}"))
                        conn.commit()

            if "users" in existing_tables:
                cols = [c["name"] for c in inspector.get_columns("users")]
                for col, definition in [
                    ("headline",   "VARCHAR"),
                    ("bio",        "TEXT"),
                    ("location",   "VARCHAR"),
                    ("website",    "VARCHAR"),
                    ("cover_url",  "VARCHAR"),
                    ("is_premium", "BOOLEAN DEFAULT FALSE"),
                    ("is_verified","BOOLEAN DEFAULT FALSE"),
                    ("is_on_hold", "BOOLEAN DEFAULT FALSE"),
                    ("language",   "VARCHAR DEFAULT 'English'"),
                ]:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
                        conn.commit()

            # ─── FIX: add missing comments.parent_id column ───
            if "comments" in existing_tables:
                cols = [c["name"] for c in inspector.get_columns("comments")]
                if "parent_id" not in cols:
                    conn.execute(text("ALTER TABLE comments ADD COLUMN parent_id INTEGER REFERENCES comments(id)"))
                    conn.commit()

    except Exception as e:
        print(f"Migration warning (non-fatal): {e}")


run_migrations()
# create_all safely creates any new tables (experiences, educations, projects, skills, etc.)
# without touching existing ones
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Element API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "Element API is running 🚀", "version": "2.0.0"}
