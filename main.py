from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, inspect

from database import engine, Base

import auth
import users
import posts
import profiles
import communities
import events
import jobs
import messages
import admin
import ai
import gifs


def run_migrations():
    """
    Lightweight startup migrations for the existing PostgreSQL database.

    These migrations are intentionally additive:
    existing data is preserved and missing columns/indexes are created.
    """

    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # ─────────────────────────────────────────────────────
        # LIKES
        # ─────────────────────────────────────────────────────

        if "likes" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("likes")]

            if "reaction_type" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE likes "
                            "ADD COLUMN reaction_type VARCHAR DEFAULT 'like'"
                        )
                    )

        # ─────────────────────────────────────────────────────
        # POSTS
        # ─────────────────────────────────────────────────────

        if "posts" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("posts")]

            post_columns = {
                "tags": "VARCHAR",
                "feeling": "VARCHAR",
                "is_archived": "BOOLEAN DEFAULT FALSE",
                "is_deleted": "BOOLEAN DEFAULT FALSE",
            }

            for col, definition in post_columns.items():
                if col not in cols:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE posts "
                                f"ADD COLUMN {col} {definition}"
                            )
                        )

        # ─────────────────────────────────────────────────────
        # COMMENTS
        # ─────────────────────────────────────────────────────

        if "comments" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("comments")]

            if "parent_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE comments "
                            "ADD COLUMN parent_id INTEGER "
                            "REFERENCES comments(id)"
                        )
                    )

        # ─────────────────────────────────────────────────────
        # USERS
        # ─────────────────────────────────────────────────────

        if "users" in existing_tables:
            cols = [c["name"] for c in inspector.get_columns("users")]

            user_columns = {
                "headline": "VARCHAR",
                "bio": "TEXT",
                "location": "VARCHAR",
                "website": "VARCHAR",
                "cover_url": "VARCHAR",
                "is_premium": "BOOLEAN DEFAULT FALSE",
                "is_verified": "BOOLEAN DEFAULT FALSE",
                "is_verified_company": "BOOLEAN DEFAULT FALSE",
                "is_on_hold": "BOOLEAN DEFAULT FALSE",
                "language": "VARCHAR DEFAULT 'English'",
                "profile_completed": "BOOLEAN DEFAULT FALSE",

                # Contact verification
                "phone_number": "VARCHAR",
                "phone_verified": "BOOLEAN DEFAULT FALSE",

                # Account lifecycle
                "account_status": "VARCHAR DEFAULT 'pending'",

                # Email verification
                "email_verified": "BOOLEAN DEFAULT FALSE",
                "email_verification_code_hash": "VARCHAR",
                "email_verification_expires_at": "TIMESTAMP WITH TIME ZONE",
                "email_verification_attempts": "INTEGER DEFAULT 0",

                # Identity verification
                "identity_status": "VARCHAR DEFAULT 'not_started'",
                "identity_submitted_at": "TIMESTAMP WITH TIME ZONE",
                "identity_reviewed_at": "TIMESTAMP WITH TIME ZONE",

                # Liveness verification
                "liveness_status": "VARCHAR DEFAULT 'not_started'",
                "liveness_submitted_at": "TIMESTAMP WITH TIME ZONE",
                "liveness_reviewed_at": "TIMESTAMP WITH TIME ZONE",

                # Authenticator app / TOTP
                "two_factor_enabled": "BOOLEAN DEFAULT FALSE",
                "totp_secret_encrypted": "TEXT",

                # Passkeys
                "passkey_enabled": "BOOLEAN DEFAULT FALSE",
            }

            for col, definition in user_columns.items():
                if col not in cols:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE users "
                                f"ADD COLUMN {col} {definition}"
                            )
                        )

            # Existing users are not automatically verified.
            #
            # Any existing row receiving the new account_status column
            # gets the database default of "pending".
            #
            # This is intentional: adding these security requirements must
            # never silently turn an existing user into a verified account.

            # Unique phone-number index.
            #
            # PostgreSQL permits multiple NULL values, while real phone
            # numbers remain unique.
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "ix_users_phone_number_unique "
                        "ON users (phone_number) "
                        "WHERE phone_number IS NOT NULL"
                    )
                )

        # ─────────────────────────────────────────────────────
        # PASSKEYS
        # ─────────────────────────────────────────────────────

        #
        # The PasskeyCredential SQLAlchemy model will create the table
        # automatically below through Base.metadata.create_all().
        #

        print("Database migrations completed successfully.")

    except Exception as e:
        print(f"Migration warning (non-fatal): {e}")


# Run additive migrations before creating any missing tables.
run_migrations()

# Create any tables that do not yet exist.
Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# FASTAPI
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Element API",
    version="2.0.0",
)


# ─────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(profiles.router)
app.include_router(communities.router)
app.include_router(events.router)
app.include_router(jobs.router)
app.include_router(messages.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(gifs.router)


# ─────────────────────────────────────────────────────────────
# HEALTH / ROOT
# ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "Element API is running 🚀",
        "version": "2.0.0",
    }
