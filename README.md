# PyStack

The full stack, from scratch.

PyStack connects **SEVENTEEN** educational projects into one integrated
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
| **PyKV** | Key-value store | The cubby holes — one labeled box per thing |
| **PyDocDB** | Document database | The index-card box — every card has its own fields |
| **PyGraphDB** | Graph database | The friendship map — who knows whom |
| **PyTSDB** | Time-series database | The attendance logbook — readings over time |
| **PyVecDB** | Vector database | The "find similar" recommendation board |
| **PyColDB** | Column-family store | The flexible report cards |
| **PyLLM** | Language model | The imagination — the brain that dreams up new text |
| **PyStack** | Integration layer | The hallways connecting everything |

PyStack is the hallways. Without hallways, you can't get from the
filing cabinet to the front office. PyStack lets a Pebble program
query a database, hash a password, fetch a web page, search documents,
and send messages -- all in one program.

## What Can You Do?

PyStack adds **14 Pebble modules** so your programs can use every
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

### Key-Value Store -- `import "kv"`

```
import "kv"

kv_set("name", "Alice")
let who = kv_get("name")
print(who)

kv_delete("name")
let keys = kv_keys()
print(keys)
```

### Document Database -- `import "docdb"`

```
import "docdb"

doc_insert("students", {"name": "Alice", "age": 14})
let results = doc_find("students", {"name": "Alice"})
print(results)

let total = doc_count("students")
print(total)
```

### Graph Database -- `import "graphdb"`

```
import "graphdb"

graph_add_node("alice", "Person")
graph_add_node("bob", "Person")
graph_add_edge("alice", "bob", "KNOWS")

let path = graph_shortest_path("alice", "bob")
print(path)
```

### Time-Series Database -- `import "tsdb"`

```
import "tsdb"

ts_add("temperature", 72.5)
ts_add("temperature", 74.0)

let readings = ts_query("temperature")
print(readings)

let avg = ts_avg("temperature", 3600)
print(avg)
```

### Vector Database -- `import "vecdb"`

```
import "vecdb"

vec_insert("song1", [0.9, 0.1, 0.3])
vec_insert("song2", [0.2, 0.8, 0.4])

let similar = vec_search([0.85, 0.15, 0.35], 1)
print(similar)
```

### Column-Family Store -- `import "coldb"`

```
import "coldb"

col_set("grades", "alice", "math", "A+")
let grade = col_get("grades", "alice", "math")
print(grade)
```

### Language Model -- `import "llm"`

```
import "llm"

let code = llm_generate("add two numbers")
print(code)

let valid = llm_write_pebble("add two numbers")
print(valid)

let name = llm_dream("pik")
print(name)
```

`llm_generate` lets the model write freely, so its Pebble-flavoured code doesn't
always parse. `llm_write_pebble` calls in PyLLM's grammar **referee**, which
vetoes every illegal character, so what comes back is always real, parseable
Pebble. A plain-English request is pinned to the top as a comment and the model
writes code underneath:

```
# add two numbers

let x = step()

let z = j

count = 95 - (81 + 54)
let z = 88 - b % y
```

## All Commands

