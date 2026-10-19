"""Deadline-aware batching strategy for LOG-8092."""

from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import datetime, timedelta
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from interfaces import (
    BaseDispatcherStrategy, CarrierService, CarrierSnapshot,
    DeliveryAttemptResult, DispatchContext, FleetUpgradeDecision,
    MonthlyPlanningContext, Shipment,
)

GroupKey = Tuple[str, str, int]


class CandidateStrategy(BaseDispatcherStrategy):
    """Send compatible batches at their hold limit, prioritising SLA risk."""

    def __init__(self, carrier_service: CarrierService) -> None:
        super().__init__(carrier_service)
        self.pending: Dict[str, Shipment] = {}
        self.groups: DefaultDict[GroupKey, Dict[str, Shipment]] = defaultdict(dict)
        self.due_heap: List[Tuple[datetime, int, str]] = []
        self.scheduled_due: Dict[str, datetime] = {}
        self.sequence = 0
        self.all_historical_records: List[Shipment] = []
        self.last_carrier_by_shipment: Dict[str, str] = {}

    def on_shipments_available(self, now: datetime, shipments: Tuple[Shipment, ...]) -> None:
        for shipment in shipments:
            self.all_historical_records.append(shipment)
            self._add(shipment, shipment.ready_at + timedelta(minutes=45))

    def on_dispatch_tick(self, context: DispatchContext) -> None:
        due = self._pop_due(context.now)
        if len(context.carriers) == 1:
            due.extend(
                shipment_id for shipment_id, shipment in self.pending.items()
                if shipment.ready_at <= context.now and shipment_id not in due
            )
        if not due:
            return
        keys = {self._key(self.pending[item]) for item in due if item in self.pending}
        keys = sorted(keys, key=lambda key: min(x.sla_deadline for x in self.groups[key].values()))
        retry = timedelta(minutes=self._tick_minutes(context))
        for key in keys:
            while True:
                ready = [x for x in self.groups.get(key, {}).values() if x.ready_at <= context.now]
                if not ready:
                    break
                ready.sort(key=lambda x: (x.sla_deadline, x.shipment_id))
                choice = self._select(context, ready)
                if choice is None:
                    for shipment in ready:
                        self._schedule(shipment.shipment_id, context.now + retry)
                    break
                carrier, batch = choice
                receipt = self.carrier_service.dispatch_batch(carrier.carrier_id, tuple(x.shipment_id for x in batch))
                if not receipt.accepted:
                    for shipment in batch:
                        self._schedule(shipment.shipment_id, context.now + retry)
                    break
                for shipment in batch:
                    self.last_carrier_by_shipment[shipment.shipment_id] = carrier.carrier_id
                    self._remove(shipment.shipment_id)
                context = DispatchContext(
                    now=context.now, reference_budget_cents=context.reference_budget_cents,
                    spent_cents=context.spent_cents + receipt.charged_cost_cents,
                    contingency_threshold_cents=context.contingency_threshold_cents,
                    carriers=self.carrier_service.snapshot(), calendar=context.calendar,
                    failure_policy=context.failure_policy, rcp_policy=context.rcp_policy,
                    decision_policy=context.decision_policy,
                )

    def on_delivery_succeeded(self, result: DeliveryAttemptResult) -> None:
        self.last_carrier_by_shipment.pop(result.shipment.shipment_id, None)
        self._remove(result.shipment.shipment_id)

    def on_delivery_failed(self, result: DeliveryAttemptResult) -> None:
        self.last_carrier_by_shipment.pop(result.shipment.shipment_id, None)
        self._remove(result.shipment.shipment_id)
        if not result.terminal:
            self._add(result.shipment, result.shipment.ready_at + timedelta(minutes=45))

    def on_monthly_planning(self, context: MonthlyPlanningContext) -> Tuple[FleetUpgradeDecision, ...]:
        return ()

    def _select(self, context: DispatchContext, ready: List[Shipment]) -> Optional[Tuple[CarrierSnapshot, List[Shipment]]]:
        candidates = []
        for carrier in context.carriers:
            if not carrier.operates_now or carrier.available_units <= 0:
                continue
            if ready[0].zone not in carrier.allowed_zones:
                continue
            batch = ready[:min(carrier.batch_capacity, len(ready))]
            required = set().union(*(x.required_capabilities for x in batch))
            if not required.issubset(carrier.capabilities):
                continue
            eta = self._eta(context, carrier, batch[0].zone)
            cost = self._cost_per_card(carrier, batch)
            slack = min(int((x.sla_deadline - context.now).total_seconds() // 60) for x in batch)
            vip = any(x.product == "VIP_BLACK" for x in batch)
            score = ((eta, carrier.operational_failure_bps, cost, carrier.carrier_id)
                     if vip or slack <= eta + 180
                     else (cost, eta, carrier.operational_failure_bps, carrier.carrier_id))
            candidates.append((score, carrier, batch))
        if not candidates:
            return None
        _, carrier, batch = min(candidates, key=lambda item: item[0])
        return carrier, batch

    @staticmethod
    def _eta(context: DispatchContext, carrier: CarrierSnapshot, zone: str) -> int:
        distances = {"URBANA": 12, "SUBURBANA": 35, "RURAL": 80, "REMOTA": 150}
        if context.decision_policy is not None:
            distances.update({x.zone: x.distance_km for x in context.decision_policy.distances})
        numerator = distances[zone] * 60 * 10_000
        denominator = carrier.speed_kmh * carrier.speed_multiplier_bps
        return carrier.pickup_minutes + (numerator + denominator - 1) // denominator

    @staticmethod
    def _cost_per_card(carrier: CarrierSnapshot, batch: Iterable[Shipment]) -> int:
        cards = list(batch)
        surcharge = next((x.surcharge_cents for x in carrier.zone_prices if x.zone == cards[0].zone), 0)
        factor = (10_000, 5_000, 10_000)[min(cards[0].attempt_number, 3) - 1]
        numerator = (carrier.base_fee_cents + surcharge) * factor * carrier.current_time_multiplier_bps
        adjusted = (numerator + 50_000_000 - 1) // 100_000_000
        total = adjusted + 120 * (len(cards) - 1) + 450 * sum(x.is_metal for x in cards)
        return (total + len(cards) - 1) // len(cards)

    @staticmethod
    def _key(shipment: Shipment) -> GroupKey:
        return shipment.delivery_cluster_id, shipment.zone, shipment.attempt_number

    @staticmethod
    def _tick_minutes(context: DispatchContext) -> int:
        return context.decision_policy.pricing.dispatch_tick_minutes if context.decision_policy else 15

    def _add(self, shipment: Shipment, due: datetime) -> None:
        self.pending[shipment.shipment_id] = shipment
        self.groups[self._key(shipment)][shipment.shipment_id] = shipment
        self._schedule(shipment.shipment_id, due)

    def _remove(self, shipment_id: str) -> None:
        shipment = self.pending.pop(shipment_id, None)
        self.scheduled_due.pop(shipment_id, None)
        if shipment is None:
            return
        key = self._key(shipment)
        self.groups[key].pop(shipment_id, None)
        if not self.groups[key]:
            self.groups.pop(key, None)

    def _schedule(self, shipment_id: str, due: datetime) -> None:
        self.scheduled_due[shipment_id] = due
        self.sequence += 1
        heapq.heappush(self.due_heap, (due, self.sequence, shipment_id))

    def _pop_due(self, now: datetime) -> List[str]:
        result = []
        while self.due_heap and self.due_heap[0][0] <= now:
            due, _, shipment_id = heapq.heappop(self.due_heap)
            if self.scheduled_due.get(shipment_id) == due and shipment_id in self.pending:
                result.append(shipment_id)
        return result
