from pydantic import BaseModel, ConfigDict

from appfit.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


class PageParams(BaseModel):
    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def clamp(self) -> "PageParams":
        return PageParams(page=max(1, self.page), size=min(max(1, self.size), MAX_PAGE_SIZE))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Message(BaseModel):
    detail: str
