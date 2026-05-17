"""Central configuration for FitGraph, loaded from environment variables and .env file."""

from pathlib import Path

import torch
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FITGRAPH_",
        env_file=".env",
        extra="ignore",
    )

    # Data directories
    data_dir: Path = Path("data")

    # Dataset size controls
    subset_outfits: int = 5000
    use_full: bool = False

    # Model hyperparameters
    clip_embed_dim: int = 512
    text_embed_dim: int = 384
    hidden_dim: int = 256
    num_heads: int = 4
    num_layers: int = 2
    dropout: float = 0.2

    # Training hyperparameters
    lr: float = 1e-3
    epochs: int = 30
    batch_size: int = 256
    temperature: float = 0.1
    num_hard_negatives: int = 5
    seed: int = 42

    # Infrastructure
    database_url: str = "postgresql+psycopg://fitgraph:fitgraph@localhost:5432/fitgraph"
    redis_url: str = "redis://localhost:6379/0"
    retrain_threshold: int = 100

    # Observability
    wandb_enabled: bool = False

    # Derived directory properties
    @computed_field  # type: ignore[misc]
    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @computed_field  # type: ignore[misc]
    @property
    def embeddings_dir(self) -> Path:
        return self.data_dir / "embeddings"

    @computed_field  # type: ignore[misc]
    @property
    def graph_dir(self) -> Path:
        return self.data_dir / "graph"

    @computed_field  # type: ignore[misc]
    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"


def resolve_device() -> str:
    """Return the best available compute device: mps > cuda > cpu."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


settings = Settings()
