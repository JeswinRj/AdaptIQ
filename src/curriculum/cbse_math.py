"""CBSE Class 11 & 12 Mathematics curriculum (NCERT chapter structure).

Chapter lists follow the current NCERT textbooks (rationalised syllabus).
Each chapter belongs to a DOMAIN — the six nodes of the skill web — and
carries its key topics plus per-chapter resource links (NCERT official
textbook portal, Khan Academy's CBSE-aligned courses, YouTube searches).
The live Wikipedia article for a chapter is fetched by src/resources/finder.

Only Mathematics 11/12 for now by design; more courses slot in later as
additional modules with the same shape.
"""
from urllib.parse import quote_plus

DOMAINS = ["Algebra", "Functions & Graphs", "Trigonometry", "Calculus",
           "Geometry & Vectors", "Statistics & Probability"]

COURSES = {
    "cbse-11-math": {
        "title": "Mathematics — Class 11 (CBSE)",
        "short": "Class 11 Maths",
        "khan": "https://www.khanacademy.org/math/in-in-grade-11-ncert",
        "ncert": "https://ncert.nic.in/textbook.php?kemh1=0-14",
        "chapters": [
            {"name": "Sets", "domain": "Algebra",
             "topics": ["Sets and representations", "Subsets", "Venn diagrams",
                        "Union, intersection, complement"], "wiki": "Set (mathematics)"},
            {"name": "Relations and Functions", "domain": "Functions & Graphs",
             "topics": ["Cartesian product", "Relations", "Functions",
                        "Domain and range"], "wiki": "Function (mathematics)"},
            {"name": "Trigonometric Functions", "domain": "Trigonometry",
             "topics": ["Radian measure", "Unit circle", "Graphs of sin/cos/tan",
                        "Trigonometric identities"], "wiki": "Trigonometric functions"},
            {"name": "Complex Numbers and Quadratic Equations", "domain": "Algebra",
             "topics": ["Imaginary unit i", "Algebra of complex numbers",
                        "Argand plane", "Quadratic roots"], "wiki": "Complex number"},
            {"name": "Linear Inequalities", "domain": "Algebra",
             "topics": ["Inequalities in one variable", "Graphical solutions"],
             "wiki": "Inequality (mathematics)"},
            {"name": "Permutations and Combinations", "domain": "Statistics & Probability",
             "topics": ["Fundamental counting principle", "Factorials",
                        "nPr and nCr"], "wiki": "Permutation"},
            {"name": "Binomial Theorem", "domain": "Algebra",
             "topics": ["Expansion of (a+b)^n", "Pascal's triangle",
                        "General term"], "wiki": "Binomial theorem"},
            {"name": "Sequences and Series", "domain": "Algebra",
             "topics": ["Arithmetic progression", "Geometric progression",
                        "Sum formulas"], "wiki": "Sequence"},
            {"name": "Straight Lines", "domain": "Geometry & Vectors",
             "topics": ["Slope", "Forms of line equations",
                        "Distance from a point"], "wiki": "Line (geometry)"},
            {"name": "Conic Sections", "domain": "Geometry & Vectors",
             "topics": ["Circle", "Parabola", "Ellipse", "Hyperbola"],
             "wiki": "Conic section"},
            {"name": "Introduction to Three Dimensional Geometry", "domain": "Geometry & Vectors",
             "topics": ["Coordinate axes in 3D", "Distance between points"],
             "wiki": "Three-dimensional space"},
            {"name": "Limits and Derivatives", "domain": "Calculus",
             "topics": ["Intuitive idea of limits", "Derivative as rate of change",
                        "First principles"], "wiki": "Limit (mathematics)"},
            {"name": "Statistics", "domain": "Statistics & Probability",
             "topics": ["Mean deviation", "Variance", "Standard deviation"],
             "wiki": "Statistics"},
            {"name": "Probability", "domain": "Statistics & Probability",
             "topics": ["Random experiments", "Events", "Axiomatic probability"],
             "wiki": "Probability"},
        ],
    },
    "cbse-12-math": {
        "title": "Mathematics — Class 12 (CBSE)",
        "short": "Class 12 Maths",
        "khan": "https://www.khanacademy.org/math/in-in-grade-12-ncert",
        "ncert": "https://ncert.nic.in/textbook.php?lemh1=0-6",
        "chapters": [
            {"name": "Relations and Functions", "domain": "Functions & Graphs",
             "topics": ["Types of relations", "One-one and onto functions",
                        "Composite functions", "Invertible functions"],
             "wiki": "Function (mathematics)"},
            {"name": "Inverse Trigonometric Functions", "domain": "Trigonometry",
             "topics": ["Principal values", "Graphs", "Properties"],
             "wiki": "Inverse trigonometric functions"},
            {"name": "Matrices", "domain": "Algebra",
             "topics": ["Types of matrices", "Matrix operations", "Transpose",
                        "Invertible matrices"], "wiki": "Matrix (mathematics)"},
            {"name": "Determinants", "domain": "Algebra",
             "topics": ["Determinant of a matrix", "Adjoint and inverse",
                        "Solving linear systems"], "wiki": "Determinant"},
            {"name": "Continuity and Differentiability", "domain": "Calculus",
             "topics": ["Continuity", "Chain rule", "Implicit differentiation",
                        "Logarithmic differentiation"], "wiki": "Continuous function"},
            {"name": "Application of Derivatives", "domain": "Calculus",
             "topics": ["Rate of change", "Increasing/decreasing functions",
                        "Maxima and minima"], "wiki": "Derivative"},
            {"name": "Integrals", "domain": "Calculus",
             "topics": ["Antiderivatives", "Substitution", "Partial fractions",
                        "Definite integrals"], "wiki": "Integral"},
            {"name": "Application of Integrals", "domain": "Calculus",
             "topics": ["Area under curves", "Area between curves"],
             "wiki": "Integral"},
            {"name": "Differential Equations", "domain": "Calculus",
             "topics": ["Order and degree", "Separable equations",
                        "Linear first-order equations"], "wiki": "Differential equation"},
            {"name": "Vector Algebra", "domain": "Geometry & Vectors",
             "topics": ["Vectors and scalars", "Dot product", "Cross product"],
             "wiki": "Euclidean vector"},
            {"name": "Three Dimensional Geometry", "domain": "Geometry & Vectors",
             "topics": ["Direction cosines", "Lines in space", "Angle between lines"],
             "wiki": "Three-dimensional space"},
            {"name": "Linear Programming", "domain": "Algebra",
             "topics": ["Constraints", "Feasible region", "Optimisation"],
             "wiki": "Linear programming"},
            {"name": "Probability", "domain": "Statistics & Probability",
             "topics": ["Conditional probability", "Bayes' theorem",
                        "Random variables"], "wiki": "Probability"},
        ],
    },
}


