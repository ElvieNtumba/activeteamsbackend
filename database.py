import os
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Iterator
from dotenv import load_dotenv
from supabase_helpers.supabase_client import supabase

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")


class ObjectId(str):
    def __new__(cls, value: Optional[Any] = None):
        if value is None:
            value = str(uuid.uuid4())
        return str.__new__(cls, str(value))

    @staticmethod
    def is_valid(value: Any) -> bool:
        if value is None:
            return False
        try:
            return bool(str(value))
        except Exception:
            return False


def _normalize_id_fields(document: Any) -> Any:
    if isinstance(document, dict):
        if "_id" in document and "id" not in document:
            document["id"] = str(document["_id"])
        if "id" in document and "_id" not in document:
            document["_id"] = ObjectId(document["id"])
        for key, value in list(document.items()):
            document[key] = _normalize_id_fields(value)
    elif isinstance(document, list):
        return [_normalize_id_fields(item) for item in document]
    return document


def _get_field_value(document: Dict[str, Any], field: str) -> Any:
    if field.startswith("$"):
        field = field[1:]
    parts = field.split(".")
    value = document
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _make_hashable(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((k, _make_hashable(v)) for k, v in sorted(value.items()))
    if isinstance(value, list):
        return tuple(_make_hashable(v) for v in value)
    return value


def _evaluate_expression(expr: Any, document: Dict[str, Any]) -> Any:
    if isinstance(expr, dict):
        if "$eq" in expr:
            left = _evaluate_expression(expr["$eq"][0], document)
            right = _evaluate_expression(expr["$eq"][1], document)
            return left == right
        if "$ne" in expr:
            left = _evaluate_expression(expr["$ne"][0], document)
            right = _evaluate_expression(expr["$ne"][1], document)
            return left != right
        if "$and" in expr:
            return all(_evaluate_expression(item, document) for item in expr["$and"])
        if "$or" in expr:
            return any(_evaluate_expression(item, document) for item in expr["$or"])
        if "$not" in expr:
            return not _evaluate_expression(expr["$not"], document)
        if "$gt" in expr:
            return _evaluate_expression(expr["$gt"][0], document) > _evaluate_expression(expr["$gt"][1], document)
        if "$gte" in expr:
            return _evaluate_expression(expr["$gte"][0], document) >= _evaluate_expression(expr["$gte"][1], document)
        if "$lt" in expr:
            return _evaluate_expression(expr["$lt"][0], document) < _evaluate_expression(expr["$lt"][1], document)
        if "$lte" in expr:
            return _evaluate_expression(expr["$lte"][0], document) <= _evaluate_expression(expr["$lte"][1], document)
        if "$concat" in expr:
            parts = [_evaluate_expression(item, document) for item in expr["$concat"]]
            return "".join(str(part or "") for part in parts)
        if "$regexMatch" in expr:
            params = expr["$regexMatch"]
            text = str(_evaluate_expression(params.get("input"), document) or "")
            pattern = params.get("regex", "")
            flags = 0
            if params.get("options", "").lower().find("i") >= 0:
                flags = re.IGNORECASE
            return re.search(pattern, text, flags) is not None
        if "$cond" in expr:
            condition = _evaluate_expression(expr["$cond"][0], document)
            return _evaluate_expression(expr["$cond"][1], document) if condition else _evaluate_expression(expr["$cond"][2], document)
        if "$sum" in expr:
            value = expr["$sum"]
            if isinstance(value, list):
                return sum(float(_evaluate_expression(item, document) or 0) for item in value)
            return float(_evaluate_expression(value, document) or 0)
        if "$ifNull" in expr:
            value = _evaluate_expression(expr["$ifNull"][0], document)
            return value if value is not None else _evaluate_expression(expr["$ifNull"][1], document)
        if "$toString" in expr:
            return str(_evaluate_expression(expr["$toString"], document) or "")
        if len(expr) == 1:
            operator, value = next(iter(expr.items()))
            if isinstance(value, str) and value.startswith("$"):
                return _get_field_value(document, value)
            return _evaluate_expression(value, document)
    if isinstance(expr, list):
        return [_evaluate_expression(item, document) for item in expr]
    if isinstance(expr, str) and expr.startswith("$"):
        return _get_field_value(document, expr)
    return expr


def _matches_query(document: Dict[str, Any], query: Any) -> bool:
    if not query:
        return True
    if isinstance(query, dict):
        for key, value in query.items():
            if key == "$or":
                return any(_matches_query(document, cond) for cond in value)
            if key == "$and":
                return all(_matches_query(document, cond) for cond in value)
            if key == "$expr":
                return bool(_evaluate_expression(value, document))
            doc_value = _get_field_value(document, key)
            if isinstance(value, dict):
                if "$eq" in value:
                    if doc_value != _evaluate_expression(value["$eq"], document):
                        return False
                elif "$ne" in value:
                    if doc_value == _evaluate_expression(value["$ne"], document):
                        return False
                elif "$in" in value:
                    if doc_value not in value["$in"]:
                        return False
                elif "$nin" in value:
                    if doc_value in value["$nin"]:
                        return False
                elif "$exists" in value:
                    exists = doc_value is not None
                    if bool(value["$exists"]) != exists:
                        return False
                elif "$regex" in value:
                    flags = re.IGNORECASE if value.get("$options", "").lower().find("i") >= 0 else 0
                    pattern = value["$regex"]
                    if doc_value is None or not re.search(pattern, str(doc_value), flags):
                        return False
                else:
                    if not _matches_query(doc_value if isinstance(doc_value, dict) else {key: doc_value}, value):
                        return False
            else:
                if doc_value != value:
                    return False
        return True
    return False


def _apply_projection(document: Dict[str, Any], projection: Any) -> Dict[str, Any]:
    if projection is None:
        return document
    projected = {}
    if isinstance(projection, dict):
        includes = {k for k, v in projection.items() if v}
        excludes = {k for k, v in projection.items() if not v}
        if includes:
            for key in includes:
                if key == "_id" and "id" in document:
                    projected["_id"] = document["_id"]
                elif key in document:
                    projected[key] = document[key]
            return projected
        projected = dict(document)
        for key in excludes:
            projected.pop(key, None)
        return projected
    return document


def _apply_sort(rows: List[Dict[str, Any]], sort_spec: Any) -> List[Dict[str, Any]]:
    if not sort_spec:
        return rows
    if isinstance(sort_spec, dict):
        for field, direction in reversed(list(sort_spec.items())):
            rows = sorted(rows, key=lambda item: _get_field_value(item, field) or "", reverse=direction < 0)
        return rows
    if isinstance(sort_spec, list):
        for field, direction in reversed(sort_spec):
            rows = sorted(rows, key=lambda item: _get_field_value(item, field) or "", reverse=direction < 0)
    return rows


class SupabaseResult:
    def __init__(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        error: Optional[Any] = None,
        count: Optional[int] = None,
        inserted_id: Optional[str] = None,
        matched_count: int = 0,
        modified_count: int = 0,
        deleted_count: int = 0,
    ):
        self.data = data or []
        self.error = error
        self.count = count
        self.inserted_id = inserted_id
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.deleted_count = deleted_count


class SupabaseCursor:
    def __init__(
        self,
        collection: "SupabaseCollection",
        query: Optional[Dict[str, Any]] = None,
        projection: Any = None,
        skip: int = 0,
        limit: Optional[int] = None,
        sort: Any = None,
        pipeline: Optional[List[Dict[str, Any]]] = None,
    ):
        self.collection = collection
        self.query = query or {}
        self.projection = projection
        self.skip = skip
        self.limit = limit
        self.sort = sort
        self.pipeline = pipeline
        self._rows: Optional[List[Dict[str, Any]]] = None
        self._iterator: Optional[Iterator] = None

    def skip(self, amount: int):
        self.skip = amount
        return self

    def limit(self, amount: int):
        self.limit = amount
        return self

    def sort(self, sort_spec: Any):
        self.sort = sort_spec
        return self

    async def _load(self) -> List[Dict[str, Any]]:
        if self._rows is None:
            if self.pipeline is not None:
                self._rows = await self.collection._aggregate_pipeline(self.pipeline, self.projection)
            else:
                self._rows = await self.collection._fetch_rows(self.query, self.projection)
            if self.sort:
                self._rows = _apply_sort(self._rows, self.sort)
            if self.skip:
                self._rows = self._rows[self.skip:]
            if self.limit is not None:
                self._rows = self._rows[: self.limit]
        return self._rows

    def __aiter__(self):
        self._iterator = None
        return self

    async def __anext__(self):
        if self._iterator is None:
            rows = await self._load()
            self._iterator = iter(rows)
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = await self._load()
        return rows if length is None else rows[:length]


class SupabaseCollection:
    def __init__(self, name: str, db: "SupabaseDB"):
        self.name = name
        self.db = db
        self.client = db.client

    def _table(self):
        return self.client.table(self.name)

    def _normalize_query(self, query: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if query is None:
            return None
        if isinstance(query, dict):
            normalized = {}
            for key, value in query.items():
                if key.startswith("$"):
                    normalized[key] = value
                    continue
                normalized_field = "id" if key == "_id" else key
                normalized[normalized_field] = value
            return normalized
        return query

    async def insert_one(self, document: Dict[str, Any]) -> SupabaseResult:
        document = dict(document)
        if "_id" in document and document["_id"] is not None:
            document["id"] = str(document["_id"])
        if "id" not in document or not document["id"]:
            document["id"] = str(ObjectId())
        document.pop("_id", None)
        result = self._table().insert(document).execute()
        if getattr(result, "error", None):
            raise Exception(result.error)
        records = result.data if result.data else []
        if records:
            record = records[0] if isinstance(records, list) else records
            _normalize_id_fields(record)
            inserted_id = record.get("id")
        else:
            inserted_id = document["id"]
        return SupabaseResult(data=[record] if records else [document], inserted_id=inserted_id)

    def find(self, query: Optional[Dict[str, Any]] = None, projection: Any = None) -> SupabaseCursor:
        return SupabaseCursor(self, query=self._normalize_query(query), projection=projection)

    async def find_one(self, query: Optional[Dict[str, Any]] = None, projection: Any = None) -> Optional[Dict[str, Any]]:
        cursor = self.find(query, projection).limit(1)
        rows = await cursor.to_list(length=1)
        return rows[0] if rows else None

    async def count_documents(self, query: Optional[Dict[str, Any]] = None) -> int:
        if self._is_simple_query(query):
            select_clause = "*"  # Use "*" instead of "id" to avoid schema-specific issues
            query_args = self._normalize_query(query)
            qb = self._table().select(select_clause, count="exact")
            qb = self._apply_query_filters(qb, query_args)
            result = qb.execute()
            if getattr(result, "error", None):
                raise Exception(result.error)
            return result.count if getattr(result, "count", None) is not None else len(result.data or [])
        rows = await self.find(query).to_list(None)
        return len(rows)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> SupabaseResult:
        rows = await self.find(query).to_list(1)
        if not rows:
            return SupabaseResult(matched_count=0, modified_count=0)
        return await self._apply_update(rows[0], update)

    async def update_many(self, query: Dict[str, Any], update: Dict[str, Any]) -> SupabaseResult:
        rows = await self.find(query).to_list(None)
        if not rows:
            return SupabaseResult(matched_count=0, modified_count=0)
        modified = 0
        for row in rows:
            result = await self._apply_update(row, update)
            if result.modified_count:
                modified += 1
        return SupabaseResult(matched_count=len(rows), modified_count=modified)

    async def delete_one(self, query: Dict[str, Any]) -> SupabaseResult:
        rows = await self.find(query).to_list(1)
        if not rows:
            return SupabaseResult(deleted_count=0)
        row = rows[0]
        result = self._table().delete().eq("id", row["id"]).execute()
        deleted_count = 0 if getattr(result, "error", None) else 1
        return SupabaseResult(deleted_count=deleted_count)

    async def delete_many(self, query: Dict[str, Any]) -> SupabaseResult:
        rows = await self.find(query).to_list(None)
        deleted = 0
        for row in rows:
            result = self._table().delete().eq("id", row["id"]).execute()
            if not getattr(result, "error", None):
                deleted += 1
        return SupabaseResult(deleted_count=deleted)

    async def create_index(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def aggregate(self, pipeline: List[Dict[str, Any]]) -> SupabaseCursor:
        return SupabaseCursor(self, pipeline=pipeline)

    def _is_simple_query(self, query: Optional[Dict[str, Any]]) -> bool:
        if not query:
            return True
        if not isinstance(query, dict):
            return False
        for key, value in query.items():
            if key in {"$or", "$and", "$expr"}:
                return False
            if isinstance(value, dict):
                for op in value.keys():
                    if op not in {"$ne", "$in", "$nin", "$exists", "$gt", "$gte", "$lt", "$lte"}:
                        return False
            if isinstance(value, list):
                return False
        return True

    def _apply_query_filters(self, qb: Any, query: Optional[Dict[str, Any]]) -> Any:
        if not query:
            return qb
        for key, value in query.items():
            if key in {"$or", "$and", "$expr"}:
                continue
            field = "id" if key == "_id" else key
            field = self._escape_field_name(field) if any(c in field for c in "@.-") else field
            if isinstance(value, dict):
                if "$ne" in value:
                    qb = qb.neq(field, value["$ne"])
                elif "$in" in value:
                    qb = qb.in_(field, [str(v) for v in value["$in"]])
                elif "$nin" in value:
                    qb = qb.not_in(field, [str(v) for v in value["$nin"]])
                elif "$gt" in value:
                    qb = qb.gt(field, value["$gt"])
                elif "$gte" in value:
                    qb = qb.gte(field, value["$gte"])
                elif "$lt" in value:
                    qb = qb.lt(field, value["$lt"])
                elif "$lte" in value:
                    qb = qb.lte(field, value["$lte"])
                elif "$exists" in value:
                    pass
                else:
                    qb = qb.eq(field, value)
            else:
                qb = qb.eq(field, value)
        return qb

    async def _fetch_rows(self, query: Optional[Dict[str, Any]], projection: Any) -> List[Dict[str, Any]]:
        select_clause = self._projection_to_select(projection)
        qb = self._table().select(select_clause)
        if self._is_simple_query(query):
            qb = self._apply_query_filters(qb, query)
        result = qb.execute()
        if getattr(result, "error", None):
            raise Exception(result.error)
        rows = result.data or []
        rows = [_normalize_id_fields(dict(row)) for row in rows]
        if projection is not None:
            rows = [_apply_projection(row, projection) for row in rows]
        if query and not self._is_simple_query(query):
            rows = [row for row in rows if _matches_query(row, query)]
        return rows

    def _escape_field_name(self, field: str) -> str:
        """Escape field names for Supabase REST API - quote if contains special chars."""
        if any(c in field for c in "@.-"):
            return f'"{field}"'
        return field

    def _projection_to_select(self, projection: Any) -> str:
        if projection is None:
            return "*"
        if isinstance(projection, dict):
            includes = []
            for key, value in projection.items():
                if value:
                    field = "id" if key == "_id" else key
                    includes.append(self._escape_field_name(field))
            if includes:
                return ",".join(includes)
            return "*"
        if isinstance(projection, list):
            return ",".join(self._escape_field_name(f) for f in projection)
        return str(projection)

    def _apply_update(self, row: Dict[str, Any], update: Dict[str, Any]) -> SupabaseResult:
        updated = dict(row)
        if "$set" in update:
            updated.update(update["$set"])
        if "$unset" in update:
            for key in update["$unset"]:
                updated.pop(key, None)
        if "$inc" in update:
            for key, amount in update["$inc"].items():
                updated[key] = (updated.get(key, 0) or 0) + amount
        if "$push" in update:
            for key, value in update["$push"].items():
                target = updated.get(key, [])
                if not isinstance(target, list):
                    target = [target] if target is not None else []
                if isinstance(value, dict) and "$each" in value:
                    target.extend(value["$each"])
                else:
                    target.append(value)
                updated[key] = target
        if "$pull" in update:
            for key, value in update["$pull"].items():
                target = updated.get(key, [])
                if isinstance(target, list):
                    if isinstance(value, dict):
                        updated[key] = [item for item in target if not _matches_query(item, value)]
                    else:
                        updated[key] = [item for item in target if item != value]
        updated.pop("_id", None)
        result = self._table().update(updated).eq("id", row["id"]).execute()
        if getattr(result, "error", None):
            raise Exception(result.error)
        return SupabaseResult(matched_count=1, modified_count=1)

    async def _aggregate_pipeline(self, pipeline: List[Dict[str, Any]], projection: Any) -> List[Dict[str, Any]]:
        rows = await self._fetch_rows(None, None)
        for stage in pipeline:
            if "$match" in stage:
                rows = [row for row in rows if _matches_query(row, stage["$match"])]
            elif "$project" in stage:
                rows = [self._apply_projection_stage(row, stage["$project"]) for row in rows]
            elif "$sort" in stage:
                rows = _apply_sort(rows, stage["$sort"])
            elif "$limit" in stage:
                rows = rows[: stage["$limit"]]
            elif "$group" in stage:
                rows = self._apply_group(rows, stage["$group"])
            elif "$replaceRoot" in stage:
                root_expr = stage["$replaceRoot"]["newRoot"]
                rows = [_evaluate_expression(root_expr, row) if isinstance(root_expr, dict) else row.get(root_expr[1:], row) for row in rows]
            elif "$unwind" in stage:
                field_path = stage["$unwind"]
                rows = self._apply_unwind(rows, field_path)
            elif "$lookup" in stage:
                rows = await self._apply_lookup(rows, stage["$lookup"])
            elif "$addFields" in stage:
                rows = [self._apply_add_fields(row, stage["$addFields"]) for row in rows]
            else:
                raise NotImplementedError(f"Unsupported aggregation stage: {stage}")
        if projection is not None:
            rows = [_apply_projection(row, projection) for row in rows]
        return rows

    def _apply_projection_stage(self, row: Dict[str, Any], projection: Dict[str, Any]) -> Dict[str, Any]:
        projected = {}
        for key, spec in projection.items():
            if isinstance(spec, dict):
                projected[key] = _evaluate_expression(spec, row)
            elif spec:
                projected[key] = row.get(key)
        return projected

    def _apply_group(self, rows: List[Dict[str, Any]], group_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        group_id_spec = group_spec.get("_id")
        groups: Dict[Any, Dict[str, Any]] = {}
        store: Dict[Any, Dict[str, Any]] = {}
        for row in rows:
            group_key = _make_hashable(_evaluate_expression(group_id_spec, row) if group_id_spec is not None else None)
            if group_key not in groups:
                groups[group_key] = {
                    "_id": _evaluate_expression(group_id_spec, row) if group_id_spec is not None else None,
                    "docs": [],
                }
            groups[group_key]["docs"].append(row)
        results: List[Dict[str, Any]] = []
        for group_key, group_data in groups.items():
            docs = group_data["docs"]
            result = {"_id": group_data["_id"]}
            for key, expr in group_spec.items():
                if key == "_id":
                    continue
                if isinstance(expr, dict) and "$sum" in expr:
                    result[key] = int(_evaluate_expression(expr, docs[0]) if isinstance(expr["$sum"], dict) else len(docs) if expr["$sum"] == 1 else _evaluate_expression(expr["$sum"], docs[0]))
                elif isinstance(expr, dict) and "$first" in expr:
                    value = expr["$first"]
                    if value == "$$ROOT":
                        result[key] = docs[0]
                    else:
                        result[key] = _evaluate_expression(value, docs[0])
                else:
                    result[key] = _evaluate_expression(expr, docs[0])
            results.append(result)
        return results

    def _apply_unwind(self, rows: List[Dict[str, Any]], field_path: str) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for row in rows:
            field_value = _get_field_value(row, field_path if not field_path.startswith("$") else field_path[1:])
            if isinstance(field_value, list):
                for item in field_value:
                    new_row = dict(row)
                    parts = field_path[1:].split(".") if field_path.startswith("$") else field_path.split(".")
                    target = new_row
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = item
                    output.append(new_row)
            else:
                output.append(row)
        return output

    async def _apply_lookup(self, rows: List[Dict[str, Any]], lookup_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        foreign_collection = self.db[lookup_spec["from"]]
        local_field = lookup_spec["localField"].lstrip("$")
        foreign_field = lookup_spec["foreignField"].lstrip("$")
        as_field = lookup_spec["as"]
        output: List[Dict[str, Any]] = []
        for row in rows:
            local_value = _get_field_value(row, local_field)
            query = {foreign_field: local_value} if local_value is not None else {"$expr": {"$eq": ["$", None]}}
            matched = await foreign_collection.find(query).to_list(None)
            output_row = dict(row)
            output_row[as_field] = matched
            output.append(output_row)
        return output

    def _apply_add_fields(self, row: Dict[str, Any], fields: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(row)
        for key, expr in fields.items():
            updated[key] = _evaluate_expression(expr, updated)
        return updated


class SupabaseDB:
    def __init__(self, client: Any):
        self.client = client

    def __getitem__(self, name: str) -> SupabaseCollection:
        return SupabaseCollection(name, self)


db = SupabaseDB(supabase)
events_collection = db["Events"]
people_collection = db["People"]
tasks_collection = db["Tasks"]
users_collection = db["Users"]
tasktypes_collection = db["TaskTypes"]
org_config_collection = db["OrgConfig"]
consolidations_collection = db["Consolidations"]
organizations_collection = db["Organizations"]
