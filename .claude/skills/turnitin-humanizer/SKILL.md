---
name: turnitin-humanizer
description: Audit existing draft text for AI plagiarism markers, uniform syntax, and Turnitin flags.
---
# Turnitin & AI Detection Stripper
Scan the existing text and rewrite flagged passages using these rules:
1. REMOVE AI SIGNATURE WORDS: Delete "delve", "pivotal", "testament", "intricate", "multifaceted", "underscores", "realm", "spearhead", "furthermore", "groundbreaking", "seamlessly".
2. BREAK UNIFORM SENTENCE LENGTH: AI drafts default to 15-20 word compound sentences. Rewrite so sentences alternate between 4-8 words (direct declarations) and 25-30 words (complex explanations).
3. ADD EXPERIMENTAL FRICTION: Insert project-specific hardware constraints, parameter tuning choices, and trial-and-error observations.
4. SHIFT VOICE: Change passive AI summaries ("It was observed that...") to direct active voice ("We observed---
name: turnitin-humanizer
description: Audit existing LaTeX manuscript files for AI detection flags, uniform syntax, and Turnitin signatures while preserving full LaTeX and mathematical integrity.
---

# LaTeX & Turnitin Humanization Protocol

When processing `.tex` files in `paper/`:

## 1. AI Vocabulary & Stylistic Removal
- **Banned AI Buzzwords:** Systematically remove and rephrase the following words and phrases: "delve", "pivotal", "testament", "intricate", "multifaceted", "underscores", "realm", "spearhead", "furthermore", "groundbreaking", "seamlessly", "holistic", "crucial", "tapestry", "demystify", "paramount", "leverage", "beacon", "it is worth noting".
- **Transition Diversification:** Replace mechanical transitions ("Moreover", "In addition", "Consequently") with direct logical progression or domain-specific connectors.

## 2. Sentence Structure & Burstiness (Perplexity Tuning)
- **Vary Sentence Length:** Force a high variance in sentence length. Alternate between short, punchy statements (5–9 words) and long, highly technical explanatory sentences (25–35 words).
- **Active Academic Voice:** Convert passive AI phrasing ("It was observed that the model achieved high accuracy") into direct active voice ("We recorded an accuracy of X%" or "Quantization reduced overall inference latency").

## 3. Grounding with Operational & Experimental Friction
- **Inject Real Hardware Details:** Integrate specific project details from `uav-split-perception` (e.g., VRAM limits on edge GPUs, INT4/FP16 quantization trade-offs, spatial resolution constraints, thermal throttling risks).
- **Document Trial-and-Error:** Explain *why* specific choices were made (e.g., "We selected dynamic gradient accumulation over larger batch sizes due to on-board UAV memory saturation").

## 4. STRICT LATEX INTEGRITY PRESERVATION
- **Protect Equations:** NEVER modify math environments (`\begin{equation}`, `\[...\]`, `$inline$`), tensor symbols, or variable notation.
- **Protect Citations & Cross-References:** Keep all `\cite{...}`, `\ref{...}`, `\label{...}`, and `\citeauthor{...}` tags completely intact.
- **Maintain Document Structure:** Preserve all LaTeX structural commands (`\section{}`, `\subsection{}`, `\begin{table}`, `\begin{figure}`).
- **Escape Special Characters:** Ensure `%`, `_`, `#`, and `&` are properly escaped outside code environments.

## 5. Section-by-Section Focus Rules
- **Abstract & Intro:** Prioritize high sentence length variance and strong, direct motivation.
- **Methodology & System Model:** Ensure equations match the text explanations without altering math symbols.
- **Results & Experiments:** Explicitly connect text descriptions to the raw metrics found in `runs/` and `experiments/`....").