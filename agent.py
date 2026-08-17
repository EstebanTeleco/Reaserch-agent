"""
Loop principal del agente.

La idea es simple (ReAct, básicamente): le paso la pregunta a Gemini junto
con las tools que tiene disponibles, y dejo que él decida qué hacer. Si
contesta texto, listo, esa es la respuesta. Si pide usar una tool, la corro
yo acá en Python normal y le devuelvo el resultado. Y así hasta que llegue
a algo definitivo o se acabe el margen de iteraciones.

No usé ningún framework (LangChain, etc) a propósito, para entender bien
qué pasa "por debajo" cuando un agente usa tools.

Nota: pasado de Claude a Gemini 2.5 Flash porque tiene capa gratuita en
la Gemini API (https://ai.google.dev/pricing) - alcanza de sobra para
correr este agente sin gastar un peso. La lógica del loop es la misma,
lo único que cambia es la forma de llamar a la API y de leer la
respuesta (Gemini devuelve "function_call" parts en vez de bloques
"tool_use").
"""
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

from tools.web_search import web_search, WEB_SEARCH_TOOL_DEFINITION
from tools.calculator import calculator, CALCULATOR_TOOL_DEFINITION

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODEL_NAME = "gemini-2.5-flash"

# Estas son las tools que Gemini "ve" y puede pedir usar. Gemini las quiere
# envueltas en un types.Tool con una lista de function_declarations.
TOOLS = [
    types.Tool(
        function_declarations=[
            WEB_SEARCH_TOOL_DEFINITION,
            CALCULATOR_TOOL_DEFINITION,
        ]
    )
]

# Y acá el mapeo nombre -> función real. Cuando Gemini devuelve un
# function_call con name="web_search", busco en este dict y ejecuto.
TOOL_FUNCTIONS = {
    "web_search": web_search,
    "calculator": calculator,
}

SYSTEM_PROMPT = """Sos un asistente de investigación. Tu trabajo es responder \
preguntas del usuario de la forma más precisa posible.

Reglas importantes:
- Si necesitás información actual o que no sabés con certeza, usá la tool \
web_search en vez de inventar una respuesta.
- Si necesitás hacer una cuenta matemática, usá la tool calculator en vez \
de calcularla vos mismo (para evitar errores).
- Cuando uses información de una búsqueda, citá la fuente (el número de \
fuente o la URL) en tu respuesta final.
- Si después de buscar no encontrás información suficiente, decilo \
claramente en vez de inventar datos.
- Sé conciso y directo en tus respuestas finales.
"""

# Con 6 alcanza para la mayoría de los casos que probé. Si en algún momento
# el agente necesita más pasos capaz vale la pena revisar el prompt en vez
# de subir este número a lo loco.
MAX_ITERATIONS = 6


def run_agent(user_question: str, verbose: bool = True) -> str:
    """
    Corre el loop del agente hasta obtener una respuesta final.

    verbose=True imprime cada paso (pensamiento, tool usada, resultado),
    lo cual sirve para debuggear o para mostrar el proceso en una demo.
    """
    # En Gemini el historial se arma con types.Content, cada uno con un
    # "role" (user/model) y una lista de "parts". Arranca con la pregunta.
    contents = [
        types.Content(role="user", parts=[types.Part(text=user_question)])
    ]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
    )

    for iteration in range(MAX_ITERATIONS):
        if verbose:
            print(f"\n--- Iteración {iteration + 1} ---")

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        model_content = candidate.content

        # Guardo la respuesta en el historial. Esto es importante: si no
        # la guardo acá, Gemini "pierde la memoria" de lo que ya pensó/pidió
        # en la próxima vuelta del loop.
        contents.append(model_content)

        function_calls = [
            part.function_call
            for part in model_content.parts
            if part.function_call is not None
        ]

        # Si no pidió tool, ya tenemos la respuesta final
        if not function_calls:
            final_text = "".join(
                part.text for part in model_content.parts if part.text
            )
            if verbose:
                print(f"\nrespuesta final:\n{final_text}")
            return final_text

        # Si llegamos acá, pidió al menos una tool. A veces vienen varias
        # en el mismo mensaje, así que recorro todas las que haya.
        response_parts = []

        for part in model_content.parts:
            if part.text and verbose:
                print(f"pensando: {part.text}")

            if part.function_call is not None:
                tool_name = part.function_call.name
                tool_input = dict(part.function_call.args or {})

                if verbose:
                    print(f"tool: {tool_name}({tool_input})")

                function_to_call = TOOL_FUNCTIONS.get(tool_name)
                if function_to_call is None:
                    # No debería pasar nunca (Gemini solo puede pedir tools
                    # que le mostramos en TOOLS) pero mejor cubrirlo
                    result = f"Error: tool '{tool_name}' no existe"
                else:
                    result = function_to_call(**tool_input)

                if verbose:
                    preview = result[:200] + "..." if len(result) > 200 else result
                    print(f"resultado: {preview}")

                # Acá no hay un "id" como en Claude: Gemini matchea el
                # resultado con el llamado por el nombre de la función, en
                # el orden en que aparecen dentro del mismo turno.
                response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": result},
                    )
                )

        # Los resultados van como un turno de rol "user" (así lo pide la
        # API), con una function_response part por cada tool que se llamó
        contents.append(types.Content(role="user", parts=response_parts))

    # Se acabaron las iteraciones sin llegar a una respuesta final.
    # Prefiero devolver esto antes que dejar que reviente con un error raro.
    return "El agente no pudo completar la investigación en el límite de pasos permitido."


if __name__ == "__main__":
    # python agent.py y listo, prueba rápida por consola
    pregunta = input("Hacé tu pregunta: ")
    respuesta = run_agent(pregunta)
    print(f"\n{'='*50}\nRESPUESTA FINAL:\n{respuesta}")
