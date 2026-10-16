"""
Spectral Index Utilities
Computes vegetation indices (NDVI, NDWI, EVI) from satellite/multispectral bands.
"""
from typing import Dict, Any

def compute_ndvi(nir: float, red: float) -> float:
    """
    Normalized Difference Vegetation Index (NDVI)
    Formula: (NIR - Red) / (NIR + Red)
    Range: -1.0 to 1.0 (Healthy vegetation: 0.6 - 0.9)
    """
    denominator = nir + red
    if denominator == 0:
        return 0.0
    ndvi = (nir - red) / denominator
    return float(max(-1.0, min(1.0, ndvi)))

def compute_ndwi(nir: float, swir: float) -> float:
    """
    Normalized Difference Water Index (NDWI - Gao's canopy water content)
    Formula: (NIR - SWIR) / (NIR + SWIR)
    Range: -1.0 to 1.0 (Higher values indicate higher leaf water content)
    """
    denominator = nir + swir
    if denominator == 0:
        return 0.0
    ndwi = (nir - swir) / denominator
    return float(max(-1.0, min(1.0, ndwi)))

def compute_evi(nir: float, red: float, blue: float, G: float = 2.5, C1: float = 6.0, C2: float = 7.5, L: float = 1.0) -> float:
    """
    Enhanced Vegetation Index (EVI) - reduces atmospheric influences and canopy background signals.
    Formula: G * (NIR - Red) / (NIR + C1 * Red - C2 * Blue + L)
    """
    denom = nir + C1 * red - C2 * blue + L
    if denom == 0:
        return 0.0
    evi = G * (nir - red) / denom
    return float(max(-1.0, min(1.0, evi)))

def evaluate_crop_health(ndvi: float, ndwi: float) -> Dict[str, Any]:
    """
    Classify plant canopy status from NDVI and NDWI.
    """
    status = "healthy"
    issues = []
    
    if ndvi < 0.2:
        status = "bare_soil_or_dead"
        issues.append("Very low biomass detected.")
    elif ndvi < 0.45:
        status = "stressed"
        issues.append("Low chlorophyll / stressed canopy.")
    elif ndvi >= 0.7:
        status = "vigorous"
        
    if ndwi < 0.1:
        if status != "stressed":
            status = "water_stressed"
        issues.append("Low canopy water content (potential drought).")
        
    return {
        "status": status,
        "ndvi": round(ndvi, 3),
        "ndwi": round(ndwi, 3),
        "issues": issues
    }
