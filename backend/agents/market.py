"""
Market & Economic Analyst Agent
Evaluates crop harvest maturity (GDD), current spot prices, EVN Time-of-Use (TOU) electricity tariffs,
cold-chain post-harvest shelf-life pricing degradation, ethylene arbitrage, and operational cost optimization.
"""
import time
from datetime import datetime
from typing import Any, ClassVar

from backend.agents.base_agent import AgentOpinion, AgentRole, BaseFarmAgent, DebateVote
from backend.core.cold_chain import (
    ColdChainEngine,
    ColdChamberState,
    ShelfLifeProjection,
)
from backend.core.twin_state import FarmDigitalTwin


class MarketAgent(BaseFarmAgent):
    """
    Agricultural Economics & Market Strategist Agent.
    Monitors wholesale commodity market prices, EVN electricity TOU tariffs,
    post-harvest cold-chain shelf-life depreciation, and conducts cost-benefit trade-offs.
    """

    # Vietnam EVN 3-Tier Time-of-Use (TOU) Schedule for Agriculture / Medium Voltage
    # Rates in VND / kWh (approximate standard tariff structure)
    TARIFF_RATES: ClassVar[dict[str, float]] = {
        "off_peak": 1133.0,   # 22:00 -> 04:00
        "normal": 1685.0,     # 04:00 -> 09:30, 11:30 -> 17:00, 20:00 -> 22:00
        "peak": 3076.0        # 09:30 -> 11:30, 17:00 -> 20:00
    }

    # Standard wholesale prices in Lam Dong / Central Highlands (VND/kg or VND/stem)
    SPOT_PRICES: ClassVar[dict[str, dict[str, Any]]] = {
        "Strawberries": {"price_vnd": 180000, "unit": "kg", "trend": "+12%", "status": "high_demand", "yield_kg_m2": 1.2},
        "Arabica Coffee": {"price_vnd": 95000, "unit": "kg", "trend": "+3%", "status": "stable", "yield_kg_m2": 0.8},
        "Bell Pepper": {"price_vnd": 35000, "unit": "kg", "trend": "-5%", "status": "slight_oversupply", "yield_kg_m2": 2.5},
        "Hydrangea": {"price_vnd": 120000, "unit": "stem_bunch", "trend": "+8%", "status": "high_demand", "yield_kg_m2": 1.0}
    }

    # Quality Grade Pricing Multipliers based on Cold Chain Freshess
    QUALITY_PRICING_FACTORS: ClassVar[dict[str, float]] = {
        "AAA_PREMIUM_EXPORT": 1.15,
        "AA_FRESH_RETAIL": 1.00,
        "A_STANDARD": 0.90,
        "EXPEDITED_SALE_REQUIRED": 0.65,
    }

    # Grid carbon intensity and carbon credit tax rate (VND / ton CO2e)
    GRID_CARBON_INTENSITY_KG_KWH = 0.7221
    CARBON_TAX_VND_PER_TON = 120000.0

    # Bulk Industrial Liquid CO2 input pricing for CEA greenhouses (VND / kg)
    CO2_COST_PER_KG_VND: ClassVar[float] = 12000.0

    # Hauled fresh municipal water benchmark during drought / salinity events (VND / m3)
    MUNICIPAL_WATER_COST_PER_M3_VND: ClassVar[float] = 25000.0

    def __init__(self, cold_chain_engine: ColdChainEngine | None = None) -> None:
        super().__init__(
            agent_id="agent_market",
            role=AgentRole.MARKET.value,
            expertise_domain="economics"
        )
        self.cold_chain_engine = cold_chain_engine or ColdChainEngine()

    def evaluate_cold_chain_inventory(
        self,
        chambers: list[ColdChamberState] | None = None,
    ) -> dict[str, Any]:
        """
        Calculates dynamic market valuation and shelf-life clearance priorities for cold storage produce.
        """
        if chambers is None:
            # Default cold room chambers monitoring farm storage
            chambers = [
                ColdChamberState(
                    chamber_id="CHAMBER-A1",
                    crop_type="Strawberries",
                    stored_weight_kg=350.0,
                    air_temp_c=3.2,
                    relative_humidity_pct=92.0,
                    ethylene_ppm=0.08,
                    hours_in_storage=18.0
                ),
                ColdChamberState(
                    chamber_id="CHAMBER-B2",
                    crop_type="Bell Peppers",
                    stored_weight_kg=600.0,
                    air_temp_c=7.5,
                    relative_humidity_pct=88.0,
                    ethylene_ppm=0.12,
                    hours_in_storage=36.0
                ),
            ]

        inventory_records: list[dict[str, Any]] = []
        total_valuation_vnd = 0.0
        expedited_sale_required = False

        for chamber in chambers:
            proj: ShelfLifeProjection = self.cold_chain_engine.evaluate_shelf_life(chamber)
            base_price = self.SPOT_PRICES.get(chamber.crop_type, {"price_vnd": 50000})["price_vnd"]
            multiplier = self.QUALITY_PRICING_FACTORS.get(proj.quality_grade, 1.0)
            adjusted_price_per_kg = round(base_price * multiplier, 0)
            lot_value_vnd = round(chamber.stored_weight_kg * adjusted_price_per_kg, 0)
            total_valuation_vnd += lot_value_vnd

            is_urgent = proj.quality_grade == "EXPEDITED_SALE_REQUIRED" or proj.remaining_shelf_life_days <= 3.0
            if is_urgent:
                expedited_sale_required = True

            inventory_records.append({
                "chamber_id": chamber.chamber_id,
                "crop_type": chamber.crop_type,
                "weight_kg": chamber.stored_weight_kg,
                "quality_grade": proj.quality_grade,
                "remaining_shelf_life_days": proj.remaining_shelf_life_days,
                "freshness_index_pct": proj.freshness_index_pct,
                "base_price_vnd": base_price,
                "adjusted_price_vnd": adjusted_price_per_kg,
                "lot_value_vnd": lot_value_vnd,
                "expedited_dispatch": is_urgent,
                "alert": proj.alert_action,
            })

        return {
            "total_inventory_valuation_vnd": total_valuation_vnd,
            "expedited_sale_required": expedited_sale_required,
            "chambers_count": len(chambers),
            "inventory_records": inventory_records,
        }

    def evaluate_microgrid_arbitrage(
        self,
        solar_power_kw: float,
        battery_soc: float,
        load_kw: float = 3.5,
        hour: float | None = None,
    ) -> dict[str, Any]:
        """
        Analyzes microgrid solar self-consumption and battery peak-shaving potential.
        Recommends whether to run loads from PV/BESS or draw from grid.
        """
        tariff = self.get_electricity_tariff(hour)
        tier = tariff["tier"]

        # Available clean energy
        clean_power_available_kw = solar_power_kw + (10.0 if battery_soc > 0.25 else 0.0)
        can_self_power = clean_power_available_kw >= load_kw

        strategy = "grid_draw"
        cost_savings_vnd = 0.0

        if can_self_power:
            if tier == "peak":
                strategy = "peak_shaving_discharge"
                cost_savings_vnd = load_kw * self.TARIFF_RATES["peak"]
            else:
                strategy = "solar_self_consumption"
                cost_savings_vnd = load_kw * tariff["rate_vnd_kwh"]
        elif tier == "off_peak" and battery_soc < 0.85:
            strategy = "off_peak_grid_bess_charge"

        return {
            "tier": tier,
            "rate_vnd_kwh": tariff["rate_vnd_kwh"],
            "solar_power_kw": round(solar_power_kw, 2),
            "battery_soc": round(battery_soc, 2),
            "can_self_power": can_self_power,
            "strategy": strategy,
            "hourly_cost_savings_vnd": round(cost_savings_vnd, 0),
        }

    def get_electricity_tariff(self, hour: float | None = None) -> dict[str, Any]:
        """
        Determines active EVN TOU electricity tariff tier and rate per kWh.
        If hour is not provided, uses current local time hour.
        """
        if hour is None:
            now = datetime.now()
            hour = now.hour + now.minute / 60.0

        if (hour >= 22.0) or (hour < 4.0):
            tier = "off_peak"
        elif (9.5 <= hour < 11.5) or (17.0 <= hour < 20.0):
            tier = "peak"
        else:
            tier = "normal"

        rate = self.TARIFF_RATES[tier]
        peak_rate = self.TARIFF_RATES["peak"]
        savings_vs_peak = round(((peak_rate - rate) / peak_rate) * 100.0, 1)

        return {
            "tier": tier,
            "rate_vnd_kwh": rate,
            "hour": round(hour, 2),
            "is_peak": tier == "peak",
            "is_off_peak": tier == "off_peak",
            "savings_vs_peak_pct": savings_vs_peak
        }

    def estimate_pumping_cost(self, water_volume_liters: float, tier: str = "normal") -> dict[str, float]:
        """
        Estimates energy required, financial cost, and Scope 2 GHG emissions to pump water.
        Benchmark: 3.5 kW pump delivers 15,000 L/h => ~0.233 kWh per 1,000 Liters.
        """
        kwh_per_1000l = 0.233
        energy_kwh = (water_volume_liters / 1000.0) * kwh_per_1000l
        rate = self.TARIFF_RATES.get(tier, self.TARIFF_RATES["normal"])
        cost_vnd = energy_kwh * rate
        peak_cost_vnd = energy_kwh * self.TARIFF_RATES["peak"]
        potential_savings = max(0.0, peak_cost_vnd - cost_vnd)

        co2e_kg = energy_kwh * self.GRID_CARBON_INTENSITY_KG_KWH
        carbon_tax_vnd = (co2e_kg / 1000.0) * self.CARBON_TAX_VND_PER_TON

        return {
            "water_volume_liters": water_volume_liters,
            "energy_kwh": round(energy_kwh, 2),
            "rate_vnd_kwh": rate,
            "cost_vnd": round(cost_vnd, 0),
            "potential_savings_vs_peak_vnd": round(potential_savings, 0),
            "scope2_emissions_kg_co2e": round(co2e_kg, 3),
            "carbon_tax_liability_vnd": round(carbon_tax_vnd, 1)
        }

    def evaluate_co2_enrichment_economics(
        self,
        co2_kg_dosed: float,
        projected_yield_gain_pct: float,
        crop_type: str = "Strawberries",
        area_m2: float = 100.0,
    ) -> dict[str, Any]:
        """
        Assesses marginal financial return on liquid CO2 enrichment dosing.
        Compares industrial CO2 procurement costs against elevated photosynthetic crop yield value.
        """
        crop_meta = self.SPOT_PRICES.get(crop_type, {"price_vnd": 50000, "yield_kg_m2": 1.0, "unit": "kg"})
        co2_cost_vnd = co2_kg_dosed * self.CO2_COST_PER_KG_VND

        base_yield_kg = area_m2 * crop_meta.get("yield_kg_m2", 1.0)
        marginal_yield_kg = round(base_yield_kg * (projected_yield_gain_pct / 100.0), 2)
        marginal_revenue_vnd = round(marginal_yield_kg * crop_meta["price_vnd"], 0)
        net_profit_vnd = round(marginal_revenue_vnd - co2_cost_vnd, 0)
        roi_ratio = round(marginal_revenue_vnd / max(1.0, co2_cost_vnd), 2)
        is_profitable = net_profit_vnd > 0

        recommendation = (
            f"CO2 enrichment highly viable (ROI: {roi_ratio}x, Net: +{net_profit_vnd:,.0f} VND)."
            if is_profitable
            else f"CO2 enrichment unprofitable (ROI: {roi_ratio}x, Net: {net_profit_vnd:,.0f} VND). Defer dosing."
        )

        return {
            "crop_type": crop_type,
            "co2_kg_dosed": co2_kg_dosed,
            "co2_cost_vnd": co2_cost_vnd,
            "marginal_yield_kg": marginal_yield_kg,
            "marginal_revenue_vnd": marginal_revenue_vnd,
            "net_profit_vnd": net_profit_vnd,
            "roi_ratio": roi_ratio,
            "is_profitable": is_profitable,
            "recommendation": recommendation,
        }

    def evaluate_solar_desalination_economics(
        self,
        permeate_m3: float,
        solar_available_kw: float,
        sec_kwh_m3: float = 1.4,
        hour: float | None = None,
    ) -> dict[str, Any]:
        """
        Calculates financial cost-benefit of on-site solar RO desalination
        vs purchasing and hauling fresh irrigation water (25,000 VND/m3).
        """
        tariff = self.get_electricity_tariff(hour)
        tier = tariff["tier"]
        rate = tariff["rate_vnd_kwh"]

        # Clean energy availability: if solar covers pump power (~2.0 kW)
        is_solar_powered = solar_available_kw >= 2.0
        effective_energy_cost_vnd = 0.0 if is_solar_powered else (permeate_m3 * sec_kwh_m3 * rate)

        water_truck_cost_vnd = permeate_m3 * self.MUNICIPAL_WATER_COST_PER_M3_VND
        net_savings_vnd = round(water_truck_cost_vnd - effective_energy_cost_vnd, 0)
        roi_ratio = round(water_truck_cost_vnd / max(1.0, effective_energy_cost_vnd), 2)

        recommendation = (
            f"Solar RO highly profitable (100% solar self-powered: Net savings +{net_savings_vnd:,.0f} VND vs hauled water)."
            if is_solar_powered
            else (
                f"Grid-powered RO economically viable during {tier} tariff (Net: +{net_savings_vnd:,.0f} VND, ROI: {roi_ratio}x)."
                if net_savings_vnd > 0 and tier != "peak"
                else f"DEFER RO DESALINATION: Peak grid tariff ({rate:,.0f} VND/kWh) renders pumping uneconomical. Defer to solar midday."
            )
        )

        return {
            "permeate_m3": permeate_m3,
            "is_solar_powered": is_solar_powered,
            "tariff_tier": tier,
            "energy_cost_vnd": round(effective_energy_cost_vnd, 0),
            "hauled_water_cost_vnd": round(water_truck_cost_vnd, 0),
            "net_savings_vnd": net_savings_vnd,
            "roi_ratio": roi_ratio,
            "recommendation": recommendation,
        }

    def evaluate_biocontrol_economics(
        self,
        canopy_area_m2: float,
        pest_density: float,
        crop_type: str = "Strawberries",
    ) -> dict[str, Any]:
        """
        Calculates financial cost-benefit of biological predator release
        vs chemical pesticide spraying with organic export premium preservation.
        """
        import math

        crop_meta = self.SPOT_PRICES.get(crop_type, {"price_vnd": 50000, "yield_kg_m2": 1.0, "unit": "kg"})
        crop_yield_kg = canopy_area_m2 * crop_meta.get("yield_kg_m2", 1.0)
        base_revenue_vnd = crop_yield_kg * crop_meta["price_vnd"]

        # Chemical spray carries risk of forfeiting the 25% organic export price premium
        organic_premium_forfeited_vnd = round(base_revenue_vnd * 0.25, 0)
        chemical_spray_cost_vnd = 250000.0 + (canopy_area_m2 * 250.0)  # chemical + labor
        total_chemical_cost_vnd = chemical_spray_cost_vnd + organic_premium_forfeited_vnd

        # Biocontrol cost: bottle packs (350,000 VND / 2,000 mites) + drone application (150,000 VND)
        dose_m2 = 2.5 if pest_density <= 5.0 else (12.0 if pest_density <= 15.0 else 28.0)
        total_mites = canopy_area_m2 * dose_m2
        bottles = max(1, math.ceil(total_mites / 2000.0))
        biocontrol_cost_vnd = (bottles * 350000.0) + 150000.0

        net_savings_vnd = round(total_chemical_cost_vnd - biocontrol_cost_vnd, 0)
        roi_ratio = round(total_chemical_cost_vnd / max(1.0, biocontrol_cost_vnd), 2)
        recommend_biocontrol = net_savings_vnd > 0

        rec = (
            f"Biocontrol highly cost-effective (Net savings: +{net_savings_vnd:,.0f} VND, ROI: {roi_ratio}x). "
            f"Preserves 25% organic export premium ({organic_premium_forfeited_vnd:,.0f} VND)."
            if recommend_biocontrol
            else f"Biocontrol expenditure ({biocontrol_cost_vnd:,.0f} VND) exceeds chemical savings. Evaluate hotspot release."
        )

        return {
            "crop_type": crop_type,
            "canopy_area_m2": canopy_area_m2,
            "pest_density": pest_density,
            "biocontrol_cost_vnd": biocontrol_cost_vnd,
            "chemical_spray_cost_vnd": chemical_spray_cost_vnd,
            "organic_premium_preserved_vnd": organic_premium_forfeited_vnd,
            "total_chemical_alternative_cost_vnd": total_chemical_cost_vnd,
            "net_savings_vnd": net_savings_vnd,
            "roi_ratio": roi_ratio,
            "recommend_biocontrol": recommend_biocontrol,
            "recommendation": rec,
        }

    def evaluate_aquaponics_dual_harvest_economics(
        self,
        fish_biomass_kg: float,
        crop_heads: int,
        crop_type: str = "Butterhead Lettuce",
    ) -> dict[str, Any]:
        """
        Assesses combined dual revenue from aquaculture finfish biomass (Tilapia)
        and hydroponic clean leafy greens.
        Tilapia wholesale: 75,000 VND/kg
        Butterhead lettuce: 12,000 VND/head (~48,000 VND/kg)
        Feed cost: ~22,000 VND/kg feed
        """
        fish_price_vnd_kg = 75000.0
        fish_revenue_vnd = round(fish_biomass_kg * fish_price_vnd_kg, 0)

        crop_price_vnd_head = 12000.0 if "lettuce" in crop_type.lower() else 10000.0
        crop_revenue_vnd = round(crop_heads * crop_price_vnd_head, 0)

        total_gross_revenue_vnd = fish_revenue_vnd + crop_revenue_vnd

        # Approximate feed & power OPEX
        feed_used_kg = fish_biomass_kg * 1.4  # FCR = 1.4
        feed_cost_vnd = round(feed_used_kg * 22000.0, 0)
        pumping_power_cost_vnd = 1800000.0  # ~30 days recirc pumping
        total_opex_vnd = feed_cost_vnd + pumping_power_cost_vnd

        net_margin_vnd = round(total_gross_revenue_vnd - total_opex_vnd, 0)
        roi_ratio = round(total_gross_revenue_vnd / max(1.0, total_opex_vnd), 2)

        rec = (
            f"Aquaponic dual-harvest highly profitable (Net margin: +{net_margin_vnd:,.0f} VND, ROI: {roi_ratio}x). "
            f"Fish revenue: {fish_revenue_vnd:,.0f} VND ({fish_biomass_kg:.1f} kg) + Crop revenue: {crop_revenue_vnd:,.0f} VND ({crop_heads} heads)."
        )

        return {
            "fish_biomass_kg": fish_biomass_kg,
            "crop_heads": crop_heads,
            "crop_type": crop_type,
            "fish_revenue_vnd": fish_revenue_vnd,
            "crop_revenue_vnd": crop_revenue_vnd,
            "total_gross_revenue_vnd": total_gross_revenue_vnd,
            "feed_cost_vnd": feed_cost_vnd,
            "pumping_power_cost_vnd": pumping_power_cost_vnd,
            "total_opex_vnd": total_opex_vnd,
            "net_margin_vnd": net_margin_vnd,
            "roi_ratio": roi_ratio,
            "recommendation": rec,
        }

    async def evaluate(self, farm: FarmDigitalTwin) -> AgentOpinion:
        tariff_info = self.get_electricity_tariff()
        is_peak = tariff_info["is_peak"]

        harvest_candidates: list[dict[str, Any]] = []
        total_estimated_value_vnd = 0.0

        for zone in farm.zones:
            crop_meta = self.SPOT_PRICES.get(zone.crop_type, {"price_vnd": 50000, "yield_kg_m2": 1.0, "unit": "kg"})
            if zone.growth_stage in ["harvest_ready", "fruiting"] and zone.accumulated_gdd > 300.0:
                # 25 m2 per plot
                est_yield_kg = 25.0 * crop_meta["yield_kg_m2"]
                est_val = est_yield_kg * crop_meta["price_vnd"]
                total_estimated_value_vnd += est_val

                harvest_candidates.append({
                    "zone_id": zone.id,
                    "crop": zone.crop_type,
                    "stage": zone.growth_stage,
                    "gdd": zone.accumulated_gdd,
                    "est_yield": est_yield_kg,
                    "est_value_vnd": round(est_val, 0),
                    "spot_price_vnd": crop_meta["price_vnd"]
                })

        # Microgrid solar & battery status check
        solar_est_kw = round((farm.current_weather.solar_radiation_mj / 3.6) * 2.5, 2) if hasattr(farm, "current_weather") else 5.0
        battery_soc_est = 0.65
        microgrid_analysis = self.evaluate_microgrid_arbitrage(solar_power_kw=solar_est_kw, battery_soc=battery_soc_est)

        # Cold-chain inventory audit
        cold_chain_audit = self.evaluate_cold_chain_inventory()

        # CO2 enrichment marginal yield economics
        co2_economics = self.evaluate_co2_enrichment_economics(
            co2_kg_dosed=12.0,
            projected_yield_gain_pct=15.0,
            crop_type="Strawberries",
            area_m2=150.0,
        )

        # Solar RO desalination cost-benefit arbitrage
        solar_ro_economics = self.evaluate_solar_desalination_economics(
            permeate_m3=4.0,
            solar_available_kw=solar_est_kw,
        )

        urgency = "low"
        if cold_chain_audit["expedited_sale_required"]:
            urgency = "critical"
            rec = "URGENT LOGISTICS: Cold storage inventory contains produce with expiring shelf-life. Dispatch immediately to avoid spoilage markdown."
        elif is_peak and not microgrid_analysis["can_self_power"]:
            rec = (
                f"EVN PEAK TARIFF WINDOW ACTIVE ({tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "
                f"Defer heavy electrical pumps/lighting until off-peak window (22:00) unless critical moisture stress occurs."
            )
            urgency = "medium"
        elif is_peak and microgrid_analysis["can_self_power"]:
            rec = (
                f"PEAK TARIFF ACTIVE, but Microgrid is SELF-POWERED (Solar: {solar_est_kw} kW, SoC: {int(battery_soc_est*100)}%). "
                f"Discharging BESS for peak-shaving saves ~{microgrid_analysis['hourly_cost_savings_vnd']:,.0f} VND/h."
            )
        else:
            rec = f"Electricity window favorable ({tariff_info['tier'].upper()} - {tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "

        if harvest_candidates:
            zone_ids = [hc["zone_id"] for hc in harvest_candidates]
            rec += (
                f" High spot commodity values: {len(harvest_candidates)} plots ready for market "
                f"({', '.join(zone_ids[:3])}) with gross projected yield value: {total_estimated_value_vnd:,.0f} VND."
            )

        reasoning = (
            f"Electricity pricing tier: {tariff_info['tier']} ({tariff_info['rate_vnd_kwh']:,.0f} VND/kWh). "
            f"Identified {len(harvest_candidates)} zones meeting thermal GDD maturity thresholds. "
            f"Cold storage valuation: {cold_chain_audit['total_inventory_valuation_vnd']:,.0f} VND across {cold_chain_audit['chambers_count']} chambers. "
            f"CO2 enrichment economics: {co2_economics['recommendation']} "
            f"Solar RO: {solar_ro_economics['recommendation']} "
            f"Wholesale prices: Strawberries at 180,000 VND/kg (+12%), Hydrangeas at 120,000 VND."
        )

        return AgentOpinion(
            agent_id=self.agent_id,
            role=self.role,
            confidence=0.90,
            recommendation=rec,
            urgency=urgency,
            data_points={
                "electricity_tariff": tariff_info,
                "harvest_candidates": harvest_candidates,
                "projected_harvest_value_vnd": total_estimated_value_vnd,
                "spot_prices": self.SPOT_PRICES,
                "microgrid_arbitrage": microgrid_analysis,
                "cold_chain_inventory": cold_chain_audit,
                "co2_enrichment_economics": co2_economics,
                "solar_desalination_economics": solar_ro_economics,
                "grid_carbon_intensity_kg_kwh": self.GRID_CARBON_INTENSITY_KG_KWH,
                "carbon_tax_rate_vnd_ton": self.CARBON_TAX_VND_PER_TON
            },
            reasoning=reasoning,
            timestamp=time.time()
        )

    def vote_on_proposal(self, proposal: dict[str, Any], context: dict[str, Any]) -> DebateVote:
        """
        Evaluates operational proposals from an economic lens.
        Defends operating margins by vetoing non-emergency high-power actions during peak tariff
        and prioritizing urgent cold-chain produce dispatches over prolonged holding.
        """
        action_type = proposal.get("action_type", "").lower()
        urgency = proposal.get("urgency", "low")
        tariff_tier = context.get("tariff_tier", self.get_electricity_tariff()["tier"])

        # Cold chain expedited clearance protection
        if "hold_storage" in action_type or "defer_shipment" in action_type:
            chamber_quality = context.get("cold_chain_quality_grade", "")
            shelf_life_days = context.get("remaining_shelf_life_days", 10.0)
            if chamber_quality == "EXPEDITED_SALE_REQUIRED" or shelf_life_days < 3.0:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="market_logistics",
                    vote_choice="REJECT",
                    confidence=0.96,
                    rationale=(
                        f"COLD-CHAIN ARBITRAGE VETO: Produce shelf-life critical ({shelf_life_days:.1f} days, "
                        f"Grade: {chamber_quality}). Immediate dispatch required to avoid total asset write-off."
                    ),
                )

        if any(k in action_type for k in ("irrigat", "pump", "water")):
            # Check if microgrid can self-power to bypass peak grid cost
            microgrid_clean = context.get("microgrid_clean_power", False) or context.get("battery_soc", 0.0) >= 0.40
            if microgrid_clean:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="irrigation_pumping",
                    vote_choice="APPROVE",
                    confidence=0.92,
                    rationale=(
                        "Microgrid agrivoltaic solar and BESS battery buffer fully cover pumping demand. "
                        "Zero EVN grid peak tariff incurred; green self-consumption authorized."
                    )
                )

            if tariff_tier == "peak" and urgency != "critical":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="irrigation_pumping",
                    vote_choice="REJECT",
                    confidence=0.88,
                    rationale=(
                        f"Current electricity tier is PEAK ({self.TARIFF_RATES['peak']:,.0f} VND/kWh). "
                        f"Irrigation is non-critical ({urgency}); deferring will save ~63% in pumping power costs."
                    )
                )

        # Greenhouse CO2 enrichment economic veto and ROI validation
        if any(k in action_type for k in ("co2_enrichment", "co2_injection", "co2_dosing")):
            vents_open = context.get("roof_vent_pct", 0.0) > 50.0
            roi = context.get("projected_roi", 2.5)
            if vents_open:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="greenhouse_economics",
                    vote_choice="REJECT",
                    confidence=0.95,
                    rationale="CO2 ECONOMIC VETO: Roof vents >50% open causes atmospheric gas dissipation. Liquid CO2 capital will be lost with negative ROI.",
                )
            if roi < 1.0 or not context.get("is_profitable", True):
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="greenhouse_economics",
                    vote_choice="REJECT",
                    confidence=0.92,
                    rationale=f"CO2 ECONOMIC VETO: Projected return on investment (ROI {roi}x) fails to cover liquid CO2 input costs.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="greenhouse_economics",
                vote_choice="APPROVE",
                confidence=0.93,
                rationale=f"Market agent approves CO2 enrichment: projected yield uplift generates positive ROI ({roi}x).",
            )

        # Solar RO Desalination economic evaluation & peak tariff avoidance
        if any(k in action_type for k in ("desalination", "ro_membrane", "ro_pump")):
            is_solar = context.get("is_solar_powered", False) or context.get("solar_available_kw", 0.0) >= 2.0
            if is_solar:
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="water_economics",
                    vote_choice="APPROVE",
                    confidence=0.96,
                    rationale="Solar array generates sufficient surplus power for RO desalination. Zero grid power cost incurred.",
                )
            if tariff_tier == "peak" and urgency != "critical":
                return DebateVote(
                    agent_id=self.agent_id,
                    topic="water_economics",
                    vote_choice="REJECT",
                    confidence=0.92,
                    rationale=f"RO ECONOMIC VETO: Peak electricity tariff active ({self.TARIFF_RATES['peak']:,.0f} VND/kWh) without solar offset. Defer RO batch to midday.",
                )
            return DebateVote(
                agent_id=self.agent_id,
                topic="water_economics",
                vote_choice="APPROVE",
                confidence=0.90,
                rationale="RO desalination cost is lower than hauled municipal water.",
            )

        # Biological pest control vs chemical pesticide export premium veto
        if any(k in action_type for k in ("chemical_spray", "pesticide_spray")) and context.get("export_grade", True):
            crop = context.get("crop_type", "Strawberries")
            return DebateVote(
                agent_id=self.agent_id,
                topic="crop_export_economics",
                vote_choice="REJECT",
                confidence=0.96,
                rationale=(
                    f"MARKET EXPORT VETO: Chemical spraying on export-grade {crop} triggers chemical residue "
                    f"withholding and forfeits the 25% organic export premium. Deploy biological control instead."
                ),
            )

        # Aquaponic dual harvest scheduling endorsement
        if any(k in action_type for k in ("aquaponics_harvest", "dual_harvest", "fish_harvest")):
            return DebateVote(
                agent_id=self.agent_id,
                topic="aquaponics_economics",
                vote_choice="APPROVE",
                confidence=0.95,
                rationale="Market agent strongly endorses aquaponic dual-harvest: simultaneous monetization of fish protein and premium zero-residue leafy greens.",
            )

        return DebateVote(
            agent_id=self.agent_id,
            topic="farm_operation",
            vote_choice="APPROVE",
            confidence=0.85,
            rationale="Proposed action aligns with farm economic viability and energy budget constraints."
        )
