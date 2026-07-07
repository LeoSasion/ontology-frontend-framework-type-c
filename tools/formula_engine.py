from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable


class FormulaError(ValueError):
    pass


AGGREGATE_FUNCTIONS = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"}
ROW_FUNCTIONS = {"ABS", "ROUND", "COALESCE", "CONCAT", "IF", "SAFE_DIVIDE"}
VALID_FORMULA_FUNCTIONS = ROW_FUNCTIONS | AGGREGATE_FUNCTIONS
MAX_FORMULA_LENGTH = 4000
MAX_FORMULA_TOKENS = 800


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def numeric_sql(expression: str) -> str:
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({expression} AS TEXT)), ',', ''), '') AS REAL)"


def text_sql(expression: str) -> str:
    return f"COALESCE(CAST({expression} AS TEXT), '')"


def tokenize_formula(text: str) -> list[Token]:
    if len(text) > MAX_FORMULA_LENGTH:
        raise FormulaError(f"公式过长，请控制在 {MAX_FORMULA_LENGTH} 个字符以内")
    tokens: list[Token] = []

    def append_token(token: Token) -> None:
        tokens.append(token)
        if len(tokens) > MAX_FORMULA_TOKENS:
            raise FormulaError(f"公式过于复杂，请控制在 {MAX_FORMULA_TOKENS} 个 token 以内")

    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "()+-*/,":  # arithmetic, grouping, function separators
            append_token(Token(char, char))
            index += 1
            continue
        if char in "<>!=":
            next_two = text[index : index + 2]
            if next_two in {">=", "<=", "!=", "==", "<>"}:
                append_token(Token("op", "!=" if next_two == "<>" else "=" if next_two == "==" else next_two))
                index += 2
            elif char in "<>":
                append_token(Token("op", char))
                index += 1
            else:
                raise FormulaError(f"不支持的运算符：{char}")
            continue
        if char == "[":
            end = text.find("]", index + 1)
            if end < 0:
                raise FormulaError("字段引用缺少右括号 ]")
            field = text[index + 1 : end].strip()
            if not field:
                raise FormulaError("字段引用不能为空")
            append_token(Token("field", field))
            index = end + 1
            continue
        if char in {"'", '"'}:
            quote = char
            end = index + 1
            value = []
            while end < len(text):
                if text[end] == quote:
                    break
                value.append(text[end])
                end += 1
            if end >= len(text):
                raise FormulaError("字符串缺少结束引号")
            append_token(Token("string", "".join(value)))
            index = end + 1
            continue
        if char.isdigit() or char == ".":
            end = index + 1
            while end < len(text) and (text[end].isdigit() or text[end] == "."):
                end += 1
            value = text[index:end]
            if value.count(".") > 1 or value == ".":
                raise FormulaError(f"数字格式错误：{value}")
            append_token(Token("number", value))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            append_token(Token("identifier", text[index:end].upper()))
            index = end
            continue
        raise FormulaError(f"不支持的字符：{char}")
    append_token(Token("eof", ""))
    return tokens


