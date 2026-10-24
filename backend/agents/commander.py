"""
Farm Commander (Council Orchestrator) Agent
Collects multi-agent deliberations, reconciles competing priorities (e.g. biology vs. energy costs),
runs structured debate rounds with weighted consensus, and generates actionable commands.
"""
from typing import List, Dict, Any, Optional
from backend.agents.base_agent import AgentOpinion, DebateRound, DebateVote
from backend.core.twin_state import FarmDigitalTwin, ActionLog
from backend.core.dispatcher import ActionDispatcher
import time


class FarmCouncilVerdict:
    """Consolidated outcome of the Multi-Agent Council deliberation and debate."""
    def __init__(
        self,
        opinions: List[AgentOpinion],
        executive_summary: str,
        scheduled_actions: List[Dict[str, Any]],
        debate_rounds: Optional[List[DebateRound]] = None
    ):
        self.opinions = opinions
        self.executive_summary = executive_summary
        self.scheduled_actions = scheduled_actions
        self.debate_rounds = debate_rounds or []
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "executive_summary": self.executive_summary,
            "opinions": [op.model_dump() for op in self.opinions],
            "scheduled_actions": self.scheduled_actions,
            "debate_rounds": [dr.model_dump() for dr in self.debate_rounds]
        }


class CommanderAgent:
    """
    Council Orchestrator and Supreme Arbitrator.
    Facilitates structured debate between specialist agents, resolves domain conflicts
    (Agronomy vs. Hydrology vs. Economics), and enforces consensus.
    """
    def __init__(self, agronomist, irrigation, market):
        self.agronomist = agronomist
        self.irrigation = irrigation
        self.market = market
        self.agents = [agronomist, irrigation, market]

    def arbitrate_debate(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> DebateRound:
        """
        Runs a formal multi-agent voting round on a specific operational proposal.
        Applies domain expertise weighting and conflict resolution rules.
        """
        domain = proposal.get("action_domain", "general")
        urgency = proposal.get("urgency", "low")
        is_emergency = urgency == "critical"

        votes: List[DebateVote] = []
        for agent in self.agents:
            vote = agent.vote_on_proposal(proposal, context)
            votes.append(vote)

        # Calculate weighted consensus score
        total_weight = 0.0
        weighted_score = 0.0

        for agent, vote in zip(self.agents, votes):
            w = agent.get_domain_weight(domain)
            total_weight += w
            if vote.vote == "accept":
                weighted_score += w * vote.confidence
            elif vote.vote == "concerns":
                weighted_score += (w * vote.confidence) * 0.5
            elif vote.vote == "reject":
                weighted_score -= w * vote.confidence

        normalized_score = weighted_score / max(total_weight, 0.001)

        # Conflict Resolution Rule 1: Emergency Biological Preservation Override
        # If crop is wilting or acute disease threatens the plot, override economic deferral
        if is_emergency and normalized_score < 0.5:
            consensus_verdict = "approved"
            resolution_notes = (
                "EMERGENCY OVERRIDE: Biological crop preservation takes absolute precedence "
                "over energy tariff optimization. Proposal approved."
            )
        elif normalized_score >= 0.4:
            consensus_verdict = "approved"
            resolution_notes = f"Consensus reached (weighted score: {normalized_score:.2f}). Proposal passed."
        elif normalized_score >= 0.0:
            consensus_verdict = "deferred"
            resolution_notes = (
                f"Conditional deferral (weighted score: {normalized_score:.2f}). "
                "Rescheduling to optimal off-peak / weather window."
            )
        else:
            consensus_verdict = "rejected"
            resolution_notes = f"Proposal rejected by council (weighted score: {normalized_score:.2f})."

        return DebateRound(
            round_number=1,
            proposal=proposal,
            votes=votes,
            weighted_score=round(normalized_score, 3),
            consensus_verdict=consensus_verdict,
            resolution_notes=resolution_notes
        )

    async def convene_council(
        self,
        farm: FarmDigitalTwin,
        dispatcher: Optional[ActionDispatcher] = None
    ) -> FarmCouncilVerdict:
        """
        Executes the complete end-to-end deliberation and debate workflow:
        1. Query Agronomist, Irrigation, and Market specialist agents
        2. Formulate proposals and conduct debate with domain weighting
        3. Enact conflict resolution (e.g., emergency watering vs peak electric tariffs)
        4. Dispatch approved actions to the ActionDispatcher / Farm Digital Twin
        """
        # Step 1: Specialist Evaluations
        op_agro = await self.agronomist.evaluate(farm)
        op_irri = await self.irrigation.evaluate(farm)
        op_mark = await self.market.evaluate(farm)

        opinions = [op_agro, op_irri, op_mark]
        scheduled_actions: List[Dict[str, Any]] = []
        debate_rounds: List[DebateRound] = []

        tariff_info = op_mark.data_points.get("electricity_tariff", {})
        tariff_tier = tariff_info.get("tier", "normal") if isinstance(tariff_info, dict) else "normal"
        context = {
            "tariff_tier": tariff_tier,
            "weather": farm.current_weather.model_dump(),
            "timestamp": time.time()
        }

        # Step 2: Formulate and Debate Irrigation Proposals
        parched = op_irri.data_points.get("zones", [])
        if parched:
            emergency = op_irri.data_points.get("emergency_wilting", False)
            total_l = op_irri.data_points.get("total_water_liters", 0.0)

            irrigation_proposal = {
                "action_type": "irrigate_plot_zones",
                "action_domain": "hydrology",
                "urgency": "critical" if emergency else op_irri.urgency,
                "zones_count": len(parched),
                "total_liters": total_l,
                "target_zone_ids": [pz["zone_id"] for pz in parched]
            }

            debate_irri = self.arbitrate_debate(irrigation_proposal, context)
            debate_rounds.append(debate_irri)

            if debate_irri.consensus_verdict == "approved":
                for pz in parched:
                    action = {
                        "type": "irrigate_zone",
                        "zone_id": pz["zone_id"],
                        "duration_minutes": int(pz["needed_mm"] * 3),
                        "volume_mm": pz["needed_mm"],
                        "volume_liters": pz.get("volume_liters", round(pz["needed_mm"] * 25.0, 1)),
                        "agent_name": "Commander (Consensus)",
                        "status": "queued"
                    }
                    scheduled_actions.append(action)

                    if dispatcher:
                        dispatcher.enqueue(action)

                    farm.action_history.append(ActionLog(
                        agent_name="Commander (Consensus)",
                        action_type="irrigate",
                        target_zone=pz["zone_id"],
                        parameters=action,
                        rationale=f"Debate approved ({debate_irri.resolution_notes})"
                    ))

                    # Update twin state
                    target = farm.get_zone(pz["zone_id"])
                    if target:
                        target.soil_moisture_pct = min(85.0, target.soil_moisture_pct + pz["needed_mm"] * 1.5)
                        if target.health_status == "water_stressed":
                            target.health_status = "recovering"
            else:
                scheduled_actions.append({
                    "type": "defer_irrigation",
                    "reason": debate_irri.resolution_notes,
                    "target_zones": [pz["zone_id"] for pz in parched],
                    "status": "deferred_to_offpeak"
                })

        # Step 3: Agronomy & Pathology Interventions
        fungal_hazards = op_agro.data_points.get("fungal_hazard_zones", [])
        chlorosis_zones = op_agro.data_points.get("chlorosis_zones", [])

        if op_agro.urgency == "critical" or fungal_hazards:
            fungicide_proposal = {
                "action_type": "apply_bio_fungicide",
                "action_domain": "pathology",
                "urgency": "critical",
                "target_zones": fungal_hazards
            }
            debate_fungi = self.arbitrate_debate(fungicide_proposal, context)
            debate_rounds.append(debate_fungi)

            if debate_fungi.consensus_verdict == "approved":
                f_act = {
                    "type": "apply_bio_fungicide",
                    "target_zones": fungal_hazards,
                    "agent_name": "Commander (Consensus)",
                    "treatment": "Trichoderma harzianum bio-spray",
                    "status": "queued"
                }
                scheduled_actions.append(f_act)
                if dispatcher:
                    dispatcher.enqueue(f_act)

        elif chlorosis_zones:
            scheduled_actions.append({
                "type": "schedule_foliar_fertilizer",
                "target_zones": chlorosis_zones,
                "status": "queued"
            })

        # Step 4: Executive Synthesis Summary
        approved_count = sum(1 for a in scheduled_actions if a.get("status") == "queued")
        summary = (
            f"Council concluded at {time.strftime('%H:%M:%S')}. "
            f"Conducted {len(debate_rounds)} debate round(s) with {approved_count} approved action(s). "
            f"Tariff regime: {tariff_tier.upper()}. "
            f"Plant vigilance: {op_agro.urgency.upper()}, Hydrology: {op_irri.urgency.upper()}."
        )

        return FarmCouncilVerdict(
            opinions=opinions,
            executive_summary=summary,
            scheduled_actions=scheduled_actions,
            debate_rounds=debate_rounds
        )

