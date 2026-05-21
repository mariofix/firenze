# Diseñador Visual de Dialplan de Asterisk — Propuesta de Arquitectura UX

Reemplazo de código abierto para [Apstel Visual Dialplan](https://www.apstel.com/features/) (descontinuado). Un diseñador de flujo de llamadas de arrastrar y soltar basado en navegador para Asterisk.

## Qué es

Un editor visual donde diseñas flujos de llamadas de Asterisk arrastrando, soltando y conectando componentes. La salida es un diagrama de flujo de llamadas que un administrador implementa en el dialplan real a través de CLI. La aplicación nunca toca el servidor Asterisk directamente.

**Flujo de trabajo:**
```
El diseñador construye el flujo visualmente → exporta diagrama / fragmentos de dialplan
→ El administrador lee el flujo → implementa en extensions.conf a través de CLI
→ El administrador ejecuta `dialplan reload`
```

Un **servidor de integración** opcional puede conectarse a una instancia de Asterisk en vivo para importar dialplans existentes o empujar cambios, pero no es obligatorio. La aplicación principal es un SPA estático que se ejecuta completamente en el navegador.

## Qué es Not

- No es un panel de administración PBX (FreePBX, Elastix, FusionPBX)
- No es un administrador de llamadas de tiempo de ejecución — no maneja llamadas en vivo
- No está vinculado a ninguna instalación específica de Asterisk o marco de trabajo

---

## Inspiración: Visual Dialplan de Apstel

Lo que Apstel ofreció (y lo que apuntamos a reemplazar):

| Característica | Apstel | Este Proyecto |
|---------|--------|--------------|
| Editor de flujo de arrastrar y soltar | Yes | Yes |
| Biblioteca de componentes (IVR, Cola, Marcar, etc.) | Sí, propietario | Sí, código abierto |
| Integraciones de base de datos (MySQL, PostgreSQL) | Yes | Planeado (a través del servidor de integración) |
| Compatibilidad con FreePBX/Elastix | Yes | Agnóstico — funciona con cualquier Asterisk |
| Componentees ASR/TTS | Yes | Planeado |
| Exportar a dialplan | Poco claro | Sí — fragmentos + conf completo |
| Licencia | Comercial, descontinuado | Código abierto (MIT o Apache-2.0) |
| Tiempo de ejecución | Aplicación de escritorio (Windows) | SPA del navegador — se ejecuta en cualquier lugar |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │  Flow Canvas  │  │  Componente       │  │  Propiedades Panel    │ │
│  │  (React Flow) │  │  Library Panel   │  │  (per-node config)   │ │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬────────────┘ │
│         │                   │                        │              │
│         └───────────┬───────┴────────────────────────┘              │
│                     │                                               │
│              ┌──────┴──────┐                                        │
│              │   Zustand    │  (flow graph + undo/redo + projects) │
│              └──────┬──────┘                                        │
│                     │                                               │
│              ┌──────┴──────┐                                        │
│              │  localStorage│  (save/load projects offline)         │
│              └─────────────┘                                        │
│                     │                                               │
│              ┌──────┴──────┐  (optional)                           │
│              │ Export       │                                        │
│              │ .drawio      │                                        │
│              │ .conf        │                                        │
│              │ .png / .svg  │                                        │
│              │ .json        │                                        │
│              └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
                      │
                      │ optional — integration server
                      │
┌─────────────────────┼───────────────────────────────────────────────┐
│              ┌──────┴──────┐                                        │
│              │ Integración  │  (FastAPI / Flask / Express — your    │
│              │ Server       │   choice, self-hosted, open source)   │
│              └──────┬──────┘                                        │
│                     │                                               │
│    ┌────────────────┼────────────────────┐                          │
│    │                │                    │                          │
│    ▼                ▼                    ▼                          │
│ ┌────────┐   ┌───────────┐   ┌────────────────┐                   │
│ │Asterisk│   │  Database  │   │ Import .conf   │                   │
│ │  AMI   │   │  (MySQL,   │   │ Parse existing │                   │
│ │  ARI   │   │  Postgres) │   │ dialplans      │                   │
│ └────────┘   └───────────┘   └────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Punto clave:** El SPA funciona de forma independiente. Sin servidor, sin inicio de sesión, sin instalación. Abre index.html en un navegador y comienza a diseñar. El servidor de integración es un proyecto separado, opcional.

---

## Pila de Tecnología

Todo código abierto, todo gratuito:

| Capa | Herramienta | Licencia | Por qué |
|-------|------|---------|-----|
| **Editor de flujo** | [React Flow](https://reactflow.dev/) | MIT | Editor de nodos de arrastrar y soltar con mangos, zoom, pan, minimapa. Construido para exactamente esto. |
| **Diseño automático** | [ELK.js](https://github.com/kieler/elkjs) | EPL-2.0 | Diseño jerárquico automático. Un clic para reorganizar automáticamente un gráfico desordenado. |
| **Frontend** | React 18 + TypeScript + Vite | MIT | React Flow requiere React. Vite construye rápido, genera paquetes pequeños. |
| **Componentees de UI** | [shadcn/ui](https://ui.shadcn.com/) | MIT | Componentees limpios, copiados y pegados en el proyecto (sin dependencia de tiempo de ejecución). |
| **Estado** | [Zustand](https://github.com/pmndrs/zustand) | MIT | Estado de flujo, deshacer/rehacer, gestión de proyectos. Ligero. |
| **Persistencia** | localStorage + JSON export/import | — | Sin servidor necesario. Proyectos guardados en el navegador o exportados como archivos `.json`. |
| **Vista previa de código** | [CodeMirror 6](https://codemirror.net/) | MIT | Vista previa de solo lectura de fragmentos de dialplan generados. |
| **Servidor de integración** (opcional) | FastAPI / Flask / Express | MIT | Auto hospedado. Se conecta a Asterisk AMI, importa archivos `.conf`, empuja cambios. |

---

## Biblioteca de Componentees

El corazón de la aplicación. Cada componente es un nodo de React Flow con mangos de entrada/salida tipados y un formulario de configuración.

### Componentees de Flujo de Llamadas

| Componente | Entradas | Salidas | Descripción |
|-----------|--------|---------|-------------|
| **Entrante** | — | 1 (call enters) | Punto de entrada. Configura: patrón DID, nombre de troncal, manejo de ID de llamada. |
| **Responder** | 1 | 1 | Responde al canal. Opcional: retraso antes de responder. |
| **Colgar** | 1 | — | Terminar la llamada. Configura: código de causa de cuelgue. |
| **Reproducción** | 1 | 1 | Reproduce un archivo de audio. Configura: nombre de archivo, idioma. |
| **Fondo** | 1 | 1 + per-digit | Play audio, accept DTMF. Salidas: one handle per expected digit. |
| **Leer** | 1 | 1 (valid) + 1 (timeout) | Lee entrada DTMF. Configura: dígitos máximos, tiempo de espera, reintentos, archivo de solicitud. |
| **Establecer Variable** | 1 | 1 | Establece una variable de canal. Configura: nombre de variable, valor/expresión. |
| **SiVa** | 1 | 2 (true/false) | Rama condicional. Configura: expresión. |
| **Cambiar** | 1 | N (per case) | Rama de múltiples caminos. Configura: variable, valores de caso. |

### Telefonía Componentes

| Componente | Entradas | Salidas | Descripción |
|-----------|--------|---------|-------------|
| **Marcar** | 1 | 3 (answered, busy, no-answer) | Marca un destino. Configura: tech/resource, tiempo de espera, opciones, ID de llamada. |
| **Cola** | 1 | 2 (answered, timeout) | Envía a una cola de llamadas. Configura: nombre de cola, tiempo de espera, archivos de anuncio. |
| **Correo de Voz** | 1 | 1 | Envía al correo de voz. Configura: buzón, opciones (saludo ocupado/no disponible). |
| **Transferencia** | 1 | 1 | Transferencia ciega/atendida. Configura: destino, tipo. |
| **Estacionar** | 1 | 1 | Estaciona la llamada. Configura: lote de estacionamiento. |
| **Conferencia** | 1 | 1 | Ingresa a un puente de conferencia. Configura: número de sala, PIN, opciones. |
| **MixMonitor** | 1 | 1 | Inicia/detiene la grabación. Configura: patrón de nombre de archivo, opciones. |

### IVR Componentes

| Componente | Entradas | Salidas | Descripción |
|-----------|--------|---------|-------------|
| **Menú** | 1 | N (per option) + 1 (invalid) + 1 (timeout) | Menú IVR completo. Configura: solicitud, opciones válidas, reintentos, tiempo de espera. |
| **Anunciar** | 1 | 1 | Reproduce anuncio y continúa. Configura: lista de archivos, interrumpible. |
| **DecirDígitos** | 1 | 1 | Habla un número. Configura: variable fuente. |
| **DecirFechaHora** | 1 | 1 | Habla fecha/hora. Configura: formato, zona horaria. |

### Advanced Componentes

| Componente | Entradas | Salidas | Descripción |
|-----------|--------|---------|-------------|
| **AGI** | 1 | 1 (success) + 1 (failure) | Ejecuta un script AGI. Configura: ruta de script, argumentos. |
| **Solicitud HTTP** | 1 | 1 (success) + 1 (failure) | CURL + JSON_DECODE. Configura: URL, método, mapeo de variable de respuesta. |
| **Búsqueda en Base de Datos** | 1 | 1 (found) + 1 (not found) | func_odbc o CURL a API de BD. Configura: consulta, variable de resultado. |
| **Establecer CDR** | 1 | 1 | Establece campos CDR. Configura: nombre de campo, valor. |
| **Subrutina** | 1 | 1 (return) | Gosub a un sub-flujo reutilizable. Configura: sub-flujo objetivo. |
| **Retorno** | 1 | — | Retorna de una subrutina. |
| **Etiqueta** | 1 | 1 | Etiqueta nombrada para objetivos Goto. Configura: nombre de etiqueta. |
| **Comentario** | — | — | Nodo de anotación no funcional. Configura: texto, color. |

### Agrupación

| Componente | Descripción |
|-----------|-------------|
| **Grupo de Contexto** | Contenedor visual que representa un `[context]`. Los nodos secundarios se convierten en extensiones dentro de él. |
| **Sub-flujo** | Grupo reutilizable de componentes. Se convierte en un objetivo `Gosub()`. Configura: nombre, argumentos. |

---

## Diseño de Nodo

Cada nodo de componente en React Flow tiene:

```
┌──────────────────────────────┐
│ ● mango(s) de entrada           │
├──────────────────────────────┤
│  [icon]  Componente Name      │
│  Resumen breve de configuración        │
│  p. ej. "Marcar SIP/troncal, 30s" │
├──────────────────────────────┤
│ ○ mango(s) de salida          │
│   etiquetado: "answered"        │
│   etiquetado: "busy"            │
│   etiquetado: "no-answer"       │
└──────────────────────────────┘
```

**Codificación de color por categoría:**

| Categoría | Color | Ejemplos |
|----------|-------|---------|
| Flujo de llamadas | Azul (`#dae8fc`) | Entrante, Responder, Colgar, SiVa |
| Telefonía | Verde (`#d5e8d4`) | Marcar, Cola, Transferencia, Estacionar |
| IVR / Audio | Amarillo (`#fff2cc`) | Menú, Reproducción, Leer, DecirDígitos |
| Integración | Púrpura (`#e1d5e7`) | AGI, Solicitud HTTP, Búsqueda en Base de Datos |
| Utilidad | Gris (`#f5f5f5`) | Establecer Variable, Etiqueta, Comentario, Establecer CDR |

---

## Diseño de UI

```
┌────────────────────────────────────────────────────────────────────────────┐
│ [☰] Diseñador de Flujo de Asterisk    [Proyecto ▼]   [Deshacer] [Rehacer]   [Exportar ▼]   │
├──────────┬─────────────────────────────────────────────┬───────────────────┤
│          │                                             │                   │
│ Componente│              Flow Canvas                    │   Propiedades      │
│ Library  │                                             │   Panel           │
│          │  ┌──────────┐       ┌──────────┐           │                   │
│ ┌──────┐ │  │ Inbound  │──────▶│ Answer   │           │ ┌───────────────┐ │
│ │Inbnd │ │  │ DID: _X. │       │          │           │ │ Dial          │ │
│ ├──────┤ │  └──────────┘       └────┬─────┘           │ ├───────────────┤ │
│ │Answer│ │                          │                  │ │ Tech: SIP     │ │
│ ├──────┤ │                     ┌────▼─────┐           │ │ Recurso:     │ │
│ │ Dial │ │                     │ Menu     │           │ │ [troncal/núm  ] │ │
│ ├──────┤ │                     │ prompt:  │           │ │ Tiempo de espera: [30] │ │
│ │ Menu │ │                     │ welcome  │           │ │ ID de Llamada:     │ │
│ ├──────┤ │                     └┬───┬───┬─┘           │ │ [${CALLERID}] │ │
│ │Queue │ │                      │   │   │             │ │ Opciones: [tT] │ │
│ ├──────┤ │                      1   2   *             │ │               │ │
│ │ Read │ │                      │   │   │             │ │ Salidas:      │ │
│ ├──────┤ │              ┌───────┘   │   └──────┐      │ │ ● Respondida    │ │
│ │ AGI  │ │              ▼           ▼          ▼      │ │ ● Ocupado        │ │
│ ├──────┤ │         ┌────────┐ ┌────────┐ ┌────────┐  │ │ ● Sin Respuesta   │ │
│ │ HTTP │ │         │ Queue  │ │  Dial  │ │Hangup  │  │ │ ● Congestión  │ │
│ ├──────┤ │         │ sales  │ │operator│ │        │  │ └───────────────┘ │
│ │ ...  │ │         └────────┘ └────────┘ └────────┘  │                   │
│ └──────┘ │                                             │                   │
│          │  ┌─── Minimap ───┐                         │                   │
│          │  │ [  ·  ]       │                         │                   │
│          │  └───────────────┘                         │                   │
├──────────┴─────────────────────────────────────────────┴───────────────────┤
│ [Vista previa de Dialplan]  Fragmento de extensions.conf generado (solo lectura)         │
│ ┌────────────────────────────────────────────────────────────────────────┐ │
│ │ [inbound-main]                                                        │ │
│ │ exten => _X.,1,Answer()                                               │ │
│ │  same => n,Background(welcome)                                        │ │
│ │  same => n,WaitExten(5)                                               │ │
│ │ exten => 1,1,Queue(sales)                                             │ │
│ │ exten => 2,1,Dial(SIP/operator,30,tT)                                │ │
│ │ exten => *,1,Hangup()                                                 │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### Comportamiento del Panel

- **Biblioteca de Componentes** (left): arrastra componentes al lienzo. Buscable. Agrupado por categoría.
- **Flow Canvas** (center): React Flow. Arrastra para conectar mangos de salida → mangos de entrada. Zoom, pan, minimapa.
- **Propiedades Panel** (right): aparece cuando se selecciona un nodo. Campos de formulario para la configuración de ese componente.
- **Dialplan Preview** (bottom): fragmento `extensions.conf` generado en vivo. Se actualiza mientras editas el flujo. Solo lectura, copiar al portapapeles.

---

## Gestión de Proyectos

Los proyectos son archivos JSON autónomos. Sin servidor, sin cuenta.

### Guardar/Cargar

- **localStorage**: guarda automáticamente el proyecto actual. Sobrevive a la actualización del navegador.
- **Export `.json`**: descarga el proyecto completo (gráfico de flujo + configuraciones de componentes) como archivo.
- **Import `.json`**: carga un proyecto exportado previamente.
- **Multiple projects**: selector de proyectos en la barra de herramientas. Cada proyecto es independiente.

### Formatos de Exportación

| Format | Caso de Uso |
|--------|----------|
| **`.json`** | Proyecto completo — reimportar en el editor posteriormente |
| **`.conf`** | Fragmento `extensions.conf` generado — copia en tu configuración de Asterisk |
| **`.drawio`** | Abre en draw.io para edición de diagrama adicional o documentación |
| **`.png` / `.svg`** | Imagen estática para documentos, wikis, Slack |

### Estructura del Archivo de Proyecto

```json
{
  "name": "Main IVR",
  "version": "1.0",
  "created": "2026-03-17T00:00:00Z",
  "modified": "2026-03-17T12:00:00Z",
  "nodes": [
    {
      "id": "node-1",
      "type": "inbound",
      "position": {"x": 100, "y": 50},
      "data": {
        "didPattern": "_X.",
        "trunkName": "didww-inbound",
        "callerIdHandling": "filter-digits"
      }
    },
    {
      "id": "node-2",
      "type": "menu",
      "position": {"x": 100, "y": 200},
      "data": {
        "prompt": "welcome",
        "options": ["1", "2", "*"],
        "timeout": 5,
        "retries": 3
      }
    }
  ],
  "edges": [
    {"source": "node-1", "sourceHandle": "out", "target": "node-2", "targetHandle": "in"}
  ],
  "globals": {
    "TRUNK_OUT": "didww-outbound"
  }
}
```

---

## Generación de Código de Dialplan

El panel inferior genera sintaxis `extensions.conf` en tiempo real desde el flujo visual.

### Reglas de Generación

Cada nodo de **Grupo de Contexto** se convierte en una sección `[context]`. Los nodos dentro se convierten en extensiones y prioridades.

```
Grupo de Contexto "inbound-main"
  └─ Entrante (_X.) → Responder → Menú (bienvenida, opciones: 1,2,*)
       ├─ 1 → Cola (ventas)
       ├─ 2 → Marcar (SIP/operador, 30s)
       └─ * → Colgar
```

Genera:

```ini
[inbound-main]
exten => _X.,1,Answer()
 same => n,Background(welcome)
 same => n,WaitExten(5)

exten => 1,1,Queue(sales)

exten => 2,1,Dial(SIP/operator,30,tT)

exten => *,1,Hangup()
```

### Lo que maneja

- Nodos secuenciales → encadenamiento de prioridad `same => n`
- Nodos de rama (SiVa, Cambiar, Menú) → líneas `exten =>` separadas por rama
- Sub-flujos → `Gosub(sub-flow-name,s,1)` + contexto `[sub-flow-name]` separado
- Grupos de Contexto → secciones `[context-name]`
- Variables → aplicaciones `Set()` con el name=value configurado
- Llamadas HTTP → `Set(response=${CURL(url)})` + `Set(var=${JSON_DECODE(response,key)})`

### Lo que no maneja (aún)

- Optimización (p. ej., colapsar llamadas Set() redundantes)
- Salida AEL o Lua (solo extensions.conf por ahora)
- Validación completa contra un Asterisk en ejecución (ese es el trabajo del servidor de integración)

---

## Servidor de Integración Opcional

Un servicio separado auto hospedado. No requerido para el editor principal.

### Lo que hace

| Característica | Descripción |
|---------|-------------|
| **Importar dialplan existente** | Analiza archivos `.conf` → proyecto JSON. Carga una configuración existente de Asterisk en el editor visual. |
| **Empujar a Asterisk** | Escribe `.conf` generado en el servidor, ejecuta `dialplan reload`. |
| **Puente AMI** | Conecta con la Interfaz del Gestor de Asterisk para estado de canal en vivo, origina llamadas para pruebas. |
| **Proxy de base de datos** | Consulta MySQL/PostgreSQL desde el editor (para configuración del componente Búsqueda en BD). |

### Arquitectura

Cualquier lenguaje, cualquier marco de trabajo. Una implementación de referencia en Python (FastAPI) o Node (Express):

```
GET  /api/dialplan/import          → analiza archivos .conf → retorna proyecto JSON
POST /api/dialplan/deploy          → recibe contenido .conf → escribe + recarga
GET  /api/asterisk/channels        → AMI: lista canales activos
POST /api/asterisk/originate       → AMI: origina una llamada de prueba
GET  /api/db/query                 → proxy una consulta BD para el componente Búsqueda BD
```

### Seguridad

- Autenticación requerida (clave API o JWT)
- El despliegue requiere permisos elevados
- Sin inyección de shell — `dialplan reload` es un comando AMI codificado
- El proxy BD usa solo consultas parametrizadas, solo lectura por defecto
- El servidor de integración es opcional y auto hospedado — controlas quién tiene acceso

---

## Pila de Tecnología

Todo código abierto, todo gratuito:

| Capa | Herramienta | Licencia |
|-------|------|---------|
| **Editor de flujo** | [React Flow](https://reactflow.dev/) | MIT |
| **Diseño automático** | [ELK.js](https://github.com/kieler/elkjs) | EPL-2.0 |
| **Frontend** | React 18 + TypeScript + Vite | MIT |
| **Componentees de UI** | [shadcn/ui](https://ui.shadcn.com/) | MIT |
| **State + undo/redo** | [Zustand](https://github.com/pmndrs/zustand) | MIT |
| **Vista previa de código** | [CodeMirror 6](https://codemirror.net/) | MIT |
| **Persistencia** | localStorage + file export | — |
| **Servidor de integración** (opcional) | FastAPI / Express / your choice | MIT |

**Despliegue:** Archivos estáticos. Hospeda en GitHub Pages, Netlify, cualquier CDN, o simplemente abre `index.html` localmente. Costo de servidor cero para el editor principal.

---

## Estructura de Archivo

```
asterisk-flow-designer/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   │
│   ├── store/
│   │   ├── flow-store.ts          # Zustand: nodes, edges, undo/redo
│   │   └── project-store.ts       # Zustand: save/load/export projects
│   │
│   ├── components/
│   │   ├── Canvas.tsx             # React Flow wrapper
│   │   ├── BibliiotecaComponentes.tsx   # Left panel: draggable component list
│   │   ├── PropiedadesPanel.tsx    # Right panel: selected node config form
│   │   ├── VistaPreviewaDialplan.tsx    # Bottom panel: generated .conf (CodeMirror)
│   │   ├── BarraHerramientas.tsx            # Top: project switcher, undo/redo, export
│   │   └── DiálogoExportar.tsx       # Export format picker
│   │
│   ├── nodes/                     # Custom React Flow node types
│   │   ├── NodoEntrante.tsx
│   │   ├── NodoResponder.tsx
│   │   ├── NodoColgar.tsx
│   │   ├── NodoMarcar.tsx
│   │   ├── NodoMenú.tsx
│   │   ├── NodoCola.tsx
│   │   ├── NodoReproducción.tsx
│   │   ├── NodoLeer.tsx
│   │   ├── NodoSiVa.tsx
│   │   ├── NodoCambiar.tsx
│   │   ├── NodoAGI.tsx
│   │   ├── NodoSolicitudHTTP.tsx
│   │   ├── NodoBúsquedaBaseDatos.tsx
│   │   ├── NodoEstablecerVariable.tsx
│   │   ├── NodoSubrutina.tsx
│   │   ├── NodoComentario.tsx
│   │   └── NodoGrupoContexto.tsx
│   │
│   ├── generators/
│   │   ├── generador-conf.ts      # Flow graph → extensions.conf syntax
│   │   ├── generador-drawio.ts    # Flow graph → .drawio XML
│   │   └── generador-imagen.ts     # Flow graph → PNG/SVG via React Flow export
│   │
│   ├── properties/                # Per-component property forms
│   │   ├── InboundPropiedades.tsx
│   │   ├── DialPropiedades.tsx
│   │   ├── MenuPropiedades.tsx
│   │   ├── QueuePropiedades.tsx
│   │   └── ...
│   │
│   └── utils/
│       ├── diseño.ts              # ELK.js auto-layout config
│       ├── validación.ts          # Flow validation (disconnected nodes, cycles, etc.)
│       └── tipos.ts               # TypeScript types for components and flow graph
│
├── servidor-integración/            # Optional — separate project
│   ├── requirements.txt           # or package.json
│   ├── servidor.py                  # FastAPI / Express
│   ├── analizador.py                  # .conf → project JSON
│   └── ami.py                     # Asterisk Manager Interface bridge
│
└── dist/                          # Built SPA — deploy anywhere
```

---

## Fases de Implementación

### Fase 1: Analizador + importación visual (MVP)

**Objetivo:** Pega tu dialplan existente, ve como un gráfico visual. Valor instantáneo, sin redibujo manual.

1. Analizador de dialplan (Python, módulo autónomo — sin dependencia de Asterisk)
   - Entrada: texto `.conf` (pega en área de texto o carga archivos)
   - Salida: proyecto JSON (nodos + bordes + configuraciones de componentes)
   - Maneja: `[context]`, `exten =>`, `same => n`, `include =>`, `#include`, `[globals]`
   - Extrae bordes de `Goto()`, `SiVa()`, `Gosub()`, `include =>`
   - Clasifica pasos: noop, variable, reproducción, marcar, agi, rama, http
   - Detecta objetivos Goto dinámicos (`Goto(${var},s,1)`)
2. Lienzo de React Flow renderizando el gráfico analizado
3. Diseño automático (ELK.js) — flujos importados organizados automáticamente
4. Propiedades panel — click a node, see its parsed config (read-only at this stage)
5. Validación básica: objetivos Goto rotos, contextos inaccesibles, variables indefinidas
6. Exportar: `.json` (reimportar después), `.png`/`.svg` (documentación)

**Valor:** "Pega tu `extensions.conf`, obtén un mapa visual de tu flujo de llamadas." Este es el gancho — cada administrador de Asterisk tiene un dialplan que nunca ha visualizado completamente. El analizador hace la mitad del trabajo; React Flow hace la otra mitad.

### Fase 2: Editor visual + generación de código

**Objetivo:** Edita el flujo importado visualmente. Diseña nuevos flujos desde cero. Genera dialplan.

1. Arrastra y suelta de la biblioteca de componentes (comienza con 5-6 nodos principales: Entrante, Responder, Marcar, Menú, Colgar, Reproducción)
2. Propiedades panel becomes editable — configure each component via forms
3. `generador-conf.ts` — vista previa de dialplan en vivo en panel inferior (flujo → `.conf`)
4. Guardar/cargar a localStorage
5. Exportar como `.conf` (fragmentos de dialplan generados)
6. Viaje redondo: importa `.conf` → edita visualmente → exporta `.conf` → diferencia del original

**Valor:** El bucle de diseño completo. Importa, ajusta, exporta. O comienza desde cero.

### Fase 3: Biblioteca de componentes completa + pulido

**Objetivo:** Cubre todas las aplicaciones comunes de Asterisk. Herramienta de calidad de producción.

1. Agrega componentes restantes: Cola, Leer, SiVa, Cambiar, Correo de Voz, Transferencia, Estacionar, Conferencia, MixMonitor, AGI, Solicitud HTTP, Búsqueda en Base de Datos, Establecer Variable, Establecer CDR, Subrutina, Etiqueta, Comentario
2. Nodos de Grupo de Contexto (contenedores visuales para secciones `[context]`)
3. Soporte de sub-flujo (grupos de componentes reutilizables)
4. Deshacer/Rehacer
5. Múltiples proyectos con selector de proyectos
6. Búsqueda/filtro de componentes en panel de biblioteca
7. Atajos de teclado (eliminar, copiar/pegar, deshacer/rehacer)
8. Exportar a `.drawio`

**Valor:** Puede diseñar cualquier flujo de llamadas de Asterisk, no solo IVRs simples.

### Fase 4: Servidor de integración (opcional)

**Objetivo:** Conecta a un Asterisk en vivo para importación/despliegue/prueba.

1. Sirve el analizador como un endpoint API (pega `.conf` en navegador → POST a servidor → obtén proyecto JSON)
2. Importación basada en archivos: apunta a un directorio de archivos `.conf` en el servidor
3. Endpoint de despliegue → escribe `.conf` generado + `dialplan reload`
4. Puente AMI → muestra estado de canal en vivo, origina llamadas de prueba
5. Proxy de BD → configura componentes de Búsqueda en BD contra datos reales

**Valor:** Flujo de trabajo de viaje redondo completo para equipos que manejan instalaciones de Asterisk.
