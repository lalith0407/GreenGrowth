# tax_calculator.py

# This script implements a comprehensive tax calculation logic for the 2024 tax year.
# It includes standard deductions, adjustments to income, and tax credits for dependents.

# --- Constants for Tax Year 2024 ---

TAX_BRACKETS_2024 = {
    "single": [
        (0, 11600, 0.10), (11600, 47150, 0.12), (47150, 100525, 0.22),
        (100525, 191950, 0.24), (191950, 243725, 0.32), (243725, 609350, 0.35),
        (609350, float("inf"), 0.37),
    ],
    "married_filing_jointly": [
        (0, 23200, 0.10), (23200, 94300, 0.12), (94300, 201050, 0.22),
        (201050, 383900, 0.24), (383900, 487450, 0.32), (487450, 731200, 0.35),
        (731200, float("inf"), 0.37),
    ],
    "head_of_household": [
        (0, 16550, 0.10), (16550, 63100, 0.12), (63100, 100500, 0.22),
        (100500, 191950, 0.24), (191950, 243700, 0.32), (243700, 609350, 0.35),
        (609350, float("inf"), 0.37),
    ],
    "married_filing_separately": [
        (0, 11600, 0.10), (11600, 47150, 0.12), (47150, 100525, 0.22),
        (100525, 191950, 0.24), (191950, 243725, 0.32), (243725, 365600, 0.35),
        (365600, float("inf"), 0.37),
    ],
}

STANDARD_DEDUCTION_2024 = {
    "single": 14600, "married_filing_jointly": 29200,
    "married_filing_separately": 14600, "head_of_household": 21900,
    "qualifying_widow": 29200
}

CHILD_TAX_CREDIT_AMOUNT = 2000
CREDIT_FOR_OTHER_DEPENDENTS_AMOUNT = 500

def compute_bracketed_tax(taxable_income, brackets):
    """Calculates tax based on progressive tax brackets."""
    tax = 0
    for lower, upper, rate in brackets:
        if taxable_income > lower:
            amount_in_bracket = min(taxable_income, upper) - lower
            tax += amount_in_bracket * rate
    return round(tax, 2)

def calculate_tax_liability(
    filing_status, w2_income=0, w2_withheld=0, int_income=0, int_withheld=0,
    nec_income=0, nec_withheld=0, early_withdrawal_penalty=0,
    num_qualifying_children=0, num_other_dependents=0,
):
    """
    Returns a dictionary with detailed tax calculation results.
    """
    status_key = filing_status.lower().replace(" ", "_")
    
    total_income = w2_income + int_income + nec_income
    total_adjustments = early_withdrawal_penalty
    adjusted_income = total_income - total_adjustments

    deduction = STANDARD_DEDUCTION_2024.get(status_key, 14600)
    taxable_income = max(0, adjusted_income - deduction)
    
    brackets = TAX_BRACKETS_2024.get(status_key)
    if not brackets:
        raise ValueError(f"Unknown filing status for tax calculation: {filing_status}")
    initial_tax = compute_bracketed_tax(taxable_income, brackets)
    
    child_tax_credit = num_qualifying_children * CHILD_TAX_CREDIT_AMOUNT
    other_dependents_credit = num_other_dependents * CREDIT_FOR_OTHER_DEPENDENTS_AMOUNT
    total_credits = child_tax_credit + other_dependents_credit
    
    final_tax_liability = max(0, initial_tax - total_credits)

    total_withheld = w2_withheld + int_withheld + nec_withheld
    
    if final_tax_liability > total_withheld:
        balance_due = round(final_tax_liability - total_withheld, 2)
        refund = 0
    else:
        balance_due = 0
        refund = round(total_withheld - final_tax_liability, 2)

    return {
        "total_income": total_income, "adjustments": total_adjustments,
        "adjusted_gross_income": adjusted_income, "standard_deduction": deduction,
        "taxable_income": taxable_income, "initial_tax_liability": initial_tax,
        "total_credits": total_credits, "final_tax_liability": final_tax_liability,
        "total_withheld": total_withheld, "tax_due": balance_due, "refund": refund
    }
