"""
Comprehensive live test suite for quiz answer grading.
Calls the real LLM — no mocks. Covers 60+ cases across subjects and edge conditions.

Usage:
    python scripts/test_quiz_grading.py               # all cases
    python scripts/test_quiz_grading.py --quick       # trivial + 12 LLM cases
    python scripts/test_quiz_grading.py --subject physics
    python scripts/test_quiz_grading.py --category misconception
    python scripts/test_quiz_grading.py --verbose     # print feedback text too
"""
import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.services.quiz_service import _is_trivially_invalid, _llm_grade_and_explain


# ── Case definition ───────────────────────────────────────────────────────────

@dataclass
class Case:
    id: str
    subject: str
    category: str   # trivial | correct | paraphrase | brief | wrong | misconception | vague | off_topic | corner
    question: str
    correct_answer: str
    user_answer: str
    expected: bool
    note: str = ""
    # filled in at runtime
    got: bool = field(default=False, init=False)
    feedback: str = field(default="", init=False)
    elapsed: float = field(default=0.0, init=False)
    passed: bool = field(default=False, init=False)
    error: str = field(default="", init=False)


# ── Test cases ────────────────────────────────────────────────────────────────

CASES: list[Case] = [

    # ── TRIVIAL REJECTION (no LLM — tested via _is_trivially_invalid) ────────
    Case("T01", "trivial", "trivial", "", "", ".", False, "single period"),
    Case("T02", "trivial", "trivial", "", "", "!", False, "single exclamation"),
    Case("T03", "trivial", "trivial", "", "", "?", False, "single question mark"),
    Case("T04", "trivial", "trivial", "", "", "123", False, "digits only"),
    Case("T05", "trivial", "trivial", "", "", "   ", False, "whitespace only"),
    Case("T06", "trivial", "trivial", "", "", "a", False, "single letter"),
    Case("T07", "trivial", "trivial", "", "", "ok", False, "one 2-letter word"),
    Case("T08", "trivial", "trivial", "", "", "no", False, "one 2-letter word"),
    Case("T09", "trivial", "trivial", "", "", "yes", False, "one 3-letter word"),
    Case("T10", "trivial", "trivial", "", "", "?!?", False, "punctuation cluster"),

    # ── PHYSICS ──────────────────────────────────────────────────────────────

    Case("P01", "physics", "correct",
         "A ball thrown horizontally from a cliff and one dropped straight down are released simultaneously. Which hits the ground first?",
         "They land at exactly the same time. Gravity accelerates both downward at 9.8 m/s² regardless of horizontal motion — horizontal velocity has no effect on vertical free-fall.",
         "Both hit at the same time because gravity pulls them down equally and horizontal speed doesn't change vertical acceleration.",
         True, "textbook correct answer"),

    Case("P02", "physics", "paraphrase",
         "A ball thrown horizontally from a cliff and one dropped straight down are released simultaneously. Which hits the ground first?",
         "They land at exactly the same time. Gravity accelerates both downward at 9.8 m/s² regardless of horizontal motion — horizontal velocity has no effect on vertical free-fall.",
         "They reach the ground together — sideways motion doesn't affect how fast gravity pulls something down.",
         True, "correct, casual phrasing"),

    Case("P03", "physics", "wrong",
         "A ball thrown horizontally from a cliff and one dropped straight down are released simultaneously. Which hits the ground first?",
         "They land at exactly the same time. Gravity accelerates both downward at 9.8 m/s² regardless of horizontal motion — horizontal velocity has no effect on vertical free-fall.",
         "The thrown ball lands first because it has greater total velocity so it covers distance faster.",
         False, "common wrong answer"),

    Case("P04", "physics", "correct",
         "A pendulum swings back and forth. How does energy change throughout one complete swing?",
         "Energy converts between kinetic (maximum at the bottom) and gravitational potential (maximum at the top) while total mechanical energy stays constant, assuming no air resistance.",
         "At the bottom it's all kinetic energy; as it rises, kinetic converts to potential. At the top it's all potential again, then back to kinetic on the way down. Total energy is conserved.",
         True, "energy conservation"),

    Case("P05", "physics", "brief",
         "A pendulum swings back and forth. How does energy change throughout one complete swing?",
         "Energy converts between kinetic (maximum at the bottom) and gravitational potential (maximum at the top) while total mechanical energy stays constant, assuming no air resistance.",
         "Kinetic and potential energy trade off while total mechanical energy stays constant.",
         True, "brief but complete"),

    Case("P06", "physics", "misconception",
         "What happens to the mass of an object as it approaches the speed of light?",
         "According to special relativity, the object's relativistic momentum increases without bound as speed approaches c, making it harder to accelerate — but rest mass stays constant. Saying mass increases is a legacy approximation.",
         "The object gets infinitely massive which is why nothing can reach the speed of light.",
         False, "outdated relativistic mass concept — rest mass is invariant"),

    # ── BIOLOGY ──────────────────────────────────────────────────────────────

    Case("B01", "biology", "correct",
         "How does antibiotic resistance develop in a bacterial population over time?",
         "Random mutations occasionally produce bacteria that survive antibiotics. When antibiotics kill susceptible bacteria, the resistant ones survive and reproduce, passing resistance to offspring — natural selection acting on genetic variation.",
         "Bacteria with random mutations that resist the antibiotic survive while others die. They reproduce and pass the resistance on, so the resistant population grows over time.",
         True, "correct evolution explanation"),

    Case("B02", "biology", "misconception",
         "How does antibiotic resistance develop in a bacterial population over time?",
         "Random mutations occasionally produce bacteria that survive antibiotics. When antibiotics kill susceptible bacteria, the resistant ones survive and reproduce, passing resistance to offspring — natural selection acting on genetic variation.",
         "Bacteria sense the antibiotic and deliberately mutate themselves to become resistant so they can survive.",
         False, "Lamarckian misconception — bacteria don't direct their mutations"),

    Case("B03", "biology", "correct",
         "Why is DNA replication described as semi-conservative?",
         "Each new DNA molecule retains one original strand as a template and builds a new complementary strand alongside it — so every copy is half old, half new.",
         "One original strand is kept in each daughter molecule, paired with a newly synthesized complementary strand — hence half old, half new.",
         True, "semi-conservative replication"),

    Case("B04", "biology", "wrong",
         "Why is DNA replication described as semi-conservative?",
         "Each new DNA molecule retains one original strand as a template and builds a new complementary strand alongside it — so every copy is half old, half new.",
         "The DNA splits completely and each half replicates itself from scratch to form two fully new copies.",
         False, "describes conservative replication, not semi-conservative"),

    Case("B05", "biology", "vague",
         "How does the immune system distinguish self from non-self?",
         "T cells are trained in the thymus to tolerate the body's own proteins (self-antigens) and attack foreign ones. MHC molecules display protein fragments on cell surfaces for T cells to inspect.",
         "The immune system somehow recognises what belongs to the body and attacks anything foreign.",
         False, "no mechanism — just restates the question"),

    # ── CHEMISTRY ────────────────────────────────────────────────────────────

    Case("C01", "chemistry", "correct",
         "Why does ice float on water when most solids sink in their liquid form?",
         "Water molecules form hydrogen bonds arranged in a hexagonal crystal lattice when frozen, spacing them further apart than in liquid water — making ice less dense and so it floats.",
         "Freezing forces water molecules into a crystalline lattice via hydrogen bonds, which spreads them out more than in the liquid state, making ice less dense.",
         True, "correct hydrogen-bond explanation"),

    Case("C02", "chemistry", "vague",
         "Why does ice float on water when most solids sink in their liquid form?",
         "Water molecules form hydrogen bonds arranged in a hexagonal crystal lattice when frozen, spacing them further apart than in liquid water — making ice less dense and so it floats.",
         "Ice is lighter than water.",
         False, "circular — doesn't explain WHY density differs"),

    Case("C03", "chemistry", "wrong",
         "Why does ice float on water when most solids sink in their liquid form?",
         "Water molecules form hydrogen bonds arranged in a hexagonal crystal lattice when frozen, spacing them further apart than in liquid water — making ice less dense and so it floats.",
         "When water freezes it contracts and traps air bubbles inside, which makes it buoyant.",
         False, "water expands when freezing, not contracts"),

    Case("C04", "chemistry", "correct",
         "What happens at the molecular level when you dissolve table salt in water?",
         "Water molecules, being polar, attract the Na⁺ and Cl⁻ ions and surround them — a process called solvation or hydration. The ionic lattice dissociates into free ions dispersed throughout the solution.",
         "The polar water molecules pull apart the ionic lattice, surrounding each sodium and chloride ion individually — the salt dissociates into free ions in solution.",
         True, "ionic dissociation"),

    # ── MATHEMATICS ──────────────────────────────────────────────────────────

    Case("M01", "mathematics", "correct",
         "What does the derivative of a function represent geometrically at any point on its curve?",
         "The derivative gives the slope of the tangent line to the curve at that point — the instantaneous rate at which the function is changing.",
         "It's the slope of the tangent line at that point, showing how fast the function is rising or falling instantaneously.",
         True, "derivative as slope of tangent"),

    Case("M02", "mathematics", "wrong",
         "What does the derivative of a function represent geometrically at any point on its curve?",
         "The derivative gives the slope of the tangent line to the curve at that point — the instantaneous rate at which the function is changing.",
         "The derivative gives the area under the curve up to that point.",
         False, "confuses derivative with integral"),

    Case("M03", "mathematics", "correct",
         "You flip a fair coin ten times and get heads every time. What is the probability of heads on the eleventh flip?",
         "Exactly 50%. Each flip is independent — past outcomes have no influence on future ones. Believing otherwise is the gambler's fallacy.",
         "Still 50% — each flip is independent so the run of heads has no effect on the next outcome.",
         True, "independence of coin flips"),

    Case("M04", "mathematics", "misconception",
         "You flip a fair coin ten times and get heads every time. What is the probability of heads on the eleventh flip?",
         "Exactly 50%. Each flip is independent — past outcomes have no influence on future ones. Believing otherwise is the gambler's fallacy.",
         "Less than 50% because tails is overdue — the law of averages means it must balance out soon.",
         False, "gambler's fallacy"),

    Case("M05", "mathematics", "paraphrase",
         "Why does multiplying two negative numbers produce a positive result?",
         "It follows from requiring arithmetic to stay consistent: if positive × positive = positive, then to maintain the distributive law, negative × negative must also equal positive. It's a necessary consequence of algebraic consistency, not just a rule.",
         "Negating twice returns you to the original direction — the mathematical rules require it to stay consistent with the distributive property.",
         True, "paraphrase of algebraic consistency argument"),

    # ── HISTORY ──────────────────────────────────────────────────────────────

    Case("H01", "history", "correct",
         "What role did the alliance system play in turning a regional dispute into World War I?",
         "The network of mutual defense treaties meant Austria-Hungary's declaration of war on Serbia triggered automatic obligations pulling in Germany, Russia, France, and Britain within weeks — a chain reaction built into the alliance structure.",
         "Treaty obligations meant each country that declared war automatically dragged its allies in — a small Balkan conflict cascaded into a continental war because of the interconnected alliance network.",
         True, "alliance chain reaction"),

    Case("H02", "history", "vague",
         "What role did the alliance system play in turning a regional dispute into World War I?",
         "The network of mutual defense treaties meant Austria-Hungary's declaration of war on Serbia triggered automatic obligations pulling in Germany, Russia, France, and Britain within weeks — a chain reaction built into the alliance structure.",
         "The alliances made the war bigger.",
         False, "restates the conclusion with no mechanism"),

    Case("H03", "history", "correct",
         "Why did the Industrial Revolution begin in Britain rather than other parts of Europe in the 18th century?",
         "Britain had a unique convergence: abundant coal and iron deposits, a colonial empire for raw materials and export markets, relatively stable property rights encouraging investment, and a culture of practical tinkering and patent protection.",
         "A rare combination of coal and iron resources, colonial trade networks, legal protections for inventors, and a practical engineering culture — no other country had all of these at once.",
         True, "multiple convergent factors"),

    Case("H04", "history", "wrong",
         "Why did the Industrial Revolution begin in Britain rather than other parts of Europe in the 18th century?",
         "Britain had a unique convergence: abundant coal and iron deposits, a colonial empire for raw materials and export markets, relatively stable property rights encouraging investment, and a culture of practical tinkering and patent protection.",
         "Britain started the Industrial Revolution because its workers were smarter and more hardworking than those in other countries.",
         False, "nationalistic non-explanation, ignores structural factors"),

    # ── COMPUTER SCIENCE ─────────────────────────────────────────────────────

    Case("CS01", "computer_science", "correct",
         "What does O(n²) time complexity mean in practice as input size grows?",
         "The number of operations scales with the square of input size — doubling the input roughly quadruples the work. For large inputs this becomes very slow compared to O(n) or O(n log n) algorithms.",
         "If you double the input, the work roughly quadruples — operations grow proportional to n squared, so it slows down fast for large inputs.",
         True, "quadratic scaling explained"),

    Case("CS02", "computer_science", "wrong",
         "What does O(n²) time complexity mean in practice as input size grows?",
         "The number of operations scales with the square of input size — doubling the input roughly quadruples the work. For large inputs this becomes very slow compared to O(n) or O(n log n) algorithms.",
         "The algorithm takes exactly n squared milliseconds to run.",
         False, "confuses asymptotic complexity with literal runtime"),

    Case("CS03", "computer_science", "correct",
         "What is the fundamental behavioral difference between a stack and a queue data structure?",
         "A stack is LIFO — last item added is first removed, like a stack of plates. A queue is FIFO — first item added is first removed, like a queue of people.",
         "Stack is last-in first-out; queue is first-in first-out.",
         True, "LIFO vs FIFO"),

    Case("CS04", "computer_science", "correct",
         "What problem does a hash table solve compared to a simple array when searching for a specific element?",
         "An array requires scanning up to every element to find a match — O(n). A hash table maps keys to positions via a hash function, allowing near O(1) average lookup regardless of how many items are stored.",
         "Instead of scanning every element, a hash function computes the storage location directly — so lookup is nearly constant time instead of linear.",
         True, "O(1) lookup via hashing"),

    # ── ECONOMICS ────────────────────────────────────────────────────────────

    Case("E01", "economics", "correct",
         "You skip a concert to study for an exam. How would an economist define the opportunity cost of studying?",
         "The opportunity cost is the value of the next-best alternative you gave up — in this case, the enjoyment and experience of the concert, not just the ticket price.",
         "The opportunity cost is the value of the concert experience you sacrificed — the best alternative you gave up.",
         True, "opportunity cost correctly defined"),

    Case("E02", "economics", "wrong",
         "You skip a concert to study for an exam. How would an economist define the opportunity cost of studying?",
         "The opportunity cost is the value of the next-best alternative you gave up — in this case, the enjoyment and experience of the concert, not just the ticket price.",
         "The opportunity cost is the cost of your textbooks.",
         False, "confuses opportunity cost with direct costs"),

    Case("E03", "economics", "correct",
         "A drought halves a country's wheat harvest. What happens to bread prices and why, using supply and demand?",
         "Supply falls sharply while demand stays roughly constant — fewer loaves available for the same number of buyers drives prices up until the market reaches a new equilibrium.",
         "Supply drops while demand stays the same, so prices rise — there's less bread available but just as many people wanting it.",
         True, "supply shock → price rise"),

    # ── PSYCHOLOGY ───────────────────────────────────────────────────────────

    Case("PS01", "psychology", "correct",
         "Why do people tend to favour news sources that agree with their existing political views?",
         "Confirmation bias leads people to seek out information that confirms existing beliefs and avoid contradictory evidence — it's cognitively easier and emotionally comfortable to have beliefs validated.",
         "Confirmation bias — people unconsciously gravitate toward information that validates what they already believe and discount sources that challenge them.",
         True, "confirmation bias correctly named and explained"),

    Case("PS02", "psychology", "vague",
         "Why do people tend to favour news sources that agree with their existing political views?",
         "Confirmation bias leads people to seek out information that confirms existing beliefs and avoid contradictory evidence — it's cognitively easier and emotionally comfortable to have beliefs validated.",
         "People like things they already agree with.",
         False, "correct intuition but no psychological mechanism"),

    Case("PS03", "psychology", "correct",
         "How does classical conditioning explain why a dog salivates when it hears a bell that was previously rung before meals?",
         "The bell (initially neutral) was repeatedly paired with food (which naturally triggers salivation). The dog learned to associate bell with food — now the bell alone triggers salivation as a conditioned response.",
         "Repeated pairing of the bell with food taught the dog to associate the two — eventually the bell alone produces the salivation response previously triggered only by food.",
         True, "classical conditioning"),

    # ── PHILOSOPHY ───────────────────────────────────────────────────────────

    Case("PH01", "philosophy", "correct",
         "What ethical tension is the trolley problem designed to highlight?",
         "It pits two major ethical frameworks against each other: consequentialism, which judges actions by their outcomes (save the most lives), and deontology, which holds that certain actions are inherently wrong regardless of consequences (actively causing death is impermissible).",
         "It contrasts consequentialist ethics — maximise lives saved — with deontological ethics — actively causing a death is wrong regardless of consequences.",
         True, "consequentialism vs deontology"),

    Case("PH02", "philosophy", "off_topic",
         "What ethical tension is the trolley problem designed to highlight?",
         "It pits consequentialism (actively divert the trolley, kill one to save five) against deontology (actively causing someone's death is wrong regardless of outcomes).",
         "Trolleys are a form of public transport and modern trams have much better braking systems than in the past.",
         False, "completely off-topic answer"),

    Case("PH03", "philosophy", "correct",
         "What does Plato's allegory of the cave say about ordinary human perception and knowledge?",
         "People are like prisoners watching shadows on a cave wall and mistaking them for reality. True knowledge requires turning away from appearances toward the Forms — philosophical reasoning is the process of emerging from the cave.",
         "Most people mistake the shadows of reality — appearances, opinions, sense data — for truth itself. Real knowledge means going beyond what we perceive toward the deeper forms or principles.",
         True, "allegory of the cave"),

    # ── ASTRONOMY ────────────────────────────────────────────────────────────

    Case("A01", "astronomy", "correct",
         "Why do we always see the same face of the Moon from Earth?",
         "The Moon's rotation period equals its orbital period — it completes exactly one rotation per orbit, called tidal locking. Earth's gravity gradually slowed the Moon's spin to this state over billions of years.",
         "The Moon rotates once per orbit due to tidal locking — its spin and orbital period are synchronised, so the same hemisphere always faces Earth.",
         True, "tidal locking"),

    Case("A02", "astronomy", "misconception",
         "Why do we always see the same face of the Moon from Earth?",
         "The Moon's rotation period equals its orbital period — it completes exactly one rotation per orbit, called tidal locking. Earth's gravity gradually slowed the Moon's spin to this state over billions of years.",
         "The Moon doesn't rotate at all — it stays perfectly still while the Earth moves around the Sun.",
         False, "moon does rotate, just at the same rate as its orbit"),

    Case("A03", "astronomy", "correct",
         "Why can't light escape from inside a black hole's event horizon?",
         "The gravitational field is so intense that the escape velocity exceeds the speed of light. Inside the event horizon, all possible paths through spacetime curve inward — even light cannot travel along a path that leads outward.",
         "Inside the event horizon, gravity is so extreme that the escape velocity exceeds c — the speed of light — so light cannot travel fast enough to escape and all paths curve inward.",
         True, "escape velocity exceeds c"),

    # ── CLIMATE & ENVIRONMENT ─────────────────────────────────────────────────

    Case("CL01", "climate", "correct",
         "A planet identical to Earth exists but with no greenhouse gases. How would its surface temperature compare to Earth's?",
         "Average surface temperature would be around -18°C rather than Earth's +15°C. Without greenhouse gases absorbing and re-emitting outgoing infrared radiation, nearly all solar energy would escape back to space.",
         "Around -18°C — without greenhouse gases trapping outgoing infrared radiation, nearly all the heat from the sun would escape back to space.",
         True, "greenhouse effect temperature"),

    Case("CL02", "climate", "paraphrase",
         "A planet identical to Earth exists but with no greenhouse gases. How would its surface temperature compare to Earth's?",
         "Average surface temperature would be around -18°C rather than Earth's +15°C. Without greenhouse gases absorbing and re-emitting outgoing infrared radiation, nearly all solar energy would escape back to space.",
         "Far colder — roughly -18°C — because there would be nothing to prevent heat from radiating away into space after arriving from the sun.",
         True, "paraphrase with same core insight"),

    Case("CL03", "climate", "misconception",
         "If we stopped all fossil fuel emissions today, what would happen to Earth's climate over the next century?",
         "Warming would slow and eventually halt as CO₂ concentrations stabilise, but temperatures would not immediately drop — CO₂ already in the atmosphere persists for centuries, so some committed warming is already locked in.",
         "Temperatures would drop back to pre-industrial levels within a few years because the atmosphere would quickly clean itself once we stop polluting.",
         False, "CO₂ persists for centuries — committed warming is locked in"),

    # ── QUANTUM PHYSICS (user's examples) ────────────────────────────────────

    Case("Q01", "quantum", "misconception",
         "Two electrons are entangled, and one is measured. How does this affect the other, and what does it suggest about their connection?",
         "Measuring one instantly determines the correlated state of the other, but no information travels between them — the outcomes are random and you cannot use entanglement to send a signal faster than light.",
         "The other electron instantly takes on a correlated state, proving that information or influence can travel faster than light between them.",
         False, "FTL communication is the key misconception — entanglement does not allow it"),

    Case("Q02", "quantum", "correct",
         "Two electrons are entangled, and one is measured. How does this affect the other, and what does it suggest about their connection?",
         "Measuring one instantly determines the correlated state of the other, but no information travels between them — the outcomes are random and you cannot use entanglement to send a signal faster than light.",
         "The other electron's state is instantly determined — they're correlated regardless of distance. But no usable information travels between them because the measurement outcomes are random, so no faster-than-light communication is possible.",
         True, "correct: notes correlation AND explicitly rules out FTL"),

    Case("Q03", "quantum", "correct",
         "If an electron behaves as both a particle and a wave, how does this wave nature enable quantum tunnelling through a barrier?",
         "The electron's wavefunction extends into and through barriers. There is a non-zero probability amplitude on the far side, meaning the electron can appear there even without enough classical energy to overcome the barrier.",
         "As a wave, the electron's probability function extends through the barrier — there's a non-zero chance of finding the electron on the other side, so it can tunnel through without needing enough energy to climb over.",
         True, "tunnelling via wavefunction penetration"),

    Case("Q04", "quantum", "correct",
         "How does measurement cause a quantum particle in superposition to 'choose' a definite state, and what does this imply?",
         "Measurement causes the wavefunction to collapse from a superposition of possibilities to a single definite outcome. This implies that quantum properties are not determined until observed — reality at the quantum scale is probabilistic until measurement.",
         "The wavefunction collapses from all possibilities to one definite state at the moment of measurement — suggesting quantum reality is inherently probabilistic and the act of observation determines outcomes.",
         True, "wavefunction collapse correctly described"),

    # ── MUSIC ─────────────────────────────────────────────────────────────────

    Case("MU01", "music", "correct",
         "Why does the same note played on a piano sound distinctly different from the same note on a violin?",
         "Each instrument produces a unique mix of overtones (harmonics) above the fundamental frequency. This pattern of harmonics — called timbre or tone colour — is what makes instruments sound distinct at identical pitch and volume.",
         "The harmonic overtones each instrument adds on top of the fundamental frequency differ — this unique spectral fingerprint is called timbre.",
         True, "timbre via harmonics"),

    Case("MU02", "music", "wrong",
         "Why does the same note played on a piano sound distinctly different from the same note on a violin?",
         "Each instrument produces a unique mix of overtones (harmonics) above the fundamental frequency. This pattern of harmonics — called timbre or tone colour — is what makes instruments sound distinct at identical pitch and volume.",
         "Because they are made of different materials — wood versus metal strings and hammers — which changes the pitch they can produce.",
         False, "materials affect tone but not pitch; answer doesn't explain timbre"),

    # ── MEDICINE ─────────────────────────────────────────────────────────────

    Case("ME01", "medicine", "correct",
         "How does a vaccine prepare the immune system without causing the actual disease?",
         "Vaccines introduce a harmless form of the pathogen — weakened, inactivated, or key surface proteins — causing the immune system to mount a response and produce memory B and T cells that can rapidly fight the real pathogen if encountered later.",
         "They expose the immune system to a safe version of the pathogen — weakened, killed, or just its proteins — so memory cells are created that can mount a fast response if the real infection appears.",
         True, "memory cell formation"),

    Case("ME02", "medicine", "misconception",
         "How does a vaccine prepare the immune system without causing the actual disease?",
         "Vaccines introduce a harmless form of the pathogen — weakened, inactivated, or key surface proteins — causing the immune system to mount a response and produce memory B and T cells that can rapidly fight the real pathogen if encountered later.",
         "Vaccines inject a live dose of the disease directly into the bloodstream so you get mildly sick and your body builds immunity the natural way.",
         False, "most vaccines use inactivated/attenuated/subunit forms, not live pathogen into blood"),

    # ── CORNER CASES ─────────────────────────────────────────────────────────

    Case("X01", "corner", "corner",
         "Why does a ball thrown horizontally fall at the same rate as one dropped straight down?",
         "Both experience the same gravitational acceleration of 9.8 m/s² downward. Horizontal velocity has no effect on vertical free-fall.",
         "Gravty acts equaly on boht balls so tehy fall at te same rate — horizntal speed dosnt affect vertical acelertion.",
         True, "correct meaning despite heavy typos"),

    Case("X02", "corner", "corner",
         "Why does ice float on liquid water?",
         "Water molecules form hydrogen bonds in a hexagonal crystal lattice when frozen, spacing molecules further apart than in liquid form — making ice less dense.",
         (
             "This is actually a fascinating question. When water freezes, the hydrogen bonds between water molecules "
             "force them into a rigid hexagonal lattice structure. This lattice is actually more spacious than the "
             "disordered arrangement of molecules in liquid water — the molecules are held further apart. Because "
             "density equals mass divided by volume, and the same mass of molecules now occupies a greater volume, "
             "ice has lower density than liquid water. Lower density means it floats. This is why lakes freeze from "
             "the top down rather than from the bottom up, which is critical for aquatic life surviving winters. "
             "It's one of water's most unusual properties, arising directly from the geometry of the H₂O molecule "
             "and the angle of its covalent bonds."
         ),
         True, "very long but correct answer"),

    Case("X03", "corner", "corner",
         "How does antibiotic resistance develop in a bacterial population?",
         "Random mutations produce bacteria that survive antibiotics. These reproduce while susceptible ones die — natural selection acting on genetic variation.",
         "Bacteria are single-celled prokaryotic organisms that reproduce via binary fission and have existed on Earth for over 3.5 billion years.",
         False, "technically true facts that don't answer the question"),

    Case("X04", "corner", "corner",
         "What does the derivative of a function represent geometrically?",
         "The slope of the tangent line to the curve at that point — the instantaneous rate of change.",
         "I think it might be related to the shape of the graph and maybe how fast it changes at some point possibly.",
         False, "hedged non-answer with no real content"),

    Case("X05", "corner", "corner",
         "A ball thrown horizontally and one dropped vertically — which hits the ground first?",
         "They hit simultaneously. Gravity acts the same downward on both regardless of horizontal motion.",
         "दोनों एक साथ जमीन पर पहुँचते हैं क्योंकि गुरुत्वाकर्षण दोनों पर समान रूप से कार्य करता है।",
         True, "correct answer in Hindi — LLM should recognise the concept"),
]


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_trivial(case: Case) -> None:
    t0 = time.perf_counter()
    result = _is_trivially_invalid(case.user_answer)
    case.elapsed = time.perf_counter() - t0
    # trivially invalid → is_correct=False; trivially valid → need LLM (shouldn't appear here)
    case.got = not result  # _is_trivially_invalid=True means answer rejected (False)
    # For trivial cases expected is always False, so:
    case.got = False if result else True
    case.passed = (case.got == case.expected)


