# getty-vocabularies-mcp — MCP server for Getty Vocabulary APIs
# Copyright (C) 2026  May S. Chan (University of Toronto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from mcp.server.fastmcp import FastMCP
import requests
import traceback
import json

mcp = FastMCP("getty vocabularies mcp server")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keyword search — Getty OpenRefine reconciliation service
# Supports AAT, TGN, ULAN. Does not support CONA or IA (not yet LOD).
RECONCILE_ENDPOINT = "https://services.getty.edu/vocab/reconcile/"

# Full record retrieval — Getty LOD JSON-LD
# Pattern: https://vocab.getty.edu/{vocab}/{id}.json
LOD_BASE = "https://vocab.getty.edu"

VOCAB_URIS = {
    "aat":  "http://vocab.getty.edu/aat/",
    "tgn":  "http://vocab.getty.edu/tgn/",
    "ulan": "http://vocab.getty.edu/ulan/",
    "ia":   "http://vocab.getty.edu/ia/",
    "cona": "http://vocab.getty.edu/cona/",
}

VOCAB_NAMES = {
    "aat":  "Art & Architecture Thesaurus",
    "tgn":  "Thesaurus of Geographic Names",
    "ulan": "Union List of Artist Names",
    "ia":   "Getty Iconography Authority",
    "cona": "Cultural Objects Name Authority",
}

# Vocabs supported by the reconciliation service search
SEARCH_SUPPORTED = {"aat", "tgn", "ulan"}

