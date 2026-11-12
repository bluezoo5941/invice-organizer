from dataclasses import asdict, dataclass


@dataclass
class InvoiceRow:
    row: int
    name: str
    ticket: str
    project: str
    error: str = ""

    def to_dict(self):
        return asdict(self)


def issue(kind, message, *, row=None, file=None, level="warning"):
    return {"kind": kind, "message": message, "row": row, "file": file, "level": level}
