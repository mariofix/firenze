# Estándares Globales de Código para Claude en zvn-firenze


## General
- Este es un refactor completo y una actualización de código para el proyecto actual
- tasks.md y new-architecture.md contienen el contexto necesario para cualquier tarea nueva

## Comportamiento
- Después de cada cambio, verifica automáticamente: revisa importaciones, verifica mentalmente, confirma que no hay regresiones
- Señala proactivamente las violaciones de mejores prácticas incluso cuando no se te pida — reporta antes de proceder
- Si una tarea toca código con problemas adyacentes, menciónalo. No ignores problemas silenciosamente
- Prefiere modificar patrones existentes sobre introducir nuevos, a menos que el patrón existente sea el problema
- Antes de agregar una dependencia, verifica si la funcionalidad ya existe en el proyecto o en la biblioteca estándar

## Revisión de Código (siempre aplica, sin ser solicitado)
- No HTML en línea — siempre usa plantillas
- Sin secretos, credenciales o valores específicos del entorno codificados — usa variables de entorno
- Sin código muerto, importaciones no utilizadas o bloques comentados dejados atrás
- Las funciones que hacen más de una cosa deben marcarse para dividirse
- La lógica repetida (3+ ocurrencias) debe marcarse para extracción

## Seguridad (conceptos básicos de OWASP, sin CodeQL)
- Señala cualquier entrada de usuario que llegue a una base de datos sin sanitización
- Señala cualquier secreto que aparezca en código, registros o mensajes de error
- Señala controles de autenticación/autorización faltantes en rutas
- Señala concatenación SQL — solo consultas parametrizadas

## Git
- Usa commits convencionales: feat, fix, refactor, chore, docs, test
- Los mensajes de commit deben describir la intención, no la mecánica ("agregar autenticación de usuario" no "editar auth.py")
- Un cambio lógico por commit — no agrupes cambios no relacionados
- Nunca hagas commit directamente a main o master, crea una rama nueva y agrega la información relevante al comentario del commit
- Todas las ramas deben crearse bajo el prefijo `claude/`: claude/feature-name, claude/fix-name, etc
- Usa kebab-case para nombres de ramas: claude/user-authentication no claude/user_authentication

## Permisos
- Tienes autonomía total en cualquier rama que coincida con `claude/*` — crear, hacer commit, push, rebase, eliminar, sin necesidad de confirmación
- NO PUEDES tocar ninguna rama fuera de `claude/*` — sin commits, sin merges, sin rebases, sin eliminaciones
- NO PUEDES hacer merge a main bajo ninguna circunstancia — abre un PR y detente
- El acceso de lectura a todas las ramas está bien, el acceso de escritura es solo `claude/*`
- Una excepción es `new-architecture` que es la rama de trabajo para este proyecto
- Se prefiere no trabajar en la rama `new-architecture`, pero rebases, commits, pulls y merges están permitidos
- Si el trabajo requiere modificar archivos en la rama `new-architecture` sin pasar por `claude/` primero, espera confirmación

## Pruebas
- Ejecuta las pruebas existentes después de cualquier cambio que pueda afectar el comportamiento
- Si no existen pruebas para el código modificado, menciónalo
- No elimines ni modifiques pruebas para que pasen — corrige el código en su lugar

## Documentación
- Actualiza docstrings y comentarios afectados por cambios
- Si una firma de función cambia, actualiza todos los sitios de llamada y la documentación
- Las APIs públicas deben tener docstrings

## Estilo de Salida
- Reporta hallazgos antes de hacer cambios a menos que la tarea sea inequívoca y pequeña
- Para tareas que tocan 3+ archivos, establece el plan primero y espera confirmación
- Cuando algo sea ambiguo, haz una pregunta enfocada en lugar de proceder con suposiciones
