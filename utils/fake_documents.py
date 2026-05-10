from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF

from utils.fake_data import TaxProfile, generate_tax_profile

if TYPE_CHECKING:
    from agents.base import Persona

_tmp = Path(tempfile.mkdtemp(prefix="webtax-agents-"))


def _w2_pdf(profile: TaxProfile) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "W-2 Wage and Tax Statement", ln=True, align="C")
    pdf.set_font("Helvetica", size=11)
    pdf.ln(5)
    pdf.cell(0, 8, f"Employee: {profile.full_name}", ln=True)
    pdf.cell(0, 8, f"Employer: {profile.employer}", ln=True)
    pdf.cell(0, 8, f"SSN (last 4): ***-**-{profile.ssn_last4}", ln=True)
    pdf.cell(0, 8, f"Box 1 - Wages: ${profile.wages / 100:,.2f}", ln=True)
    pdf.cell(0, 8, f"Box 2 - Federal income tax withheld: ${profile.federal_withheld / 100:,.2f}", ln=True)
    pdf.cell(0, 8, f"State: {profile.state}", ln=True)
    pdf.cell(0, 8, "Tax Year: 2025", ln=True)
    path = _tmp / f"w2_{profile.ssn_last4}.pdf"
    pdf.output(str(path))
    return path


def _1099_pdf(profile: TaxProfile) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Form 1099-NEC / 1099-MISC", ln=True, align="C")
    pdf.set_font("Helvetica", size=11)
    pdf.ln(5)
    pdf.cell(0, 8, f"Recipient: {profile.full_name}", ln=True)
    pdf.cell(0, 8, f"SSN (last 4): ***-**-{profile.ssn_last4}", ln=True)
    pdf.cell(0, 8, f"Nonemployee compensation: ${profile.income_1099 / 100:,.2f}", ln=True)
    pdf.cell(0, 8, "Tax Year: 2025", ln=True)
    path = _tmp / f"1099_{profile.ssn_last4}.pdf"
    pdf.output(str(path))
    return path


def _completed_return_pdf(client_name: str) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Form 1040 - U.S. Individual Income Tax Return", ln=True, align="C")
    pdf.set_font("Helvetica", size=11)
    pdf.ln(5)
    pdf.cell(0, 8, f"Taxpayer: {client_name}", ln=True)
    pdf.cell(0, 8, "Tax Year: 2025", ln=True)
    pdf.cell(0, 8, "[Completed return — prepared by accountant]", ln=True)
    path = _tmp / f"return_{client_name.replace(' ', '_')}.pdf"
    pdf.output(str(path))
    return path


def generate_source_documents(persona: Persona) -> list[Path]:
    profile = generate_tax_profile()
    docs = [_w2_pdf(profile)]
    if profile.has_1099:
        docs.append(_1099_pdf(profile))
    return docs


def generate_completed_return(client_name: str) -> Path:
    return _completed_return_pdf(client_name)
