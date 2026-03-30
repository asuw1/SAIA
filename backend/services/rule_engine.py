"""Rule Engine service for SAIA V4."""

import logging
import json
import re
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
import asyncpg

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluates rules against log events."""

    def __init__(self):
        """Initialize the rule engine."""
        self.rules_cache: list[dict] = []

    async def load_rules(self, db: asyncpg.Connection) -> None:
        """
        Load all active rules from PostgreSQL into memory cache.

        Args:
            db: AsyncPG connection
        """
        try:
            rows = await db.fetch("""
                SELECT id, name, domain, clause_reference, severity, conditions, is_active
                FROM rules
                WHERE is_active = TRUE
            """)
            self.rules_cache = [dict(row) for row in rows]
            logger.info(f"Loaded {len(self.rules_cache)} active rules into cache")
        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            self.rules_cache = []

    async def evaluate_event(self, db: asyncpg.Connection, event: dict) -> list[dict]:
        """
        Evaluate all cached rules against a single event.

        Args:
            db: AsyncPG connection
            event: Normalized log event dict

        Returns:
            List of fired rules: [{"rule_id", "rule_name", "clause_reference", "severity"}, ...]
        """
        fired_rules = []

        for rule in self.rules_cache:
            try:
                conditions = rule.get("conditions", {})
                if not isinstance(conditions, dict):
                    try:
                        conditions = json.loads(conditions)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Invalid conditions for rule {rule['id']}")
                        continue

                # Check field_checks (AND logic)
                field_checks = conditions.get("field_checks", [])
                field_checks_pass = await self._check_field_conditions(
                    event, field_checks
                )

                if not field_checks_pass:
                    continue

                # Check aggregation (if present)
                aggregation = conditions.get("aggregation")
                if aggregation:
                    agg_pass = await self._check_aggregation(
                        db, event, aggregation
                    )
                    if not agg_pass:
                        continue

                # Rule fired
                fired_rules.append({
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "clause_reference": rule["clause_reference"],
                    "severity": rule["severity"],
                })

            except Exception as e:
                logger.warning(f"Error evaluating rule {rule.get('id')}: {e}")
                continue

        return fired_rules

    async def _check_field_conditions(
        self, event: dict, field_checks: list[dict]
    ) -> bool:
        """
        Check if all field conditions match the event (AND logic).

        Args:
            event: Log event
            field_checks: List of {"field", "operator", "value"} dicts

        Returns:
            True if all conditions pass
        """
        for check in field_checks:
            field = check.get("field")
            operator = check.get("operator", "eq")
            value = check.get("value")

            event_value = event.get(field)

            # Perform comparison based on operator
            if operator == "eq":
                if event_value != value:
                    return False
            elif operator == "ne":
                if event_value == value:
                    return False
            elif operator == "gt":
                try:
                    if event_value is None or float(event_value) <= float(value):
                        return False
                except (ValueError, TypeError):
                    return False
            elif operator == "lt":
                try:
                    if event_value is None or float(event_value) >= float(value):
                        return False
                except (ValueError, TypeError):
                    return False
            elif operator == "gte":
                try:
                    if event_value is None or float(event_value) < float(value):
                        return False
                except (ValueError, TypeError):
                    return False
            elif operator == "lte":
                try:
                    if event_value is None or float(event_value) > float(value):
                        return False
                except (ValueError, TypeError):
                    return False
            elif operator == "in":
                if isinstance(value, list):
                    if event_value not in value:
                        return False
                else:
                    return False
            elif operator == "contains":
                if event_value is None or value not in str(event_value):
                    return False
            elif operator == "regex":
                try:
                    if event_value is None or not re.search(value, str(event_value)):
                        return False
                except re.error:
                    logger.warning(f"Invalid regex pattern: {value}")
                    return False
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        return True

    async def _check_aggregation(
        self, db: asyncpg.Connection, event: dict, aggregation: dict
    ) -> bool:
        """
        Check aggregation condition against PostgreSQL.

        Args:
            db: AsyncPG connection
            event: Log event
            aggregation: {"group_by": [...], "window_minutes": int, "count_threshold": int}

        Returns:
            True if count exceeds threshold
        """
        try:
            group_by = aggregation.get("group_by", [])
            window_minutes = aggregation.get("window_minutes", 60)
            count_threshold = aggregation.get("count_threshold", 5)

            if not group_by:
                return False

            # Build WHERE conditions for group_by fields
            where_conditions = []
            params = []
            param_index = 1

            for field in group_by:
                value = event.get(field)
                if value is not None:
                    where_conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1
                else:
                    where_conditions.append(f"{field} IS NULL")

            # Add time window condition
            where_conditions.append(
                f"timestamp > NOW() - INTERVAL '{window_minutes} minutes'"
            )

            where_clause = " AND ".join(where_conditions)
            query = f"""
                SELECT COUNT(*) as cnt
                FROM log_events
                WHERE {where_clause}
            """

            result = await db.fetchval(query, *params)
            count = result or 0

            return count >= count_threshold

        except Exception as e:
            logger.warning(f"Error checking aggregation: {e}")
            return False

    async def dry_run(
        self, db: asyncpg.Connection, rule_conditions: dict, domain: str, limit: int = 100
    ) -> dict:
        """
        Test a rule against recent events without creating alerts.

        Args:
            db: AsyncPG connection
            rule_conditions: Rule conditions dict
            domain: Domain to test
            limit: Max events to return

        Returns:
            {"matched_count": int, "sample_matches": list[dict]}
        """
        try:
            field_checks = rule_conditions.get("field_checks", [])

            # Build WHERE conditions from field_checks
            where_conditions = ["domain = $1"]
            params = [domain]
            param_index = 2

            for check in field_checks:
                field = check.get("field")
                operator = check.get("operator", "eq")
                value = check.get("value")

                if operator == "eq":
                    where_conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "ne":
                    where_conditions.append(f"{field} != ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "gt":
                    where_conditions.append(f"{field} > ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "lt":
                    where_conditions.append(f"{field} < ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "gte":
                    where_conditions.append(f"{field} >= ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "lte":
                    where_conditions.append(f"{field} <= ${param_index}")
                    params.append(value)
                    param_index += 1
                elif operator == "in":
                    if isinstance(value, list):
                        where_conditions.append(f"{field} = ANY(${param_index})")
                        params.append(value)
                        param_index += 1
                elif operator == "contains":
                    where_conditions.append(f"{field}::text LIKE ${param_index}")
                    params.append(f"%{value}%")
                    param_index += 1
                elif operator == "regex":
                    where_conditions.append(f"{field}::text ~ ${param_index}")
                    params.append(value)
                    param_index += 1

            where_clause = " AND ".join(where_conditions)

            # Count matches
            count_query = f"""
                SELECT COUNT(*) as cnt
                FROM log_events
                WHERE {where_clause}
            """
            matched_count = await db.fetchval(count_query, *params)

            # Get sample matches
            sample_query = f"""
                SELECT id, timestamp, event_type, action, principal, resource, result
                FROM log_events
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_index}
            """
            params.append(limit)
            samples = await db.fetch(sample_query, *params)

            return {
                "matched_count": matched_count or 0,
                "sample_matches": [dict(row) for row in samples],
            }

        except Exception as e:
            logger.error(f"Error in dry_run: {e}")
            return {"matched_count": 0, "sample_matches": []}


# Global singleton instance
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Get or create the singleton rule engine instance."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
