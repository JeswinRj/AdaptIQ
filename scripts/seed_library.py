"""Seed the knowledge library with legally clean starter content.

  1. Platform-authored notes/formula sheets/examples (our own content).
  2. Wikipedia topic summaries via the REST API (CC-BY-SA 4.0, attributed,
     share-alike recorded) for every curriculum chapter.
  3. Tier-2 link records (NCERT portal, CBSE sample papers): our own short
     description is indexed for search, but results render as links only.

Usage: python scripts/seed_library.py [--no-wiki]
Idempotent-ish: wipes and rebuilds the library DB.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.curriculum import cbse_math
from src.library import pipeline, store
from src.resources.finder import find_resources

P = []  # (title, resource_type, text)

P.append(("Integrals — essential formulas", "formula", """
## Standard integrals
\\[ \\int x^n \\,dx = \\frac{x^{n+1}}{n+1} + C \\quad (n \\neq -1) \\]
\\[ \\int \\frac{1}{x} \\,dx = \\ln|x| + C \\]
\\( \\int e^x \\,dx = e^x + C \\);  \\( \\int a^x \\,dx = \\frac{a^x}{\\ln a} + C \\)
\\( \\int \\sin x \\,dx = -\\cos x + C \\);  \\( \\int \\cos x \\,dx = \\sin x + C \\)
\\( \\int \\sec^2 x \\,dx = \\tan x + C \\);  \\( \\int \\csc^2 x \\,dx = -\\cot x + C \\)
\\( \\int \\frac{dx}{1+x^2} = \\tan^{-1}x + C \\);  \\( \\int \\frac{dx}{\\sqrt{1-x^2}} = \\sin^{-1}x + C \\)

## Integration by parts
\\[ \\int u \\,dv = uv - \\int v \\,du \\]
Choose u by ILATE priority: Inverse trig, Logarithmic, Algebraic,
Trigonometric, Exponential — pick u as the function appearing FIRST in this
list; dv is the rest. Repeat parts if the new integral is still a product.