def get_course(course_id: str) -> dict:
    return COURSES[course_id]


def chapter_links(course_id: str, chapter: dict, modality: str) -> list:
    """Curated resource links for one chapter, ordered by modality."""
    course = COURSES[course_id]
    grade = "11" if "11" in course_id else "12"
    q = quote_plus(f"class {grade} maths {chapter['name']}")
    links = [
        ("NCERT textbook (official, free)", course["ncert"]),
        (f"Khan Academy — {course['short']} course", course["khan"]),
        (f"YouTube — {chapter['name']} one-shot lessons",
         f"https://www.youtube.com/results?search_query={q}+one+shot"),
    ]
    if modality == "visual":
        links.insert(2, (f"YouTube — {chapter['name']} animated/visualised",
                         f"https://www.youtube.com/results?search_query={q}+visualization+animated"))
    elif modality == "kinesthetic":
        links.insert(2, (f"GeoGebra interactive — {chapter['name']}",
                         f"https://www.geogebra.org/search/{quote_plus(chapter['name'])}"))
    elif modality == "auditory":
        links.insert(2, (f"YouTube — {chapter['name']} explained (lecture)",
                         f"https://www.youtube.com/results?search_query={q}+explained+lecture"))
    else:
        links.insert(2, (f"NCERT exemplar problems ({chapter['name']})",
                         "https://ncert.nic.in/exemplar-problems.php"))
    links.append((f"Practice paper search — {chapter['name']}",
                  f"https://www.google.com/search?q={q}+important+questions+pdf"))
    return links


def domain_progress(course_id: str, completed_chapters: list) -> dict:
    """Percent mastery per skill-web domain from completed chapter indexes."""
    chapters = COURSES[course_id]["chapters"]
    totals = {d: 0 for d in DOMAINS}
    done = {d: 0 for d in DOMAINS}
    for i, ch in enumerate(chapters):
        totals[ch["domain"]] += 1
        if i in completed_chapters:
            done[ch["domain"]] += 1
    return {d: (round(done[d] / totals[d] * 100) if totals[d] else 0)
            for d in DOMAINS}
