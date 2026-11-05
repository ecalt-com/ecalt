"""A short, real .docx for the full-loop demo (#22): "The Solar System".
Usage: python e2e/make_demo_docx.py <out_path>  (python-docx from the backend venv)"""
import sys
from docx import Document

out = sys.argv[1] if len(sys.argv) > 1 else "solar-system.docx"
doc = Document()
doc.add_heading("The Solar System", level=0)
doc.add_heading("The Sun and its family", level=1)
doc.add_paragraph(
    "The Solar System is the Sun and everything that travels around it. The Sun is a star: a huge ball "
    "of hot gas that makes its own light and heat. Its gravity holds eight planets, their moons, dwarf "
    "planets such as Pluto, and millions of smaller rocks called asteroids and comets in orbit.")
doc.add_heading("Rocky planets and gas giants", level=1)
doc.add_paragraph(
    "The four planets closest to the Sun - Mercury, Venus, Earth and Mars - are small and rocky. The four "
    "outer planets - Jupiter, Saturn, Uranus and Neptune - are giants made mostly of gas and ice. Jupiter "
    "is the largest planet; it is so big that all the other planets could fit inside it.")
doc.add_heading("Why planets orbit", level=1)
doc.add_paragraph(
    "A planet moves forward very fast while the Sun's gravity pulls it inward. The two together bend its "
    "path into an orbit, a curved loop around the Sun. Planets closer to the Sun move faster and have "
    "shorter years: Mercury goes round in 88 days, while Neptune takes about 165 Earth years.")
doc.save(out)
print(out)
