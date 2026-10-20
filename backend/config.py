import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    farm_name: str = Field(default="Da Lat Smart Farm Beta", alias="FARM_NAME")
    farm_lat: float = Field(default=11.9404, alias="FARM_LAT")
    farm_lon: float = Field(default=108.4583, alias="FARM_LON")
    grid_size_x: int = Field(default=4, alias="GRID_SIZE_X")
    grid_size_y: int = Field(default=4, alias="GRID_SIZE_Y")
    
    # Agronomic and spectral alert thresholds
    alert_ndvi_critical: float = Field(default=0.35, alias="ALERT_NDVI_CRITICAL")
    alert_ndwi_water_stress: float = Field(default=0.05, alias="ALERT_NDWI_WATER_STRESS")
    fao56_default_elevation_m: float = Field(default=1500.0, alias="FAO56_DEFAULT_ELEVATION_M")
    default_crop_species: str = Field(default="maize", alias="DEFAULT_CROP_SPECIES")
    
    # API credentials
    copernicus_client_id: str | None = Field(default=None, alias="COPERNICUS_CLIENT_ID")
    copernicus_client_secret: str | None = Field(default=None, alias="COPERNICUS_CLIENT_SECRET")
    
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    active_llm_provider: str = Field(default="mock", alias="ACTIVE_LLM_PROVIDER") # 'mock', 'gemini', 'openai'

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