| Command | What It Does |
|---------|-------------|
| `pystack pebble <file.pbl>` | Run a Pebble program with all 14 modules available |
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
| `webdemo` | Start a real PyWeb async server on localhost: public page, a doorman who says 401 until you log in, a session cookie wristband, then three live events | PyWeb |
| `dns <hostname>` | Resolve hostname to IP | PyNet |
| `overlap [n] [seconds]` | Run n sleeps at once on PyNet's event loop and time them | PyNet |
| `netecho <text>` | Send a message through a local PyNet server and time the round trip | PyNet |
| `wsecho <text>` | Send a message through a local PyNet WebSocket server and print the echo | PyNet |
| `git-hash <text>` | Print the Git blob hash (same as `git hash-object`) | PyGit |
| `git-diff <old> <new>` | Show a diff between two strings | PyGit |
| `mq-put <queue> <msg>` | Put a message on a queue | PyMQ |
| `mq-get <queue>` | Get the next message from a queue | PyMQ |
| `mqnet` | Run a real PyMQ broker on localhost: one worker crashes, its lease comes back to another, a poison job lands in the dead-letter box | PyMQ |
| `dbcrash` | Pull the plug on a journalled PyDB: a helper commits three job runs (with dates and timestamps) and dies mid-way through a fourth; reopening brings back the three and not the fourth | PyDB |
| `kv-set <key> <value>` | Store a value under a key | PyKV |
| `kv-get <key>` | Get a value by key | PyKV |
| `kv-delete <key>` | Delete a key | PyKV |
| `kv-keys` | List all keys | PyKV |
| `doc-insert <collection> <json>` | Insert a document | PyDocDB |
| `doc-find <collection> [query]` | Find documents | PyDocDB |
| `doc-count <collection>` | Count documents | PyDocDB |
| `graph <add-node\|add-edge\|path> ...` | Graph database operations | PyGraphDB |
| `ts-add <series> <value>` | Add a data point | PyTSDB |
| `ts-query <series>` | Query a series | PyTSDB |
| `ts-avg <series> <window_seconds>` | Average over a time window | PyTSDB |
| `vec <insert\|search\|cosine> ...` | Vector database operations | PyVecDB |
| `col <set\|get> <family> <row> <col> [value]` | Column-family operations | PyColDB |
| `dream <prompt>` | Dream up new Pokemon names | PyLLM |

## Quick Start

```bash
# Install dependencies (pinned releases of all 16 sibling projects)
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

## Developing alongside a sibling

Every sibling project is pinned to a release tag in `pyproject.toml`
(`[tool.uv.sources]`), and `uv.lock` records the exact commit. A change merged
into a sibling can't affect PyStack until PyStack chooses to upgrade.

To try an unreleased change from a sibling checkout next to this one, install
it over the pinned release:

```bash
uv pip install -e ../pebble-lang
uv run --no-sync pytest
```

Use `uv run --no-sync` while you do this: a plain `uv run` (like `uv sync`)
puts the pinned release back, which is how you undo the override.

To upgrade a sibling, edit its tag in `[tool.uv.sources]`, run
`uv lock --upgrade-package <name>`, and open a pull request so CI checks the
pair together.

## Releasing

1. Merge the change to `main`.
2. Tag it: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`.
   A change to the public API bumps the minor version (`v0.1.0` → `v0.2.0`);
   anything else bumps the patch (`v0.1.0` → `v0.1.1`).

## Your Data Is Saved

PyStack is like a real database: what you store is still there next time.
Your SQL tables and the data in `kv`, `docdb`, `graphdb`, `coldb`, `tsdb`,
`vecdb`, `search` and `mq` are all kept in the `pystack_data/` folder. Each
plugin has its own sub-folder (for example `pystack_data/kv/store.json`).

PyStack saves when it stops: `.quit` or `exit`, the end of a script, or
stopping the web server with Ctrl-C. Type `save` in the shell to save
straight away. If PyStack crashes, changes since the last save are lost.

Saving is crash-safe: a fresh copy is written beside the old file and
swapped in at once, so a file is never half-written. If a save file is ever
damaged, PyStack refuses to start and names the file, rather than starting
empty and overwriting your data.

Message queues (`mq`) work like a real broker: messages still waiting in a
queue are saved in `pystack_data/mq/queues.json` and are there next time, in
the same order. Pub/sub subscriptions are different. They are like live
radio: a message published while nobody is listening is gone, and
subscriptions don't outlive the run.

