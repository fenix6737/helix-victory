from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://helix:helix@localhost:5432/helix_victory"
    database_url_sync: str = "postgresql://helix:helix@localhost:5432/helix_victory"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    public_access: bool = False  # env: PUBLIC_ACCESS=1 — LAN/トンネル公開時

    admin_username: str = "helix_admin"
    admin_password: str = "HelixVictory2026!Admin"
    jwt_secret: str = "change-this-jwt-secret-in-production-min-32-chars"
    jwt_expire_hours: int = 24
    ingest_api_key: str = "helix-ingest-key-change-me"

    analysis_min_samples: int = 30
    analysis_missing_rate_max: float = 0.25
    score_recommend_min: float = 68.0  # env: SCORE_RECOMMEND_MIN
    score_hold_min: float = 42.0  # env: SCORE_HOLD_MIN

    cache_ttl_ranking: int = 60
    cache_ttl_stats: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        base = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if self.public_access:
            extra = [
                "http://127.0.0.1:3000",
                "http://localhost:3000",
            ]
            for o in extra:
                if o not in base:
                    base.append(o)
        return base


settings = Settings()
