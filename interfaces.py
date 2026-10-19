"""Contrato público e inmutable de LOG-8092.

Este fichero es de solo lectura durante la prueba. La implementación del motor
inyecta una fachada que satisface ``CarrierService``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Protocol, Sequence, Tuple


SPEC_VERSION = "0.4.0"


@dataclass(frozen=True, slots=True)
class ZonePrice:
    zone: str
    surcharge_cents: int


@dataclass(frozen=True, slots=True)
class ActiveUpgrade:
    upgrade_type: str
    quantity: int


@dataclass(frozen=True, slots=True)
class Shipment:
    shipment_id: str
    available_at: datetime
    ready_at: datetime
    sla_deadline: datetime
    product: str
    zone: str
    delivery_cluster_id: str
    is_metal: bool
    state: str
    attempt_number: int
    required_capabilities: Tuple[str, ...] = ()
    retry_eligible_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class CarrierSnapshot:
    carrier_id: str
    allowed_zones: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    supported_upgrades: Tuple[str, ...]
    available_units: int
    base_total_units: int
    total_units: int
    retiring_units: int
    base_batch_capacity: int
    batch_capacity: int
    pickup_minutes: int
    speed_kmh: int
    speed_multiplier_bps: int
    base_fee_cents: int
    zone_prices: Tuple[ZonePrice, ...]
    night_multiplier_bps: int
    holiday_multiplier_bps: int
    current_time_multiplier_bps: int
    operates_now: bool
    next_available_at: Optional[datetime]
    operational_failure_bps: int
    rolling_success_rate_bps: Optional[int]
    active_upgrades: Tuple[ActiveUpgrade, ...]


@dataclass(frozen=True, slots=True)
class FailureAttemptRate:
    attempt_number: int
    customer_absence_bps: int


@dataclass(frozen=True, slots=True)
class FailureZoneProfile:
    zone: str
    absence_modifier_bps: int
    inaccessible_route_bps: int


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    attempts: Tuple[FailureAttemptRate, ...]
    zones: Tuple[FailureZoneProfile, ...]
    sunday_operation_modifier_bps: int
    holiday_operation_modifier_bps: int


@dataclass(frozen=True, slots=True)
class ScenarioCalendar:
    timezone: str
    holidays: Tuple[date, ...]


@dataclass(frozen=True, slots=True)
class RcpExpectationRange:
    product: str
    min_full_satisfaction_ratio_bps: int
    max_full_satisfaction_ratio_bps: int


@dataclass(frozen=True, slots=True)
class RcpAudienceProfile:
    audience: str
    base_response_bps: int
    dissatisfaction_uplift_bps: int
    impact_weight_bps: int


@dataclass(frozen=True, slots=True)
class RcpPolicy:
    influencer_rate_bps: int
    undelivered_rating: int
    delivered_floor_rating: int
    on_time_boundary_rating: int
    late_floor_ratio_bps: int
    expectations: Tuple[RcpExpectationRange, ...]
    audiences: Tuple[RcpAudienceProfile, ...]


@dataclass(frozen=True, slots=True)
class ZoneDistance:
    zone: str
    distance_km: int


@dataclass(frozen=True, slots=True)
class SlaDefinition:
    product: str
    duration_minutes: int
    clock: str
    days: Tuple[int, ...]
    open: str
    close: str


@dataclass(frozen=True, slots=True)
class UpgradeDefinition:
    upgrade_type: str
    cost_cents: int
    max_per_carrier_period: int
    multiplier_bps: Optional[int] = None


@dataclass(frozen=True, slots=True)
class PricingPolicy:
    additional_card_cents: int
    metal_security_cents: int
    terminal_penalty_cents: int
    attempt_multipliers_bps: Tuple[int, ...]
    max_voluntary_hold_minutes: int
    dispatch_tick_minutes: int


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    admission_days: int
    distances: Tuple[ZoneDistance, ...]
    sla: Tuple[SlaDefinition, ...]
    upgrades: Tuple[UpgradeDefinition, ...]
    pricing: PricingPolicy


@dataclass(frozen=True, slots=True)
class DispatchContext:
    now: datetime
    reference_budget_cents: int
    spent_cents: int
    contingency_threshold_cents: int
    carriers: Tuple[CarrierSnapshot, ...]
    calendar: ScenarioCalendar
    failure_policy: FailurePolicy
    rcp_policy: RcpPolicy
    decision_policy: Optional[DecisionPolicy] = None


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    accepted: bool
    carrier_id: str
    shipment_ids: Tuple[str, ...]
    dispatched_at: datetime
    charged_cost_cents: int
    batch_id: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class DeliveryAttemptResult:
    shipment: Shipment
    carrier_id: str
    batch_id: str
    attempt_number: int
    occurred_at: datetime
    terminal: bool
    failure_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class FleetUpgradeDecision:
    carrier_id: str
    upgrade_type: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class MonthlyPlanningContext:
    now: datetime
    period_index: int
    reference_budget_cents: int
    spent_cents: int
    contingency_threshold_cents: int
    carriers: Tuple[CarrierSnapshot, ...]
    calendar: ScenarioCalendar
    failure_policy: FailurePolicy
    rcp_policy: RcpPolicy
    upgrades_enabled: bool = True
    decision_policy: Optional[DecisionPolicy] = None


class CarrierService(Protocol):
    def snapshot(self) -> Tuple[CarrierSnapshot, ...]:
        """Devuelve el estado inmutable de todos los transportistas."""

    def dispatch_batch(
        self, carrier_id: str, shipment_ids: Sequence[str]
    ) -> DispatchReceipt:
        """Intenta aceptar atómicamente un lote en el instante simulado actual."""


class BaseDispatcherStrategy(ABC):
    """Única extensión ejecutada por el evaluador."""

    def __init__(self, carrier_service: CarrierService) -> None:
        self._carrier_service = carrier_service

    @property
    def carrier_service(self) -> CarrierService:
        return self._carrier_service

    @abstractmethod
    def on_shipments_available(
        self, now: datetime, shipments: Tuple[Shipment, ...]
    ) -> None:
        """Recibe un bloque cronológico de nuevos envíos."""

    @abstractmethod
    def on_dispatch_tick(self, context: DispatchContext) -> None:
        """Ofrece una oportunidad periódica de despacho."""

    @abstractmethod
    def on_delivery_succeeded(self, result: DeliveryAttemptResult) -> None:
        """Notifica una entrega terminal satisfactoria."""

    @abstractmethod
    def on_delivery_failed(self, result: DeliveryAttemptResult) -> None:
        """Notifica un intento fallido, terminal o reintentable."""

    @abstractmethod
    def on_monthly_planning(
        self, context: MonthlyPlanningContext
    ) -> Tuple[FleetUpgradeDecision, ...]:
        """Devuelve decisiones de arrendamiento para el nuevo periodo."""