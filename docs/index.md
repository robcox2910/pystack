# PyStack

## The Full Stack, From Scratch

### What's a "Full Stack"?

A **full stack** is all the layers of software between you and the
computer. Think of it like a three-layer cake:

- **Bottom layer** -- the operating system (manages everything)
- **Middle layer** -- the programming language (writes the programs)
- **Top layer** -- the database (stores the data)

Most people never see these layers. But you've built all three from
scratch! **PyStack** is the frosting that holds the cake together.

| Project | What It Is | Analogy |
|---------|-----------|---------|
| **PyOS** | Operating system | The school building |
| **Pebble** | Programming language | The language students speak |
| **PyDB** | Database engine | The filing cabinet |
| **PyStack** | The glue | The hallways connecting everything |

## Four Ways to Use PyStack

### 1. Run a Pebble program with database access

Write a program that creates a table and queries it:

```
import "db"

db_execute("CREATE TABLE friends (name TEXT, age INTEGER)")
db_execute("INSERT INTO friends VALUES ('Alice', 12)")
db_execute("INSERT INTO friends VALUES ('Bob', 13)")

let friends = db_query("SELECT * FROM friends")
for f in friends {
    print(f["name"] + " is " + str(f["age"]))
}
```

```bash
pystack pebble hello_db.pbl
```

### 2. Use the integrated OS shell

The OS shell has `pebble` and `sql` commands built in:

```bash
pystack os
pystack-os> pebble eval 'print(1 + 2)'
3
pystack-os> sql CREATE TABLE scores (player TEXT, score INTEGER)
Table 'scores' created
pystack-os> ls /data
scores.json
```

### 3. Open the web UI

A browser-based interface with three panels side by side:

```bash
pystack web
# Opens http://localhost:8080
```

- **OS Terminal** -- type shell commands
- **Pebble Editor** -- write and run code
- **SQL Console** -- query the database

### 4. Interactive SQL REPL

```bash
pystack sql
pydb> SELECT * FROM friends ORDER BY age
```

## The Database Functions

When a Pebble program does `import "db"`, it gets three functions:

| Function | What It Does | Example |
|----------|-------------|---------|
| `db_query(sql)` | Run a SELECT, get results | `db_query("SELECT * FROM t")` |
| `db_execute(sql)` | Run a write command, get status | `db_execute("INSERT INTO t VALUES (1)")` |
| `db_tables()` | List all table names | `db_tables()` |

## How It Works Under the Hood

PyStack uses **adapters** -- like translators between people who speak
different languages:

```
Pebble program calls db_query("SELECT * FROM cards")
    │
    ├── PyStack adapter translates this call
    │       │
    │       └── PyDB parses the SQL and runs it
    │               │
    │               └── Results come back as a Pebble list
    │
    └── print(results)  -- your program gets the data!
```

The adapters are small -- about 90 lines each. They don't contain any
database logic or compiler logic. They just connect the pieces.

## Plugin System

PyStack is designed to grow. Future components (like a web server or
version control system) can plug in without changing any existing code.
A plugin can:

- Add new commands to the PyOS shell
- Add new functions to the Pebble language
- Run custom setup when PyStack boots

## Installation

```bash
uv sync --all-extras
pystack pebble examples/hello.pbl
```
