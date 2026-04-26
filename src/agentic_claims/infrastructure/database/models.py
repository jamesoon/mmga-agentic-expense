"""SQLAlchemy ORM models for expense claims database."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Claim(Base):
    """Expense claim aggregate root."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claimNumber: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, name="claim_number"
    )
    employeeId: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, name="employee_id"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    totalAmount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, name="total_amount"
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="SGD"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, name="category"
    )
    # Dual currency support (original currency + converted SGD)
    originalCurrency: Mapped[Optional[str]] = mapped_column(
        String(3), nullable=True, name="original_currency"
    )
    originalAmount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, name="original_amount"
    )
    convertedAmountSgd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, name="converted_amount_sgd"
    )
    # Agent output columns (Phase 8)
    complianceFindings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, name="compliance_findings"
    )
    fraudFindings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, name="fraud_findings"
    )
    advisorDecision: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, name="advisor_decision"
    )
    advisorFindings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, name="advisor_findings"
    )
    approvedBy: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, name="approved_by"
    )
    userJustification: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, name="user_justification"
    )

    submissionDate: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, name="submission_date"
    )
    approvalDate: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, name="approval_date"
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), name="created_at"
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        name="updated_at",
    )

    # Relationships
    receipts: Mapped[list["Receipt"]] = relationship(
        "Receipt", back_populates="claim", cascade="all, delete-orphan"
    )
    auditLogs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="claim", cascade="all, delete-orphan"
    )


class Receipt(Base):
    """Receipt entity with line items stored as JSON."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claimId: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True, name="claim_id"
    )
    receiptNumber: Mapped[str] = mapped_column(String(50), nullable=False, name="receipt_number")
    merchant: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    totalAmount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, name="total_amount"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Dual currency support (original currency + converted SGD)
    originalCurrency: Mapped[Optional[str]] = mapped_column(
        String(3), nullable=True, name="original_currency"
    )
    originalAmount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, name="original_amount"
    )
    convertedAmountSgd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, name="converted_amount_sgd"
    )
    imagePath: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="image_path")
    lineItems: Mapped[dict] = mapped_column(JSONB, nullable=False, name="line_items")
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), name="created_at"
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        name="updated_at",
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="receipts")


class AuditLog(Base):
    """Audit trail for claim modifications."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claimId: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True, name="claim_id"
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    oldValue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="old_value")
    newValue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="new_value")
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="auditLogs")


class User(Base):
    """Application user with role-based access."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    hashedPassword: Mapped[str] = mapped_column(
        String(255), nullable=False, name="hashed_password"
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    employeeId: Mapped[str] = mapped_column(
        String(50), nullable=False, name="employee_id"
    )
    displayName: Mapped[str] = mapped_column(
        String(100), nullable=False, name="display_name"
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), name="created_at"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, name="email"
    )
    cognitoSub: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True, name="cognito_sub"
    )


class UserQuotaUsage(Base):
    """Per-user daily quota counters (Spec A B8)."""

    __tablename__ = "user_quota_usage"

    userId: Mapped[int] = mapped_column(Integer, primary_key=True, name="user_id")
    quotaDate: Mapped[date] = mapped_column(Date, primary_key=True, name="date")
    submissions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class EvalRun(Base):
    """Spec B — eval harness run (index row)."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    startedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), name="started_at"
    )
    finishedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, name="finished_at"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    gitSha: Mapped[str] = mapped_column(String(40), nullable=False, name="git_sha")
    judgeModel: Mapped[str] = mapped_column(String(100), nullable=False, name="judge_model")
    verifierModel: Mapped[str] = mapped_column(String(100), nullable=False, name="verifier_model")
    configJson: Mapped[dict] = mapped_column(JSONB, nullable=False, name="config_json")
    resultsPath: Mapped[str] = mapped_column(String(500), nullable=False, name="results_path")
    summaryJson: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, name="summary_json")
    triggeredBy: Mapped[str] = mapped_column(String(200), nullable=False, name="triggered_by")


class EvalJudgment(Base):
    """Spec B — per-benchmark per-pipeline judgment row."""

    __tablename__ = "eval_judgments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    runId: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False, index=True, name="run_id",
    )
    benchmarkId: Mapped[str] = mapped_column(String(20), nullable=False, index=True, name="benchmark_id")
    pipeline: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    selfConsistencyRuns: Mapped[list] = mapped_column(JSONB, nullable=False, name="self_consistency_runs")
    consistencyScore: Mapped[float] = mapped_column(Float, nullable=False, name="consistency_score")
    crossModalVerdict: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, name="cross_modal_verdict")
    crossModalAgree: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, name="cross_modal_agree")
    primaryJudgeScore: Mapped[float] = mapped_column(Float, nullable=False, name="primary_judge_score")
    verifierJudgeScore: Mapped[float] = mapped_column(Float, nullable=False, name="verifier_judge_score")
    verifierAgree: Mapped[bool] = mapped_column(Boolean, nullable=False, name="verifier_agree")
    disagreementScore: Mapped[float] = mapped_column(
        Float, nullable=False, index=True, name="disagreement_score"
    )
    costUsd: Mapped[float] = mapped_column(Float, nullable=False, name="cost_usd")
    reasoningDigest: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="reasoning_digest")
