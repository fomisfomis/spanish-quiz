import anthropic
import json
import os
from datetime import datetime

QUIZ_PROMPT = """You are generating a daily Spanish grammar quiz for an intermediate learner.

Create exactly 20 fresh multiple-choice questions with this exact distribution:
- 4 questions on SER vs ESTAR (mix of basic and tricky cases — e.g. ser/estar + adjective, location of events vs objects, change-of-state)
- 3 questions on Pretérito Indefinido vs Imperfecto (habitual vs completed, interrupted actions, background vs event)
- 2 questions on Usos de QUE (que vs lo que, qué in exclamations, qué in questions, es que, prepositions + que)
- 2 questions on reflexive verbs — "Yo y yo / Yo y tú / Yo y el mundo" patterns (me estreso vs me estresas vs me estresa el tráfico)
- 3 questions on Condicional vs Futuro Simple, including when to use "voy a + infinitivo" vs "iré"
- 3 questions on Subjuntivo Simple (wishes, emotions, negated opinions, impersonal expressions, cuando/en cuanto + future, hypothetical antecedents)
- 2 questions on Imperativo (tú affirmative, negative with subjuntivo, pronoun attachment, ustedes commands)
- 1 question on Futuro Compuesto (completion before future point OR deduction/probability about past events)

Output ONLY a valid JSON array — no markdown, no explanation, no code fences. Raw JSON only. Use this exact structure:
[
  {
    "topic": "SER vs ESTAR",
    "q": "Spanish sentence with ___ as the blank",
    "en": "English translation of the sentence",
    "options": ["option A text", "option B text", "option C text", "option D text"],
    "correct": 1,
    "explanation": "1-2 sentences explaining the rule, not just the answer"
  }
]

The "correct" field is zero-indexed: 0=A, 1=B, 2=C, 3=D.

Requirements:
- Use varied, natural, real-world contexts (work, family, travel, cooking, relationships, daily life)
- Vary the position of the correct answer — avoid putting it always in the same slot
- For SER vs ESTAR, include at least one adjective that changes meaning (rico, listo, aburrido, malo, vivo, etc.)
- Explanations must teach the underlying grammar rule, not just state which answer is correct
- Every sentence must feel fresh — avoid overused textbook examples"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Spanish Quiz — __DATE__</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Georgia', serif; background: #f5f0eb; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .shell { background: #fff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.10); max-width: 680px; width: 100%; overflow: hidden; }
  .header { background: #c0392b; color: #fff; padding: 24px 28px 20px; }
  .header h1 { font-size: 1.4em; font-weight: normal; letter-spacing: 0.02em; }
  .header p { font-size: 0.9em; opacity: 0.85; margin-top: 4px; }
  .progress-bar-wrap { background: rgba(255,255,255,0.25); border-radius: 99px; height: 6px; margin-top: 14px; }
  .progress-bar { background: #fff; height: 6px; border-radius: 99px; transition: width 0.4s ease; width: 0%; }
  .topic-badge { display: inline-block; background: #fef3f2; color: #c0392b; border: 1px solid #f5c6c2; border-radius: 99px; font-size: 0.75em; padding: 3px 10px; margin-bottom: 10px; letter-spacing: 0.03em; text-transform: uppercase; }
  .card { padding: 28px 28px 24px; }
  .q-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .q-num { font-size: 0.82em; color: #999; }
  .question { font-size: 1.13em; color: #1a1a1a; margin-bottom: 6px; line-height: 1.6; }
  .question em { display: block; font-size: 0.85em; color: #666; font-style: italic; margin-top: 4px; }
  .options { margin-top: 18px; display: flex; flex-direction: column; gap: 10px; }
  .option-btn { background: #f8f6f3; border: 2px solid #e8e3dc; border-radius: 10px; padding: 12px 16px; text-align: left; font-size: 0.97em; font-family: inherit; cursor: pointer; transition: background 0.15s, border-color 0.15s, transform 0.1s; color: #222; line-height: 1.4; }
  .option-btn:hover:not(:disabled) { background: #fef3f2; border-color: #c0392b; transform: translateX(3px); }
  .option-btn .letter { font-weight: bold; color: #c0392b; margin-right: 8px; }
  .option-btn.correct { background: #eafaf1; border-color: #27ae60; }
  .option-btn.correct .letter { color: #27ae60; }
  .option-btn.wrong { background: #fdf0ef; border-color: #e74c3c; }
  .option-btn.wrong .letter { color: #e74c3c; }
  .option-btn:disabled { cursor: default; transform: none; }
  .feedback { margin-top: 18px; padding: 14px 16px; border-radius: 10px; font-size: 0.93em; line-height: 1.6; display: none; }
  .feedback.correct-fb { background: #eafaf1; border-left: 4px solid #27ae60; color: #1d6a3a; display: block; }
  .feedback.wrong-fb { background: #fdf0ef; border-left: 4px solid #e74c3c; color: #7b1a14; display: block; }
  .feedback strong { display: block; margin-bottom: 4px; }
  .nav { margin-top: 22px; display: flex; justify-content: flex-end; }
  .next-btn { background: #c0392b; color: #fff; border: none; border-radius: 8px; padding: 10px 24px; font-size: 0.95em; font-family: inherit; cursor: pointer; display: none; transition: background 0.15s; }
  .next-btn:hover { background: #a93226; }
  .results { padding: 36px 28px; text-align: center; display: none; }
  .score-ring { width: 110px; height: 110px; border-radius: 50%; background: conic-gradient(#27ae60 var(--pct), #e8e3dc var(--pct)); display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; font-size: 1.6em; font-weight: bold; color: #1a1a1a; box-shadow: 0 0 0 8px #fff, 0 0 0 10px #e8e3dc; }
  .results h2 { font-size: 1.4em; color: #1a1a1a; margin-bottom: 8px; }
  .results p { color: #666; font-size: 0.95em; margin-bottom: 20px; }
  .restart-btn { background: #c0392b; color: #fff; border: none; border-radius: 8px; padding: 11px 28px; font-size: 1em; font-family: inherit; cursor: pointer; }
  .restart-btn:hover { background: #a93226; }
  .breakdown { margin-top: 24px; text-align: left; border-top: 1px solid #ece8e3; padding-top: 18px; }
  .breakdown h3 { font-size: 0.9em; color: #999; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .bd-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px dashed #ece8e3; font-size: 0.9em; }
  .bd-row:last-child { border-bottom: none; }
  .bd-score { font-weight: bold; color: #c0392b; }
</style>
</head>
<body>
<div class="shell">
  <div class="header">
    <h1>&#127466;&#127480; Spanish Grammar Quiz</h1>
    <p>__DATE__ &nbsp;&middot;&nbsp; 20 questions &nbsp;&middot;&nbsp; Intermediate level</p>
    <div class="progress-bar-wrap"><div class="progress-bar" id="progressBar"></div></div>
  </div>
  <div class="card" id="quizCard">
    <div class="q-meta">
      <span class="topic-badge" id="topicBadge"></span>
      <span class="q-num" id="qNum"></span>
    </div>
    <div class="question" id="questionText"></div>
    <div class="options" id="optionsContainer"></div>
    <div class="feedback" id="feedback"></div>
    <div class="nav"><button class="next-btn" id="nextBtn">Next &rarr;</button></div>
  </div>
  <div class="results" id="resultsScreen">
    <div class="score-ring" id="scoreRing"></div>
    <h2 id="resultsHeading"></h2>
    <p id="resultsSubtext"></p>
    <button class="restart-btn" onclick="restart()">Restart Quiz</button>
    <div class="breakdown" id="breakdown"></div>
  </div>
</div>
<script>
const questions = __QUESTIONS_JSON__;
const letters = ["A","B","C","D"];
let current = 0, score = 0, topicScores = {}, answered = false;
function init() {
  current = 0; score = 0; topicScores = {}; answered = false;
  questions.forEach(q => { topicScores[q.topic] = topicScores[q.topic] || {right:0,total:0}; });
  document.getElementById("resultsScreen").style.display = "none";
  document.getElementById("quizCard").style.display = "";
  showQuestion();
}
function showQuestion() {
  answered = false;
  const q = questions[current];
  document.getElementById("topicBadge").textContent = q.topic;
  document.getElementById("qNum").textContent = `Question ${current+1} of ${questions.length}`;
  document.getElementById("progressBar").style.width = `${(current/questions.length)*100}%`;
  document.getElementById("questionText").innerHTML = q.q + `<em>${q.en}</em>`;
  const container = document.getElementById("optionsContainer");
  container.innerHTML = "";
  q.options.forEach((opt, i) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.innerHTML = `<span class="letter">${letters[i]})</span>${opt}`;
    btn.addEventListener("click", () => selectAnswer(i));
    container.appendChild(btn);
  });
  document.getElementById("feedback").className = "feedback";
  document.getElementById("feedback").innerHTML = "";
  document.getElementById("nextBtn").style.display = "none";
}
function selectAnswer(idx) {
  if (answered) return;
  answered = true;
  const q = questions[current];
  const buttons = document.querySelectorAll(".option-btn");
  buttons.forEach(b => b.disabled = true);
  topicScores[q.topic].total++;
  if (idx === q.correct) {
    buttons[idx].classList.add("correct"); score++; topicScores[q.topic].right++;
    showFeedback(true, q.explanation);
  } else {
    buttons[idx].classList.add("wrong"); buttons[q.correct].classList.add("correct");
    showFeedback(false, q.explanation);
  }
  document.getElementById("nextBtn").style.display = "block";
}
function showFeedback(isCorrect, explanation) {
  const fb = document.getElementById("feedback");
  fb.className = "feedback " + (isCorrect ? "correct-fb" : "wrong-fb");
  fb.innerHTML = (isCorrect ? "&#10003; Correct! &nbsp;" : "&#10007; Not quite. &nbsp;") + explanation;
}
document.getElementById("nextBtn").addEventListener("click", () => {
  current++;
  if (current >= questions.length) showResults(); else showQuestion();
});
function showResults() {
  document.getElementById("quizCard").style.display = "none";
  document.getElementById("progressBar").style.width = "100%";
  document.getElementById("resultsScreen").style.display = "block";
  const pct = Math.round((score/questions.length)*100);
  const ring = document.getElementById("scoreRing");
  ring.style.setProperty("--pct", `${pct}%`);
  ring.textContent = `${score}/${questions.length}`;
  const h = document.getElementById("resultsHeading"), p = document.getElementById("resultsSubtext");
  if (pct >= 90)      { h.textContent="Excellent work!";       p.textContent="Outstanding — you have a strong command of these structures."; }
  else if (pct >= 70) { h.textContent="Good job!";             p.textContent="Solid performance. Review the topics you missed and try again."; }
  else if (pct >= 50) { h.textContent="Keep practicing!";      p.textContent="You're on the right track — focus on the sections below."; }
  else                { h.textContent="More practice needed."; p.textContent="Don't worry — review the explanations and try again."; }
  const bd = document.getElementById("breakdown");
  bd.innerHTML = "<h3>Score by Topic</h3>";
  Object.entries(topicScores).forEach(([topic, s]) => {
    const row = document.createElement("div");
    row.className = "bd-row";
    row.innerHTML = `<span>${topic}</span><span class="bd-score">${s.right}/${s.total}</span>`;
    bd.appendChild(row);
  });
}
function restart() { init(); }
init();
</script>
</body>
</html>"""

def generate_quiz():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%B %d, %Y")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": QUIZ_PROMPT}]
    )
    raw = message.content[0].text.strip()
    questions = json.loads(raw)
    return questions, today

def build_html(questions, today):
    questions_json = json.dumps(questions, ensure_ascii=False, indent=2)
    return HTML_TEMPLATE.replace("__DATE__", today).replace("__QUESTIONS_JSON__", questions_json)

def main():
    print("Calling Claude API to generate quiz...")
    questions, today = generate_quiz()
    print(f"Generated {len(questions)} questions for {today}")
    html = build_html(questions, today)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved index.html")

if __name__ == "__main__":
    main()
