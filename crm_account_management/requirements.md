# Pneumac CRM / Account Management

## Changelog

### v18.0.2.0.0 (2026-03-02) - Phase 2.1 Complete

**Features Implemented:**
- ✅ Full product list with sort-by-name/qty/amount (replaces top-12 limitation)
- ✅ Yearly period option on buying trends chart
- ✅ Drill-down on all dashboard numbers: YTD, rolling 12M, quotations, orders, opportunities
- ✅ Drill-down on chart bars (click bar → filtered invoice list for that period)
- ✅ Drill-down on product table rows (click product → filtered sale orders)
- ✅ Per-OU configurable fiscal year start date (overrides company default)
- ✅ Average gross profit % on dashboard
- ✅ Remaining-to-invoice amount on Open Orders row
- ✅ Test suite reorganized into per-user-story files (test_us01 through test_us20)

**Technical:**
- JS widget uses `actionService.doAction` for client-side navigation from chart/table clicks
- Action methods returning raw dicts include `"views"` key (required by `call_kw` vs `call_button` difference)
- `fiscal_year_start_date` added to `@api.depends` for all YTD computed fields
- `open_orders_to_invoice_amount` computed by subtracting posted invoices from open order totals

**Bug Fixes:**
- `fiscal_year_start_date` per-OU override now correctly used in `_get_fiscal_year_start()`
- Odoo 18: `mail.activity.create()` requires `res_model_id` (NOT NULL)
- Odoo 18: `sale.order.action_confirm()` resets `date_order`; restored in tests
- Rolling 12M drill-down correctly links to invoices (not sale orders), consistent with metric source

---

### v18.0.1.0.0 (2026-01-30) - Phase 1 Complete

**Features Implemented:**
- ✅ US-01: Customer Account Dashboard (YTD fiscal sales, rolling 12M, quotations, orders, opportunities)
- ✅ US-02: Buying Trends widget (sales chart, top products)
- ✅ US-04: Account-Level Chatter
- ✅ US-05: Auto-Create OU for Top-Level Company Partners (with salesperson sync)
- ✅ US-08: View OU Structure (partner aggregation, hierarchy rollup)
- ✅ US-09: View Partner's OUs (navigation button on partner form)
- ✅ US-19: Annual Review PDF Report
- ✅ US-20: Top Products View

**Technical:**
- Stored computed fields with dotted dependencies for real-time updates
- Nightly cron job to refresh all metrics
- Search filters: Has YTD Sales, YTD Growth/Decline, Open Quotations/Orders/Opportunities
- 95% test coverage on models
- French translation (i18n/fr.po)

**Bug Fixes:**
- Odoo 18 compatibility (tree→list views, post_init_hook signature, QWeb td restrictions)
- Sales metrics use `amount_total` (not `amount_total_signed`)
- Fiscal year support (company fiscalyear_last_month/day)
- Percentage fields stored as decimals for percentage widget
- Open orders exclude fully invoiced AND fully delivered

---

## Problem Statement

Pneumac would like a better set of functionality for doing account management in Odoo.

### Pain Points

- Salespeople cannot see, at a glance, the buying trends of their clients, their payment
  history, sales history vs last year/period, and a general chatter for the whole customer
  account rather than just by individual contact.
- It's difficult for managers to track the activity of sales reps: contacts done, # of clients
  contacted, visited, whatever over a given period.
- It's hard for someone to take over when a rep is away on vacation because the customer
  history is a bit all over the place (including in emails).

### Inspiration (TGWT)

- A quick "dashboard" view for each customer account showing YTD sales vs last year,
  budget for the year (optional, not yet implemented at TGWT), open quotations $ vs won,
  open orders $ and count, opportunities $ + won $.
- A report printed for an annual review with customer, detailing their buying trends,
  highlighting top products.

### Additional Ideas

- Highlight top products for each customer AND products purchased by companies in their
  industry.

---

## Requirements

### Core Requirements

1. **Customer Account entity**: A grouping construct for partners that enables account-level views and metrics
2. **Automatic account creation**: Every top-level company partner automatically gets an account (no manual step)
3. **Flexible grouping**: Partners can be grouped in ways independent of Odoo's partner parent/child hierarchy
4. **Hierarchical accounts**: Accounts can contain other accounts (for corporate structures with subsidiaries)
5. **Sub-groupings**: Ability to create sub-groups within an account (departments, divisions) without creating new partners
6. **Internationalization**: Interface available in English (default) and French (via translation)

### Dashboard Requirements