## Substitution
If the integrand contains \\( f(g(x)) \\cdot g'(x) \\), put \\( t = g(x) \\)
so \\( dt = g'(x)\\,dx \\).
"""))

P.append(("Integration by parts — worked examples", "example", """
## Example 1: integrate x times e to the x
By ILATE, \\( u = x \\) (algebraic beats exponential), \\( dv = e^x\\,dx \\).
Then \\( du = dx \\) and \\( v = e^x \\).
\\[ \\int x e^x \\,dx = x e^x - \\int e^x \\,dx = x e^x - e^x + C = e^x(x-1) + C \\]

## Example 2: integrate x ln x
\\( u = \\ln x \\) (logarithmic first), \\( dv = x\\,dx \\), so
\\( du = \\frac{dx}{x} \\), \\( v = \\frac{x^2}{2} \\).
\\[ \\int x \\ln x \\,dx = \\frac{x^2}{2}\\ln x - \\int \\frac{x^2}{2} \\cdot \\frac{1}{x} \\,dx = \\frac{x^2}{2}\\ln x - \\frac{x^2}{4} + C \\]

## Example 3: integrate ln x (the classic trick)
Write it as \\( \\int (\\ln x)(1) \\,dx \\). Take \\( u = \\ln x \\),
\\( dv = dx \\), so \\( du = \\frac{dx}{x} \\), \\( v = x \\).
\\[ \\int \\ln x \\,dx = x \\ln x - \\int x \\cdot \\frac{1}{x} \\,dx = x \\ln x - x + C \\]
Common mistake: forgetting that dv must include dx.
"""))

P.append(("Integrals — practice questions", "practice", """
## Practice: integration
1. \\( \\int x \\cos x \\,dx \\)  (parts; answer: \\( x \\sin x + \\cos x + C \\))
2. \\( \\int x^2 e^x \\,dx \\)  (parts twice; answer: \\( e^x(x^2 - 2x + 2) + C \\))
3. \\( \\int \\tan^{-1}x \\,dx \\)  (parts with \\( dv = dx \\); answer: \\( x\\tan^{-1}x - \\tfrac{1}{2}\\ln(1+x^2) + C \\))
4. \\( \\int \\frac{2x}{1+x^2} \\,dx \\)  (substitution \\( t = 1+x^2 \\); answer: \\( \\ln(1+x^2) + C \\))
5. Evaluate \\( \\int_0^1 x e^x \\,dx \\).  (answer: 1)
"""))

P.append(("Limits and derivatives — essential formulas", "formula", """
## Standard limits
\\[ \\lim_{x \\to 0} \\frac{\\sin x}{x} = 1 \\qquad \\lim_{x \\to 0} \\frac{1 - \\cos x}{x} = 0 \\]
\\[ \\lim_{x \\to 0} \\frac{e^x - 1}{x} = 1 \\qquad \\lim_{x \\to 0} \\frac{\\ln(1+x)}{x} = 1 \\]
\\[ \\lim_{x \\to a} \\frac{x^n - a^n}{x - a} = n a^{n-1} \\]

## Derivatives from first principles
\\[ f'(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h} \\]

## Standard derivatives
\\( \\frac{d}{dx} x^n = n x^{n-1} \\);  \\( \\frac{d}{dx} \\sin x = \\cos x \\);  \\( \\frac{d}{dx} \\cos x = -\\sin x \\)
\\( \\frac{d}{dx} \\tan x = \\sec^2 x \\);  \\( \\frac{d}{dx} e^x = e^x \\);  \\( \\frac{d}{dx} \\ln x = \\frac{1}{x} \\)
Product rule: \\( (uv)' = u'v + uv' \\).  Quotient rule: \\( \\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2} \\).
Chain rule: \\( \\frac{d}{dx} f(g(x)) = f'(g(x)) \\cdot g'(x) \\).
"""))

P.append(("Differentiation — worked examples", "example", """
## Example 1: differentiate y equals x squared sin x
Product rule: \\( y' = 2x \\sin x + x^2 \\cos x \\).

## Example 2: differentiate a power of a bracket
For \\( y = (3x^2 + 1)^5 \\), chain rule with inner \\( g = 3x^2 + 1 \\):
\\[ y' = 5(3x^2 + 1)^4 \\cdot 6x = 30x(3x^2 + 1)^4 \\]

## Example 3: from first principles, derivative of x squared
\\[ f'(x) = \\lim_{h \\to 0} \\frac{(x+h)^2 - x^2}{h} = \\lim_{h \\to 0} \\frac{2xh + h^2}{h} = \\lim_{h \\to 0} (2x + h) = 2x \\]
"""))

P.append(("Matrices — core notes", "notes", """
## What a matrix is
A matrix is a rectangular arrangement of numbers in rows and columns.
Order m×n means m rows and n columns. Two matrices are equal only when
they have the same order and all corresponding entries are equal.

## Operations
Addition/subtraction: entry-wise, requires the same order.
Scalar multiplication: multiply every entry.
Matrix multiplication: \\( AB \\) exists when columns of A = rows of B; the
\\( (i,j) \\) entry is the dot product of row i of A with column j of B.
In general \\( AB \\neq BA \\) — matrix multiplication is not commutative.

## Special matrices
Identity \\( I \\) (1s on the diagonal): \\( AI = IA = A \\). Zero matrix
\\( O \\). A square matrix is symmetric if \\( A^T = A \\) and
skew-symmetric if \\( A^T = -A \\). Any square matrix splits into a
symmetric part plus a skew part:
\\[ A = \\tfrac{1}{2}(A + A^T) + \\tfrac{1}{2}(A - A^T) \\]
"""))

P.append(("Determinants — essential formulas", "formula", """
## 2x2 and 3x3 determinants
\\[ \\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix} = ad - bc \\]
3x3: expand along any row/column with alternating signs (cofactors).

## Key properties
Swapping two rows changes the sign. Two identical rows make the
determinant 0. Multiplying one row by k multiplies the determinant by k.
\\( \\det(AB) = \\det(A)\\det(B) \\);  \\( \\det(A^T) = \\det(A) \\).

## Inverse and linear systems
\\[ A^{-1} = \\frac{\\operatorname{adj}(A)}{\\det(A)}, \\quad \\det(A) \\neq 0 \\text{ (non-singular)} \\]
Area of a triangle with vertices \\( (x_1,y_1), (x_2,y_2), (x_3,y_3) \\):
\\[ \\tfrac{1}{2} \\left| x_1(y_2 - y_3) + x_2(y_3 - y_1) + x_3(y_1 - y_2) \\right| \\]
"""))

P.append(("Quadratic equations — notes and formulas", "formula", """
## Standard form and roots
\\( ax^2 + bx + c = 0 \\) with \\( a \\neq 0 \\). The quadratic formula:
\\[ x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} \\]
Discriminant \\( D = b^2 - 4ac \\): if \\( D > 0 \\) two real distinct
roots; \\( D = 0 \\) equal real roots; \\( D < 0 \\) complex conjugate roots.

## Sum and product of roots
\\( \\alpha + \\beta = -\\frac{b}{a} \\) and \\( \\alpha\\beta = \\frac{c}{a} \\).
A quadratic with roots \\( \\alpha, \\beta \\) is
\\( x^2 - (\\alpha + \\beta)x + \\alpha\\beta = 0 \\).
"""))

P.append(("Sequences and series — AP and GP formulas", "formula", """
## Arithmetic progression (AP)
nth term: \\( a_n = a + (n-1)d \\).
Sum: \\[ S_n = \\frac{n}{2}\\left[2a + (n-1)d\\right] = \\frac{n}{2}(a + l) \\]

## Geometric progression (GP)
nth term: \\( a_n = a r^{n-1} \\).
Sum: \\( S_n = \\frac{a(r^n - 1)}{r - 1}, \\; r \\neq 1 \\).
Infinite GP with \\( |r| < 1 \\): \\( S_\\infty = \\frac{a}{1 - r} \\).
Arithmetic mean of a, b is \\( \\frac{a+b}{2} \\); geometric mean is
\\( \\sqrt{ab} \\); always \\( \\text{AM} \\geq \\text{GM} \\).
"""))

P.append(("Probability — formulas and one worked example", "formula", """
## Core formulas
\\( P(E) = \\frac{\\text{favourable outcomes}}{\\text{total outcomes}} \\) (equally likely).
\\( P(A \\cup B) = P(A) + P(B) - P(A \\cap B) \\).  \\( P(A') = 1 - P(A) \\).
Conditional probability: \\( P(A \\mid B) = \\frac{P(A \\cap B)}{P(B)} \\).
Independence: \\( P(A \\cap B) = P(A) \\cdot P(B) \\).
Bayes' theorem:
\\[ P(A_i \\mid B) = \\frac{P(B \\mid A_i) P(A_i)}{\\sum_j P(B \\mid A_j) P(A_j)} \\]

## Worked example
Two dice are thrown. Find \\( P(\\text{sum} = 8) \\). Favourable outcomes:
(2,6), (3,5), (4,4), (5,3), (6,2) — that is 5 of 36, so
\\( P = \\frac{5}{36} \\).
"""))

P.append(("Trigonometric identities — quick sheet", "formula", """
## Fundamental identities
\\( \\sin^2\\theta + \\cos^2\\theta = 1 \\);
\\( 1 + \\tan^2\\theta = \\sec^2\\theta \\);
\\( 1 + \\cot^2\\theta = \\csc^2\\theta \\).

## Compound angles
\\[ \\sin(A \\pm B) = \\sin A \\cos B \\pm \\cos A \\sin B \\]
\\[ \\cos(A \\pm B) = \\cos A \\cos B \\mp \\sin A \\sin B \\]
\\[ \\tan(A \\pm B) = \\frac{\\tan A \\pm \\tan B}{1 \\mp \\tan A \\tan B} \\]

## Double angles
\\( \\sin 2A = 2 \\sin A \\cos A \\)
\\( \\cos 2A = \\cos^2 A - \\sin^2 A = 1 - 2\\sin^2 A = 2\\cos^2 A - 1 \\)
\\( \\tan 2A = \\frac{2 \\tan A}{1 - \\tan^2 A} \\)
"""))

P.append(("Relations and functions — quick revision", "summary", """
## Quick revision: functions
A function assigns exactly ONE output to every input in its domain.
One-one (injective): different inputs give different outputs.
Onto (surjective): every element of the codomain is hit.
Bijective = one-one and onto, hence invertible; the inverse reverses the
mapping. Composition: \\( (f \\circ g)(x) = f(g(x)) \\) — apply g first.
The domain of \\( f \\circ g \\) needs \\( g(x) \\) to land inside the
domain of f.
"""))

TIER2 = [
    ("NCERT Mathematics textbooks (official download portal)",
     "https://ncert.nic.in/textbook.php",
     "Official NCERT Class 11 and 12 mathematics textbooks and exemplar "
     "problems: sets, functions, trigonometry, algebra, calculus, limits, "
     "derivatives, integrals, matrices, determinants, vectors, probability, "
     "statistics. Free official PDFs.", "syllabus"),
    ("CBSE sample question papers & marking schemes",
     "https://cbseacademic.nic.in/SQP_CLASSXII.html",
     "Official CBSE sample papers, previous year style questions and marking "
     "schemes for Class 12 mathematics board exams. Exam pattern, question "
     "practice, revision.", "practice"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wiki", action="store_true",
                        help="skip live Wikipedia fetches")
    args = parser.parse_args()

    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
    con = store.connect()

    for title, rtype, text in P:
        r = pipeline.ingest(con, title=title, text=text, source="platform",
                            license="platform", redistribute_allowed=True,
                            resource_type=rtype,
                            attribution="Adapt IQ study team")
        print(f"  platform: {title} ({r['chunks']} chunks)")

    for title, url, desc, rtype in TIER2:
        r = pipeline.ingest(con, title=title, text=desc, source="ncert",
                            url=url, license="linked (all rights reserved)",
                            redistribute_allowed=False, resource_type=rtype,
                            attribution="Official source — opens externally")
        print(f"  tier-2 link: {title}")

    if not args.no_wiki:
        import time
        seen = set()
        for cid, course in cbse_math.COURSES.items():
            for ch in course["chapters"]:
                if ch["wiki"] in seen:
                    continue
                seen.add(ch["wiki"])
                time.sleep(0.6)   # polite fetching, per the architecture doc
                res = find_resources(ch["wiki"], "Mathematics", "basic",
                                     "reading_writing")
                art = res.get("article")
                if not (art and art.get("summary")):
                    continue
                pipeline.ingest(
                    con, title=f"{art['title']} (encyclopedia overview)",
                    text=art["summary"], source="wikipedia",
                    url=art["url"], license="CC-BY-SA-4.0",
                    redistribute_allowed=True, resource_type="reference",
                    attribution=f"From Wikipedia, '{art['title']}', "
                                "CC BY-SA 4.0")
                print(f"  wikipedia: {art['title']}")

    print("Library:", store.stats(con))


if __name__ == "__main__":
    main()
