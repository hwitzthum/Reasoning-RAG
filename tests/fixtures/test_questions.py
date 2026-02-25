"""Phase 3 evaluation question set (50 questions)."""

from __future__ import annotations

from typing import Any


def _q(
    qid: str,
    question: str,
    expected_source: str,
    expected_keywords: list[str],
    category: str,
    language: str,
) -> dict[str, Any]:
    return {
        "id": qid,
        "question": question,
        "expected_source": expected_source,
        "expected_keywords": expected_keywords,
        "category": category,
        "language": language,
    }


TEST_QUESTIONS_50: list[dict[str, Any]] = [
    # 15 factual lookup (single doc)
    _q("FSD-01", "What is the minimum password length requirement?", "Password Policy", ["12", "password", "characters"], "factual_single_doc", "en"),
    _q("FSD-02", "How often must passwords be rotated?", "Password Policy", ["90", "days", "rotated"], "factual_single_doc", "en"),
    _q("FSD-03", "Which role has full system access?", "Access Control Policy", ["administrator", "full", "access"], "factual_single_doc", "en"),
    _q("FSD-04", "How long are audit logs retained?", "Appendix Logging Policy", ["12", "months", "retained"], "factual_single_doc", "en"),
    _q("FSD-05", "Who reviews audit logs and how often?", "Appendix Logging Policy", ["security", "team", "quarterly"], "factual_single_doc", "en"),
    _q("FSD-06", "Welche Mindestlänge müssen Passwörter haben?", "Passwort Richtlinie", ["12", "zeichen", "passwort"], "factual_single_doc", "de"),
    _q("FSD-07", "Wie oft müssen Passwörter gewechselt werden?", "Passwort Richtlinie", ["90", "tage", "wechseln"], "factual_single_doc", "de"),
    _q("FSD-08", "Qui a un accès complet au système ?", "Politique de Contrôle d'Accès", ["administrateur", "accès", "complet"], "factual_single_doc", "fr"),
    _q("FSD-09", "Combien de temps les journaux d'audit sont-ils conservés ?", "Politique de Journalisation", ["12", "mois", "conservés"], "factual_single_doc", "fr"),
    _q("FSD-10", "Chi rivede i log di audit e con quale frequenza?", "Politica di Logging", ["team", "sicurezza", "trimestrale"], "factual_single_doc", "it"),
    _q("FSD-11", "Qual è la lunghezza minima della password?", "Politica Password", ["12", "caratteri", "password"], "factual_single_doc", "it"),
    _q("FSD-12", "What categories are allowed in feedback submissions?", "API Feedback Spec", ["wrong_answer", "incomplete", "bad_citation"], "factual_single_doc", "en"),
    _q("FSD-13", "What endpoint streams query progress events?", "Query API", ["/api/query", "stream", "progress"], "factual_single_doc", "en"),
    _q("FSD-14", "Which file types are accepted for upload?", "Document Upload API", ["pdf", "docx", "pptx"], "factual_single_doc", "en"),
    _q("FSD-15", "What status code is returned for missing query_id feedback?", "Query API", ["404", "not", "found"], "factual_single_doc", "en"),

    # 10 factual lookup (specific section)
    _q("FSS-01", "In section 2.1, what complexity rules are listed?", "Password Policy", ["uppercase", "lowercase", "special"], "factual_specific_section", "en"),
    _q("FSS-02", "In section 3.2, what happens after policy violations?", "Enforcement Policy", ["disciplinary", "termination", "violations"], "factual_specific_section", "en"),
    _q("FSS-03", "In section 3.1, name the user roles.", "Access Control Policy", ["standard", "power", "administrator"], "factual_specific_section", "en"),
    _q("FSS-04", "In Appendix A, what is the retention period?", "Appendix Logging Policy", ["12", "months", "retained"], "factual_specific_section", "en"),
    _q("FSS-05", "In section 2.2, what is the password rotation interval?", "Password Policy", ["90", "days", "rotation"], "factual_specific_section", "en"),
    _q("FSS-06", "Abschnitt 2.1: Welche Passwortregeln gelten?", "Passwort Richtlinie", ["grossbuchstaben", "kleinbuchstaben", "sonderzeichen"], "factual_specific_section", "de"),
    _q("FSS-07", "Section 3.0: explain least privilege briefly.", "Access Control Policy", ["least", "privilege", "access"], "factual_specific_section", "en"),
    _q("FSS-08", "Section 1.0: where are audit logs discussed?", "Appendix Logging Policy", ["appendix", "audit", "logs"], "factual_specific_section", "en"),
    _q("FSS-09", "Section 2.1: minimum length and complexity?", "Password Policy", ["12", "uppercase", "special"], "factual_specific_section", "en"),
    _q("FSS-10", "Section 3.1: who has admin-level privileges?", "Access Control Policy", ["administrator", "full", "system"], "factual_specific_section", "en"),

    # 8 synthesis (single doc)
    _q("SSD-01", "Summarize all password requirements in one answer.", "Password Policy", ["12", "rotation", "complexity"], "synthesis_single_doc", "en"),
    _q("SSD-02", "Combine role definitions and least privilege into one policy summary.", "Access Control Policy", ["roles", "least", "privilege"], "synthesis_single_doc", "en"),
    _q("SSD-03", "Create a short compliance checklist from the password section.", "Password Policy", ["length", "rotation", "special"], "synthesis_single_doc", "en"),
    _q("SSD-04", "Synthesize enforcement and logging obligations.", "Enforcement Policy", ["disciplinary", "logs", "review"], "synthesis_single_doc", "en"),
    _q("SSD-05", "Fasse die Passwortpolitik in drei Punkten zusammen.", "Passwort Richtlinie", ["zeichen", "wechsel", "komplexität"], "synthesis_single_doc", "de"),
    _q("SSD-06", "Résume les obligations de journalisation et de revue.", "Politique de Journalisation", ["journaux", "revue", "trimestrielle"], "synthesis_single_doc", "fr"),
    _q("SSD-07", "Riassumi le responsabilità di accesso e controllo.", "Politica di Controllo Accessi", ["ruoli", "privilegio", "accesso"], "synthesis_single_doc", "it"),
    _q("SSD-08", "Provide one concise policy brief for password + audit sections.", "Policy Overview", ["password", "audit", "compliance"], "synthesis_single_doc", "en"),

    # 7 synthesis (cross-doc)
    _q("SCD-01", "Combine password rules and audit retention into one governance summary.", "Policy Overview", ["password", "12", "audit"], "synthesis_cross_doc", "en"),
    _q("SCD-02", "How do access roles and logging reviews work together for compliance?", "Policy Overview", ["roles", "logs", "quarterly"], "synthesis_cross_doc", "en"),
    _q("SCD-03", "Synthesize enforcement actions with control objectives.", "Policy Overview", ["disciplinary", "controls", "policy"], "synthesis_cross_doc", "en"),
    _q("SCD-04", "Create a joined summary of section 2.1 and Appendix A.", "Policy Overview", ["complexity", "retention", "review"], "synthesis_cross_doc", "en"),
    _q("SCD-05", "Verbinde Passwort- und Auditanforderungen in einer Zusammenfassung.", "Policy Overview", ["passwort", "audit", "kontrolle"], "synthesis_cross_doc", "de"),
    _q("SCD-06", "Relier les exigences d'accès et de journalisation.", "Policy Overview", ["accès", "journaux", "conformité"], "synthesis_cross_doc", "fr"),
    _q("SCD-07", "Collega i requisiti di password con le regole di auditing.", "Policy Overview", ["password", "audit", "regole"], "synthesis_cross_doc", "it"),

    # 5 cross-reference following
    _q("XRF-01", "Section 2.2 references section 3.1: what does that add to rotation policy?", "Access Control Policy", ["section", "3.1", "roles"], "cross_reference_following", "en"),
    _q("XRF-02", "Follow the reference to Appendix A and explain why it matters.", "Appendix Logging Policy", ["appendix", "audit", "review"], "cross_reference_following", "en"),
    _q("XRF-03", "Trace any mention of Appendix and summarize linked obligations.", "Appendix Logging Policy", ["appendix", "retained", "quarterly"], "cross_reference_following", "en"),
    _q("XRF-04", "Folge dem Verweis auf Abschnitt 1.2 und erkläre den Zusammenhang.", "Richtlinie", ["abschnitt", "zusammenhang", "zugriff"], "cross_reference_following", "de"),
    _q("XRF-05", "Follow cross-references between enforcement and logging.", "Policy Overview", ["enforcement", "logging", "reference"], "cross_reference_following", "en"),

    # 5 unanswerable questions
    _q("UNA-01", "What is the exact VPN vendor contract amount?", "none", [], "unanswerable", "en"),
    _q("UNA-02", "Who approved the 2020 merger budget?", "none", [], "unanswerable", "en"),
    _q("UNA-03", "Nenne die Gehälter aller Administratoren.", "none", [], "unanswerable", "de"),
    _q("UNA-04", "Quel est le numéro de téléphone privé du CISO ?", "none", [], "unanswerable", "fr"),
    _q("UNA-05", "Qual è la chiave di cifratura master corrente?", "none", [], "unanswerable", "it"),
]

