from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://devpulse:devpulse@localhost:5432/devpulse"
    github_token: str = ""
    github_repos: str = ""  # comma-separated "owner/repo"
    github_webhook_secret: str = "change_me"
    environment: str = "development"

    @property
    def repo_list(self) -> list[str]:
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
