"""
Theophysics Text Normalization Layer
=====================================
Converts Theophysics-specific symbols, equations, and notation to spoken form.
Designed to work with the TTS pipeline for the 188 Axiom Framework.

Author: David Lowe / Theophysics Project
"""

import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Optional AI fallback for equations not in master file
try:
    from ai_math_translator import AIMathTranslator
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


DEFAULT_OPTIONS = {
    "remove_frontmatter": True,
    "remove_code_blocks": True,
    "remove_images": True,
    "remove_structural_index_block": True,
    "remove_media_callout_block": True,
    "process_tables": True,
    "table_mode": "narrative",  # narrative | strip | keep
    "process_latex_blocks": True,
    "math_label_enabled": True,
    "math_label_text": "... Mathematically:",
    "unknown_math_policy": "drop",  # drop | placeholder | keep
    "remove_markdown_links": False,
    "remove_wiki_links": False,
    "remove_raw_urls": True,
    "dedupe_link_text": True,
    "remove_hashtags": True,
    "remove_inline_code": True,
    "remove_callouts": True,
    "remove_highlights": True,
    "remove_footnotes": True,
    "remove_comments": True,
    "remove_html_tags": True,
    "replace_comparison_symbols": True,
    "comparison_symbol_map": {
        "<": "less than",
        ">": "greater than",
    },
    "remove_markdown": True,
    "normalize_symbols": True,
    "normalize_greek": True,
    "normalize_special_letters": True,
    "normalize_subscripts": True,
    "normalize_superscripts": True,
    "normalize_axiom_refs": True,
    "normalize_law_refs": True,
    "optimize_numbers": True,
    "dedupe_lines": True,
    "clean_whitespace": True,
}


