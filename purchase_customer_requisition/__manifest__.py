{
    "name": "Purchase Customer Requisition",
    "version": "1.1",
    "category": "Purchase",
    "summary": "Link customer requisition references to purchase orders",
    "description": """\
    Advanced Customer Requisition Management

    Key Features:
    - 🔗 Customer-specific requisition tracking in purchase orders
    - 👥 Multi-customer agreement management
    - 🔄 Automated price synchronization from framework contracts
    - 🔍 Optimized search via key field indexing
    - 📊 Full integration with Purchase, Sale and Stock modules

    Use Cases:
    1. Centralized management of customer procurement agreements
    2. Automated PO line referencing from customer contracts
    3. Real-time price updates from master agreements
    4. Unified purchasing/customer reporting
    """,
    "license": "LGPL-3",
    "depends": [
        "sale",
        "purchase",
        "stock",
        "purchase_requisition_stock",
        "purchase_requisition",
        "sale_purchase",
    ],
    "data": [
        "views/purchase_views.xml",
        "views/purchase_requisition_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
