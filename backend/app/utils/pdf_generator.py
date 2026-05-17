"""PDF rendering. Today: payslips. Add new renderers here as they're needed.

Implementation uses ReportLab's Platypus (high-level flow layout) so the
PDF reflows automatically as content grows. No system fonts are referenced
— Helvetica is built into every PDF reader.
"""
from __future__ import annotations

import io
from calendar import month_name

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.models.employee import Employee
from app.models.payslip import Payslip


_PAGE_MARGIN = 15 * mm


def _money(value: float) -> str:
    """Render an amount as `INR 12,345.00`. No locale dependency."""
    return f"INR {value:,.2f}"


def render_payslip_pdf(payslip: Payslip, employee: Employee) -> bytes:
    """Build a one-page payslip PDF and return its bytes.

    Layout:
      - header line: "Payslip — {Month YYYY}"
      - employee block: name, roll_no, email
      - earnings table: 4 components + Gross
      - deductions table: 4 components + Total Deductions
      - net pay highlighted
      - footer with generated_at timestamp

    Company name would also belong in the header — the Employee model
    has a relationship to Company. If the caller passed an employee
    whose `company` relationship is lazy and the session is already
    closed, the call will lazy-load and may fail. Routers should
    therefore call this with an actively-bound Employee.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=_PAGE_MARGIN,
        bottomMargin=_PAGE_MARGIN,
        leftMargin=_PAGE_MARGIN,
        rightMargin=_PAGE_MARGIN,
        title=f"Payslip {payslip.year}-{payslip.month:02d}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=16, spaceAfter=4 * mm
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )
    body_style = styles["Normal"]
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey,
    )

    company_name = None
    try:
        company_name = employee.company.name if employee.company else None
    except Exception:
        # Detached session / lazy-load failed — fine to render without
        # a company name in the header.
        company_name = None

    story = []

    # Header
    period = f"{month_name[payslip.month]} {payslip.year}"
    if company_name:
        story.append(Paragraph(company_name, title_style))
    story.append(Paragraph(f"Payslip — {period}", title_style))
    story.append(Spacer(1, 4 * mm))

    # Employee block
    emp_rows = [
        ["Name", employee.name or ""],
        ["Employee ID", employee.roll_no or "—"],
        ["Email", employee.email or "—"],
    ]
    emp_table = Table(emp_rows, colWidths=[40 * mm, 100 * mm])
    emp_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 6 * mm))

    # Earnings
    story.append(Paragraph("Earnings", label_style))
    earnings_rows = [
        ["Basic", _money(payslip.basic)],
        ["HRA", _money(payslip.hra)],
        ["Special Allowance", _money(payslip.special_allowance)],
        ["Other Allowances", _money(payslip.other_allowances)],
        ["Gross", _money(payslip.gross)],
    ]
    earnings_table = Table(earnings_rows, colWidths=[100 * mm, 60 * mm])
    earnings_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, -2), (-1, -2), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
    ]))
    story.append(earnings_table)
    story.append(Spacer(1, 6 * mm))

    # Deductions
    story.append(Paragraph("Deductions", label_style))
    ded_rows = [
        ["PF", _money(payslip.pf)],
        ["Professional Tax", _money(payslip.professional_tax)],
        ["TDS", _money(payslip.tds)],
        ["Other Deductions", _money(payslip.other_deductions)],
        ["Total Deductions", _money(payslip.total_deductions)],
    ]
    ded_table = Table(ded_rows, colWidths=[100 * mm, 60 * mm])
    ded_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, -2), (-1, -2), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
    ]))
    story.append(ded_table)
    story.append(Spacer(1, 8 * mm))

    # Net pay — highlighted box
    net_table = Table(
        [["Net Pay", _money(payslip.net)]], colWidths=[100 * mm, 60 * mm]
    )
    net_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 4 * mm))

    # Days info
    story.append(Paragraph(
        f"Days in period: {payslip.days_in_period} | "
        f"Worked: {payslip.days_worked:g} | "
        f"LWP: {payslip.days_lwp:g}",
        body_style,
    ))
    story.append(Spacer(1, 6 * mm))

    # Footer
    generated = payslip.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(
        f"Generated on {generated}. This is a computer-generated payslip; "
        f"no signature required.",
        footer_style,
    ))

    doc.build(story)
    return buf.getvalue()
