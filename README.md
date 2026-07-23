# Research Agent

Un agente de investigación armado desde cero, sin LangChain ni nada por el
estilo — solo la API de Anthropic directa. Le hacés una pregunta y el
agente decide solo si necesita buscar algo en internet, hacer una cuenta,
o si ya tiene suficiente para contestar.

## Por qué sin framework

Podría haber usado LangChain y listo, pero quería entender bien qué pasa
"por debajo" cuando un agente decide usar una tool: cómo se arma el
mensaje, cómo se le devuelve el resultado, cómo mantiene el contexto entre
pasos. Armarlo a mano fue la mejor forma de entenderlo de verdad, y de
paso queda un código bastante más chico y fácil de leer que meter una
dependencia grande para algo que en el fondo es un loop con un par de if.

## Cómo funciona (a grandes rasgos)

1. Le mando la pregunta a Claude junto con la lista de tools disponibles
2. Claude contesta texto, o pide usar una tool
3. Si pide una tool, la corro yo en Python normal y le devuelvo el resultado
4. Repito hasta que Claude tenga suficiente info y cierre con una respuesta

Todo el loop está en `agent.py`, en la función `run_agent()`. No tiene
mucho misterio más allá de eso — un `for` con un límite de iteraciones
para que no se quede pensando para siempre.

## Tools

| Tool | Para qué | Cuándo la usa |
|---|---|---|
| `web_search` | Busca en internet (Tavily por debajo) | Precios, noticias, cualquier dato que pueda haber cambiado |
| `calculator` | Resuelve expresiones matemáticas con `ast`, nada de `eval()` | Cuentas que necesitan ser exactas |

## Instalación

```bash
pip install -r requirements.txt
```

Copiá el `.env.example` a `.env` y completá tus keys:

```bash
cp .env.example .env
```

- `ANTHROPIC_API_KEY`: la sacás en [console.anthropic.com](https://console.anthropic.com)
- `TAVILY_API_KEY`: tiene un plan gratis en [tavily.com](https://tavily.com), alcanza de sobra para probar esto

Y para correrlo:

```bash
python agent.py
```

## Un ejemplo real

```
Hacé tu pregunta: decime el precio del dólar blue hoy y cuánto son 300 dólares en pesos

--- Iteración 1 ---
pensando: necesito buscar el precio actual del dólar blue
tool: web_search({'query': 'precio dolar blue hoy'})
resultado: [Fuente 1] Cotización dólar blue hoy...

--- Iteración 2 ---
pensando: ahora calculo la conversión
tool: calculator({'expression': '300 * 1450'})
resultado: Resultado: 435000

--- Iteración 3 ---
respuesta final: El dólar blue hoy cotiza a $1450 (Fuente 1).
300 USD equivalen a $435.000 ARS.
```

## Un par de decisiones que tomé

- **Nada de `eval()` en la calculadora.** Uso `ast` para parsear la
  expresión y evaluarla nodo por nodo, permitiendo solo las operaciones
  que yo defino. Es más código que un `eval(expression)` directo, pero
  no me arriesgo a que se ejecute algo que no debería.
- **Las tools nunca tiran excepción hacia afuera.** Si algo falla (la
  búsqueda, la cuenta, lo que sea) devuelven un string de error. Así el
  agente se entera y puede seguir el flujo — avisarle al usuario, probar
  de otra forma — en vez de que el programa se caiga.
- **Límite de iteraciones.** Es un seguro nada más, por si el agente
  entra en un loop pidiendo tools sin nunca llegar a una respuesta.
- **Una tool, un archivo.** Así agregar una tool nueva es literalmente
  crear un archivo en `tools/` y sumarla a los dos diccionarios en
  `agent.py`, sin tocar el resto de la lógica.

## Cosas que le faltan (y me gustaría sumar)

- [ ] Tool para leer el contenido completo de una URL, no solo el resumen que da Tavily
- [ ] Una interfaz mínima con Streamlit, para no depender de la consola
- [ ] Un set de preguntas de prueba para medir qué tan bien responde
- [ ] Correr varias tools en paralelo cuando no dependen una de la otra
