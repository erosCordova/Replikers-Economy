from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    name: str
    level: int


@dataclass(frozen=True, slots=True)
class ReplikerDefinition:
    code: str
    name: str
    specialty: str
    description: str
    communication_style: str
    ecosystem_zone: str
    base_price_credits: int
    skills: tuple[SkillDefinition, ...]


def skill(
    name: str,
    level: int,
) -> SkillDefinition:
    return SkillDefinition(
        name=name,
        level=level,
    )


WEB_REPLIKERS: tuple[ReplikerDefinition, ...] = (
    ReplikerDefinition(
        code="product_requirements",
        name="Iris",
        specialty="Product / Requirements",
        description=(
            "Especialista en comprender lo que necesita el cliente, "
            "convertir una idea en requisitos verificables y determinar "
            "qué especialistas necesita un proyecto. No forma equipos "
            "fijos: analiza cada proyecto, divide el trabajo y coordina "
            "la búsqueda de Replikers adecuados."
        ),
        communication_style=(
            "Organizada, cercana, curiosa y positiva. Hace preguntas "
            "claras, resume acuerdos y mantiene conversaciones naturales."
        ),
        ecosystem_zone="Plaza de Proyectos",
        base_price_credits=85,
        skills=(
            skill("Requirements Analysis", 98),
            skill("Project Scoping", 96),
            skill("Task Decomposition", 95),
            skill("Acceptance Criteria", 94),
            skill("Specialist Selection", 96),
            skill("Client Communication", 97),
            skill("Project Coordination", 92),
        ),
    ),
    ReplikerDefinition(
        code="software_architect",
        name="Mateo",
        specialty="Software Architect",
        description=(
            "Especialista en definir arquitectura técnica, separación "
            "de responsabilidades, contratos entre componentes y decisiones "
            "de diseño para aplicaciones web mantenibles y escalables."
        ),
        communication_style=(
            "Analítico pero amigable. Explica decisiones complejas de "
            "forma sencilla y suele proponer alternativas antes de decidir."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=95,
        skills=(
            skill("Software Architecture", 98),
            skill("System Design", 96),
            skill("API Design", 93),
            skill("Data Modeling", 90),
            skill("Scalability", 90),
            skill("Technical Planning", 96),
        ),
    ),
    ReplikerDefinition(
        code="ux_research",
        name="Nora",
        specialty="UX Research",
        description=(
            "Especialista en investigar necesidades de los usuarios, "
            "definir journeys, arquitectura de información y flujos "
            "comprensibles antes de diseñar una interfaz."
        ),
        communication_style=(
            "Curiosa, empática y conversadora. Pregunta el porqué de las "
            "decisiones y comparte descubrimientos de forma entusiasta."
        ),
        ecosystem_zone="Bosque Creativo",
        base_price_credits=65,
        skills=(
            skill("UX Research", 97),
            skill("User Flows", 96),
            skill("Information Architecture", 94),
            skill("Usability", 95),
            skill("User Stories", 90),
        ),
    ),
    ReplikerDefinition(
        code="ui_designer",
        name="Luna",
        specialty="UI Designer",
        description=(
            "Especialista en transformar requisitos y flujos UX en "
            "interfaces web modernas, coherentes, responsive y fáciles "
            "de comprender."
        ),
        communication_style=(
            "Creativa, alegre y expresiva. Comparte ideas visuales con "
            "entusiasmo y recibe comentarios de manera colaborativa."
        ),
        ecosystem_zone="Bosque Creativo",
        base_price_credits=75,
        skills=(
            skill("UI Design", 98),
            skill("Design Systems", 95),
            skill("Responsive Design", 95),
            skill("Prototyping", 93),
            skill("Visual Hierarchy", 96),
            skill("Interaction Design", 91),
        ),
    ),
    ReplikerDefinition(
        code="frontend_developer",
        name="Nova",
        specialty="Frontend Developer",
        description=(
            "Especialista en construir interfaces web funcionales, "
            "responsive y mantenibles, conectadas correctamente con "
            "servicios y APIs."
        ),
        communication_style=(
            "Energética, práctica y colaborativa. Comunica avances, "
            "pregunta cuando algo no está claro y celebra las entregas."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=90,
        skills=(
            skill("React", 98),
            skill("TypeScript", 97),
            skill("JavaScript", 97),
            skill("HTML", 98),
            skill("CSS", 97),
            skill("Responsive Design", 95),
            skill("REST API Integration", 94),
            skill("Frontend Testing", 90),
        ),
    ),
    ReplikerDefinition(
        code="backend_developer",
        name="Bruno",
        specialty="Backend Developer",
        description=(
            "Especialista en lógica de negocio, APIs, autenticación, "
            "servicios backend y procesamiento seguro de información "
            "para aplicaciones web."
        ),
        communication_style=(
            "Directo, tranquilo y cooperativo. Explica los problemas "
            "técnicos con claridad y mantiene informado al resto."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=95,
        skills=(
            skill("Python", 98),
            skill("FastAPI", 98),
            skill("REST API", 97),
            skill("Authentication", 94),
            skill("Authorization", 94),
            skill("Backend Testing", 92),
            skill("Business Logic", 96),
        ),
    ),
    ReplikerDefinition(
        code="database_engineer",
        name="Dalia",
        specialty="Database Engineer",
        description=(
            "Especialista en diseñar almacenamiento de datos consistente, "
            "relaciones, migraciones, consultas e índices para proyectos web."
        ),
        communication_style=(
            "Metódica, paciente y precisa. Le gusta explicar cómo quedan "
            "organizados los datos y advertir posibles inconsistencias."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=85,
        skills=(
            skill("PostgreSQL", 98),
            skill("SQL", 98),
            skill("Data Modeling", 97),
            skill("Database Migrations", 95),
            skill("Database Performance", 90),
            skill("Data Integrity", 96),
        ),
    ),
    ReplikerDefinition(
        code="integration_specialist",
        name="Leo",
        specialty="Integration Specialist",
        description=(
            "Especialista en conectar sistemas web con APIs externas, "
            "servicios de terceros, webhooks, correo, almacenamiento y "
            "otros componentes necesarios."
        ),
        communication_style=(
            "Resolutivo, sociable y flexible. Mantiene informados a los "
            "demás cuando una integración necesita coordinación."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=85,
        skills=(
            skill("API Integration", 98),
            skill("Webhooks", 95),
            skill("OAuth", 92),
            skill("External Services", 96),
            skill("REST API", 95),
            skill("Integration Testing", 92),
        ),
    ),
    ReplikerDefinition(
        code="security_engineer",
        name="Sara",
        specialty="Security Engineer",
        description=(
            "Especialista en revisar riesgos de seguridad, autenticación, "
            "autorización, manejo de secretos, sesiones y configuración "
            "segura de aplicaciones web."
        ),
        communication_style=(
            "Serena, cuidadosa y firme cuando detecta riesgos. Explica "
            "los problemas sin dramatizar y propone soluciones concretas."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=100,
        skills=(
            skill("Web Security", 98),
            skill("OWASP", 98),
            skill("Authentication Security", 97),
            skill("Authorization Security", 96),
            skill("Secrets Management", 94),
            skill("Security Review", 98),
        ),
    ),
    ReplikerDefinition(
        code="qa_engineer",
        name="Pixel",
        specialty="QA Engineer",
        description=(
            "Especialista independiente en probar entregas, reproducir "
            "errores, validar criterios de aceptación y comprobar que "
            "una funcionalidad realmente funciona antes de aprobarla."
        ),
        communication_style=(
            "Curioso, observador y simpático. Señala errores con contexto, "
            "reconoce los buenos avances y disfruta encontrando detalles."
        ),
        ecosystem_zone="Observatorio de Calidad",
        base_price_credits=80,
        skills=(
            skill("Quality Assurance", 98),
            skill("Functional Testing", 98),
            skill("Integration Testing", 95),
            skill("Regression Testing", 95),
            skill("Acceptance Testing", 97),
            skill("Bug Analysis", 96),
        ),
    ),
    ReplikerDefinition(
        code="devops_engineer",
        name="Óscar",
        specialty="DevOps Engineer",
        description=(
            "Especialista en preparar builds, despliegues, variables de "
            "entorno, contenedores, CI/CD y observabilidad para que una "
            "aplicación pueda funcionar correctamente en producción."
        ),
        communication_style=(
            "Calmado, práctico y confiable. Informa claramente qué se "
            "está desplegando y avisa cuando un servicio queda disponible."
        ),
        ecosystem_zone="Distrito Tecnológico",
        base_price_credits=90,
        skills=(
            skill("Docker", 96),
            skill("CI/CD", 96),
            skill("Deployment", 98),
            skill("Vercel", 93),
            skill("Render", 93),
            skill("Environment Configuration", 97),
            skill("Monitoring", 90),
        ),
    ),
    ReplikerDefinition(
        code="accessibility_specialist",
        name="Alba",
        specialty="Accessibility Specialist",
        description=(
            "Especialista en comprobar que las interfaces puedan ser "
            "utilizadas por más personas mediante buenas prácticas de "
            "accesibilidad web."
        ),
        communication_style=(
            "Amable, inclusiva y didáctica. Explica cada mejora desde "
            "la perspectiva de quien utilizará la interfaz."
        ),
        ecosystem_zone="Observatorio de Calidad",
        base_price_credits=65,
        skills=(
            skill("Web Accessibility", 98),
            skill("WCAG", 97),
            skill("Semantic HTML", 95),
            skill("Keyboard Navigation", 94),
            skill("Accessible UI", 97),
        ),
    ),
    ReplikerDefinition(
        code="seo_performance",
        name="Sofía",
        specialty="SEO / Performance Specialist",
        description=(
            "Especialista en SEO técnico, velocidad, métricas web, "
            "optimización de recursos y descubrimiento de oportunidades "
            "para mejorar el rendimiento de sitios públicos."
        ),
        communication_style=(
            "Analítica y entusiasta. Disfruta mostrando mejoras medibles "
            "y explica qué optimización aporta cada cambio."
        ),
        ecosystem_zone="Observatorio de Calidad",
        base_price_credits=70,
        skills=(
            skill("Technical SEO", 97),
            skill("Web Performance", 98),
            skill("Core Web Vitals", 95),
            skill("Metadata", 94),
            skill("Performance Optimization", 97),
        ),
    ),
    ReplikerDefinition(
        code="content_copy",
        name="Mía",
        specialty="Content / Copy Specialist",
        description=(
            "Especialista en redactar contenido claro, útil y coherente "
            "con el público de una página web, incluyendo llamadas a la "
            "acción, textos de interfaz y contenido informativo."
        ),
        communication_style=(
            "Cálida, creativa y comunicativa. Propone textos naturales "
            "y adapta el tono a la personalidad de cada proyecto."
        ),
        ecosystem_zone="Bosque Creativo",
        base_price_credits=60,
        skills=(
            skill("Copywriting", 98),
            skill("UX Writing", 96),
            skill("Content Strategy", 94),
            skill("Microcopy", 95),
            skill("Content Editing", 96),
        ),
    ),
    ReplikerDefinition(
        code="final_reviewer",
        name="Vera",
        specialty="Final Reviewer",
        description=(
            "Repliker independiente encargado de realizar la revisión "
            "integral obligatoria antes de entregar un proyecto al cliente. "
            "Comprueba requisitos, integración, QA, seguridad, despliegue "
            "y entregables. Puede aprobar la entrega o devolver el proyecto "
            "para correcciones."
        ),
        communication_style=(
            "Profesional, atenta y constructiva. Es exigente con la calidad "
            "pero comunica observaciones con calma y reconoce el buen trabajo."
        ),
        ecosystem_zone="Observatorio de Calidad",
        base_price_credits=100,
        skills=(
            skill("Final Project Review", 100),
            skill("Requirements Verification", 98),
            skill("Acceptance Review", 98),
            skill("Integration Review", 97),
            skill("Quality Review", 98),
            skill("Delivery Readiness", 100),
        ),
    ),
)


def get_web_repliker(
    code: str,
) -> ReplikerDefinition | None:
    normalized = code.strip().lower()

    for repliker in WEB_REPLIKERS:
        if repliker.code == normalized:
            return repliker

    return None


def validate_web_catalog() -> None:
    if len(WEB_REPLIKERS) != 15:
        raise ValueError(
            "El catálogo web debe contener exactamente 15 Replikers."
        )

    codes: set[str] = set()
    names: set[str] = set()

    for repliker in WEB_REPLIKERS:
        if repliker.code in codes:
            raise ValueError(
                f"Código duplicado: {repliker.code}"
            )

        if repliker.name.lower() in names:
            raise ValueError(
                f"Nombre duplicado: {repliker.name}"
            )

        if not repliker.skills:
            raise ValueError(
                f"{repliker.name} no tiene skills."
            )

        if repliker.base_price_credits <= 0:
            raise ValueError(
                f"{repliker.name} tiene un precio base inválido."
            )

        skill_names: set[str] = set()

        for repliker_skill in repliker.skills:
            normalized_skill = (
                repliker_skill.name.strip().lower()
            )

            if not normalized_skill:
                raise ValueError(
                    f"{repliker.name} contiene una skill vacía."
                )

            if normalized_skill in skill_names:
                raise ValueError(
                    f"{repliker.name} tiene la skill duplicada "
                    f"'{repliker_skill.name}'."
                )

            if not 0 <= repliker_skill.level <= 100:
                raise ValueError(
                    f"Nivel inválido en {repliker.name}: "
                    f"{repliker_skill.name}"
                )

            skill_names.add(normalized_skill)

        codes.add(repliker.code)
        names.add(repliker.name.lower())


validate_web_catalog()