class TheophysicsNormalizer:
    """
    Normalizes Theophysics-specific notation for TTS output.
    Handles: Greek letters, chi-field symbols, equations, axiom references, laws.
    """

    def __init__(
        self,
        ai_translator: Optional["AIMathTranslator"] = None,
        options: Optional[Dict] = None,
    ):
        self.ai_translator = ai_translator
        self.options = self._build_options(options)

        self.greek_lower = {
            "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma", "\u03b4": "delta",
            "\u03b5": "epsilon", "\u03b6": "zeta", "\u03b7": "eta", "\u03b8": "theta",
            "\u03b9": "iota", "\u03ba": "kappa", "\u03bb": "lambda", "\u03bc": "mu",
            "\u03bd": "nu", "\u03be": "xi", "\u03bf": "omicron", "\u03c0": "pi",
            "\u03c1": "rho", "\u03c3": "sigma", "\u03c4": "tau", "\u03c5": "upsilon",
            "\u03c6": "phi", "\u03c7": "chi", "\u03c8": "psi", "\u03c9": "omega",
            "\u03c2": "sigma",
        }
        self.greek_upper = {
            "\u0391": "Alpha", "\u0392": "Beta", "\u0393": "Gamma", "\u0394": "Delta",
            "\u0395": "Epsilon", "\u0396": "Zeta", "\u0397": "Eta", "\u0398": "Theta",
            "\u0399": "Iota", "\u039a": "Kappa", "\u039b": "Lambda", "\u039c": "Mu",
            "\u039d": "Nu", "\u039e": "Xi", "\u039f": "Omicron", "\u03a0": "Pi",
            "\u03a1": "Rho", "\u03a3": "Sigma", "\u03a4": "Tau", "\u03a5": "Upsilon",
            "\u03a6": "Phi", "\u03a7": "Chi", "\u03a8": "Psi", "\u03a9": "Omega",
        }

        self.theophysics_symbols = {
            "chi-field": "chi field",
            "\u221e": "infinity",
            "\u2192": "approaches",
            "\u2190": "comes from",
            "\u2194": "is equivalent to",
            "\u21d2": "implies",
            "\u21d4": "if and only if",
            "\u2248": "approximately equals",
            "\u2261": "is identically equal to",
            "\u2260": "is not equal to",
            "\u2264": "is less than or equal to",
            "\u2265": "is greater than or equal to",
            "\u2103": "degrees Celsius",
            "\u2109": "degrees Fahrenheit",
            "\u00b0": "degrees",
        }

        self.special_letters = {
            "\U0001d530": "s",
            "\u210f": "h-bar",
            "\u2112": "L",
            "\u2202": "partial",
        }

        self.subscripts = {
            "\u2080": " sub zero ", "\u2081": " sub one ", "\u2082": " sub two ",
            "\u2083": " sub three ", "\u2084": " sub four ", "\u2085": " sub five ",
            "\u2086": " sub six ", "\u2087": " sub seven ", "\u2088": " sub eight ",
            "\u2089": " sub nine ", "\u2090": " sub a ", "\u2091": " sub e ",
            "\u2092": " sub o ", "\u2093": " sub x ", "\u1d62": " sub i ",
            "\u2c7c": " sub j ", "\u2096": " sub k ", "\u2097": " sub l ",
            "\u2098": " sub m ", "\u2099": " sub n ", "\u209a": " sub p ",
            "\u209b": " sub s ", "\u209c": " sub t ",
        }

        self.superscripts = {
            "\u2070": " to the zero ", "\u00b9": " to the one ",
            "\u00b2": " squared ", "\u00b3": " cubed ",
            "\u2074": " to the fourth ", "\u2075": " to the fifth ",
            "\u2076": " to the sixth ", "\u2077": " to the seventh ",
            "\u2078": " to the eighth ", "\u2079": " to the ninth ",
            "\u207f": " to the n ", "\u2071": " to the i ",
        }

        self.axiom_pattern = re.compile(r"\bA(\d{1,3})\b")
        self.law_pattern = re.compile(r"\bL(\d{1,2})\b")

        self.math_translations = self.load_math_translations()
        self.bridge_translations = self.load_bridge_translations()

        # Unicode math patterns (for docs without $ delimiters)
        self.unicode_math_patterns = [
            # Field equations with box operator
            (re.compile(r"□χ\s*\+\s*m²χ.*?=.*?(?:\n|$)", re.UNICODE), "The chi field equation: the d'Alembertian of chi plus mass term plus self-interaction plus gravitational coupling equals the grace source plus witness field squared."),
            (re.compile(r"□Φ\s*\+\s*m.*?Φ.*?=.*?(?:\n|$)", re.UNICODE), "The witness field equation: the d'Alembertian of Phi plus mass term plus chi-Phi coupling equals the witness source."),
            # Einstein equations
            (re.compile(r"G[_μν]+\s*\+\s*ξ.*?=\s*8πG.*?T", re.UNICODE), "The modified Einstein equations with chi-field coupling to spacetime curvature."),
            (re.compile(r"G_?eff\s*=\s*G\s*/.*?ξχ²", re.UNICODE), "The effective gravitational constant equals Newton's G divided by one plus the chi-squared correction."),
            # Will current
            (re.compile(r"W[_μ]+\s*=.*?Φ[̄ˉ].*?γ.*?Φ", re.UNICODE), "The will current W-mu equals Phi-bar gamma-mu Phi — the Noether current of the witness field."),
            (re.compile(r"∇[_μ]+\s*W[μ^]+\s*=\s*0", re.UNICODE), "The divergence of the will current equals zero — will is conserved."),
            # Coherence functional
            (re.compile(r"χ\[Ω\]\s*=\s*∫\s*∏.*?X[_i]+.*?dμ", re.UNICODE), "The coherence functional chi of Omega equals the integral of the product of all ten normalized variables."),
            # Coherence evolution
            (re.compile(r"dC/dt\s*=\s*G\(C\)\s*[−-]\s*S\(C\)\s*\+\s*Φ\(C\)", re.UNICODE), "The coherence evolution equation: the rate of change of coherence equals grace growth minus entropic decay plus witness coupling."),
            # Shannon entropy
            (re.compile(r"H\s*=\s*[−-]Σ\s*p[_i]*\s*log\s*p", re.UNICODE), "Shannon entropy: H equals negative sum of p-i log p-i — the unique information measure."),
            # Normalization map
            (re.compile(r"X[_i]+\s*=.*?H[_i]+.*?H.*?max.*?H.*?min", re.UNICODE), "The normalization map: X-i equals H-i minus H-i-min divided by H-i-max minus H-i-min, mapping each variable to the zero-to-one range."),
            # Hubble gradient
            (re.compile(r"H[₀0]\(z\)\s*=\s*67\.4\s*\+", re.UNICODE), "The Hubble gradient: H-naught of z equals 67.4 plus 6.1 divided by one plus z over z-t to the alpha — predicting how the expansion rate varies with redshift."),
            # LLC
            (re.compile(r"𝓛.*?LLC.*?=.*?χ\(t\)", re.UNICODE), "The Lowe Coherence Lagrangian: coherence-weighted kinetic energy minus entropic potential."),
            # Product veto
            (re.compile(r"If\s+any\s+X[_i]*\s*=\s*0.*?χ\s*=\s*0", re.UNICODE | re.IGNORECASE), "The veto property: if any single variable equals zero, total coherence equals zero — no variable can compensate for another."),
            # Moral energy
            (re.compile(r"d[ℰE]/dt\s*=\s*[−-]α\s*D\(t\)\s*\+\s*β\s*C", re.UNICODE), "The moral energy evolution: rate of change equals negative alpha times disorder plus beta times coherence with Christ."),
            # Grace constant
            (re.compile(r"lim.*?S\s*→\s*S.*?max.*?C\(t\)\s*=\s*C.*?grace", re.UNICODE), "The grace constant: even at maximum entropy, coherence never reaches exactly zero — an irreducible residue of grace persists."),
        ]

    def _build_options(self, options: Optional[Dict]) -> Dict:
        merged = dict(DEFAULT_OPTIONS)
        if not options:
            return merged

        for key, value in options.items():
            if key == "comparison_symbol_map" and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return merged

    def _enabled(self, key: str) -> bool:
        return bool(self.options.get(key, False))

    def remove_code_blocks(self, text: str) -> str:
        text = re.sub(r"```[\w]*\n[\s\S]*?```", "", text)
        text = re.sub(r"~~~[\w]*\n[\s\S]*?~~~", "", text)
        return text

    def remove_images(self, text: str) -> str:
        text = re.sub(r"!\[\[([^\]]+)\]\]", "", text)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)
        text = re.sub(r"<img[^>]*>", "", text)
        return text

    def remove_inline_code(self, text: str) -> str:
        return re.sub(r"`([^`]+)`", r"\1", text)

    def remove_hashtags(self, text: str) -> str:
        text = re.sub(r"(?:\s+#\w+)+$", "", text, flags=re.MULTILINE)
        text = re.sub(r"#(\w+)", r"\1", text)
        return text

    def remove_markdown_links(self, text: str) -> str:
        keep_text = bool(self.options.get("keep_markdown_link_text", True))
        if keep_text:
            return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        return re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)

    def remove_wiki_links(self, text: str) -> str:
        keep_text = bool(self.options.get("keep_wiki_link_text", True))
        if keep_text:
            text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
            text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
            return text
        text = re.sub(r"\[\[[^\]]+\]\]", "", text)
        return text

    def remove_raw_urls(self, text: str) -> str:
        text = re.sub(r"https?://[^\s]+", "", text)
        text = re.sub(r"ftp://[^\s]+", "", text)
        text = re.sub(r"www\.[^\s]+", "", text)
        text = re.sub(r"\S+@\S+\.\S+", "", text)
        return text

    def dedupe_lines(self, text: str) -> str:
        lines = text.splitlines()
        out = []
        prev = ""
        for line in lines:
            norm = re.sub(r"\s+", " ", line).strip().lower()
            if norm and norm == prev:
                continue
            out.append(line)
            prev = norm
        return "\n".join(out)

    def dedupe_immediate_phrases(self, text: str) -> str:
        pattern = re.compile(r"\b([A-Za-z][A-Za-z0-9\- ]{1,60})\s+\1\b", re.IGNORECASE)
        prev = None
        cur = text
        while prev != cur:
            prev = cur
            cur = pattern.sub(r"\1", cur)
        return cur

    def remove_callouts(self, text: str) -> str:
        # Keep callout content, remove Obsidian marker prefix.
        return re.sub(r"^\s*>\s*\[![^\]]+\]\s*", "", text, flags=re.MULTILINE)

    def remove_named_callout_blocks(self, text: str) -> str:
        """
        Remove metadata-heavy callout blocks that should not be narrated in TTS:
        - Structural Index callout ([!abstract]- ... Structural Index ...)
        - Media callout ([!info]- ... Listen, Watch and Download ...)
        - Explicit MEDIA_CALLOUT markers if present
        """
        lines = text.splitlines()
        out: List[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            lower = line.lower()

            if self._enabled("remove_media_callout_block") and "<!-- media_callout_start -->" in lower:
                i += 1
                while i < len(lines) and "<!-- media_callout_end -->" not in lines[i].lower():
                    i += 1
                if i < len(lines):
                    i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                continue

            if (
                self._enabled("remove_structural_index_block")
                and re.match(r"^\s*>\s*\[!abstract\]", line, flags=re.IGNORECASE)
                and "structural index" in lower
            ):
                i += 1
                while i < len(lines):
                    candidate = lines[i]
                    if re.match(r"^\s*>", candidate):
                        i += 1
                        continue
                    if not candidate.strip():
                        i += 1
                        continue
                    break
                continue

            if (
                self._enabled("remove_media_callout_block")
                and re.match(r"^\s*>\s*\[!info\]", line, flags=re.IGNORECASE)
                and (
                    "listen, watch and download" in lower
                    or "listen, watch & download" in lower
                )
            ):
                i += 1
                while i < len(lines):
                    candidate = lines[i]
                    if re.match(r"^\s*>", candidate):
                        i += 1
                        continue
                    if not candidate.strip():
                        i += 1
                        continue
                    break
                continue

            out.append(line)
            i += 1

        return "\n".join(out)

    def remove_footnotes(self, text: str) -> str:
        # Remove definition lines first so labels are still present for matching.
        text = re.sub(r"^\[\^[^\]]+\]:.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s{2,}.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[\^[^\]]+\]", "", text)
        return text

    def remove_comments(self, text: str) -> str:
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        # Keep %%tts ... %% blocks; remove other Obsidian comments.
        text = re.sub(r"%%(?!tts).*?%%", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def remove_html_tags(self, text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text)

    def replace_comparison_symbols(self, text: str) -> str:
        sym = self.options.get("comparison_symbol_map", {})

        lt_word = sym.get("<", "less than")
        gt_word = sym.get(">", "greater than")

        text = re.sub(r"(?<=\S)\s*<\s*(?=\S)", f" {lt_word} ", text)
        text = re.sub(r"(?<=\S)\s*>\s*(?=\S)", f" {gt_word} ", text)
        return text

    def load_math_translations(self) -> Dict[str, str]:
        mapping = {}
        script_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(script_dir)

        # Prefer FIXED over original MASTER
        filenames = [
            "MATH_TRANSLATION_MASTER_FIXED.xlsx",
            "MATH_TRANSLATION_MASTER.xlsx",
        ]
        candidates = []
        for fn in filenames:
            candidates.extend([
                fn,
                os.path.join(script_dir, fn),
                os.path.join(parent_dir, "config", fn),
                os.path.join(parent_dir, fn),
            ])

        file_path = None
        for path in candidates:
            if os.path.exists(path):
                file_path = path
                break

        if not file_path:
            print("[WARN] MATH_TRANSLATION_MASTER.xlsx not found. Equations will be skipped.")
            return mapping

        try:
            print(f"[INFO] Loading math translations from: {file_path}")
            df = pd.read_excel(file_path)

            latex_col = "latex"
            audio_col = "tts_audio"

            if latex_col not in df.columns or audio_col not in df.columns:
                print(f"[ERROR] Master file missing required columns: {latex_col}, {audio_col}")
                return mapping

            for _, row in df.iterrows():
                latex = str(row[latex_col]).strip()
                audio = str(row[audio_col]).strip()
                latex_norm = re.sub(r"\s+", " ", latex)
                latex_no_space = re.sub(r"\s+", "", latex)

                if latex and audio and audio.lower() != "nan":
                    mapping[latex] = audio
                    mapping[latex_norm] = audio
                    mapping[latex_no_space] = audio

            print(f"[INFO] Loaded {len(mapping)} math translation pairs from master file.")

        except Exception as e:
            print(f"[ERROR] Failed to load math translations: {e}")

        return mapping

    def load_bridge_translations(self) -> List[Tuple[str, str]]:
        """Load the Theology-Physics Bridge table for concept-level narration."""
        bridges: List[Tuple[str, str]] = []
        script_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(script_dir)
        candidates = [
            "THEOLOGY_PHYSICS_BRIDGE.xlsx",
            os.path.join(script_dir, "THEOLOGY_PHYSICS_BRIDGE.xlsx"),
            os.path.join(parent_dir, "config", "THEOLOGY_PHYSICS_BRIDGE.xlsx"),
        ]

        file_path = None
        for path in candidates:
            if os.path.exists(path):
                file_path = path
                break

        if not file_path:
            return bridges

        try:
            df = pd.read_excel(file_path)
            for _, row in df.iterrows():
                physics = str(row.get("physics_concept", "")).strip()
                plain = str(row.get("plain_english", "")).strip()
                if physics and plain and plain.lower() != "nan":
                    bridges.append((physics, plain))
            print(f"[INFO] Loaded {len(bridges)} bridge translations.")
        except Exception as e:
            print(f"[ERROR] Failed to load bridge translations: {e}")

        return bridges

    def process_unicode_math(self, text: str) -> str:
        """Detect and translate equations rendered as Unicode (no $ delimiters)."""
        for pattern, spoken in self.unicode_math_patterns:
            text = pattern.sub(f" ... Mathematically: {spoken} ... ", text)
        return text

    def apply_bridge_concepts(self, text: str) -> str:
        """Apply theology-physics bridge translations to prose."""
        for physics_concept, plain_english in self.bridge_translations:
            # Only replace if the concept appears as a recognizable phrase
            # Use word boundaries to avoid partial matches
            escaped = re.escape(physics_concept)
            pattern = re.compile(rf"(?i)\b{escaped}\b")
            if pattern.search(text):
                text = pattern.sub(plain_english, text, count=1)
        return text

    def find_equation_translation(self, equation: str) -> str:
        clean_eq = equation.replace("$", "").strip()
        normalized = re.sub(r"\s+", " ", clean_eq)
        no_spaces = re.sub(r"\s+", "", clean_eq)

        if clean_eq in self.math_translations:
            return self.math_translations[clean_eq]
        if normalized in self.math_translations:
            return self.math_translations[normalized]
        if no_spaces in self.math_translations:
            return self.math_translations[no_spaces]

        return self.generate_equation_fallback(clean_eq)

    def generate_equation_fallback(self, equation: str) -> str:
        eq = equation.lower()
        if "=" in eq:
            if "delta" in eq or "\u2202" in eq:
                return "a change or difference equation"
            if "int" in eq or "\u222b" in eq:
                return "an integral equation"
            if "sum" in eq or "\u2211" in eq:
                return "a summation equation"
            return "an equation"
        return "a complex mathematical equation"

    def process_latex_blocks(self, text: str) -> str:
        unknown_policy = str(self.options.get("unknown_math_policy", "drop")).lower()
        label_enabled = bool(self.options.get("math_label_enabled", True))
        label_text = str(self.options.get("math_label_text", "Math translation:")).strip()

        def replace_match(match):
            content = match.group(0)
            inner = match.group(1) if match.groups() else match.group(0)
            clean_inner = inner.replace("$", "").strip()
            is_display_math = content.startswith("$$") and content.endswith("$$")

            if re.match(r"^\s*\$?\d+[\d,\.]*\s*$", clean_inner):
                return content

            if len(clean_inner.strip()) <= 1:
                single_char = clean_inner.strip().lower()
                if single_char in self.greek_lower:
                    return f" {self.greek_lower[single_char]} "
                return content

            translation = self.find_equation_translation(clean_inner)
            if translation:
                if label_enabled:
                    return f" {label_text} {translation}. "
                return f" {translation} "

            if unknown_policy == "keep":
                return content
            if unknown_policy == "placeholder":
                return " mathematical expression "
            if is_display_math:
                return ""
            return ""

        text = re.sub(r"\$\$(.*?)\$\$", replace_match, text, flags=re.DOTALL)
        text = re.sub(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$", replace_match, text)
        return text

    def detect_markdown_table(self, text: str) -> List[Tuple[int, int, str]]:
        tables = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if "|" in line and (line.startswith("|") or line.count("|") >= 2):
                table_start = i
                table_lines = [lines[i]]
                i += 1

                while i < len(lines):
                    candidate = lines[i].strip()
                    if "|" in candidate and (candidate.startswith("|") or candidate.count("|") >= 2):
                        table_lines.append(lines[i])
                        i += 1
                    elif candidate == "":
                        if i + 1 < len(lines) and "|" in lines[i + 1]:
                            table_lines.append(lines[i])
                            i += 1
                        else:
                            break
                    else:
                        break

                if len(table_lines) >= 2:
                    tables.append((table_start, i, "\n".join(table_lines)))
            else:
                i += 1

        return tables

    def _split_table_row(self, line: str) -> List[str]:
        row = line.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [cell.strip() for cell in row.split("|")]

    def parse_markdown_table(self, table_text: str) -> Tuple[List[str], List[List[str]]]:
        lines = [line for line in table_text.split("\n") if line.strip()]
        if not lines:
            return [], []

        headers = self._split_table_row(lines[0])

        data_start = 1
        if len(lines) > 1 and re.match(r"^[\s\|:\-]+$", lines[1].strip()):
            data_start = 2

        rows: List[List[str]] = []
        for line in lines[data_start:]:
            if "|" not in line:
                continue
            cells = self._split_table_row(line)
            if not any(cells):
                continue
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            rows.append(cells[: len(headers)] if headers else cells)

        return headers, rows

    def table_to_narrative(self, table_text: str) -> str:
        headers, rows = self.parse_markdown_table(table_text)
        if not rows:
            return ""

        # Classify table type and route to best narrator
        table_type = self._classify_table(headers, rows)

        if table_type == "time_series":
            return self._narrate_time_series(headers, rows)
        elif table_type == "entity":
            return self._narrate_entity(headers, rows)
        elif table_type == "comparison":
            return self._narrate_comparison(headers, rows)
        else:
            return self._narrate_generic(headers, rows)

    def _classify_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Detect table type from headers and content."""
        lower_headers = [h.lower() for h in headers]

        # Time series: has year/date/period column
        time_keywords = {"year", "date", "period", "decade", "century", "epoch",
                         "time", "month", "quarter", "era", "age", "phase"}
        if any(any(kw in h for kw in time_keywords) for h in lower_headers):
            return "time_series"

        # Comparison: first column is a dimension/category, rest are entities
        comparison_keywords = {"dimension", "feature", "property", "aspect",
                               "metric", "criterion", "vs", "versus"}
        if any(any(kw in h for kw in comparison_keywords) for h in lower_headers):
            return "comparison"

        # Entity: narrow table (2-5 cols), first col looks like names/labels
        if len(headers) <= 5 and len(rows) >= 2:
            first_col_values = [r[0] for r in rows if r[0]]
            if all(not v.replace(".", "").replace("-", "").isdigit() for v in first_col_values[:5]):
                return "entity"

        return "generic"

    def _is_skip_column(self, header: str) -> bool:
        """Detect columns that add noise to narration (IDs, indices, etc.)."""
        skip = {"id", "uid", "uuid", "index", "idx", "#", "row", "no", "no."}
        return header.strip().lower() in skip

    def _narrate_entity(self, headers: List[str], rows: List[List[str]]) -> str:
        """Natural language for entity tables (Name | Score | Rank)."""
        narratives: List[str] = []
        # Use first column as the entity name
        name_col = 0
        attr_cols = [i for i in range(1, len(headers))
                     if not self._is_skip_column(headers[i])]

        for row in rows:
            name = row[name_col] if row[name_col] else "Unknown"
            parts = []
            for ci in attr_cols:
                val = row[ci] if ci < len(row) else ""
                if not val:
                    continue
                header = headers[ci]
                parts.append(f"{header} {val}")
            if parts:
                narratives.append(f"{name}: {', '.join(parts)}.")

        if len(narratives) > 12:
            return self._compress_narration(headers, rows, narratives)
        return "\n\n".join(narratives)

    def _narrate_time_series(self, headers: List[str], rows: List[List[str]]) -> str:
        """Natural language for time-indexed tables."""
        narratives: List[str] = []
        attr_cols = [i for i in range(1, len(headers))
                     if not self._is_skip_column(headers[i])]

        for row in rows:
            time_val = row[0] if row[0] else "Unknown period"
            parts = []
            for ci in attr_cols:
                val = row[ci] if ci < len(row) else ""
                if not val:
                    continue
                parts.append(f"{headers[ci]} was {val}")
            if parts:
                narratives.append(f"In {time_val}, {', '.join(parts)}.")

        if len(narratives) > 12:
            return self._compress_narration(headers, rows, narratives)
        return "\n\n".join(narratives)

    def _narrate_comparison(self, headers: List[str], rows: List[List[str]]) -> str:
        """Natural language for comparison tables (Dimension | SystemA | SystemB)."""
        narratives: List[str] = []

        for row in rows:
            dimension = row[0] if row[0] else "Unknown"
            comparisons = []
            for ci in range(1, len(headers)):
                val = row[ci] if ci < len(row) else ""
                if not val:
                    continue
                comparisons.append(f"{headers[ci]}: {val}")
            if comparisons:
                narratives.append(f"For {dimension}, {'; '.join(comparisons)}.")

        if len(narratives) > 12:
            return self._compress_narration(headers, rows, narratives)
        return "\n\n".join(narratives)

    def _narrate_generic(self, headers: List[str], rows: List[List[str]]) -> str:
        """Fallback: improved version of the original row-by-row narrator."""
        narratives: List[str] = []
        active_headers = [(i, h) for i, h in enumerate(headers)
                          if not self._is_skip_column(h)]

        for idx, row in enumerate(rows, start=1):
            parts = []
            for col_idx, header in active_headers:
                cell = row[col_idx] if col_idx < len(row) else ""
                if not cell:
                    continue
                parts.append(f"{header} is {cell}")
            if parts:
                narratives.append(f"Row {idx}: " + "; ".join(parts) + ".")

        if len(narratives) > 12:
            return self._compress_narration(headers, rows, narratives)
        return "\n\n".join(narratives)

    def _compress_narration(self, headers: List[str], rows: List[List[str]],
                            full_narratives: List[str]) -> str:
        """For large tables: summary + first/last rows + count."""
        total = len(rows)
        col_count = len([h for h in headers if not self._is_skip_column(h)])
        summary = f"This table contains {total} entries across {col_count} columns."

        # Show first 3 and last 2
        shown = full_narratives[:3]
        if total > 5:
            shown.append(f"... {total - 5} more entries ...")
            shown.extend(full_narratives[-2:])
        elif total > 3:
            shown.extend(full_narratives[3:])

        return summary + "\n\n" + "\n\n".join(shown)

    def process_tables(self, text: str) -> str:
        mode = str(self.options.get("table_mode", "narrative")).lower()
        if mode == "keep":
            return text

        tables = self.detect_markdown_table(text)
        if not tables:
            return text

        lines = text.split("\n")
        for start_line, end_line, table_text in reversed(tables):
            if mode == "strip":
                replacement_lines = [""]
            else:
                narrative = self.table_to_narrative(table_text)
                if narrative:
                    # Mode transition + table intro for cognitive pacing
                    replacement_lines = ["", "... Now, a structured mapping. ...", "", narrative, "", "... Continuing. ...", ""]
                else:
                    replacement_lines = [""]
            lines[start_line:end_line] = replacement_lines

        return "\n".join(lines)

    def optimize_numbers_for_tts(self, text: str) -> str:
        text = re.sub(r"(\d)%", r"\1 percent", text)
        text = re.sub(r"\b(\d+),?000,?000\b", r"\1 million", text)
        text = re.sub(r"\b(\d+),?000\b", r"\1 thousand", text)
        return text

    def extract_tts_blocks(self, text: str) -> Tuple[str, List[str]]:
        tts_pattern = re.compile(r"%%tts\s*(.*?)\s*%%", re.DOTALL | re.IGNORECASE)
        tts_blocks = tts_pattern.findall(text)
        text_with_markers = tts_pattern.sub("<<TTS_BLOCK>>", text)
        return text_with_markers, tts_blocks

    def reinsert_tts_blocks(self, text: str, tts_blocks: List[str]) -> str:
        for block in tts_blocks:
            text = text.replace("<<TTS_BLOCK>>", block.strip(), 1)
        return text.replace("<<TTS_BLOCK>>", "")

    def normalize_greek(self, text: str) -> str:
        for greek, spoken in {**self.greek_lower, **self.greek_upper}.items():
            text = text.replace(greek, f" {spoken} ")
        return text

    def normalize_special_letters(self, text: str) -> str:
        for letter, spoken in self.special_letters.items():
            text = text.replace(letter, f" {spoken} ")
        return text

    def normalize_symbols(self, text: str) -> str:
        for symbol, spoken in self.theophysics_symbols.items():
            text = text.replace(symbol, f" {spoken} ")
        return text

    def normalize_subscripts(self, text: str) -> str:
        for sub, spoken in self.subscripts.items():
            text = text.replace(sub, spoken)
        return text

    def normalize_superscripts(self, text: str) -> str:
        for sup, spoken in self.superscripts.items():
            text = text.replace(sup, spoken)
        return text

    def normalize_axiom_refs(self, text: str) -> str:
        def replace_axiom(match):
            return f" Axiom {match.group(1)} "

        return self.axiom_pattern.sub(replace_axiom, text)

    def normalize_law_refs(self, text: str) -> str:
        law_names = {
            "1": "Law 1, Unity", "2": "Law 2, Duality", "3": "Law 3, Trinity",
            "4": "Law 4, Quaternary Foundation", "5": "Law 5, Quintessence",
            "6": "Law 6, Hexadic Harmony", "7": "Law 7, Septenary Completion",
            "8": "Law 8, Octave Recursion", "9": "Law 9, Ennead Fulfillment",
            "10": "Law 10, Decadic Totality",
        }

        def replace_law(match):
            num = match.group(1)
            return f" {law_names.get(num, f'Law {num}')} "

        return self.law_pattern.sub(replace_law, text)

    def remove_yaml_frontmatter(self, text: str) -> str:
        if text.startswith("---"):
            lines = text.split("\n")
            in_frontmatter = False
            frontmatter_end = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        frontmatter_end = i
                        break

            if frontmatter_end > 0:
                text = "\n".join(lines[frontmatter_end + 1 :])

        text = re.sub(r"^[*]{3,}\s*\n(?:.*?\n)*?[*]{3,}\s*\n", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[+]{3,}\s*\n(?:.*?\n)*?[+]{3,}\s*\n", "", text, flags=re.MULTILINE)
        return text.strip()

    def remove_markdown(self, text: str) -> str:
        if self._enabled("remove_highlights"):
            text = re.sub(r"==([^=]+)==", r"\1", text)

        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)

        # list/callout quote markers while preserving readable content
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        return text

    def clean_whitespace(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        return text.strip()

    def add_cognitive_pacing(self, text: str) -> str:
        """Add breathing room and mode transition signals for TTS clarity.
        
        Handles:
        - Section headers get a pause before and after
        - Dense sequences of structural content get breathing room
        - Theorem/Axiom/Definition markers get announced
        """
        lines = text.split("\n")
        out: List[str] = []
        prev_was_content = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect section-level transitions (lines that were headers, now just text)
            if stripped and not stripped.startswith("..."):
                # Theorem / Axiom / Definition / Constraint markers
                for marker in ["Theorem", "Axiom", "Definition", "Constraint", "Corollary",
                               "Proof", "Conjecture", "Lemma", "Proposition", "Key Result",
                               "Critical", "Kill Condition", "Prediction"]:
                    if stripped.startswith(marker) or stripped.startswith(f"**{marker}"):
                        if prev_was_content:
                            out.append("")  # breathing room before structural marker
                        break

                # Part / Section transitions (Part I, Part II, §1, §2, etc.)
                if re.match(r"^(Part\s+[IVXLCDM]+|§\d+)", stripped):
                    out.append("")
                    out.append(f"... {stripped} ...")
                    out.append("")
                    prev_was_content = False
                    continue

            out.append(line)
            prev_was_content = bool(stripped)

        return "\n".join(out)

    def normalize(self, text: str) -> str:
        if self._enabled("remove_frontmatter"):
            text = self.remove_yaml_frontmatter(text)

        text_with_markers, tts_blocks = self.extract_tts_blocks(text)

        if self._enabled("remove_code_blocks"):
            text_with_markers = self.remove_code_blocks(text_with_markers)
        if self._enabled("remove_images"):
            text_with_markers = self.remove_images(text_with_markers)
        if self._enabled("remove_structural_index_block") or self._enabled("remove_media_callout_block"):
            text_with_markers = self.remove_named_callout_blocks(text_with_markers)
        if self._enabled("remove_callouts"):
            text_with_markers = self.remove_callouts(text_with_markers)
        if self._enabled("remove_footnotes"):
            text_with_markers = self.remove_footnotes(text_with_markers)
        if self._enabled("remove_comments"):
            text_with_markers = self.remove_comments(text_with_markers)

        if self._enabled("process_tables"):
            text_with_markers = self.process_tables(text_with_markers)

        if self._enabled("process_latex_blocks"):
            text_with_markers = self.process_latex_blocks(text_with_markers)

        # Unicode math detection (for docs without $ delimiters)
        text_with_markers = self.process_unicode_math(text_with_markers)

        if self._enabled("remove_markdown_links"):
            text_with_markers = self.remove_markdown_links(text_with_markers)
        if self._enabled("remove_wiki_links"):
            text_with_markers = self.remove_wiki_links(text_with_markers)
        if self._enabled("remove_raw_urls"):
            text_with_markers = self.remove_raw_urls(text_with_markers)

        if self._enabled("dedupe_link_text"):
            text_with_markers = self.dedupe_immediate_phrases(text_with_markers)

        if self._enabled("remove_hashtags"):
            text_with_markers = self.remove_hashtags(text_with_markers)
        if self._enabled("remove_inline_code"):
            text_with_markers = self.remove_inline_code(text_with_markers)
        if self._enabled("remove_html_tags"):
            text_with_markers = self.remove_html_tags(text_with_markers)
        if self._enabled("replace_comparison_symbols"):
            text_with_markers = self.replace_comparison_symbols(text_with_markers)
        if self._enabled("remove_markdown"):
            text_with_markers = self.remove_markdown(text_with_markers)

        text = self.reinsert_tts_blocks(text_with_markers, tts_blocks)

        if self._enabled("normalize_symbols"):
            text = self.normalize_symbols(text)
        if self._enabled("normalize_greek"):
            text = self.normalize_greek(text)
        if self._enabled("normalize_special_letters"):
            text = self.normalize_special_letters(text)
        if self._enabled("normalize_subscripts"):
            text = self.normalize_subscripts(text)
        if self._enabled("normalize_superscripts"):
            text = self.normalize_superscripts(text)
        if self._enabled("normalize_axiom_refs"):
            text = self.normalize_axiom_refs(text)
        if self._enabled("normalize_law_refs"):
            text = self.normalize_law_refs(text)

        # Apply theology-physics bridge translations
        if self.bridge_translations:
            text = self.apply_bridge_concepts(text)
        if self._enabled("optimize_numbers"):
            text = self.optimize_numbers_for_tts(text)
        if self._enabled("dedupe_lines"):
            text = self.dedupe_lines(text)
        if self._enabled("clean_whitespace"):
            text = self.clean_whitespace(text)

        # Cognitive pacing: mode transitions, breathing room
        text = self.add_cognitive_pacing(text)

        return text


_normalizer = None


def get_normalizer() -> TheophysicsNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = TheophysicsNormalizer()
    return _normalizer


def normalize_for_tts(text: str) -> str:
    return get_normalizer().normalize(text)


if __name__ == "__main__":
    test_document = """
# Theophysics Update
Here is an equation: $\\Delta E_{\\text{required}} = T \\cdot \\Delta S$.
And another: $$ \\chi = \\iiint (G \\cdot M) dt $$
A table:
| Variable | Value |
| --- | --- |
| Axiom | A42 |
| Ratio | 3/7 |
"""
    normalizer = TheophysicsNormalizer()
    print(normalizer.normalize(test_document))
