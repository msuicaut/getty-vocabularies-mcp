# Getty Vocabularies MCP

An experimental MCP (Model Context Protocol) server connecting Claude to the Getty Vocabulary APIs for AAT, TGN, and ULAN authority lookups, developed to investigate the potential of large language models in subject analysis and authority control.

---

## What This Server Does

Getty Vocabularies MCP connects Claude Desktop to the Getty reconciliation and Linked Open Data APIs, allowing you to search and retrieve Getty authority data directly within your AI-assisted cataloging workflow.

Once installed, you can ask Claude things like:

- *"Search the AAT for headings related to fresco techniques"*
- *"Find the ULAN record for Rembrandt"*
- *"What are the narrower terms under 'Gothic' in the AAT?"*
- *"Retrieve the full record for this Getty URI"*

The server handles all the API calls, parses the responses, and returns structured data Claude can reason about.

---

## Who This Is For

- **Catalogers** using Claude Desktop who want AI-assisted subject heading work grounded in real Getty authority data
- **Library and museum systems staff** building or evaluating AI-assisted cataloging tools and workflows
- **Developers** integrating Getty vocabulary lookups into MCP-based systems

---

## Vocabularies Supported

| Key    | Full name                          | Keyword search |
|--------|------------------------------------|----------------|
| `aat`  | Art & Architecture Thesaurus       | ✅             |
| `tgn`  | Thesaurus of Geographic Names      | ✅             |
| `ulan` | Union List of Artist Names         | ✅             |
| `ia`   | Getty Iconography Authority        | URI only       |
| `cona` | Cultural Objects Name Authority    | URI only       |

---

## Tools

| Tool | Description |
|------|-------------|
| `search_getty` | Keyword search across AAT, TGN, ULAN, or all three. |
| `search_aat` | AAT keyword search — styles, periods, materials, techniques, object types, roles. |
| `search_ulan` | ULAN keyword search — artists, architects, designers, craftspeople. |
| `search_tgn` | TGN keyword search — place names, historical place names, geographic features. |
| `get_getty_record` | Full record by URI or numeric ID — preferred label, alt labels, scope note, broader/narrower/related terms. |
| `get_getty_scope_note` | Scope note only for a record. Faster than retrieving the full record. |
| `get_getty_hierarchy` | Broader and narrower terms, configurable to depth 1 or 2. |

---

## Notes on Search Behaviour

**Keyword search** matches anywhere in the term label. All three search
tools (`search_aat`, `search_ulan`, `search_tgn`) support partial matches
and are good first choices for most queries.

**CONA and IA** are not available via keyword search — the Getty
reconciliation service covers AAT, TGN, and ULAN only. If you have a
known URI for a CONA or IA record, use `get_getty_record` to retrieve it
directly.

**Preferred labels** are extracted using the Getty-specific
`gvp:prefLabelGVP` value chain where available, which reflects the
canonical Getty authorized form. When this chain is absent, the server
falls back to `skos:prefLabel`.

**Hierarchy depth** for `get_getty_hierarchy` is capped at 2. Deeper
traversal requires sequential network calls per level and is
impractically slow. Depth 1 is sufficient for most cataloging use cases.
TGN hierarchies in particular are very deep — depth 1 is recommended.

**Bare numeric IDs** passed to `get_getty_record`, `get_getty_scope_note`,
or `get_getty_hierarchy` default to the AAT namespace. Always prefer the
full URI returned by a search tool to avoid ambiguity when working with
TGN, ULAN, IA, or CONA records.

---

## Installation

### Requirements

- Python 3.10 or later
- Claude Desktop (or another MCP-compatible host)

### Install from GitHub

**Mac:**

```bash
pip3 install git+https://github.com/msuicaut/getty-vocabularies-mcp.git
```

**Windows (Anaconda Prompt):**

```
pip install git+https://github.com/msuicaut/getty-vocabularies-mcp.git
```

### Install from a local clone

```bash
git clone https://github.com/msuicaut/getty-vocabularies-mcp.git
cd getty-vocabularies-mcp
pip install -e .
```

On Windows with Anaconda, use Anaconda Prompt and add
`--break-system-packages` if prompted.

---

## Claude Desktop Configuration

After installation, add the server to your `claude_desktop_config.json`.
Claude Desktop uses a restricted PATH that does not include the Python
bin directory, so the full path to the command is required.

To find your exact path, run the following in Terminal (Mac) or
Anaconda Prompt (Windows):

- **Mac:** `which getty-vocabularies-mcp`
- **Windows:** `where getty-vocabularies-mcp`

The examples below are illustrative only — your actual path will differ
depending on your Python version and installation method.

**Mac (example):**
```json
{
  "mcpServers": {
    "getty-vocabularies": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.13/bin/getty-vocabularies-mcp"
    }
  }
}
```

**Windows/Anaconda (example):**
```json
{
  "mcpServers": {
    "getty-vocabularies": {
      "command": "C:\\Users\\username\\anaconda3\\Scripts\\getty-vocabularies-mcp.exe"
    }
  }
}
```

Always replace the path with the actual output of the `which` or `where`
command on your machine.

**Finding your config file:**

- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

After editing the config, quit Claude Desktop completely and reopen it.
The getty-vocabularies tools will be available in your next conversation.

### Verifying the installation

Once Claude Desktop is open, ask: *"What Getty vocabulary tools do you
have available?"* — you should see all seven tools listed.

---

## Updating

**Mac:**

```bash
pip3 install --upgrade git+https://github.com/msuicaut/getty-vocabularies-mcp.git
```

**Windows (Anaconda Prompt):**

```
pip install --upgrade git+https://github.com/msuicaut/getty-vocabularies-mcp.git
```

After updating, clear `__pycache__` and restart Claude Desktop fully.

---

## Troubleshooting

**Tools not appearing in Claude Desktop**

- Confirm the package installed without errors: `pip show getty-vocabularies-mcp`
- Confirm the command is available: `getty-vocabularies-mcp --help` (should start the server, not throw an error)
- Check that the config file path is correct for your OS
- Quit Claude Desktop fully (not just close the window) before reopening

**`prefLabel` missing from a record**

This usually means the URI passed to `get_getty_record` does not match
any node in the LOD response — typically because the vocabulary prefix
is wrong. Verify the URI using a search tool first and pass the full URI
from the search results.

**No scope note returned**

Scope notes are most consistently present in AAT records. Many TGN and
ULAN records do not have scope notes — a missing note is normal and does
not indicate an error.

**Changes to server.py not taking effect**

Python caches compiled bytecode in `__pycache__` folders. After editing
`server.py`, delete any `__pycache__` folders in the package directory
and restart Claude Desktop fully.

---

## License

GPLv3. See [LICENSE](LICENSE).

---

## Development Note

The code in this project was developed in collaboration with Claude, Anthropic's AI assistant. The design decisions — including tool selection, API choice, label extraction strategy, and the application of cataloging practice to the server's behaviour — reflect the author's professional cataloging expertise. Claude handled the implementation of those decisions in Python.

---

## Acknowledgement

This project makes use of the Getty Vocabulary Program's public APIs, including the Getty reconciliation service and the Getty Linked Open Data endpoints. The Getty Research Institute provides open access to AAT, TGN, ULAN, IA, and CONA through these services.

The project was inspired by and adapted from KL Tang's
[cataloger-mcp](https://github.com/kltng/cataloger-mcp), extended here
to apply to Getty Vocabularies lookup.

