"""
Tool de búsqueda web, usando Tavily por debajo (tiene un plan gratis
bastante generoso y devuelve resultados ya "limpios", sin tener que
scrapear HTML a mano).
"""
import os
from tavily import TavilyClient

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


def web_search(query: str, max_results: int = 5) -> str:
    """
    Busca en internet y devuelve todo como un string plano, numerado,
    para que Claude lo pueda leer y citar la fuente que corresponda.
    """
    try:
        response = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",  # "advanced" tira mejores resultados pero
                                    # es más lento y consume más créditos
        )

        results = response.get("results", [])

        if not results:
            return "No se encontraron resultados para esta búsqueda."

        # Numero cada resultado como [Fuente N] para que después, en la
        # respuesta final, Claude pueda referenciar de dónde sacó cada dato
        formatted = []
        for i, r in enumerate(results, start=1):
            formatted.append(
                f"[Fuente {i}] {r['title']}\n"
                f"URL: {r['url']}\n"
                f"Resumen: {r['content']}\n"
            )

        return "\n".join(formatted)

    except Exception as e:
        # Timeout, key vencida, lo que sea: devolvemos el error como texto
        # para que el agente se entere y decida qué hacer (avisar al
        # usuario, probar de nuevo, etc) en vez de que el programa explote
        return f"Error al buscar en la web: {str(e)}"


WEB_SEARCH_TOOL_DEFINITION = {
    "name": "web_search",
    "description": (
        "Busca información actualizada en internet. Usar cuando la pregunta "
        "requiere datos recientes, actuales, o información que puede haber "
        "cambiado (precios, noticias, eventos, datos que cambian con el tiempo). "
        "No usar para preguntas de conocimiento general que no cambian."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "La consulta de búsqueda, en pocas palabras clave",
            },
            "max_results": {
                "type": "integer",
                "description": "Cantidad máxima de resultados a devolver (default 5)",
            },
        },
        "required": ["query"],
    },
}