7. **Single-page view**: Dashboard metrics and chatter on one scrollable page (no tabs)
8. **Key metrics**: YTD sales vs prior year, open quotations (count/$), won quotations, open orders (count/$), opportunities (open/won)
9. **Aggregation**: Metrics aggregate from all partners in the account, including child accounts (recursive)

### Partner Organization Requirements

10. **Implicit membership**: A company's contacts and addresses are implicitly part of its account
11. **Explicit membership**: Contacts/addresses can be explicitly added to sub-groups within an account
12. **View contacts by group**: On a partner form, display contacts grouped by their sub-group membership

### Account Manager Requirements

13. **Account ownership**: Accounts should have an assigned account manager (for CRM purposes)
14. **Ownership logic**: When multiple companies are in an account, set owner from first company added; sync when only one company

### Manager Oversight Requirements

15. **Account-level activity metrics**: On each account, show activity counts (calls, emails, meetings), last activity date, and activity trend
16. **Account health indicators**: On each account, show sales trend (up/down vs prior period), payment trend, order frequency vs historical
17. **Inactive account identification**: Ability to filter/list accounts with no activity in X days (configurable threshold)
18. **At-risk account identification**: Ability to identify accounts with declining sales, overdue payments, or no recent orders
19. **Portfolio-level dashboard**: Aggregate view of all accounts (or filtered subset) showing total activity, inactive count, at-risk count, revenue trends
20. **Rep activity report**: Per-rep metrics showing # of accounts contacted, # of activities logged, # of visits (if tracked), filterable by date range
21. **Rep comparison view**: Side-by-side comparison of rep performance (activity levels, account coverage, outcomes)
22. **Drill-down capability**: From aggregate/rep views, ability to drill down to specific accounts
23. **Goal setting**: Ability to set activity/outcome goals for reps (e.g., # of contacts per week, # of accounts visited per month)
24. **Goal tracking**: Track progress against goals, show % complete, highlight reps behind/ahead of target

### Future Considerations

25. **OU as selector**: Accounts could be used on sales orders/invoices to discriminate shipping/billing addresses

---

## User Stories

### Account Dashboard & Visibility

**US-01: View Customer Account Dashboard**
As a salesperson, I want to see a dashboard for each customer account showing key metrics at a glance, so I can quickly understand the health and activity of the account.

Acceptance Criteria:
- Dashboard displays YTD sales $ vs same period last year
- Dashboard displays open quotations count and $
- Dashboard displays won quotations count and $ (current period)
- Dashboard displays open sales orders count and $
- Dashboard displays open opportunities count and $ vs won opportunities
- Metrics are calculated from all partners linked to the account
- Dashboard and chatter appear on a single scrollable page (no tabs)

**US-02: View Buying Trends**
As a salesperson, I want to see buying trends for a customer account, so I can identify patterns and opportunities.

Acceptance Criteria:
- Show sales by month/quarter over time (graph)
- Compare current period to prior year
- Identify top products purchased by this account

**US-03: View Payment History**
As a salesperson, I want to see payment behavior for a customer account, so I can assess credit risk and follow up appropriately.

Acceptance Criteria:
- Show average days to pay
- Show overdue invoices count and $
- Show payment trend (improving/worsening)

**US-04: Account-Level Chatter**
As a salesperson, I want a chatter/notes section on the customer account, so I can record account-level notes and communications that aren't specific to a single contact.

Acceptance Criteria:
- Customer account has its own chatter thread
- Can log notes, schedule activities
- Chatter is separate from individual partner chatters

### Account Structure

**US-05: Auto-Create OU for Top-Level Company Partners**
As a system, when a top-level partner (`parent_id=False`, `is_company=True`) is created, an Organizational Unit is automatically created that the partner "owns".

Acceptance Criteria:
- OU is created automatically when top-level company partner is created
- OU name defaults to partner name
- Partner's children (contacts, addresses) are implicitly members of its OU
- No manual action required for the common case

**US-06: Create Sub-OUs Within an OU**
As a salesperson, I want to create sub-OUs within a company's OU (e.g., departments, divisions), so I can organize contacts and addresses into logical groupings.

Acceptance Criteria:
- Can create unowned OUs with a parent OU
- Unowned OUs must have a parent OU (constraint)
- Can add partner children (contacts, addresses) as explicit members of sub-OUs
- Sub-OUs inherit from parent OU for aggregation purposes

**US-07: Nest OUs to Model Corporate Structure**
As a salesperson, I want to add one company's OU as a child of another company's OU, so I can model corporate hierarchies (e.g., subsidiaries, regional offices).

Acceptance Criteria:
- Can set an owned OU's parent to another OU
- Metrics aggregate recursively through OU hierarchy
- Example: "Montreal Brewery" OU is child of "Molson Coors Canada" OU

**US-08: View OU Structure**
As a salesperson, I want to see the full structure of an OU (child OUs, member partners), so I can understand the organization.

Acceptance Criteria:
- OU form shows child OUs (hierarchy)
- OU form shows member partners (contacts, addresses)
- Shows owning partner if applicable
- Can navigate to child OUs and member partners

**US-09: View Partner's OUs**
As a salesperson, I want to see which OUs a partner belongs to, so I can navigate to the account view.

Acceptance Criteria:
- Partner form shows the OU it owns (if top-level company)
- Partner form shows OUs it is a member of (if contact/address)
- Can click through to OU form/dashboard

**US-10: View Contacts Grouped by OU**
As a salesperson, I want to see a company's contacts grouped by the sub-OUs they belong to, so I can understand the internal structure.

Acceptance Criteria:
- On partner form, contacts are displayed grouped by OU membership
- Contacts not in any sub-OU shown in a default group
- Can expand/collapse OU groups

### Manager Oversight

**US-11: Track Sales Rep Activity**
As a sales manager, I want to see activity metrics for my sales reps, so I can monitor engagement with customers.

Acceptance Criteria:
- Report/dashboard showing per-rep: # of accounts contacted, # of activities logged, # of visits (if tracked)
- Filterable by date range
- Can drill down to see which accounts were contacted

**US-12: Identify Inactive Accounts**
As a sales manager, I want to identify customer accounts with no recent activity, so I can ensure they aren't being neglected.

Acceptance Criteria:
- List/filter accounts by "last activity date"
- Highlight accounts with no activity in X days (configurable)

**US-13: Identify At-Risk Accounts**
As a sales manager, I want to identify accounts showing warning signs (declining sales, overdue payments, no recent orders), so I can intervene proactively.

Acceptance Criteria:
- Filter/list accounts by risk indicators
- Show accounts with declining sales trend vs prior period
- Show accounts with overdue invoices
- Show accounts with no orders in X days

**US-14: View Portfolio Dashboard**
As a sales manager, I want to see an aggregate dashboard of all customer accounts, so I can understand overall portfolio health.

Acceptance Criteria:
- Total active accounts, inactive count, at-risk count
- Total revenue and trend vs prior period
- Total activities logged across all accounts
- Filterable by rep, region, industry, or other criteria

**US-15: Compare Rep Performance**
As a sales manager, I want to compare performance across my sales reps, so I can identify coaching opportunities and recognize top performers.

Acceptance Criteria:
- Side-by-side view of reps showing activity counts, account coverage, revenue
- Sortable by any metric
- Filterable by date range
- Visual indicators for above/below average performance

**US-16: Set Rep Goals**
As a sales manager, I want to set activity and outcome goals for my sales reps, so I can establish clear expectations.

Acceptance Criteria:
- Define goals per rep (e.g., # of contacts/week, # of accounts visited/month, revenue target)
- Goals can be set for different time periods (weekly, monthly, quarterly)
- Goals can be activity-based or outcome-based

**US-17: Track Goal Progress**
As a sales manager, I want to track progress against rep goals, so I can monitor performance and intervene when needed.

Acceptance Criteria:
- Show % complete for each goal
- Visual progress indicator (on track, behind, ahead)
- Highlight reps significantly behind target
- Drill down to see contributing activities/outcomes

### Handoff & Coverage

**US-18: View Consolidated Account History**
As a salesperson covering for a colleague, I want to see a consolidated history of all interactions with a customer account, so I can quickly get up to speed.

Acceptance Criteria:
- Account form shows recent activities across all linked partners
- Shows recent emails, calls, meetings, notes
- Sorted by date, most recent first

### Reporting

**US-19: Generate Annual Review Report**
As a salesperson, I want to generate a printable annual review report for a customer account, so I can use it in customer meetings.

Acceptance Criteria:
- PDF report showing: sales summary, YoY comparison, top products, buying trends
- Can select date range (default: last 12 months)
- Branded with company logo

**US-20: View Top Products by Customer**
As a salesperson, I want to see the top products purchased by a customer account, so I can understand their buying patterns.

Acceptance Criteria:
- List of products ranked by $ or quantity
- Filterable by date range
- Shows trend (up/down vs prior period)

**US-21: Compare to Industry Peers**
As a salesperson, I want to see what products are commonly purchased by companies in the same industry, so I can identify cross-sell opportunities.

Acceptance Criteria:
- Show top products for the account's industry
- Highlight products the account hasn't purchased
- Requires industry_id to be set on linked partners

---

## Phase 1 Scope

Phase 1 focuses on **account visibility, buying history/habits, and YTD state**.

### Included User Stories

| ID | Title | Category |
|----|-------|----------|
| US-01 | View Customer Account Dashboard | Dashboard & Visibility |
| US-02 | View Buying Trends | Dashboard & Visibility |
| US-04 | Account-Level Chatter | Dashboard & Visibility |
| US-05 | Auto-Create OU for Top-Level Company Partners | Account Structure |
| US-08 | View OU Structure | Account Structure |
| US-09 | View Partner's OUs | Account Structure |
| US-19 | Generate Annual Review Report | Reporting |
| US-20 | View Top Products by Customer | Reporting |

### Phase 2: Manager Oversight & Activity Planning

| ID | Title | Category |
|----|-------|----------|
| US-11 | View Rep Activity Summary | Manager Oversight |
| US-12 | Track Contacts Made per Period | Manager Oversight |
| US-13 | Track Client Visits | Manager Oversight |
| US-14 | Set Activity Goals | Manager Oversight |
| US-15 | Compare Actual vs Goal | Manager Oversight |
| US-16 | View Team Dashboard | Manager Oversight |
| US-17 | Activity Reports | Manager Oversight |

#### Phase 2 User Stories (Detailed)

**US-11: View Rep Activity Summary**
- As a sales manager, I want to see a summary of each rep's activity (calls, emails, meetings, visits) over a period
- Acceptance: Dashboard showing activity counts by type per rep for selected date range

**US-12: Track Contacts Made per Period**
- As a sales manager, I want to see how many unique contacts each rep has reached out to
- Acceptance: Count of unique partners contacted via logged activities

**US-13: Track Client Visits**
- As a sales manager, I want to track in-person client visits separately from other activities
- Acceptance: Visit activity type with location/notes; visit count metrics

**US-14: Set Activity Goals**
- As a sales manager, I want to set monthly/quarterly targets for my team (e.g., 20 calls/week, 5 visits/month)
- Acceptance: Goal configuration per rep or team with period (weekly/monthly/quarterly)

**US-15: Compare Actual vs Goal**
- As a sales manager, I want to see how each rep is tracking against their goals
- Acceptance: Progress indicators (% of goal, on-track/behind status)

**US-16: View Team Dashboard**
- As a sales manager, I want a single view showing all my reps' performance
- Acceptance: Team overview with sortable metrics, drill-down to individual rep

**US-17: Activity Reports**
- As a sales manager, I want to generate reports on team activity for management review
- Acceptance: PDF/Excel export of activity metrics by rep, account, period

#### Phase 2 Requirements

15. **Activity tracking**: Integrate with Odoo's mail.activity for tracking calls, emails, meetings, visits
16. **Activity goals**: Model for setting targets per rep (activity type, count, period)
17. **Goal comparison**: Computed fields comparing actual activity counts to goals
18. **Manager dashboard**: Kanban/list view for managers showing team performance
19. **Activity reports**: QWeb report for activity summary by rep/period

### Deferred to Future Phases

| ID | Title | Reason |
|----|-------|--------|
| US-03 | View Payment History | Credit risk focus, not core visibility |
| US-06 | Create Sub-OUs Within an OU | Advanced organization |
| US-07 | Nest OUs to Model Corporate Structure | Advanced organization |
| US-10 | View Contacts Grouped by OU | Depends on US-06 |
| US-18 | View Consolidated Account History | Handoff/coverage feature |
| US-21 | Compare to Industry Peers | Complex, high value – prioritize for Phase 3 |

---

## Client Feedback & Phase 2 Enhancements (2026-02-11)

### New Requirements from Client Feedback

**Dashboard & Navigation Enhancements:**

1. **Full Product List with Sorting**: Replace top 12 products limitation with a sortable table showing all purchased products
2. **Yearly Graph Option**: Add "yearly" period option to the customer account dashboard graph
3. **Drill-Down Capability**: Enable clicking on dashboard numbers and graph bars to view detailed records (invoices, sales orders, etc.)
4. **Configurable Reference Date**: Allow setting reference date for dashboard calculations (calendar vs fiscal year), also used for annual reports
5. **Improved Quarterly Graph Labels**: Better month grouping indicators for quarterly view clarity

**New Metrics & Analytics:**

6. **Average Gross Profit %**: Display average gross profit percentage on customer account dashboard
7. **Comparative Analytics**: 
   - Compare metrics with other clients
   - Compare with clients buying similar products
   - Compare with clients in similar industries
8. **Payment Analytics**:
   - Average days to pay
   - Average days late
   - All metrics comparable by period and to other clients
   - Display payment terms on dashboard for reference

### Implementation Priority

**High Priority (Phase 2.1) — Complete ✅:**
- ✅ Full product list table with sorting (Req 1)
- ✅ Yearly graph option (Req 2)
- ✅ Drill-down capability: chart bars, dashboard numbers, product rows (Req 3)
- ✅ Configurable fiscal year start date per OU (Req 4)
- ✅ Average gross profit % (Req 6)

**Medium Priority (Phase 2.2) — Not started:**
- Improved quarterly labels (Req 5)
- Payment analytics: avg days to pay, overdue invoices, payment trend (Req 8)
- Basic comparative analytics (Req 7)

**Future Enhancement:**
- Advanced comparative analytics (industry peers, similar products)

---

## Open Questions

1. ~~**Time periods**: Should we support fiscal year, calendar year, rolling 12 months, or custom date ranges? (Suggest: default to calendar year with option for custom range)~~ **Resolved**: Default to company fiscal year. Future enhancement: global config parameter + per-OU override for custom fiscal year start date.

2. **Activity types**: Which activities should count for tracking? (Suggest: all standard Odoo activities – emails, calls, meetings, tasks)

3. **Report format**: PDF only, or also Excel export? (Suggest: PDF for customer-facing, Excel for internal analysis)

4. **Industry data quality**: Is `res.partner.industry_id` populated reliably? If not, US-21 may need to be deferred.

5. **Budget tracking**: Mentioned as "optional, not yet implemented" – defer to phase 2?

6. ~~**Salesperson assignment**: Should accounts have an assigned salesperson, or inherit from linked partners?~~ **Resolved**: Accounts have an assigned account manager. Set from first company added; syncs when only one company.

---

## Design

### Data Model: Organizational Units (OUs)

The requirements are implemented using an **Organizational Unit (OU)** model that addresses fundamental limitations in Odoo's partner hierarchy.

#### Design Philosophy

Odoo increasingly discourages parent-child relationships between `is_company=True` partners due to internal complexity. Our OU structure replaces that pattern:

- **Partners stay flat**: A company partner has only contacts and addresses as children (no company-under-company)
- **OUs model corporate structure**: Hierarchy is expressed via OU-contains-OU, not partner-parent-child
- **Separation of concerns**: Partners = legal/transactional entities; OUs = organizational groupings

#### OU Rules

1. **Owned OUs**: Every top-level partner (`parent_id=False`, `is_company=True`) automatically gets an OU it "owns"
   - The OU is almost synonymous with the partner itself
   - The partner's children (contacts, addresses) are implicitly members of its OU

2. **OU Hierarchy**: OUs can contain other OUs
   - Corporate structures modeled via OU containment
   - Example: "Molson Coors Canada" OU contains "Montreal Brewery" OU

3. **Unowned OUs**: OUs without an owning partner (e.g., departments, divisions)
   - Must have a parent OU (no orphaned OUs)
   - Used for sub-groupings within a company

4. **Constraint**: Every OU must have either an owning partner OR a parent OU (or both)

#### Example: Molson Coors

```
Partner: Molson Coors Canada (top-level)
  ├── contact: CEO
  └── address: HQ

Partner: Montreal Brewery (top-level)
  ├── contact: John Smith
  ├── contact: Jane Doe
  └── address: 123 Brewing St

OU Structure:
OU: "Molson Coors Canada" (owned by: Molson Coors Canada partner)
  └── OU: "Montreal Brewery" (owned by: Montreal Brewery partner)
        ├── OU: "Packaging Dept" (unowned, parent = Montreal Brewery OU)
        │     └── member: Bob (contact)
        └── OU: "Brewing Dept" (unowned, parent = Montreal Brewery OU)
              └── member: Alice (contact)
```

#### Model Fields (organizational.unit)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name (defaults to owning partner's name) |
| `owner_id` | Many2one(res.partner) | The top-level company that "owns" this OU (optional) |
| `parent_id` | Many2one(organizational.unit) | Parent OU (required if no owner_id) |
| `child_ids` | One2many | Child OUs |
| `member_ids` | Many2many(res.partner) | Explicit partner members (contacts, addresses) |
| `user_id` | Many2one(res.users) | Account manager |

#### UI Terminology

Model is generic `organizational.unit`, but displayed contextually:
- "Customer Account" in CRM
- "Vendor Account" in purchasing (future)

#### Notes

TGWT built this as a standalone module with a customer account model that links back to `res.partner` but isn't a `res.partner` itself. There is a button on the `res.partner` form to create a customer account from the partner. Our approach differs by auto-creating OUs and supporting hierarchy.
