"""
Nucleo agentico de Repliker Economy.

Los grafos se importan explicitamente desde
sus modulos concretos para evitar dependencias
circulares y efectos secundarios al cargar
el paquete app.agentic.

Ejemplos:

from app.agentic.project_graph import (
    build_project_lifecycle_graph,
)

from app.agentic.execution_graph import (
    run_execution_graph,
)
"""
