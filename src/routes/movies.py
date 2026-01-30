from typing import Annotated

from fastapi import (
    APIRouter,
    Query,
    Depends,
    HTTPException
)
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from database import get_db, MovieModel, Base
from database.models import (
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel
)
from schemas import (
    MovieListResponseSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    MessageResponse
)

router = APIRouter()


async def get_or_create_entities(db: AsyncSession, model, names: list[str]):
    if not names:
        return []

    result = await db.execute(select(model).where(model.name.in_(names)))
    existing_entities = result.scalars().all()
    existing_names = {e.name for e in existing_entities}

    new_entities = [model(name=name) for name in names if
                    name not in existing_names]

    if new_entities:
        db.add_all(new_entities)

    return list(existing_entities) + new_entities


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        db: AsyncSession = Depends(get_db),
):
    count_stmt = select(func.count()).select_from(MovieModel)
    count_result = await db.execute(count_stmt)
    total_items = count_result.scalar_one()

    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page

    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page

    stmt = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    movies = result.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    prev_page = (
        f"/theater/movies/?page={page - 1}&per_page={per_page}"
        if page > 1
        else None
    )

    next_page = (
        f"/theater/movies/?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    return MovieListResponseSchema(
        movies=movies,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=201
)
async def create_movie(
        db: Annotated[AsyncSession, Depends(get_db)],
        movie_data: MovieCreateSchema
):
    existing_movie = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date
        )
    )
    if existing_movie.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' "
                   f"and release date '{movie_data.date}' already exists."
        )

    country_query = await db.execute(
        select(CountryModel).where(CountryModel.code == movie_data.country)
    )
    db_country = country_query.scalar_one_or_none()

    if not db_country:
        db_country = CountryModel(code=movie_data.country, name=None)
        db.add(db_country)

    db_genres = await get_or_create_entities(
        db, GenreModel, movie_data.genres
    )
    db_actors = await get_or_create_entities(
        db, ActorModel, movie_data.actors
    )
    db_languages = await get_or_create_entities(
        db, LanguageModel, movie_data.languages
    )

    movie_fields = movie_data.model_dump(
        exclude={"country", "genres", "actors", "languages"}
    )

    db_movie = MovieModel(
        **movie_fields,
        country=db_country,
        genres=db_genres,
        actors=db_actors,
        languages=db_languages
    )

    db.add(db_movie)

    try:
        await db.commit()
        query = (
            select(MovieModel)
            .where(MovieModel.id == db_movie.id)
            .options(
                joinedload(MovieModel.country),
                selectinload(MovieModel.genres),
                selectinload(MovieModel.actors),
                selectinload(MovieModel.languages)
            )
        )
        result = await db.execute(query)
        db_movie = result.scalar_one()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return db_movie


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
)
async def get_movie(
        movie_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
) -> MovieDetailSchema:
    query = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages)
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(query)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return movie


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(
        movie_id: int,
        db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    movie = await db.get(MovieModel,
                         movie_id)

    if not movie:
        raise HTTPException(status_code=404,
                            detail="Movie with the given ID was not found.")

    await db.delete(movie)
    await db.commit()


@router.patch(
    "/movies/{movie_id}/",
    response_model=MessageResponse
)
async def update_movie(
        movie_id: int,
        movie_update: MovieUpdateSchema,
        db: Annotated[AsyncSession, Depends(get_db)],
):
    movie = await db.get(MovieModel, movie_id)

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    update_data = movie_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(movie, field, value)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid input data."
        )

    return {"detail": "Movie updated successfully."}
