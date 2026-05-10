"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-19

Creates all tables for the MVP: sources, articles, entities, article_entities,
users, user_cookies, subscriptions. NER and pgvector columns are deferred to
later migrations so the initial schema stays simple.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── enums ──────────────────────────────────
    lang_enum = postgresql.ENUM("en", "zh", "ja", name="lang", create_type=False)
    source_kind_enum = postgresql.ENUM("rss", "html", "api", name="source_kind", create_type=False)
    source_tier_enum = postgresql.ENUM("free", "paywall", name="source_tier", create_type=False)
    cookie_status_enum = postgresql.ENUM(
        "missing", "ok", "expiring", "expired", name="cookie_status", create_type=False
    )
    entity_kind_enum = postgresql.ENUM("person", "company", name="entity_kind", create_type=False)

    bind = op.get_bind()
    for t in (lang_enum, source_kind_enum, source_tier_enum, cookie_status_enum, entity_kind_enum):
        t.create(bind, checkfirst=True)

    # ─── sources ────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("name_local", sa.String(128), nullable=True),
        sa.Column("lang", lang_enum, nullable=False),
        sa.Column("region", sa.String(8), nullable=False),
        sa.Column("kind", source_kind_enum, nullable=False),
        sa.Column("tier", source_tier_enum, nullable=False, server_default="free"),
        sa.Column("feed_url", sa.String(512), nullable=True),
        sa.Column("fetcher", sa.String(128), nullable=False),
        sa.Column("schedule_cron", sa.String(64), nullable=False, server_default="*/15 * * * *"),
        sa.Column("needs_cookies", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_sources_slug", "sources", ["slug"])
    op.create_index("ix_sources_enabled", "sources", ["enabled"])

    # ─── articles ───────────────────────────────
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(),
                  sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("url_hash", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(256), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lang", lang_enum, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("lead_image_url", sa.String(1024), nullable=True),
        sa.Column("reading_time_min", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.CHAR(64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"])
    op.create_index("idx_articles_published_at", "articles", ["published_at"])
    op.create_index("idx_articles_source_published", "articles", ["source_id", "published_at"])

    # ─── entities ───────────────────────────────
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("canonical_name", sa.String(256), nullable=False),
        sa.Column("name_local", sa.String(256), nullable=True),
        sa.Column("kind", entity_kind_enum, nullable=False),
        sa.Column("wikidata_qid", sa.String(32), nullable=True, unique=True),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_entities_slug", "entities", ["slug"])

    # ─── article_entities ───────────────────────
    op.create_table(
        "article_entities",
        sa.Column("article_id", sa.Integer(),
                  sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Integer(),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.PrimaryKeyConstraint("article_id", "entity_id"),
    )
    op.create_index("ix_article_entities_entity_id", "article_entities", ["entity_id"])

    # ─── users ──────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(256), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=True),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ─── user_cookies ───────────────────────────
    op.create_table(
        "user_cookies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(),
                  sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cookies_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("status", cookie_status_enum, nullable=False, server_default="ok"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "source_id", name="uniq_user_cookies_user_src"),
    )

    # ─── subscriptions ──────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.Integer(),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notify_channels", postgresql.ARRAY(sa.String(32)),
                  nullable=False, server_default="{}"),
        sa.Column("muted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "entity_id"),
    )
    op.create_index("ix_subscriptions_entity_id", "subscriptions", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_entity_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("user_cookies")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_article_entities_entity_id", table_name="article_entities")
    op.drop_table("article_entities")
    op.drop_index("ix_entities_slug", table_name="entities")
    op.drop_table("entities")
    op.drop_index("idx_articles_source_published", table_name="articles")
    op.drop_index("idx_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_content_hash", table_name="articles")
    op.drop_index("ix_articles_url_hash", table_name="articles")
    op.drop_index("ix_articles_source_id", table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_index("ix_sources_slug", table_name="sources")
    op.drop_table("sources")

    for name in ("entity_kind", "cookie_status", "source_tier", "source_kind", "lang"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
