import os
import shutil
import tempfile
import warnings
import traceback
import base64
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# --- Import your project logic ---
from silent import TaxFormParser
from taxcalculation import calculate_tax_liability
from pdffilling import fill_1040_pdf

# --- Suppress warnings ---
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Load environment variables ---
load_dotenv()

# --- Initialize the FastAPI App ---
app = FastAPI(
    title="Tax Document Processing API",
    description="An API to upload and process tax documents, calculate tax liability, and generate a filled Form 1040.",
    version="1.3.0"
)

# --- Add CORS Middleware ---
# This allows your Vercel frontend to make requests to this API.
origins = [
    "http://localhost:3000", # For local testing
    "https://your-frontend-app-name.vercel.app", # <-- IMPORTANT: Replace with your actual Vercel app URL
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for API Response Structure ---
class ParsedForm(BaseModel):
    file: str
    document_type: str
    parsed_fields: Dict[str, Any]

class TaxSummary(BaseModel):
    total_income: float
    adjustments: float
    adjusted_gross_income: float
    standard_deduction: float
    taxable_income: float
    initial_tax_liability: float
    total_credits: float
    final_tax_liability: float
    total_withheld: float
    tax_due: float
    refund: float

class ProcessingResult(BaseModel):
    parsed_forms: List[ParsedForm]
    tax_summary: TaxSummary
    filled_pdf_base64: str

# --- Helper Functions ---
def _to_float(s: Any) -> float:
    if isinstance(s, (int, float)): return float(s)
    try: return float(str(s).replace(",", "").replace("$", ""))
    except (ValueError, TypeError): return 0.0

def aggregate_and_compute(parsed_results: List[Dict], filing_status: str, num_children: int, num_dependents: int) -> Dict:
    w2_fields = next((r["parsed_fields"] for r in parsed_results if r["document_type"] == "W-2"), {})
    int_fields = next((r["parsed_fields"] for r in parsed_results if r["document_type"] == "1099-INT"), {})
    nec_fields = next((r["parsed_fields"] for r in parsed_results if r["document_type"] == "1099-NEC"), {})
    w2_income = _to_float(w2_fields.get("Box 1: Wages, tips, other compensation", "0"))
    w2_withheld = _to_float(w2_fields.get("Box 2: Federal income tax withheld", "0"))
    int_income = _to_float(int_fields.get("Box 1: Interest income", "0"))
    int_withheld = _to_float(int_fields.get("Box 4: Federal income tax withheld", "0"))
    early_penalty = _to_float(int_fields.get("Box 2: Early withdrawal penalty", "0"))
    nec_income = _to_float(nec_fields.get("Box 1: Nonemployee compensation", "0"))
    nec_withheld = _to_float(nec_fields.get("Box 4: Federal income tax withheld", "0"))
    return calculate_tax_liability(
        filing_status=filing_status, w2_income=w2_income, w2_withheld=w2_withheld,
        int_income=int_income, int_withheld=int_withheld, nec_income=nec_income,
        nec_withheld=nec_withheld, early_withdrawal_penalty=early_penalty,
        num_qualifying_children=num_children, num_other_dependents=num_dependents
    )

def blocking_file_processor(files: List[UploadFile], openai_api_key: str) -> List[Dict]:
    parser = TaxFormParser(openai_api_key=openai_api_key)
    parsed_results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            try:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                res = parser.process_pdf(file_path)
                # The type hint for res in silent.py's process_pdf is now `tuple[Dict[str, Any], str]`
                if isinstance(res, tuple) and len(res) == 2:
                    parsed_dict, doc_type = res
                else:
                    parsed_dict, doc_type = res or {}, "Unknown"
                parsed_results.append({"file": file.filename, "document_type": doc_type, "parsed_fields": parsed_dict})
            except Exception as e:
                traceback.print_exc()
                parsed_results.append({"file": file.filename, "document_type": "Error", "parsed_fields": {"error": str(e)}})
    return parsed_results

# --- API Endpoint ---
@app.post("/process-forms/", response_model=ProcessingResult)
async def process_tax_forms(
    filing_status: str = Form(...),
    num_qualifying_children: int = Form(0),
    num_other_dependents: int = Form(0),
    files: List[UploadFile] = File(...)
):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not found in environment variables.")

    parsed_results = await run_in_threadpool(
        blocking_file_processor,
        files=files,
        openai_api_key=openai_api_key
    )

    try:
        tax_summary = aggregate_and_compute(parsed_results, filing_status, num_qualifying_children, num_other_dependents)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred during tax calculation: {e}")
    
    w2_data = next((r["parsed_fields"] for r in parsed_results if r["document_type"] == "W-2"), {})
    pdf_data_to_fill = {
        "Your first name and middle initial": w2_data.get("Employee Name", " ").split(' ')[0],
        "Last name": w2_data.get("Employee Name", " ").split(' ')[-1],
        "Your social security number": w2_data.get("Employee Social Security Number (SSN)", ""),
        f"Filing Status - {filing_status.replace('_', ' ').title()}": True,
        '1a - Wages from Form(s) W-2': tax_summary['total_income'],
        '9 - Total income': tax_summary['total_income'],
        '11 - Adjusted gross income (AGI)': tax_summary['adjusted_gross_income'],
        '12 - Standard deduction or itemized deductions': tax_summary['standard_deduction'],
        '15 - Taxable income': tax_summary['taxable_income'],
        '16 - Tax': tax_summary['initial_tax_liability'],
        '19 - Child tax credit or credit for other dependents': tax_summary['total_credits'],
        '24 - Total tax': tax_summary['final_tax_liability'],
        '25d - Add lines 25a through 25c': tax_summary['total_withheld'],
        '33 - Total payments': tax_summary['total_withheld'],
        '34 - Amount you overpaid': tax_summary['refund'],
        '37 - Amount you owe': tax_summary['tax_due'],
    }
    input_pdf_template = "f1040.pdf" 
    filled_pdf_bytes = fill_1040_pdf(input_pdf_template, pdf_data_to_fill)
    
    if filled_pdf_bytes:
        pdf_base64_string = base64.b64encode(filled_pdf_bytes).decode('utf-8')
    else:
        pdf_base64_string = ""

    return {"parsed_forms": parsed_results, "tax_summary": tax_summary, "filled_pdf_base64": pdf_base64_string}

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Tax Processing API. Go to /docs for the interactive API documentation."}