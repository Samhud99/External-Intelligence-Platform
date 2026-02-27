from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path("data")
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"
    log_level: str = "INFO"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def configs_dir(self) -> Path:
        return self.data_dir / "configs"

    @property
    def results_dir(self) -> Path:
        return self.data_dir / "results"

    def ensure_dirs(self) -> None:
        for d in [self.jobs_dir, self.configs_dir, self.results_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