_HEADERS = {
    "User-Agent": "getty-vocabularies-mcp-server/1.0",
    "Accept":     "application/json",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_vocab(uri: str) -> str:
    """Detect vocabulary key from a URI."""
    for key, prefix in VOCAB_URIS.items():
        if uri.startswith(prefix):
            return key
    return "unknown"


def _normalise_uri(id_or_uri: str, default_vocab: str = "aat") -> tuple[str, str]:
    """
    Given a bare ID or full URI, return (canonical_uri, vocab_key).
    Bare IDs default to the specified vocabulary.
    Normalises to http:// form for consistency (Getty LOD uses http:// in @id values).
    """
    s = id_or_uri.strip()
    if s.startswith("http"):
        uri = s.rstrip("/").replace("https://", "http://")
    else:
        uri = f"http://vocab.getty.edu/{default_vocab}/{s}"
    return uri, _detect_vocab(uri)


def _lod_fetch(uri: str) -> dict:
    """
    Fetch a Getty LOD record as JSON-LD by appending .json to the URI.
    Uses https:// for the actual request (Getty redirects http:// to https://).
    """
    safe_uri = uri.replace("http://", "https://")
    url = safe_uri.rstrip("/") + ".json"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=15)
        response.raise_for_status()
        return {"data": response.json()}
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def _reconcile_search(query: str, vocab_type: str, limit: int) -> dict:
    """
    POST a keyword query to the Getty reconciliation service.
    vocab_type: one of "/aat", "/tgn", "/ulan", "/all"
    Returns normalised list of {id, label, vocab, uri} or error dict.
    """
    queries_payload = json.dumps({
        "q0": {
            "query": query,
            "type":  vocab_type,
            "limit": limit,
        }
    })
    try:
        response = requests.post(
            RECONCILE_ENDPOINT,
            data={"queries": queries_payload},
            headers={**_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for candidate in data.get("q0", {}).get("result", []):
            raw_id = candidate.get("id", "")
            # raw_id is like "aat/300056048" — prepend the base URI
            if raw_id:
                uri = f"http://vocab.getty.edu/{raw_id.lstrip('/')}"
            else:
                uri = ""
            vocab = _detect_vocab(uri)
            getty_id = uri.rstrip("/").split("/")[-1]
            results.append({
                "id":    getty_id,
                "label": candidate.get("name", ""),
                "vocab": vocab,
                "uri":   uri,
                "score": candidate.get("score", None),
            })
        return {"results": results}
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


def _parse_lod_record(data: list, uri: str) -> dict:
    """
    Parse a Getty JSON-LD graph (list of nodes) into a structured record dict.
    Extracts prefLabel, altLabels, scopeNote, broader, narrower, related.
    """
    SKOS      = "http://www.w3.org/2004/02/skos/core#"
    GVP       = "http://vocab.getty.edu/ontology#"
    SKOSXL    = "http://www.w3.org/2008/05/skos-xl#"
    RDF_TYPE  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    # Normalise URI for node matching (try both http and https)
    canon    = uri.rstrip("/").replace("https://", "http://")
    canon_s  = uri.rstrip("/").replace("http://", "https://")

    # Find the primary node
    primary = None
    for node in data:
        node_id = node.get("@id", "").rstrip("/")
        if node_id in (canon, canon_s):
            primary = node
            break

    if primary is None:
        return {"error": f"Could not find primary node for URI {uri} in LOD response"}

    def _first_en(values):
        """Return first English (or untagged) string value from a JSON-LD value list."""
        if not values:
            return ""
        for v in values:
            if isinstance(v, dict):
                lang = v.get("@language", "")
                val  = v.get("@value", "")
                if lang in ("en", "en-us", "") and val:
                    return val
            elif isinstance(v, str):
                return v
        return ""

    def _all_en(values):
        """Return all English (or untagged) string values from a JSON-LD value list."""
        results = []
        if not values:
            return results
        for v in values:
            if isinstance(v, dict):
                lang = v.get("@language", "")
                val  = v.get("@value", "")
                if lang in ("en", "en-us", "") and val and val not in results:
                    results.append(val)
            elif isinstance(v, str) and v not in results:
                results.append(v)
        return results

    def _uri_list(values):
        """Extract list of @id URIs from a JSON-LD value list."""
        uris = []
        for v in values:
            if isinstance(v, dict) and "@id" in v:
                uris.append(v["@id"].rstrip("/"))
        return uris

    record = {
        "id":        canon.split("/")[-1],
        "uri":       canon,
        "vocab":     _detect_vocab(canon),
        "vocabName": VOCAB_NAMES.get(_detect_vocab(canon), ""),
    }

    # Preferred label — try gvp:prefLabelGVP value chain first, then skos:prefLabel
    pref = ""
    gvp_label_refs = _uri_list(primary.get(f"{GVP}prefLabelGVP", []))
    for ref_uri in gvp_label_refs:
        for node in data:
            if node.get("@id", "").rstrip("/") == ref_uri:
                lf = _first_en(node.get(f"{SKOSXL}literalForm", []))
                if lf:
                    pref = lf
                    break
        if pref:
            break
    if not pref:
        pref = _first_en(primary.get(f"{SKOS}prefLabel", []))
    if pref:
        record["prefLabel"] = pref

    # Alt labels
    alts = _all_en(primary.get(f"{SKOS}altLabel", []))
    if alts:
        record["altLabels"] = alts

    # Scope note
    notes = _all_en(primary.get(f"{SKOS}scopeNote", []))
    if notes:
        record["scopeNote"] = notes[0] if len(notes) == 1 else notes

    # Record types
    types = []
    for t in _uri_list(primary.get("@type", [])):
        short = t.split("#")[-1].split("/")[-1]
        if short and short not in ("Concept", "Resource") and short not in types:
            types.append(short)
    if types:
        record["recordTypes"] = types

    # Broader / narrower / related — resolve labels from graph
    def _resolve_related(uri_list):
        resolved = []
        for rel_uri in uri_list:
            rel_label = ""
            for node in data:
                if node.get("@id", "").rstrip("/") == rel_uri.rstrip("/"):
                    # Try prefLabelGVP chain
                    for ref in _uri_list(node.get(f"{GVP}prefLabelGVP", [])):
                        for n2 in data:
                            if n2.get("@id", "").rstrip("/") == ref:
                                lf = _first_en(n2.get(f"{SKOSXL}literalForm", []))
                                if lf:
                                    rel_label = lf
                                    break
                        if rel_label:
                            break
                    if not rel_label:
                        rel_label = _first_en(node.get(f"{SKOS}prefLabel", []))
                    break
            resolved.append({
                "id":    rel_uri.rstrip("/").split("/")[-1],
                "label": rel_label,
                "uri":   rel_uri,
            })
        return resolved

    broader_uris  = _uri_list(primary.get(f"{SKOS}broader", []))
    narrower_uris = _uri_list(primary.get(f"{SKOS}narrower", []))[:25]
    related_uris  = _uri_list(primary.get(f"{SKOS}related", []))[:10]

    if broader_uris:
        record["broaderTerms"]  = _resolve_related(broader_uris)
    if narrower_uris:
        record["narrowerTerms"] = _resolve_related(narrower_uris)
    if related_uris:
        record["relatedTerms"]  = _resolve_related(related_uris)

    return record


# ---------------------------------------------------------------------------
# Tool 1 — Keyword search (AAT, TGN, ULAN via reconciliation service)
# ---------------------------------------------------------------------------

@mcp.tool()
def search_getty(query: str, vocab: str = "all", limit: int = 25) -> dict:
    """
    Search Getty Vocabularies by keyword using the Getty reconciliation service.

    Parameters
    ----------
    query : str
        Search term(s). Partial matches supported.
    vocab : str
        Which vocabulary to search. One of: aat, tgn, ulan, all.
        Default is "all". Note: CONA and IA are not supported by this
        search endpoint — use get_getty_record with a known URI instead.
    limit : int
        Maximum number of results to return. Default 25.

    Returns
    -------
    dict with a 'results' list of {id, label, vocab, uri, score} dicts.
    """
    v = vocab.strip().lower()
    type_map = {
        "aat":  "/aat",
        "tgn":  "/tgn",
        "ulan": "/ulan",
        "all":  "/all",
    }
    if v not in type_map:
        return {
            "error": (
                f"Unknown vocabulary '{vocab}'. "
                "Search supports: aat, tgn, ulan, all. "
                "CONA and IA are not available via keyword search."
            )
        }
    result = _reconcile_search(query, type_map[v], limit)
    if "results" in result:
        result["query"] = query
        result["vocab"] = vocab
    return result


# ---------------------------------------------------------------------------
# Tool 2 — Full record retrieval by URI or ID
# ---------------------------------------------------------------------------

@mcp.tool()
def get_getty_record(id_or_uri: str) -> dict:
    """
    Retrieve the full record for a Getty authority by URI or numeric ID.

    Parameters
    ----------
    id_or_uri : str
        A full Getty URI (e.g. "http://vocab.getty.edu/aat/300056048") or
        a numeric Getty ID. Bare IDs default to AAT — always prefer the
        full URI from search results to avoid ambiguity.

    Returns
    -------
    dict with: id, uri, vocab, vocabName, prefLabel, altLabels, scopeNote,
    recordTypes, broaderTerms, narrowerTerms, relatedTerms.
    Fields absent from the record are omitted.

    Notes
    -----
    Works with AAT, TGN, and ULAN. CONA and IA records may not return
    full structured data as they are not fully available as LOD.
    """
    uri, vocab = _normalise_uri(id_or_uri)
    result = _lod_fetch(uri)
    if "error" in result:
        return result
    data = result.get("data", [])
    if not isinstance(data, list):
        return {"error": "Unexpected LOD response format", "data": data}
    record = _parse_lod_record(data, uri)
    if not record.get("prefLabel") and "error" not in record:
        record["warning"] = (
            f"No data found for URI {uri}. "
            "Verify the ID is correct and the vocabulary prefix matches."
        )
    return record


# ---------------------------------------------------------------------------
# Tool 3 — Scope note retrieval
# ---------------------------------------------------------------------------

@mcp.tool()
def get_getty_scope_note(id_or_uri: str) -> dict:
    """
    Retrieve the scope note (usage guidance) for a Getty authority record.

    Parameters
    ----------
    id_or_uri : str
        A full Getty URI or numeric Getty ID. Full URI preferred.

    Returns
    -------
    dict with: id, uri, vocab, prefLabel, scopeNote.
    If no scope note exists, a 'message' key explains this.

    Notes
    -----
    Scope notes are most consistently present in AAT records.
    """
    record = get_getty_record(id_or_uri)
    if "error" in record:
        return record
    result = {
        "id":        record.get("id", ""),
        "uri":       record.get("uri", ""),
        "vocab":     record.get("vocab", ""),
        "prefLabel": record.get("prefLabel", ""),
    }
    if "scopeNote" in record:
        result["scopeNote"] = record["scopeNote"]
    else:
        result["message"] = (
            "No scope note found for this record. "
            "Scope notes are most consistently present in AAT records."
        )
    return result


# ---------------------------------------------------------------------------
# Tool 4 — Hierarchy navigation
# ---------------------------------------------------------------------------

@mcp.tool()
def get_getty_hierarchy(id_or_uri: str, depth: int = 1) -> dict:
    """
    Retrieve broader and narrower terms for a Getty authority record.

    Parameters
    ----------
    id_or_uri : str
        A full Getty URI or numeric Getty ID.
    depth : int
        Levels of hierarchy to retrieve. 1 = immediate broader/narrower
        only. Maximum 2 for LOD retrieval (deeper levels require
        multiple sequential fetches and are slower). Default 1.

    Returns
    -------
    dict with: id, uri, vocab, prefLabel, broaderTerms, narrowerTerms.
    Each term entry has: id, label, uri.

    Notes
    -----
    Depth > 1 requires additional network calls (one per level).
    TGN hierarchy is very deep — depth=1 is usually sufficient.
    """
    depth = max(1, min(depth, 2))
    record = get_getty_record(id_or_uri)
    if "error" in record:
        return record

    result = {
        "id":          record.get("id", ""),
        "uri":         record.get("uri", ""),
        "vocab":       record.get("vocab", ""),
        "vocabName":   record.get("vocabName", ""),
        "prefLabel":   record.get("prefLabel", ""),
        "depth":       depth,
        "broaderTerms":  record.get("broaderTerms", []),
        "narrowerTerms": record.get("narrowerTerms", []),
    }

    # If depth=2, fetch one level deeper for each broader/narrower term
    if depth == 2:
        for term in result["broaderTerms"]:
            if term.get("uri"):
                parent = get_getty_record(term["uri"])
                if "error" not in parent:
                    term["broaderTerms"] = parent.get("broaderTerms", [])

        for term in result["narrowerTerms"][:10]:  # limit to avoid excessive calls
            if term.get("uri"):
                child = get_getty_record(term["uri"])
                if "error" not in child:
                    term["narrowerTerms"] = child.get("narrowerTerms", [])

    return result


# ---------------------------------------------------------------------------
# Tools 5-7 — Vocabulary-specific convenience search wrappers
# ---------------------------------------------------------------------------

@mcp.tool()
def search_aat(query: str, limit: int = 25) -> dict:
    """
    Search the Getty Art & Architecture Thesaurus (AAT) by keyword.

    Use for: styles, periods, materials, techniques, object types, roles,
    physical attributes, and other concepts used in art and architecture
    cataloging.

    Parameters
    ----------
    query : str
        Search term(s). E.g. "oil painting", "Baroque", "fresco".
    limit : int
        Maximum results to return. Default 25.

    Returns
    -------
    dict with 'results' list of {id, label, vocab, uri, score} dicts.
    """
    return search_getty(query=query, vocab="aat", limit=limit)


@mcp.tool()
def search_ulan(query: str, limit: int = 25) -> dict:
    """
    Search the Getty Union List of Artist Names (ULAN) by keyword.

    Use for: artists, architects, designers, craftspeople, and other
    makers of cultural objects. Full records via get_getty_record include
    birth/death dates and nationality data.

    Parameters
    ----------
    query : str
        Artist or architect name. E.g. "Rembrandt", "Zaha Hadid".
    limit : int
        Maximum results to return. Default 25.

    Returns
    -------
    dict with 'results' list of {id, label, vocab, uri, score} dicts.
    """
    return search_getty(query=query, vocab="ulan", limit=limit)


@mcp.tool()
def search_tgn(query: str, limit: int = 25) -> dict:
    """
    Search the Getty Thesaurus of Geographic Names (TGN) by keyword.

    Use for: place names, historical place names, geographic features.
    Full records via get_getty_record include place type and hierarchy.

    Parameters
    ----------
    query : str
        Place name. E.g. "Florence", "Constantinople", "Nile River".
    limit : int
        Maximum results to return. Default 25.

    Returns
    -------
    dict with 'results' list of {id, label, vocab, uri, score} dicts.
    """
    return search_getty(query=query, vocab="tgn", limit=limit)


# ---------------------------------------------------------------------------
# Resources (convenience wrappers)
# ---------------------------------------------------------------------------

@mcp.resource("getty://aat/search/{query}")
def aat_resource(query: str) -> dict:
    return search_aat(query)

@mcp.resource("getty://ulan/search/{query}")
def ulan_resource(query: str) -> dict:
    return search_ulan(query)

@mcp.resource("getty://tgn/search/{query}")
def tgn_resource(query: str) -> dict:
    return search_tgn(query)

@mcp.resource("getty://record/{uri}")
def record_resource(uri: str) -> dict:
    return get_getty_record(uri)

@mcp.resource("getty://hierarchy/{uri}")
def hierarchy_resource(uri: str) -> dict:
    return get_getty_hierarchy(uri)


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def start_mcp_server(port: int = None):
    """Starts the Getty MCP server in HTTP/SSE mode or stdio mode."""
    import uvicorn
    if port is not None:
        print(f"Starting getty vocabularies mcp server on HTTP port {port}")
        uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=port)
    else:
        print("Starting getty vocabularies mcp server in stdio mode")
        mcp.run()


if __name__ == "__main__":
    import sys
    cli_port = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cli_port = int(sys.argv[1])
    start_mcp_server(port=cli_port)
