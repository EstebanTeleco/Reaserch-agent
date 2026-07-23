"""
Calculadora segura para que Claude no tenga que hacer cuentas "de memoria".

Ojo con esto: la forma fácil sería usar eval(expression) directo, pero eso
es abrir la puerta a que se ejecute cualquier cosa si algún input raro se
cuela ahí. Por eso parseamos la expresión con ast y solo evaluamos los
nodos que nosotros permitimos explícitamente.
"""
import ast
import operator

# Operadores permitidos. Si en algún momento hace falta soportar módulo (%)
# o algo más, se agrega acá.
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,  # el signo negativo, tipo -5
}


def _eval_node(node):
    """Baja recursivamente por el árbol de la expresión y va resolviendo."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador no permitido: {type(node.op)}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador no permitido: {type(node.op)}")
        return op(operand)
    else:
        # Cualquier otra cosa (llamadas a función, nombres de variable, etc)
        # la rechazamos. No queremos que esto termine siendo un intérprete
        # de Python completo.
        raise ValueError(f"Expresión no soportada: {type(node)}")


def calculator(expression: str) -> str:
    """
    Recibe algo como "500 * 1234.5" o "(10 + 5) / 3" y devuelve el resultado.
    Si la expresión es inválida devuelve un string de error en vez de tirar
    excepción, para que el agente pueda seguir el flujo sin romperse.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
        return f"Resultado: {result}"
    except Exception as e:
        return f"Error al calcular '{expression}': {str(e)}"


CALCULATOR_TOOL_DEFINITION = {
    "name": "calculator",
    "description": (
        "Evalúa expresiones matemáticas (suma, resta, multiplicación, división, "
        "potencias). Usar cuando la respuesta requiere hacer una cuenta precisa, "
        "en vez de calcularla mentalmente."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "La expresión matemática a evaluar, ej: '500 * 1234.5'",
            },
        },
        "required": ["expression"],
    },
}
