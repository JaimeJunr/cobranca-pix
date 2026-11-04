"""Monta o "Pix copia e cola" estático (BR Code), sem falar com banco nenhum.

O BR Code é uma sequência de campos TLV (id de 2 dígitos, tamanho de 2 dígitos, valor),
no padrão EMV QRCPS, e termina com um CRC16 que o app do banco confere antes de pagar.
Referência: Manual de Padrões para Iniciação do Pix, do Banco Central.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

PIX_GUI = "br.gov.bcb.pix"
MAX_NAME_LENGTH = 25
MAX_CITY_LENGTH = 15
MAX_AMOUNT_LENGTH = 13
TXID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,25}$")


class PixPayloadError(ValueError):
    pass


def build_static_payload(
    *,
    key: str,
    merchant_name: str,
    merchant_city: str,
    amount: Decimal | str | None = None,
    txid: str = "***",
) -> str:
    if not key:
        raise PixPayloadError(f"invalid key: received {key!r}, expected a non-empty Pix key")
    if txid != "***" and not TXID_PATTERN.match(txid):
        raise PixPayloadError(f"invalid txid: received {txid!r}, expected 1-25 letters/digits")

    fields = [
        _tlv("00", "01"),
        _tlv("26", _tlv("00", PIX_GUI) + _tlv("01", key)),
        _tlv("52", "0000"),
        _tlv("53", "986"),
    ]
    if amount is not None:
        fields.append(_tlv("54", _format_amount(amount)))
    fields += [
        _tlv("58", "BR"),
        _tlv("59", _ascii(merchant_name, MAX_NAME_LENGTH)),
        _tlv("60", _ascii(merchant_city, MAX_CITY_LENGTH)),
        _tlv("62", _tlv("05", txid)),
    ]
    # O CRC cobre tudo, inclusive o próprio cabeçalho "6304" do campo do CRC.
    without_crc = "".join(fields) + "6304"
    return without_crc + crc16_ccitt(without_crc)


def crc16_ccitt(data: str) -> str:
    """CRC16-CCITT-FALSE (polinômio 0x1021, início 0xFFFF), em hexadecimal maiúsculo."""
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _tlv(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def _ascii(text: str, max_length: int) -> str:
    # Nome e cidade sem acento: vários apps de banco recusam caractere fora do ASCII.
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return normalized[:max_length].strip()


def _format_amount(amount: Decimal | str) -> str:
    try:
        value = Decimal(str(amount))
    except InvalidOperation as error:
        raise PixPayloadError(
            f"invalid amount: received {amount!r}, expected a positive decimal"
        ) from error
    formatted = f"{value:.2f}"
    if value <= 0 or len(formatted) > MAX_AMOUNT_LENGTH:
        raise PixPayloadError(
            f"invalid amount: received {amount!r}, expected a positive decimal "
            f"with at most {MAX_AMOUNT_LENGTH} characters"
        )
    return formatted
