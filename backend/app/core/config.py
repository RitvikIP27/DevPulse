from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://devpulse:devpulse@localhost:5432/devpulse"
    github_token: str = ""
    github_repos: str = ""  # comma-separated "owner/repo"
    github_webhook_secret: str = "change_me"
    environment: str = "development"

    # --- Runtime / incident providers (optional) ---
    # Unset means the provider is NOT_CONFIGURED. DevPulse never substitutes a
    # default endpoint, because silently querying the wrong system is worse than
    # reporting that runtime data is unavailable.
    prometheus_url: str = ""
    pagerduty_token: str = ""
    pagerduty_service_ids: str = ""  # comma-separated

    #: Enables the synthetic reference scenarios (PRD 5). Demo data is written to
    #: clearly marked demo repositories only, and never mixed with real ones.
    demo_mode: bool = False

    # --- AI reasoning (optional) ---
    # Absent means analysis is unavailable, not that everything is fine: the
    # deterministic evidence package is still produced and returned.
    anthropic_api_key: str = ""
    anthropic_model: str = ""

    # --- Authentication ---
    # Off by default so a local single-user install is not forced through a
    # login. MUST be enabled before exposing DevPulse beyond localhost.
    auth_enabled: bool = False
    secret_key: str = "dev-only-insecure-key-change-me"
    access_token_expire_minutes: int = 60 * 12

    # Browsers enforce CORS, so "*" means any website a user visits could call
    # this API with their credentials. Narrow it whenever auth is on.
    cors_origins: str = "*"

    @property
    def repo_list(self) -> list[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def pagerduty_service_id_list(self) -> list[str]:
        return [s.strip() for s in self.pagerduty_service_ids.split(",") if s.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
