/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class BuyingTrendsWidget extends Component {
    static template = "crm_account_management.BuyingTrendsWidget";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            salesData: [],
            topProducts: [],
            loading: true,
            period: "month",
            productPeriod: "12m",
            sortBy: "total_amount",
            productsError: "",
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadData();
        });

        onWillDestroy(() => {
            if (this.chart) {
                this.chart.destroy();
                this.chart = null;
            }
        });
    }

    _getProductDateRange() {
        const now = new Date();
        let dateFrom = null;
        let dateTo = now.toISOString().split("T")[0];
        if (this.state.productPeriod === "12m") {
            const from = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
            dateFrom = from.toISOString().split("T")[0];
        }
        // "all" → dateFrom stays null (server defaults to all time)
        return { dateFrom, dateTo };
    }

    async loadData() {
        this.state.loading = true;
        const ouId = this.props.record.data.id;

        if (!ouId) {
            this.state.loading = false;
            return;
        }

        try {
            const salesData = await this.orm.call(
                "organizational.unit",
                "get_sales_by_period",
                [[ouId], this.state.period, 12]
            );
            this.state.salesData = salesData;
        } catch (error) {
            console.error("Error loading sales trend data:", error);
            this.state.salesData = [];
        }

        try {
            const { dateFrom, dateTo } = this._getProductDateRange();
            const topProducts = await this.orm.call(
                "organizational.unit",
                "get_top_products",
                [[ouId], null, dateFrom, dateTo],
                { sort_by: this.state.sortBy }
            );
            this.state.topProducts = topProducts;
            this.state.productsError = "";
        } catch (error) {
            console.error("Error loading top products data:", error);
            this.state.topProducts = [];
            this.state.productsError = String(error && error.message ? error.message : error);
        }

        this.state.loading = false;
        setTimeout(() => this.renderChart(), 100);
    }

    async onPeriodChange(ev) {
        this.state.period = ev.target.value;
        await this.loadData();
    }

    async onProductPeriodChange(ev) {
        this.state.productPeriod = ev.target.value;
        await this.loadData();
    }

    async onSortChange(field) {
        this.state.sortBy = field;
        await this.loadData();
    }

    /**
     * Compute the inclusive [date_from, date_to] ISO strings for the period
     * whose start date is given (as returned by DATE_TRUNC from the server).
     */
    _getPeriodDateRange(periodStr) {
        // Parse "YYYY-MM-DD" safely without timezone shifting
        const [year, month, day] = String(periodStr).split("-").map(Number);
        let dateFrom, dateTo;

        if (this.state.period === "year") {
            dateFrom = new Date(year, 0, 1);
            dateTo = new Date(year, 11, 31);
        } else if (this.state.period === "quarter") {
            // month is 1-based here; quarter start month is already correct from DATE_TRUNC
            dateFrom = new Date(year, month - 1, 1);
            // End of quarter = first day of 3 months later, minus 1 day
            const nextQStart = new Date(year, month - 1 + 3, 1);
            dateTo = new Date(nextQStart.getTime() - 86400000);
        } else {
            // month
            dateFrom = new Date(year, month - 1, 1);
            dateTo = new Date(year, month, 0); // last day of month
        }

        const fmt = (d) => {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, "0");
            const dd = String(d.getDate()).padStart(2, "0");
            return `${y}-${m}-${dd}`;
        };
        return { dateFrom: fmt(dateFrom), dateTo: fmt(dateTo) };
    }

    async onBarClick(dataIndex) {
        const ouId = this.props.record.data.id;
        if (!ouId) return;
        const entry = this.state.salesData[dataIndex];
        if (!entry) return;

        const { dateFrom, dateTo } = this._getPeriodDateRange(entry.period);
        try {
            const action = await this.orm.call(
                "organizational.unit",
                "action_view_invoices_period",
                [[ouId], dateFrom, dateTo]
            );
            await this.actionService.doAction(action);
        } catch (error) {
            console.error("Error opening period invoices:", error);
        }
    }

    async onProductClick(productId) {
        const ouId = this.props.record.data.id;
        if (!ouId || !productId) return;
        const { dateFrom, dateTo } = this._getProductDateRange();
        try {
            const action = await this.orm.call(
                "organizational.unit",
                "action_view_orders_for_product",
                [[ouId], productId, dateFrom, dateTo]
            );
            await this.actionService.doAction(action);
        } catch (error) {
            console.error("Error opening product orders:", error);
        }
    }

    renderChart() {
        const canvas = document.getElementById("salesTrendChart");
        if (!canvas) return;

        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }

        if (!this.state.salesData.length) return;

        const ctx = canvas.getContext("2d");

        const labels = this.state.salesData.map(d => {
            if (!d.period) return "N/A";
            const [year, month] = String(d.period).split("-").map(Number);
            if (this.state.period === "year") {
                return String(year);
            } else if (this.state.period === "quarter") {
                const q = Math.ceil(month / 3);
                return `Q${q} ${year}`;
            }
            const dt = new Date(year, month - 1, 1);
            return dt.toLocaleDateString(undefined, { month: "short", year: "numeric" });
        });
        const data = this.state.salesData.map(d => d.total || 0);

        const self = this;

        this.chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Sales",
                    data,
                    backgroundColor: "rgba(113, 75, 103, 0.7)",
                    borderColor: "rgba(113, 75, 103, 1)",
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick(_evt, elements) {
                    if (elements && elements.length > 0) {
                        self.onBarClick(elements[0].index);
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => value.toLocaleString(),
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => context.parsed.y.toLocaleString(undefined, {
                                style: "currency",
                                currency: "CAD",
                            }),
                        }
                    }
                }
            }
        });
    }

    formatCurrency(value) {
        return parseFloat(value || 0).toLocaleString(undefined, {
            style: "currency",
            currency: "CAD",
            minimumFractionDigits: 2,
        });
    }

    formatNumber(value) {
        return parseFloat(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

export const buyingTrendsWidget = {
    component: BuyingTrendsWidget,
};

registry.category("view_widgets").add("buying_trends", buyingTrendsWidget);
