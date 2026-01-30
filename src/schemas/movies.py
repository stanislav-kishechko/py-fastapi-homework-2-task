import datetime
from typing import List, Optional

import pycountry
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)

from database import MovieStatusEnum


class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int


class CountryResponse(BaseModel):
    id: int
    code: str
    name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NamedEntityResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class MovieCreateSchema(BaseModel):
    name: str = Field(..., max_length=255)
    date: datetime.date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @field_validator('date')
    @classmethod
    def date_not_too_far_in_future(cls, value):
        one_year_from_now = datetime.date.today() + datetime.timedelta(
            days=365)
        if value > one_year_from_now:
            raise ValueError('Date cannot be more than one year in the future')
        return value

    @field_validator('country')
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        if not value:
            raise ValueError('Country code is required')

        country_code = value.upper()

        country = pycountry.countries.get(alpha_3=country_code)
        if not country:
            raise ValueError(
                f"'{country_code}' is not a valid ISO 3166-1 alpha-3 country code"
            )

        return country_code


class MovieDetailSchema(BaseModel):
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: CountryResponse
    genres: List[NamedEntityResponse]
    actors: List[NamedEntityResponse]
    languages: List[NamedEntityResponse]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    date: Optional[datetime.date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)


class MessageResponse(BaseModel):
    detail: str
