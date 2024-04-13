from pypdf import PdfReader
from datetime import date
from enum import Enum
from dataclasses import dataclass
import re


def read_pdf(path: str) -> list[str]:
    reader = PdfReader(path)
    return [
        page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False)
        # Skip first and last page
        for page in reader.pages[1:-1]
    ]


def get_page_lines(page: str) -> list[list[str]]:
    parsed_lines = []
    for line in page.splitlines():
        parsed_line = re.sub(r' {2,}', '|', line).split('|')
        parsed_lines.append(parsed_line)
    return parsed_lines


class Currency(Enum):
    PEN = "PEN"
    USD = "USD"


@dataclass
class Operation:
    date: date
    description: str
    country: str | None
    amount: float
    currency: Currency


@dataclass
class Holder:
    name: str
    ending_card: str
    operations: list[Operation]


def parse_amount(amount: str) -> float | None:
    if amount == "---":
        return None
    return float(amount.replace(",", ""))


def parse_operation_line(line: list[str]) -> Operation:
    if len(line) == 6:
        pen_amount = parse_amount(line[4])
        usd_amount = parse_amount(line[5])
        amount = pen_amount if pen_amount is not None else usd_amount
        if amount is None:
            raise ValueError("Invalid amount", line)
        day, month = map(int, line[1].split("-"))
        return Operation(
            date=date(2021, month, day),
            description=line[2],
            country=line[3],
            amount=amount,
            currency=Currency.PEN if line[4] != "---" else Currency.USD,
        )
    elif len(line) == 5:
        pen_amount = parse_amount(line[3])
        usd_amount = parse_amount(line[4])
        amount = pen_amount if pen_amount is not None else usd_amount
        if amount is None:
            raise ValueError("Invalid amount", line)
        day, month = map(int, line[1].split("-"))
        return Operation(
            date=date(2021, month, day),
            description=line[2],
            country=None,
            amount=amount,
            currency=Currency.PEN if line[3] != "---" else Currency.USD,
        )
    raise ValueError("Invalid line")


def parse_page_lines(parsed_lines: list[list[str]]) -> list[Holder]:
    holders = []
    for line in parsed_lines:
        if line[0][:10] == "DETALLE DE":
            name, ending_card = line[1].split(" - ")
            holders.append(Holder(name, ending_card, []))
        elif len(holders) > 0:
            holders[-1].operations.append(parse_operation_line(line))
        elif line[0][:14] == "LIMITE MENSUAL":
            break
    return holders


def main():
    pages = read_pdf("statements/bbva_signature_eecc_24_01.pdf")
    parsed_lines = [get_page_lines(page) for page in pages]
    holders = [holder for page in parsed_lines for holder in parse_page_lines(page)]
    total = 0
    for operation in holders[2].operations:
        if operation.currency == Currency.USD:
            continue
        print(operation.amount)
        total += operation.amount
    print(total)


main()
