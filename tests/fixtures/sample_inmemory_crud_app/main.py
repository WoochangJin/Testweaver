"""FastAPI book-management CRUD exercise.

The application deliberately uses in-memory storage, as required by the
exercise. Data is lost whenever the process restarts.
"""

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="Book Management API")


class BookCreate(BaseModel):
    """Request model used when creating or replacing a book."""

    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    isbn: Optional[str] = Field(default=None, min_length=13, max_length=13)
    publication_year: Optional[int] = Field(default=None, ge=1000, le=2024)
    genre: Optional[str] = Field(default=None, max_length=50)


class Book(BookCreate):
    """Book response model with its server-generated identifier."""

    id: int


# In-memory storage required by the exercise.
books_db: Dict[int, Book] = {}
next_id: int = 1


def get_book_or_404(book_id: int) -> Book:
    """Return a stored book or raise a meaningful 404 response."""

    book = books_db.get(book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} was not found",
        )
    return book


@app.get(
    "/books",
    response_model=List[Book],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_books(
    author: Optional[str] = Query(default=None),
    genre: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None, ge=1000, le=2024),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1),
) -> List[Book]:
    """Retrieve books, with optional filtering and pagination."""

    books = list(books_db.values())

    if author is not None:
        normalized_author = author.casefold()
        books = [book for book in books if book.author.casefold() == normalized_author]

    if genre is not None:
        normalized_genre = genre.casefold()
        books = [
            book
            for book in books
            if book.genre is not None and book.genre.casefold() == normalized_genre
        ]

    if year is not None:
        books = [book for book in books if book.publication_year == year]

    return books[skip : skip + limit]


@app.get(
    "/books/{book_id}",
    response_model=Book,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_book(book_id: int) -> Book:
    """Retrieve one book by ID."""

    return get_book_or_404(book_id)


@app.post(
    "/books",
    response_model=Book,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_book(book_data: BookCreate) -> Book:
    """Create and store a new book."""

    global next_id

    book = Book(id=next_id, **book_data.model_dump())
    books_db[next_id] = book
    next_id += 1
    return book


@app.put(
    "/books/{book_id}",
    response_model=Book,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def update_book(book_id: int, book_data: BookCreate) -> Book:
    """Fully replace an existing book while preserving its ID."""

    get_book_or_404(book_id)

    updated_book = Book(id=book_id, **book_data.model_dump())
    books_db[book_id] = updated_book
    return updated_book


@app.delete(
    "/books/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_book(book_id: int) -> Response:
    """Delete an existing book and return an empty 204 response."""

    get_book_or_404(book_id)
    del books_db[book_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)