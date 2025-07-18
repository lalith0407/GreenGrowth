import os
import re
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from unstructured.partition.pdf import partition_pdf
import openai
import json
import warnings
import traceback
import tempfile # Added import

warnings.filterwarnings("ignore", category=DeprecationWarning)

class TaxFormParser:
    """
    A class to parse tax documents, identify their type, and extract
    structured data using OCR and AI.
    """
    def __init__(self, openai_api_key: str):
        """
        Initializes the parser and sets up the OpenAI client.
        Configures Tesseract path for Linux environments.
        """
        # Explicitly set Tesseract command for Linux/Docker environment
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract" # This is where apt-get installs it
        
        self.client = self._initialize_openai_client(openai_api_key)
        self.form_field_defs = self._get_form_field_definitions()

    def _initialize_openai_client(self, api_key: str):
        """Initializes and returns the OpenAI client."""
        if not api_key:
            print("WARNING: OpenAI API key is missing. AI extraction will be skipped.")
            return None
        try:
            return openai.OpenAI(api_key=api_key)
        except Exception as e:
            print(f"ERROR: Failed to initialize OpenAI client: {e}")
            return None

    def _get_form_field_definitions(self) -> dict:
        """Returns the dictionary of field definitions for supported tax forms."""
        return {
            "W-2": {
                "Employer Identification Number (EIN)": "the box labeled “Employer identification number”",
                "Employer Name": "the upper-left under “Employer’s name”",
                "Employee Name": "the lower-left under “Employee’s name”",
                "Employee Social Security Number (SSN)": "the box labeled “Employee’s social security number”",
                "Box 1: Wages, tips, other compensation": "the box labeled “1 Wages, tips, other compensation”",
                "Box 2: Federal income tax withheld": "the box labeled “2 Federal income tax withheld”",
            },
            "1099-INT": {
                "Payer's Name": "the upper-left under “PAYER’S name”",
                "Payer's TIN": "the box labeled “PAYER’S TIN”",
                "Recipient's Name": "the lower-left under “RECIPIENT’S name”",
                "Recipient's TIN": "the box labeled “RECIPIENT’S TIN”",
                "Box 1: Interest income": "the box labeled “1 Interest income”",
                "Box 2: Early withdrawal penalty": "the box labeled '2 Early withdrawal penalty'",
                "Box 4: Federal income tax withheld": "the box labeled “4 Federal income tax withheld”",
            },
            "1099-NEC": {
                "Payer's Name": "the upper-left under “PAYER’S name”",
                "Payer's TIN": "the box labeled “PAYER’S TIN”",
                "Recipient's Name": "the lower-left under “RECIPIENT’S name”",
                "Recipient's TIN": "the box labeled “RECIPIENT’S TIN”",
                "Box 1: Nonemployee compensation": "the box labeled “1 Nonemployee compensation”",
                "Box 4: Federal income tax withheld": "the box labeled “4 Federal income tax withheld”",
            },
        }

    def _parse_text_from_page(self, file_path: str, page_number: int) -> str:
        """Parses a single page of a PDF using Tesseract OCR."""
        try:
            # --- IMPORTANT CHANGE: Reduce DPI for memory efficiency ---
            images = convert_from_path(file_path, first_page=page_number, last_page=page_number, dpi=150) # Reduce DPI
            if not images: return ""
            return pytesseract.image_to_string(images[0])
        except Exception as e:
            print(f"ERROR: Tesseract OCR failed for page {page_number} of {file_path}. Error: {e}")
            return ""

    def _identify_document_type(self, file_path: str) -> str | None:
        doc_type_patterns = {
            "W-2": [r"Form\s*W-2", r"Wage\s+and\s+Tax\s+Statement", r"Wages,\s+tips,\s+other\s+compensation"],
            "1099-INT": [r"Form\s*1099-INT", r"Interest\s+Income", r"Early\s+withdrawal\s+penalty"],
            "1099-NEC": [r"Form\s*1099-NEC", r"Nonemployee\s+Compensation", r"Payer's\s+TIN"],
        }
        header_patterns = {dt: pats[0] for dt, pats in doc_type_patterns.items()}
        scores = {dt: 0 for dt in doc_type_patterns}
        try:
            with fitz.open(file_path) as doc:
                for page_num in range(1, len(doc) + 1):
                    # Use a lower DPI for initial text extraction to save memory
                    text = self._parse_text_from_page(file_path, page_num) 
                    if not text: continue
                    for dt, header_pat in header_patterns.items():
                        if re.search(header_pat, text, re.IGNORECASE): return dt
                    for dt, patterns in doc_type_patterns.items():
                        for pat in patterns:
                            if re.search(pat, text, re.IGNORECASE): scores[dt] += 1
        except Exception: return None
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else None

    def _find_page_with_cues(self, file_path: str, doc_type: str) -> int | None:
        cue_definitions = {
            "W-2": ["Wages, tips, other compensation", "Federal income tax withheld", "Wage and Tax Statement"],
            "1099-INT": ["Interest Income", "Payer's TIN", "Early withdrawal penalty"],
            "1099-NEC": ["Nonemployee Compensation", "Payer's TIN", "Federal income tax withheld"]
        }
        cues = cue_definitions.get(doc_type)
        if not cues: return None
        best_page, max_score = None, 0
        try:
            with fitz.open(file_path) as doc:
                for i in range(1, len(doc) + 1):
                    # Use a lower DPI for initial text extraction to save memory
                    text = self._parse_text_from_page(file_path, i) 
                    if not text: continue
                    score = sum(bool(re.search(cue, text, re.IGNORECASE)) for cue in cues)
                    if score > max_score:
                        max_score, best_page = score, i
        except Exception: return None
        return best_page if max_score > 0 else None

    def _create_temp_pdf(self, source_path: str, page_number: int, output_path: str):
        with fitz.open(source_path) as src, fitz.open() as dst:
            dst.insert_pdf(src, from_page=page_number - 1, to_page=page_number - 1)
            dst.save(output_path)

    def _process_file_with_unstructured(self, file_path: str) -> str:
        try:
            # unstructured's hi_res strategy can be memory intensive.
            # Keep it if accuracy is paramount, otherwise consider other strategies
            # or pre-process images at a lower DPI if unstructured supports it.
            elements = partition_pdf(filename=file_path, strategy="hi_res", infer_table_structure=True)
            return "\n\n".join([el.text or "" for el in elements])
        except Exception as e:
            print(f"ERROR: Unstructured PDF processing failed: {e}")
            traceback.print_exc()
            return ""

    def _extract_data_with_openai(self, context: str, doc_type: str) -> dict:
        defs = self.form_field_defs.get(doc_type)
        if not defs or not self.client: return {}
        fields = list(defs.keys())
        instructions = "\n".join(f"- **{fld}**: {loc}" for fld, loc in defs.items())
        system_prompt = f"You are an expert AI assistant extracting structured data from US tax forms. The current document type is **{doc_type}**. Use these definitions: {instructions}. Return one JSON object. If a value is not found, use 'N/A'."
        user_prompt = f"Based on this context from a {doc_type}, extract values for these fields:\n\nCONTEXT:\n---\n{context}\n---\n\nFIELDS_TO_EXTRACT:\n{json.dumps(fields, indent=2)}"
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"ERROR: OpenAI data extraction failed: {e}")
            traceback.print_exc()
            return {}

    def process_pdf(self, file_path: str) -> tuple:
        if not self.client or not os.path.exists(file_path): return {}, "Error"
        doc_type = self._identify_document_type(file_path)
        if not doc_type: return {}, "Unknown"
        page = self._find_page_with_cues(file_path, doc_type)
        if not page: return {}, doc_type
        
        temp_pdf = os.path.join(tempfile.gettempdir(), "_temp_page.pdf") # Use standard temp dir
        try:
            self._create_temp_pdf(file_path, page, temp_pdf)
            context = self._process_file_with_unstructured(temp_pdf)
            if not context: return {}, doc_type
            return self._extract_data_with_openai(context, doc_type), doc_type
        except Exception as e:
            print(f"ERROR: General PDF processing failed for {file_path}: {e}")
            traceback.print_exc()
            return {}, "Error" # Return "Error" type for clarity on failure
        finally:
            if os.path.exists(temp_pdf):
                try:
                    os.remove(temp_pdf)
                except OSError as e:
                    print(f"WARNING: Could not remove temporary file {temp_pdf}: {e}")