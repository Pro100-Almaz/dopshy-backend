# Dopshy Backend

FastAPI-based backend with PostgreSQL, SQLAlchemy, and JWT authentication.

---

## 🗂️ Project Structure

```
backend/
├── src/
│   ├── api/                    # API layer
│   │   ├── routes/            # Endpoint route definitions
│   │   └── dependencies/      # Dependency injection (sessions, repos)
│   ├── models/                # Data models
│   │   ├── db/               # SQLAlchemy database models
│   │   └── schemas/          # Pydantic schemas (request/response)
│   ├── repository/            # Data access layer
│   │   ├── crud/             # CRUD operations per entity
│   │   └── database.py       # Database configuration
│   ├── securities/            # Security utilities
│   │   ├── authorizations/   # JWT token management
│   │   └── hashing/          # Password hashing
│   ├── config/               # Configuration management
│   └── utilities/            # Helpers and exceptions
└── tests/                    # Test suites
```

---

## 🔌 Making Native SQL Queries

### Using SQLAlchemy Raw SQL

```python
from sqlalchemy import text
from src.api.dependencies.session import get_async_session

async def custom_query_example(session):
    # Raw SQL query
    query = text("""
        SELECT id, username, email 
        FROM account 
        WHERE is_active = :active 
        LIMIT :limit
    """)
    
    result = await session.execute(
        query, 
        {"active": True, "limit": 10}
    )
    
    rows = result.fetchall()
    return rows
```

### In CRUD Repository

```python
# src/repository/crud/account.py
async def get_accounts_with_raw_sql(self):
    stmt = text("SELECT * FROM account WHERE created_at > :date")
    result = await self.async_session.execute(stmt, {"date": "2024-01-01"})
    return result.fetchall()
```

**Note**: Prefer SQLAlchemy ORM queries for type safety and maintainability. Use raw SQL only when necessary.

---

## 🚀 Adding New Endpoints

### Step 1: Create Database Model
**File**: `src/models/db/your_model.py`

```python
from src.repository.table import Base
from sqlalchemy import Column, Integer, String

class YourModel(Base):
    __tablename__ = "your_table"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
```

### Step 2: Create Pydantic Schemas
**File**: `src/models/schemas/your_model.py`

```python
from pydantic import BaseModel

class YourModelInCreate(BaseModel):
    name: str

class YourModelInResponse(BaseModel):
    id: int
    name: str
```

### Step 3: Create CRUD Repository
**File**: `src/repository/crud/your_model.py`

```python
import sqlalchemy
from src.repository.crud.base import BaseCRUDRepository
from src.models.db.your_model import YourModel

class YourModelCRUDRepository(BaseCRUDRepository):
    async def create_item(self, name: str) -> YourModel:
        new_item = YourModel(name=name)
        self.async_session.add(new_item)
        await self.async_session.commit()
        await self.async_session.refresh(new_item)
        return new_item
    
    async def read_items(self):
        stmt = sqlalchemy.select(YourModel)
        result = await self.async_session.execute(stmt)
        return result.scalars().all()
```

### Step 4: Create Route
**File**: `src/api/routes/your_route.py`

```python
import fastapi
from src.api.dependencies.repository import get_repository
from src.repository.crud.your_model import YourModelCRUDRepository
from src.models.schemas.your_model import YourModelInResponse

router = fastapi.APIRouter(prefix="/items", tags=["items"])

@router.get("", response_model=list[YourModelInResponse])
async def get_items(
    repo: YourModelCRUDRepository = fastapi.Depends(
        get_repository(repo_type=YourModelCRUDRepository)
    )
):
    return await repo.read_items()

@router.post("", response_model=YourModelInResponse)
async def create_item(
    name: str,
    repo: YourModelCRUDRepository = fastapi.Depends(
        get_repository(repo_type=YourModelCRUDRepository)
    )
):
    return await repo.create_item(name=name)
```

### Step 5: Register Route
**File**: `src/api/endpoints.py`

```python
from src.api.routes import your_route

router = fastapi.APIRouter()
router.include_router(router=your_route.router)
```

### Step 6: Create Migration
```bash
cd backend
alembic revision --autogenerate -m "Add your_table"
alembic upgrade head
```

---

## 🛠️ Development Setup

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn src.main:app --reload
```

---

## 🔑 Key Patterns

- **Repository Pattern**: All database operations go through CRUD repositories
- **Dependency Injection**: Use `fastapi.Depends()` for sessions and repositories
- **Async/Await**: All database operations are asynchronous
- **Type Safety**: Pydantic schemas validate request/response data
- **JWT Auth**: Token-based authentication via `/authentication` endpoints

---

## 📚 Example: Querying Accounts

```python
# Using ORM (Recommended)
stmt = sqlalchemy.select(Account).where(Account.email == "user@example.com")
result = await session.execute(stmt)
account = result.scalar()

# Using Raw SQL
query = text("SELECT * FROM account WHERE email = :email")
result = await session.execute(query, {"email": "user@example.com"})
account = result.fetchone()
```