class FormulaParser:
    def __init__(self, text: str):
        self.tokens = tokenize_formula(text)
        self.index = 0

    def current(self) -> Token:
        return self.tokens[self.index]

    def consume(self) -> Token:
        token = self.current()
        self.index += 1
        return token

    def match(self, value: str) -> bool:
        if self.current().value == value or self.current().kind == value:
            self.consume()
            return True
        return False

    def expect(self, value: str) -> None:
        if not self.match(value):
            raise FormulaError(f"公式语法错误，期望 {value}，实际 {self.current().value or self.current().kind}")

    def parse(self) -> dict[str, Any]:
        ast = self.parse_comparison()
        if self.current().kind != "eof":
            raise FormulaError(f"公式末尾存在无法解析的内容：{self.current().value}")
        return ast

    def parse_comparison(self) -> dict[str, Any]:
        node = self.parse_term()
        while self.current().kind == "op":
            op = self.consume().value
            right = self.parse_term()
            node = {"type": "binary", "op": op, "left": node, "right": right}
        return node

    def parse_term(self) -> dict[str, Any]:
        node = self.parse_factor()
        while self.current().value in {"+", "-"}:
            op = self.consume().value
            right = self.parse_factor()
            node = {"type": "binary", "op": op, "left": node, "right": right}
        return node

    def parse_factor(self) -> dict[str, Any]:
        node = self.parse_unary()
        while self.current().value in {"*", "/"}:
            op = self.consume().value
            right = self.parse_unary()
            node = {"type": "binary", "op": op, "left": node, "right": right}
        return node

    def parse_unary(self) -> dict[str, Any]:
        if self.match("-"):
            return {"type": "unary", "value": self.parse_primary()}
        return self.parse_primary()

    def parse_primary(self) -> dict[str, Any]:
        token = self.current()
        if token.kind in {"number", "string", "field"}:
            self.consume()
            return {"type": token.kind, "value" if token.kind != "field" else "name": token.value}
        if token.kind == "identifier":
            name = self.consume().value
            self.expect("(")
            args: list[dict[str, Any]] = []
            if self.current().value != ")":
                while True:
                    args.append(self.parse_comparison())
                    if not self.match(","):
                        break
            self.expect(")")
            return {"type": "call", "name": name, "args": args}
        if self.match("("):
            node = self.parse_comparison()
            self.expect(")")
            return node
        raise FormulaError(f"无法解析公式片段：{token.value or token.kind}")


def parse_formula(text: str) -> dict[str, Any]:
    if not text.strip():
        raise FormulaError("公式不能为空")
    return FormulaParser(text).parse()


def walk_ast(node: dict[str, Any]):
    yield node
    for key in ("left", "right", "value"):
        child = node.get(key)
        if isinstance(child, dict):
            yield from walk_ast(child)
    for child in node.get("args", []) if isinstance(node.get("args"), list) else []:
        if isinstance(child, dict):
            yield from walk_ast(child)


def ast_dependencies(ast: dict[str, Any]) -> list[str]:
    return sorted({str(node.get("name")) for node in walk_ast(ast) if node.get("type") == "field"})


def ast_has_function(ast: dict[str, Any], functions: set[str]) -> bool:
    return any(str(node.get("name", "")).upper() in functions for node in walk_ast(ast) if node.get("type") == "call")


def validate_formula_fields(ast: dict[str, Any], available_fields: set[str]) -> None:
    missing = [field for field in ast_dependencies(ast) if field not in available_fields]
    if missing:
        raise FormulaError(f"字段不存在：{', '.join(missing)}")


def validate_formula_functions(ast: dict[str, Any], mode: str) -> None:
    allowed = ROW_FUNCTIONS | (AGGREGATE_FUNCTIONS if mode == "aggregate" else set())
    for node in walk_ast(ast):
        if node.get("type") != "call":
            continue
        name = str(node.get("name", "")).upper()
        if name not in allowed:
            raise FormulaError(f"不支持的函数：{name}")
        if mode == "row" and name in AGGREGATE_FUNCTIONS:
            raise FormulaError(f"行级字段不能使用聚合函数：{name}")


def parse_and_validate_formula(text: str, *, mode: str, available_fields: set[str]) -> dict[str, Any]:
    if mode not in {"row", "aggregate"}:
        raise FormulaError("公式模式只支持 row 或 aggregate")
    ast = parse_formula(text)
    validate_formula_functions(ast, mode)
    if mode == "aggregate" and not ast_has_function(ast, AGGREGATE_FUNCTIONS):
        raise FormulaError("聚合指标公式至少需要包含 SUM、AVG、COUNT 等聚合函数")
    validate_formula_fields(ast, available_fields)
    return ast


