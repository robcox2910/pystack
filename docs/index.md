# PyStack

## The Full Stack, From Scratch

Imagine building an entire computer from scratch -- the operating
system, the programming language, and the database. Then connecting
them all together so programs you write can store and query data,
managed by an OS you built.

That's **PyStack**.

It connects three projects you've already built:

| Project | What It Is | Analogy |
|---------|-----------|---------|
| **PyOS** | Operating system simulator | The school building |
| **Pebble** | Programming language | The language students speak |
| **PyDB** | Database engine | The filing cabinet |

PyStack is the **wiring** that connects them. It lets Pebble programs
talk to PyDB databases, all running inside PyOS.

## How It Works

```
Your Pebble program
    │
    ├── import "db"
    ├── db_execute("CREATE TABLE ...")
    ├── db_query("SELECT * FROM ...")
    │
    └── PyStack adapter translates these calls
            │
            └── PyDB executes the SQL
                    │
                    └── Results flow back to your program
```

## Getting Started

Write a Pebble program, save it as `hello_db.pbl`:

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

Run it:

```bash
pystack pebble hello_db.pbl
```

That's a Pebble program querying a PyDB database. The full stack,
from scratch.
