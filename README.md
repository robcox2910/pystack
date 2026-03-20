# PyStack

The full stack, from scratch.

PyStack is a unified educational platform that integrates three projects
into one cohesive environment:

- **PyOS** -- an operating system simulator
- **Pebble** -- a programming language with compiler and bytecode VM
- **PyDB** -- a relational database engine

Write Pebble programs that query PyDB databases, all running on a
simulated operating system. Every layer is built from scratch, explained
with analogies a 12-year-old can follow.

## Example

Write a Pebble program (`gradebook.pbl`):

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

Run it:

```bash
pystack pebble gradebook.pbl
```

Output:

```
Alice: 95
Bob: 87
```

## Quick Start

```bash
# Install dependencies (including PyOS, Pebble, and PyDB)
uv sync --all-extras

# Run a Pebble program with database access
pystack pebble examples/hello.pbl

# Launch interactive SQL REPL
pystack sql

# Run tests
uv run pytest
```

## License

MIT
