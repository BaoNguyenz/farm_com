"""
Scenario Benchmarks REST API Endpoints (v1)
Provides execution triggers, scenario catalog listings, and evaluation reports for farm resilience testing.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from backend.core.twin_state import FarmDigitalTwin
from backend.agents.commander import CommanderAgent
from backend.benchmarks.runner import benchmark_runner


router = APIRouter(prefix="/scenarios", tags=["Scenario Benchmarks v1"])


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


def get_commander() -> CommanderAgent:
    from backend.main import commander_agent
    return commander_agent


class RunScenarioRequest(BaseModel):
    scenario_id: str = Field("all", description="Scenario key ('drought_shock', 'fungal_outbreak', 'tariff_optimization', 'frost_hazard') or 'all'")
    broadcast_updates: bool = Field(True, description="Whether to stream benchmark progress via WebSocket")


@router.get("/list")
async def list_scenarios() -> List[Dict[str, Any]]:
    """Retrieve catalog of registered stress scenarios and evaluation parameters."""
    return benchmark_runner.get_available_scenarios()


@router.post("/run")
async def run_scenario_benchmark(
    payload: RunScenarioRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state),
    commander: CommanderAgent = Depends(get_commander)
) -> Dict[str, Any]:
    """Execute one or all scenario benchmarks against digital twin and multi-agent council."""
    from backend.core.websocket_manager import ws_hub

    if payload.scenario_id == "all":
        report = await benchmark_runner.run_all(farm, commander)
        report_dict = report.to_dict()

        if payload.broadcast_updates:
            await ws_hub.broadcast_council_event("BENCHMARK_SUITE_COMPLETED", report_dict)

        return {
            "status": "success",
            "type": "suite_completed",
            "report": report_dict
        }

    try:
        result = await benchmark_runner.run_scenario(payload.scenario_id, farm, commander)
        res_dict = result.to_dict()

        if payload.broadcast_updates:
            await ws_hub.broadcast_council_event("SCENARIO_BENCHMARK_COMPLETED", res_dict)

        return {
            "status": "success",
            "type": "single_scenario_completed",
            "result": res_dict
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/latest")
async def get_latest_benchmark_report() -> Optional[Dict[str, Any]]:
    """Retrieve the most recent multi-scenario benchmark scorecard."""
    latest = benchmark_runner.last_report
    if not latest:
        return {"status": "no_reports_yet", "report": None}
    return {"status": "success", "report": latest.to_dict()}
