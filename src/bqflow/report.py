from pydantic import BaseModel


class TaskReport(BaseModel):
    name: list[str]
    duration: float
    total_bytes_billed: int