Because data is kept, running the same example twice adds the same data
twice. To start fresh, delete the `pystack_data/` folder (or just one
plugin's folder, like `pystack_data/kv/`). Saved search engines keep their
ids; `search_list()` lists them, so a later program can find them.

## Plugin System

PyStack uses a plugin system to integrate projects. Active plugins
include:

| Plugin | Pebble Module | Shell Commands |
|--------|--------------|----------------|
| CryptoPlugin | `crypto` | `hash` |
| WebPlugin | `web` | `curl`, `webdemo` |
| GitPlugin | `git` | `git-hash`, `git-diff` |
| NetPlugin | `net` | `dns`, `overlap`, `netecho`, `wsecho` |
| SearchPlugin | `search` | (none -- used from Pebble) |
| MQPlugin | `mq` | `mq-put`, `mq-get`, `mqnet` |
| PyDBPlugin | (none) | `dbcrash` |
| PySchedulerPlugin | (none) | `sched` |
| LLMPlugin | `llm` | `dream` |

The `db` module comes from the Pebble-DB adapter instead of a plugin,
because it needs this environment's database.

PyStack hands Pebble each environment's own modules on every run (through
Pebble's public `run_source`), so two environments never see each other's
data.

Each plugin can:

- Add a new stdlib module to the Pebble language (`import "crypto"`)
- Add new commands to the PyOS shell (`hash`, `curl`, `dns`, etc.)
- Load its saved data at start-up (`load_state(folder)`), save it
  (`save_state(folder)`) and clean up (`on_shutdown()`)
- Run custom setup logic at boot time (`on_boot()`)

A plugin keeps its data on itself (`self`), never in module-level
variables, and saves into its own folder, `pystack_data/<module>/`.

Plugins are discovered automatically via Python entry points, or
registered manually in the `PyStackEnvironment`.

<!-- series:start -->
## Related Projects

This project is one of a series that builds real systems "from scratch in Python" to teach how they work. See the [series home](https://robcox2910.github.io/) for the full story.

| Project | What it teaches | Repository | Docs |
| --- | --- | --- | --- |
| PyOS | Operating systems | [py-os](https://github.com/robcox2910/py-os) | [Docs](https://robcox2910.github.io/py-os/) |
| Pebble | Compilers and programming languages | [pebble-lang](https://github.com/robcox2910/pebble-lang) | [Docs](https://robcox2910.github.io/pebble-lang/) |
| PyDB | Relational databases | [pydb](https://github.com/robcox2910/pydb) | [Docs](https://robcox2910.github.io/pydb/) |
| PyKV | Key-value stores | [pykv](https://github.com/robcox2910/pykv) | [Docs](https://robcox2910.github.io/pykv/) |
| PyDocDB | Document databases | [pydoc-db](https://github.com/robcox2910/pydoc-db) | [Docs](https://robcox2910.github.io/pydoc-db/) |
| PyGraphDB | Graph databases | [pygraphdb](https://github.com/robcox2910/pygraphdb) | [Docs](https://robcox2910.github.io/pygraphdb/) |
| PyTSDB | Time-series databases | [pytsdb](https://github.com/robcox2910/pytsdb) | [Docs](https://robcox2910.github.io/pytsdb/) |
| PyVecDB | Vector databases | [pyvecdb](https://github.com/robcox2910/pyvecdb) | [Docs](https://robcox2910.github.io/pyvecdb/) |
| PyColDB | Column-family databases | [pycoldb](https://github.com/robcox2910/pycoldb) | [Docs](https://robcox2910.github.io/pycoldb/) |
| PyCrypt | Cryptography | [pycrypt](https://github.com/robcox2910/pycrypt) | [Docs](https://robcox2910.github.io/pycrypt/) |
| PyNet | Computer networking | [pynet](https://github.com/robcox2910/pynet) | [Docs](https://robcox2910.github.io/pynet/) |
| PyWeb | HTTP web servers | [pyweb](https://github.com/robcox2910/pyweb) | [Docs](https://robcox2910.github.io/pyweb/) |
| PyGit | Version control | [pygit](https://github.com/robcox2910/pygit) | [Docs](https://robcox2910.github.io/pygit/) |
| PySearch | Search engines | [pysearch](https://github.com/robcox2910/pysearch) | [Docs](https://robcox2910.github.io/pysearch/) |
| PyMQ | Message queues | [pymq](https://github.com/robcox2910/pymq) | [Docs](https://robcox2910.github.io/pymq/) |
| PyLLM | Language models (the brain) | [pyllm](https://github.com/robcox2910/pyllm) | [Docs](https://robcox2910.github.io/pyllm/) |
| **PyStack** | **Full-stack integration** | [pystack](https://github.com/robcox2910/pystack) | [Docs](https://robcox2910.github.io/pystack/) |
<!-- series:end -->

<!-- docs:start -->
## Documentation

Full docs (with kid-friendly explanations of every idea): https://robcox2910.github.io/pystack/
<!-- docs:end -->

## License

MIT
