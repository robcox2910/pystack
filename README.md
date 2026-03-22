# PyStack

The full stack, from scratch.

PyStack connects **TEN** educational projects into one integrated
platform. Think of it like a school:

| Project | Role | School Analogy |
|---------|------|----------------|
| **PyOS** | Operating system | The school building |
| **Pebble** | Programming language | The language students speak |
| **PyDB** | Database engine | The filing cabinet |
| **PyCrypt** | Cryptography toolkit | The combination lock |
| **PyWeb** | HTTP web server | The front office |
| **PyNet** | Networking library | The phone system |
| **PyGit** | Version control | The yearbook archive |
| **PySearch** | Full-text search engine | The library index |
| **PyMQ** | Message queue | The intercom |
| **PyStack** | Integration layer | The hallways connecting everything |

PyStack is the hallways. Without hallways, you can't get from the
filing cabinet to the front office. PyStack lets a Pebble program
query a database, hash a password, fetch a web page, search documents,
and send messages -- all in one program.

## What Can You Do?

PyStack adds **7 Pebble modules** so your programs can use every
project. Just `import` the one you need.

### Database -- `import "db"`

```
import "db"

db_execute("CREATE TABLE pets (name TEXT, kind TEXT)")
db_execute("INSERT INTO pets VALUES ('Buddy', 'dog')")

let pets = db_query("SELECT * FROM pets")
for pet in pets {
    print(pet["name"] + " is a " + pet["kind"])
}

let tables = db_tables()
print(tables)
```

### Cryptography -- `import "crypto"`

```
import "crypto"

let h = hash("secret password")
print(h)

let encrypted = caesar_encrypt("HELLO", 3)
print(encrypted)

let decrypted = caesar_decrypt(encrypted, 3)
print(decrypted)

let tag = hmac_sign("important message", "my-key")
let ok = hmac_verify("important message", tag, "my-key")
print(ok)
```

### Web -- `import "web"`

```
import "web"

let page = http_get("http://example.com")
print(page)

let parts = url_parse("https://example.com:8080/hello?q=1")
print(parts["host"])
print(parts["port"])
```

### Git -- `import "git"`

```
import "git"

let h = git_hash("hello world")
print(h)

let d = git_diff("old version", "new version")
print(d)
```

### Networking -- `import "net"`

```
import "net"

let ip = dns_lookup("example.com")
print(ip)

let parts = url_parse("https://example.com/page")
print(parts["scheme"])

let encoded = base64_encode("Hello!")
print(encoded)

let decoded = base64_decode(encoded)
print(decoded)
```

### Search -- `import "search"`

```
import "search"

let engine = search_create()
search_add(engine, "doc1", "the cat sat on the mat")
search_add(engine, "doc2", "the dog chased the cat")

let results = search_query(engine, "cat")
print(results)
```

### Message Queue -- `import "mq"`

```
import "mq"

let q = mq_create("orders")
mq_put("orders", "one coffee please")
mq_put("orders", "two teas")

let msg = mq_get("orders")
print(msg)

mq_subscribe("news")
mq_publish("news", "school is cancelled!")
let messages = mq_receive("news")
print(messages)
```

## All Commands

| Command | What It Does |
|---------|-------------|
| `pystack pebble <file.pbl>` | Run a Pebble program with all 7 modules available |
| `pystack sql` | Interactive SQL REPL |
| `pystack os` | PyOS shell with Pebble, SQL, and plugin commands |
| `pystack web` | Browser-based UI at http://localhost:8080 |
| `pystack --help` | Show available commands |
| `pystack <file.pbl>` | Shortcut for `pystack pebble <file.pbl>` |

## Shell Commands

When you run `pystack os`, these commands are available at the
`pystack-os>` prompt:

| Command | What It Does | From |
|---------|-------------|------|
| `pebble run <file.pbl>` | Run a Pebble program | PyOS + Pebble |
| `pebble eval '<code>'` | Evaluate Pebble code inline | PyOS + Pebble |
| `sql <statement>` | Run a SQL statement | PyOS + PyDB |
| `hash <text>` | Print the SHA-256 hash | PyCrypt |
| `curl <url>` | Fetch a URL | PyWeb + PyNet |
| `dns <hostname>` | Resolve hostname to IP | PyNet |
| `git-hash <text>` | Print the SHA-1 hash (Git-style) | PyGit |
| `git-diff <old> <new>` | Show a diff between two strings | PyGit |
| `mq-put <queue> <msg>` | Put a message on a queue | PyMQ |
| `mq-get <queue>` | Get the next message from a queue | PyMQ |

## Quick Start

```bash
# Install dependencies (all 10 projects wired together)
uv sync --all-extras

# Run an example program
pystack pebble examples/hello.pbl

# Try the interactive SQL REPL
pystack sql

# Launch the OS shell
pystack os

# Open the browser UI
pystack web

# Run tests
uv run pytest
```

## Plugin System

PyStack uses a plugin system to integrate projects. There are
currently **6 active plugins**:

| Plugin | Pebble Module | Shell Commands |
|--------|--------------|----------------|
| CryptoPlugin | `crypto` | `hash` |
| WebPlugin | `web` | `curl` |
| GitPlugin | `git` | `git-hash`, `git-diff` |
| NetPlugin | `net` | `dns` |
| SearchPlugin | `search` | (none -- used from Pebble) |
| MQPlugin | `mq` | `mq-put`, `mq-get` |

The `db` module is registered separately via the Pebble-DB adapter
(it needs a database instance, so it's set up before the plugins).

Each plugin can:

- Add a new stdlib module to the Pebble language (`import "crypto"`)
- Add new commands to the PyOS shell (`hash`, `curl`, `dns`, etc.)
- Run custom setup logic at boot time

Plugins are discovered automatically via Python entry points, or
registered manually in the `PyStackEnvironment`.

## Related Projects

PyStack is part of an educational series where every layer of the
computing stack is built from scratch. All projects use TDD,
kid-friendly documentation, and are designed for learners aged 12+.

| Project | What It Teaches | Repository |
|---------|----------------|------------|
| PyOS | Operating systems | [robcox2910/py-os](https://github.com/robcox2910/py-os) |
| Pebble | Compilers and programming languages | [robcox2910/pebble-lang](https://github.com/robcox2910/pebble-lang) |
| PyDB | Relational databases | [robcox2910/pydb](https://github.com/robcox2910/pydb) |
| PyCrypt | Cryptography | [robcox2910/pycrypt](https://github.com/robcox2910/pycrypt) |
| PyWeb | HTTP web servers | [robcox2910/pyweb](https://github.com/robcox2910/pyweb) |
| PyNet | Computer networking | [robcox2910/pynet](https://github.com/robcox2910/pynet) |
| PyGit | Version control | [robcox2910/pygit](https://github.com/robcox2910/pygit) |
| PySearch | Search engines | [robcox2910/pysearch](https://github.com/robcox2910/pysearch) |
| PyMQ | Message queues | [robcox2910/pymq](https://github.com/robcox2910/pymq) |
| PyStack | Full-stack integration | [robcox2910/pystack](https://github.com/robcox2910/pystack) |

## Documentation

Full docs at [robcox2910.github.io/pystack](https://robcox2910.github.io/pystack/)

## License

MIT
