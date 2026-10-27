"""
Generates real, valid sample policy PDFs for testing the actual upload
pipeline (POST /api/documents/upload -> API Gateway -> S3 -> Textract ->
Lambda -> DynamoDB -> Snowflake) -- as opposed to sql/seed/policy_documents_100.csv,
which seeds Snowflake directly and never touches Textract/Lambda.

Each PDF's body text is written so aws/lambda/document_processor/handler.py's
keyword classifier and regex field extraction can actually find something:
  - _classify_document() looks for "auto insurance"/"vehicle"/"vin",
    "homeowners"/"dwelling"/"property insurance", or
    "life insurance"/"beneficiary".
  - _extract_policy_fields() looks for "Policy Number: ..." and
    "Effective Date: ...".

Usage:
    pip install fpdf2
    python scripts/generate_sample_pdfs.py
Output:
    sample_documents/*.pdf  (10 files by default)
"""
import os

from fpdf import FPDF

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_documents")

# (customer_id, policy_id, doc_type_label, title, body_lines)
# doc_type_label is just for the filename; the Lambda classifies from body text.
SAMPLES = [
    ("CUST-001", "POL-1001", "auto", "AUTO INSURANCE POLICY DOCUMENT", [
        "Policyholder: John Doe",
        "Policy Number: POL-1001",
        "Effective Date: 01/15/2024",
        "Vehicle: 2022 Toyota Camry",
        "VIN: 1HGCM82633A004352",
        "Coverage: Comprehensive Auto Insurance",
    ]),
    ("CUST-002", "POL-1002", "home", "HOMEOWNERS INSURANCE POLICY DOCUMENT", [
        "Policyholder: Jane Smith",
        "Policy Number: POL-1002",
        "Effective Date: 02/14/2024",
        "Property Insurance for Dwelling at 123 Maple Street",
        "Coverage: Homeowners Standard",
    ]),
    ("CUST-003", "POL-1003", "life", "LIFE INSURANCE POLICY DOCUMENT", [
        "Policyholder: Robert Lee",
        "Policy Number: POL-1003",
        "Effective Date: 03/03/2024",
        "Beneficiary: Maria Lee",
        "Coverage: Term Life Insurance, 20 Year",
    ]),
    ("CUST-004", "POL-1004", "auto", "AUTO INSURANCE POLICY DOCUMENT", [
        "Policyholder: Alice Brown",
        "Policy Number: POL-1004",
        "Effective Date: 04/04/2024",
        "Vehicle: 2021 Honda Civic",
        "VIN: 2HGFB2F5XEH123456",
        "Coverage: Auto Insurance Liability Plus",
    ]),
    ("CUST-005", "POL-1005", "home", "HOMEOWNERS INSURANCE POLICY DOCUMENT", [
        "Policyholder: Michael Green",
        "Policy Number: POL-1005",
        "Effective Date: 05/05/2024",
        "Property Insurance for Dwelling at 45 Oak Avenue",
        "Coverage: Homeowners Premium",
    ]),
    ("CUST-006", "POL-1006", "life", "LIFE INSURANCE POLICY DOCUMENT", [
        "Policyholder: Sarah Wilson",
        "Policy Number: POL-1006",
        "Effective Date: 06/06/2024",
        "Beneficiary: David Wilson",
        "Coverage: Whole Life Select",
    ]),
    ("CUST-007", "POL-1007", "auto", "AUTO INSURANCE POLICY DOCUMENT", [
        "Policyholder: Karen Davis",
        "Policy Number: POL-1007",
        "Effective Date: 07/07/2024",
        "Vehicle: 2023 Ford F-150",
        "VIN: 1FTFW1E50PFA12345",
        "Coverage: Comprehensive Auto Insurance",
    ]),
    ("CUST-008", "POL-1008", "home", "HOMEOWNERS INSURANCE POLICY DOCUMENT", [
        "Policyholder: Thomas Miller",
        "Policy Number: POL-1008",
        "Effective Date: 08/08/2024",
        "Property Insurance for Dwelling at 78 Pine Road",
        "Coverage: Renters Basic",
    ]),
    ("CUST-009", "POL-1009", "life", "LIFE INSURANCE POLICY DOCUMENT", [
        "Policyholder: Nancy Taylor",
        "Policy Number: POL-1009",
        "Effective Date: 09/09/2024",
        "Beneficiary: James Taylor",
        "Coverage: Universal Life",
    ]),
    ("CUST-010", "POL-1010", "unclassified", "GENERAL POLICY DOCUMENT", [
        "Policyholder: Patricia Anderson",
        "Policy Number: POL-1010",
        "Effective Date: 10/10/2024",
        "Coverage: Umbrella Policy",
        # Deliberately omits auto/home/life keywords so this one is
        # classified UNKNOWN by the Lambda -- useful for testing that
        # fallback path.
    ]),
]


def build_pdf(title, lines):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", style="B", size=16)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(effective_width, 10, title)
    pdf.ln(4)

    pdf.set_font("Helvetica", size=12)
    for line in lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 8, line)
    return pdf


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for customer_id, policy_id, doc_type, title, lines in SAMPLES:
        pdf = build_pdf(title, lines)
        filename = f"{customer_id}_{policy_id}_{doc_type}.pdf"
        path = os.path.join(OUTPUT_DIR, filename)
        pdf.output(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
