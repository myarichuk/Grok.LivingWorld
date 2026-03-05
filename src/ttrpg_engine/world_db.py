"""Lightweight world database with mmap-backed append log and inverted indexes."""

from __future__ import annotations

import base64
import json
import mmap
import os
import re
import zlib
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

_TOKEN_PATTERN = re.compile(r"[a-z0-9_']+")
_INDEX_FIELDS = (
    "text",
    "description",
    "event",
    "name",
    "action",
    "impulse",
    "zone",
    "scene_id",
)
_COMPRESSED_FIELD = "__payload_zlib_b64__"
_DOC_COMPRESSED_FIELD = "__doc_zlib_b64__"
_COMPRESS_MIN_BYTES = 256


class WorldDB:
    """Append-only document store for world state snapshots and events.

    Storage format is newline-delimited JSON where each append writes exactly one
    document line. The database keeps a full in-memory cache of documents and
    indexes for fast search, and uses an append-only file for persistence.
    """

    def __init__(self, path: str = "world.db") -> None:
        self.path = path
        self._index: dict[str, list[str]] = defaultdict(list)
        self._turn_index: dict[int, list[str]] = defaultdict(list)
        self._scene_index: dict[str, list[str]] = defaultdict(list)
        self._faction_index: dict[str, list[str]] = defaultdict(list)
        self._data: dict[str, dict[str, Any]] = {}
        self._offsets: dict[str, tuple[int, int]] = {}
        self._tombstones: set[str] = set()
        self._next_id = 1
        self._dirty = False
        self._corrupt_lines = 0

        self._fh: Any | None = None
        self._mmap: mmap.mmap | None = None
        self._mmap_size = 0
        self._mmap_stale = False

        self._open_storage()
        self._rebuild_from_file()

    def close(self) -> None:
        """Release mmap/file handles.

        Safe to call multiple times.
        """
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self._mmap_size = 0
        self._mmap_stale = False

    def __enter__(self) -> WorldDB:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _open_storage(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "wb"):
                pass

        self.close()
        self._fh = open(self.path, "r+b")
        self._remap()

    def _remap(self) -> None:
        if self._fh is None:
            return

        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None

        self._fh.flush()
        size = os.path.getsize(self.path)
        self._mmap_size = size
        if size > 0:
            self._mmap = mmap.mmap(self._fh.fileno(), length=0, access=mmap.ACCESS_READ)
        self._mmap_stale = False

    def _ensure_mmap_for_end(self, end: int) -> None:
        if self._mmap is None or self._mmap_stale or end > self._mmap_size:
            self._remap()

    def _rebuild_from_file(self) -> None:
        self._index.clear()
        self._turn_index.clear()
        self._scene_index.clear()
        self._faction_index.clear()
        self._data.clear()
        self._offsets.clear()
        self._tombstones.clear()
        self._corrupt_lines = 0

        if self._fh is None:
            return

        self._fh.seek(0)
        cursor = 0

        while True:
            line = self._fh.readline()
            if not line:
                break

            start = cursor
            cursor += len(line)
            stripped = line.strip()
            if not stripped:
                continue

            try:
                loaded = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._corrupt_lines += 1
                continue

            if not isinstance(loaded, dict):
                self._corrupt_lines += 1
                continue

            doc = self._decode_doc_for_runtime(loaded)
            key = self._extract_key(doc)
            if key is None:
                continue

            self._apply_doc(key, doc)
            self._offsets[key] = (start, cursor)

        self._next_id = self._compute_next_id()
        self._dirty = False

    def _compute_next_id(self) -> int:
        numeric_ids = [int(key) for key in self._data if key.isdigit()]
        return (max(numeric_ids) + 1) if numeric_ids else 1

    def _extract_key(self, doc: dict[str, Any]) -> str | None:
        key = doc.get("id")
        if key is None:
            key = doc.get("key")
        if key is None:
            return None
        return str(key)

    def _doc_terms(self, doc: dict[str, Any]) -> set[str]:
        terms: set[str] = set()

        for field in _INDEX_FIELDS:
            value = doc.get(field)
            if isinstance(value, str):
                terms.update(_TOKEN_PATTERN.findall(value.lower()))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str):
                        terms.update(_TOKEN_PATTERN.findall(item.lower()))

        return terms

    def _index_doc(self, key: str, doc: dict[str, Any]) -> None:
        for term in self._doc_terms(doc):
            _insert_sorted_unique(self._index[term], key)
        turn = _turn_sort_key(doc)
        _insert_sorted_unique(self._turn_index[turn], key)
        scene_id = _scene_id_key(doc)
        if scene_id:
            _insert_sorted_unique(self._scene_index[scene_id], key)
        faction_entity_id = _faction_entity_id_key(doc)
        if faction_entity_id:
            _insert_sorted_unique(self._faction_index[faction_entity_id], key)

    def _deindex_key(self, key: str, doc: dict[str, Any]) -> None:
        for term in self._doc_terms(doc):
            keys = self._index.get(term)
            if keys is None:
                continue
            _remove_sorted(keys, key)
        turn = _turn_sort_key(doc)
        turn_keys = self._turn_index.get(turn)
        if turn_keys is not None:
            _remove_sorted(turn_keys, key)
        scene_id = _scene_id_key(doc)
        if scene_id:
            scene_keys = self._scene_index.get(scene_id)
            if scene_keys is not None:
                _remove_sorted(scene_keys, key)
        faction_entity_id = _faction_entity_id_key(doc)
        if faction_entity_id:
            faction_keys = self._faction_index.get(faction_entity_id)
            if faction_keys is not None:
                _remove_sorted(faction_keys, key)

    def _is_tombstone(self, doc: dict[str, Any]) -> bool:
        return bool(doc.get("tombstone"))

    def _apply_doc(self, key: str, doc: dict[str, Any]) -> None:
        if key in self._data:
            self._deindex_key(key, self._data[key])

        if self._is_tombstone(doc):
            self._data[key] = doc
            self._tombstones.add(key)
            return

        self._data[key] = doc
        self._tombstones.discard(key)
        self._index_doc(key, doc)

    def _encode_doc_for_storage(self, doc: dict[str, Any]) -> dict[str, Any]:
        encoded = dict(doc)
        payload = encoded.get("payload")
        if payload is not None:
            try:
                payload_json = json.dumps(payload, ensure_ascii=False)
            except (TypeError, ValueError):
                payload_json = ""
            payload_bytes = payload_json.encode("utf-8")
            if len(payload_bytes) >= _COMPRESS_MIN_BYTES:
                compressed = zlib.compress(payload_bytes)
                encoded.pop("payload", None)
                encoded[_COMPRESSED_FIELD] = base64.b64encode(compressed).decode(
                    "ascii"
                )

        try:
            encoded_json = json.dumps(encoded, ensure_ascii=False)
        except (TypeError, ValueError):
            return dict(doc)

        encoded_bytes = encoded_json.encode("utf-8")
        if len(encoded_bytes) < _COMPRESS_MIN_BYTES:
            return encoded
        compressed_doc = zlib.compress(encoded_bytes)
        return {_DOC_COMPRESSED_FIELD: base64.b64encode(compressed_doc).decode("ascii")}

    def _decode_doc_for_runtime(self, doc: dict[str, Any]) -> dict[str, Any]:
        decoded = dict(doc)
        encoded_doc = decoded.get(_DOC_COMPRESSED_FIELD)
        if isinstance(encoded_doc, str):
            try:
                compressed_doc = base64.b64decode(encoded_doc)
                decoded_doc = zlib.decompress(compressed_doc).decode("utf-8")
                parsed_doc = json.loads(decoded_doc)
            except (ValueError, TypeError, zlib.error, json.JSONDecodeError):
                return decoded
            if not isinstance(parsed_doc, dict):
                return decoded
            decoded = dict(parsed_doc)

        encoded_payload = decoded.get(_COMPRESSED_FIELD)
        if not isinstance(encoded_payload, str):
            return decoded

        try:
            compressed = base64.b64decode(encoded_payload)
            payload_raw = zlib.decompress(compressed).decode("utf-8")
            payload = json.loads(payload_raw)
        except (ValueError, TypeError, zlib.error, json.JSONDecodeError):
            return decoded

        decoded.pop(_COMPRESSED_FIELD, None)
        decoded["payload"] = payload
        return decoded

    def append_only(self, doc: dict[str, Any]) -> str:
        """Append one document and update in-memory indexes.

        If ``id`` is absent, a numeric id is assigned.
        """
        return self.append_batch([doc])[0]

    def append_batch(self, docs: list[dict[str, Any]]) -> list[str]:
        """Append multiple docs with a single file write/flush cycle."""
        if not docs:
            return []

        runtime_docs: list[dict[str, Any]] = []
        encoded_lines: list[bytes] = []
        keys: list[str] = []
        for incoming in docs:
            runtime_doc = dict(incoming)
            if "id" not in runtime_doc:
                runtime_doc["id"] = str(self._next_id)
                self._next_id += 1
            key = str(runtime_doc["id"])
            storage_doc = self._encode_doc_for_storage(runtime_doc)
            encoded_lines.append(
                (json.dumps(storage_doc, ensure_ascii=False) + "\n").encode("utf-8")
            )
            runtime_docs.append(runtime_doc)
            keys.append(key)

        if self._fh is None:
            self._open_storage()
        assert self._fh is not None

        self._fh.seek(0, os.SEEK_END)
        cursor = self._fh.tell()
        for key, runtime_doc, encoded in zip(
            keys, runtime_docs, encoded_lines, strict=True
        ):
            start = cursor
            self._fh.write(encoded)
            cursor += len(encoded)
            self._apply_doc(key, runtime_doc)
            self._offsets[key] = (start, cursor)
        self._fh.flush()
        self._mmap_stale = True
        self._dirty = True
        return keys

    def delete(self, key: str, turn: int | None = None) -> bool:
        """Soft-delete document by appending a tombstone record."""
        key = str(key)
        if key not in self._data or key in self._tombstones:
            return False

        tombstone: dict[str, Any] = {
            "id": key,
            "tombstone": True,
        }
        if turn is not None:
            tombstone["turn"] = turn

        self.append_only(tombstone)
        return True

    def compact(self) -> int:
        """Rewrite storage with only live docs and rebuild mmap/index offsets.

        Returns count of persisted live docs.
        """
        live_docs = [
            doc
            for key, doc in self._data.items()
            if key not in self._tombstones and not self._is_tombstone(doc)
        ]

        tmp_path = f"{self.path}.compact.tmp"
        with open(tmp_path, "wb") as out:
            for doc in live_docs:
                storage_doc = self._encode_doc_for_storage(doc)
                line = json.dumps(storage_doc, ensure_ascii=False) + "\n"
                out.write(line.encode("utf-8"))

        self.close()
        os.replace(tmp_path, self.path)
        self._open_storage()
        self._rebuild_from_file()
        self._dirty = False
        return len(live_docs)

    def get(self, key: str) -> dict[str, Any] | None:
        """Fetch by key from in-memory map."""
        key = str(key)
        if key in self._tombstones:
            return None
        return self._data.get(key)

    def get_from_mmap(self, key: str) -> dict[str, Any] | None:
        """Fetch by key by reading the exact byte-range from mmap."""
        key = str(key)
        if key in self._tombstones:
            return None

        bounds = self._offsets.get(key)
        if bounds is None:
            return None

        start, end = bounds
        self._ensure_mmap_for_end(end)
        if self._mmap is None or end > self._mmap_size:
            return None

        raw = self._mmap[start:end].strip()
        if not raw:
            return None

        try:
            loaded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(loaded, dict):
            return None

        doc = self._decode_doc_for_runtime(loaded)
        if self._is_tombstone(doc):
            return None
        return doc

    def query(
        self,
        must: Iterable[str] | None = None,
        should: Iterable[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search docs using inverted index semantics.

        - ``must`` terms are AND-ed.
        - ``should`` terms are OR-ed and unioned with ``must`` results.
        - Empty query returns all docs sorted by ``turn`` descending.
        """
        must_terms = [term.lower() for term in (must or ()) if term.strip()]
        should_terms = [term.lower() for term in (should or ()) if term.strip()]

        result_set: set[str] | None = None

        for term in must_terms:
            term_keys = self._index.get(term)
            if not term_keys:
                return []
            if result_set is None:
                result_set = set(term_keys)
            else:
                result_set &= set(term_keys)

        if should_terms:
            should_set: set[str] = set()
            for term in should_terms:
                should_set |= set(self._index.get(term, []))
            if result_set is None:
                result_set = should_set
            else:
                result_set |= should_set

        if result_set is None:
            result_set = set(self._data.keys())

        docs = [
            self._data[key]
            for key in result_set
            if key in self._data and key not in self._tombstones
        ]
        docs.sort(key=lambda doc: (-_turn_sort_key(doc), str(doc.get("id", ""))))
        return docs[: max(0, limit)]

    def query_turn_range(
        self,
        turn_min: int,
        turn_max: int,
        scene_id: str | None = None,
        limit: int = 100,
        faction_entity_id: str | int | None = None,
    ) -> list[dict[str, Any]]:
        """Return docs in a turn range, optionally filtered by scene/faction."""
        if turn_min > turn_max:
            return []

        keys: set[str] = set()
        for turn in range(turn_min, turn_max + 1):
            keys.update(self._turn_index.get(turn, []))

        if scene_id is not None:
            scene_keys = set(self._scene_index.get(scene_id, []))
            keys &= scene_keys
        if faction_entity_id is not None:
            normalized_faction = str(faction_entity_id).strip()
            if normalized_faction:
                faction_keys = set(self._faction_index.get(normalized_faction, []))
                keys &= faction_keys

        docs = [
            self._data[key]
            for key in keys
            if key in self._data and key not in self._tombstones
        ]
        docs.sort(key=lambda doc: (_turn_sort_key(doc), str(doc.get("id", ""))))
        return docs[: max(0, limit)]

    def query_by_faction(
        self, faction_entity_id: str | int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return docs indexed under a faction id sorted by turn ascending."""
        normalized_faction = str(faction_entity_id).strip()
        if not normalized_faction:
            return []
        keys = set(self._faction_index.get(normalized_faction, []))
        docs = [
            self._data[key]
            for key in keys
            if key in self._data and key not in self._tombstones
        ]
        docs.sort(key=lambda doc: (_turn_sort_key(doc), str(doc.get("id", ""))))
        return docs[: max(0, limit)]

    def export_checkpoint(self) -> str:
        """Export full in-memory state as base64(zlib(json))."""
        if not self._dirty:
            return ""

        payload = {
            "docs": list(self._data.values()),
            "next_id": self._next_id,
        }
        packed = zlib.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return base64.b64encode(packed).decode("ascii")

    def import_checkpoint(self, b64_data: str) -> int:
        """Replace in-memory state from checkpoint payload.

        Returns number of loaded docs, or -1 on failure.
        """
        try:
            packed = base64.b64decode(b64_data)
            payload = json.loads(zlib.decompress(packed).decode("utf-8"))
            docs = payload["docs"]
            next_id = int(payload["next_id"])
        except (ValueError, TypeError, KeyError, zlib.error, json.JSONDecodeError):
            return -1

        self._index.clear()
        self._turn_index.clear()
        self._scene_index.clear()
        self._faction_index.clear()
        self._data.clear()
        self._offsets.clear()
        self._tombstones.clear()

        for doc in docs:
            if not isinstance(doc, dict):
                return -1
            key = self._extract_key(doc)
            if key is None:
                return -1
            self._apply_doc(key, doc)

        self._next_id = max(1, next_id)
        self.compact()
        return len(docs)

    def stats(self) -> dict[str, int]:
        """Return basic in-memory and storage metrics."""
        file_size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        live_docs = len(self._data) - len(self._tombstones)
        return {
            "doc_count": live_docs,
            "next_id": self._next_id,
            "file_size_bytes": file_size,
            "indexed_terms": len(self._index),
            "turn_buckets": len(self._turn_index),
            "scene_buckets": len(self._scene_index),
            "faction_buckets": len(self._faction_index),
            "corrupt_lines": self._corrupt_lines,
            "tombstones": len(self._tombstones),
        }

    def iter_docs(self, include_tombstones: bool = False) -> list[dict[str, Any]]:
        """Return stored docs from in-memory state."""
        docs: list[dict[str, Any]] = []
        for key, doc in self._data.items():
            if not include_tombstones and key in self._tombstones:
                continue
            docs.append(dict(doc))
        return docs


def _insert_sorted_unique(items: list[str], key: str) -> None:
    position = bisect_left(items, key)
    if position >= len(items) or items[position] != key:
        items.insert(position, key)


def _remove_sorted(items: list[str], key: str) -> None:
    position = bisect_left(items, key)
    if position < len(items) and items[position] == key:
        items.pop(position)


def _turn_sort_key(doc: dict[str, Any]) -> int:
    value = doc.get("turn", -1)
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _scene_id_key(doc: dict[str, Any]) -> str:
    scene_id = doc.get("scene_id")
    if isinstance(scene_id, str):
        return scene_id
    return ""


def _faction_entity_id_key(doc: dict[str, Any]) -> str:
    faction_entity_id = doc.get("faction_entity_id")
    if faction_entity_id is None:
        return ""
    normalized = str(faction_entity_id).strip()
    return normalized
