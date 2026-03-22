# PyStack

## The Full Stack, From Scratch

### What's a "Full Stack"?

A **full stack** is all the layers of software that make a computer
useful. Think of it like a school. A school isn't just one thing -- it's
a building, a language, filing cabinets, locks, a phone system, a
library, an intercom, and hallways that connect them all.

PyStack connects **ten** educational projects, and each one teaches you
how a real piece of technology works:

| Project | What It Is | School Analogy |
|---------|-----------|----------------|
| **PyOS** | Operating system | The school building -- manages everything |
| **Pebble** | Programming language | The language students speak |
| **PyDB** | Database engine | The filing cabinet -- stores and retrieves data |
| **PyCrypt** | Cryptography toolkit | The combination lock -- keeps secrets safe |
| **PyWeb** | HTTP web server | The front office -- talks to visitors |
| **PyNet** | Networking library | The phone system -- connects to the outside world |
| **PyGit** | Version control | The yearbook archive -- tracks every change |
| **PySearch** | Full-text search engine | The library index -- finds things fast |
| **PyMQ** | Message queue | The intercom -- sends messages between rooms |
| **PyStack** | Integration layer | The hallways connecting everything |

You built all ten from scratch. PyStack is the hallways -- it lets
a single Pebble program use any of these systems together.

## Seven Pebble Modules

When PyStack boots, it registers **7 stdlib modules** in the Pebble
language. Each module comes from a different project. Just write
`import "modulename"` at the top of your Pebble program.

| Module | Project | Functions |
|--------|---------|-----------|
| `db` | PyDB | `db_query(sql)`, `db_execute(sql)`, `db_tables()` |
| `crypto` | PyCrypt | `hash(text)`, `caesar_encrypt(text, shift)`, `caesar_decrypt(text, shift)`, `hmac_sign(msg, key)`, `hmac_verify(msg, tag, key)` |
| `web` | PyWeb + PyNet | `http_get(url)`, `url_parse(url)` |
| `git` | PyGit | `git_hash(text)`, `git_diff(old, new)` |
| `net` | PyNet | `dns_lookup(hostname)`, `url_parse(url)`, `base64_encode(text)`, `base64_decode(text)` |
| `search` | PySearch | `search_create()`, `search_add(engine, id, text)`, `search_query(engine, query)` |
| `mq` | PyMQ | `mq_create(name)`, `mq_put(name, msg)`, `mq_get(name)`, `mq_publish(topic, msg)`, `mq_subscribe(topic)`, `mq_receive(topic)` |

That's **25 functions** across 7 modules. Every one of them calls
real code from a real project you built yourself.

## Four Ways to Use PyStack

### 1. Run a Pebble program with all modules available

Write a program that creates a table, adds data, and queries it:

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

The OS shell has `pebble`, `sql`, and all plugin commands built in:

```bash
pystack os
pystack-os> pebble eval 'print(1 + 2)'
3
pystack-os> sql CREATE TABLE scores (player TEXT, score INTEGER)
Table 'scores' created
pystack-os> hash hello
2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
pystack-os> dns example.com
93.184.216.34
pystack-os> mq-put orders "one coffee"
Queued on 'orders': one coffee
pystack-os> mq-get orders
one coffee
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
pydb> CREATE TABLE cards (name TEXT, power INTEGER)
pydb> INSERT INTO cards VALUES ('Pikachu', 55)
pydb> SELECT * FROM cards
```

## Shell Commands in PyStack OS

When you run `pystack os`, these commands are available at the prompt.
The first two come from the core adapters. The rest come from plugins.

| Command | What It Does | Provided By |
|---------|-------------|-------------|
| `pebble run <file>` | Run a Pebble program | Core (OS-Pebble adapter) |
| `pebble eval '<code>'` | Evaluate Pebble code inline | Core (OS-Pebble adapter) |
| `sql <statement>` | Run a SQL statement | Core (OS-DB adapter) |
| `hash <text>` | Print the SHA-256 hash of text | CryptoPlugin |
| `curl <url>` | Fetch a URL and print the body | WebPlugin |
| `dns <hostname>` | Resolve a hostname to an IP address | NetPlugin |
| `git-hash <text>` | Print the SHA-1 hash (Git-style) | GitPlugin |
| `git-diff <old> <new>` | Show a unified diff | GitPlugin |
| `mq-put <queue> <msg>` | Put a message on a named queue | MQPlugin |
| `mq-get <queue>` | Get the next message from a queue | MQPlugin |

Plus all the standard PyOS commands like `ls`, `cat`, `mkdir`, `help`,
and more.

## How It Works

PyStack uses **adapters** and **plugins** to connect projects together.
Think of them like translators between people who speak different
languages.

```
Your Pebble program calls db_query("SELECT * FROM pets")
    |
    +-- The adapter translates this for PyDB
    |       |
    |       +-- PyDB parses the SQL and runs it
    |               |
    |               +-- Results come back as a Pebble list
    |
    +-- print(results)  -- your program gets the data!
```

**Adapters** connect core systems (Pebble to PyDB, PyOS to Pebble).
They are small -- about 90 lines each.

**Plugins** connect additional projects (PyCrypt, PyWeb, PyGit, PyNet,
PySearch, PyMQ). Each plugin registers a Pebble module and optionally
adds shell commands.

## Plugin System

PyStack has **6 active plugins** that integrate projects beyond the
core three (PyOS, Pebble, PyDB):

| Plugin | Pebble Module | Shell Commands | Project |
|--------|--------------|----------------|---------|
| CryptoPlugin | `import "crypto"` | `hash` | PyCrypt |
| WebPlugin | `import "web"` | `curl` | PyWeb |
| GitPlugin | `import "git"` | `git-hash`, `git-diff` | PyGit |
| NetPlugin | `import "net"` | `dns` | PyNet |
| SearchPlugin | `import "search"` | (none) | PySearch |
| MQPlugin | `import "mq"` | `mq-put`, `mq-get` | PyMQ |

The `db` module is handled separately by the Pebble-DB adapter because
it needs a live database instance.

Each plugin is a Python class that extends the `Plugin` base class.
A plugin can do three things:

1. **Register a Pebble module** -- so programs can `import` it
2. **Add shell commands** -- available in `pystack os`
3. **Run boot logic** -- custom setup when PyStack starts

Plugins can also be discovered automatically via Python entry points
(the `pystack.plugins` group), so other packages can extend PyStack
without modifying its code.

## Installation

```bash
# Clone the repository
git clone https://github.com/robcox2910/pystack.git
cd pystack

# Install all dependencies (all 10 projects wired together)
uv sync --all-extras

# Run an example
pystack pebble examples/hello.pbl

# Run the tests
uv run pytest
```
