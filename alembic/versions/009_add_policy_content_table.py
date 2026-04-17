"""Add policy_content table for user-editable policy sections.

Revision ID: 009
Revises: 008
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("section_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(100), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_key"),
    )

    op.create_index("ix_policy_content_category", "policy_content", ["category"])

    # Seed user-editable policy sections
    conn = op.get_bind()
    conn.execute(text("""
        INSERT INTO policy_content (category, section_key, title, content, updated_by) VALUES

        -- ─── MEALS ─────────────────────────────────────────────────────────────────
        ('meals', 'meals.daily_caps', 'Daily Meal Caps',
        '## Meal Daily Caps

Maximum reimbursable amounts per person per meal:

- **Breakfast**: SGD 15.00 per person
- **Lunch**: SGD 20.00 per person
- **Dinner**: SGD 30.00 per person
- **Total daily cap**: SGD 50.00 per person (sum of all meals in one calendar day)

Claims exceeding the total daily cap of SGD 50 will be rejected unless pre-approved by department head for exceptional circumstances.

Breakfast claims must include receipt showing date, time, and itemized list if total exceeds SGD 10. Lunch and dinner claims require itemized breakdown if above SGD 15 and SGD 20 respectively.', 'system'),

        ('meals', 'meals.business_entertainment', 'Business Meal Entertainment Rules',
        '## Business Meal Entertainment

Business meals involving external guests or clients:

- **Pre-approval required** for meals exceeding SGD 100 total (all attendees combined). Submit Expense Pre-Approval Form (EPF-01) at least 3 business days prior.
- **Maximum 8 attendees** per business meal. More than 8 requires written justification and VP-level approval.
- **Gratuity**: Service charges and gratuity reimbursable up to 15% of pre-tax meal cost. Tips exceeding 15% require written justification.
- **Documentation required**: Original itemized receipt, list of attendees with names and affiliations, brief description of business purpose. For claims above SGD 200: meeting agenda or formal invitation.', 'system'),

        ('meals', 'meals.overseas_allowances', 'Overseas Meal Allowances',
        '## Overseas Meal Allowances

For approved international travel, meal caps are adjusted with an overseas multiplier of **1.5x domestic caps**:

- Breakfast: SGD 22.50
- Lunch: SGD 30.00
- Dinner: SGD 45.00
- Total daily cap: SGD 75.00

Overseas allowance applies to destinations listed in the University Travel Destination Register. For unlisted destinations, contact Finance for per diem rates.', 'system'),

        -- ─── GENERAL ───────────────────────────────────────────────────────────────
        ('general', 'general.approval_thresholds', 'Approval Thresholds',
        '## Approval Thresholds

Expense claims are subject to tiered approval based on total claim amount:

- **Under SGD 200**: Auto-approved if all policy requirements are met, no red flags, and within 30-day deadline. Processed within 3-5 business days.
- **SGD 200 – SGD 1,000**: Requires line manager approval within 5 business days.
- **Over SGD 1,000**: Requires department head approval within 7 business days.
- **Exception approvals**: Claims that violate policy caps (meal over daily cap, taxi over single-trip cap, hotel over tier cap) require Expense Override Form (EOF-04) regardless of total amount, routed to department head or VP.', 'system'),

        ('general', 'general.appeals', 'Appeals Process',
        '## Appeals Process

Employees may appeal rejected claims within **14 calendar days** of rejection notification.

To appeal: Submit Appeal Request Form (ARF-10) via expense portal with original claim reference number, explanation of why rejection should be overturned, and additional supporting evidence.

Appeal review timeline: 10 business days from submission.

**Outcomes**: Approved (reinstated), Partially Approved (reduced amount), or Denied (final, no further appeals).

Appeals are most successful for: lost receipt claims with strong supporting evidence, policy interpretation ambiguity, documented extenuating circumstances. Appeals are rarely successful for late submission (30-day deadline is non-negotiable) or deliberate policy violations.', 'system'),

        -- ─── TRANSPORT ─────────────────────────────────────────────────────────────
        ('transport', 'transport.caps', 'Transport Per-Trip Caps',
        '## Transport Per-Trip Caps and Reimbursement Rates

- **MRT/Bus**: Actual fare, no cap
- **Taxi/Grab (single trip)**: Maximum SGD 40 per trip. Trips exceeding SGD 40 require written justification.
- **Private car mileage**: SGD 0.60 per kilometer
- **Taxi between 11 PM – 6 AM (late-night surcharge)**: Reimbursable at actual fare up to SGD 60 per trip
- **Airport transfers**: Maximum SGD 50 per trip (to/from Singapore Changi Airport)

For ride-hail services, GrabShare or equivalent shared ride is required when traveling alone. Standard (non-shared) ride is reimbursable when shared option is unavailable or justified.', 'system'),

        -- ─── ACCOMMODATION ─────────────────────────────────────────────────────────
        ('accommodation', 'accommodation.rate_caps', 'Nightly Rate Caps by Destination',
        '## Nightly Rate Caps by Destination Tier

All accommodation reimbursements are subject to nightly rate caps (excluding taxes):

| Destination | Cap per Night |
|-------------|--------------|
| Singapore (domestic) | SGD 250 |
| Southeast Asia (MY, ID, TH, VN, PH, etc.) | SGD 200 |
| Northeast Asia (JP, KR, CN, HK, TW) | SGD 300 |
| Australia / New Zealand | SGD 280 |
| Europe / UK | SGD 350 |
| North America (US, CA) | SGD 350 |
| Other destinations | SGD 250 |

GST and mandatory service charges are reimbursable on top of the nightly cap. Claims exceeding these caps require department head written approval before booking.', 'system'),

        ('accommodation', 'accommodation.eligibility', 'Overnight Stay Eligibility',
        '## Overnight Stay Eligibility

Accommodation is eligible when:
- Business destination is more than **80 kilometers** from the employee primary workplace (SUTD campus) or registered home address, OR
- A business event ends after **10:00 PM** and returning home is impractical or unsafe

For multi-day conferences or training programs, accommodation is automatically eligible for the event duration plus one travel night before and one after.

For destinations within 80 km, department head written approval is required with justification (e.g., early morning meeting requiring arrival the night before).', 'system'),

        -- ─── OFFICE SUPPLIES ───────────────────────────────────────────────────────
        ('office_supplies', 'office_supplies.caps', 'Per-Item and Category Caps',
        '## Office Supplies Caps and Limits

- **Per-item cap**: SGD 100 per single item. Items above SGD 100 must use university procurement process.
- **Software licenses**: Annual cost must be under SGD 50. Must be required for a specific business task and not available via university IT licensing.
- **Single-transaction cap**: SGD 300 aggregate per transaction. Purchases exceeding SGD 300 require department head approval via Purchase Pre-Approval Form (PPF-05).
- **Annual limit per employee**: SGD 500 per fiscal year for miscellaneous office supplies reimbursed via personal claim. Exceeding this limit requires department head approval.

Approved categories include: stationery, external printing services, business cards, batteries, USB drives and adapters (under per-item cap), event name tags and lanyards.', 'system')
    """))


def downgrade() -> None:
    op.drop_index("ix_policy_content_category", table_name="policy_content")
    op.drop_table("policy_content")