async def run_llm(case: Case) -> None:
    t0 = time.perf_counter()
    try:
        is_correct, feedback = await _llm_grade_and_explain(
            case.question, case.correct_answer, case.user_answer
        )
        case.got = is_correct
        case.feedback = feedback
        case.passed = (case.got == case.expected)
    except Exception as e:
        case.error = str(e)
        case.passed = False
    finally:
        case.elapsed = time.perf_counter() - t0


# ── Display helpers ───────────────────────────────────────────────────────────

CATEGORY_ORDER = [
    "trivial", "correct", "paraphrase", "brief",
    "wrong", "misconception", "vague", "off_topic", "corner",
]

SUBJECT_EMOJI = {
    "trivial":          "⚡",
    "physics":          "🔭",
    "biology":          "🧬",
    "chemistry":        "⚗️",
    "mathematics":      "📐",
    "history":          "📜",
    "computer_science": "💻",
    "economics":        "📊",
    "psychology":       "🧠",
    "philosophy":       "🏛️",
    "astronomy":        "🌌",
    "climate":          "🌍",
    "quantum":          "⚛️",
    "music":            "🎵",
    "medicine":         "💉",
    "corner":           "🔀",
}


def print_case(c: Case, verbose: bool) -> None:
    mark = "✓" if c.passed else "✗"
    exp  = "CORRECT" if c.expected else "WRONG  "
    got  = "CORRECT" if c.got     else "WRONG  "
    match = "   " if c.passed else "≠EXP"
    emoji = SUBJECT_EMOJI.get(c.subject, "•")
    ms = f"{c.elapsed*1000:.0f}ms"

    if c.category == "trivial":
        label = f"trivial_invalid={not c.got}"
        print(f"  {mark} [{c.id}] {label:<28} {ms:>6}  {c.note}")
    else:
        print(f"  {mark} [{c.id}] {emoji} {c.subject:<16} {c.category:<14} "
              f"exp={exp}  got={got}  {match}  {ms:>6}  {c.note}")
        if c.error:
            print(f"       ERROR: {c.error}")
        if verbose and c.feedback:
            wrapped = c.feedback[:160] + ("…" if len(c.feedback) > 160 else "")
            print(f"       feedback: {wrapped}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser(description="Live quiz grading test suite")
    parser.add_argument("--quick", action="store_true",
                        help="Trivial tests + 12 LLM cases only (~30s)")
    parser.add_argument("--subject",
                        help="Filter to a specific subject (e.g. physics, biology, quantum)")
    parser.add_argument("--category",
                        help="Filter to a category (correct, wrong, misconception, corner, …)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print LLM feedback text for each case")
    args = parser.parse_args()

    # Select cases
    cases = list(CASES)
    if args.subject:
        cases = [c for c in cases if c.subject == args.subject]
    if args.category:
        cases = [c for c in cases if c.category == args.category]

    # Quick mode: all trivials + one case per LLM category across a variety of subjects
    QUICK_IDS = {
        "T01","T02","T03","T04","T05","T06","T07","T08","T09","T10",
        "P01","P03","B01","B02","C01","M03","M04","H01","CS03",
        "Q01","Q02","CL03","X01","X03",
    }
    if args.quick:
        cases = [c for c in cases if c.id in QUICK_IDS]

    trivials = [c for c in cases if c.category == "trivial"]
    llm_cases = [c for c in cases if c.category != "trivial"]

    print("=" * 70)
    print(f"ECALT Quiz Grading Test Suite  —  {len(trivials)} trivial + {len(llm_cases)} LLM cases")
    if args.quick:
        print("Mode: QUICK")
    print("=" * 70)

    total_start = time.perf_counter()

    # ── Trivial tests (sync, instant) ─────────────────────────────────────────
    if trivials:
        print(f"\n── Trivial rejection ({len(trivials)} cases — no LLM) " + "─" * 20)
        for c in trivials:
            await run_trivial(c)
            print_case(c, args.verbose)

    # ── LLM tests (async, real AI) ────────────────────────────────────────────
    if llm_cases:
        # Group by subject for cleaner output
        by_subject: dict[str, list[Case]] = {}
        for c in llm_cases:
            by_subject.setdefault(c.subject, []).append(c)

        for subject, group in by_subject.items():
            emoji = SUBJECT_EMOJI.get(subject, "•")
            print(f"\n── {emoji} {subject.upper().replace('_',' ')} ({len(group)} cases) " + "─" * 20)
            for c in group:
                await run_llm(c)
                print_case(c, args.verbose)

    # ── Summary ───────────────────────────────────────────────────────────────
    all_cases = trivials + llm_cases
    total_elapsed = time.perf_counter() - total_start

    passed = [c for c in all_cases if c.passed]
    failed = [c for c in all_cases if not c.passed]

    # Category breakdown
    cat_stats: dict[str, tuple[int, int]] = {}
    for c in all_cases:
        p, t = cat_stats.get(c.category, (0, 0))
        cat_stats[c.category] = (p + (1 if c.passed else 0), t + 1)

    print(f"\n{'=' * 70}")
    print(f"Results: {len(passed)}/{len(all_cases)} passed in {total_elapsed:.1f}s")
    print()
    print(f"  {'Category':<16} {'Pass':>5} {'Total':>6}")
    print(f"  {'─' * 16} {'─' * 5} {'─' * 6}")
    for cat in CATEGORY_ORDER:
        if cat not in cat_stats:
            continue
        p, t = cat_stats[cat]
        bar = "✓" * p + "✗" * (t - p)
        print(f"  {cat:<16} {p:>5}/{t:<5}  {bar}")

    if failed:
        print(f"\n  Failed cases: {', '.join(c.id for c in failed)}")
        for c in failed:
            exp = "CORRECT" if c.expected else "WRONG"
            got = "CORRECT" if c.got else "WRONG"
            print(f"    [{c.id}] {c.subject}/{c.category} — expected {exp}, got {got}"
                  + (f" — {c.note}" if c.note else ""))
    else:
        print("\n  All cases passed.")

    print("=" * 70)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
