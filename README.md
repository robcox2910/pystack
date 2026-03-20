# PyStack

The full stack, from scratch.

PyStack connects three educational projects into one integrated platform:

- **PyOS** -- an operating system (the school building)
- **Pebble** -- a programming language (the language students speak)
- **PyDB** -- a database engine (the filing cabinet)

Think of a "full stack" like a three-layer cake. The OS is the bottom
layer, the programming language is the middle, and the database is the
top. PyStack is the frosting that holds them together.

## What Can You Do?

### Write programs that talk to a database

```
import "db"

db_execute("CREATE TABLE grades (student TEXT, score INTEGER)")
db_execute("INSERT INTO grades VALUES ('Alice', 95)")
db_execute("INSERT INTO grades VALUES ('Bob', 87)")

let rows = db_query("SELECT student, score FROM grades ORDER BY score DESC")
for row in rows {
    print(row["student"] + ": " + str(row["score"]))
}
```

```bash
pystack pebble examples/gradebook.pbl
# Alice: 95
# Bob: 87
```

### Use an integrated OS shell

```bash
pystack os
pystack-os> pebble run /programs/hello.pbl   # Run Pebble programs
pystack-os> sql SELECT * FROM scores          # Query the database
pystack-os> ls /data                          # See database files in the OS
```

### Open the web UI

```bash
pystack web
# Opens http://localhost:8080 with three panels:
# - OS Terminal
# - Pebble Code Editor
# - SQL Console
```

### Or just use SQL

```bash
pystack sql
pydb> CREATE TABLE cards (name TEXT, power INTEGER)
pydb> INSERT INTO cards VALUES ('Pikachu', 55)
pydb> SELECT * FROM cards
```

## Quick Start

```bash
# Install dependencies (including PyOS, Pebble, and PyDB)
uv sync --all-extras

# Run the example program
pystack pebble examples/hello.pbl

# Launch the web UI
pystack web

# Run tests
uv run pytest
```

## All Commands

| Command | What It Does |
|---------|-------------|
| `pystack pebble <file.pbl>` | Run a Pebble program with database access |
| `pystack sql` | Interactive SQL REPL |
| `pystack os` | PyOS shell with Pebble + SQL integration |
| `pystack web` | Browser-based UI at http://localhost:8080 |
| `pystack --help` | Show available commands |

## Pebble Database Functions

When a Pebble program does `import "db"`, it gets three functions:

| Function | What It Does |
|----------|-------------|
| `db_query(sql)` | Run a SELECT and get results as a list of dicts |
| `db_execute(sql)` | Run CREATE/INSERT/UPDATE/DELETE and get a status message |
| `db_tables()` | Get a list of all table names |

## Plugin System

PyStack is extensible. Future components (like a web server or version
control) can plug in without changing core code. See the plugin
documentation for details.

## License

MIT
