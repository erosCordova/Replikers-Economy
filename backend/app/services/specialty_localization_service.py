from __future__ import annotations


SPECIALTY_LABELS_ES = {
    "product / requirements":
        "Producto y Requisitos",
    "software architect":
        "Arquitecto de Software",
    "ux research":
        "Investigación de Experiencia de Usuario",
    "ui designer":
        "Diseñador de Interfaz",
    "frontend developer":
        "Desarrollador de Interfaz",
    "backend developer":
        "Desarrollador de Servidor",
    "database engineer":
        "Ingeniero de Base de Datos",
    "integration specialist":
        "Especialista en Integraciones",
    "security engineer":
        "Ingeniero de Seguridad",
    "qa engineer":
        "Ingeniero de Pruebas",
    "devops engineer":
        "Ingeniero de Operaciones y Despliegue",
    "accessibility specialist":
        "Especialista en Accesibilidad",
    "seo / performance specialist":
        "Especialista en Posicionamiento y Rendimiento",
    "seo/performance specialist":
        "Especialista en Posicionamiento y Rendimiento",
    "content / copy specialist":
        "Especialista en Contenido",
    "content/copy specialist":
        "Especialista en Contenido",
    "final reviewer":
        "Revisor Final",
    "generalist":
        "Generalista",
}


def specialty_label_es(
    value: str | None,
) -> str:
    normalized = " ".join(
        str(
            value or ""
        )
        .strip()
        .casefold()
        .split()
    )

    if not normalized:
        return "Especialidad requerida"

    return SPECIALTY_LABELS_ES.get(
        normalized,
        "Especialidad requerida",
    )
