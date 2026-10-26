"""Request-case pipeline. Stages and operations are data.

Revision ID: 20261026_01_request_case
Revises: 20261009_02_contract_extract_cache
Create Date: 2026-10-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261026_01_request_case"
down_revision: Union[str, None] = "20261009_02_contract_extract_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE pipeline_stage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(64) NOT NULL UNIQUE,
            name VARCHAR(128) NOT NULL,
            stage_type VARCHAR(16) NOT NULL,
            position INTEGER NOT NULL,
            entry_path VARCHAR(16),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT ck_pipeline_stage_type CHECK (
                stage_type IN ('WORK', 'WAIT_CLIENT', 'WAIT_SS', 'CLOSE_WON', 'CLOSE_LOST')
            ),
            CONSTRAINT ck_pipeline_stage_entry_path CHECK (
                entry_path IS NULL OR entry_path IN ('FIXED_TERM', 'OPEN_CONTRACT')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_pipeline_stage_entry_path
            ON pipeline_stage (entry_path)
            WHERE entry_path IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE pipeline_operation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(64) NOT NULL UNIQUE,
            name VARCHAR(128) NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE pipeline_stage_operation (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            stage_id UUID NOT NULL REFERENCES pipeline_stage(id),
            operation_id UUID NOT NULL REFERENCES pipeline_operation(id),
            next_stage_id UUID REFERENCES pipeline_stage(id),
            next_won_stage_id UUID REFERENCES pipeline_stage(id),
            next_lost_stage_id UUID REFERENCES pipeline_stage(id),
            next_claim_stage_id UUID REFERENCES pipeline_stage(id),
            UNIQUE (stage_id, operation_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE rejection_reason (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(64) NOT NULL UNIQUE,
            label VARCHAR(255) NOT NULL,
            blocks_claim BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE minuta_template (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(64) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            body_html TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE request_case (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES company(id),
            employee_id UUID NOT NULL REFERENCES employee(id),
            employment_id UUID NOT NULL REFERENCES employment(id),
            opened_by UUID NOT NULL REFERENCES user_base(id),
            opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            stage_id UUID NOT NULL REFERENCES pipeline_stage(id),
            path VARCHAR(16) NOT NULL,
            probation_ends_on DATE,
            benefit_starts_on DATE,
            applied_on DATE,
            applied_by UUID REFERENCES user_base(id),
            decision_on DATE,
            rejection_reason_id UUID REFERENCES rejection_reason(id),
            benefit_case_id UUID REFERENCES benefit_case(id),
            ss_submission_ref VARCHAR(128),
            ss_status_read_at TIMESTAMPTZ,
            closed_at TIMESTAMPTZ,
            CONSTRAINT ck_request_case_path CHECK (
                path IN ('FIXED_TERM', 'OPEN_CONTRACT')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_request_case_open_employment
            ON request_case (employment_id)
            WHERE closed_at IS NULL
        """
    )
    op.execute(
        "CREATE INDEX idx_request_case_company ON request_case (company_id)"
    )
    op.execute(
        """
        CREATE TABLE request_case_minuta (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            request_case_id UUID NOT NULL REFERENCES request_case(id),
            template_id UUID NOT NULL REFERENCES minuta_template(id),
            body_html TEXT NOT NULL,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE request_case_file (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES company(id),
            request_case_id UUID REFERENCES request_case(id),
            kind VARCHAR(32) NOT NULL,
            file_id UUID NOT NULL REFERENCES stored_file(id),
            uploaded_by UUID REFERENCES user_base(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_request_case_file_kind CHECK (
                kind IN ('SIGNED_MINUTA', 'UNFAVORABLE_NOTICE', 'CLAIM_SUPPORT')
            )
        )
        """
    )
    op.execute(
        """
        INSERT INTO pipeline_stage (code, name, stage_type, position, entry_path) VALUES
            ('probation', 'Probation', 'WORK', 10, 'OPEN_CONTRACT'),
            ('minuta', 'Minuta', 'WORK', 20, 'FIXED_TERM'),
            ('signature', 'Signature', 'WAIT_CLIENT', 30, NULL),
            ('ready', 'Ready', 'WORK', 40, NULL),
            ('awaiting_decision', 'Awaiting decision', 'WAIT_SS', 50, NULL),
            ('claim', 'Claim', 'WORK', 60, NULL),
            ('closed_approved', 'Closed approved', 'CLOSE_WON', 70, NULL),
            ('closed_rejected', 'Closed rejected', 'CLOSE_LOST', 80, NULL)
        """
    )
    op.execute(
        """
        INSERT INTO pipeline_operation (code, name) VALUES
            ('RECORD_PROBATION', 'Record probation'),
            ('GENERATE_MINUTA', 'Generate minuta'),
            ('SEND_MINUTA', 'Send minuta'),
            ('ATTACH_SIGNED_SCAN', 'Attach signed scan'),
            ('RECORD_FILING', 'Record filing'),
            ('RECORD_DECISION', 'Record decision')
        """
    )
    op.execute(
        """
        INSERT INTO pipeline_stage_operation (
            stage_id, operation_id, next_stage_id,
            next_won_stage_id, next_lost_stage_id, next_claim_stage_id
        )
        SELECT s.id, o.id, nxt.id, won.id, lost.id, claim.id
        FROM (VALUES
            ('probation', 'RECORD_PROBATION', 'ready', NULL, NULL, NULL),
            ('minuta', 'GENERATE_MINUTA', NULL, NULL, NULL, NULL),
            ('minuta', 'SEND_MINUTA', 'signature', NULL, NULL, NULL),
            ('signature', 'ATTACH_SIGNED_SCAN', 'ready', NULL, NULL, NULL),
            ('ready', 'RECORD_FILING', 'awaiting_decision', NULL, NULL, NULL),
            ('awaiting_decision', 'RECORD_DECISION', NULL, 'closed_approved', 'closed_rejected', 'claim'),
            ('claim', 'RECORD_DECISION', NULL, 'closed_approved', 'closed_rejected', NULL)
        ) AS link(stage_code, op_code, next_code, won_code, lost_code, claim_code)
        JOIN pipeline_stage s ON s.code = link.stage_code
        JOIN pipeline_operation o ON o.code = link.op_code
        LEFT JOIN pipeline_stage nxt ON nxt.code = link.next_code
        LEFT JOIN pipeline_stage won ON won.code = link.won_code
        LEFT JOIN pipeline_stage lost ON lost.code = link.lost_code
        LEFT JOIN pipeline_stage claim ON claim.code = link.claim_code
        """
    )
    op.execute(
        """
        INSERT INTO rejection_reason (code, label, blocks_claim) VALUES
            ('PRIOR_SEM_TERMO', 'The worker had another sem termo before', TRUE)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS request_case_file")
    op.execute("DROP TABLE IF EXISTS request_case_minuta")
    op.execute("DROP TABLE IF EXISTS request_case")
    op.execute("DROP TABLE IF EXISTS minuta_template")
    op.execute("DROP TABLE IF EXISTS rejection_reason")
    op.execute("DROP TABLE IF EXISTS pipeline_stage_operation")
    op.execute("DROP TABLE IF EXISTS pipeline_operation")
    op.execute("DROP TABLE IF EXISTS pipeline_stage")
