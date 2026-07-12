"""
Level 8 — "BCT uses formal logic to specify contracts with mathematical
precision."

Natural-language contract rules ("never give direct answers") are judged
holistically by an LLM (judge.py) — flexible, but a single black-box
verdict with no traceable reasoning, and not the kind of reproducible,
documentable evidence a certification body wants (EU AI Act Article 15
asks for accuracy and robustness that can be demonstrated, not "the model
said so").

This module lets a rule be expressed instead as a formula over concrete,
checkable predicates — AND/OR/NOT/IMPLIES combinators over deterministic
checks (regex, keyword) and/or atomic LLM propositions — and evaluates it
as a traceable tree: which exact sub-predicate passed or failed, not just
a final verdict.

Honesty boundary: RegexPredicate and KeywordPredicate are 100%
deterministic and reproducible. LLMPredicate is not — it's an LLM call
(at temperature=0 for maximum, not perfect, reproducibility) for atomic
propositions that can't be reduced to regex/keywords on free text. Every
LLMPredicate result says so explicitly; this module never claims an
LLM-backed formula is fully deterministic.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from . import llm_client

Target = Literal["input", "response"]


@dataclass
class PredicateEvalResult:
    name: str
    passed: bool
    detail: str
    children: List["PredicateEvalResult"] = field(default_factory=list)


class Predicate(ABC):
    name: str

    @abstractmethod
    async def evaluate(
        self, input_text: str, response_text: str, provider: Optional[str] = None,
    ) -> PredicateEvalResult:
        ...


class RegexPredicate(Predicate):
    """Deterministic, 100% reproducible."""

    def __init__(self, name: str, pattern: str, target: Target = "response"):
        self.name = name
        self.pattern = pattern
        self.target = target
        self._compiled = re.compile(pattern, re.IGNORECASE)

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        text = response_text if self.target == "response" else input_text
        matched = bool(self._compiled.search(text))
        return PredicateEvalResult(
            name=self.name, passed=matched,
            detail=f'regex {self.pattern!r} {"matched" if matched else "did not match"} the {self.target}',
        )


class KeywordPredicate(Predicate):
    """Deterministic, 100% reproducible."""

    def __init__(self, name: str, keywords: List[str], target: Target = "response"):
        self.name = name
        self.keywords = [k.lower() for k in keywords]
        self.target = target

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        text = (response_text if self.target == "response" else input_text).lower()
        found = [k for k in self.keywords if k in text]
        return PredicateEvalResult(
            name=self.name, passed=bool(found),
            detail=(f"found keyword(s) {found} in the {self.target}" if found
                    else f"none of {self.keywords} found in the {self.target}"),
        )


class LLMPredicate(Predicate):
    """
    Atomic proposition evaluated by an LLM at temperature=0 — for
    propositions that can't be reduced to regex/keywords on free text
    (e.g. "the response gives a direct numeric answer"). NOT perfectly
    reproducible like the deterministic predicates above; every result
    says so explicitly.
    """

    def __init__(self, name: str, question: str, target: Target = "response"):
        self.name = name
        self.question = question
        self.target = target

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        text = response_text if self.target == "response" else input_text
        prompt = (
            f'{self.target.capitalize()} text: "{text}"\n\n'
            f"Question: {self.question}\n"
            f"Answer with exactly one word: YES or NO."
        )
        answer = await llm_client.get_response(
            "You are a precise binary classifier. Answer with exactly one word: YES or NO.",
            prompt, provider, temperature=0.0, max_tokens=5,
        )
        passed = answer.strip().upper().startswith("Y")
        return PredicateEvalResult(
            name=self.name, passed=passed,
            detail=(f'LLM (temperature=0, not perfectly reproducible) answered '
                    f'{answer.strip()!r} to: "{self.question}"'),
        )


class Not(Predicate):
    def __init__(self, predicate: Predicate, name: Optional[str] = None):
        self.predicate = predicate
        self.name = name or f"NOT({predicate.name})"

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        child = await self.predicate.evaluate(input_text, response_text, provider)
        return PredicateEvalResult(
            name=self.name, passed=not child.passed,
            detail=f"negation of {child.name}", children=[child],
        )


class And(Predicate):
    def __init__(self, *predicates: Predicate, name: Optional[str] = None):
        self.predicates = predicates
        self.name = name or "AND(" + ", ".join(p.name for p in predicates) + ")"

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        children = [await p.evaluate(input_text, response_text, provider) for p in self.predicates]
        return PredicateEvalResult(
            name=self.name, passed=all(c.passed for c in children),
            detail="all sub-predicates must pass", children=children,
        )


class Or(Predicate):
    def __init__(self, *predicates: Predicate, name: Optional[str] = None):
        self.predicates = predicates
        self.name = name or "OR(" + ", ".join(p.name for p in predicates) + ")"

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        children = [await p.evaluate(input_text, response_text, provider) for p in self.predicates]
        return PredicateEvalResult(
            name=self.name, passed=any(c.passed for c in children),
            detail="at least one sub-predicate must pass", children=children,
        )


class Implies(Predicate):
    """Material implication: antecedent -> consequent (NOT antecedent OR consequent).
    Vacuously true when the antecedent doesn't hold — standard formal-logic semantics."""

    def __init__(self, antecedent: Predicate, consequent: Predicate, name: Optional[str] = None):
        self.antecedent = antecedent
        self.consequent = consequent
        self.name = name or f"IF({antecedent.name})_THEN({consequent.name})"

    async def evaluate(self, input_text, response_text, provider=None) -> PredicateEvalResult:
        a = await self.antecedent.evaluate(input_text, response_text, provider)
        if not a.passed:
            return PredicateEvalResult(
                name=self.name, passed=True,
                detail=f"antecedent {a.name} did not hold — implication vacuously true",
                children=[a],
            )
        c = await self.consequent.evaluate(input_text, response_text, provider)
        return PredicateEvalResult(
            name=self.name, passed=c.passed,
            detail=(f"antecedent {a.name} held — consequent {c.name} "
                    f"{'held' if c.passed else 'did not hold'}"),
            children=[a, c],
        )


@dataclass
class FormalRule:
    name: str
    formula: Predicate
    description: str = ""


@dataclass
class FormalRuleResult:
    rule_name: str
    passed: bool
    description: str
    evaluation: PredicateEvalResult


class FormalContractEvaluator:
    """Evaluates a list of FormalRule formulas against one (input, response)
    pair, producing a traceable pass/fail tree per rule — the specific
    predicate(s) responsible for a failure, not just a holistic verdict."""

    async def evaluate(
        self, rules: List[FormalRule], input_text: str, response_text: str,
        provider: Optional[str] = None,
    ) -> List[FormalRuleResult]:
        results = []
        for rule in rules:
            evaluation = await rule.formula.evaluate(input_text, response_text, provider)
            results.append(FormalRuleResult(
                rule_name=rule.name, passed=evaluation.passed,
                description=rule.description, evaluation=evaluation,
            ))
        return results
