# Database Provider Architecture

This document describes the refactored database layer that uses SOLID principles to support multiple database backends.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   database_manager.py                       │
│                   (Routes & API logic)                      │
└────────────────────────┬────────────────────────────────────┘
                         │ uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              DatabaseFactory (database_factory.py)          │
│              Creates provider based on DB_BACKEND env var   │
└────────────────────────┬────────────────────────────────────┘
                         │ creates
        ┌────────────────┴────────────────┐
        ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│ SupabaseProvider     │          │  MariaDBProvider     │
│ (supabase_provider)  │          │  (mariadb_provider)  │
└──────────────────────┘          └──────────────────────┘
        ▲                                  ▲
        └────────────────┬─────────────────┘
                         │ implements
                         ▼
         ┌──────────────────────────────┐
         │  DatabaseProvider Interface  │
         │  (database_provider.py)      │
         └──────────────────────────────┘
```

## Key Components

### 1. **DatabaseProvider (Abstract Interface)**
File: `modules/database_provider.py`

Defines the contract that all database implementations must follow:
- `connect()` - Establish connection
- `is_connected()` - Check connection status
- `table(name)` - Get query builder for a table
- `close()` - Close connection

### 2. **TableQuery (Abstract Interface)**
Provides a fluent query builder API:
```python
db.table('subjects')
  .select('id,name')
  .eq('subject_id', 8)
  .limit(10)
  .execute()
```

### 3. **SupabaseProvider**
File: `modules/supabase_provider.py`

Implementation for Supabase REST API:
- Inherits from `DatabaseProvider`
- Wraps Supabase client
- Implements `SupabaseTableQuery` for query building

### 4. **MariaDBProvider**
File: `modules/mariadb_provider.py`

Implementation for MariaDB:
- Inherits from `DatabaseProvider`
- Wraps existing `MariaDBAdapter`
- Implements `MariaDBTableQuery` for query building

### 5. **DatabaseFactory**
File: `modules/database_factory.py`

Factory pattern for creating providers:
```python
# Reads DB_BACKEND env var, returns appropriate provider
db = DatabaseFactory.create_provider()

# Or specify explicitly
db = DatabaseFactory.create_provider(backend='mariadb')
```

## Configuration

### Enable Supabase (Default)
```env
DB_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-api-key
```

### Enable MariaDB
```env
DB_BACKEND=mariadb
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=password
MARIADB_DATABASE=schooldb
```

Or use connection string:
```env
DB_BACKEND=mariadb
MARIADB_URL=mysql+pymysql://user:password@host:3306/database
```

## SOLID Principles Applied

### Single Responsibility Principle (SRP)
- Each provider class handles only its database type
- Factory handles only provider creation
- Routes don't know about database implementation details

### Open/Closed Principle (OCP)
- Open for extension: Add new providers without modifying existing code
- Closed for modification: Core interface remains stable

### Liskov Substitution Principle (LSP)
- Any `DatabaseProvider` can be used interchangeably
- Routes work with interface, not concrete implementations

### Interface Segregation Principle (ISP)
- Separate interfaces for different concerns
- `DatabaseProvider` vs `TableQuery` vs `QueryResult`

### Dependency Inversion Principle (DIP)
- Routes depend on abstract `DatabaseProvider`, not concrete classes
- Factory handles concrete type selection

## Usage in Routes

Routes receive the provider via context:
```python
def register_some_routes(app, context):
    get_supabase = context['get_supabase']  # Returns DatabaseProvider
    
    @app.route('/some-endpoint')
    def handler():
        db = get_supabase()
        result = db.table('chunks').select('*').eq('id', 5).execute()
        return result.data
```

## Adding a New Database Backend

1. Create provider file: `modules/new_db_provider.py`
2. Implement `DatabaseProvider` interface
3. Add factory method to `DatabaseFactory._create_new_db_provider()`
4. Add environment variables to `.env.example`
5. Set `DB_BACKEND=new_db` in `.env`

Example:
```python
# modules/new_db_provider.py
from modules.database_provider import DatabaseProvider

class PostgreSQLProvider(DatabaseProvider):
    def connect(self) -> bool:
        # Implementation
        pass
    
    def table(self, table_name: str):
        # Return TableQuery implementation
        pass
```

## Backward Compatibility

The old variable name `supabase` is replaced with `db`, but the same interface is maintained:
- `get_supabase()` now returns the abstract `DatabaseProvider`
- Routes use the same `.table().select().eq().execute()` pattern
- No changes needed in route logic

## Testing

To test with different backends:

```bash
# Test with Supabase
DB_BACKEND=supabase npm run dev

# Test with MariaDB
DB_BACKEND=mariadb npm run dev
```

## Error Handling

Each provider's `execute()` returns a `QueryResult`:
```python
result = db.table('chunks').select('*').execute()
if result.data:
    # Process results
else:
    # Handle empty result
    
# Check for errors
if result.status == 'error':
    # Handle error
```
