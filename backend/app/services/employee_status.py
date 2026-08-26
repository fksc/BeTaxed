"""Company HR/Admin employee status override (DEV-837, SL-005)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps.context import CompanyContext
from app.models import Employee, Employment, EmploymentEvent
from app.services.contracts import require_hr_or_admin
from app.services.domain_events import emit_domain_event

ALLOWED_STATUS = frozenset({"ACTIVE", "ON_LEAVE", "TERMINATED"})
LEAVE_TYPES = frozenset({"PARENTAL", "SICKNESS", "UNPAID", "OTHER"})


async def override_employee_status(
    session: AsyncSession,
    ctx: CompanyContext,
    *,
    employee_id: uuid.UUID,
    status_value: str,
    effective_on: date | None = None,
    leave_type: str | None = None,
) -> Employee:
    require_hr_or_admin(ctx)
    if status_value not in ALLOWED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be ACTIVE, ON_LEAVE, or TERMINATED.",
        )
    if leave_type is not None and leave_type not in LEAVE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="leave_type must be PARENTAL, SICKNESS, UNPAID, or OTHER.",
        )

    employee = await session.get(Employee, employee_id)
    if (
        employee is None
        or employee.company_id != ctx.company.id
        or employee.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )

    if employee.status == status_value:
        if status_value == "ON_LEAVE" and leave_type is not None:
            await _amend_leave_type(
                session,
                ctx,
                employee,
                leave_type=leave_type,
                effective_on=effective_on or date.today(),
            )
        return employee

    old_status = employee.status
    source = "ADMIN" if ctx.user.user_type == "BETAXED_STAFF" else "USER"
    when = effective_on or date.today()
    leave = leave_type if status_value == "ON_LEAVE" else None
    if status_value == "ON_LEAVE" and leave is None:
        leave = "OTHER"

    open_emp = (
        await session.execute(
            select(Employment)
            .where(
                Employment.employee_id == employee.id,
                Employment.ended_on.is_(None),
            )
            .order_by(Employment.started_on.desc())
        )
    ).scalars().first()

    employee.status = status_value
    employee.status_source = source

    override = EmploymentEvent(
        company_id=ctx.company.id,
        intake_id=employee.intake_id,
        employee_id=employee.id,
        employment_id=open_emp.id if open_emp is not None else None,
        event_type="STATUS_OVERRIDE",
        effective_on=when,
        source=source,
        old_status=old_status,
        new_status=status_value,
        leave_type=leave,
    )
    session.add(override)

    if status_value == "ON_LEAVE" and old_status != "ON_LEAVE":
        session.add(
            EmploymentEvent(
                company_id=ctx.company.id,
                intake_id=employee.intake_id,
                employee_id=employee.id,
                employment_id=open_emp.id if open_emp is not None else None,
                event_type="LEAVE_STARTED",
                effective_on=when,
                source=source,
                leave_type=leave,
                old_status=old_status,
                new_status=status_value,
            )
        )
    if old_status == "ON_LEAVE" and status_value != "ON_LEAVE":
        session.add(
            EmploymentEvent(
                company_id=ctx.company.id,
                intake_id=employee.intake_id,
                employee_id=employee.id,
                employment_id=open_emp.id if open_emp is not None else None,
                event_type="LEAVE_ENDED",
                effective_on=when,
                source=source,
                old_status=old_status,
                new_status=status_value,
            )
        )

    await session.flush()
    await emit_domain_event(
        session,
        event_type="EMPLOYEE_STATUS_OVERRIDE",
        source_entity_type="EMPLOYEE",
        source_entity_id=employee.id,
        actor_id=ctx.user.id,
        company_id=ctx.company.id,
        payload={
            "employee_id": str(employee.id),
            "old_status": old_status,
            "new_status": status_value,
        },
    )
    return employee


async def _amend_leave_type(
    session: AsyncSession,
    ctx: CompanyContext,
    employee: Employee,
    *,
    leave_type: str,
    effective_on: date,
) -> None:
    last = (
        (
            await session.execute(
                select(EmploymentEvent)
                .where(
                    EmploymentEvent.employee_id == employee.id,
                    EmploymentEvent.event_type == "LEAVE_STARTED",
                )
                .order_by(EmploymentEvent.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if last is not None and last.leave_type == leave_type:
        return
    open_emp = (
        (
            await session.execute(
                select(Employment)
                .where(
                    Employment.employee_id == employee.id,
                    Employment.ended_on.is_(None),
                )
                .order_by(Employment.started_on.desc())
            )
        )
        .scalars()
        .first()
    )
    source = "ADMIN" if ctx.user.user_type == "BETAXED_STAFF" else "USER"
    session.add(
        EmploymentEvent(
            company_id=ctx.company.id,
            intake_id=employee.intake_id,
            employee_id=employee.id,
            employment_id=open_emp.id if open_emp is not None else None,
            event_type="LEAVE_STARTED",
            effective_on=effective_on,
            source=source,
            leave_type=leave_type,
            old_status="ON_LEAVE",
            new_status="ON_LEAVE",
        )
    )
    await session.flush()
