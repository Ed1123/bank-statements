import csv
from dotenv import load_dotenv
from itertools import chain
import os
from pypdf import PdfReader, errors
from datetime import date, datetime, timedelta, timezone, tzinfo
from enum import Enum
from dataclasses import dataclass
import re


def read_pdf(path: str) -> list[str]:
    try:
        reader = PdfReader(path, password=os.environ.get("PDF_PASSWORD"))
    except errors.PdfReadError:
        reader = PdfReader(path)
    metadata = reader.metadata
    if not metadata:
        raise ValueError("PDF has no metadata")
    creation_str = metadata.get("/CreationDate")
    if not creation_str:
        raise ValueError("PDF has no creation date")
    creation_datetime_str, creation_tz_str = creation_str[2:16], creation_str[16:]
    if creation_tz_str == "Z":
        tzinfo = timezone.utc
    else:
        tzinfo = timezone(timedelta(hours=int(creation_tz_str[:-4])))

    creation_date = datetime.strptime(creation_datetime_str, "%Y%m%d%H%M%S").replace(
        tzinfo=tzinfo
    )
    print(creation_date.astimezone())
    return [
        page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False)
        # Skip first and last page
        for page in reader.pages[1:-1]
    ]


def get_page_lines(page: str) -> list[list[str]]:
    parsed_lines = []
    for line in page.splitlines():
        parsed_line = re.sub(r' {4,}', '|', line).split('|')
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


def parse_lines(parsed_lines: list[list[str]]) -> list[Holder]:
    holders = []
    i = 0
    while not parsed_lines[i][0].lstrip().startswith("DETALLE DE OPERACIONES"):
        i += 1
    while i < len(parsed_lines):
        line = parsed_lines[i]
        if line[0].startswith("LIMITE MENSUAL"):
            break
        if line[0].startswith("DETALLE DE OPERACIONES"):
            match = re.search(r"(\w+ \w+) - (\d{4})", "|".join(line))
            if not match:
                raise ValueError("Invalid holder line", line)
            name = match.group(1)
            ending_card = match.group(2)
            holders.append(Holder(name, ending_card, []))
        elif len(line) > 4 and line[1][2:3] == "-":
            holders[-1].operations.append(parse_operation_line(line))
        i += 1
    return holders


def parse_pdf(path: str) -> list[Holder]:
    pages = read_pdf(path)
    parsed_lines = list(chain.from_iterable(get_page_lines(page) for page in pages))
    return parse_lines(parsed_lines)


def save_to_csv(statement: list[Holder], path: str):
    file = open(path, 'w')
    csv_writer = csv.writer(file)
    csv_writer.writerow(
        ["Name", "Ending Card", "Date", "Description", "Country", "Amount", "Currency"]
    )
    for holder in statement:
        for operation in holder.operations:
            csv_writer.writerow(
                [
                    holder.name,
                    holder.ending_card,
                    operation.date,
                    operation.description,
                    operation.country,
                    operation.amount,
                    operation.currency.value,
                ]
            )


def parse_files(directory: str):
    print("Parsing files in", directory)
    for filename in os.listdir(directory):
        print(f"Parsing {directory}/{filename}...")
        if not filename.endswith(".pdf"):
            continue
        statement = parse_pdf(f"{directory}/{filename}")
        output_path = f"{directory}/{filename.removesuffix('.pdf')}.csv"
        save_to_csv(statement, output_path)
        print("Saved to", output_path)


def main():
    statement = parse_pdf("statements/bbva_signature_eecc_24_01.pdf")
    total = 0
    for operation in statement[2].operations:
        if operation.currency == Currency.USD:
            continue
        print(operation.amount)
        total += operation.amount
    print(total)

    save_to_csv(statement, "statement.csv")
    load_dotenv()
    parse_files("statements")


main()
