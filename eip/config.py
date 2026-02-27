import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path(os.getenv("EIP_DATA_DIR", "data"))
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    default_model: str = os.getenv("EIP_DEFAULT_MODEL", "claude-sonnet-4-6")
    log_level: str = os.getenv("EIP_LOG_LEVEL", "INFO")

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
