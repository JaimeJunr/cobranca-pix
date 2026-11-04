"""Arquivos gerados a partir de uma cobrança: QR Code (SVG) e PDF de cobrança."""

import io

import segno
from fpdf import FPDF

from charges.models import Charge


def render_qrcode_svg(charge: Charge) -> bytes:
    buffer = io.BytesIO()
    segno.make(charge.pix_payload(), error="m").save(buffer, kind="svg", scale=6, border=2)
    return buffer.getvalue()


def render_charge_pdf(charge: Charge, *, compress: bool = True) -> bytes:
    """PDF simples de cobrança com QR Code Pix. Não é boleto registrado: não tem
    linha digitável nem passa por banco, só mostra os dados e o Pix copia e cola."""
    pdf = FPDF(format="A4")
    pdf.set_compression(compress)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Cobrança Pix", new_x="LMARGIN", new_y="NEXT")
    if charge.status == Charge.Status.PAID:
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, "PAGA", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", size=11)
    for label, value in _charge_lines(charge):
        pdf.cell(45, 8, label)
        pdf.cell(0, 8, value, new_x="LMARGIN", new_y="NEXT")

    qr_png = io.BytesIO()
    segno.make(charge.pix_payload(), error="m").save(qr_png, kind="png", scale=8, border=2)
    pdf.image(qr_png, x=pdf.l_margin, y=pdf.get_y() + 4, w=60)
    pdf.set_y(pdf.get_y() + 70)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Pix copia e cola:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", size=8)
    pdf.multi_cell(0, 4, charge.pix_payload())
    return bytes(pdf.output())


def _charge_lines(charge: Charge) -> list[tuple[str, str]]:
    return [
        ("Identificador (txid):", charge.txid),
        ("Pagador:", charge.payer_name),
        ("CPF/CNPJ:", charge.payer_document),
        ("Descrição:", charge.description),
        ("Valor:", f"R$ {charge.amount:.2f}".replace(".", ",")),
        ("Vencimento:", charge.due_date.strftime("%d/%m/%Y")),
        ("Situação:", charge.get_status_display()),
    ]
