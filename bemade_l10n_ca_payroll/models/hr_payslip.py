from odoo import models, fields, api


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _l18n_ca_compute_fed_tax_constants(self, taxable_income: float, coefficients):
        """
            Take a table of input coefficients in the form
            [
                (a, r, k),
                ...
            ] where a, r, and k are the threshold, tax rate and federal constants from government tables,
            and return the r and k applicable for the given annual taxable income.

            :param taxable_income: annual taxable income
            :param coefficients: coefficients table to use (get it from rule parameters data, usually)
            :return: (r, k) values where r is the tax rate and k is the federal constant to use
        """
        R = coefficients[0][1]
        K = coefficients[0][2]

        # Get the rate and constant by income tier (stop once we reach a tier above the taxable income)
        for a, r, k in coefficients:
            if taxable_income < a:
                return R, K
            R = r
            K = k
        return R, K
