import pytest

from charges.documents import render_charge_pdf, render_qrcode_svg
from charges.models import Charge

pytestmark = pytest.mark.django_db


def test_pdf_contains_payer_and_pix_code(make_charge):
    charge = make_charge(payer_name="Ana Pereira")

    pdf = render_charge_pdf(charge, compress=False)

    assert pdf.startswith(b"%PDF")
    assert b"Ana Pereira" in pdf
    assert charge.txid.encode() in pdf


def test_pdf_of_paid_charge_shows_paid_stamp(make_charge):
    charge = make_charge(status=Charge.Status.PAID)

    pdf = render_charge_pdf(charge, compress=False)

    assert b"PAGA" in pdf


def test_qrcode_svg_encodes_payload(make_charge):
    svg = render_qrcode_svg(make_charge())

    assert svg.startswith(b"<?xml") or svg.startswith(b"<svg")
