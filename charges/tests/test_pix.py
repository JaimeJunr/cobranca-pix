import pytest

from charges.pix import PixPayloadError, build_static_payload, crc16_ccitt

# Exemplo oficial do Manual de Padrões para Iniciação do Pix (Banco Central).
BCB_EXAMPLE = (
    "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
    "5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***63041D3D"
)


def test_payload_matches_central_bank_example():
    payload = build_static_payload(
        key="123e4567-e12b-12d1-a456-426655440000",
        merchant_name="Fulano de Tal",
        merchant_city="BRASILIA",
    )

    assert payload == BCB_EXAMPLE


def test_payload_includes_amount_and_txid():
    payload = build_static_payload(
        key="pix@example.com",
        merchant_name="Loja",
        merchant_city="Caxias do Sul",
        amount="150.50",
        txid="COB123",
    )

    assert "5406150.50" in payload
    assert "62100506COB123" in payload
    assert payload.endswith(crc16_ccitt(payload[:-4]))


def test_payload_removes_accents_and_truncates_long_names():
    payload = build_static_payload(
        key="pix@example.com",
        merchant_name="Associação Beneficente de São João",
        merchant_city="Florianópolis do Sul",
    )

    assert "5925Associacao Beneficente de" in payload
    assert "6015Florianopolis d6" in payload


@pytest.mark.parametrize("amount", ["0", "-1", "abc", "10000000000.00"])
def test_payload_rejects_invalid_amount(amount):
    with pytest.raises(PixPayloadError, match="amount"):
        build_static_payload(
            key="pix@example.com", merchant_name="Loja", merchant_city="Caxias", amount=amount
        )


def test_payload_rejects_invalid_txid():
    with pytest.raises(PixPayloadError, match="txid"):
        build_static_payload(
            key="pix@example.com", merchant_name="Loja", merchant_city="Caxias", txid="cob-1"
        )


def test_payload_rejects_empty_key():
    with pytest.raises(PixPayloadError, match="key"):
        build_static_payload(key="", merchant_name="Loja", merchant_city="Caxias")
