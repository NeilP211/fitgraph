"""SQLAlchemy 2.x ORM models mirroring db/schema.sql."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(default=None)

    outfits: Mapped[list[Outfit]] = relationship("Outfit", back_populates="user")
    ratings: Mapped[list[Rating]] = relationship("Rating", back_populates="user")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    semantic_category: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    search_doc: Mapped[str | None] = mapped_column(TSVECTOR)
    image_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(default=None)

    embedding: Mapped[ItemEmbedding | None] = relationship(
        "ItemEmbedding", back_populates="item", uselist=False
    )
    outfit_items: Mapped[list[OutfitItem]] = relationship(
        "OutfitItem", back_populates="item"
    )


class ItemEmbedding(Base):
    __tablename__ = "item_embeddings"

    item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(256))
    model_version: Mapped[str | None] = mapped_column(Text)

    item: Mapped[Item] = relationship("Item", back_populates="embedding")


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped[User | None] = relationship("User", back_populates="outfits")
    outfit_items: Mapped[list[OutfitItem]] = relationship(
        "OutfitItem",
        back_populates="outfit",
        order_by="OutfitItem.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    outfit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("outfits.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("items.id"), primary_key=True
    )
    position: Mapped[int | None] = mapped_column(Integer)

    outfit: Mapped[Outfit] = relationship("Outfit", back_populates="outfit_items")
    item: Mapped[Item] = relationship("Item", back_populates="outfit_items")


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    query_item_id: Mapped[str | None] = mapped_column(Text)
    suggested_item_id: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped[User | None] = relationship("User", back_populates="ratings")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str | None] = mapped_column(Text)
    val_auc: Mapped[float | None] = mapped_column(Double, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(default=None)
