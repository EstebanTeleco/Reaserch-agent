"""
Loop principal del agente.

La idea es simple (ReAct, básicamente): le paso la pregunta a Claude junto
con las tools que tiene disponibles, y dejo que él decida qué hacer. Si
contesta texto, listo, esa es la respuesta. Si pide usar una tool, la corro
yo acá en Python normal y le devuelvo el resultado. Y así hasta que llegue
a algo definitivo o se acabe el margen de iteraciones.

No usé ningún framework (LangChain, etc) a propósito, para entender bien
qué pasa "por debajo" cuando un agente usa tools.
"""
import os
from anthropic import Anthropic
from dotenv import load_dotenv

from tools.web_search import web_search, WEB_SEARCH_TOOL_DEFINITION
from tools.calculator import calculator, CALCULATOR_TOOL_DEFINITION

load_dotenv()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Estas son las tools que Claude "ve" y puede pedir usar
TOOLS = [WEB_SEARCH_TOOL_DEFINITION, CALCULATOR_TOOL_DEFINITION]

# Y acá el mapeo nombre -> función real. Cuando Claude devuelve
# tool_use con name="web_search", busco en este dict y ejecuto.
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
    messages = [{"role": "user", "content": user_question}]

    for iteration in range(MAX_ITERATIONS):
        if verbose:
            print(f"\n--- Iteración {iteration + 1} ---")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Guardo la respuesta en el historial. Esto es importante: si no
        # la guardo acá, Claude "pierde la memoria" de lo que ya pensó/pidió
        # en la próxima vuelta del loop.
        messages.append({"role": "assistant", "content": response.content})

        # Si no pidió tool, ya tenemos la respuesta final
        if response.stop_reason != "tool_use":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            if verbose:
                print(f"\nrespuesta final:\n{final_text}")
            return final_text

        # Si llegamos acá, pidió al menos una tool. A veces vienen varias
        # en el mismo mensaje (ej: texto + tool_use, o dos tool_use juntos),
        # así que recorro todos los bloques por las dudas.
        tool_results = []

        for block in response.content:
            if block.type == "text" and verbose:
                print(f"pensando: {block.text}")

            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                if verbose:
                    print(f"tool: {tool_name}({tool_input})")

                function_to_call = TOOL_FUNCTIONS.get(tool_name)
                if function_to_call is None:
                    # No debería pasar nunca (Claude solo puede pedir tools
                    # que le mostramos en TOOLS) pero mejor cubrirlo
                    result = f"Error: tool '{tool_name}' no existe"
                else:
                    result = function_to_call(**tool_input)

                if verbose:
                    preview = result[:200] + "..." if len(result) > 200 else result
                    print(f"resultado: {preview}")

                # El tool_use_id es clave acá, es lo que le permite a Claude
                # saber a qué llamado corresponde cada resultado (sobre todo
                # cuando hay más de una tool en el mismo turno)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    }
                )

        # Los resultados van como mensaje de rol "user" — así lo pide la API,
        # aunque en la práctica sea el sistema respondiendo, no el usuario
        messages.append({"role": "user", "content": tool_results})

    # Se acabaron las iteraciones sin llegar a una respuesta final.
    # Prefiero devolver esto antes que dejar que reviente con un error raro.
    return "El agente no pudo completar la investigación en el límite de pasos permitido."


if __name__ == "__main__":
    # python agent.py y listo, prueba rápida por consola
    pregunta = input("Hacé tu pregunta: ")
    respuesta = run_agent(pregunta)
    print(f"\n{'='*50}\nRESPUESTA FINAL:\n{respuesta}")
