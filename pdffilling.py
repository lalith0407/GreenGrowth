from pypdf import PdfReader, PdfWriter
import io

def fill_1040_pdf(input_pdf_path: str, user_data: dict) -> bytes:
    """
    Fills a fillable Form 1040 PDF with user-provided data and returns it as 
    an in-memory byte object, suitable for server environments like Render.
    """
    corrected_full_field_mapping = {
        # This mapping is based on our analysis of the numbered PDF
        'f1_04[0]': 'Your first name and middle initial', 'f1_05[0]': 'Last name',
        'f1_06[0]': 'Your social security number', 'f1_07[0]': "Spouse's first name and middle initial",
        'f1_08[0]': "Spouse's last name", 'f1_09[0]': "Spouse's social security number",
        'f1_10[0]': 'Home address (number and street)', 'f1_11[0]': 'Apt. no.',
        'f1_12[0]': 'City, town, or post office', 'f1_13[0]': 'State', 'f1_14[0]': 'ZIP code',
        'f1_15[0]': 'Foreign country name', 'f1_16[0]': 'Foreign province/state/county',
        'f1_17[0]': 'Foreign postal code', 'f1_18[0]': 'MFS spouse name',
        'f1_19[0]': 'HOH or QSS qualifying child name', 'c1_1[0]': 'Presidential Election Campaign - You',
        'c1_2[0]': 'Presidential Election Campaign - Spouse', 'c1_3[0]': 'Filing Status - Single',
        'c1_3[1]': 'Filing Status - Married filing jointly', 'c1_3[2]': 'Filing Status - Married filing separately',
        'c1_4[0]': 'Filing Status - Head of household (HOH)', 'c1_5[0]': 'Filing Status - Qualifying surviving spouse (QSS)',
        'c1_6[0]': 'Digital Assets - Yes', 'c1_7[0]': 'Digital Assets - No',
        'c1_8[0]': 'Someone can claim: You as a dependent', 'c1_9[0]': 'Someone can claim: Your spouse as a dependent',
        'c1_10[0]': 'Age/Blindness - You: Were born before January 2, 1960', 'c1_11[0]': 'Age/Blindness - You: Are blind',
        'c1_12[0]': 'Age/Blindness - Spouse: Was born before January 2, 1960', 'c1_13[0]': 'Age/Blindness - Spouse: Is blind',
        'c1_14[0]': 'Dependent 1 - Child tax credit checkbox', 'c1_15[0]': 'Dependent 1 - Credit for other dependents checkbox',
        'c1_16[0]': 'Dependent 2 - Child tax credit checkbox', 'c1_17[0]': 'Dependent 2 - Credit for other dependents checkbox',
        'c1_18[0]': 'Dependent 3 - Child tax credit checkbox', 'c1_19[0]': 'Dependent 3 - Credit for other dependents checkbox',
        'c1_20[0]': 'Dependent 4 - Child tax credit checkbox', 'c1_21[0]': 'Dependent 4 - Credit for other dependents checkbox',
        'c1_22[0]': 'More than four dependents checkbox', 'c2_5[0]': '35c - Type: Checking',
        'c2_5[1]': '35c - Type: Savings', 'c2_6[0]': 'Third Party Designee - Yes', 'c2_6[1]': 'Third Party Designee - No',
        'f1_20[0]': 'Dependent 1 - First name', 'f1_21[0]': 'Dependent 1 - Last name',
        'f1_22[0]': 'Dependent 1 - Social security number', 'f1_23[0]': 'Dependent 1 - Relationship to you',
        'f1_24[0]': 'Dependent 2 - First name', 'f1_25[0]': 'Dependent 2 - Last name',
        'f1_26[0]': 'Dependent 2 - Social security number', 'f1_27[0]': 'Dependent 2 - Relationship to you',
        'f1_28[0]': 'Dependent 3 - First name', 'f1_29[0]': 'Dependent 3 - Last name',
        'f1_30[0]': 'Dependent 3 - Social security number', 'f1_31[0]': 'Dependent 3 - Relationship to you',
        'f1_40[0]': 'Dependent 4 - First name', 'f1_41[0]': 'Dependent 4 - Last name',
        'f1_42[0]': 'Dependent 4 - Social security number', 'f1_43[0]': 'Dependent 4 - Relationship to you',
        'f1_32[0]': '1a - Wages from Form(s) W-2', 'f1_34[0]': '1b - Household employee wages',
        'f1_35[0]': '1c - Tip income', 'f1_36[0]': '1d - Medicaid waiver payments',
        'f1_37[0]': '1e - Taxable dependent care benefits', 'f1_38[0]': '1f - Employer-provided adoption benefits',
        'f1_39[0]': '1g - Wages from Form 8919', 'f1_44[0]': '1h - Other earned income',
        'f1_45[0]': '1i - Nontaxable combat pay election', 'f1_46[0]': '1z - Total of lines 1a through 1h',
        'f1_47[0]': '2a - Tax-exempt interest', 'f1_48[0]': '2b - Taxable interest',
        'f1_49[0]': '3a - Qualified dividends', 'f1_50[0]': '3b - Ordinary dividends',
        'f1_51[0]': '4a - IRA distributions', 'f1_52[0]': '4b - IRA distributions, taxable amount',
        'f1_53[0]': '5a - Pensions and annuities', 'f1_54[0]': '5b - Pensions and annuities, taxable amount',
        'f1_55[0]': '6a - Social security benefits', 'f1_56[0]': '6b - Social security benefits, taxable amount',
        'f1_57[0]': '7 - Capital gain or (loss)', 'f1_58[0]': '8 - Additional income from Schedule 1, line 10',
        'f1_59[0]': '9 - Total income', 'f1_60[0]': '10 - Adjustments to income from Schedule 1',
        'f2_01[0]': '11 - Adjusted gross income (AGI)', 'f2_02[0]': '12 - Standard deduction or itemized deductions',
        'f2_03[0]': '13 - Qualified business income deduction', 'f2_04[0]': '14 - Add lines 12 and 13',
        'f2_05[0]': '15 - Taxable income', 'f2_06[0]': '16 - Tax',
        'f2_07[0]': '17 - Amount from Schedule 2, line 3', 'f2_08[0]': '18 - Add lines 16 and 17',
        'f2_09[0]': '19 - Child tax credit or credit for other dependents', 'f2_10[0]': '20 - Amount from Schedule 3, line 8',
        'f2_11[0]': '21 - Add lines 19 and 20', 'f2_12[0]': '22 - Subtract line 21 from 18',
        'f2_13[0]': '23 - Other taxes, including self-employment tax', 'f2_14[0]': '24 - Total tax',
        'f2_15[0]': '25a - Federal income tax withheld from W-2', 'f2_16[0]': '25b - Federal income tax withheld from 1099',
        'f2_17[0]': '25c - Federal income tax withheld from Other forms', 'f2_18[0]': '25d - Add lines 25a through 25c',
        'f2_19[0]': '26 - 2024 estimated tax payments', 'f2_20[0]': '27 - Earned income credit (EIC)',
        'f2_21[0]': '28 - Additional child tax credit', 'f2_22[0]': '29 - American opportunity credit',
        'f2_23[0]': '31 - Amount from Schedule 3, line 15', 'f2_24[0]': '32 - Total other payments and refundable credits',
        'f2_25[0]': '33 - Total payments', 'f2_26[0]': '34 - Amount you overpaid',
        'f2_27[0]': '35a - Amount of line 34 to be refunded', 'RoutingNo[0]': '35b - Routing number',
        'AccountNo[0]': '35d - Account number', 'f2_28[0]': '36 - Amount of line 34 to apply to 2025 tax',
        'f2_29[0]': '37 - Amount you owe', 'f2_30[0]': '38 - Estimated tax penalty',
        'f2_31[0]': "Designee's name", 'f2_32[0]': 'Designee Phone no.',
        'f2_33[0]': 'Designee Personal Identification Number (PIN)', 'f2_35[0]': 'Your Identity Protection PIN',
        'f2_36[0]': "Spouse's Identity Protection PIN", 'f2_38[0]': 'Your occupation',
        'f2_39[0]': "Spouse's occupation", 'f2_40[0]': 'Your phone number',
        'f2_41[0]': 'Your email address', 'f2_42[0]': "Preparer's name",
        'f2_43[0]': "Preparer's PTIN", 'f2_44[0]': "Firm's name",
        'f1_01[0]': "Firm's address", 'f1_02[0]': "Firm's phone number", 'f1_03[0]': "Firm's EIN"
    }

    description_to_field_name = {v: k for k, v in corrected_full_field_mapping.items()}
    
    pdf_form_data = {}
    for description, value in user_data.items():
        if description in description_to_field_name:
            field_name = description_to_field_name[description]
            pdf_form_data[field_name] = '/Yes' if isinstance(value, bool) and value else str(value)

    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
        writer.append(reader)

        for page in writer.pages:
            if page.get('/Annots'):
                 writer.update_page_form_field_values(page, pdf_form_data)

        pdf_bytes_io = io.BytesIO()
        writer.write(pdf_bytes_io)
        pdf_bytes_io.seek(0)
        return pdf_bytes_io.getvalue()

    except FileNotFoundError:
        print(f"❌ Error: The input file was not found at '{input_pdf_path}'")
        return None
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return None