def _require_arg_count(name: str, args: list[str], expected: int) -> None:
    if len(args) != expected:
        raise FormulaError(f"{name} 需要 {expected} 个参数")


FieldResolver = Callable[[str], str]


def ast_to_sql(ast: dict[str, Any], *, mode: str, resolve_field: FieldResolver) -> str:
    validate_formula_functions(ast, mode)

    def compile_node(node: dict[str, Any]) -> str:
        node_type = node.get("type")
        if node_type == "number":
            return str(node.get("value") or "0")
        if node_type == "string":
            return sql_string(str(node.get("value") or ""))
        if node_type == "field":
            return resolve_field(str(node.get("name") or ""))
        if node_type == "unary":
            return f"(-{numeric_sql(compile_node(node['value']))})"
        if node_type == "binary":
            op = str(node.get("op") or "")
            left = compile_node(node["left"])
            right = compile_node(node["right"])
            if op in {"+", "-", "*"}:
                return f"({numeric_sql(left)} {op} {numeric_sql(right)})"
            if op == "/":
                return f"(CASE WHEN {numeric_sql(right)} = 0 THEN NULL ELSE {numeric_sql(left)} / {numeric_sql(right)} END)"
            if op in {"=", "!="}:
                return f"({left} {'<>' if op == '!=' else '='} {right})"
            if op in {">", ">=", "<", "<="}:
                return f"({numeric_sql(left)} {op} {numeric_sql(right)})"
            raise FormulaError(f"不支持的运算符：{op}")
        if node_type == "call":
            name = str(node.get("name") or "").upper()
            args = [compile_node(arg) for arg in node.get("args", [])]
            if name == "IF":
                _require_arg_count(name, args, 3)
                return f"(CASE WHEN {args[0]} THEN {args[1]} ELSE {args[2]} END)"
            if name == "ABS":
                _require_arg_count(name, args, 1)
                return f"ABS({numeric_sql(args[0])})"
            if name == "ROUND":
                if len(args) not in {1, 2}:
                    raise FormulaError("ROUND 需要 1 或 2 个参数")
                digits = args[1] if len(args) == 2 else "0"
                return f"ROUND({numeric_sql(args[0])}, CAST({digits} AS INTEGER))"
            if name == "COALESCE":
                if not args:
                    raise FormulaError("COALESCE 至少需要 1 个参数")
                return f"COALESCE({', '.join(args)})"
            if name == "CONCAT":
                if not args:
                    raise FormulaError("CONCAT 至少需要 1 个参数")
                return "(" + " || ".join(text_sql(arg) for arg in args) + ")"
            if name == "SAFE_DIVIDE":
                _require_arg_count(name, args, 2)
                denominator = numeric_sql(args[1])
                return f"(CASE WHEN {denominator} IS NULL OR {denominator} = 0 THEN NULL ELSE {numeric_sql(args[0])} / {denominator} END)"
            if name in AGGREGATE_FUNCTIONS:
                if mode != "aggregate":
                    raise FormulaError(f"行级字段不能使用聚合函数：{name}")
                if name == "COUNT":
                    if not args:
                        return "COUNT(*)"
                    _require_arg_count(name, args, 1)
                    return f"COUNT({args[0]})"
                _require_arg_count(name, args, 1)
                if name == "COUNT_DISTINCT":
                    return f"COUNT(DISTINCT {args[0]})"
                return f"{name}({numeric_sql(args[0])})"
        raise FormulaError("公式节点格式错误")

    return compile_node(ast)


def dump_ast(ast: dict[str, Any]) -> str:
    return json.dumps(ast, ensure_ascii=False, separators=(",", ":"))


def load_ast(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError as error:
        raise FormulaError("公式 AST 格式错误") from error
    if not isinstance(parsed, dict):
        raise FormulaError("公式 AST 格式错误")
    return parsed


def formula_preview_text(text: str, max_length: int = 120) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())[:max_length]
